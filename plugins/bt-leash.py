import logging
import os
import subprocess
import re
import time
import threading
import shutil
import socket
from flask import abort, render_template_string, jsonify
import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
from pwnagotchi.utils import save_config

TEMPLATE = """
{% extends "base.html" %}
{% set active_page = "bt-tether" %}
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
        #searchText {
            width: 100%;
        }
        table {
            table-layout: auto;
            width: 100%;
        }
        table, th, td {
            border: 1px solid;
            border-collapse: collapse;
        }
        th, td {
            padding: 15px;
            text-align: left;
        }
        @media screen and (max-width:700px) {
            table, tr, td {
                padding:0;
                border:1px solid;
            }
            table {
                border:none;
            }
            tr:first-child, thead, th {
                display:none;
                border:none;
            }
            tr {
                float: left;
                width: 100%;
                margin-bottom: 2em;
            }
            td {
                float: left;
                width: 100%;
                padding:1em;
            }
            td::before {
                content:attr(data-label);
                word-wrap: break-word;
                color: white;
                border-right:2px solid;
                width: 20%;
                float:left;
                padding:1em;
                font-weight: bold;
                margin:-1em 1em -1em -1em;
            }
        }
        #status-msg {
            padding: 10px;
            border-radius: 5px;
            background-color: #f5f5f5;
        }
        #status-msg strong {
            color: #333;
        }
        /* Highlight PIN/passkey display */
        #status-msg:has-text('🔑') {
            background-color: #fff3cd;
            border: 2px solid #ffc107;
            font-size: 1.1em;
            font-weight: bold;
        }
    </style>
{% endblock %}
{% block script %}
    document.addEventListener('DOMContentLoaded', function() {
        var searchInput = document.getElementById("searchText");
        if (searchInput) {
            searchInput.onkeyup = function() {
                var filter, table, tr, td, i, txtValue;
                filter = searchInput.value.toUpperCase();
                table = document.getElementById("tableOptions");
                if (table) {
                    tr = table.getElementsByTagName("tr");

                    for (i = 0; i < tr.length; i++) {
                        td = tr[i].getElementsByTagName("td")[0];
                        if (td) {
                            txtValue = td.textContent || td.innerText;
                            if (txtValue.toUpperCase().indexOf(filter) > -1) {
                                tr[i].style.display = "";
                            }else{
                                tr[i].style.display = "none";
                            }
                        }
                    }
                }
            }
        }
        updateStatus();
        setInterval(updateStatus, 1000);
    });

    var root = "{{ request.path }}";
    if (!root.endsWith('/')) {
        root += '/';
    }

    function updateStatus() {
        fetch(root + 'status')
            .then(response => response.json())
            .then(data => {
                document.getElementById('bt-info').innerHTML = data.bluetooth;
                document.getElementById('dev-info').innerHTML = data.device;
                document.getElementById('conn-info').innerHTML = data.connection;
                document.getElementById('status-msg').innerHTML = '<strong>Status:</strong> ' + data.error;
                
                var scanContainer = document.getElementById('scan-results-container');
                if (data.scan_results && data.scan_results.length > 0) {
                    var html = '<h4>Discovered Devices (Click to copy MAC)</h4><ul style="list-style-type: none; padding: 0;">';
                    data.scan_results.forEach(function(dev) {
                        html += '<li style="padding: 5px; border-bottom: 1px solid #ccc;">';
                        html += '<a href="#" onclick="copyMAC(\\'' + dev.mac + '\\'); return false;" style="text-decoration: none; color: inherit;">';
                        html += '<strong>' + dev.mac + '</strong> - ' + dev.name;
                        html += '</a></li>';
                    });
                    html += '</ul>';
                    scanContainer.innerHTML = html;
                }
                
                // Update paired devices list
                updatePairedDevicesList(data.paired_devices || []);
            })
            .catch(err => console.error('Error fetching status:', err));
    }

    function updatePairedDevicesList(devices) {
    var container = document.getElementById('paired-devices-container');
    if (!devices || devices.length === 0) {
        container.innerHTML = '<p style="color: #999; font-style: italic;">No devices paired yet.</p>';
        return;
    }
    var html = '<table style="width: 100%; border-collapse: collapse;">';
    html += '<tr style="background-color: #f0f0f0;">';
    html += '<th style="padding: 8px; text-align: left;">Status</th>';
    html += '<th style="padding: 8px; text-align: left;">Device</th>';
    html += '<th style="padding: 8px; text-align: left;">MAC</th>';
    html += '<th style="padding: 8px; text-align: left;">Type</th>';
    html += '<th style="padding: 8px; text-align: left;">Actions</th>';
    html += '</tr>';
    devices.forEach(function(device) {
        var isConnected = device.connected;
        var statusIcon = isConnected ? '<span style="color: green;">🟢</span>' : '<span style="color: red;">🔴</span>';
        var connectDisabled = isConnected ? 'disabled' : '';
        var disconnectDisabled = isConnected ? '' : 'disabled';
        html += '<tr style="border-bottom: 1px solid #ddd;">';
        html += '<td style="padding: 8px; text-align: center;">' + statusIcon + '</td>';
        html += '<td style="padding: 8px;">' + device.name + '</td>';
        html += '<td style="padding: 8px; font-family: monospace;">' + device.mac + '</td>';
        html += '<td style="padding: 8px;">' + getDeviceIcon(device.type) + ' ' + device.type + '</td>';
        html += '<td style="padding: 8px;">';
        html += '<button onclick="connectDevice(\\'' + device.mac + '\\')" style="margin-right: 5px; padding: 4px 8px;" ' + connectDisabled + '>Connect</button>';
        html += '<button onclick="disconnectDevice(\\'' + device.mac + '\\')" style="margin-right: 5px; padding: 4px 8px;" ' + disconnectDisabled + '>Disconnect</button>';
        html += '<button onclick="removeDevice(\\'' + device.mac + '\\')" style="padding: 4px 8px; background-color: #dc3545; color: white; border: none; cursor: pointer;">Remove</button>';
        html += '</td>';
        html += '</tr>';
    });
    html += '</table>';
    container.innerHTML = html;
    }

    function getDeviceIcon(type) {
        var icons = {
            'keyboard': '⌨️',
            'mouse': '🖱️',
            'headset': '🎧',
            'other': '🔧'
        };
        return icons[type] || '📱';
    }

    function copyMAC(mac) {
        // Try to copy to clipboard
        if (navigator.clipboard) {
            navigator.clipboard.writeText(mac).then(function() {
                // Also populate the device MAC field if it exists
                var deviceMacInput = document.querySelector('input[name="device_mac"]');
                if (deviceMacInput) {
                    deviceMacInput.value = mac;
                }
                // Show feedback
                var status = document.getElementById('status-msg');
                status.innerHTML = '<strong>Status:</strong> MAC address copied: ' + mac;
                status.style.backgroundColor = '#d4edda';
                setTimeout(function() {
                    status.style.backgroundColor = '';
                }, 2000);
            });
        } else {
            // Fallback: just populate the field
            var deviceMacInput = document.querySelector('input[name="device_mac"]');
            if (deviceMacInput) {
                deviceMacInput.value = mac;
                var status = document.getElementById('status-msg');
                status.innerHTML = '<strong>Status:</strong> MAC address set: ' + mac;
            }
        }
    }

    function connectDevice(mac) {
        var formData = new FormData();
        formData.set('action', 'connect_device');
        formData.set('device_mac', mac);
        formData.set('csrf_token', document.querySelector('meta[name="csrf-token"]').getAttribute('content'));
        
        fetch(root + 'action', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            }
        })
        .then(response => response.json())
        .then(data => {
            updateStatus();
        })
        .catch(err => console.error('Error connecting device:', err));
    }

    function disconnectDevice(mac) {
        var formData = new FormData();
        formData.set('action', 'disconnect_device');
        formData.set('device_mac', mac);
        formData.set('csrf_token', document.querySelector('meta[name="csrf-token"]').getAttribute('content'));
        
        fetch(root + 'action', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            }
        })
        .then(response => response.json())
        .then(data => {
            updateStatus();
        })
        .catch(err => console.error('Error disconnecting device:', err));
    }

    function removeDevice(mac) {
        if (!confirm('Remove this device? You will need to pair it again to reconnect.')) {
            return;
        }
        
        var formData = new FormData();
        formData.set('action', 'remove_device');
        formData.set('device_mac', mac);
        formData.set('csrf_token', document.querySelector('meta[name="csrf-token"]').getAttribute('content'));
        
        fetch(root + 'action', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            }
        })
        .then(response => response.json())
        .then(data => {
            updateStatus();
        })
        .catch(err => console.error('Error removing device:', err));
    }

    function submitAction(event, actionName) {
        event.preventDefault();
        var form = event.target;
        var formData = new FormData(form);
        if (actionName) {
            formData.set('action', actionName);
        }
        
        // Show loading state if scan
        if (actionName === 'scan') {
            document.getElementById('status-msg').innerHTML = '<strong>Status:</strong> Scanning...';
        }

        var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        fetch(root + 'action', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            updateStatus();
        })
        .catch(err => console.error('Error submitting action:', err));
    }
{% endblock %}
{% block content %}
    <div style="margin-bottom: 20px;">
        <!-- PHONE TETHERING SECTION -->
        <h3>📱 Phone Tethering Configuration</h3>
        <p style="font-size: 0.9em; color: #666;">This is your main internet connection device.</p>
        
        <form method="POST" onsubmit="submitAction(event, 'save')">
            <input type="hidden" name="action" value="save"/>
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
            <label>Phone Name: <input type="text" name="phone_name" value="{{ options.get('phone-name', '') }}" placeholder="Name"></label><br>
            <label>MAC: <input type="text" name="mac" value="{{ options.get('mac', '') }}" placeholder="00:00:00:00:00:00"></label><br>
            <label>Type: 
                <select name="phone_type">
                    <option value="android" {% if options.get('phone') == 'android' %}selected{% endif %}>Android</option>
                    <option value="ios" {% if options.get('phone') == 'ios' %}selected{% endif %}>iOS</option>
                </select>
            </label><br>
            <label>IP: <input type="text" name="ip" value="{{ options.get('ip', '') }}" placeholder="Optional"></label><br>
            <label>DNS: <input type="text" name="dns" value="{{ options.get('dns', '') }}" placeholder="Optional"></label><br>
            <input type="submit" value="Save & Connect">
        </form>
        
        <div style="margin-top: 10px;">
            <form method="POST" style="margin-bottom: 10px;" onsubmit="submitAction(event, 'pair')">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <input type="hidden" name="action" value="pair"/>
                <input type="hidden" name="device_type" value="phone"/>
                <input type="submit" value="Pair Phone" {% if not options.get('mac') %}disabled{% endif %}>
            </form>
            
            <form method="POST" style="display:inline; margin-right: 5px;" onsubmit="submitAction(event, 'trust')">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <input type="hidden" name="action" value="trust"/>
                <input type="submit" value="Trust" {% if not options.get('mac') %}disabled{% endif %}>
            </form>
            
            <form method="POST" style="display:inline;" onsubmit="submitAction(event, 'disconnect')">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <input type="hidden" name="action" value="disconnect"/>
                <input type="submit" value="Disconnect" {% if not options.get('phone-name') %}disabled{% endif %}>
            </form>
            
            <form method="POST" style="display:inline; margin-left: 5px;" onsubmit="submitAction(event, 'fix_bt')">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <input type="hidden" name="action" value="fix_bt"/>
                <input type="submit" value="Fix BT (Soft Reset)" style="background-color: #ff9800; color: white; border: none; cursor: pointer;">
            </form>
        </div>
        
        <hr style="margin: 20px 0;">
        
        <!-- OTHER DEVICES SECTION -->
        <h3>⌨️ Other Bluetooth Devices</h3>
        <p style="font-size: 0.9em; color: #666;">Pair keyboards, mice, and other Bluetooth devices here. These won't affect your phone tethering connection.</p>
        
        <!-- Pair New Device Form -->
        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
            <h4 style="margin-top: 0;">Pair New Device</h4>
            <form method="POST" onsubmit="submitAction(event, 'pair_device')">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <input type="hidden" name="action" value="pair_device"/>
                
                <label style="display: block; margin-bottom: 10px;">
                    Device Name:
                    <input type="text" name="device_name" placeholder="e.g., Bluetooth Keyboard" style="margin-left: 10px; padding: 5px; width: 200px;">
                </label>
                
                <label style="display: block; margin-bottom: 10px;">
                    Device MAC:
                    <input type="text" name="device_mac" placeholder="00:00:00:00:00:00" style="margin-left: 10px; padding: 5px; width: 200px;">
                </label>
                
                <label style="display: block; margin-bottom: 10px;">
                    Device Type:
                    <select name="device_type" style="margin-left: 10px; padding: 5px;">
                        <option value="keyboard">⌨️ Keyboard</option>
                        <option value="mouse">🖱️ Mouse</option>
                        <option value="headset">🎧 Headset</option>
                        <option value="other">🔧 Other</option>
                    </select>
                </label>
                
                <input type="submit" value="Pair Device" style="padding: 8px 16px; font-size: 14px; margin-top: 5px;">
            </form>
        </div>
        
        <!-- Paired Devices List -->
        <div id="paired-devices-list">
            <h4>Paired Devices</h4>
            <div id="paired-devices-container">
                <!-- Will be populated by JavaScript -->
            </div>
        </div>
        
        <hr style="margin: 20px 0;">
        
        <!-- SCAN SECTION -->
        <h3>🔍 Scan for Devices</h3>
        <div style="margin-top: 10px;">
            <form method="POST" style="display:inline;" onsubmit="submitAction(event, 'scan')">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <input type="hidden" name="action" value="scan"/>
                <input type="submit" value="Scan (20s)">
            </form>
        </div>
        
        <div id="scan-results-container">
        {% if scan_results %}
            <h4>Discovered Devices (Click to copy MAC)</h4>
            <ul style="list-style-type: none; padding: 0;">
                {% for dev in scan_results %}
                    <li style="padding: 5px; border-bottom: 1px solid #ccc;">
                        <a href="#" onclick="copyMAC('{{ dev.mac }}'); return false;" style="text-decoration: none; color: inherit;">
                            <strong>{{ dev.mac }}</strong> - {{ dev.name }}
                        </a>
                    </li>
                {% endfor %}
            </ul>
        {% endif %}
        </div>
        
        <p id="status-msg"><strong>Status:</strong> {{ error }}</p>
    </div>
    <hr/>
    <input type="text" id="searchText" placeholder="Search for ..." title="Type in a filter">
    <table id="tableOptions">
        <tr>
            <th>Item</th>
            <th>Configuration</th>
        </tr>
        <tr>
            <td data-label="bluetooth">Bluetooth</td>
            <td id="bt-info">{{bluetooth|safe}}</td>
        </tr>
        <tr>
            <td data-label="device">Device</td>
            <td id="dev-info">{{device|safe}}</td>
        </tr>
        <tr>
            <td data-label="connection">Connection</td>
            <td id="conn-info">{{connection|safe}}</td>
        </tr>
    </table>
{% endblock %}
"""

