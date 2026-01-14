#!/usr/bin/env python3
import os
import sys
import socket
import logging
import threading
import json
import re
import pwnagotchi.plugins as plugins
from pwnagotchi.plugins import Plugin

# Configuration
SOCKET_PATH = "/tmp/pwnctl.sock"

class PwnCTL(plugins.Plugin):
    __author__ = 'V0rT3x'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Internal Bridge between CLI and Plugin APIs.'

    def __init__(self):
        self.running = False

    def on_loaded(self):
        logging.info("[pwnctl] Plugin loaded. Starting bridge...")
        self.running = True
        # Create the symlink automatically if it doesn't exist
        self._ensure_symlink()
        # Start the listener thread
        threading.Thread(target=self.server_loop, daemon=True).start()

    def _ensure_symlink(self):
        # Identify the correct Python path (the one running the plugin)
        venv_python = sys.executable 
        plugin_path = os.path.realpath(__file__)
        launcher_path = "/usr/local/bin/pwnctl"

        # Content for the bash wrapper
        launcher_content = f"#!/bin/bash\n{venv_python} {plugin_path} \"$@\"\n"

        if not os.path.exists(launcher_path):
            try:
                with open(launcher_path, 'w') as f:
                    f.write(launcher_content)
                os.chmod(launcher_path, 0o755)
                logging.info(f"[pwnctl] Created launcher at {launcher_path}")
            except Exception as e:
                logging.error(f"[pwnctl] Failed to create launcher: {e}")

    def server_loop(self):
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.bind(SOCKET_PATH)
                os.chmod(SOCKET_PATH, 0o666)
                s.listen(1)
                while self.running:
                    conn, _ = s.accept()
                    try:
                        data = conn.recv(1024).decode('utf-8').strip()
                        if data:
                            # Command format: <plugin> <action>
                            parts = data.split(maxsplit=1)
                            plugin_name = parts[0]
                            action = parts[1] if len(parts) > 1 else "index"
                            
                            response = self.dispatch_to_webhook(plugin_name, action)
                            conn.sendall(self.clean_output(response).encode('utf-8'))
                    except Exception as e:
                        conn.sendall(f"Internal Error: {e}".encode('utf-8'))
                    finally:
                        conn.close()
        finally:
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

    def dispatch_to_webhook(self, plugin_name, action):
        """The magic part: calling on_webhook with a mock request object."""
        if plugin_name not in plugins.loaded:
            return f"Error: Plugin '{plugin_name}' not loaded."

        target = plugins.loaded[plugin_name]
        if hasattr(target, 'on_webhook'):
            try:
                # Mock Request object to satisfy 'request.method' checks
                class MockRequest:
                    def __init__(self):
                        self.method = "GET"
                
                # FIX: Remove the leading slash to match your plugin's 'elif path == "..."' logic
                res = target.on_webhook(path=action, request=MockRequest())
                
                # If res is a tuple (e.g., "message", 200), just return the content
                if isinstance(res, tuple):
                    return str(res[0])
                return str(res)
            except Exception as e:
                return f"Execution Error: {e}"
        return f"Error: Plugin '{plugin_name}' has no on_webhook."

    def clean_output(self, raw):
        """Strips HTML tags if the plugin returns a web page."""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', raw).strip()
    
    def on_unload(self, ui):
        logging.info("[pwnctl] Unloading and cleaning up...")
        self.running = False
        
        # 1. Close the socket to force the accept() loop to exit
        try:
            # We create a dummy connection to 'wake up' the accept() call 
            # if simply closing doesn't work on your kernel version
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(SOCKET_PATH)
        except:
            pass
            
        # 2. Delete the socket file
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
            
        # 3. AUTOMATED CLEANUP: Remove the CLI launcher/symlink
        dst = "/usr/local/bin/pwnctl"
        if os.path.exists(dst):
            try:
                os.remove(dst) # os.unlink(dst) also works for symlinks
                logging.info(f"[pwnctl] Removed CLI launcher at {dst}")
            except Exception as e:
                logging.error(f"[pwnctl] Failed to remove launcher: {e}")
        
        logging.info("[pwnctl] Bridge stopped.")
        
        logging.info("[pwnctl] Bridge stopped.")

# --- CLI ENTRY POINT ---
def main():
    if len(sys.argv) < 2:
        print("Usage: pwnctl <plugin> <action>")
        sys.exit(1)

    payload = " ".join(sys.argv[1:])
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(SOCKET_PATH)
            s.sendall(payload.encode('utf-8'))
            print(s.recv(4096).decode('utf-8'))
    except FileNotFoundError:
        print("Error: pwnctl socket not found. Is the plugin enabled?")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()