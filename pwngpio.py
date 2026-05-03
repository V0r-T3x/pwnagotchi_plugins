import logging
import socket
import subprocess
import time

from gpiozero import Button, RotaryEncoder
import pwnagotchi.plugins as plugins


SOCKET_PATH = "/tmp/pwnctl.sock"


class PwnGPIO(plugins.Plugin):
    __author__ = "RasTacsko, extended/reworked by V0rT3x"
    __version__ = "0.2.0"
    __license__ = "GPL3"
    __description__ = "V0rT3x GPIO/encoder input provider for pwnctl with legacy command fallback."

    def __init__(self):
        self.buttons = {}
        self.button_hold_times = {}
        self.encoder = None
        self.encoder_button = None
        self.encoder_button_pin = None
        self.previous_step = 0
        self.default_mapping = {}
        self.context_stack = []
        self.gpio_controls = {}
        self.encoder_config = {}
        self.hold_time = 1.0

    def runcommand(self, command):
        logging.info(f"[pwngpio] Running legacy command: {command}")
        process = subprocess.Popen(
            command,
            shell=True,
            stdin=None,
            stdout=open("/dev/null", "w"),
            stderr=None,
            executable="/bin/bash",
        )
        process.wait()

    def on_loaded(self):
        logging.info("[pwngpio] GPIO/encoder input provider loaded.")
        if "gpiocontrol" in plugins.loaded:
            logging.warning("[pwngpio] gpiocontrol is also loaded. Do not bind the same GPIO pins in both plugins.")

        try:
            self.hold_time = float(self.options.get("hold_time", 1.0))
        except Exception:
            self.hold_time = 1.0

        self.default_mapping = self.options.get("gpios", {})
        self._configure_buttons(self.options.get("gpios", {}))
        self._configure_encoder(self.options.get("encoder", {}))

    def _configure_buttons(self, gpios):
        default_controls = ["BTN_A", "BTN_B", "BTN_UP", "BTN_DOWN", "BTN_LEFT", "BTN_RIGHT"]
        configured_index = 0
        if not hasattr(gpios, "items"):
            return

        for gpio, actions in gpios.items():
            if gpio == "enabled":
                continue
            try:
                gpio_pin = int(gpio)
                actions = actions if hasattr(actions, "get") else {}
                control = actions.get("control")
                if not control:
                    control = default_controls[configured_index] if configured_index < len(default_controls) else f"GPIO_{gpio_pin}"
                configured_index += 1

                metadata = {
                    "control": self._normalize_control(control),
                    "short_press": actions.get("short_press"),
                    "long_press": actions.get("long_press"),
                }
                self.gpio_controls[gpio_pin] = metadata

                button = Button(gpio_pin, pull_up=True, bounce_time=0.05, hold_time=self.hold_time)
                button.when_pressed = lambda btn=button, g=gpio_pin: self.on_button_pressed(g)
                button.when_released = lambda btn=button, g=gpio_pin: self.on_button_released(g)
                self.buttons[gpio_pin] = button
                logging.info(
                    f"[pwngpio] Configured GPIO #{gpio_pin} as {metadata['control']} "
                    f"short={metadata['short_press']} long={metadata['long_press']}"
                )
            except (ValueError, TypeError) as e:
                logging.warning(f"[pwngpio] Skipping invalid GPIO key in config: {gpio} ({e})")

    def _configure_encoder(self, encoder_pins):
        if not hasattr(encoder_pins, "get"):
            return
        self.encoder_config = {
            "control_up": self._normalize_control(encoder_pins.get("control_up", "ENC_UP")),
            "control_down": self._normalize_control(encoder_pins.get("control_down", "ENC_DOWN")),
            "button_control": self._normalize_control(encoder_pins.get("button_control", "ENC_BTN")),
            "up_command": encoder_pins.get("up_command"),
            "down_command": encoder_pins.get("down_command"),
            "button_short_press": encoder_pins.get("button_short_press"),
            "button_long_press": encoder_pins.get("button_long_press"),
        }

        encoder_a = encoder_pins.get("a")
        encoder_b = encoder_pins.get("b")
        encoder_button_pin = encoder_pins.get("button")

        if encoder_a and encoder_b:
            self.encoder = RotaryEncoder(encoder_a, encoder_b, max_steps=1000, bounce_time=0.1, wrap=True)
            self.previous_step = self.encoder.steps
            self.encoder.when_rotated = self.on_encoder_rotated
            logging.info(f"[pwngpio] Encoder configured with pins A: {encoder_a}, B: {encoder_b}")

        if encoder_button_pin:
            self.encoder_button_pin = int(encoder_button_pin)
            self.encoder_button = Button(self.encoder_button_pin, pull_up=True, bounce_time=0.05, hold_time=self.hold_time)
            self.encoder_button.when_pressed = lambda: self.on_button_pressed(self.encoder_button_pin)
            self.encoder_button.when_released = lambda: self.on_encoder_button_released()
            logging.info(f"[pwngpio] Encoder button configured on GPIO {self.encoder_button_pin}.")

    def _normalize_control(self, control):
        return str(control or "").strip().upper().replace(" ", "_").replace("-", "_")

    def _legacy_mapping_for_gpio(self, gpio):
        current_map = self.get_current_mapping()
        gpio_key = str(gpio)
        if hasattr(current_map, "get"):
            mapping = current_map.get(gpio_key)
            if hasattr(mapping, "get"):
                return mapping
        return {}

    def emit_input_event(self, control, gesture, source="gpio", value=None, raw=None, fallback_command=None):
        control = self._normalize_control(control)
        gesture = str(gesture or "").strip().lower().replace(" ", "_").replace("-", "_")
        routed = False

        pwnctl = plugins.loaded.get("pwnctl")
        direct_available = pwnctl and (hasattr(pwnctl, "emit_input_event") or hasattr(pwnctl, "resolve_input_event"))
        if direct_available:
            try:
                handler = getattr(pwnctl, "emit_input_event", None) or getattr(pwnctl, "resolve_input_event")
                response = handler(control, gesture, source=source, value=value, raw=raw)
                logging.info(f"[pwngpio] pwnctl routed {control} {gesture}: {response}")
                return True
            except Exception as e:
                logging.warning(f"[pwngpio] Direct pwnctl routing failed for {control} {gesture}: {e}")

        if not direct_available:
            routed = self._emit_via_socket(control, gesture, source)
            if not routed:
                routed = self._emit_via_cli(control, gesture, source)

        if routed:
            return True

        if fallback_command:
            logging.warning(f"[pwngpio] Falling back to legacy command for {control} {gesture}.")
            self.runcommand(fallback_command)
            return "legacy"

        return False

    def _emit_via_socket(self, control, gesture, source):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.35)
                sock.connect(SOCKET_PATH)
                sock.sendall(f"input {control} {gesture} {source}".encode("utf-8"))
                response = sock.recv(2048).decode("utf-8", errors="replace")
                logging.info(f"[pwngpio] pwnctl socket routed {control} {gesture}: {response}")
                return True
        except Exception as e:
            logging.debug(f"[pwngpio] pwnctl socket routing unavailable: {e}")
            return False

    def _emit_via_cli(self, control, gesture, source):
        try:
            result = subprocess.run(
                ["pwnctl", "input", control, gesture, source],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=0.75,
                check=False,
            )
            if result.returncode == 0:
                output = result.stdout.decode("utf-8", errors="replace").strip()
                logging.info(f"[pwngpio] pwnctl CLI routed {control} {gesture}: {output}")
                return True
            logging.debug(f"[pwngpio] pwnctl CLI failed: {result.stderr.decode('utf-8', errors='replace')}")
        except Exception as e:
            logging.debug(f"[pwngpio] pwnctl CLI routing unavailable: {e}")
        return False

    def get_current_mapping(self):
        logging.debug("[pwngpio] legacy get_current_mapping compatibility shim used.")
        if self.context_stack:
            return self.context_stack[-1][1]
        return self.default_mapping

    def request_control(self, plugin_name, mapping):
        logging.warning(f"[pwngpio] legacy request_control from '{plugin_name}' is deprecated; use pwnctl bindings.")
        self.context_stack.append((plugin_name, mapping))

    def release_control(self, plugin_name):
        logging.warning(f"[pwngpio] legacy release_control from '{plugin_name}' is deprecated; use pwnctl bindings.")
        self.context_stack = [ctx for ctx in self.context_stack if ctx[0] != plugin_name]

    def on_button_pressed(self, gpio):
        self.button_hold_times[gpio] = time.time()
        logging.debug(f"[pwngpio] Button {gpio} pressed.")

    def on_button_released(self, gpio):
        started = self.button_hold_times.get(gpio, time.time())
        hold_time = time.time() - started
        metadata = self.gpio_controls.get(gpio, {"control": f"GPIO_{gpio}", "short_press": None, "long_press": None})
        legacy_override = self._legacy_mapping_for_gpio(gpio)
        short_command = legacy_override.get("short_press", metadata.get("short_press")) if hasattr(legacy_override, "get") else metadata.get("short_press")
        long_command = legacy_override.get("long_press", metadata.get("long_press")) if hasattr(legacy_override, "get") else metadata.get("long_press")
        gesture = "long" if hold_time >= self.hold_time else "short"
        fallback = long_command if gesture == "long" else short_command

        logging.info(f"[pwngpio] Button {gpio} ({metadata['control']}) released after {hold_time:.2f}s as {gesture}.")
        self.emit_input_event(
            metadata["control"],
            gesture,
            source="gpio",
            raw={"gpio": gpio, "hold_time": hold_time},
            fallback_command=fallback,
        )

    def on_encoder_rotated(self):
        if not self.encoder:
            return
        steps = self.encoder.steps
        if steps > self.previous_step:
            logging.info(f"[pwngpio] Encoder rotated up as {self.encoder_config.get('control_up')}.")
            self.emit_input_event(
                self.encoder_config.get("control_up", "ENC_UP"),
                "rotate",
                source="gpio",
                value=1,
                raw={"steps": steps, "previous_step": self.previous_step},
                fallback_command=self.encoder_config.get("up_command"),
            )
        elif steps < self.previous_step:
            logging.info(f"[pwngpio] Encoder rotated down as {self.encoder_config.get('control_down')}.")
            self.emit_input_event(
                self.encoder_config.get("control_down", "ENC_DOWN"),
                "rotate",
                source="gpio",
                value=-1,
                raw={"steps": steps, "previous_step": self.previous_step},
                fallback_command=self.encoder_config.get("down_command"),
            )
        self.previous_step = steps

    def on_encoder_button_released(self):
        if self.encoder_button_pin is None:
            return
        started = self.button_hold_times.get(self.encoder_button_pin, time.time())
        hold_time = time.time() - started
        gesture = "long" if hold_time >= self.hold_time else "short"
        fallback = self.encoder_config.get("button_long_press") if gesture == "long" else self.encoder_config.get("button_short_press")
        self.emit_input_event(
            self.encoder_config.get("button_control", "ENC_BTN"),
            gesture,
            source="gpio",
            raw={"gpio": self.encoder_button_pin, "hold_time": hold_time, "encoder_button": True},
            fallback_command=fallback,
        )

    def on_pwnctl(self, cmd):
        parts = str(cmd or "help").split()
        command = parts[0] if parts else "help"
        if command in ("help", "index"):
            return "pwngpio commands: status, test <CONTROL> <GESTURE>"
        if command == "status":
            return self._format_status()
        if command == "test":
            if len(parts) < 3:
                return "Usage: pwnctl pwngpio test <CONTROL> <GESTURE>"
            result = self.emit_input_event(parts[1], parts[2], source="pwngpio-test")
            return f"test {parts[1]} {parts[2]} -> {result}"
        return "pwngpio commands: status, test <CONTROL> <GESTURE>"

    def _format_status(self):
        lines = ["pwngpio status:"]
        if self.gpio_controls:
            for gpio in sorted(self.gpio_controls):
                meta = self.gpio_controls[gpio]
                lines.append(f"GPIO {gpio}: {meta.get('control')} short={meta.get('short_press')} long={meta.get('long_press')}")
        else:
            lines.append("No GPIO buttons configured.")

        if self.encoder:
            lines.append(
                "Encoder: "
                f"up={self.encoder_config.get('control_up')} down={self.encoder_config.get('control_down')} "
                f"steps={self.encoder.steps}"
            )
        else:
            lines.append("Encoder: not configured")

        if self.encoder_button:
            lines.append(f"Encoder button: GPIO {self.encoder_button_pin} control={self.encoder_config.get('button_control')}")
        return "\n".join(lines)

    def on_unload(self, ui):
        logging.info("[pwngpio] GPIO/encoder input provider unloaded.")
        for button in self.buttons.values():
            button.close()
        if self.encoder:
            self.encoder.close()
        if self.encoder_button:
            self.encoder_button.close()
