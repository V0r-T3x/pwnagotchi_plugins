import gc
import logging
import re
import threading
import time

import pwnagotchi
import pwnagotchi.plugins as plugins
from flask import Flask, render_template_string
from jinja2 import ChoiceLoader, DictLoader


class DashBoard(plugins.Plugin):
    __author__ = 'V0rT3x'
    __version__ = '1.0.1'
    __description__ = 'Custom Dashboard page with Plugin Widgets'

    def __init__(self):
        self._agent = None
        self._app = None
        self._original_loader = None
        self._patched_loader = None

    def on_ready(self, agent):
        self._agent = agent

    def on_loaded(self):
        threading.Thread(target=self._patch_dashboard_menu, daemon=True).start()

    def on_webhook(self, path, request):
        """
        Native Pwnagotchi plugin WebUI endpoint.

        Handler.plugins() dispatches this as:
          /plugins/dashboard
          /plugins/dashboard/<subpath>
        """
        return self._render_dashboard()

    def _render_dashboard(self):
        current_mode = 'manual'
        if self._agent is not None:
            current_mode = getattr(self._agent, 'mode', 'manual')
        other_mode = 'AUTO' if current_mode == 'manual' else 'MANU'

        widgets = []
        for name, plugin in plugins.loaded.items():
            if hasattr(plugin, 'on_dashboard'):
                try:
                    content = plugin.on_dashboard()
                    if content:
                        widgets.append((name, content))
                except Exception as exc:
                    logging.exception('[DashBoard] Widget error in %s: %s', name, exc)

        return render_template_string("""
{% extends "base.html" %}
{% set active_page = "dashboard" %}

{% block title %}
{{ title }} - Dashboard
{% endblock %}

{% block styles %}
{{ super() }}
<style>
    #ui {
        width: 100%;
    }
    .dashboard-container {
        padding: 0.5em;
    }
    .dashboard-widget {
        margin: 10px 0;
        padding: 10px;
        border: 1px solid #ccc;
        border-radius: 5px;
    }
    .dashboard-widget-title {
        margin: 0 0 8px 0;
        font-weight: bold;
    }
</style>
{% endblock %}

{% block script %}
function cacheImage(img, key) {
    try {
        var canvas = document.createElement("canvas");
        canvas.width = img.width;
        canvas.height = img.height;
        var ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);
        var dataURL = canvas.toDataURL("image/png");
        localStorage.setItem(key, dataURL);
    } catch(e) {
        console.log("Error caching image: " + e);
    }
}

function loadCachedImage(key, imgElement) {
    var dataURL = localStorage.getItem(key);
    if (dataURL) {
        imgElement.src = dataURL;
    }
}

window.onload = function() {
    var image = document.getElementById("ui");

    loadCachedImage("ui_cache", image);

    function updateImage() {
        var tmp_image = new Image();
        tmp_image.src = "/ui?" + new Date().getTime();
        tmp_image.onload = function() {
            image.src = this.src;
            cacheImage(this, "ui_cache");
        };
    }

    setInterval(updateImage, 1000);
};
{% endblock %}

{% block content %}
<div class="dashboard-container">
    <img class="ui-image pixelated" src="/ui" id="ui"/>

    <div data-role="navbar">
        <ul>
            <li>
                <form class="action" method="post" action="/shutdown" onsubmit="return confirm('this will halt the unit, continue?');">
                    <input type="submit" class="button ui-btn ui-corner-all" value="Shutdown"/>
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                </form>
            </li>
            <li>
                <form class="action" method="post" action="/reboot" onsubmit="return confirm('this will reboot the unit, continue?');">
                    <input type="submit" class="button ui-btn ui-corner-all" value="Reboot"/>
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                </form>
            </li>
            <li>
                <form class="action" method="post" action="/restart" onsubmit="return confirm('This will restart the service in {{ other_mode }} mode, continue?');">
                    <input type="submit" class="button ui-btn ui-corner-all" value="Restart in {{ other_mode }} mode"/>
                    <input type="hidden" name="mode" value="{{ other_mode }}"/>
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                </form>
            </li>
            <li>
                <form class="action" method="post" action="/restart_kali" onsubmit="return confirm('This will restart the service in KALI mode, continue?');">
                    <input type="submit" class="button ui-btn ui-corner-all" value="Restart in KALI mode"/>
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                </form>
            </li>
        </ul>
    </div>

    {% if widgets %}
        {% for name, widget in widgets %}
            <div class="dashboard-widget">
                <div class="dashboard-widget-title">{{ name }}</div>
                {{ widget|safe }}
            </div>
        {% endfor %}
    {% else %}
        <div class="dashboard-widget">
            No dashboard widgets exposed yet. Plugins can add one with <code>on_dashboard()</code>.
        </div>
    {% endif %}
</div>
{% endblock %}
        """, title=pwnagotchi.name(), current_mode=current_mode, other_mode=other_mode, widgets=widgets)

    def _patch_dashboard_menu(self):
        logging.info('[DashBoard] Patching base.html menu for plugin dashboard...')

        app = self._find_web_app()
        if app is None:
            logging.error('[DashBoard] Could not find Pwnagotchi Flask app to patch.')
            return

        self._app = app
        logging.info('[DashBoard] Flask app found; endpoints=%s', sorted(app.view_functions.keys()))

        if self._patch_base_template(app):
            logging.info('[DashBoard] base.html patched with Dashboard menu item.')
        else:
            logging.warning('[DashBoard] Could not patch base.html; dashboard remains available at /plugins/dashboard.')

    def _find_web_app(self, timeout=60):
        """Find the real Pwnagotchi WebUI Flask app, not just any Flask object."""
        required_endpoints = {'index', 'ui', 'plugins'}

        for _ in range(timeout):
            for obj in gc.get_objects():
                if not isinstance(obj, Flask):
                    continue

                endpoints = set(getattr(obj, 'view_functions', {}).keys())
                if required_endpoints.issubset(endpoints):
                    return obj

            time.sleep(1)

        return None

    def _patch_base_template(self, app):
        if self._original_loader is not None:
            logging.info('[DashBoard] base.html loader already patched by this plugin.')
            return True

        try:
            source, filename, _uptodate = app.jinja_env.loader.get_source(app.jinja_env, 'base.html')
            logging.info('[DashBoard] base.html resolved from: %s', filename)
        except Exception as exc:
            logging.warning('[DashBoard] Could not read base.html source: %s', exc)
            return False

        patched_source = self._inject_dashboard_nav_item(source)
        if patched_source is None:
            logging.warning('[DashBoard] Could not find navigation insertion point in base.html.')
            logging.debug('[DashBoard] base.html source head:\n%s', source[:1500])
            return False

        patched_source = self._inject_dashboard_navfit(patched_source)
        if patched_source is None:
            logging.warning('[DashBoard] Could not patch compact navbar CSS/class in base.html.')
            return False

        if patched_source == source:
            logging.info('[DashBoard] base.html already contains Dashboard menu item and compact navbar fix.')
            return True

        self._original_loader = app.jinja_env.loader
        self._patched_loader = ChoiceLoader([
            DictLoader({'base.html': patched_source}),
            self._original_loader,
        ])
        app.jinja_env.loader = self._patched_loader
        app.jinja_env.cache.clear()
        return True

    def _inject_dashboard_nav_item(self, source):
        dashboard_href = '/plugins/dashboard'
        dashboard_line = "( '/plugins/dashboard', 'dashboard', 'action', 'Dashboard' ),"
        legacy_dashboard_re = re.compile(
            r"\(\s*['\"]/plugins/dashboard['\"]\s*,\s*['\"]dashboard['\"]\s*,\s*['\"]grid['\"]\s*,\s*['\"]Dashboard['\"]\s*\)\s*,"
        )
        if legacy_dashboard_re.search(source):
            return legacy_dashboard_re.sub(dashboard_line, source, count=1)

        literal_dashboard_grid_re = re.compile(
            r'(<a\b(?=[^>]*\bhref=["\']/plugins/dashboard["\'])(?=[^>]*\bdata-icon=)["\']?[^>]*\bdata-icon=)(["\'])grid\2',
            re.IGNORECASE,
        )
        if literal_dashboard_grid_re.search(source):
            return literal_dashboard_grid_re.sub(r'\1\2action\2', source, count=1)

        if '/plugins/dashboard' in source:
            logging.info('[DashBoard] base.html already contains Dashboard menu item.')
            return source

        # Preferred shape from the uploaded base.html:
        #     ( '/plugins', 'plugins', 'grid', 'Plugins' ),
        plugin_re = re.compile(
            r"(?m)^(?P<indent>[ \t]*)\(\s*['\"]/plugins['\"]\s*,\s*['\"]plugins['\"]\s*,\s*['\"]grid['\"]\s*,\s*['\"]Plugins['\"]\s*\)\s*,\s*$"
        )
        match = plugin_re.search(source)
        if match:
            item = f"{match.group('indent')}{dashboard_line}\n"
            return source[:match.start()] + item + source[match.start():]

        # Fallback: inject after Peers if Plugins was renamed or removed.
        peers_re = re.compile(
            r"(?m)^(?P<indent>[ \t]*)\(\s*['\"]/inbox/peers['\"]\s*,\s*['\"]peers['\"]\s*,\s*['\"]user['\"]\s*,\s*['\"]Peers['\"]\s*\)\s*,\s*$"
        )
        match = peers_re.search(source)
        if match:
            item = f"\n{match.group('indent')}{dashboard_line}"
            return source[:match.end()] + item + source[match.end():]

        # Last-resort fallback for a non-list navbar template.
        literal_nav_re = re.compile(r"(?is)(<ul[^>]*>)(?!.*?/plugins/dashboard)")
        match = literal_nav_re.search(source)
        if match:
            item = '\n                <li class="navitem"><a href="%s" id="dashboard" data-icon="action">Dashboard</a></li>' % dashboard_href
            return source[:match.end()] + item + source[match.end():]

        return None

    def _inject_dashboard_navfit(self, source):
        patched_source = source
        navfit_css = """    <style id="v0-dashboard-navfit-css">
        .v0-dashboard-navfit ul {
            display: flex !important;
            flex-wrap: nowrap !important;
            width: 100% !important;
        }
        .v0-dashboard-navfit li {
            float: none !important;
            clear: none !important;
            width: auto !important;
            flex: 1 1 0 !important;
            min-width: 0 !important;
        }
        .v0-dashboard-navfit li a {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            padding-left: 0.25em !important;
            padding-right: 0.25em !important;
            font-size: 0.85em;
        }
    </style>
"""

        navbar_re = re.compile(
            r'(<div\b(?=[^>]*\bdata-role=["\']navbar["\'])(?=[^>]*\bdata-iconpos=["\']left["\'])[^>]*)(>)',
            re.IGNORECASE,
        )
        navbar_class_re = re.compile(
            r'<div\b(?=[^>]*\bdata-role=["\']navbar["\'])(?=[^>]*\bdata-iconpos=["\']left["\'])(?=[^>]*\bv0-dashboard-navfit\b)',
            re.IGNORECASE,
        )
        if not navbar_class_re.search(patched_source):
            match = navbar_re.search(patched_source)
            if not match:
                return None

            navbar_open = match.group(1)
            if re.search(r'\bclass=["\']', navbar_open):
                navbar_open = re.sub(
                    r'\bclass=(["\'])(.*?)\1',
                    lambda class_match: 'class=%s%s v0-dashboard-navfit%s' % (
                        class_match.group(1),
                        class_match.group(2),
                        class_match.group(1),
                    ),
                    navbar_open,
                    count=1,
                )
            else:
                navbar_open += ' class="v0-dashboard-navfit"'

            patched_source = patched_source[:match.start()] + navbar_open + match.group(2) + patched_source[match.end():]

        if 'v0-dashboard-navfit-css' not in patched_source:
            styles_block_re = re.compile(r'(?s)(\{% block styles %\}.*?)([ \t]*\{% endblock %\})')
            match = styles_block_re.search(patched_source)
            if not match:
                return None
            patched_source = (
                patched_source[:match.start()]
                + match.group(1)
                + navfit_css
                + match.group(2)
                + patched_source[match.end():]
            )

        return patched_source

    def on_unload(self, ui):
        if not self._app:
            return

        if self._original_loader is not None:
            if self._app.jinja_env.loader is self._patched_loader:
                logging.info('[DashBoard] Restoring original base.html loader...')
                self._app.jinja_env.loader = self._original_loader
                self._app.jinja_env.cache.clear()
            else:
                logging.warning('[DashBoard] Jinja loader changed after dashboard patch; not restoring to avoid clobbering another plugin.')

            self._original_loader = None
            self._patched_loader = None
