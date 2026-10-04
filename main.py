"""
main.py - Tkinter user interface for the P2P network.

Run with:  python main.py
"""

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from p2p_node import P2PNode, get_local_ip


class App:
    def __init__(self, root):
        self.root = root
        self.node = None
        self.peer_ids = []          
        self.events = queue.Queue()  

        root.title("UAP P2P Network")
        root.geometry("900x620")
        root.minsize(760, 520)
        self._build_ui()
        self._set_running(False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(100, self._poll_events)

    # ----------------------------------------------------------- layout
    def _build_ui(self):
        pad = {"padx": 6, "pady": 4}

        # My Peer
        me = ttk.LabelFrame(self.root, text="My Peer")
        me.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(me, text="Name:").grid(row=0, column=0, **pad)
        self.name_var = tk.StringVar(value="Alice")
        self.name_entry = ttk.Entry(me, textvariable=self.name_var, width=18)
        self.name_entry.grid(row=0, column=1, **pad)
        ttk.Label(me, text="Port:").grid(row=0, column=2, **pad)
        self.port_var = tk.StringVar(value="5000")
        self.port_entry = ttk.Entry(me, textvariable=self.port_var, width=8)
        self.port_entry.grid(row=0, column=3, **pad)
        self.start_btn = ttk.Button(me, text="Start Peer", command=self.start_peer)
        self.start_btn.grid(row=0, column=4, **pad)
        self.stop_btn = ttk.Button(me, text="Stop", command=self.stop_peer)
        self.stop_btn.grid(row=0, column=5, **pad)
        self.info_var = tk.StringVar(value="Peer not started")
        ttk.Label(me, textvariable=self.info_var).grid(
            row=1, column=0, columnspan=6, sticky="w", **pad)

        # Connect
        con = ttk.LabelFrame(self.root, text="Connect to Another Peer")
        con.pack(fill="x", padx=8, pady=4)
        ttk.Label(con, text="IP:").grid(row=0, column=0, **pad)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        self.ip_entry = ttk.Entry(con, textvariable=self.ip_var, width=18)
        self.ip_entry.grid(row=0, column=1, **pad)
        ttk.Label(con, text="Port:").grid(row=0, column=2, **pad)
        self.rport_var = tk.StringVar(value="5001")
        self.rport_entry = ttk.Entry(con, textvariable=self.rport_var, width=8)
        self.rport_entry.grid(row=0, column=3, **pad)
        self.connect_btn = ttk.Button(con, text="Connect", command=self.connect_peer)
        self.connect_btn.grid(row=0, column=4, **pad)

        file_f = ttk.LabelFrame(self.root, text="Send File")
        file_f.pack(side="bottom", fill="x", padx=8, pady=(4, 8))
        ttk.Label(file_f, text="Text, image, audio, video, PDF, ZIP, etc.").pack(
            side="left", **pad)
        self.file_btn = ttk.Button(file_f, text="Choose File & Send",
                                   command=self.choose_and_send_file)
        self.file_btn.pack(side="right", **pad)

        text_f = ttk.LabelFrame(self.root, text="Send Text")
        text_f.pack(side="bottom", fill="x", padx=8, pady=4)
        self.msg_var = tk.StringVar()
        self.msg_entry = ttk.Entry(text_f, textvariable=self.msg_var)
        self.msg_entry.pack(side="left", fill="x", expand=True, **pad)
        self.msg_entry.bind("<Return>", lambda e: self.send_text())
        self.send_btn = ttk.Button(text_f, text="Send", command=self.send_text)
        self.send_btn.pack(side="right", **pad)
        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=True, padx=8, pady=4)

        peers_f = ttk.LabelFrame(mid, text="Connected Peers")
        peers_f.pack(side="left", fill="y")
        self.peer_list = tk.Listbox(peers_f, width=34, exportselection=False)
        self.peer_list.pack(fill="both", expand=True, padx=4, pady=4)

        log_f = ttk.LabelFrame(mid, text="Messages / Events")
        log_f.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.log = tk.Text(log_f, state="disabled", wrap="word",
                           font=("Courier New", 10))
        scroll = ttk.Scrollbar(log_f, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)
        self.log.tag_configure("error", foreground="#b00020")
        self.log.tag_configure("system", foreground="#555555")

    def _set_running(self, running):
        idle = "disabled" if running else "normal"
        active = "normal" if running else "disabled"
        for w in (self.name_entry, self.port_entry, self.start_btn):
            w.configure(state=idle)
        for w in (self.stop_btn, self.ip_entry, self.rport_entry,
                  self.connect_btn, self.msg_entry, self.send_btn,
                  self.file_btn):
            w.configure(state=active)

    def _on_node_event(self, text):    
        self.events.put(("log", text))

    def _on_peers_changed(self):         
        self.events.put(("peers", None))

    def _poll_events(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "log":
                    self._append_log(data)
                else:
                    self._refresh_peers()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _append_log(self, text):
        tag = ("error" if text.startswith("[ERROR]")
               else "system" if text.startswith("[SYSTEM]") else "")
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _refresh_peers(self):
        selected = self._selected_peer_id()
        self.peer_list.delete(0, "end")
        self.peer_ids = []
        peers = self.node.get_peers() if self.node else []
        for p in peers:
            self.peer_list.insert("end", f"{p.label}  {p.address}")
            self.peer_ids.append(p.peer_id)
            if p.peer_id == selected:
                self.peer_list.selection_set("end")

    def _selected_peer_id(self):
        sel = self.peer_list.curselection()
        if sel and sel[0] < len(self.peer_ids):
            return self.peer_ids[sel[0]]
        return None

    def start_peer(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a peer name.")
            return
        try:
            port = int(self.port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Port must be a number from 1 to 65535.")
            return
        node = P2PNode(name, port, on_event=self._on_node_event,
                       on_peers_changed=self._on_peers_changed)
        try:
            node.start()
        except OSError as exc:
            messagebox.showerror("Error", f"Could not start peer on port {port}:\n{exc}")
            return
        self.node = node
        self.info_var.set(f"{name} | ID: {node.peer_id} | Port: {port} | "
                          f"My IP: {get_local_ip()}")
        self._set_running(True)

    def stop_peer(self):
        if self.node:
            self.node.stop()
            self.node = None
        self.info_var.set("Peer not started")
        self._set_running(False)
        self._refresh_peers()

    def connect_peer(self):
        if not self.node:
            return
        ip, port = self.ip_var.get(), self.rport_var.get()
        threading.Thread(target=self.node.connect, args=(ip, port),
                         daemon=True).start()

    def send_text(self):
        if not self.node:
            return
        peer_id = self._selected_peer_id()
        if peer_id is None:
            self._append_log("[ERROR] Select a peer from the list first")
            return
        text = self.msg_var.get().strip()
        if not text:
            return
        self.msg_var.set("")
        threading.Thread(target=self.node.send_text, args=(peer_id, text),
                         daemon=True).start()

    def choose_and_send_file(self):
        if not self.node:
            return
        peer_id = self._selected_peer_id()
        if peer_id is None:
            self._append_log("[ERROR] Select a peer from the list first")
            return
        path = filedialog.askopenfilename(title="Choose a file to send")
        if not path:
            return
        self._append_log("[SYSTEM] Sending file...")
        threading.Thread(target=self.node.send_file, args=(peer_id, path),
                         daemon=True).start()

    def _on_close(self):
        if self.node:
            self.node.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
