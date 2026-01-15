import logging
import os
import json
import time
import pwnagotchi
import pwnagotchi.plugins as plugins
from pwnagotchi.plugins import toggle_plugin
import pwnagotchi.ui.faces as faces
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue, Text, Rect, FilledRect
from pwnagotchi.ui.view import BLACK
from pwnagotchi.ui.view import WHITE
from pwnagotchi.ui import view
from flask import abort, jsonify, make_response, request, render_template_string, redirect
from pwnagotchi.utils import save_config

TEMPLATE = """
{% extends "base.html" %}
{% set active_page = "plugins" %}
{% block title %}
    LightMenu Configuration
{% endblock %}
{% block content %}
    <h2>LightMenu Configuration</h2>
    {% if success %}
    <div class="ui-body ui-body-a ui-corner-all" style="background-color: #90ee90; color: black; padding: 10px; margin-bottom: 10px;">
        Configuration saved!
    </div>
    {% endif %}
    <form method="POST" action="/plugins/lightmenu/config">
        <div class="ui-field-contain">
            <label for="dashboard_enabled">Enable Dashboard Widget:</label>
            <select name="dashboard_enabled" id="dashboard_enabled" data-role="flipswitch">
                <option value="false" {% if not options.dashboard_enabled %}selected{% endif %}>Off</option>
                <option value="true" {% if options.dashboard_enabled %}selected{% endif %}>On</option>
            </select>
        </div>
        <div class="ui-field-contain">
            <label for="reset_on_close">Reset Menu on Close:</label>
            <select name="reset_on_close" id="reset_on_close" data-role="flipswitch">
                <option value="false" {% if not options.reset_on_close %}selected{% endif %}>Off</option>
                <option value="true" {% if options.reset_on_close %}selected{% endif %}>On</option>
            </select>
        </div>
        <div class="ui-field-contain">
            <label for="menu_timeout">Menu Timeout (seconds, 0 to disable):</label>
            <input type="number" name="menu_timeout" id="menu_timeout" value="{{ options.menu_timeout }}" />
        </div>
        <input type="submit" value="Save" data-role="button" data-inline="true" data-theme="b" />
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
    </form>

    <hr>
    <h3>Custom Menus</h3>
    {% for menu_name, items in custom_menus.items() %}
    <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; border-radius: 5px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h4 style="margin: 0;">{{ menu_name }}</h4>
            <form method="POST" action="/plugins/lightmenu/delete_menu" onsubmit="return confirm('Delete menu {{ menu_name }}?');" style="margin:0;">
                <input type="hidden" name="menu_name" value="{{ menu_name }}">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <input type="submit" value="Delete" data-role="button" data-inline="true" data-mini="true" data-icon="delete">
            </form>
        </div>
        
        <ul data-role="listview" data-inset="true" data-mini="true">
            {% for item in items %}
            <li>
                <div class="ui-grid-a">
                    <div class="ui-block-a" style="width: 85%;">
                        <form method="POST" action="/plugins/lightmenu/edit_item" style="margin:0;">
                            <input type="hidden" name="menu_name" value="{{ menu_name }}">
                            <input type="hidden" name="item_index" value="{{ loop.index0 }}">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                            <div class="ui-grid-b">
                                <div class="ui-block-a" style="width: 40%; padding-right: 5px;">
                                    <input type="text" name="label" value="{{ item.label }}" placeholder="Label" data-mini="true">
                                </div>
                                <div class="ui-block-b" style="width: 45%; padding-right: 5px;">
                                    <input type="text" name="command" value="{{ item.command }}" placeholder="Command" data-mini="true">
                                </div>
                                <div class="ui-block-c" style="width: 15%;">
                                    <button type="submit" data-role="button" data-inline="true" data-mini="true" data-icon="check" data-iconpos="notext">Save</button>
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="ui-block-b" style="width: 15%; text-align: right;">
                        <form method="POST" action="/plugins/lightmenu/delete_item" style="margin:0;">
                            <input type="hidden" name="menu_name" value="{{ menu_name }}">
                            <input type="hidden" name="item_index" value="{{ loop.index0 }}">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                            <input type="submit" value="X" data-role="button" data-inline="true" data-mini="true" data-icon="delete" data-iconpos="notext">
                        </form>
                    </div>
                </div>
            </li>
            {% endfor %}
        </ul>

        <form method="POST" action="/plugins/lightmenu/add_item">
            <input type="hidden" name="menu_name" value="{{ menu_name }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
            <div class="ui-grid-a">
                <div class="ui-block-a"><input type="text" name="label" placeholder="Label" required></div>
                <div class="ui-block-b"><input type="text" name="command" placeholder="Command" required></div>
            </div>
            <input type="submit" value="Add Item" data-role="button" data-mini="true" data-icon="plus">
        </form>
    </div>
    {% endfor %}

    <div style="border: 1px solid #ccc; padding: 10px; margin-top: 20px; border-radius: 5px;">
        <h4>Create New Menu</h4>
        <form method="POST" action="/plugins/lightmenu/add_menu">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
            <input type="text" name="menu_name" placeholder="Menu Name" required>
            <input type="submit" value="Create Menu" data-role="button" data-icon="plus">
        </form>
    </div>
{% endblock %}
"""

