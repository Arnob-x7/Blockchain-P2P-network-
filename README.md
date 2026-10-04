# P2P Network – Communication and File Sharing

**Course:** CSE 433 – Blockchain & Distributed Security Lab, University of Asia Pacific
**Student:** _<Arnab Paul>_  |  **ID:** _<22201204>_  |  **Section:** _<D2>_

## 1. Project description

A lightweight peer-to-peer application written in Python using TCP sockets.
Each running copy of the program is one **peer**. A peer is both:

- a **TCP server** – it listens on a port and accepts connections, and
- a **TCP client** – it can connect to other peers by IP address and port.

Peers talk to each other **directly**, with no central server. Once connected
they can exchange text messages and any ordinary file (text, image, audio,
video, PDF, ZIP ...), because files are treated as raw binary data.

### Project structure

```
P2P_Network/
|-- main.py          Tkinter GUI (user interaction)
|-- p2p_node.py      Networking: server + client roles, threads, text, file transfer
|-- protocol.py      Message framing and message builders
|-- requirements.txt (no third-party packages)
|-- downloads/       Received files are saved here
`-- README.md
```

### How it works

| Stage | What happens |
|---|---|
| Connect | Peer B opens a TCP connection to `IP:port` of Peer A (`connect()` / `accept()`). |
| Handshake | B sends `hello` (id, name, port); A replies `hello_ack`. Both now know who the other is. |
| Framing | Every JSON message is sent as `[4-byte length][JSON]`; the receiver reads exactly that many bytes. |
| Text | `{"type":"text", "sender_id", "sender_name", "message"}` |
| File | Framed `file` metadata (`filename`, `filesize`) followed by exactly `filesize` raw bytes, sent/received in 64 KB chunks. |
| Threads | One thread per connection, plus one thread accepting new connections. |

## 2. Requirements

- Python **3.9 or later** (tested on 3.12)
- Tkinter (included with the standard Windows/macOS installers; on Linux install it, see below)
- No third-party packages – `requirements.txt` is intentionally empty.

## 3. Installation / setup

1. Install Python 3.9+ from <https://www.python.org>. On Windows, tick **"Add Python to PATH"**.
2. On Ubuntu/Debian only, if you get `No module named 'tkinter'`:
   ```
   sudo apt install python3-tk
   ```
3. Unzip the project and open a terminal inside the project folder.

## 4. How to run

```
python main.py
```

(Use `python3 main.py` on Linux/macOS.) To run several peers on one computer,
open several terminals and run the command in each.

## 5. How to connect two peers

**On the same computer**

| | Peer A | Peer B |
|---|---|---|
| Name | Alice | Bob |
| Port | 5000 | 5001 |

1. In window A: enter name `Alice`, port `5000`, click **Start Peer**.
2. In window B: enter name `Bob`, port `5001`, click **Start Peer**.
3. In window B, under *Connect to Another Peer*: IP `127.0.0.1`, Port `5000`, click **Connect**.
4. Both windows now list the other peer under **Connected Peers**.

**On two computers (same Wi-Fi / LAN)**

1. Start Peer A on computer A. Its LAN IP is shown in the "My Peer" panel (e.g. `192.168.1.10`).
2. Start Peer B on computer B.
3. On computer B connect to `192.168.1.10` and port `5000`.
4. If it fails, allow Python through the firewall on computer A (Windows Defender Firewall: allow
   *Python* on **Private networks**), and make sure both computers are on the same network.

**More peers:** start Peer C (e.g. port `5002`) and connect it to A and to B.
Connections are not forwarded automatically, so connect each pair that should communicate.

## 6. How to send text and files

1. **Click a peer** in the *Connected Peers* list to select it.
2. **Text:** type in *Send Text* and press **Send** (or Enter).
3. **File:** click **Choose File & Send** and pick any file.
4. The receiving peer saves the file in the `downloads/` folder next to `main.py`
   (if a file with the same name exists, `_1`, `_2` ... is added; nothing is overwritten).

## 7. Error handling

Invalid IP / port, connection refused, peer not running, peer disconnecting
(also in the middle of a file), missing file, and sending without selecting a
peer are all reported in the event log, for example:

```
[ERROR] Connection failed: Connection refused (is the peer running?)
```

The program does not crash when a peer disconnects; the peer is simply removed from the list.

## 8. Example screenshots

_Insert your own screenshots here (Peer 1, Peer 2, Peer 3 windows showing connected peers, messages and a received file)._

```
![Peer 1](screenshots/peer1.png)
![Peer 2](screenshots/peer2.png)
![Peer 3](screenshots/peer3.png)
```
