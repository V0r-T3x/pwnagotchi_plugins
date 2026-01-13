"""
Configuration options for btleash plugin:
main.plugins.bt-leash.mac = "XX:XX:XX:XX:XX:XX"  # Phone MAC address
main.plugins.bt-leash.auto_reconnect = false  # Auto reconnect the tether connection
main.plugins.bt-leash.position = [  # Position on the screen
 x,
 y,
]
main.plugins.bt-leash.ui_enabled = true  # Show or hide the UI widget
"""

import logging
import subprocess
import time
import threading
import json
import re
import shutil
import select
import os
from flask import abort, render_template_string, jsonify, request

import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
from pwnagotchi.utils import save_config

# Check for DBus
try:
    import dbus
    import dbus.mainloop.glib
    import dbus.service
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False

TEMPLATE = """
{% extends "base.html" %}
{% set active_page = "plugins" %}
{% block title %}
    {{ title }}
{% endblock %}
{% block meta %}
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, user-scalable=0" />
    <meta name="csrf-token" content="{{ csrf_token() }}">
{% endblock %}
{% block styles %}
{{ super() }}
    <style>
        .bt-card {
            border: 1px solid #ccc;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 5px;
            background-color: #f9f9f9;
        }
        .bt-log {
            background: #000;
            color: #0f0;
            padding: 10px;
            height: 200px;
            overflow-y: scroll;
            font-family: monospace;
            font-size: 0.8em;
            border: 1px solid #333;
        }
        .bt-btn {
            margin-right: 5px;
            margin-bottom: 5px;
            padding: 5px 10px;
            cursor: pointer;
        }
        .bt-btn-danger {
            background-color: #ffdddd;
            border: 1px solid #ffaaaa;
        }
        .bt-device-row {
            border-bottom: 1px solid #eee;
            padding: 10px 0;
        }
        .bt-section-header {
            margin-top: 0;
            border-bottom: 2px solid #eee;
        }
    </style>
{% endblock %}
{% block script %}
    var csrfToken = "{{ csrf_token() }}";
    var configLoaded = false;
    
    function updateStatus() {
        fetch('/plugins/bt-leash/status')
            .then(r => r.json())
            .then(data => {
                // Update Logs
                var logDiv = document.getElementById('bt-log');
                if(logDiv) {
                    logDiv.innerHTML = data.logs.join('<br>');
                    // Auto scroll if near bottom
                    if(logDiv.scrollTop + logDiv.clientHeight >= logDiv.scrollHeight - 50) {
                        logDiv.scrollTop = logDiv.scrollHeight;
                    }
                }
                
                var pinDiv = document.getElementById('pin-display');
                if(pinDiv) {
                    if(data.pin) {
                        pinDiv.innerHTML = "<h3>Pairing PIN: " + data.pin + "</h3>";
                        pinDiv.style.display = 'block';
                    } else {
                        pinDiv.style.display = 'none';
                    }
                }

                // Update Device Info
                var devInfo = document.getElementById('device-info');
                if(devInfo) {
                    if (data.connected_device) {
                        var d = data.connected_device; // This is the configured tether device
                        var html = "<strong>Name:</strong> " + d.name + "<br>";
                        html += "<strong>MAC:</strong> " + d.mac + "<br>";
                        html += "<strong>Status:</strong> " + (d.connected ? "Connected" : "Disconnected") + "<br>";
                        html += "<strong>IP:</strong> " + (data.ip ? data.ip : "-") + "<br>";
                        html += "<strong>Paired:</strong> " + (d.paired ? "Yes" : "No") + " | ";
                        html += "<strong>Trusted:</strong> " + (d.trusted ? "Yes" : "No") + "<br>";
                        html += "<div style='margin-top:10px;'>";
                        html += "<label style='margin-right: 10px;'><input type='checkbox' id='auto-connect' onchange='toggleAutoConnect(this)' " + (data.auto_reconnect ? "checked" : "") + "> Auto-Reconnect</label><br><br>";
                        if (d.connected) {
                            html += "<button class='bt-btn' onclick='sendAction(\\\"disconnect\\\", \\\"" + d.mac + "\\\")'>Disconnect</button>";
                        } else {
                            html += "<button class='bt-btn' onclick='sendAction(\\\"connect\\\", \\\"" + d.mac + "\\\")'>Connect</button>";
                        }
                        if (d.paired) {
                            html += "<button class='bt-btn bt-btn-danger' onclick='sendAction(\\\"unpair\\\", \\\"" + d.mac + "\\\")'>Unpair</button>";
                        } else {
                            html += "<button class='bt-btn' onclick='sendAction(\\\"pair\\\", \\\"" + d.mac + "\\\")'>Pair</button>";
                        }
                        if (d.trusted) {
                            html += "<button class='bt-btn bt-btn-danger' onclick='sendAction(\\\"untrust\\\", \\\"" + d.mac + "\\\")'>Untrust</button>";
                        } else {
                            html += "<button class='bt-btn' onclick='sendAction(\\\"trust\\\", \\\"" + d.mac + "\\\")'>Trust</button>";
                        }
                        html += "</div>";
                        devInfo.innerHTML = html;
                    } else {
                        devInfo.innerHTML = "No tethering device configured. Select one from the list below.";
                    }
                }

                // Update Config Position
                if (!configLoaded) {
                    var posInput = document.getElementById('ui-position');
                    if(posInput && data.position) {
                        posInput.value = data.position;
                    }

                    // Update UI Enabled
                    var uiCheck = document.getElementById('ui-enabled');
                    if(uiCheck && data.ui_enabled !== undefined) {
                        uiCheck.checked = data.ui_enabled;
                        try {
                            if ($(uiCheck).data('mobile-checkboxradio')) {
                                $(uiCheck).checkboxradio("refresh");
                            }
                        } catch (e) {}
                    }
                    configLoaded = true;
                }

                // Update Paired Devices
                var pairedList = document.getElementById('paired-list');
                if(pairedList && data.paired_devices) {
                    pairedList.innerHTML = "";
                    if(data.paired_devices.length === 0) {
                        pairedList.innerHTML = "No paired devices.";
                    } else {
                        data.paired_devices.forEach(d => {
                            var item = document.createElement('div');
                            item.className = 'bt-device-row';
                            var html = "<strong>" + d.name + "</strong> (" + d.mac + ") " + (d.connected ? "🟢" : "🔴") + "<br>";
                            html += "<button class='bt-btn' onclick='sendAction(\\\"set_tether\\\", \\\"" + d.mac + "\\\")'>Set as Tether</button>";
                            html += "<button class='bt-btn bt-btn-danger' onclick='sendAction(\\\"unpair\\\", \\\"" + d.mac + "\\\")'>Unpair</button>";
                            item.innerHTML = html;
                            pairedList.appendChild(item);
                        });
                    }
                }
            });
    }

    function scanDevices() {
        var list = document.getElementById('scan-list');
        list.innerHTML = "Scanning...";
        
        fetch('/plugins/bt-leash/scan', {method: 'POST', headers: {'X-CSRFToken': csrfToken}})
            .then(r => r.json())
            .then(data => {
                list.innerHTML = "";
                if(data.devices.length === 0) {
                    list.innerHTML = "No devices found.";
                    return;
                }
                data.devices.forEach(d => {
                    var item = document.createElement('div');
                    item.className = 'bt-device-row';
                    var html = "<strong>" + (d.name || "Unknown") + "</strong> (" + d.mac + ")";
                    if(d.rssi) html += " RSSI: " + d.rssi;
                    html += "<br>";
                    html += "<button class='bt-btn' onclick='sendAction(\\\"pair\\\", \\\"" + d.mac + "\\\")'>Pair</button>";
                    // html += "<button class='bt-btn' onclick='sendAction(\\\"trust\\\", \\\"" + d.mac + "\\\")'>Trust</button>";
                    html += "<button class='bt-btn' onclick='sendAction(\\\"set_tether\\\", \\\"" + d.mac + "\\\")'>Add Tether</button>";
                    html += "<button class='bt-btn' onclick='sendAction(\\\"gadget\\\", \\\"" + d.mac + "\\\")'>Connect Gadget</button>";
                    item.innerHTML = html;
                    list.appendChild(item);
                });
            });
    }

    function sendAction(action, mac) {
        var formData = new FormData();
        formData.append('mac', mac);
        fetch('/plugins/bt-leash/' + action, {
            method: 'POST', 
            body: formData,
            headers: {'X-CSRFToken': csrfToken}
        }).then(r => r.json()).then(d => {
            alert(d.message);
            configLoaded = false;
            updateStatus();
        });
    }

    function saveConfig() {
        var pos = document.getElementById('ui-position').value;
        var uiEnabled = document.getElementById('ui-enabled').checked;
        var formData = new FormData();
        formData.append('position', pos);
        formData.append('ui_enabled', uiEnabled);
        fetch('/plugins/bt-leash/save_config', {
            method: 'POST',
            body: formData,
            headers: {'X-CSRFToken': csrfToken}
        }).then(r => r.json()).then(d => {
            alert(d.message);
            updateStatus();
        });
    }

    function toggleAutoConnect(cb) {
        var action = cb.checked ? 'enable_auto_connect' : 'disable_auto_connect';
        fetch('/plugins/bt-leash/' + action, {method: 'POST', headers: {'X-CSRFToken': csrfToken}})
            .then(r => r.json())
            .then(data => {
                updateStatus();
            });
    }

    setInterval(updateStatus, 2000);
    updateStatus();
{% endblock %}
{% block content %}
    <h2>Bluetooth Leash Manager</h2>
    
    <div class="bt-card">
        <h3 class="bt-section-header">Tethering Device</h3>
        <div id="device-info">Loading...</div>
    </div>

    <div class="bt-card">
        <h3 class="bt-section-header">Paired Devices</h3>
        <div id="paired-list">Loading...</div>
    </div>

    <div class="bt-card">
        <h3 class="bt-section-header">Process Log</h3>
        <div id="pin-display" style="color: red; text-align: center; display:none; background: #fff0f0; padding: 10px; border: 1px solid red; margin-bottom: 10px;"></div>
        <div id="bt-log" class="bt-log"></div>
    </div>

    <div class="bt-card">
        <h3 class="bt-section-header">Scanner</h3>
        <button class="bt-btn" onclick="scanDevices()">Scan Devices</button>
        <div id="scan-list" style="margin-top: 10px;"></div>
    </div>

    <div class="bt-card">
        <h3 class="bt-section-header">Configuration</h3>
        <label>UI Position (x,y): <input type="text" id="ui-position" placeholder="e.g. 120,20" style="width: 100px;"></label><br>
        <label style="margin-right: 10px;"><input type="checkbox" id="ui-enabled" {% if options.get('ui_enabled', True) %}checked{% endif %}> Show UI Widget</label><br><br>
        <button class="bt-btn" onclick="saveConfig()">Save Config</button>
    </div>
{% endblock %}
"""