# We all love crazy regex patterns
MAC_PTTRN = r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"
IP_PTTRN = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
DNS_PTTRN = r"^\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(\s*[ ,;]\s*\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})*\s*$"

class BTLeash(plugins.Plugin):
    __author__ = "@V0rT3x"
    __version__ = "1.0"
    __license__ = "GPL3"
    __description__ = "A complete Bluetooth tethering and device manager plugin with multi-device support."

    def __init__(self):
        self.ready = False
        self.options = dict()
        self.phone_name = None
        self.mac = None
        self.gateway = None
        self.error_message = "Configuration not loaded yet."
        self.config_path = '/etc/pwnagotchi/config.toml'
        self.scan_results = []
        self.scanning = False
        # NEW: Track additional paired devices (keyboards, etc.)
        self.paired_devices = []  # List of {mac, name, type, paired_at}
        self.pairing_device_mac = None  # Temporary MAC for pairing non-phone devices
        self.pairing_in_progress = False
        self.ui_status = "-"
        self.stop_event = threading.Event()
        self.status_thread = None
        self.status_cache = {
            'bluetooth': "Not configured",
            'device': "Not configured",
            'connection': "Not configured",
            'paired_devices': []
        }
        self.last_web_request = 0
        self._prev_ui_status = None

    # Add new methods
    def load_paired_devices(self):
        """Force sync with the system's paired devices list"""
        try:
            system_devices = []
            # Get actual paired devices from the OS
            # Use subprocess directly to avoid exception on non-zero exit code (e.g. no controller)
            result = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True)
            
            if result.returncode != 0:
                # Log as debug to avoid spamming errors if BT is not ready yet
                logging.debug(f"[BT-Tether] 'bluetoothctl devices' returned {result.returncode}")
                return
            
            # Pattern to catch: Device XX:XX:XX:XX:XX:XX DeviceName
            for line in result.stdout.splitlines():
                match = re.search(r"Device\s+([0-9A-F:]{17})\s+(.*)", line, re.IGNORECASE)
                if match:
                    mac = match.group(1)
                    name = match.group(2)
                    
                    # Try to find existing metadata (like 'type') from options if available
                    config_devices = self.options.get('paired-evices', [])
                    existing_meta = next((d for d in config_devices if d['mac'] == mac), {})
                    
                    system_devices.append({
                        'mac': mac,
                        'name': name,
                        'type': existing_meta.get('type', 'other'),
                        'paired_at': existing_meta.get('paired_at', 'unknown')
                    })

            self.paired_devices = system_devices
            logging.info(f"[BT-Tether] Synced {len(self.paired_devices)} devices from system")
        except Exception as e:
            logging.error(f"[BT-Tether] Error syncing paired devices: {e}")

    def save_paired_device(self, mac, name, device_type):
        """Save a newly paired device to config"""
        try:
            import datetime
            device_entry = {
                'mac': mac,
                'name': name,
                'type': device_type,
                'paired_at': str(datetime.datetime.now())
            }
            d
            # Remove if already exists
            self.paired_devices = [d for d in self.paired_devices if d.get('mac') != mac]
            # Add new entry
            self.paired_devices.append(device_entry)
            
            # Save to config
            config = pwnagotchi.config
            if 'bt-tether' not in config['main']['plugins']:
                config['main']['plugins']['bt-tether'] = {}
            
            config['main']['plugins']['bt-tether']['paired-devices'] = self.paired_devices
            save_config(config, self.config_path)
            
            logging.info(f"[BT-Tether] Saved paired device: {name} ({mac})")
            return True
        except Exception as e:
            logging.error(f"[BT-Tether] Error saving paired device: {e}")
            return False

    def remove_paired_device(self, mac):
        """Remove a paired device from config"""
        try:
            self.paired_devices = [d for d in self.paired_devices if d.get('mac') != mac]
            
            config = pwnagotchi.config
            if 'bt-tether' in config['main']['plugins']:
                config['main']['plugins']['bt-tether']['paired-devices'] = self.paired_devices
                save_config(config, self.config_path)
            
            logging.info(f"[BT-Tether] Removed paired device: {mac}")
            return True
        except Exception as e:
            logging.error(f"[BT-Tether] Error removing paired device: {e}")
            return False

    @staticmethod
    def exec_cmd(cmd, args, pattern=None, log_error=True, timeout=10):
        try:
            result = subprocess.run([cmd] + args, check=True, capture_output=True, text=True, timeout=timeout)
            if pattern:
                return result.stdout.find(pattern)
            return result
        except subprocess.CalledProcessError as e:
            if log_error:
                logging.error(f"[BT-Tether] Command {cmd} failed: {e.stderr}")
            raise Exception(f"{e.stderr.strip() if e.stderr else str(e)}")
        except Exception as exp:
            if log_error:
                logging.error(f"[BT-Tether] Error with {cmd}")
                logging.error(f"[BT-Tether] Exception : {exp}")
            raise exp

    def bluetoothctl(self, args, pattern=None, log_error=True):
        return self.exec_cmd("bluetoothctl", args, pattern, log_error)

    def nmcli(self, args, pattern=None, log_error=True):
        return self.exec_cmd("nmcli", args, pattern, log_error)

    def bluetoothctl_script(self, commands, delay=1, timeout=30):
        try:
            process = subprocess.Popen(
                ['bluetoothctl'], 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            output = ""
            for cmd in commands:
                process.stdin.write(f"{cmd}\n")
                process.stdin.flush()
                if delay > 0:
                    time.sleep(delay) # Crucial: give the daemon time to process each step
            
            stdout, stderr = process.communicate(input="exit\n", timeout=timeout)
            logging.debug(f"[BT-Tether] bluetoothctl output: {stdout}")
            return stdout
        except Exception as e:
            logging.error(f"[BT-Tether] bluetoothctl script failed: {e}")
            raise e

    def _scan_thread(self):
        self.scanning = True
        try:
            self.error_message = "Scanning... please wait."
            self.bluetoothctl(["power", "on"])
            
            # Start scan
            scan_proc = subprocess.Popen(["bluetoothctl", "scan", "on"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(20) # Scan for 20 seconds
            scan_proc.terminate() # Gracefully stop
            
            # Retrieve devices
            result = self.bluetoothctl(["devices"])
            self.scan_results = []
            for line in result.stdout.splitlines():
                parts = line.split(" ", 2)
                if len(parts) >= 3 and parts[0] == "Device":
                    self.scan_results.append({'mac': parts[1], 'name': parts[2]})
            
            self.error_message = f"Found {len(self.scan_results)} devices."
        except Exception as e:
            self.error_message = f"Scan error: {e}"
        finally:
            self.scanning = False

    def _pair_phone_thread(self, mac, device_type):
        """Background thread for pairing phone"""
        self.pairing_in_progress = True
        try:
            logging.info(f"[BT-Tether] Starting pairing for {mac}")
            self.error_message = "Preparing Bluetooth adapter..."
            
            # Stop any scanning
            try:
                subprocess.run(["bluetoothctl", "scan", "off"], 
                             capture_output=True, timeout=3)
            except:
                pass
            
            self.bluetoothctl(["power", "on"])
            time.sleep(1)
            
            # Untrust device first to prevent auto-connection attempts
            try:
                self.bluetoothctl(["untrust", mac], log_error=False)
                time.sleep(1)
                logging.info(f"[BT-Tether] Untrusted device {mac} to ensure clean state.")
            except:
                pass

            # Remove device to start fresh
            try:
                self.bluetoothctl(["remove", mac], log_error=False)
                time.sleep(1)
                logging.info(f"[BT-Tether] Removed existing pairing for {mac}")
            except:
                pass
            
            # Configure agent
            try:
                subprocess.run(["bluetoothctl", "agent", "off"], 
                             capture_output=True, timeout=3)
                time.sleep(0.5)
            except:
                pass
            
            # Determine agent type
            if device_type == 'keyboard':
                agent_type = "DisplayOnly"
            else:
                agent_type = "NoInputNoOutput"
            
            # Scan for device
            self.error_message = "Scanning for device... Make sure device is discoverable!"
            logging.info(f"[BT-Tether] Starting scan for {mac}")
            
            scan_proc = subprocess.Popen(
                ["bluetoothctl", "scan", "on"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for device
            found = False
            for i in range(20):
                time.sleep(1)
                try:
                    devices = self.bluetoothctl(["devices"], log_error=False)
                    if mac.upper() in devices.stdout.upper():
                        found = True
                        logging.info(f"[BT-Tether] Device {mac} found after {i+1}s")
                        self.error_message = f"Device found! ({i+1}s)"
                        break
                except:
                    pass
            
            if not found:
                scan_proc.terminate()
                self.error_message = f"Device {mac} not found. Is Bluetooth enabled and discoverable?"
                logging.error(f"[BT-Tether] {self.error_message}")
                return
            
            # Trust device
            self.error_message = "Trusting device..."
            try:
                self.bluetoothctl(["trust", mac], log_error=False)
                time.sleep(0.5)
            except:
                pass
            
            # Pair with PIN/passkey display
            if device_type == 'keyboard':
                self.error_message = "⏳ Pairing... Watch for PIN below!"
            else:
                self.error_message = "⏳ Pairing... Auto-accepting passkey..."
            
            logging.info(f"[BT-Tether] Attempting to pair with {mac} (type: {device_type})")
            
            try:
                cmd = ['bluetoothctl']
                if shutil.which('stdbuf'):
                    cmd = ['stdbuf', '-oL', 'bluetoothctl']

                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=0
                )
                
                logging.info(f"[BT-Tether] Setting agent to {agent_type} inside session")
                proc.stdin.write("agent off\n")
                proc.stdin.flush()
                time.sleep(0.5)
                proc.stdin.write(f"agent {agent_type}\n")
                proc.stdin.flush()
                time.sleep(0.5)
                proc.stdin.write("default-agent\n")
                proc.stdin.flush()
                time.sleep(0.5)
                proc.stdin.write(f"pair {mac}\n")
                proc.stdin.flush()
                
                paired = False
                start_time = time.time()
                output_buffer = []
                displayed_pin = None
                displayed_passkey = None
                
                while time.time() - start_time < 60:
                    import select
                    ready = select.select([proc.stdout], [], [], 0.5)
                    
                    if ready[0]:
                        line = proc.stdout.readline()
                        if line:
                            output_buffer.append(line)
                            logging.info(f"[BT-Tether] bluetoothctl: {line.strip()}")
                            
                            # Extract PIN
                            if "Enter PIN code:" in line or "Request PIN code" in line:
                                import re as regex
                                pin_match = regex.search(r'(\d{4,8})', line)
                                if pin_match:
                                    displayed_pin = pin_match.group(1)
                                    self.error_message = f"🔑 ENTER THIS PIN ON YOUR KEYBOARD: {displayed_pin}"
                                    logging.info(f"[BT-Tether] PIN to enter on keyboard: {displayed_pin}")
                            
                            # Extract SSP Passkey (DisplayOnly)
                            if "passkey" in line.lower():
                                passkey_match = re.search(r'Passkey:.*?(\d{6})', line, re.IGNORECASE)
                                if passkey_match:
                                    displayed_passkey = passkey_match.group(1)
                                    self.error_message = f"🔑 TYPE THIS ON DEVICE: {displayed_passkey} + ENTER"
                                    logging.info(f"[BT-Tether] Passkey to type: {displayed_passkey}")

                            # Extract passkey
                            if "Confirm passkey" in line:
                                import re as regex
                                passkey_match = regex.search(r'(\d{6})', line)
                                if passkey_match:
                                    displayed_passkey = passkey_match.group(1)
                                    if device_type == 'keyboard':
                                        self.error_message = f"🔑 PASSKEY: {displayed_passkey} - Verify it matches on device"
                                        logging.info(f"[BT-Tether] Passkey displayed: {displayed_passkey}")
                                    else:
                                        self.error_message = f"🔑 PASSKEY: {displayed_passkey} - Auto-confirming..."
                                        logging.info(f"[BT-Tether] Auto-confirming passkey: {displayed_passkey}")
                            
                            # Auto-confirm
                            if "yes/no" in line:
                                if device_type == 'keyboard':
                                    time.sleep(2)
                                    proc.stdin.write("yes\n")
                                    proc.stdin.flush()
                                    logging.info(f"[BT-Tether] Auto-confirmed after display")
                                else:
                                    logging.info(f"[BT-Tether] Auto-confirming")
                                    proc.stdin.write("yes\n")
                                    proc.stdin.flush()
                            
                            # Check success
                            if "Pairing successful" in line:
                                paired = True
                                logging.info(f"[BT-Tether] Pairing successful")
                                if displayed_passkey:
                                    self.error_message = f"✓ Paired! Passkey was: {displayed_passkey}"
                                elif displayed_pin:
                                    self.error_message = f"✓ Paired! PIN was: {displayed_pin}"
                                else:
                                    self.error_message = "✓ Pairing successful!"
                                break
                            
                            if "Failed to pair" in line:
                                logging.error(f"[BT-Tether] Pairing failed: {line}")
                                self.error_message = "⚠️ Pairing failed. Waiting for retry..."
                                displayed_passkey = None
                                displayed_pin = None
                    else:
                        if device_type != 'keyboard':
                            proc.stdin.write("yes\n")
                            proc.stdin.flush()
                
                proc.stdin.write("exit\n")
                proc.stdin.flush()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                
                # Verify pairing
                time.sleep(1)
                info = self.bluetoothctl(["info", mac], log_error=False)
                
                if "Paired: yes" in info.stdout:
                    if not paired:
                        self.error_message = "✓ Pairing successful!"
                    logging.info(f"[BT-Tether] Pairing verified via info")
                    
                    # Connect if phone
                    if device_type == 'phone':
                        self.error_message = "Connecting to device..."
                        try:
                            self.bluetoothctl(["trust", mac], log_error=False)
                            time.sleep(0.5)
                            
                            connect_result = subprocess.run(
                                ["bluetoothctl", "connect", mac],
                                capture_output=True,
                                text=True,
                                timeout=15
                            )
                            
                            if "Connection successful" in connect_result.stdout or connect_result.returncode == 0:
                                self.error_message = "✓ Paired and connected! Enable BT Tethering on phone, then click 'Save & Connect'"
                            else:
                                self.error_message = "✓ Paired! Connection failed - enable BT Tethering on phone, then click 'Save & Connect'"
                        except Exception as e:
                            self.error_message = "✓ Paired! Connection failed - enable BT Tethering on phone, then click 'Save & Connect'"
                else:
                    if displayed_passkey:
                        self.error_message = f"✗ Pairing failed. Passkey was: {displayed_passkey}. Check device and try again."
                    else:
                        self.error_message = f"✗ Pairing failed. Check device and try again."
                    logging.error(f"[BT-Tether] Pairing verification failed")
                
            except Exception as e:
                self.error_message = f"Pairing error: {str(e)}"
                logging.error(f"[BT-Tether] Pairing exception: {e}")
            
            scan_proc.terminate()
            
        except Exception as e:
            self.error_message = f"Pairing failed: {str(e)}"
            logging.error(f"[BT-Tether] Pairing outer exception: {e}")
            try:
                subprocess.run(["bluetoothctl", "scan", "off"], 
                             capture_output=True, timeout=3)
            except:
                pass
        finally:
            self.pairing_in_progress = False

    def _pair_device_thread(self, mac, device_name, device_type):
        """Background thread for pairing non-phone devices"""
        self.pairing_in_progress = True
        self.pairing_device_mac = mac
        
        try:
            logging.info(f"[BT-Tether] Starting pairing for device {device_name} ({mac})")
            self.error_message = "Preparing Bluetooth adapter..."
            
            # Stop any scanning
            try:
                subprocess.run(["bluetoothctl", "scan", "off"], 
                             capture_output=True, timeout=3)
            except:
                pass
            
            self.bluetoothctl(["power", "on"])
            time.sleep(1)
            
            # Untrust device first to prevent auto-connection attempts
            try:
                self.bluetoothctl(["untrust", mac], log_error=False)
                time.sleep(1)
                logging.info(f"[BT-Tether] Untrusted device {mac} to ensure clean state.")
            except:
                pass

            # Remove device to start fresh
            try:
                self.bluetoothctl(["remove", mac], log_error=False)
                time.sleep(1)
                logging.info(f"[BT-Tether] Removed existing pairing for {mac}")
            except:
                pass
            
            # Configure agent
            try:
                subprocess.run(["bluetoothctl", "agent", "off"], 
                             capture_output=True, timeout=3)
                time.sleep(0.5)
            except:
                pass
            
            # Determine agent type
            if device_type == 'keyboard':
                agent_type = "DisplayOnly"
            else:
                agent_type = "NoInputNoOutput"
            
            # Scan for device
            self.error_message = "Scanning for device... Make sure it's discoverable!"
            logging.info(f"[BT-Tether] Starting scan for {mac}")
            
            scan_proc = subprocess.Popen(
                ["bluetoothctl", "scan", "on"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for device
            found = False
            for i in range(20):
                time.sleep(1)
                try:
                    devices = self.bluetoothctl(["devices"], log_error=False)
                    if mac.upper() in devices.stdout.upper():
                        found = True
                        logging.info(f"[BT-Tether] Device {mac} found after {i+1}s")
                        self.error_message = f"Device found! ({i+1}s)"
                        break
                except:
                    pass
            
            if not found:
                scan_proc.terminate()
                self.error_message = f"Device not found. Is Bluetooth enabled and discoverable?"
                logging.error(f"[BT-Tether] {self.error_message}")
                return
            
            # Trust device
            self.error_message = "Trusting device..."
            try:
                self.bluetoothctl(["trust", mac], log_error=False)
                time.sleep(0.5)
            except:
                pass
            
            # Pair with PIN/passkey display
            if device_type == 'keyboard':
                self.error_message = "⏳ Pairing... Watch for PIN below!"
            else:
                self.error_message = "⏳ Pairing... Auto-accepting passkey..."
            
            logging.info(f"[BT-Tether] Attempting to pair with {mac} (type: {device_type})")
            
            try:
                cmd = ['bluetoothctl']
                if shutil.which('stdbuf'):
                    cmd = ['stdbuf', '-oL', 'bluetoothctl']

                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=0
                )
                
                logging.info(f"[BT-Tether] Setting agent to {agent_type} inside session")
                proc.stdin.write("agent off\n")
                proc.stdin.flush()
                time.sleep(0.5)
                proc.stdin.write(f"agent {agent_type}\n")
                proc.stdin.flush()
                time.sleep(0.5)
                proc.stdin.write("default-agent\n")
                proc.stdin.flush()
                time.sleep(0.5)
                proc.stdin.write(f"pair {mac}\n")
                proc.stdin.flush()
                
                paired = False
                start_time = time.time()
                output_buffer = []
                displayed_pin = None
                displayed_passkey = None
                
                while time.time() - start_time < 120:
                    import select
                    ready = select.select([proc.stdout], [], [], 0.5)
                    
                    if ready[0]:
                        line = proc.stdout.readline()
                        if line:
                            output_buffer.append(line)
                            logging.info(f"[BT-Tether] bluetoothctl: {line.strip()}")
                            
                            # Extract PIN
                            if "Enter PIN code:" in line or "Request PIN code" in line:
                                import re as regex
                                pin_match = regex.search(r'(\d{4,8})', line)
                                if pin_match:
                                    displayed_pin = pin_match.group(1)
                                    self.error_message = f"🔑 ENTER THIS PIN ON YOUR {device_type.upper()}: {displayed_pin}"
                                    logging.info(f"[BT-Tether] PIN to enter: {displayed_pin}")
                            
                            # Extract SSP Passkey (DisplayOnly)
                            if "passkey" in line.lower():
                                passkey_match = re.search(r'Passkey:.*?(\d{6})', line, re.IGNORECASE)
                                if passkey_match:
                                    displayed_passkey = passkey_match.group(1)
                                    self.error_message = f"🔑 TYPE THIS ON {device_type.upper()}: {displayed_passkey} + ENTER"
                                    logging.info(f"[BT-Tether] Passkey to type: {displayed_passkey}")

                            # Extract passkey
                            if "Confirm passkey" in line:
                                import re as regex
                                passkey_match = regex.search(r'(\d{6})', line)
                                if passkey_match:
                                    displayed_passkey = passkey_match.group(1)
                                    if device_type == 'keyboard':
                                        self.error_message = f"🔑 PASSKEY: {displayed_passkey} - Verify it matches on device"
                                        logging.info(f"[BT-Tether] Passkey displayed: {displayed_passkey}")
                                    else:
                                        self.error_message = f"🔑 PASSKEY: {displayed_passkey} - Auto-confirming..."
                                        logging.info(f"[BT-Tether] Auto-confirming passkey: {displayed_passkey}")
                            
                            # Auto-confirm
                            if "yes/no" in line:
                                if device_type == 'keyboard':
                                    time.sleep(2)
                                    proc.stdin.write("yes\n")
                                    proc.stdin.flush()
                                    logging.info(f"[BT-Tether] Auto-confirmed after display")
                                else:
                                    logging.info(f"[BT-Tether] Auto-confirming")
                                    proc.stdin.write("yes\n")
                                    proc.stdin.flush()
                            
                            # Check success
                            if "Pairing successful" in line:
                                paired = True
                                logging.info(f"[BT-Tether] Pairing successful")
                                if displayed_passkey:
                                    self.error_message = f"✓ Paired {device_name}! Passkey: {displayed_passkey}"
                                elif displayed_pin:
                                    self.error_message = f"✓ Paired {device_name}! PIN: {displayed_pin}"
                                else:
                                    self.error_message = f"✓ Paired {device_name}!"
                                break
                            
                            if "Failed to pair" in line:
                                logging.error(f"[BT-Tether] Pairing failed: {line}")
                                self.error_message = "⚠️ Pairing failed. Waiting for retry..."
                                displayed_passkey = None
                                displayed_pin = None
                    else:
                        if device_type != 'keyboard':
                            proc.stdin.write("yes\n")
                            proc.stdin.flush()
                
                proc.stdin.write("exit\n")
                proc.stdin.flush()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                
                # Verify pairing
                time.sleep(1)
                info = self.bluetoothctl(["info", mac], log_error=False)
                
                if "Paired: yes" in info.stdout:
                    # Save to paired devices list
                    self.save_paired_device(mac, device_name, device_type)
                    if not paired:
                        self.error_message = f"✓ Paired {device_name}!"
                    logging.info(f"[BT-Tether] Device paired and saved")
                else:
                    self.error_message = f"✗ Pairing failed for {device_name}"
                    logging.error(f"[BT-Tether] Pairing verification failed")
                
            except Exception as e:
                self.error_message = f"Pairing error: {str(e)}"
                logging.error(f"[BT-Tether] Pairing exception: {e}")
            
            scan_proc.terminate()
            
        except Exception as e:
            self.error_message = f"Pairing failed: {str(e)}"
            logging.error(f"[BT-Tether] Pairing outer exception: {e}")
            try:
                subprocess.run(["bluetoothctl", "scan", "off"], 
                             capture_output=True, timeout=3)
            except:
                pass
        finally:
            self.pairing_device_mac = None
            self.pairing_in_progress = False

    def recover_bluetooth(self):
        if self.pairing_in_progress:
            logging.info("[BT-Tether] Pairing in progress, skipping recovery.")
            return

        logging.info("[BT-Tether] Attempting to recover crashed BT firmware...")
        self.error_message = "Attempting to recover Bluetooth firmware..."
        
        def _recover():
            try:
                # 1. Stop high-level services
                subprocess.run(["systemctl", "stop", "bluetooth"])
                
                # 2. Re-trigger the UART bus
                uart_ids = []
                base_path = "/sys/bus/amba/drivers/uart-pl011"
                if os.path.exists(base_path):
                    for item in os.listdir(base_path):
                        if item.endswith(".serial"):
                            uart_ids.append(item)
                
                if not uart_ids:
                    # Common IDs for Pi Zero 2 W / Pi 3 / Pi 4
                    uart_ids = ["3f201000.serial", "40001100.serial", "fe201000.serial"]

                for uart_id in uart_ids:
                    unbind_path = os.path.join(base_path, "unbind")
                    bind_path = os.path.join(base_path, "bind")
                    
                    if os.path.exists(unbind_path):
                        try:
                            with open(unbind_path, "w") as f:
                                f.write(uart_id)
                            time.sleep(1)
                        except Exception:
                            pass

                    if os.path.exists(bind_path):
                        try:
                            with open(bind_path, "w") as f:
                                f.write(uart_id)
                            logging.info(f"[BT-Tether] Reset UART {uart_id}")
                        except Exception as e:
                            logging.error(f"[BT-Tether] Bind {uart_id} failed: {e}")

                # 3. Restart services
                subprocess.run(["systemctl", "restart", "hciuart"])
                time.sleep(2)
                subprocess.run(["systemctl", "start", "bluetooth"])
                time.sleep(2)
                
                # Re-power on adapter
                self.bluetoothctl(["power", "on"])
                self.error_message = "Bluetooth recovery completed."
                logging.info("[BT-Tether] Bluetooth recovery completed.")
                
                # Re-establish connection if configured
                if self.phone_name:
                    time.sleep(5) # Wait for services to settle
                    self.nmcli(["connection", "up", self.phone_name], log_error=False)
                    
            except Exception as e:
                logging.error(f"[BT-Tether] Recovery failed: {e}")
                self.error_message = f"Recovery failed: {e}"

        threading.Thread(target=_recover).start()

    def _get_connected_macs_fast(self):
        """
        Get connected MAC addresses using filesystem checks only (Zero Overhead).
        Avoids subprocess calls like hcitool which cause UI freezes.
        """
        macs = set()
        # Method 1: Check debugfs (covers all BT connections if available)
        try:
            if os.path.exists('/sys/kernel/debug/bluetooth/hci0/conn'):
                with open('/sys/kernel/debug/bluetooth/hci0/conn', 'r') as f:
                    for line in f:
                        # Format: <handle> <mac> <type> ...
                        parts = line.split()
                        if len(parts) >= 2:
                            # MAC is usually the second element
                            if re.match(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', parts[1]):
                                macs.add(parts[1].upper())
        except Exception:
            pass
            
        # Method 2: Check input devices (covers Keyboards/Mice if debugfs fails)
        try:
            if os.path.exists('/proc/bus/input/devices'):
                with open('/proc/bus/input/devices', 'r') as f:
                    content = f.read()
                    # Look for Uniq=XX:XX:XX:XX:XX:XX
                    found = re.findall(r'Uniq=([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})', content)
                    for m in found:
                        macs.add(m.upper())
        except Exception:
            pass
            
        return macs

    def _status_worker(self):
        while not self.stop_event.is_set():
            if self.ready and self.phone_name and self.mac:
                new_status = "-"
                try:
                    # 1. Check for BNEP interface (indicates Bluetooth PAN connection)
                    # This avoids spawning subprocesses like hcitool/nmcli which cause UI freezes
                    bnep_exists = False
                    try:
                        if os.path.exists('/sys/class/net'):
                            for iface in os.listdir('/sys/class/net'):
                                if iface.startswith('bnep'):
                                    bnep_exists = True
                                    break
                    except Exception:
                        pass

                    if bnep_exists:
                        # 2. Check Connectivity via Socket
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.settimeout(0.1)
                        try:
                            s.connect((self.gateway, 53))
                            new_status = "U"
                        except Exception:
                            new_status = "C"
                        finally:
                            s.close()
                    else:
                        # 2. Check Bluetooth Link (Zero Overhead)
                        # If not tethered, check if at least connected via BT
                        connected_macs = self._get_connected_macs_fast()
                        if self.mac.upper() in connected_macs:
                            new_status = "C"
                        else:
                            new_status = "D"
                except Exception:
                    pass
                self.ui_status = new_status
            else:
                self.ui_status = "D"

            if time.time() - self.last_web_request < 15:
                try:
                    self._update_web_cache()
                except Exception as e:
                    logging.error(f"[BT-Tether] Error updating web cache: {e}")
            
            time.sleep(5)

    def _update_web_cache(self):
        # Optimized: Avoid heavy nmcli/bluetoothctl calls that freeze the UI
        bluetooth = "Detailed info disabled to prevent UI freeze"
        device = "Detailed info disabled to prevent UI freeze"
        connection = "Detailed info disabled to prevent UI freeze"

        # Fast check for connected devices (Zero Overhead)
        connected_macs = self._get_connected_macs_fast()

        devices_with_status = []
        for device_item in self.paired_devices:
            device_info = device_item.copy()
            device_info['connected'] = device_item['mac'].upper() in connected_macs
            devices_with_status.append(device_info)

        self.status_cache = {
            'bluetooth': bluetooth,
            'device': device,
            'connection': connection,
            'paired_devices': devices_with_status
        }

    def get_current_status(self):
        return (
            self.status_cache['bluetooth'],
            self.status_cache['device'],
            self.status_cache['connection'],
            self.status_cache['paired_devices']
        )

    def on_loaded(self):
        self.load_paired_devices()
        logging.info("[BT-Tether] plugin loaded.")
        self.stop_event.clear()
        self.status_thread = threading.Thread(target=self._status_worker)
        self.status_thread.daemon = True
        self.status_thread.start()

    def on_config_changed(self, config):
        if config and 'main' in config and 'plugins' in config['main'] and 'bt-tether' in config['main']['plugins']:
            self.options = config['main']['plugins']['bt-tether']

        self.load_paired_devices()
        if "phone-name" not in self.options:
            self.error_message = "Phone name not provided in config.toml"
            logging.error(f"[BT-Tether] {self.error_message}")
            return
        if not ("mac" in self.options and re.match(MAC_PTTRN, self.options["mac"])):
            self.error_message = "MAC address not provided or invalid in config.toml"
            logging.error(f"[BT-Tether] {self.error_message}")
            return

        if not ("phone" in self.options and self.options["phone"].lower() in ["android", "ios"]):
            self.error_message = "Phone type not supported in config.toml (only 'android' or 'ios')"
            logging.error(f"[BT-Tether] {self.error_message}")
            return
        if self.options["phone"].lower() == "android":
            address = self.options.get("ip", "192.168.44.2")
            gateway = "192.168.44.1"
        elif self.options["phone"].lower() == "ios":
            address = self.options.get("ip", "172.20.10.2")
            gateway = "172.20.10.1"
        self.gateway = gateway
        if not re.match(IP_PTTRN, address):
            self.error_message = f"IP address '{address}' is invalid."
            logging.error(f"[BT-Tether] {self.error_message}")
            return

        self.phone_name = self.options["phone-name"] + " Network"
        self.mac = self.options["mac"]
        dns = self.options.get("dns", "8.8.8.8 1.1.1.1")
        if not re.match(DNS_PTTRN, dns):
            if dns == "":
                self.error_message = "DNS setting is empty in config.toml"
                logging.error(f"[BT-Tether] {self.error_message}")
            else:
                self.error_message = f"Wrong DNS setting in config.toml: '{dns}'"
                logging.error(f"[BT-Tether] {self.error_message}")
            return
        dns = re.sub("[\s,;]+", " ", dns).strip()  # DNS cleaning

        pairing_triggered = False
        try:
            info = self.bluetoothctl(["info", self.mac], log_error=False)
            if "Paired: yes" not in info.stdout:
                logging.info(f"[BT-Tether] Phone {self.mac} not paired. Initiating pairing...")
                pairing_triggered = True
                if not self.pairing_in_progress:
                    threading.Thread(target=self._pair_phone_thread, args=(self.mac, 'phone')).start()
        except Exception as e:
            logging.error(f"[BT-Tether] Error checking pairing status: {e}")

        try:
            # To ensure a clean state, we'll delete the connection if it exists.
            try:
                self.nmcli(["connection", "delete", self.phone_name])
                logging.info(f"[BT-Tether] Removed existing connection profile '{self.phone_name}'.")
            except Exception:
                # This is expected if the connection doesn't exist.
                logging.info(f"[BT-Tether] Connection profile '{self.phone_name}' did not exist, creating new.")
                pass

            # Create the new connection with all settings.
            # Metric is set to 200 to prefer this connection over USB tethering.
            logging.info(f"[BT-Tether] Creating new connection profile '{self.phone_name}'.")
            
            self.nmcli(
                [
                    "connection", "add",
                    "connection.type", "bluetooth",
                    "con-name", self.phone_name,
                    "bluetooth.type", "panu",
                    "bluetooth.bdaddr", f"{self.mac}",
                    "connection.autoconnect", "yes",
                    "connection.autoconnect-retries", "0",
                    "ipv4.method", "manual",
                    "ipv4.dns", f"{dns}",
                    "ipv4.addresses", f"{address}/24",
                    "ipv4.gateway", f"{gateway}",
                    "ipv4.route-metric", "200",
                ]
            )
            # Configure Device to autoconnect
            try:
                self.nmcli([
                    "device", "set", f"{self.mac}",
                    "autoconnect", "yes",
                    "managed", "yes"
                ], log_error=False)
            except Exception:
                pass
            self.nmcli(["connection", "reload"])
            self.ready = True
            self.error_message = ""  # Clear error on success
            logging.info(f"[BT-Tether] Connection {self.phone_name} configured")
        except Exception as e:
            self.error_message = f"Error while configuring with nmcli: {e}"
            logging.error(f"[BT-Tether] {self.error_message}")
            return
        if not pairing_triggered:
            if not pairing_triggered:
                try:
                    logging.info(f"[BT-Tether] Scanning for {self.mac}...")
                    try:
                        scan_proc = subprocess.Popen(["bluetoothctl", "scan", "on"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        for _ in range(20):
                            time.sleep(1)
                            devices = self.bluetoothctl(["devices"], log_error=False)
                            if self.mac.upper() in devices.stdout.upper():
                                break
                        scan_proc.terminate()
                    except Exception:
                        pass
                    self.nmcli(["connection", "up", f"{self.phone_name}"], log_error=False)
                except Exception as e:
                    # This error might be normal if the phone is not yet available
                    self.error_message = f"Failed to connect to device: {e}"
                    logging.debug(f"[BT-Tether] {self.error_message}")
                    logging.error(
                        f"[BT-Tether] Failed to connect to device: have you enabled bluetooth tethering on your phone?"
                    )

    def on_ready(self, agent):
        try:
            logging.info(f"[BT-Tether] Disabling bettercap's BLE module")
            agent.run("ble.recon off", verbose_errors=False)
        except Exception as e:
            logging.info(f"[BT-Tether] Bettercap BLE was already off.")

    def on_unload(self, ui):
        self.stop_event.set()
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=2)
        with ui._lock:
            ui.remove_element("bluetooth")
        try:
            self.nmcli(["connection", "down", f"{self.phone_name}"])
        except Exception as e:
            logging.error(f"[BT-Tether] Failed to disconnect from device: {e}")

    def on_ui_setup(self, ui):
        with ui._lock:
            ui.add_element(
                "bluetooth",
                LabeledValue(
                    color=BLACK,
                    label="BT",
                    value="-",
                    position=(ui.width() / 2 - 10, 0),
                    label_font=fonts.Bold,
                    text_font=fonts.Medium,
                ),
            )

    def on_ui_update(self, ui):
        if not self.ready:
            return
        if self.ui_status == self._prev_ui_status:
            return
        with ui._lock:
            ui.set("bluetooth", self.ui_status)
            self._prev_ui_status = self.ui_status
            
    def on_webhook(self, path, request):
        if path == "status":
            self.last_web_request = time.time()
            bluetooth, device, connection, paired_devices = self.get_current_status()
            return jsonify({'bluetooth': bluetooth, 'device': device, 'connection': connection, 'error': self.error_message, 'scan_results': self.scan_results, 'paired_devices': paired_devices})

        if request.method == "POST" or path == "action":
            action = request.form.get('action')
            if action == "save":
                self.options['phone-name'] = request.form.get('phone_name')
                self.options['mac'] = request.form.get('mac')
                self.options['phone'] = request.form.get('phone_type')
                if request.form.get('ip'):
                    self.options['ip'] = request.form.get('ip')
                if request.form.get('dns'):
                    self.options['dns'] = request.form.get('dns')

                try:
                    config = pwnagotchi.config
                    if 'bt-tether' not in config['main']['plugins']:
                        config['main']['plugins']['bt-tether'] = {}

                    update_data = {
                        'enabled': True,
                        'phone-name': self.options['phone-name'],
                        'mac': self.options['mac'],
                        'phone': self.options['phone']
                    }
                    if 'ip' in self.options:
                        update_data['ip'] = self.options['ip']
                    if 'dns' in self.options:
                        update_data['dns'] = self.options['dns']

                    config['main']['plugins']['bt-tether'].update(update_data)
                    save_config(config, self.config_path)
                except Exception as e:
                    logging.error(f"[BT-Tether] Error saving config: {e}")

                self.on_config_changed(None)
            elif action == "trust":
                mac = self.options.get('mac')
                if mac:
                    try:
                        self.bluetoothctl(["trust", mac])
                        self.error_message = f"Trusted {mac}"
                    except Exception as e:
                        self.error_message = f"Error trusting: {e}"
            elif action == "pair":
                mac = self.options.get('mac')
                if not mac or not re.match(MAC_PTTRN, mac):
                    self.error_message = "No valid MAC address set"
                elif self.pairing_in_progress:
                    return jsonify({'success': False, 'error': "Pairing already in progress..."})
                else:
                    device_type = request.form.get('device_type', 'phone')
                    threading.Thread(target=self._pair_phone_thread, args=(mac, device_type)).start()
                    self.error_message = "Pairing started in background... Watch status for updates!"

            elif action == "remove":
                mac = self.options.get('mac')
                if mac:
                    try:
                        self.bluetoothctl(["remove", mac])
                        self.error_message = f"Removed {mac}"
                    except Exception as e:
                        self.error_message = f"Error removing: {e}"
            elif action == "disconnect":
                if self.phone_name:
                    try:
                        self.nmcli(["connection", "down", self.phone_name])
                        self.error_message = f"Disconnected {self.phone_name}"
                    except Exception as e:
                        self.error_message = f"Error disconnecting: {e}"
            elif action == "scan":
                if not self.scanning:
                    threading.Thread(target=self._scan_thread).start()
                    self.error_message = "Scanning started in background..."
                else:
                    self.error_message = "Scan already in progress."

            elif action == "pair_device":
                # Pair a non-phone device (keyboard, etc.)
                mac = request.form.get('device_mac')
                device_name = request.form.get('device_name', 'Unknown Device')
                device_type = request.form.get('device_type', 'other')
                
                if not mac or not re.match(MAC_PTTRN, mac):
                    self.error_message = "No valid MAC address provided for device pairing"
                    return jsonify({'success': False, 'error': self.error_message})
                elif self.pairing_in_progress:
                    return jsonify({'success': False, 'error': "Pairing already in progress..."})
                else:
                    threading.Thread(target=self._pair_device_thread, args=(mac, device_name, device_type)).start()
                    self.error_message = "Pairing started in background... Watch status for updates!"

            elif action == "remove_device":
                # Remove a non-phone paired device
                mac = request.form.get('device_mac')
                if mac:
                    try:
                        self.bluetoothctl(["remove", mac])
                        self.remove_paired_device(mac)
                        self.error_message = f"Removed device {mac}"
                    except Exception as e:
                        self.error_message = f"Error removing device: {e}"

            elif action == "connect_device":
                # Connect to a paired device
                mac = request.form.get('device_mac')
                if mac:
                    try:
                        self.bluetoothctl(["connect", mac])
                        self.error_message = f"Connected to {mac}"
                    except Exception as e:
                        self.error_message = f"Error connecting: {e}"

            elif action == "disconnect_device":
                # Disconnect a device
                mac = request.form.get('device_mac')
                if mac:
                    try:
                        self.bluetoothctl(["disconnect", mac])
                        self.error_message = f"Disconnected {mac}"
                    except Exception as e:
                        self.error_message = f"Error disconnecting: {e}"

            elif action == "fix_bt":
                self.recover_bluetooth()
                self.error_message = "Bluetooth recovery started..."

            if path == "action":
                return jsonify({'success': True, 'error': self.error_message})

        if path == "/" or not path:
            bluetooth, device, connection, _ = self.get_current_status()

            logging.debug(device)
            return render_template_string(
                TEMPLATE,
                title="BT-Tether",
                bluetooth=bluetooth,
                device=device,
                connection=connection,
                options=self.options,
                error=self.error_message,
                scan_results=self.scan_results
            )
        abort(404)
