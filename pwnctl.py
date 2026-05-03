#!/usr/bin/env python3
import os
import sys
import socket
import logging
import threading
import json
import re
import shlex
import time
import pwnagotchi.plugins as plugins
from pwnagotchi.plugins import Plugin

try:
    from flask import jsonify, render_template_string, request
except Exception:
    jsonify = None
    render_template_string = None
    request = None

try:
    import pwnagotchi
    from pwnagotchi.utils import save_config
except Exception:
    pwnagotchi = None
    save_config = None

# Configuration
SOCKET_PATH = "/tmp/pwnctl.sock"

PWNCTL_TEMPLATE = """
{% extends "base.html" %}
{% set active_page = "plugins" %}
{% block title %}pwnctl{% endblock %}
{% block content %}
<meta name="csrf-token" content="{{ csrf_token() if csrf_token is defined else '' }}">
<style>
  .pwnctl-wrap { max-width: 1200px; margin: 0 auto; }
  .pwnctl-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
  .pwnctl-card { border: 1px solid #ddd; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; background: rgba(255,255,255,0.04); }
  .pwnctl-row { display: flex; gap: .5rem; flex-wrap: wrap; align-items: end; margin-bottom: .65rem; }
  .pwnctl-row label { display: flex; flex-direction: column; gap: .25rem; min-width: 150px; flex: 1; }
  .pwnctl-row select, .pwnctl-row button { min-height: 2.25rem; }
  .pwnctl-table { width: 100%; border-collapse: collapse; }
  .pwnctl-table th, .pwnctl-table td { border-bottom: 1px solid #ddd; padding: .4rem; text-align: left; vertical-align: top; }
  .pwnctl-scroll { max-height: 330px; overflow: auto; }
  .pwnctl-muted { opacity: .75; }
  .pwnctl-result { white-space: pre-wrap; }
</style>
<div class="pwnctl-wrap">
  <h1>pwnctl input routing</h1>

  <div class="pwnctl-grid">
    <section class="pwnctl-card">
      <h2>Runtime status</h2>
      <p><strong>Active contexts:</strong> <span id="active-contexts">loading</span></p>
      <p><strong>Last event:</strong> <span id="last-event" class="pwnctl-muted">none</span></p>
      <p><strong>Last action:</strong> <span id="last-action" class="pwnctl-muted">none</span></p>
    </section>

    <section class="pwnctl-card">
      <h2>Binding editor</h2>
      <div class="pwnctl-row">
        <label>Context <select id="bind-context"></select></label>
        <label>Control <select id="bind-control"></select></label>
      </div>
      <div class="pwnctl-row">
        <label>Gesture <select id="bind-gesture"></select></label>
        <label>Action <select id="bind-action"></select></label>
      </div>
      <div class="pwnctl-row">
        <button id="save-binding" type="button">Save binding</button>
        <button id="delete-binding" type="button">Delete override</button>
        <button id="reset-bindings" type="button">Reset bindings</button>
      </div>
    </section>

    <section class="pwnctl-card">
      <h2>Test input</h2>
      <div class="pwnctl-row">
        <label>Control <select id="test-control"></select></label>
        <label>Gesture <select id="test-gesture"></select></label>
      </div>
      <div class="pwnctl-row">
        <button id="test-resolve" type="button">Resolve only</button>
        <button id="test-input" type="button">Send input</button>
      </div>
      <pre id="test-result" class="pwnctl-result"></pre>
    </section>
  </div>

  <section class="pwnctl-card">
    <h2>Effective bindings</h2>
    <div class="pwnctl-scroll">
      <table class="pwnctl-table">
        <thead><tr><th>Context</th><th>Control</th><th>Gesture</th><th>Action</th><th>Source</th></tr></thead>
        <tbody id="effective-bindings"></tbody>
      </table>
    </div>
  </section>

  <section class="pwnctl-card">
    <h2>User overrides</h2>
    <div class="pwnctl-scroll">
      <table class="pwnctl-table">
        <thead><tr><th>Context</th><th>Control</th><th>Gesture</th><th>Action</th><th></th></tr></thead>
        <tbody id="user-bindings"></tbody>
      </table>
    </div>
  </section>

  <section class="pwnctl-card">
    <h2>Available actions</h2>
    <div class="pwnctl-scroll">
      <table class="pwnctl-table">
        <thead><tr><th>Action</th><th>Plugin</th><th>Command</th><th>Risk</th></tr></thead>
        <tbody id="actions"></tbody>
      </table>
    </div>
  </section>
</div>

<script>
const COMMON_CONTROLS = ["BTN_A","BTN_B","BTN_MENU","BTN_UP","BTN_DOWN","BTN_LEFT","BTN_RIGHT","ENC_UP","ENC_DOWN","ENC_BTN","ANY"];
const GESTURES = ["short","long","rotate"];
const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute("content");
let state = {};

function bindingRows(bindings) {
  const rows = [];
  Object.keys(bindings || {}).sort().forEach(context => {
    const controls = bindings[context] || {};
    Object.keys(controls).sort().forEach(control => {
      const gestures = controls[control] || {};
      Object.keys(gestures).sort().forEach(gesture => {
        rows.push({context, control, gesture, action: gestures[gesture]});
      });
    });
  });
  return rows;
}

function fillSelect(id, values) {
  const el = document.getElementById(id);
  const current = el.value;
  el.innerHTML = "";
  values.forEach(value => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    el.appendChild(opt);
  });
  if (values.includes(current)) el.value = current;
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken},
    body: JSON.stringify(body)
  };
  const res = await fetch("/plugins/pwnctl/" + path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

function sourceFor(row) {
  const def = (((state.default_bindings || {})[row.context] || {})[row.control] || {})[row.gesture];
  const usr = (((state.user_bindings || {})[row.context] || {})[row.control] || {})[row.gesture];
  if (usr && def) return "user override";
  if (usr) return "user";
  return "default";
}

function render() {
  const contexts = Object.keys(state.known_contexts || {});
  bindingRows(state.default_bindings).concat(bindingRows(state.user_bindings)).forEach(row => {
    if (!contexts.includes(row.context)) contexts.push(row.context);
  });
  contexts.sort((a, b) => ((state.known_contexts[b] || {}).priority || 0) - ((state.known_contexts[a] || {}).priority || 0));

  const controls = COMMON_CONTROLS.slice();
  bindingRows(state.effective_bindings).forEach(row => {
    if (!controls.includes(row.control)) controls.push(row.control);
  });

  const actions = Object.keys(state.actions || {}).sort();
  fillSelect("bind-context", contexts);
  fillSelect("bind-control", controls);
  fillSelect("bind-gesture", GESTURES);
  fillSelect("bind-action", actions);
  fillSelect("test-control", controls);
  fillSelect("test-gesture", GESTURES);

  document.getElementById("active-contexts").textContent = (state.active_contexts || []).map(c => c.id + " (" + c.priority + ")").join(" > ") || "none";
  document.getElementById("last-event").textContent = state.last_input_event ? JSON.stringify(state.last_input_event) : "none";
  document.getElementById("last-action").textContent = state.last_resolved_action ? JSON.stringify(state.last_resolved_action) : "none";

  document.getElementById("effective-bindings").innerHTML = bindingRows(state.effective_bindings).map(row =>
    `<tr><td>${row.context}</td><td>${row.control}</td><td>${row.gesture}</td><td>${row.action}</td><td>${sourceFor(row)}</td></tr>`
  ).join("") || `<tr><td colspan="5">No bindings.</td></tr>`;

  document.getElementById("user-bindings").innerHTML = bindingRows(state.user_bindings).map(row =>
    `<tr><td>${row.context}</td><td>${row.control}</td><td>${row.gesture}</td><td>${row.action}</td><td><button type="button" data-unbind="${row.context}|${row.control}|${row.gesture}">Delete</button></td></tr>`
  ).join("") || `<tr><td colspan="5">No user overrides.</td></tr>`;

  document.getElementById("actions").innerHTML = actions.map(id => {
    const a = state.actions[id] || {};
    return `<tr><td>${id}</td><td>${a.plugin || ""}</td><td>${a.cmd || ""}</td><td>${a.risk || ""}</td></tr>`;
  }).join("") || `<tr><td colspan="4">No actions registered.</td></tr>`;

  document.querySelectorAll("[data-unbind]").forEach(btn => {
    btn.onclick = async () => {
      const [context, control, gesture] = btn.dataset.unbind.split("|");
      state = await api("unbind", {context, control, gesture});
      render();
    };
  });
}

async function loadStatus() {
  state = await api("status");
  render();
}

document.getElementById("save-binding").onclick = async () => {
  state = await api("bind", {
    context: document.getElementById("bind-context").value,
    control: document.getElementById("bind-control").value,
    gesture: document.getElementById("bind-gesture").value,
    action: document.getElementById("bind-action").value
  });
  render();
};

document.getElementById("delete-binding").onclick = async () => {
  state = await api("unbind", {
    context: document.getElementById("bind-context").value,
    control: document.getElementById("bind-control").value,
    gesture: document.getElementById("bind-gesture").value
  });
  render();
};

document.getElementById("reset-bindings").onclick = async () => {
  if (!confirm("Clear all pwnctl user binding overrides?")) return;
  state = await api("reset_bindings", {});
  render();
};

document.getElementById("test-resolve").onclick = async () => {
  const data = await api("test_resolve", {
    control: document.getElementById("test-control").value,
    gesture: document.getElementById("test-gesture").value
  });
  document.getElementById("test-result").textContent = data.result;
  await loadStatus();
};

document.getElementById("test-input").onclick = async () => {
  const data = await api("test_input", {
    control: document.getElementById("test-control").value,
    gesture: document.getElementById("test-gesture").value
  });
  document.getElementById("test-result").textContent = data.result;
  await loadStatus();
};

loadStatus().catch(err => {
  document.getElementById("test-result").textContent = err.message;
});
</script>
{% endblock %}
"""