class BTLeash(plugins.Plugin):
    __author__ = "@V0rT3x"
    __version__ = "1.0.0"
    __license__ = "GPL3"
    __description__ = "A complete Bluetooth tethering and device manager plugin with multi-device support."

    def __init__(self):
        self.bus = None
        self.adapter = None
        self.manager = None
        self.logs = []
        self.pin = None
        self.tether_mac = None
        self.current_ip = None
        self.phone_name = "Unknown"
        self.options = dict()
        self.auto_reconnect = False
        self.running = False
        self.ui = None
        self.ui_position = None
        
    def on_loaded(self):
        self.log("Plugin loaded.")
        if DBUS_AVAILABLE:
            try:
                # dbus.mainloop.glib.DBusGMainLoop(set_as_default=True) # Avoid if possible to not conflict
                self.bus = dbus.SystemBus()
                self.manager = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
                self.adapter = dbus.Interface(self.bus.get_object("org.bluez", "/org/bluez/hci0"), "org.bluez.Adapter1")
                self.log("DBus SystemBus connected.")
            except Exception as e:
                self.log(f"Error connecting to DBus: {e}")
        else:
            self.log("DBus python module not found.")

        self.tether_mac = self.options.get('mac', '')
        self.auto_reconnect = self.options.get('auto_reconnect', False)
        self.running = True
        self.worker_thread = threading.Thread(target=self.worker)
        self.worker_thread.start()

    def on_ready(self, agent):
        if not self.tether_mac:
            self.log("No MAC address configured!")
            return
        # Auto-connect logic could go here if desired, but user wants manual control via UI mostly
        # self.connect_to_pan()

    def log(self, msg):
        logging.info(f"[BT-Leash] {msg}")
        self.logs.append(f"{time.strftime('%H:%M:%S')} - {msg}")
        if len(self.logs) > 100:
            self.logs.pop(0)

    def on_ui_setup(self, ui):
        self.ui = ui
        pos = self.options.get('position', (ui.width() / 2 - 10, 20))
        self.ui_position = pos
        if self.options.get('ui_enabled', True):
            with ui._lock:
                ui.add_element(
                    "bt_leash",
                    LabeledValue(
                        color=BLACK,
                        label="BT",
                        value="-",
                        position=pos,
                        label_font=fonts.Bold,
                        text_font=fonts.Medium,
                    ),
                )

    def on_ui_update(self, ui):
        if self.options.get('ui_enabled', True):
            ui.set("bt_leash", self.current_ip if self.current_ip else "-")

    def get_ip_address(self, ifname):
        """Simple way to pull the current IP of an interface"""
        try:
            output = subprocess.check_output(["ip", "-4", "addr", "show", ifname]).decode()
            for line in output.split('\n'):
                if "inet " in line:
                    return line.split()[1].split('/')[0]
        except:
            return None

    def get_managed_devices(self):
        devices = []
        if not self.manager: return devices
        try:
            objects = self.manager.GetManagedObjects()
            for path, interfaces in objects.items():
                if "org.bluez.Device1" in interfaces:
                    dev = interfaces["org.bluez.Device1"]
                    devices.append({
                        "path": path,
                        "name": str(dev.get("Name", "Unknown")),
                        "mac": str(dev.get("Address")),
                        "paired": bool(dev.get("Paired")),
                        "trusted": bool(dev.get("Trusted")),
                        "connected": bool(dev.get("Connected")),
                        "rssi": int(dev.get("RSSI", 0)) if "RSSI" in dev else None
                    })
        except Exception as e:
            self.log(f"Error getting devices: {e}")
        return devices
                
    def on_unload(self, ui):
        with ui._lock:
            try:
                ui.remove_element("bt_leash")
            except Exception as e:
                logging.error(f"[BT-Leash] Error removing UI element: {e}")

        self.running = False
        if self.tether_mac and self.bus:
            try:
                dev_path = f"/org/bluez/hci0/dev_{self.tether_mac.replace(':', '_').upper()}"
                dev_obj = self.bus.get_object("org.bluez", dev_path)
                network = dbus.Interface(dev_obj, "org.bluez.Network1")
                network.Disconnect()
                self.log(f"Disconnected tether connection to {self.tether_mac}")
            except Exception as e:
                logging.debug(f"[BT-Leash] Error disconnecting tether on unload: {e}")

    def on_webhook(self, path, request):
        if not self.bus:
            return jsonify({'error': 'DBus not connected'}), 500

        if path == "/" or not path:
            return render_template_string(TEMPLATE, title="BT-Leash", options=self.options)

        if path == "status":
            # Check internet/ip
            ip = self.get_ip_address("bnep0")
            self.current_ip = ip
            
            tether_device = None
            paired_devices = []
            
            devs = self.get_managed_devices()
            
            if self.tether_mac:
                for d in devs:
                    if d['mac'].upper() == self.tether_mac.upper():
                        tether_device = d
                        break
                if not tether_device:
                    tether_device = {'name': 'Configured Device', 'mac': self.tether_mac, 'paired': False, 'trusted': False, 'connected': False}

            for d in devs:
                # Check for paired devices
                if d['paired']:
                    if self.tether_mac and d['mac'].upper() == self.tether_mac.upper():
                        continue
                    paired_devices.append(d)
            
            return jsonify({
                'logs': self.logs,
                'pin': self.pin,
                'connected_device': tether_device,
                'paired_devices': paired_devices,
                'internet': ip is not None,
                'auto_reconnect': self.auto_reconnect,
                'position': self.ui_position,
                'ui_enabled': self.options.get('ui_enabled', True),
                'ip': ip
            })

        if request.method == "POST":
            if path == "save_config":
                try:
                    pos_str = request.form.get('position')
                    ui_val = request.form.get('ui_enabled')
                    # Explicitly check for the string "true"
                    ui_enabled = True if ui_val == "true" else False
                    
                    # Update internal state
                    self.options['ui_enabled'] = ui_enabled
                    
                    if pos_str:
                        try:
                            x, y = map(int, pos_str.split(','))
                            self.options['position'] = [x, y]
                            self.ui_position = [x, y]
                        except ValueError:
                            return jsonify({'message': 'Invalid position format'}), 400

                    # Save to config file
                    config = pwnagotchi.config
                    if 'bt-leash' not in config['main']['plugins']:
                        config['main']['plugins']['bt-leash'] = {}
                    
                    if pos_str:
                        config['main']['plugins']['bt-leash']['position'] = self.options['position']
                    
                    config['main']['plugins']['bt-leash']['ui_enabled'] = ui_enabled
                    save_config(config, '/etc/pwnagotchi/config.toml')
                    
                    # Update UI
                    if self.ui:
                        with self.ui._lock:
                            try:
                                self.ui.remove_element("bt_leash")
                            except:
                                pass
                            if ui_enabled:
                                pos = self.ui_position if self.ui_position else (self.ui.width() / 2 - 10, 20)
                                self.ui.add_element(
                                    "bt_leash",
                                    LabeledValue(
                                        color=BLACK,
                                        label="BT",
                                        value=self.current_ip if self.current_ip else "-",
                                        position=pos,
                                        label_font=fonts.Bold,
                                        text_font=fonts.Medium,
                                    ),
                                )
                    return jsonify({'message': 'Configuration saved'})
                except Exception as e:
                    return jsonify({'message': f"Error: {e}"}), 500

            if path == "enable_auto_connect":
                self.auto_reconnect = True
                self.options['auto_reconnect'] = True
                self.save_config_option('auto_reconnect', True)
                return jsonify({'message': 'Auto-connect enabled'})
            
            if path == "disable_auto_connect":
                self.auto_reconnect = False
                self.options['auto_reconnect'] = False
                self.save_config_option('auto_reconnect', False)
                return jsonify({'message': 'Auto-connect disabled'})

            if path == "scan":
                try:
                    self.adapter.StartDiscovery()
                    time.sleep(15) # Scan for 15 seconds to ensure devices are found
                    self.adapter.StopDiscovery()
                    devices = self.get_managed_devices()
                    return jsonify({'devices': devices})
                except Exception as e:
                    return jsonify({'message': f"Scan error: {e}"})

            mac = request.form.get('mac')
            if not mac: return jsonify({'message': 'No MAC provided'}), 400
            
            dev_path = f"/org/bluez/hci0/dev_{mac.replace(':', '_').upper()}"

            if path == "pair":
                self.pair_device_wrapper(mac)
                return jsonify({'message': 'Pairing initiated... check logs for PIN'})

            if path == "trust":
                try:
                    dev_obj = self.bus.get_object("org.bluez", dev_path)
                    props = dbus.Interface(dev_obj, "org.freedesktop.DBus.Properties")
                    props.Set("org.bluez.Device1", "Trusted", dbus.Boolean(True))
                    self.log(f"Trusted {mac}")
                    return jsonify({'message': 'Trusted'})
                except Exception as e:
                    return jsonify({'message': f"Trust failed: {e}"})

            if path == "untrust":
                try:
                    dev_obj = self.bus.get_object("org.bluez", dev_path)
                    props = dbus.Interface(dev_obj, "org.freedesktop.DBus.Properties")
                    props.Set("org.bluez.Device1", "Trusted", dbus.Boolean(False))
                    self.log(f"Untrusted {mac}")
                    return jsonify({'message': 'Untrusted'})
                except Exception as e:
                    return jsonify({'message': f"Untrust failed: {e}"})

            if path == "set_tether":
                try:
                    self.tether_mac = mac
                    self.options['mac'] = mac
                    
                    config = pwnagotchi.config
                    if 'btleash' not in config['main']['plugins']:
                        config['main']['plugins']['btleash'] = {}
                    config['main']['plugins']['btleash']['mac'] = mac
                    save_config(config, '/etc/pwnagotchi/config.toml')
                    
                    self.log(f"Tether device configured: {mac}")
                    return jsonify({'message': 'Tether device configured'})
                except Exception as e:
                    self.log(f"Set tether failed: {e}")
                    return jsonify({'message': f"Set tether failed: {e}"})

            if path == "connect":
                if self.connect_tether(mac):
                    return jsonify({'message': 'Tether connection initiated'})
                else:
                    return jsonify({'message': 'Connect failed'}), 500

            if path == "gadget":
                try:
                    dev_obj = self.bus.get_object("org.bluez", dev_path)
                    dev = dbus.Interface(dev_obj, "org.bluez.Device1")
                    self.log(f"Connecting Gadget (General) to {mac}...")
                    dev.Connect()
                    return jsonify({'message': 'Gadget connection initiated'})
                except Exception as e:
                    self.log(f"Gadget connect failed: {e}")
                    return jsonify({'message': f"Connect failed: {e}"})

            if path == "disconnect":
                try:
                    dev_obj = self.bus.get_object("org.bluez", dev_path)
                    dev = dbus.Interface(dev_obj, "org.bluez.Device1")
                    dev.Disconnect()
                    self.log(f"Disconnected {mac}")
                    return jsonify({'message': 'Disconnected'})
                except Exception as e:
                    return jsonify({'message': f"Disconnect failed: {e}"})

            if path == "unpair":
                try:
                    self.adapter.RemoveDevice(dev_path)
                    self.log(f"Removed/Unpaired {mac}")
                    return jsonify({'message': 'Unpaired'})
                except Exception as e:
                    return jsonify({'message': f"Unpair failed: {e}"})

        abort(404)

    def save_config_option(self, key, value):
        config = pwnagotchi.config
        if 'bt-leash' not in config['main']['plugins']:
            config['main']['plugins']['bt-leash'] = {}
        config['main']['plugins']['bt-leash'][key] = value
        save_config(config, '/etc/pwnagotchi/config.toml')

    def connect_tether(self, mac):
        try:
            dev_path = f"/org/bluez/hci0/dev_{mac.replace(':', '_').upper()}"
            dev_obj = self.bus.get_object("org.bluez", dev_path)
            network = dbus.Interface(dev_obj, "org.bluez.Network1")
            self.log(f"Connecting NAP to {mac}...")
            network.Connect("nap")
            
            # Trigger DHCP
            threading.Thread(target=self.run_dhcp).start()
            return True
        except Exception as e:
            self.log(f"Connect failed: {e}")
            return False

    def worker(self):
        while self.running:
            if self.auto_reconnect and self.tether_mac:
                # Check if connected (IP exists)
                if not self.get_ip_address("bnep0"):
                    # Not connected, try to connect
                    # We check if device object exists first to avoid spamming logs if device is completely gone/unpaired
                    try:
                        dev_path = f"/org/bluez/hci0/dev_{self.tether_mac.replace(':', '_').upper()}"
                        self.bus.get_object("org.bluez", dev_path)
                        # If object exists, try connect
                        self.connect_tether(self.tether_mac)
                    except:
                        pass
            time.sleep(15)

    def pair_device_wrapper(self, mac):
        self.pin = None
        self.log(f"Starting pairing with {mac}...")
        
        def run_pair():
            try:
                # Using bluetoothctl to handle pairing agent and PIN display
                cmd = ['bluetoothctl']
                if shutil.which('stdbuf'):
                    cmd = ['stdbuf', '-oL', 'bluetoothctl']

                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=False, bufsize=0)
                
                proc.stdin.write(b"agent on\n")
                proc.stdin.write(b"default-agent\n")
                proc.stdin.write(f"pair {mac}\n".encode())
                proc.stdin.flush()
                
                start_time = time.time()
                output_buffer = ""
                
                while time.time() - start_time < 60: # 60s timeout
                    if proc.poll() is not None:
                        break
                    
                    r, _, _ = select.select([proc.stdout], [], [], 0.5)
                    if r:
                        try:
                            chunk = os.read(proc.stdout.fileno(), 1024)
                            if not chunk: break
                            output_buffer += chunk.decode('utf-8', errors='ignore')
                        except:
                            break
                    
                    # Check for prompts that might not have newlines
                    if "Confirm passkey" in output_buffer and "yes/no" in output_buffer:
                        m = re.search(r"Confirm passkey\s*(\d+)", output_buffer)
                        if m:
                            self.pin = m.group(1)
                            self.log(f"Confirm PIN: {self.pin}")
                            time.sleep(2)
                            proc.stdin.write(b"yes\n")
                            proc.stdin.flush()
                            output_buffer = "" # Clear buffer to avoid re-triggering
                            continue

                    should_break = False
                    while '\n' in output_buffer:
                        line, output_buffer = output_buffer.split('\n', 1)
                        line = line.strip()
                        
                        if "Passkey:" in line:
                            m = re.search(r"Passkey:\s*(\d+)", line)
                            if m:
                                self.pin = m.group(1)
                                self.log(f"PIN: {self.pin}")

                        if "Pairing successful" in line:
                            self.log("Pairing successful.")
                            self.pin = None
                            should_break = True
                            break
                            
                        if "Failed to pair" in line:
                            self.log(f"Pairing failed: {line}")
                            should_break = True
                            break
                    
                    if should_break:
                        break
                        
                proc.terminate()
            except Exception as e:
                self.log(f"Pairing error: {e}")

        threading.Thread(target=run_pair).start()

    def run_dhcp(self):
        time.sleep(2)
        self.log("Running DHCP on bnep0...")
        try:
            subprocess.run(["dhclient", "bnep0"], timeout=15, capture_output=True)
            ip = self.get_ip_address("bnep0")
            if ip:
                self.log(f"Got IP: {ip}")
                self.current_ip = ip
            else:
                self.log("DHCP failed to get IP")
        except Exception as e:
            self.log(f"DHCP error: {e}")