class LightMenu(plugins.Plugin):
    __author__ = 'V0rT3x'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A light version of the fancymenu from Fancygotchi, accessible via webhooks for pwnctl integration.'

    def __init__(self):
        self.current_menu = 'Main menu'
        self.menu_stack = []
        self.current_index = 0
        self.menu_visible = False
        self.ui = None
        self.label_count = 0
        self.menu_item_offset = 0
        self.redraw_menu = False
        self.move_cursor = False
        self.update_labels = False
        self.add_elements = False
        self.remove_elements = False
        self.show_up_arrow = False
        self.show_down_arrow = False
        self.up_arrow_visible = False
        self.down_arrow_visible = False
        self.last_activity_time = 0
        
        # Layout variables
        self.menu_positions = []
        self.pos_up = (0, 0)
        self.pos_down = (0, 0)
        self.pos_cursor = (0, 0)
        self.cursor_x = 0
        self.menu_area = (0, 0, 0, 0) # x, y, w, h

        # Define menus similar to Fancygotchi, but light
        self.menus = {
            'Main menu': [
                ("Plugins", {"action": "submenu", "name": "Plugins"}),
                ("System", {"action": "submenu", "name": "System"}),
            ],
            'System': [
                ("Restart Auto", {"action": "restart", "mode": "AUTO"}),
                ("Restart Manu", {"action": "restart", "mode": "MANU"}),
                ("Reboot Auto", {"action": "reboot", "mode": "AUTO"}),
                ("Reboot Manu", {"action": "reboot", "mode": "MANU"}),
                ("Shutdown", {"action": "shutdown"}),
            ],
            'Plugins': [],
            # Add more menus as needed, e.g., 'Second screen', 'Plugins toggle' (dynamic)
        }

    def on_loaded(self):
        logging.info("[lightmenu] Plugin loaded.")
        if 'dashboard_enabled' not in self.options:
            self.options['dashboard_enabled'] = True
        if 'reset_on_close' not in self.options:
            self.options['reset_on_close'] = True
        if 'menu_timeout' not in self.options:
            self.options['menu_timeout'] = 30
        
        # Ensure custom_menus is a JSON string to prevent TOML/Box serialization issues
        if 'custom_menus' not in self.options:
            self.options['custom_menus'] = "{}"
        elif not isinstance(self.options['custom_menus'], str):
            try:
                self.options['custom_menus'] = json.dumps(self.options['custom_menus'])
            except Exception:
                self.options['custom_menus'] = "{}"

        self.build_menus()

    def build_menus(self):
        self.menus = {
            'Main menu': [
                ("Plugins", {"action": "submenu", "name": "Plugins"}),
                ("System", {"action": "submenu", "name": "System"}),
            ],
            'System': [
                ("Restart Auto", {"action": "restart", "mode": "AUTO"}),
                ("Restart Manu", {"action": "restart", "mode": "MANU"}),
                ("Reboot Auto", {"action": "reboot", "mode": "AUTO"}),
                ("Reboot Manu", {"action": "reboot", "mode": "MANU"}),
                ("Shutdown", {"action": "shutdown"}),
            ],
            'Plugins': [],
        }
        self.populate_plugins_menu()
        self.populate_custom_menus()
        self.populate_on_menu()

    def populate_custom_menus(self):
        custom_menus = self.get_custom_menus()
        for menu_name, items in custom_menus.items():
            # Add to Main menu
            self.menus['Main menu'].append((menu_name, {"action": "submenu", "name": menu_name}))
            
            # Create menu items
            menu_items = []
            for item in items:
                menu_items.append((item['label'], {"action": "command", "cmd": item['command']}))
            self.menus[menu_name] = menu_items

    def populate_plugins_menu(self):
        plugin_names = list(pwnagotchi.config['main']['plugins'].keys())
        for p in pwnagotchi.plugins.loaded:
            if p not in plugin_names:
                plugin_names.append(p)
        
        sorted_plugins = sorted(plugin_names)
        plugins_menu = []
        plugins_menu.append(("Refresh list", {"action": "refresh_plugins"}))
        
        for plugin in sorted_plugins:
            if plugin == 'lightmenu': continue
            
            plugins_menu.append((plugin, {"action": "submenu", "name": f"Plugin: {plugin}"}))
            
            self.menus[f"Plugin: {plugin}"] = [
                ("Enable", {"action": "plugin", "name": plugin, "enable": True}),
                ("Disable", {"action": "plugin", "name": plugin, "enable": False})
            ]
            
        self.menus['Plugins'] = plugins_menu

    def populate_on_menu(self):
        for name, plugin in plugins.loaded.items():
            if hasattr(plugin, 'on_menu'):
                try:
                    menus = plugin.on_menu()
                    if isinstance(menus, dict):
                        for menu_name, items in menus.items():
                            if menu_name not in self.menus:
                                self.menus['Main menu'].append((menu_name, {"action": "submenu", "name": menu_name}))
                                self.menus[menu_name] = items
                except Exception as e:
                    logging.error(f"[lightmenu] Error in on_menu for {name}: {e}")

    def on_ui_setup(self, ui):
        self.ui = ui
        self._res = [ui._width, ui._height]
        width = self._res[0]
        height = self._res[1]
        
        # Adaptive layout configuration
        if width < 200: # Small screen (e.g. 128x64)
            menu_x = 0
            menu_y = 10
            menu_w = width
            menu_h = height - 10
        else: # Larger screen (e.g. 250x122)
            menu_x = int(width * 0.46)
            menu_y = int(height * 0.13)
            menu_w = width - menu_x - 1
            menu_h = height - menu_y - 1
            
        self.menu_area = (menu_x, menu_y, menu_w, menu_h)
        self.line_height = 12 
        
        available_h = menu_h - 8
        self.label_count = int(available_h / self.line_height)
        if self.label_count < 1: self.label_count = 1
        
        self.menu_positions = []
        start_y = menu_y + 4
        for i in range(self.label_count):
            self.menu_positions.append((menu_x + 10, start_y + (i * self.line_height)))
            
        self.pos_up = (menu_x + menu_w - 12, menu_y + 2)
        self.pos_down = (menu_x + menu_w - 12, menu_y + menu_h - 12)
        self.cursor_x = menu_x + 2
        self.pos_cursor = (self.cursor_x, start_y)

    def on_ui_update(self, ui):
        if self.menu_visible:
            try:
                timeout = int(self.options.get('menu_timeout', 30))
            except (ValueError, TypeError):
                timeout = 30

            if timeout > 0 and time.time() - self.last_activity_time > timeout:
                self.close_menu()
                return

            if self.update_labels:
                self.update_labels = False
                menu_items = self.get_current_menu_items()
                offset = self.menu_item_offset
                
                for i in range(self.label_count):
                    key = f'menuitem{i}'
                    if offset + i < len(menu_items):
                        ui.set(key, menu_items[offset + i])
                    else:
                        ui.set(key, ' ')

            if self.move_cursor:
                self.move_cursor = False
                index = self.current_index - self.menu_item_offset
                if 0 <= index < self.label_count:
                    target_y = self.menu_positions[index][1]
                    self.pos_cursor = (self.cursor_x, target_y)
                    try:
                        ui.remove_element('menucursor')
                    except Exception:
                        pass
                    ui.add_element('menucursor', Text(color=BLACK, value='>', position=self.pos_cursor, font=fonts.Medium))

            # Handle arrows
            if self.show_up_arrow and not self.up_arrow_visible:
                self.up_arrow_visible = True
                ui.add_element('menuup', Text(color=BLACK, value='^', position=self.pos_up, font=fonts.Medium))
            elif not self.show_up_arrow and self.up_arrow_visible:
                self.up_arrow_visible = False
                try:
                    ui.remove_element('menuup')
                except Exception:
                    pass

            if self.show_down_arrow and not self.down_arrow_visible:
                self.down_arrow_visible = True
                ui.add_element('menudown', Text(color=BLACK, value='v', position=self.pos_down, font=fonts.Medium))
            elif not self.show_down_arrow and self.down_arrow_visible:
                self.down_arrow_visible = False
                try:
                    ui.remove_element('menudown')
                except Exception:
                    pass

    def on_dashboard(self):
        if not self.options.get('dashboard_enabled', True):
            return ""
        return """
        <div style="text-align: center;">
            <h3>LightMenu</h3>
            <div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 5px;">
                <button class="ui-btn ui-btn-inline ui-corner-all" onclick="fetch('/plugins/lightmenu/up')">Up</button>
                <button class="ui-btn ui-btn-inline ui-corner-all" onclick="fetch('/plugins/lightmenu/down')">Down</button>
                <button class="ui-btn ui-btn-inline ui-corner-all" onclick="fetch('/plugins/lightmenu/select')">Select</button>
                <button class="ui-btn ui-btn-inline ui-corner-all" onclick="fetch('/plugins/lightmenu/back')">Back</button>
                <button class="ui-btn ui-btn-inline ui-corner-all" onclick="fetch('/plugins/lightmenu/toggle')">Toggle</button>
            </div>
        </div>
        """

    def on_pwnctl(self, cmd):
        if cmd == 'help' or cmd == 'index':
            return "LightMenu commands: up, down, select, back, open, close, toggle"
        return self.on_webhook(cmd, None)

    def get_custom_menus(self):
        try:
            if isinstance(self.options['custom_menus'], str):
                return json.loads(self.options['custom_menus'])
            return self.options['custom_menus']
        except Exception:
            return {}

    def save_custom_menus(self, menus):
        # Save as JSON string to avoid Box/TOML corruption
        json_str = json.dumps(menus)
        self.options['custom_menus'] = json_str
        
        config = pwnagotchi.config
        if 'lightmenu' not in config['main']['plugins']:
            config['main']['plugins']['lightmenu'] = {}
        
        config['main']['plugins']['lightmenu']['custom_menus'] = json_str
        save_config(config, '/etc/pwnagotchi/config.toml')

    def on_webhook(self, path, request):
        if request:
            if request.method == "GET" and (path == "/" or not path):
                return render_template_string(TEMPLATE, options=self.options, custom_menus=self.get_custom_menus())
            if request.method == "POST" and path == "config":
                self.options['dashboard_enabled'] = request.form.get('dashboard_enabled') == 'true'
                self.options['reset_on_close'] = request.form.get('reset_on_close') == 'true'
                try:
                    self.options['menu_timeout'] = int(request.form.get('menu_timeout'))
                except (ValueError, TypeError):
                    self.options['menu_timeout'] = 30
                
                config = pwnagotchi.config
                if 'lightmenu' not in config['main']['plugins']:
                    config['main']['plugins']['lightmenu'] = {}
                config['main']['plugins']['lightmenu']['dashboard_enabled'] = self.options['dashboard_enabled']
                config['main']['plugins']['lightmenu']['reset_on_close'] = self.options['reset_on_close']
                config['main']['plugins']['lightmenu']['menu_timeout'] = self.options['menu_timeout']
                save_config(config, '/etc/pwnagotchi/config.toml')
                
                return render_template_string(TEMPLATE, options=self.options, custom_menus=self.get_custom_menus(), success=True)
            
            if request.method == "POST":
                if path == "add_menu":
                    menu_name = request.form.get('menu_name')
                    if menu_name:
                        custom_menus = self.get_custom_menus()
                        if menu_name not in custom_menus:
                            custom_menus[menu_name] = []
                            self.save_custom_menus(custom_menus)
                            self.build_menus()
                    return redirect('/plugins/lightmenu')

                elif path == "delete_menu":
                    menu_name = request.form.get('menu_name')
                    custom_menus = self.get_custom_menus()
                    if menu_name in custom_menus:
                        del custom_menus[menu_name]
                        self.save_custom_menus(custom_menus)
                        self.build_menus()
                    return redirect('/plugins/lightmenu')

                elif path == "add_item":
                    menu_name = request.form.get('menu_name')
                    label = request.form.get('label')
                    command = request.form.get('command')
                    if menu_name and label and command:
                        custom_menus = self.get_custom_menus()
                        if menu_name in custom_menus:
                            custom_menus[menu_name].append({'label': label, 'command': command})
                            self.save_custom_menus(custom_menus)
                            self.build_menus()
                    return redirect('/plugins/lightmenu')

                elif path == "edit_item":
                    menu_name = request.form.get('menu_name')
                    try:
                        item_index = int(request.form.get('item_index'))
                        label = request.form.get('label')
                        command = request.form.get('command')
                        custom_menus = self.get_custom_menus()
                        if menu_name in custom_menus:
                            if 0 <= item_index < len(custom_menus[menu_name]):
                                if label and command:
                                    custom_menus[menu_name][item_index] = {'label': label, 'command': command}
                                    self.save_custom_menus(custom_menus)
                                    self.build_menus()
                    except (ValueError, TypeError):
                        pass
                    return redirect('/plugins/lightmenu')

                elif path == "delete_item":
                    menu_name = request.form.get('menu_name')
                    try:
                        item_index = int(request.form.get('item_index'))
                        custom_menus = self.get_custom_menus()
                        if menu_name in custom_menus:
                            if 0 <= item_index < len(custom_menus[menu_name]):
                                custom_menus[menu_name].pop(item_index)
                                self.save_custom_menus(custom_menus)
                                self.build_menus()
                    except (ValueError, TypeError):
                        pass
                    return redirect('/plugins/lightmenu')

        if not self.ui:
            return "UI not ready"

        path = path.lower()
        self.last_activity_time = time.time()
        if path == 'up':
            self.navigate('up')
        elif path == 'down':
            self.navigate('down')
        elif path == 'select':
            self.select()
        elif path == 'back':
            self.back()
        elif path == 'open':
            self.open_menu()
        elif path == 'close':
            self.close_menu()
        elif path == 'toggle':
            if self.menu_visible:
                self.close_menu()
            else:
                self.open_menu()
        else:
            return "Invalid command"

        self.update_ui()
        return "OK"

    def _get_current_menu_full_list(self):
        items = self.menus.get(self.current_menu, [])
        if self.current_menu != 'Main menu':
            return [("Back", {"action": "back"}), ("Home", {"action": "home"})] + items
        return items

    def get_current_menu_items(self):
        return [item[0] for item in self._get_current_menu_full_list()]

    def get_current_menu_length(self):
        return len(self._get_current_menu_full_list())

    def navigate(self, direction):
        menu_length = self.get_current_menu_length()
        if menu_length == 0:
            return

        if not self.menu_visible:
            self.open_menu()

        delta = -1 if direction == 'up' else 1
        self.current_index = (self.current_index + delta) % menu_length

        # Handle pagination
        if self.current_index < self.menu_item_offset:
            self.menu_item_offset = max(0, self.menu_item_offset - self.label_count)
            self.update_labels = True
        elif self.current_index >= self.menu_item_offset + self.label_count:
            self.menu_item_offset += self.label_count
            self.update_labels = True

        self.move_cursor = True

        # Update arrows
        self.show_up_arrow = self.menu_item_offset > 0
        self.show_down_arrow = self.menu_item_offset + self.label_count < menu_length

    def select(self):
        if not self.menu_visible:
            return

        menu_items = self._get_current_menu_full_list()
        selected = menu_items[self.current_index]
        action = selected[1]

        if action['action'] == 'submenu':
            self.menu_stack.append(self.current_menu)
            self.current_menu = action['name']
            self.current_index = 0
            self.menu_item_offset = 0
            self.update_labels = True
            self.move_cursor = True
            return
        elif action['action'] == 'back':
            self.back()
            return
        elif action['action'] == 'home':
            self.menu_stack = []
            self.current_menu = 'Main menu'
            self.current_index = 0
            self.menu_item_offset = 0
            self.update_labels = True
            self.move_cursor = True
            return
        elif action['action'] == 'plugin':
            try:
                toggle_plugin(action['name'], action['enable'])
                logging.info(f"[lightmenu] Toggled plugin {action['name']} to {action['enable']}")
            except Exception as e:
                logging.error(f"[lightmenu] Error toggling plugin: {e}")
            self.close_menu()
            return
        elif action['action'] == 'refresh_plugins':
            self.populate_plugins_menu()
            self.current_menu = 'Plugins'
            self.current_index = 0
            self.menu_item_offset = 0
            self.update_labels = True
            self.move_cursor = True
            return
        elif action['action'] == 'pwnctl':
            plugin_name = action.get('plugin')
            cmd = action.get('cmd')
            if plugin_name in plugins.loaded:
                target = plugins.loaded[plugin_name]
                if hasattr(target, 'on_pwnctl'):
                    target.on_pwnctl(cmd)
                elif hasattr(target, 'on_webhook'):
                    class MockRequest:
                        method = "GET"
                    target.on_webhook(cmd, MockRequest())
            self.close_menu()
            return
        elif action['action'] == 'restart':
            pwnagotchi.restart(action['mode'])
        elif action['action'] == 'reboot':
            pwnagotchi.reboot(action['mode'])
        elif action['action'] == 'shutdown':
            pwnagotchi.shutdown()
        elif action['action'] == 'command':
            logging.info(f"[lightmenu] Executing command: {action['cmd']}")
            os.system(action['cmd'])
        self.close_menu()  # Close after action

    def back(self):
        if self.menu_stack:
            self.current_menu = self.menu_stack.pop()
            self.current_index = 0
            self.menu_item_offset = 0
            self.update_labels = True
            self.move_cursor = True
        elif self.current_menu != 'Main menu':
            self.current_menu = 'Main menu'
            self.current_index = 0
            self.menu_item_offset = 0
            self.update_labels = True
            self.move_cursor = True
        else:
            self.close_menu()

    def open_menu(self):
        if not self.menu_visible:
            self.menu_visible = True
            self.last_activity_time = time.time()
            self.add_elements = True
            self.update_labels = True
            self.move_cursor = True
            
            x, y, w, h = self.menu_area
            view.ROOT.add_element('menubg', FilledRect((x, y, x + w, y + h), WHITE))
            view.ROOT.add_element('menuborder', Rect((x, y, x + w, y + h), BLACK))
            
            for i in range(self.label_count):
                key = f'menuitem{i}'
                pos = self.menu_positions[i]
                view.ROOT.add_element(key, LabeledValue(color=BLACK, label='', value=' ', position=pos, label_font=fonts.Medium, text_font=fonts.Medium))

    def close_menu(self):
        if self.menu_visible:
            self.menu_visible = False
            self.remove_elements = True
            if self.options.get('reset_on_close', True):
                self.current_menu = 'Main menu'
                self.current_index = 0
                self.menu_item_offset = 0

            try:
                view.ROOT.remove_element('menubg')
                view.ROOT.remove_element('menuborder')
                for i in range(self.label_count):
                    view.ROOT.remove_element(f'menuitem{i}')
                view.ROOT.remove_element('menucursor')
                if self.up_arrow_visible:
                    view.ROOT.remove_element('menuup')
                if self.down_arrow_visible:
                    view.ROOT.remove_element('menudown')
            except Exception:
                pass

    def update_ui(self):
        if self.add_elements:
            self.add_elements = False
            self.open_menu()  # Already handled in open_menu
        if self.remove_elements:
            self.remove_elements = False
            self.close_menu()

    def on_unload(self, ui):
        self.close_menu()
        logging.info("[lightmenu] Plugin unloaded.")