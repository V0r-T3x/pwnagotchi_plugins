# Pwnagotchi Plugins

This repository contains a collection of custom plugins for [Pwnagotchi](https://pwnagotchi.ai/).

## Plugins List

### 🦷 BT Leash (`bt-leash.py`)
**Description**: A complete Bluetooth tethering and device manager plugin with multi-device support. It includes a Web UI for managing paired devices, scanning, and toggling tethering.
**Configuration**:
```toml
main.plugins.bt-leash.enabled = true
main.plugins.bt-leash.mac = "XX:XX:XX:XX:XX:XX"  # Phone MAC address
main.plugins.bt-leash.auto_reconnect = false
main.plugins.bt-leash.ui_enabled = true
```

### 🕒 Clock (`clock.py`)
**Description**: Adds a simple clock and calendar to the Pwnagotchi UI.
**Configuration**:
```toml
main.plugins.clock.enabled = true
main.plugins.clock.date_format = "%m/%d/%y"
```

### 👾 Discord (`discord.py`)
**Description**: Posts recent activity (handshakes, stats) to a Discord channel using webhooks. Requires the `discord.py` module installed via pip.
**Configuration**:
```toml
main.plugins.discord.enabled = true
main.plugins.discord.webhook_url = "YOUR_WEBHOOK_URL"
main.plugins.discord.username = "Pwnagotchi"
```

### 🌍 Fix Region (`fix_region.py`)
**Description**: Sets the wireless regulatory domain (region) to unlock channels 12 and 13 (useful outside the US).
**Configuration**:
```toml
main.plugins.fix_region.enabled = true
main.plugins.fix_region.region = "GB" # Change to your country code
```

### 🌡️ MemTemp (`memtemp.py`)
**Description**: Displays memory usage, CPU load, CPU temperature, and CPU frequency on the screen.
**Configuration**:
```toml
main.plugins.memtemp.enabled = true
main.plugins.memtemp.scale = "celsius" # or fahrenheit, kelvin
main.plugins.memtemp.orientation = "horizontal" # or vertical
```

### 🏠 OpwnHouse (`opwnhouse.py`)
**Description**: Displays nearby cracked networks and their passwords on the screen. Includes a rich Web UI tab with a "Radar" view, ASCII art scene, and tools to manage/export your cracked network list (potfile).
**Configuration**:
```toml
main.plugins.opwnhouse.enabled = true
main.plugins.opwnhouse.hunter_mode = true # Hot/Cold signal strength feedback
```

### 🔋 PiSugar 3 (`pisugar3.py`)
**Description**: Adds a battery percentage and voltage indicator for the PiSugar 3 UPS. Includes safe shutdown capability when battery is low.
**Configuration**:
```toml
main.plugins.pisugar3.enabled = true
main.plugins.pisugar3.shutdown = 5 # Shutdown when battery is at 5%
```

## Installation

1. Copy the desired `.py` files into your custom plugins directory (usually `/usr/local/share/pwnagotchi/custom-plugins/` or `/var/pwnagotchi/custom-plugins/`).
2. Edit your `/etc/pwnagotchi/config.toml` to enable and configure the plugins.
3. Restart pwnagotchi: `systemctl restart pwnagotchi`.
