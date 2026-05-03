# V0rT3x Pwnagotchi Plugin Suite

The V0rT3x Plugin Suite is a modular plugin ecosystem for Pwnagotchi and Kaligotchi-style builds. Each plugin is meant to remain useful on its own, but the suite is designed so the plugins become stronger when combined: UI layers, physical controls, telemetry, second-screen output, Bluetooth tethering, cracked-network memory, and command routing can all discover and drive each other through plugin hooks.

This project evolved from Fancygotchi-inspired ideas, but the big update splits those ideas into lighter, more focused, less invasive plugins. You can install one tool, a small field kit, or the whole mesh.

> **Experimental status:** this suite is still evolving. APIs, hooks, options, and plugin behavior may change in the near future, and not every plugin has been fully tested across mainstream Pwnagotchi forks yet. Enable only the plugins you need, back up your config, and expect some build-specific tuning.

## Suite Philosophy

- Standalone first: every plugin should still make sense by itself.
- Mesh-aware when combined: plugins expose hooks such as `on_pwnctl`, `on_menu`, `on_dashboard`, and V0rT3x action/context providers where the code implements them.
- Optional organs, not a monolith: choose the exact controls, screens, dashboards, and telemetry your build needs.
- Low invasiveness: prefer plugin hooks and local bridges over hard patches to the core stack.
- `pwnctl.py` is the action/control bridge for CLI, Web UI, GPIO, and plugin commands.
- `refacer.py` is the theme, render, asset, font, spatial widget, and display-control layer.
- `windows.py` is the second-screen, screen saver, terminal, and auxiliary-display host.
- `lightmenu.py` and `pwngpio.py` provide menu and physical control surfaces.
- `bt-leash.py` provides Bluetooth tethering and device management.
- `opwnhouse.py` keeps local cracked-network memory and proximity views.
- `dashboard.py` aggregates suite web overview cards from plugins that implement `on_dashboard`.

## Topology Overview

```text
Input / Control:
  pwngpio -> pwnctl -> plugin actions
  lightmenu -> pwnctl / webhooks
  future touch -> refacer bbox -> pwnctl

Visual / UI:
  refacer -> main UI/theme/editor
  windows -> second screen / aux / screensaver
  dashboard -> web overview

Telemetry / Memory:
  opwnhouse -> cracked network memory / proximity / hunter mode
  memtemp -> device health
  clock -> time/date

Connectivity:
  bt-leash -> Bluetooth tether / device manager
  discord -> external notifications
```

## Capability Matrix

| Plugin | Standalone role | Mesh role | Web UI | pwnctl | UI Widget | Aux / Dashboard |
| ------ | --------------- | --------- | ------ | ------ | --------- | --------------- |
| `bt-leash.py` | Bluetooth tether and device manager | Connectivity path for mobile builds | Yes: index, status, scan, pair, trust, untrust, connect, disconnect, unpair, gadget, config | Via webhook fallback | Yes | No |
| `clock.py` | Date/time display | Utility telemetry beside other widgets | No | No | Yes | No |
| `dashboard.py` | Custom Web UI dashboard page | Collects `on_dashboard` cards from loaded plugins | Yes: dashboard page | Via webhook fallback | No | Dashboard host |
| `discord.py` | Discord webhook notifier | Remote activity reporting when internet is available | No | No | No | No |
| `fix_region.py` | Wireless regulatory-domain helper | Enables region/channel fix for compatible builds | No | No | No | No |
| `lightmenu.py` | Lightweight on-device menu overlay | Menu actions, V0rT3x actions/contexts, dashboard card, pwnctl/webhook command dispatch | Yes: config and menu commands | Yes: `up`, `down`, `select`, `back`, `open`, `close`, `toggle` | Yes | Dashboard card |
| `memtemp.py` | Memory, CPU load, temperature, and frequency display | Health telemetry beside other UI layers | No | No | Yes | No |
| `opwnhouse.py` | Cracked-network memory and proximity display | Hunter/proximity memory layer for field builds | Yes: proximity, JSON, config, files, import/export/edit/delete | Via webhook fallback | Yes | No |
| `pwnctl.py` | UNIX socket and Web UI command bridge | Central action bus, input router, contexts, bindings, webhook fallback | Yes: status, actions, contexts, bindings, bind/unbind/reset/test | Core bridge | No | No |
| `pwngpio.py` | GPIO buttons and rotary encoder input | Sends normalized input events to `pwnctl`; legacy command fallback | No | Yes: `status`, `test <CONTROL> <GESTURE>` | No | No |
| `refacer.py` | Main UI render/theme manager | Theme, spatial widget model, menu entries, pwnctl display/theme actions | Yes: theme editor, preview, assets, fonts, CSS, config, debug routes | Yes: theme, rotation, stealth, display commands | Main UI interceptor | Menu entries |
| `windows.py` | Second-screen/display hijacker | Screen modes, screen savers, terminal mode, V0rT3x actions/contexts, aux plugin host | Yes: status, config, second-screen, mode/saver/aux controls | Yes: status, display, saver, aux, runtime-default commands | Display handoff | Aux host |