class PwnCTL(plugins.Plugin):
    __author__ = 'V0rT3x'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Internal Bridge between CLI and Plugin APIs.'

    def __init__(self):
        self.running = False
        self.actions = {}
        self.context_priorities = {}
        self.default_bindings = {}
        self.user_bindings = {}
        self.runtime_contexts = {}
        self.event_log = []
        self.max_event_log = 50
        self.exclusive_contexts = set()
        self.last_input_event = None
        self.last_resolved_action = None
        self.broker_lock = threading.RLock()

    def on_loaded(self):
        logging.info("[pwnctl] Plugin loaded. Starting bridge...")
        self.running = True
        # Create the symlink automatically if it doesn't exist
        self._ensure_symlink()
        try:
            self._init_builtin_actions()
            self._init_builtin_contexts()
            self._init_exclusive_contexts()
            self._init_default_bindings()
            self._load_user_bindings()
        except Exception as e:
            logging.error(f"[pwnctl] Input broker init failed: {e}")
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
                        data = conn.recv(8192).decode('utf-8').strip()
                        if data:
                            response = self.handle_command(data)
                            conn.sendall(self.clean_output(response).encode('utf-8'))
                    except Exception as e:
                        conn.sendall(f"Internal Error: {e}".encode('utf-8'))
                    finally:
                        conn.close()
        finally:
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

    def get_plugins_list(self):
        pwnctl_list = []
        webhook_list = []
        
        for name, plugin in plugins.loaded.items():
            if hasattr(plugin, 'on_pwnctl'):
                try:
                    help_msg = plugin.on_pwnctl('help')
                    pwnctl_list.append(f"{name} : {help_msg}")
                except:
                    pwnctl_list.append(f"{name} : (Error retrieving help)")
            elif hasattr(plugin, 'on_webhook'):
                webhook_list.append(name)
        
        response = "Natively compatible plugins (on_pwnctl):\n"
        if pwnctl_list:
            response += "\n".join(pwnctl_list)
        else:
            response += "None"
            
        response += "\n\nPlugins with webhook support (blind bridge):\n"
        if webhook_list:
            response += "\n".join(webhook_list)
        else:
            response += "None"
            
        return response

    def handle_command(self, data):
        try:
            parts = shlex.split(data)
        except Exception:
            parts = data.split()
        if not parts:
            return "Usage: pwnctl <plugin> <action>"

        command = parts[0]
        if command == 'list':
            return self.get_plugins_list()
        if command == 'actions':
            return self.format_actions()
        if command == 'contexts':
            return self.format_contexts()
        if command == 'bindings':
            return self.format_bindings()
        if command == 'refresh':
            return self.refresh_registry()
        if command == 'events':
            return self.format_events()
        if command == 'claim':
            if len(parts) < 3:
                return "Usage: pwnctl claim <OWNER> <CONTEXT> [PRIORITY]"
            priority = int(parts[3]) if len(parts) > 3 else None
            self.claim_context(parts[1], parts[2], priority=priority)
            return f"claimed {parts[2]} for {parts[1]}"
        if command == 'release':
            if len(parts) < 3:
                return "Usage: pwnctl release <OWNER> <CONTEXT>"
            self.release_context(parts[1], parts[2])
            return f"released {parts[2]} for {parts[1]}"
        if command in ('last', 'last_event'):
            return self.format_last_event()
        if command in ('input', 'resolve'):
            if len(parts) < 3:
                return f"Usage: pwnctl {command} <CONTROL> <GESTURE> [SOURCE]"
            return self.resolve_input_event(
                parts[1],
                parts[2],
                source=parts[3] if len(parts) > 3 else 'cli',
                dry_run=(command == 'resolve')
            )
        if command == 'call':
            if len(parts) < 2:
                return "Usage: pwnctl call <ACTION_ID>"
            return self.execute_action(parts[1])

        plugin_name = command
        action = " ".join(parts[1:]) if len(parts) > 1 else "index"
        return self.dispatch_to_webhook(plugin_name, action)

    def register_action(self, action_id, plugin, cmd, label=None, category="misc", risk="safe"):
        if not action_id or not plugin or not cmd:
            return
        self.actions[str(action_id)] = {
            "id": str(action_id),
            "label": label or str(action_id),
            "plugin": str(plugin),
            "cmd": str(cmd),
            "category": str(category or "misc"),
            "risk": str(risk or "safe"),
        }

    def _init_builtin_actions(self):
        with self.broker_lock:
            self.actions = {}
            builtins = {
                "lightmenu.open": ("lightmenu", "open", "Open light menu", "lightmenu"),
                "lightmenu.close": ("lightmenu", "close", "Close light menu", "lightmenu"),
                "lightmenu.toggle": ("lightmenu", "toggle", "Toggle light menu", "lightmenu"),
                "lightmenu.up": ("lightmenu", "up", "Menu up", "lightmenu"),
                "lightmenu.down": ("lightmenu", "down", "Menu down", "lightmenu"),
                "lightmenu.select": ("lightmenu", "select", "Menu select", "lightmenu"),
                "lightmenu.back": ("lightmenu", "back", "Menu back", "lightmenu"),
                "pwnctl.noop": ("pwnctl", "noop", "No operation", "pwnctl"),
                "refacer.display_on": ("refacer", "display_on", "Display on", "refacer"),
                "refacer.display_off": ("refacer", "display_off", "Display off", "refacer"),
                "refacer.display_toggle": ("refacer", "display_toggle", "Toggle display", "refacer"),
                "refacer.display_clear": ("refacer", "display_clear", "Clear display", "refacer"),
                "refacer.stealth_toggle": ("refacer", "stealth_toggle", "Toggle stealth", "refacer"),
                "refacer.theme_next": ("refacer", "theme_next", "Next theme", "refacer"),
                "refacer.theme_prev": ("refacer", "theme_prev", "Previous theme", "refacer"),
                "refacer.rotation_next": ("refacer", "rotation_next", "Next rotation", "refacer"),
                "windows.second_screen": ("windows", "second_screen", "Second screen", "windows"),
                "windows.display_pwny": ("windows", "display_pwny", "Display pwny", "windows"),
                "windows.display_hijack": ("windows", "display_hijack", "Display hijack", "windows"),
                "windows.display_next": ("windows", "display_next", "Next display", "windows"),
                "windows.display_previous": ("windows", "display_previous", "Previous display", "windows"),
                "windows.screen_saver_start": ("windows", "screen_saver_start", "Start screen saver", "windows"),
                "windows.screen_saver_stop": ("windows", "screen_saver_stop", "Stop screen saver", "windows"),
                "windows.screen_saver_next": ("windows", "screen_saver_next", "Next screen saver", "windows"),
                "windows.screen_saver_previous": ("windows", "screen_saver_previous", "Previous screen saver", "windows"),
                "windows.aux_next": ("windows", "aux_next", "Next aux", "windows"),
                "windows.aux_prev": ("windows", "aux_prev", "Previous aux", "windows"),
                "windows.reset_runtime_defaults": ("windows", "reset_runtime_defaults", "Reset runtime defaults", "windows"),
                "windows.set_mode:screen_saver": ("windows", "set_mode:screen_saver", "Set screen saver mode", "windows"),
                "windows.set_mode:auxiliary": ("windows", "set_mode:auxiliary", "Set auxiliary mode", "windows"),
                "windows.set_mode:terminal": ("windows", "set_mode:terminal", "Set terminal mode", "windows"),
                "bt-leash.status": ("bt-leash", "status", "BT leash status", "bt-leash"),
                "bt-leash.scan": ("bt-leash", "scan", "BT leash scan", "bt-leash"),
            }
            for action_id, (plugin, cmd, label, category) in builtins.items():
                self.register_action(action_id, plugin, cmd, label=label, category=category)

            for name, plugin in plugins.loaded.items():
                if not hasattr(plugin, "on_v0rt3x_actions"):
                    continue
                try:
                    extra = plugin.on_v0rt3x_actions()
                    if not isinstance(extra, dict):
                        continue
                    for action_id, meta in extra.items():
                        if not isinstance(meta, dict):
                            continue
                        self.register_action(
                            action_id,
                            meta.get("plugin"),
                            meta.get("cmd"),
                            label=meta.get("label"),
                            category=meta.get("category", name),
                            risk=meta.get("risk", "safe")
                        )
                except Exception as e:
                    logging.warning(f"[pwnctl] Failed to harvest actions from {name}: {e}")

    def _init_builtin_contexts(self):
        with self.broker_lock:
            self.context_priorities = {
                "refacer_display_sleeping": {"priority": 100, "label": "Refacer display sleeping"},
                "lightmenu_open": {"priority": 90, "label": "Light menu open"},
                "windows_saver": {"priority": 80, "label": "Windows screen saver"},
                "windows_aux": {"priority": 75, "label": "Windows auxiliary"},
                "windows_second_screen": {"priority": 70, "label": "Windows second screen"},
                "base_ui": {"priority": 10, "label": "Base UI"},
            }
            for name, plugin in plugins.loaded.items():
                if not hasattr(plugin, "on_v0rt3x_contexts"):
                    continue
                try:
                    extra = plugin.on_v0rt3x_contexts()
                    if not isinstance(extra, dict):
                        continue
                    for context_id, meta in extra.items():
                        if isinstance(meta, dict):
                            priority = int(meta.get("priority", 0))
                            label = meta.get("label", context_id)
                        else:
                            priority = int(meta)
                            label = context_id
                        self.context_priorities[str(context_id)] = {"priority": priority, "label": str(label)}
                except Exception as e:
                    logging.warning(f"[pwnctl] Failed to harvest contexts from {name}: {e}")

    def _init_exclusive_contexts(self):
        exclusive = {
            "refacer_display_sleeping",
            "lightmenu_open",
            "windows_saver",
            "windows_aux",
            "windows_second_screen",
        }
        try:
            configured = self.options.get("exclusive_contexts", None)
            if isinstance(configured, (list, tuple, set)):
                exclusive.update(str(context_id) for context_id in configured if context_id)
            elif isinstance(configured, dict):
                for context_id, enabled in configured.items():
                    context_id = str(context_id or "").strip()
                    if not context_id:
                        continue
                    if enabled:
                        exclusive.add(context_id)
                    else:
                        exclusive.discard(context_id)
        except Exception as e:
            logging.debug(f"[pwnctl] Failed to load exclusive contexts config: {e}")
        self.exclusive_contexts = exclusive

    def _init_default_bindings(self):
        self.default_bindings = {
            "base_ui": {
                "BTN_A": {"short": "lightmenu.open", "long": "windows.second_screen"},
                "BTN_MENU": {"short": "lightmenu.toggle", "long": "windows.second_screen"},
                "BTN_B": {"short": "refacer.display_toggle", "long": "refacer.stealth_toggle"},
            },
            "lightmenu_open": {
                "BTN_UP": {"short": "lightmenu.up"},
                "BTN_DOWN": {"short": "lightmenu.down"},
                "BTN_A": {"short": "lightmenu.select"},
                "BTN_B": {"short": "lightmenu.back", "long": "lightmenu.close"},
                "ENC_UP": {"rotate": "lightmenu.up"},
                "ENC_DOWN": {"rotate": "lightmenu.down"},
                "ENC_BTN": {"short": "lightmenu.select", "long": "lightmenu.back"},
            },
            "windows_aux": {
                "BTN_RIGHT": {"short": "windows.aux_next"},
                "BTN_LEFT": {"short": "windows.aux_prev"},
                "BTN_B": {"short": "windows.display_pwny"},
                "BTN_DOWN": {"short": "windows.aux_next"},
                "BTN_UP": {"short": "windows.aux_prev"},
                "BTN_MENU": {"short": "windows.display_next", "long": "windows.display_pwny"},
                "BTN_A": {"short": "windows.aux_next", "long": "windows.display_pwny"},
                "ENC_UP": {"rotate": "windows.aux_prev"},
                "ENC_DOWN": {"rotate": "windows.aux_next"},
            },
            "windows_saver": {
                "BTN_RIGHT": {"short": "windows.screen_saver_next"},
                "BTN_LEFT": {"short": "windows.screen_saver_previous"},
                "BTN_B": {"short": "windows.screen_saver_stop"},
                "BTN_DOWN": {"short": "windows.screen_saver_next"},
                "BTN_UP": {"short": "windows.screen_saver_previous"},
                "BTN_MENU": {"short": "windows.display_next", "long": "windows.display_pwny"},
                "BTN_A": {"short": "windows.screen_saver_next", "long": "windows.display_pwny"},
            },
            "windows_second_screen": {
                "BTN_DOWN": {"short": "windows.display_next"},
                "BTN_UP": {"short": "windows.display_previous"},
                "BTN_MENU": {"short": "windows.display_next", "long": "windows.display_pwny"},
                "BTN_A": {"short": "windows.screen_saver_next", "long": "windows.display_pwny"},
                "BTN_B": {"long": "windows.display_pwny"},
                "BTN_RIGHT": {"short": "windows.display_next"},
                "BTN_LEFT": {"short": "windows.display_previous"},
            },
            "refacer_display_sleeping": {
                "ANY": {
                    "short": "refacer.display_on",
                    "long": "refacer.display_on",
                    "rotate": "refacer.display_on",
                }
            },
        }

    def emit_event(self, plugin, event, context=None, payload=None):
        entry = {
            "ts": time.time(),
            "plugin": str(plugin or "").strip(),
            "event": str(event or "").strip(),
            "context": str(context or "").strip() if context else None,
            "payload": self._plain_dict(payload or {}),
        }
        with self.broker_lock:
            self.event_log.append(entry)
            if len(self.event_log) > self.max_event_log:
                self.event_log = self.event_log[-self.max_event_log:]
        logging.debug("[pwnctl] event %s", entry)
        return True

    def claim_context(self, owner, context_id, priority=None, payload=None, ttl=None):
        owner = str(owner or "").strip()
        context_id = str(context_id or "").strip()
        if not owner or not context_id:
            return False
        now = time.time()
        priority = self._context_priority(context_id) if priority is None else int(priority)
        with self.broker_lock:
            self.runtime_contexts[context_id] = {
                "id": context_id,
                "owner": owner,
                "priority": priority,
                "active": True,
                "payload": self._plain_dict(payload or {}),
                "updated_at": now,
                "expires_at": now + ttl if ttl else None,
            }
        self.emit_event(owner, "context_claimed", context_id, payload or {})
        return True

    def release_context(self, owner, context_id):
        owner = str(owner or "").strip()
        context_id = str(context_id or "").strip()
        released = False
        with self.broker_lock:
            current = self.runtime_contexts.get(context_id)
            if current and current.get("owner") == owner:
                self.runtime_contexts.pop(context_id, None)
                released = True
        if released:
            self.emit_event(owner, "context_released", context_id, {})
        return released

    def refresh_registry(self):
        with self.broker_lock:
            self._init_builtin_actions()
            self._init_builtin_contexts()
            self._init_exclusive_contexts()
        return f"registry refreshed: {len(self.actions)} actions, {len(self.context_priorities)} contexts"

    def _plain_dict(self, value):
        if isinstance(value, dict):
            return {str(k): self._plain_dict(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._plain_dict(v) for v in value]
        if hasattr(value, "items"):
            try:
                return {str(k): self._plain_dict(v) for k, v in value.items()}
            except Exception:
                return {}
        return value

    def _load_user_bindings(self):
        try:
            bindings = self._plain_dict(self.options.get("bindings", {}))
            self.user_bindings = self._normalize_bindings(bindings) if isinstance(bindings, dict) else {}
        except Exception as e:
            logging.warning(f"[pwnctl] Failed to load user bindings: {e}")
            self.user_bindings = {}

    def _normalize_bindings(self, bindings):
        normalized = {}
        for context_id, controls in bindings.items():
            if not isinstance(controls, dict):
                continue
            normalized_controls = {}
            for control, gestures in controls.items():
                if not isinstance(gestures, dict):
                    continue
                normalized_gestures = {}
                for gesture, action_id in gestures.items():
                    if action_id:
                        normalized_gestures[self._normalize_gesture(gesture)] = str(action_id)
                if normalized_gestures:
                    normalized_controls[self._normalize_control(control)] = normalized_gestures
            if normalized_controls:
                normalized[str(context_id)] = normalized_controls
        return normalized

    def get_effective_bindings(self):
        effective = self._plain_dict(self.default_bindings)
        for context_id, controls in self._plain_dict(self.user_bindings).items():
            if not isinstance(controls, dict):
                continue
            effective.setdefault(context_id, {})
            for control, gestures in controls.items():
                if not isinstance(gestures, dict):
                    continue
                effective[context_id].setdefault(control, {})
                effective[context_id][control].update(gestures)
        return effective

    def _cleanup_empty_bindings(self, root):
        if not isinstance(root, dict):
            return root
        for context_id in list(root.keys()):
            controls = root.get(context_id)
            if not isinstance(controls, dict):
                continue
            for control in list(controls.keys()):
                gestures = controls.get(control)
                if isinstance(gestures, dict) and not gestures:
                    controls.pop(control, None)
            if not controls:
                root.pop(context_id, None)
        return root

    def _save_user_bindings(self):
        if pwnagotchi is None or save_config is None:
            msg = "pwnagotchi config save API unavailable"
            logging.warning(f"[pwnctl] {msg}")
            return False, msg
        try:
            config = getattr(pwnagotchi, "config", None)
            if config is None:
                msg = "pwnagotchi.config unavailable"
                logging.warning(f"[pwnctl] {msg}")
                return False, msg

            main = config.setdefault("main", {})
            main_plugins = main.setdefault("plugins", {})
            plugin_config = main_plugins.setdefault("pwnctl", {})
            plugin_config["bindings"] = self._plain_dict(self.user_bindings)
            save_config(config, "/etc/pwnagotchi/config.toml")
            return True, "saved"
        except Exception as e:
            logging.error(f"[pwnctl] Failed to save user bindings: {e}")
            return False, str(e)

    def _validate_action_id(self, action_id):
        action_id = str(action_id or "").strip()
        if not action_id:
            return False
        if action_id in self.actions:
            return True
        if "." not in action_id:
            return False
        plugin_name, cmd = action_id.split(".", 1)
        if not plugin_name or not cmd:
            return False
        return plugin_name in plugins.loaded

    def _known_contexts_payload(self):
        payload = {}
        for context_id, meta in self.context_priorities.items():
            if isinstance(meta, dict):
                payload[context_id] = {
                    "priority": self._context_priority(context_id),
                    "label": meta.get("label", context_id),
                }
            else:
                payload[context_id] = {"priority": self._context_priority(context_id), "label": context_id}
        return payload

    def _status_payload(self):
        return {
            "active_contexts": self.get_active_contexts(),
            "known_contexts": self._known_contexts_payload(),
            "actions": self._plain_dict(self.actions),
            "default_bindings": self._plain_dict(self.default_bindings),
            "user_bindings": self._plain_dict(self.user_bindings),
            "effective_bindings": self.get_effective_bindings(),
            "last_input_event": self._plain_dict(self.last_input_event),
            "last_resolved_action": self._plain_dict(self.last_resolved_action),
            "runtime_contexts": self._plain_dict(self.runtime_contexts),
            "event_log": self._plain_dict(self.event_log),
        }

    def _json_response(self, payload, status=200):
        if jsonify is None:
            return json.dumps(payload), status, {"Content-Type": "application/json"}
        response = jsonify(payload)
        response.status_code = status
        return response

    def _web_request_json(self, web_request):
        if web_request is None:
            return {}
        try:
            data = web_request.get_json(silent=True)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        try:
            if hasattr(web_request, "form"):
                return dict(web_request.form)
        except Exception:
            pass
        return {}

    def _context_priority(self, context_id):
        meta = self.context_priorities.get(context_id, {})
        if isinstance(meta, dict):
            return int(meta.get("priority", 0))
        return int(meta or 0)

    def _is_exclusive_context(self, context_id):
        return str(context_id or "") in self.exclusive_contexts

    def _windows_second_screen_active(self, windows):
        return bool(getattr(windows, "dispHijack", False) or getattr(windows, "display_hijacked", False))

    def _windows_mode(self, windows):
        for attr in ("current_mode", "_current_mode", "mode"):
            mode = getattr(windows, attr, None)
            if mode is not None:
                return str(mode).lower()
        return ""

    def get_active_contexts(self):
        contexts = {}

        def add_context(context_id, priority=None, active=True, source="detected", payload=None, owner=None):
            if not context_id:
                return
            context_id = str(context_id)
            priority = self._context_priority(context_id) if priority is None else int(priority)
            existing = contexts.get(context_id)
            if existing:
                if priority > existing.get("priority", 0):
                    existing["priority"] = priority
                sources = set(str(existing.get("source", "")).split("+"))
                sources.add(source)
                existing["source"] = "+".join(sorted(src for src in sources if src))
                existing["active"] = bool(existing.get("active", False) or active)
                if payload is not None:
                    existing["payload"] = self._plain_dict(payload)
                if owner:
                    existing["owner"] = owner
                return
            contexts[context_id] = {"id": context_id, "priority": priority, "active": bool(active), "source": source}
            if payload is not None:
                contexts[context_id]["payload"] = self._plain_dict(payload)
            if owner:
                contexts[context_id]["owner"] = owner

        try:
            lightmenu = plugins.loaded.get("lightmenu")
            if lightmenu and getattr(lightmenu, "menu_visible", False) is True:
                add_context("lightmenu_open")
        except Exception:
            pass

        try:
            windows = plugins.loaded.get("windows")
            if windows:
                second_active = self._windows_second_screen_active(windows)
                mode = self._windows_mode(windows)
                if second_active and "saver" in mode:
                    add_context("windows_saver")
                if second_active and "aux" in mode:
                    add_context("windows_aux")
                if second_active:
                    add_context("windows_second_screen")
        except Exception:
            pass

        try:
            refacer = plugins.loaded.get("refacer")
            if refacer:
                sleeping = getattr(refacer, "_display_sleeping", None)
                if sleeping is None:
                    sleeping = getattr(refacer, "display_sleeping", None)
                enabled = getattr(refacer, "_display_enabled", None)
                if enabled is None:
                    enabled = getattr(refacer, "display_enabled", None)
                if sleeping is True or enabled is False:
                    add_context("refacer_display_sleeping")
        except Exception:
            pass

        now = time.time()
        with self.broker_lock:
            for context_id, context in list(self.runtime_contexts.items()):
                expires_at = context.get("expires_at")
                if expires_at and expires_at <= now:
                    self.runtime_contexts.pop(context_id, None)
                    continue
                if context.get("active", True):
                    add_context(
                        context_id,
                        priority=context.get("priority"),
                        active=True,
                        source="runtime",
                        payload=context.get("payload", {}),
                        owner=context.get("owner"),
                    )

        add_context("base_ui")
        return sorted(contexts.values(), key=lambda item: item.get("priority", 0), reverse=True)

    def _normalize_control(self, control):
        return str(control or "").strip().upper().replace(" ", "_").replace("-", "_")

    def _normalize_gesture(self, gesture):
        return str(gesture or "").strip().lower().replace(" ", "_").replace("-", "_")

    def _binding_lookup(self, bindings, context_id, control, gesture):
        context = bindings.get(context_id, {})
        if not isinstance(context, dict):
            return None
        for control_key in (control, "ANY"):
            gestures = context.get(control_key, {})
            if not isinstance(gestures, dict):
                continue
            action_id = gestures.get(gesture)
            if action_id:
                return str(action_id)
        return None

    def _get_binding_for(self, context_id, control, gesture):
        return (
            self._binding_lookup(self.user_bindings, context_id, control, gesture)
            or self._binding_lookup(self.default_bindings, context_id, control, gesture)
        )

    def resolve_input_event(self, control, gesture, source="unknown", value=None, raw=None, dry_run=False):
        control = self._normalize_control(control)
        gesture = self._normalize_gesture(gesture)
        event = {"control": control, "gesture": gesture, "source": source, "value": value, "raw": raw}
        with self.broker_lock:
            self.last_input_event = event
            contexts = self.get_active_contexts()
            seen = set()
            for context in contexts:
                context_id = context.get("id")
                seen.add(context_id)
                action_id = self._get_binding_for(context_id, control, gesture)
                if not action_id:
                    if self._is_exclusive_context(context_id):
                        self.last_resolved_action = {
                            "action": None,
                            "blocked_by": context_id,
                            "control": control,
                            "gesture": gesture,
                            "reason": "exclusive_context_no_binding",
                        }
                        if dry_run:
                            return f"{control} {gesture} from {source} blocked by exclusive context {context_id}: no binding"
                        return f"No binding for {control} {gesture} in exclusive context {context_id}"
                    continue
                self.last_resolved_action = {
                    "action": action_id,
                    "context": context_id,
                    "control": control,
                    "gesture": gesture,
                }
                if dry_run:
                    return f"{control} {gesture} from {source} resolves to {action_id} in {context_id}"
                try:
                    result = self.execute_action(action_id)
                    return f"{control} {gesture} from {source} -> {action_id}: {result}"
                except Exception as e:
                    logging.error(f"[pwnctl] Action execution failed for {action_id}: {e}")
                    return f"Error executing {action_id}: {e}"

            if "base_ui" not in seen:
                action_id = self._get_binding_for("base_ui", control, gesture)
                if action_id:
                    self.last_resolved_action = {
                        "action": action_id,
                        "context": "base_ui",
                        "control": control,
                        "gesture": gesture,
                    }
                    if dry_run:
                        return f"{control} {gesture} from {source} resolves to {action_id} in base_ui"
                    try:
                        result = self.execute_action(action_id)
                        return f"{control} {gesture} from {source} -> {action_id}: {result}"
                    except Exception as e:
                        logging.error(f"[pwnctl] Action execution failed for {action_id}: {e}")
                        return f"Error executing {action_id}: {e}"

        active = ", ".join(ctx.get("id", "?") for ctx in contexts)
        self.last_resolved_action = {
            "action": None,
            "control": control,
            "gesture": gesture,
            "reason": "no_binding",
            "active_contexts": [ctx.get("id", "?") for ctx in contexts],
        }
        return f"No binding for {control} {gesture} in active contexts: {active}"

    def emit_input_event(self, control, gesture, source="unknown", value=None, raw=None):
        return self.resolve_input_event(control, gesture, source=source, value=value, raw=raw)

    def execute_action(self, action_id):
        action_id = str(action_id or "").strip()
        if action_id == "pwnctl.noop":
            return "OK noop"
        meta = self.actions.get(action_id)
        if meta:
            return self.dispatch_to_webhook(meta.get("plugin"), meta.get("cmd"))
        if "." in action_id:
            plugin_name, cmd = action_id.split(".", 1)
            return self.dispatch_to_webhook(plugin_name, cmd)
        return f"Error: Unknown action '{action_id}'."

    def format_actions(self):
        if not self.actions:
            return "No actions registered."
        lines = ["Registered actions:"]
        for action_id in sorted(self.actions):
            meta = self.actions[action_id]
            lines.append(f"{action_id} -> {meta.get('plugin')} {meta.get('cmd')} [{meta.get('category')}/{meta.get('risk')}]")
        return "\n".join(lines)

    def format_contexts(self):
        active = {ctx["id"]: ctx for ctx in self.get_active_contexts()}
        lines = ["Contexts:"]
        known = dict(self.context_priorities)
        for context_id, ctx in active.items():
            known.setdefault(context_id, {
                "priority": ctx.get("priority", 0),
                "label": context_id,
            })
        def sort_priority(item):
            context_id = item[0]
            priority = self._context_priority(context_id)
            if priority == 0 and context_id in active:
                priority = int(active[context_id].get("priority", 0))
            elif context_id in active:
                priority = max(priority, int(active[context_id].get("priority", 0)))
            return priority

        for context_id, meta in sorted(known.items(), key=sort_priority, reverse=True):
            priority = self._context_priority(context_id)
            if priority == 0 and context_id in active:
                priority = int(active[context_id].get("priority", 0))
            label = meta.get("label", context_id) if isinstance(meta, dict) else context_id
            ctx = active.get(context_id)
            state = "active" if ctx else "inactive"
            source = f" {ctx.get('source')}" if ctx and ctx.get("source") not in (None, "detected") else ""
            lines.append(f"{context_id} ({priority}) {state}{source} - {label}")
        return "\n".join(lines)

    def format_bindings(self):
        lines = ["Default bindings:"]
        lines.extend(self._format_binding_set(self.default_bindings))
        lines.append("\nUser bindings:")
        lines.extend(self._format_binding_set(self.user_bindings) if self.user_bindings else ["None"])
        return "\n".join(lines)

    def _format_binding_set(self, bindings):
        lines = []
        for context_id in sorted(bindings):
            controls = bindings.get(context_id, {})
            if not isinstance(controls, dict):
                continue
            for control, gestures in sorted(controls.items()):
                if not isinstance(gestures, dict):
                    continue
                for gesture, action_id in sorted(gestures.items()):
                    lines.append(f"{context_id}.{control}.{gesture} = {action_id}")
        return lines or ["None"]

    def format_last_event(self):
        last_plugin_event = self.event_log[-1] if self.event_log else None
        return (
            f"last_input_event={self.last_input_event}\n"
            f"last_resolved_action={self.last_resolved_action}\n"
            f"last_plugin_event={last_plugin_event}"
        )

    def format_events(self):
        if not self.event_log:
            return "No pwnctl plugin events."
        lines = ["Recent pwnctl plugin events:"]
        for entry in self.event_log:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.get("ts", 0)))
            lines.append(
                f"{ts} {entry.get('plugin')} {entry.get('event')} "
                f"context={entry.get('context')} payload={entry.get('payload')}"
            )
        return "\n".join(lines)

    def on_webhook(self, path, request):
        route = str(path or "").strip("/")
        method = getattr(request, "method", "GET")

        if method == "GET" and route in ("", "/"):
            if render_template_string is None:
                return "pwnctl WebUI unavailable: Flask render_template_string could not be imported.", 500
            return render_template_string(PWNCTL_TEMPLATE)

        if method == "GET" and route == "status":
            return self._json_response(self._status_payload())

        if method == "GET" and route == "actions":
            return self._json_response(self._plain_dict(self.actions))

        if method == "GET" and route == "contexts":
            return self._json_response({
                "active_contexts": self.get_active_contexts(),
                "known_contexts": self._known_contexts_payload(),
            })

        if method == "GET" and route == "bindings":
            return self._json_response({
                "default_bindings": self._plain_dict(self.default_bindings),
                "user_bindings": self._plain_dict(self.user_bindings),
                "effective_bindings": self.get_effective_bindings(),
            })

        if method != "POST":
            return self._json_response({"error": "Unsupported pwnctl WebUI route."}, 404)

        data = self._web_request_json(request)

        if route == "bind":
            context = str(data.get("context", "")).strip()
            control = self._normalize_control(data.get("control"))
            gesture = self._normalize_gesture(data.get("gesture"))
            action_id = str(data.get("action", "")).strip()
            if not context or not control or not gesture or not action_id:
                return self._json_response({"error": "context, control, gesture, and action are required"}, 400)
            if not self._validate_action_id(action_id):
                return self._json_response({"error": f"Invalid action id: {action_id}"}, 400)
            with self.broker_lock:
                self.user_bindings.setdefault(context, {}).setdefault(control, {})[gesture] = action_id
                self._cleanup_empty_bindings(self.user_bindings)
                try:
                    self.options["bindings"] = self._plain_dict(self.user_bindings)
                except Exception:
                    pass
                saved, message = self._save_user_bindings()
                payload = self._status_payload()
                payload["saved"] = saved
                payload["save_message"] = message
                return self._json_response(payload)

        if route == "unbind":
            context = str(data.get("context", "")).strip()
            control = self._normalize_control(data.get("control"))
            gesture = self._normalize_gesture(data.get("gesture"))
            if not context or not control or not gesture:
                return self._json_response({"error": "context, control, and gesture are required"}, 400)
            with self.broker_lock:
                try:
                    self.user_bindings.get(context, {}).get(control, {}).pop(gesture, None)
                except Exception:
                    pass
                self._cleanup_empty_bindings(self.user_bindings)
                try:
                    self.options["bindings"] = self._plain_dict(self.user_bindings)
                except Exception:
                    pass
                saved, message = self._save_user_bindings()
                payload = self._status_payload()
                payload["saved"] = saved
                payload["save_message"] = message
                return self._json_response(payload)

        if route == "reset_bindings":
            with self.broker_lock:
                self.user_bindings = {}
                try:
                    self.options["bindings"] = {}
                except Exception:
                    pass
                saved, message = self._save_user_bindings()
                payload = self._status_payload()
                payload["saved"] = saved
                payload["save_message"] = message
                return self._json_response(payload)

        if route in ("test_resolve", "test_input"):
            control = data.get("control")
            gesture = data.get("gesture")
            if not control or not gesture:
                return self._json_response({"error": "control and gesture are required"}, 400)
            result = self.resolve_input_event(
                control,
                gesture,
                source="webui-test",
                dry_run=(route == "test_resolve")
            )
            payload = self._status_payload()
            payload["result"] = result
            return self._json_response(payload)

        return self._json_response({"error": "Unsupported pwnctl WebUI route."}, 404)

    def dispatch_to_webhook(self, plugin_name, action):
        """The magic part: calling on_webhook with a mock request object."""
        if plugin_name not in plugins.loaded:
            return f"Error: Plugin '{plugin_name}' not loaded."

        target = plugins.loaded[plugin_name]
        
        if hasattr(target, 'on_pwnctl'):
            try:
                return str(target.on_pwnctl(action))
            except Exception as e:
                return f"Error: {e}"

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
            print(s.recv(8192).decode('utf-8'))
    except FileNotFoundError:
        print("Error: pwnctl socket not found. Is the plugin enabled?")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
