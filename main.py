#!/usr/bin/env python3
"""
NeoPixel Segment Controller (responsive UI)
Segments: 0=8 LEDs, 1-4=9 LEDs (total 44 on one data line, pin 8)

Features:
- COM dropdown + Refresh + Baud
- Connect / Disconnect
- Global ALL ON/OFF and ALL Color
- Per-segment RGB sliders (1..255), live preview, Set / ON / OFF
- Fully resizable: sliders and panels expand with the window

Protocol (newline-terminated):
  S,<sid>,R,G,B       -> set entire segment sid
  P,<sid>,<idx>,R,G,B -> set pixel idx in segment sid (optional)
  A,R,G,B             -> set all LEDs
  "0" / "1"           -> all off / all white
"""

import time
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports

BAUD_DEFAULT = 9600
DEBOUNCE_MS = 120
SEG_LENS = [8, 9, 9, 9, 9]  # sid 0..4

# ---------------- Serial Bridge ----------------
class SerialBridge:
    def __init__(self):
        self.ser = None
    def open(self, port, baud):
        self.close()
        self.ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2.0)  # Uno auto-reset
    def close(self):
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass
        self.ser = None
    def send_line(self, text):
        if not (self.ser and self.ser.is_open):
            return False
        if not text.endswith("\n"):
            text += "\n"
        self.ser.write(text.encode("ascii"))
        self.ser.flush()
        return True

# --------------- Segment Control Widget ---------------
class SegmentControl(ttk.LabelFrame):
    def __init__(self, master, sid: int, led_count: int, send_func, *args, **kwargs):
        super().__init__(master, text=f"Segment {sid} ({led_count} LEDs)", padding=8, *args, **kwargs)
        self.sid = sid
        self.send_func = send_func
        self.after_id = None
        self.last_sent = (255, 1, 128)

        # StringVars so entries tolerate empty text
        self.r_var = tk.StringVar(value="255")
        self.g_var = tk.StringVar(value="1")
        self.b_var = tk.StringVar(value="128")

        # Layout with grid so it stretches
        self.columnconfigure(0, weight=1)   # left column (sliders) expands
        self.columnconfigure(1, weight=0)   # right column (swatch/buttons) fixed

        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(1, weight=1)   # scale column inside each row expands

        self._mk_slider(left, "R", self.r_var, row=0)
        self._mk_slider(left, "G", self.g_var, row=1)
        self._mk_slider(left, "B", self.b_var, row=2)

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="n", padx=(12,0))
        ttk.Label(right, text="Preview").grid(row=0, column=0, pady=(0,4))
        self.swatch = tk.Canvas(right, width=90, height=70, bg="#ff0180",
                                highlightthickness=1, highlightbackground="#777")
        self.swatch.grid(row=1, column=0, pady=(0,6))
        ttk.Button(right, text="Set", command=self.send_now).grid(row=2, column=0, sticky="ew")
        btns = ttk.Frame(right)
        btns.grid(row=3, column=0, sticky="ew", pady=(6,0))
        ttk.Button(btns, text="ON", command=self.on).grid(row=0, column=0, sticky="ew", padx=(0,4))
        ttk.Button(btns, text="OFF", command=self.off).grid(row=0, column=1, sticky="ew")
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        self._update_swatch()

    def _mk_slider(self, parent, label, var, row):
        r = ttk.Label(parent, text=label, width=2)
        r.grid(row=row, column=0, sticky="w", padx=(0,8), pady=2)

        scale = ttk.Scale(parent, from_=1, to=255, orient="horizontal",
                          command=lambda v, V=var: self._on_scale(V, v))
        scale.grid(row=row, column=1, sticky="ew", pady=2)  # expands horizontally with window

        entry = ttk.Entry(parent, textvariable=var, width=5, justify="right")
        entry.grid(row=row, column=2, sticky="e", padx=(8,0))

        def on_entry_change(*_):
            val = self._parse_entry(var.get())
            if val is None:
                return
            clamped = max(1, min(255, val))
            if str(clamped) != var.get():
                var.set(str(clamped))
            scale.set(clamped)
            self._update_swatch(); self._schedule_send()

        var.trace_add("write", on_entry_change)
        init_val = self._parse_entry(var.get())
        scale.set(init_val if init_val is not None else 1)

    def _on_scale(self, var, raw_value):
        try:
            v = int(float(raw_value))
        except Exception:
            return
        v = max(1, min(255, v))
        if var.get() != str(v):
            var.set(str(v))  # triggers entry trace
        else:
            self._update_swatch(); self._schedule_send()

    def _parse_entry(self, text):
        t = text.strip()
        if not t or not t.isdigit(): return None
        try: return int(t)
        except Exception: return None

    def _rgb(self):
        def val_or(last, s):
            t = self._parse_entry(s)
            return t if t is not None else last
        r = max(1, min(255, val_or(self.last_sent[0], self.r_var.get())))
        g = max(1, min(255, val_or(self.last_sent[1], self.g_var.get())))
        b = max(1, min(255, val_or(self.last_sent[2], self.b_var.get())))
        return (r, g, b)

    def _update_swatch(self):
        r, g, b = self._rgb()
        self.swatch.configure(bg=f"#{r:02x}{g:02x}{b:02x}")

    def _schedule_send(self):
        if self.after_id: self.after_cancel(self.after_id)
        self.after_id = self.after(DEBOUNCE_MS, self.send_now)

    def send_now(self):
        self.after_id = None
        r, g, b = self._rgb()
        if (r, g, b) == self.last_sent:
            return
        if self.send_func(f"S,{self.sid},{r},{g},{b}"):
            self.last_sent = (r, g, b)

    def on(self):
        if self.send_func(f"S,{self.sid},255,255,255"):
            self.r_var.set("255"); self.g_var.set("255"); self.b_var.set("255")
            self.last_sent = (255,255,255); self._update_swatch()

    def off(self):
        if self.send_func(f"S,{self.sid},0,0,0"):
            self.last_sent = (0,0,0)
            self.swatch.configure(bg="#000000")

