import logging
from gpiozero import Button, RotaryEncoder, Device
from gpiozero.pins.pigpio import PiGPIOFactory
import subprocess
import time
import pwnagotchi.plugins as plugins

class GPIOControl(plugins.Plugin):
    __author__ = 'https://github.com/RasTacsko, modified by V0rT3x'
    __version__ = '0.1.20'
    __license__ = 'GPL3'
    __description__ = 'GPIO Button and Rotary Encoder support plugin with press, hold, and rotate logic.'

    def __init__(self):
        self.buttons = {}
        self.button_hold_times = {}  # Track button press times
        self.encoder = None
        self.encoder_button = None
        self.previous_step = 0
        self.default_mapping = {}
        self.context_stack = []

    def runcommand(self, command):
        logging.info(f"Running command: {command}")
        process = subprocess.Popen(command, shell=True, stdin=None, stdout=open("/dev/null", "w"), stderr=None,
                                   executable="/bin/bash")
        process.wait()

    def on_loaded(self):
        logging.info("GPIO Control loaded with context support.")
        self.default_mapping = self.options.get('gpios', {})

        # Initialize GPIO buttons
        gpios = self.options.get('gpios', {})
        if isinstance(gpios, dict):
            for gpio, actions in gpios.items():
                if gpio == 'enabled':
                    continue
                try:
                    gpio_pin = int(gpio)
                    button = Button(gpio_pin, pull_up=True, bounce_time=0.05, hold_time=1.0)
                    short_press_command = actions.get('short_press')
                    long_press_command = actions.get('long_press')
                    
                    button.when_pressed = lambda btn=button, g=gpio_pin: self.on_button_pressed(g)
                    button.when_released = lambda btn=button, g=gpio_pin, sp=short_press_command, lp=long_press_command: \
                        self.on_button_released(g, sp, lp)
                    
                    self.buttons[gpio_pin] = button
                    logging.info(f"Configured GPIO #{gpio_pin} for short press: {short_press_command} and long press: {long_press_command}")
                except (ValueError, TypeError):
                    logging.warning(f"Skipping invalid GPIO key in config: {gpio}")
                    continue

        # Initialize Encoder and encoder button
        encoder_pins = self.options.get('encoder', {})
        encoder_a = encoder_pins.get('a')
        encoder_b = encoder_pins.get('b')
        encoder_button_pin = encoder_pins.get('button')
        encoder_up_command = encoder_pins.get('up_command')
        encoder_down_command = encoder_pins.get('down_command')

        if encoder_a and encoder_b:
            self.encoder = RotaryEncoder(encoder_a, encoder_b, max_steps=1000, bounce_time=0.1, wrap=True)
            self.encoder.when_rotated = lambda: self.on_encoder_rotated(encoder_up_command, encoder_down_command)
            logging.info(f"Encoder configured with pins A: {encoder_a}, B: {encoder_b}")
        if encoder_button_pin:
            self.encoder_button = Button(encoder_button_pin, pull_up=True, bounce_time=0.05, hold_time=1.0)
            self.encoder_button.when_pressed = lambda: self.on_button_pressed(encoder_button_pin)
            self.encoder_button.when_released = lambda: self.on_button_released(encoder_button_pin, encoder_pins.get('button_short_press'), encoder_pins.get('button_long_press'))
            logging.info(f"Encoder button configured on GPIO {encoder_button_pin}.")

    def get_current_mapping(self):
        """Returns the mapping from the top of the stack, or default if empty."""
        if self.context_stack:
            return self.context_stack[-1][1]
        return self.default_mapping

    def request_control(self, plugin_name, mapping):
        """Allows a plugin to push its own mapping onto the stack."""
        logging.info(f"[gpiocontrol] Plugin '{plugin_name}' is taking control.")
        self.context_stack.append((plugin_name, mapping))

    def release_control(self, plugin_name):
        """Allows a plugin to remove itself from the stack, returning control to previous."""
        self.context_stack = [ctx for ctx in self.context_stack if ctx[0] != plugin_name]
        logging.info(f"[gpiocontrol] Plugin '{plugin_name}' released control.")

    def on_button_pressed(self, gpio):
        """Record the time the button was pressed."""
        self.button_hold_times[gpio] = time.time()
        logging.debug(f"Button {gpio} pressed.")

    def on_button_released(self, gpio, short_press_command, long_press_command):
        """Handle button release and determine if it's a short or long press."""
        hold_time = time.time() - self.button_hold_times[gpio]
        logging.info(f"Button {gpio} released after {hold_time:.2f} seconds.")
        
        current_map = self.get_current_mapping()
        gpio_key = str(gpio)
        
        cmd_short = short_press_command
        cmd_long = long_press_command
        
        if gpio_key in current_map:
             cmd_short = current_map[gpio_key].get('short_press', short_press_command)
             cmd_long = current_map[gpio_key].get('long_press', long_press_command)

        if hold_time >= 1.0:
            logging.info(f"Long press detected on GPIO {gpio}. Running command: {cmd_long}")
            if cmd_long:
                self.runcommand(cmd_long)
        else:
            logging.info(f"Short press detected on GPIO {gpio}. Running command: {cmd_short}")
            if cmd_short:
                self.runcommand(cmd_short)

    def on_encoder_rotated(self, up_command, down_command):
        """Handle encoder rotation."""
        steps = self.encoder.steps
        if steps > self.previous_step:
            logging.info(f"Encoder rotated up. Running command: {up_command}")
            if up_command:
                self.runcommand(up_command)
        elif steps < self.previous_step:
            logging.info(f"Encoder rotated down. Running command: {down_command}")
            if down_command:
                self.runcommand(down_command)
        self.previous_step = steps

    def on_unload(self, ui):
        logging.info("GPIO Button and Encoder control plugin unloaded.")
        # Clean up GPIO resources
        for button in self.buttons.values():
            button.close()
        if self.encoder:
            self.encoder.close()
        if self.encoder_button:
            self.encoder_button.close()