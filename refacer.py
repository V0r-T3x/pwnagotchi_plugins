import logging
from flask import render_template_string, jsonify, request

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.view as view
import pwnagotchi.ui.fonts as fonts
from PIL import Image, ImageDraw, ImageOps
import threading
import time

TEMPLATE = """
{% extends "base.html" %}
{% set active_page = "plugins" %}
{% block title %}
    Refacer
{% endblock %}
{% block meta %}
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, user-scalable=0" />
    <meta name="csrf-token" content="{{ csrf_token() }}">
{% endblock %}
{% block styles %}
{{ super() }}
<style>
    #refacer-container {
        padding: 15px;
    }
    .refacer-card {
        border: 1px solid #ccc;
        padding: 15px;
        margin-bottom: 15px;
        border-radius: 5px;
        background-color: #f9f9f9;
    }
</style>
{% endblock %}
{% block script %}
function saveConfig() {
    var one_bit = document.getElementById('1bit').value === 'true';
    var save_images = document.getElementById('save_images').value === 'true';
    var save_interval = document.getElementById('save_interval').value;
    var fps = document.getElementById('fps').value;
    
    var xhr = new XMLHttpRequest();
    var url = window.location.pathname;
    if (url.endsWith("/")) {
        url += "config";
    } else {
        url += "/config";
    }
    xhr.open("POST", url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('X-CSRFToken', "{{ csrf_token() }}");
    
    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                alert("Configuration saved!");
            } else {
                alert("Error saving configuration.");
            }
        }
    };
    
    var data = JSON.stringify({
        "1bit": one_bit,
        "save_images": save_images,
        "save_interval": parseInt(save_interval),
        "fps": parseInt(fps)
    });
    
    xhr.send(data);
}
{% endblock %}
{% block content %}
    <div id="refacer-container">
        <h2>Refacer Plugin</h2>
        <div class="refacer-card">
            <h3>Configuration</h3>
            <form onsubmit="event.preventDefault(); saveConfig();">
                <div class="ui-field-contain">
                    <label for="1bit">1-Bit Color Conversion:</label>
                    <select name="1bit" id="1bit" data-role="flipswitch">
                        <option value="false" {% if not options.get('1bit') %}selected{% endif %}>Off</option>
                        <option value="true" {% if options.get('1bit') %}selected{% endif %}>On</option>
                    </select>
                </div>
                <div class="ui-field-contain">
                    <label for="save_images">Save Images to FS:</label>
                    <select name="save_images" id="save_images" data-role="flipswitch">
                        <option value="false" {% if not options.get('save_images') %}selected{% endif %}>Off</option>
                        <option value="true" {% if options.get('save_images') %}selected{% endif %}>On</option>
                    </select>
                </div>
                <div class="ui-field-contain">
                    <label for="save_interval">Save Interval (frames):</label>
                    <input type="number" name="save_interval" id="save_interval" value="{{ options.get('save_interval', 10) }}">
                </div>
                <div class="ui-field-contain">
                    <label for="fps">Target FPS:</label>
                    <input type="number" name="fps" id="fps" value="{{ options.get('fps', 30) }}">
                </div>
                <button type="submit" class="ui-btn ui-btn-b ui-corner-all">Save Configuration</button>
            </form>
        </div>
    </div>
{% endblock %}
"""