# ---------------- Main App ----------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NeoPixel Segments (8, 9, 9, 9, 9) — Responsive")
        self.geometry("1100x720")            # initial size
        self.minsize(900, 600)               # sensible minimum
        # resizable is True by default; keep it that way

        self.bridge = SerialBridge()
        self._label_to_dev = {}

        # Root uses grid so content stretches
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)  # main grid area grows

        # Top bar
        top = ttk.Frame(self, padding=(10,10,10,6))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(3, weight=1)  # allow the combo to stretch

        ttk.Label(top, text="Serial Port:").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=(6,6))
        ttk.Button(top, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=(0,6))
        ttk.Label(top, text="Baud:").grid(row=0, column=3, sticky="e", padx=(12,4))
        self.baud_var = tk.StringVar(value=str(BAUD_DEFAULT))
        self.baud_entry = ttk.Entry(top, textvariable=self.baud_var, width=8, justify="right")
        self.baud_entry.grid(row=0, column=4, sticky="w", padx=(0,8))
        self.btn_connect = ttk.Button(top, text="Connect", command=self.connect)
        self.btn_connect.grid(row=0, column=5, padx=(0,6))
        self.btn_disconnect = ttk.Button(top, text="Disconnect", command=self.disconnect, state="disabled")
        self.btn_disconnect.grid(row=0, column=6)

        # Global controls
        globalf = ttk.Frame(self, padding=(10,4,10,6))
        globalf.grid(row=1, column=0, sticky="ew")
        globalf.columnconfigure(3, weight=1)
        ttk.Button(globalf, text="ALL ON (White)", command=lambda: self.send_line("1")).grid(row=0, column=0, sticky="w")
        ttk.Button(globalf, text="ALL OFF", command=lambda: self.send_line("0")).grid(row=0, column=1, sticky="w", padx=(6,6))
        ttk.Button(globalf, text="ALL Color", command=self.all_color_dialog).grid(row=0, column=2, sticky="w")

        # Main grid for segment panels (scroll-free, responsive)
        grid = ttk.Frame(self, padding=(10,6,10,10))
        grid.grid(row=2, column=0, sticky="nsew")
        # Make two responsive columns
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        # And enough rows responsive to spread height
        for r in range(3):  # we’ll have up to 3 rows with 5 panels total
            grid.rowconfigure(r, weight=1)

        self.segs = []
        for sid, nled in enumerate(SEG_LENS):
            w = SegmentControl(grid, sid, nled, self.send_line)
            r, c = divmod(sid, 2)  # 0:(0,0), 1:(0,1), 2:(1,0), 3:(1,1), 4:(2,0)
            w.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            self.segs.append(w)

        # Status bar
        self.status_var = tk.StringVar(value="Status: Disconnected")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status.grid(row=3, column=0, sticky="ew", padx=10, pady=(2,10))

        self.refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ----- Serial & UI helpers -----
    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        labels, mapping = [], {}
        for p in ports:
            label = f"{p.device} ({p.description})"
            labels.append(label); mapping[label] = p.device
        self._label_to_dev = mapping
        self.port_combo["values"] = labels
        if labels: self.port_combo.current(0)
        else: self.port_combo.set("")
        self.set_status("Ports refreshed")

    def connect(self):
        label = (self.port_var.get() or "").strip()
        if not label:
            messagebox.showwarning("Select Port", "Please select a serial port."); return
        dev = self._label_to_dev.get(label, label)
        try:
            baud = int(self.baud_var.get().strip())
        except Exception:
            messagebox.showerror("Invalid Baud", "Baud must be an integer (e.g., 9600)."); return
        try:
            self.bridge.open(dev, baud)
        except Exception as e:
            messagebox.showerror("Connection Failed", f"Could not open {dev}:\n{e}")
            self.set_status("Connection failed"); return

        self.btn_connect.config(state="disabled")
        self.btn_disconnect.config(state="normal")
        self.port_combo.config(state="disabled")
        self.baud_entry.config(state="disabled")
        self.set_status(f"Connected to {dev} @ {baud} baud")

    def disconnect(self):
        self.bridge.close()
        self.btn_connect.config(state="normal")
        self.btn_disconnect.config(state="disabled")
        self.port_combo.config(state="readonly")
        self.baud_entry.config(state="normal")
        self.set_status("Disconnected")

    def send_line(self, text):
        ok = self.bridge.send_line(text)
        self.set_status(f"Sent: {text.strip()}" if ok else "Not connected")
        return ok

    def all_color_dialog(self):
        top = tk.Toplevel(self); top.title("Set ALL Color")
        top.resizable(False, False)
        vals = [tk.StringVar(value="255"), tk.StringVar(value="255"), tk.StringVar(value="255")]
        for i, ch in enumerate(("R","G","B")):
            row = ttk.Frame(top, padding=6); row.pack(fill="x")
            ttk.Label(row, text=f"{ch}:", width=4).pack(side="left")
            ttk.Entry(row, textvariable=vals[i], width=6, justify="right").pack(side="left")
        def send():
            try:
                r = max(0, min(255, int(vals[0].get())))
                g = max(0, min(255, int(vals[1].get())))
                b = max(0, min(255, int(vals[2].get())))
            except Exception:
                messagebox.showerror("Invalid", "Enter integers 0..255"); return
            self.send_line(f"A,{r},{g},{b}")
            top.destroy()
        ttk.Button(top, text="Set ALL", command=send).pack(pady=8)
        top.grab_set(); top.focus()

    def set_status(self, s): self.status_var.set(f"Status: {s}")

    def on_close(self):
        self.bridge.close()
        self.destroy()

if __name__ == "__main__":
    App().mainloop()
