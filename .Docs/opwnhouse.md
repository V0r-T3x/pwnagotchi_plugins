# OpwnHouse Plugin Summary

## Overview
**OpwnHouse** is a comprehensive Pwnagotchi plugin designed to visualize, manage, and utilize cracked Wi-Fi credentials. It serves as both a heads-up display for the Pwnagotchi screen—showing the credentials of the nearest cracked network—and a rich web-based management interface for the device's cracked network database.

## Key Features

### 1. On-Screen Display (UI)
The plugin renders information directly on the Pwnagotchi's e-ink or LCD screen.
*   **Proximity Display:** Shows the **ESSID** and **Password** of the nearest cracked access point based on signal strength (RSSI).
*   **Status Indicators:** Optionally displays a statistics counter (e.g., `3/150`), indicating that 3 cracked networks are currently nearby out of 150 total known cracked networks.
*   **Orientation Support:** Supports both `vertical` and `horizontal` text layouts to match the user's screen preference.
*   **Display Compatibility:** Includes built-in coordinate presets for popular displays (Waveshare V1/V2, Waveshare 1.44" LCD, Inky) and allows manual coordinate overrides for custom hardware.

### 2. Web Interface
The plugin injects a robust interface into the Pwnagotchi web UI (`/plugins/opwnhouse`), divided into three tabs:

#### A. Proximity Tab
*   **ASCII Scene:** Renders a dynamic, scrolling ASCII art landscape. "Houses" represent nearby networks; unlocked houses (🔓) are cracked networks, and locked houses (🔒) are uncracked. The position of the house corresponds to the signal strength.
*   **Live Table:** Lists currently detected access points with details: ESSID, BSSID, STAMAC, Password (if known), GPS coordinates, and RSSI.
*   **QR Codes:** Clicking on a cracked network row opens a modal with a Wi-Fi QR code, allowing for instant connection via a smartphone camera.

#### B. Cracked List Tab
*   **Database Management:** Displays a searchable, paginated table of all cracked networks stored on the device.
*   **Editing:** Users can manually edit network details (ESSID, BSSID, Password) or delete entries.
*   **GPS Enrichment:** Displays GPS coordinates for networks if corresponding `.gps.json` files are found.

#### C. Configuration Tab
*   **Settings Form:** Provides a GUI to modify plugin settings (positions, orientation, paths) without needing to SSH into the device to edit `config.toml`.
*   **Import/Export:** Tools to import external `.potfile` or `.cracked` files and export the consolidated database (`opwnhouse.potfile`).
*   **File Management:** Allows users to select and delete specific potfiles from the filesystem.

### 3. Backend Logic
*   **File Scanning:** Automatically scans configured directories (default `/root/handshakes` and optional custom directories) for `.potfile`, `.cracked`, and `.pcap` files.
*   **Data Consolidation:** Aggregates credentials into a master file (`opwnhouse.potfile`) and maintains a companion JSON file (`opwnhouse.json`) for metadata like GPS locations and notes.
*   **GPS Integration:** Correlates BSSIDs with Pwnagotchi's `.gps.json` files to enrich the database with location data.
*   **Interoperability:** Automatically generates `.pcap.cracked` marker files when a password is found, ensuring compatibility with other tools like `webgpsmap`.

### 4. Hunter Mode (Hot/Cold Game)
Turn your Pwnagotchi into a proximity tracker for cracked networks!
*   **Real-time Feedback:** Tracks RSSI trends to guide you toward the signal source.
    *   **HOTTER 🔥:** Signal improved by ≥ 4dB (you are getting closer).
    *   **COLDER 🥶:** Signal dropped by ≥ 4dB (you are moving away).
    *   **STEADY:** Signal is stable.
*   **Visuals:**
    *   **Device Screen:** Displays "HOT!" or "COLD!" indicators next to the network info.
    *   **Web UI:** The Proximity table includes a "Trend" column with colorful status indicators.

---

## User Configurations

The plugin can be configured via the Web UI or by adding the following keys to `/etc/pwnagotchi/config.toml`.

### Configuration Options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `main.plugins.opwnhouse.enabled` | Boolean | `false` | Enables or disables the plugin. |
| `main.plugins.opwnhouse.orientation` | String | `"vertical"` | Sets the text layout on the screen. <br>**Values:** `"vertical"`, `"horizontal"`. |
| `main.plugins.opwnhouse.display_stats` | Boolean | `false` | If `true`, displays the counter of nearby/total cracked networks (e.g., "3/50"). |
| `main.plugins.opwnhouse.hunter_mode` | Boolean | `false` | Enables "Hot/Cold" feedback for signal tracking. |
| `main.plugins.opwnhouse.position` | List/String | *Varies* | X, Y coordinates for the main text (ESSID/Password). <br>**Example:** `[0, 91]` or `"0, 91"`. |
| `main.plugins.opwnhouse.stats_position` | List/String | *Varies* | X, Y coordinates for the stats counter. <br>**Example:** `[0, 61]` or `"0, 61"`. |
| `main.plugins.opwnhouse.custom_dir` | String | `""` | Path to an additional directory to scan for handshake/potfiles. |
| `main.plugins.opwnhouse.save_path` | String | `/root/handshakes/opwnhouse.potfile` | Path where the consolidated potfile will be saved. |
| `main.plugins.opwnhouse.per_page` | Integer | `20` | Number of rows per page in the Web UI "Cracked List" table. |

### Display Compatibility & Defaults

The plugin attempts to auto-detect the display type defined in `config.toml` and applies the following default coordinates. These can be overridden using the `position` and `stats_position` options above to work with **any display**.

| Display Type | Default Main Position | Default Stats Position |
| :--- | :--- | :--- |
| **Waveshare V2** | `0, 95` | `0, 61` |
| **Waveshare V1** | `0, 95` | `0, 61` |
| **Waveshare 1.44" LCD** | `0, 92` | `0, 67` |
| **Inky** | `0, 83` | `0, 54` |
| **Default / Other** | `0, 91` | `0, 61` |