## Main Suite Plugins

### 🦷 BT Leash (`bt-leash.py`)

Bluetooth tethering and device management with DBus/BlueZ integration. It can scan devices, pair, trust, untrust, unpair, connect, disconnect, and set a tether MAC from the Web UI. The code implements auto-reconnect behavior with reconnect limits, a visible UI widget, and a `gadget` route that calls the generic BlueZ device connect path.

### 🕒 Clock (`clock.py`)

A small clock/calendar plugin for the Pwnagotchi UI. It adds a date/time widget and can adjust placement when `memtemp` is enabled.

### 🧭 Dashboard (`dashboard.py`)

A custom Web UI dashboard/index surface. It renders the current UI image and collects dashboard widgets from loaded plugins that implement `on_dashboard`, making it the suite's overview aggregator.

### 👾 Discord (`discord.py`)

Posts recent activity to Discord through a webhook when internet is available. It is useful for remote activity reporting after sessions with captured handshakes and requires the `discord.py` module.

### 🌍 Fix Region (`fix_region.py`)

A regulatory-domain helper that creates a small `iw reg set` service so channels 12 and 13 can be used where legal. Configure the region code for your country before enabling it.

### 🧩 LightMenu (`lightmenu.py`)

A lightweight menu overlay inspired by Fancygotchi/FancyMenu concepts. It provides dynamic plugin menus, custom menu editing in the Web UI, menu navigation via webhook commands, native `on_pwnctl` support, `on_dashboard`, and V0rT3x action/context hooks. It can be driven from Web UI, `pwnctl`, or GPIO events routed through `pwngpio`.

### 🌡️ MemTemp (`memtemp.py`)

Displays device health on the main UI: memory usage, CPU load, CPU temperature, and CPU frequency. The code supports horizontal or vertical orientation, configurable fields, position, line spacing, and temperature scale.

### 🏠 OpwnHouse (`opwnhouse.py`)

Tracks cracked networks and nearby APs, importing and exporting `.potfile` and `.cracked` data. Its Web UI includes list, proximity, landscape, radar, config, file-management, edit/delete, GPS refresh, and JSON views. Hunter mode, RSSI history/trend, and GPS enrichment are implemented in the code.

### 🧠 pwnctl (`pwnctl.py`)

The suite's local command bridge. It creates a UNIX socket at `/tmp/pwnctl.sock`, attempts to create a `/usr/local/bin/pwnctl` wrapper, exposes a Web UI for actions, contexts, bindings, and test input, and routes commands to plugins through native `on_pwnctl` handlers or a webhook fallback. It also discovers V0rT3x action/context providers through `on_v0rt3x_actions` and `on_v0rt3x_contexts`.

### 🎮 PwnGPIO (`pwngpio.py`)

GPIO and rotary encoder input provider for `pwnctl`. It sends normalized input events such as controls and gestures to the `pwnctl` socket, supports short/long button presses and encoder rotation, and falls back to legacy shell commands when no pwnctl action handles the event. It is adapted from RasTacsko's `gpiocontrol` concept and reworked for the newer V0rT3x/Pwnagotchi stack.

### 🎨 Refacer (`refacer.py`)