class Refacer(plugins.Plugin):
    __author__ = '@V0rT3x'
    __version__ = '1.1.0'
    __license__ = 'GPL3'
    __description__ = 'Decouples rendering from state updates for advanced UI effects.'
    
    def __init__(self):
        self.ready = False
        self._running = False
        self._render_thread = None
        self._view_instance = None
        self.fps = 30 # Define your custom FPS here
        self._lock = threading.Lock()
        self._agent = None
        self.enabled = True

    def on_ready(self, agent):
        self._agent = agent

    def on_loaded(self):
        self.fps = self.options.get('fps', 30)
        self._old_update = view.View.update
        
        # Hijack the update to ONLY sync data, not draw
        refacer = self
        def proxy_update(view_instance, force=False, new_data={}):
            return refacer.sync_state_only(view_instance, force, new_data)
        
        view.View.update = proxy_update
        
        # Start the independent render loop
        self._running = True
        self._render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self._render_thread.start()
        
        logging.info(f"[Refacer] Started independent render loop at {self.fps} FPS.")

    def on_unload(self, ui):
        self._running = False
        if self._render_thread:
            self._render_thread.join(timeout=1)
        view.View.update = self._old_update
        logging.info("[Refacer] Render loop stopped and View restored.")

    def on_webhook(self, path, request):
        if request.method == "GET":
            if path == "/" or not path:
                return render_template_string(TEMPLATE, options=self.options)
        elif request.method == "POST":
            if path == "config":
                try:
                    data = request.get_json()
                    self.options['1bit'] = data['1bit']
                    self.options['save_images'] = data['save_images']
                    self.options['save_interval'] = data['save_interval']
                    self.options['fps'] = data['fps']
                    self.fps = self.options['fps']
                    
                    if self._agent:
                        config = self._agent.config()
                        if 'refacer' not in config['main']['plugins']:
                            config['main']['plugins']['refacer'] = {}
                        
                        config['main']['plugins']['refacer']['1bit'] = self.options['1bit']
                        config['main']['plugins']['refacer']['save_images'] = self.options['save_images']
                        config['main']['plugins']['refacer']['save_interval'] = self.options['save_interval']
                        config['main']['plugins']['refacer']['fps'] = self.options['fps']
                        
                        from pwnagotchi.utils import save_config
                        save_config(config, '/etc/pwnagotchi/config.toml')
                    
                    return jsonify({'status': 'success'})
                except Exception as e:
                    logging.error(f"[Refacer] Error saving config: {e}")
                    return jsonify({'status': 'error', 'message': str(e)}), 500
        return "Not Found", 404

    def rgba_text(self, text, tfont, color='black'):
        try:
            if color == 'white': color = (249, 249, 249, 255)
            
            if text is not None and tfont is not None:
                try:
                    w, h = tfont.getsize(text)
                except AttributeError:
                    left, top, right, bottom = tfont.getbbox(text)
                    w = right - left
                    h = bottom - top
                
                nb_lines = text.count('\n') + 1
                h = (h + 1) * nb_lines
                if nb_lines > 1:
                    lines = text.split('\n')
                    max_char = 0
                    tot_char = 0
                    for line in lines:
                        tot_char = tot_char + len(line)
                        char_line = len(line)
                        if char_line > max_char: max_char = char_line
                    if tot_char > 0:
                        w = int(w / (tot_char / max_char))
                
                imgtext = Image.new('1', (int(w), int(h)), 1)
                dt = ImageDraw.Draw(imgtext)
                dt.text((0, 0), text, font=tfont, fill=0)
                
                imgtext = ImageOps.colorize(imgtext.convert('L'), black=color, white='white')
                imgtext = imgtext.convert("RGBA")
                
                data = imgtext.getdata()
                newData = []
                for item in data:
                    if item[0] in range(250, 256) and item[1] in range(250, 256) and item[2] in range(250, 256):
                        newData.append((255, 255, 255, 0))
                    else:
                        newData.append(item)
                imgtext.putdata(newData)
                return imgtext
        except Exception as e:
            logging.error(f"[Refacer] rgba_text error: {e}")
            return None

    def sync_state_only(self, view_instance, force=False, new_data={}):
        """This replaces the core update; it just ingests data for our thread."""
        for key, val in new_data.items():
            view_instance.set(key, val)
        
        # Dispatch on_ui_update to all plugins so they can react to state changes
        for plugin in plugins.loaded.values():
            if hasattr(plugin, 'on_ui_update'):
                try:
                    plugin.on_ui_update(view_instance)
                except Exception as e:
                    logging.error(f"[Refacer] Error in plugin {plugin.__class__.__name__}: {e}")

        if not self.enabled:
            return
        
        self._view_instance = view_instance

    def _render_loop(self):
        """Independent loop for image creation and animations."""
        frame_counter = 0
        while self._running:
            if not self.enabled:
                time.sleep(0.5)
                continue

            if not self._view_instance:
                time.sleep(0.1)
                continue

            start_time = time.time()
            
            with self._view_instance._lock:
                if not self._view_instance._frozen:
                    # 1. Create the RGBA Canvas
                    canvas = Image.new('RGBA', 
                                     (self._view_instance._width, self._view_instance._height), 
                                     (255, 255, 255, 0))
                    
                    # 2. Render CSS/State (Animations can be calculated here)
                    self.render_refaced_frame(canvas, self._view_instance._state)
                    
                    # 3. Update the shared View canvas
                    # If using E-ink, you might convert to '1' here
                    if self.options.get('1bit', False):
                        self._view_instance._canvas = canvas.convert('1')
                    else:
                        self._view_instance._canvas = canvas 

                    # Render to hardware
                    if hasattr(self._view_instance, '_enabled') and self._view_instance._enabled:
                        try:
                            self._view_instance._implementation.render(self._view_instance._canvas)
                        except Exception:
                            pass

                    # 4. Push to Web and Callbacks
                    import pwnagotchi.ui.web as web
                    
                    if self.options.get('save_images', False):
                        if frame_counter % self.options.get('save_interval', 10) == 0:
                            web.update_frame(self._view_instance._canvas)
                    
                    for cb in self._view_instance._render_cbs:
                        cb(self._view_instance._canvas)

            frame_counter += 1
            # Control FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, (1.0 / self.fps) - elapsed)
            time.sleep(sleep_time)

    def render_refaced_frame(self, canvas, state):
        # Your CSS/PIL engine logic goes here
        # You can now use a global 'frame_count' for animations
        draw = ImageDraw.Draw(canvas)
        for key, widget in state.items():
            if widget:
                xy = getattr(widget, 'xy', None)
                if xy is None:
                    continue

                # Handle Lines (4 coordinates)
                if isinstance(xy, (list, tuple)) and len(xy) == 4:
                    draw.line(xy, fill=(0, 0, 0, 255))
                    continue

                value = getattr(widget, 'value', None)
                label = getattr(widget, 'label', None)
                
                if label:
                    label_font = getattr(widget, 'label_font', fonts.Bold)
                    lbl_img = self.rgba_text(str(label), label_font, 'black')
                    if lbl_img:
                        canvas.paste(lbl_img, (int(xy[0]), int(xy[1])), lbl_img)
                        xy = (xy[0] + lbl_img.width + 5, xy[1])
                
                if value is not None:
                    text_font = getattr(widget, 'text_font', getattr(widget, 'font', fonts.Medium))
                    val_img = self.rgba_text(str(value), text_font, 'black')
                    if val_img:
                        canvas.paste(val_img, (int(xy[0]), int(xy[1])), val_img)