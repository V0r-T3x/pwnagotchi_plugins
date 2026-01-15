import logging
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.web.server as web_server
import threading
import time
import gc
from flask import render_template_string, Flask

class DashBoard(plugins.Plugin):
    __author__ = 'V0rT3x'
    __version__ = '1.0.0'
    __description__ = 'Custom Dashboard Index page with Plugin Widgets'

    def __init__(self):
        self._agent = None
        self._original_index = None
        self._app = None

    def on_ready(self, agent):
        self._agent = agent

    def on_loaded(self):
        threading.Thread(target=self._patch_index, daemon=True).start()

    def _patch_index(self):
        logging.info("[DashBoard] Patching index content block...")
        
        app = None
        # Wait for web server to initialize
        for _ in range(60):
            for obj in gc.get_objects():
                if isinstance(obj, Flask):
                    app = obj
                    break
            if app:
                break
            time.sleep(1)
            
        if app:
            self._app = app
            if 'index' in app.view_functions:
                self._original_index = app.view_functions['index']

            # This replaces the original 'index' function
            def custom_index_handler():
                # We need to replicate the logic the original handler uses to get 'other_mode'
                current_mode = 'manual'
                if self._agent:
                    current_mode = self._agent.mode
                other_mode = 'AUTO' if current_mode == 'manual' else 'MANU'
                
                widgets = []
                for name, plugin in plugins.loaded.items():
                    if hasattr(plugin, 'on_dashboard'):
                        try:
                            content = plugin.on_dashboard()
                            if content:
                                widgets.append(content)
                        except Exception as e:
                            logging.error(f"[DashBoard] Widget error in {name}: {e}")

                # Your custom template string
                # Note: We still extend "base.html" so the menu/css stays intact
                return render_template_string("""
{% extends "base.html" %}
{% set active_page = "home" %}

{% block title %}
{{ title }} - Upgraded
{% endblock %}

{% block styles %}
{{ super() }}
<style>
    #ui {
        width: 100%;
    }
    .widget {
        margin: 10px 0;
        padding: 10px;
        border: 1px solid #ccc;
        border-radius: 5px;
    }
</style>
{% endblock %}

{% block script %}
window.onload = function() {
    var image = document.getElementById("ui");
    function updateImage() {
        image.src = image.src.split("?")[0] + "?" + new Date().getTime();
    }
    setInterval(updateImage, 1000);

}
{% endblock %}

{% block content %}
<div class="custom-container">
    <img class="ui-image pixelated" src="/ui" id="ui"/>

    <div data-role="navbar">
        <ul>
            <li>
                <form class="action" method="post" action="/shutdown" onsubmit="return confirm('Halt?');">
                    <input type="submit" class="button ui-btn ui-corner-all" value="Shutdown"/>
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                </form>
            </li>
            <li>
                <form class="action" method="post" action="/reboot" onsubmit="return confirm('Reboot?');">
                    <input type="submit" class="button ui-btn ui-corner-all" value="Reboot"/>
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                </form>
            </li>
            <li>
                <form class="action" method="post" action="/restart" onsubmit="return confirm('Restart in MANU mode?');">
                    <input type="submit" class="button ui-btn ui-corner-all" value="Restart MANU"/>
                    <input type="hidden" name="mode" value="MANU"/>
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                </form>
            </li>
            <li>
                <form class="action" method="post" action="/restart" onsubmit="return confirm('Restart in AUTO mode?');">
                    <input type="submit" class="button ui-btn ui-corner-all" value="Restart AUTO"/>
                    <input type="hidden" name="mode" value="AUTO"/>
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                </form>
            </li>
        </ul>
    </div>
    {% for widget in widgets %}
        <div class="widget">
            {{ widget|safe }}
        </div>
    {% endfor %}
</div>
{% endblock %}
                """, title="Pwnagotchi", other_mode=other_mode, widgets=widgets)

            # Hijack the route
            app.view_functions['index'] = custom_index_handler
        else:
            logging.error("[DashBoard] Could not find Flask app to patch.")

    def on_unload(self, ui):
        if self._app and self._original_index:
            logging.info("[DashBoard] Restoring original index handler...")
            self._app.view_functions['index'] = self._original_index