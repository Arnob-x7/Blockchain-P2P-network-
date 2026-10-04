
import ipaddress
import os
import socket
import threading
import uuid

import protocol
from protocol import ProtocolError

CONNECT_TIMEOUT = 5
HANDSHAKE_TIMEOUT = 10 


def get_local_ip() -> str:

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class Peer:


    def __init__(self, sock, ip, peer_id, name, listen_port):
        self.sock = sock
        self.ip = ip
        self.peer_id = peer_id
        self.name = name
        self.listen_port = listen_port
        self.send_lock = threading.Lock()

    @property
    def label(self):
        return f"{self.name} [{self.peer_id}]"

    @property
    def address(self):
        return f"{self.ip}:{self.listen_port}"


class P2PNode:
    def __init__(self, name, port, on_event=None, on_peers_changed=None,
                 download_dir="downloads", host="0.0.0.0"):
        self.name = name.strip()
        self.port = port
        self.host = host
        self.peer_id = uuid.uuid4().hex[:8]
        self.download_dir = download_dir
        self.on_event = on_event or print
        self.on_peers_changed = on_peers_changed or (lambda: None)

        self.server_socket = None
        self.running = False
        self.peers = {}              
        self._lock = threading.Lock() 

    def _log(self, text):
        self.on_event(text)

    def get_peers(self):
        with self._lock:
            return list(self.peers.values())

    def _find_peer(self, peer_id):
        with self._lock:
            return self.peers.get(peer_id)

    def start(self):
        if not self.name:
            raise ValueError("Peer name cannot be empty")
        if not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ValueError("Port must be a number between 1 and 65535")

        os.makedirs(self.download_dir, exist_ok=True)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self.host, self.port)) 
            server.listen()                       
        except OSError:
            server.close()
            raise
        self.server_socket = server
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        self._log(f"[SYSTEM] Peer started: {self.name} [{self.peer_id}] "
                  f"on port {self.port}")

    def stop(self):
        if not self.running:
            return
        self.running = False
        try:
            self.server_socket.close()
        except OSError:
            pass
        for peer in self.get_peers():
            self._drop_peer(peer, announce=False)
        self._log("[SYSTEM] Peer stopped")
        self.on_peers_changed()

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
            except OSError:
                break 
            threading.Thread(target=self._handle_incoming,
                             args=(conn, addr), daemon=True).start()

    def _handle_incoming(self, conn, addr):
        try:
            conn.settimeout(HANDSHAKE_TIMEOUT)
            hello = protocol.recv_message(conn)
            ident = self._parse_identity(hello, protocol.HELLO)
            peer = Peer(conn, addr[0], *ident)
            if not self._add_peer(peer):
                conn.close()
                return
            protocol.send_message(conn, protocol.make_hello(
                protocol.HELLO_ACK, self.peer_id, self.name, self.port))
            conn.settimeout(None)
        except (OSError, ProtocolError) as exc:
            self._log(f"[ERROR] Incoming connection from {addr[0]} failed: {exc}")
            conn.close()
            return
        self._log(f"[SYSTEM] Connected to {peer.name}")
        self._listen_to_peer(peer)
    def connect(self, ip, port):
        if not self.running:
            self._log("[ERROR] Start your peer before connecting")
            return False
        try:
            ip = str(ipaddress.ip_address(str(ip).strip()))
        except ValueError:
            self._log("[ERROR] Invalid IP address")
            return False
        try:
            port = int(port)
            if not 1 <= port <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            self._log("[ERROR] Invalid port (must be 1-65535)")
            return False
        for p in self.get_peers():
            if p.ip == ip and p.listen_port == port:
                self._log(f"[ERROR] Already connected to {p.name}")
                return False

        sock = None
        try:
            sock = socket.create_connection((ip, port), timeout=CONNECT_TIMEOUT)
            protocol.send_message(sock, protocol.make_hello(
                protocol.HELLO, self.peer_id, self.name, self.port))
            reply = protocol.recv_message(sock)
            ident = self._parse_identity(reply, protocol.HELLO_ACK)
            sock.settimeout(None)
            if ident[0] == self.peer_id:
                raise ProtocolError("cannot connect to yourself")
            peer = Peer(sock, ip, *ident)
            if not self._add_peer(peer):
                raise ProtocolError("already connected to this peer")
        except ConnectionRefusedError:
            self._log("[ERROR] Connection failed: Connection refused "
                      "(is the peer running?)")
            return self._fail(sock)
        except (OSError, ProtocolError) as exc:
            self._log(f"[ERROR] Connection failed: {exc}")
            return self._fail(sock)

        self._log(f"[SYSTEM] Connected to {peer.name} ({peer.address})")
        threading.Thread(target=self._listen_to_peer, args=(peer,),
                         daemon=True).start()
        return True

    @staticmethod
    def _fail(sock):
        if sock:
            sock.close()
        return False
    @staticmethod
    def _parse_identity(msg, expected_type):
        if msg.get("type") != expected_type:
            raise ProtocolError(f"expected '{expected_type}', "
                                f"got '{msg.get('type')}'")
        peer_id, name, port = (msg.get("peer_id"), msg.get("peer_name"),
                               msg.get("port"))
        if (not isinstance(peer_id, str) or not isinstance(name, str)
                or not isinstance(port, int) or not peer_id or not name):
            raise ProtocolError("invalid handshake data")
        return peer_id, name, port

    def _add_peer(self, peer):
        with self._lock:
            if peer.peer_id == self.peer_id or peer.peer_id in self.peers:
                return False
            self.peers[peer.peer_id] = peer
        self.on_peers_changed()
        return True

    def _drop_peer(self, peer, announce=True, reason=None):
        with self._lock:
            removed = self.peers.get(peer.peer_id) is peer
            if removed:
                del self.peers[peer.peer_id]
        try:
            peer.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            peer.sock.close()
        except OSError:
            pass
        if removed:
            if announce:
                extra = f" ({reason})" if reason else ""
                self._log(f"[SYSTEM] {peer.name} disconnected{extra}")
            self.on_peers_changed()

    def _listen_to_peer(self, peer):
        reason = None
        try:
            while self.running:
                msg = protocol.recv_message(peer.sock)
                kind = msg["type"]
                if kind == protocol.TEXT:
                    self._log(f"{peer.name} -> You: {msg.get('message', '')}")
                elif kind == protocol.FILE:
                    self._receive_file(peer, msg)
                else:
                    self._log(f"[ERROR] Unknown message type '{kind}' "
                              f"from {peer.name}")
        except (OSError, ProtocolError) as exc:
            reason = str(exc)
        finally:
            self._drop_peer(peer, reason=reason)

    def _receive_file(self, peer, msg):
        filename = os.path.basename(str(msg.get("filename", "")).replace("\\", "/"))
        filename = filename or "received_file"
        size = msg.get("filesize")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ProtocolError("invalid file size")   # stream is unreliable now

        path = self._unique_path(filename)
        remaining = size
        try:
            with open(path, "wb") as f:
                while remaining > 0:   # filesize tells us when to stop
                    chunk = peer.sock.recv(min(protocol.CHUNK_SIZE, remaining))
                    if not chunk:
                        raise ConnectionError("connection lost during file transfer")
                    f.write(chunk)
                    remaining -= len(chunk)
        except Exception:
            if os.path.exists(path):
                os.remove(path)   # don't keep half-received files
            raise
        self._log(f"{peer.name} -> You: File received: {os.path.basename(path)} "
                  f"({size} bytes) saved to {path}")

    def _unique_path(self, filename):
        path = os.path.join(self.download_dir, filename)
        base, ext = os.path.splitext(filename)
        n = 1
        while os.path.exists(path): 
            path = os.path.join(self.download_dir, f"{base}_{n}{ext}")
            n += 1
        return path

    def send_text(self, peer_id, text):
        peer = self._find_peer(peer_id)
        if peer is None:
            self._log("[ERROR] Select a connected peer first")
            return False
        try:
            with peer.send_lock:
                protocol.send_message(peer.sock, protocol.make_text(
                    self.peer_id, self.name, text))
        except OSError as exc:
            self._log(f"[ERROR] Could not send to {peer.name}: {exc}")
            self._drop_peer(peer, reason=str(exc))
            return False
        self._log(f"You -> {peer.name}: {text}")
        return True

    def send_file(self, peer_id, path):
        peer = self._find_peer(peer_id)
        if peer is None:
            self._log("[ERROR] Select a connected peer first")
            return False
        if not path or not os.path.isfile(path):
            self._log(f"[ERROR] File does not exist: {path}")
            return False
        try:
            size = os.path.getsize(path)
            name = os.path.basename(path)
            with peer.send_lock:
                protocol.send_message(peer.sock, protocol.make_file(
                    self.peer_id, self.name, name, size))
                sent = 0
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(protocol.CHUNK_SIZE)
                        if not chunk:
                            break
                        peer.sock.sendall(chunk)
                        sent += len(chunk)
                if sent != size:
                    raise OSError("file changed while sending")
        except OSError as exc:
            self._log(f"[ERROR] File transfer to {peer.name} failed: {exc}")
            self._drop_peer(peer, reason=str(exc))
            return False
        self._log(f"You -> {peer.name}: File sent: {name} ({size} bytes)")
        return True