A Fancygotchi-inspired main-screen render and theme layer with full compatibility for Fancygotchi 2.0 themes, including the themes in [`V0r-T3x/Fancygotchi_themes/fancygotchi_2.0`](https://github.com/V0r-T3x/Fancygotchi_themes/tree/main/fancygotchi_2.0). It includes a theme manager/editor, live preview, asset manager, font handling, Font Awesome glyph browser, CSS editor, widget positioning/spatial model, boot animation controls, stealth mode, rotation, display sleep/control features, and pwnctl actions for themes, rotation, stealth, and display state.

### 🪟 Windows (`windows.py`)

Second-screen and alternate display manager. It can hijack or restore the Pwnagotchi display, run screen saver modes, host auxiliary plugins that implement `on_aux`, provide terminal mode, separate runtime state from defaults, and expose both Web UI and `pwnctl` controls for mode, saver, aux, and display switching.

## Example Build Profiles

### Minimal physical-control build

- `lightmenu.py`
- `pwnctl.py`
- `pwngpio.py`

### Visual/theme build

- `refacer.py`
- `dashboard.py`
- `memtemp.py`
- `clock.py`

### Second-screen telemetry build

- `windows.py`
- `refacer.py`

### Mobile cyberdeck build

- `bt-leash.py`
- `windows.py`
- `pwnctl.py`
- `dashboard.py`

### Hunter / cracked-network memory build

- `opwnhouse.py`
- `refacer.py`
- `lightmenu.py`
- `pwngpio.py`

## Installation

1. Copy the desired `.py` files to your custom plugins directory:

```bash
sudo cp *.py /usr/local/share/pwnagotchi/custom-plugins/
```

or:

```bash
sudo cp *.py /var/pwnagotchi/custom-plugins/
```

2. Enable only the plugins needed for your build in `/etc/pwnagotchi/config.toml`.

3. Restart Pwnagotchi:

```bash
sudo systemctl restart pwnagotchi
```

## Minimal Config Examples

Keep configs small at first. Add options only when you need that plugin's extra behavior.

```toml
main.plugins.bt-leash.enabled = true
main.plugins.bt-leash.mac = "XX:XX:XX:XX:XX:XX"
main.plugins.bt-leash.auto_reconnect = false
main.plugins.bt-leash.ui_enabled = true

main.plugins.clock.enabled = true
main.plugins.clock.date_format = "%m/%d/%y"

main.plugins.dashboard.enabled = true

main.plugins.discord.enabled = true
main.plugins.discord.webhook_url = "https://discord.com/api/webhooks/..."
main.plugins.discord.username = "Pwnagotchi"

main.plugins.fix_region.enabled = true
main.plugins.fix_region.region = "GB"

main.plugins.lightmenu.enabled = true
main.plugins.lightmenu.menu_timeout = 30
main.plugins.lightmenu.dashboard_enabled = true

main.plugins.memtemp.enabled = true
main.plugins.memtemp.scale = "celsius"
main.plugins.memtemp.orientation = "horizontal"

main.plugins.opwnhouse.enabled = true
main.plugins.opwnhouse.hunter_mode = true
main.plugins.opwnhouse.display_stats = false

main.plugins.pwnctl.enabled = true

main.plugins.pwngpio.enabled = true
main.plugins.pwngpio.hold_time = 1.0

main.plugins.refacer.enabled = true
main.plugins.refacer.theme = "Default"
main.plugins.refacer.fps = 30

main.plugins.windows.enabled = true
main.plugins.windows.default_mode = "screen_saver"
main.plugins.windows.default_screen_saver = "show_logo"
```

Example GPIO shape for `pwngpio.py`:

```toml
main.plugins.pwngpio.gpios."17".control = "BTN_A"
main.plugins.pwngpio.gpios."17".short_press = "pwnctl input BTN_A short gpio"
main.plugins.pwngpio.gpios."17".long_press = "pwnctl input BTN_A long gpio"

main.plugins.pwngpio.encoder.a = 22
main.plugins.pwngpio.encoder.b = 23
main.plugins.pwngpio.encoder.button = 24
```

## Compatibility Notes

- These plugins are designed for Pwnagotchi-compatible forks and Kaligotchi-style builds, but exact behavior depends on the fork's plugin manager, Web UI, and display stack.
- Web dashboards and control pages depend on Flask/Web UI availability.
- GPIO input requires hardware pins and `gpiozero`.
- Bluetooth features require BlueZ and DBus support.
- `discord.py` is required for Discord webhook posting.
- Refacer is fully compatible with Fancygotchi 2.0 themes, but those themes may require their local assets and fonts to be present on the device.
- Windows second-screen support depends on the target display hardware and driver support.
- Some plugins write system files or config through Pwnagotchi helpers; review options before enabling on a production field build.

## Additional / Legacy Plugins

### PiSugar 3 (`pisugar3.py`)

`pisugar3.py` is present in this repository, but it is not part of the main V0rT3x Plugin Suite topology. It adds a PiSugar 3 battery percentage/voltage UI indicator and can shut down when capacity reaches the configured threshold.

```toml
main.plugins.pisugar3.enabled = true
main.plugins.pisugar3.shutdown = 5
```
