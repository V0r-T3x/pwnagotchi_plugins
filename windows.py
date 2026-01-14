import argparse
import asyncio
import copy
import glob
import importlib.util
import json
import logging
import math
import numpy as np
import os
import random
import re
import requests
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import toml
import traceback
import zipfile

from io import BytesIO
from multiprocessing.connection import Client, Listener
from os import system
from shutil import copy2, copyfile, copytree
from textwrap import TextWrapper
from toml import dump, load
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps, ImageSequence
from flask import abort, jsonify, make_response, render_template_string, send_file, session

import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.faces as faces
import pwnagotchi.ui.fonts as fonts
from pwnagotchi import utils
from pwnagotchi.plugins import toggle_plugin
from pwnagotchi.ui import display
from pwnagotchi.ui.hw import display_for
from pwnagotchi.utils import load_config, merge_config, save_config

V0RT3X_REPO = "https://github.com/V0r-T3x"

LOGO = """░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒░░░░░░▒▒▒▒▒▒▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▓▓▓▓████▓▓▓▓▓▓▓▓▓████████▓▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▓▓▓███████▓▓▓▓▓▓▓▓██████████▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█▓█████▓▓▓▓▓▓▓▓▓▓▓██████████▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓███████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓██████████▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▓▓▓█▓▒▒▒▒▒▒▒▒▓▓▓▓▓▓▓▓███████████▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█▓▓▓█▓▒▒▒▒▓▓▓▓▓▓▓▓▓█████████████▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░▒▓▓▓█▓▓▓█▓▓██████████████████████████████▓▓▓▓▓▓▓▒░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░███████████████████████████████████████████████████▓░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░████████████████████████████████████████████████████░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░▒████████▓▓▓▓▓▓▓▓██████████████████████████████████▒░░░░▒▒▒▒░░░░░░░░░░
░░░░░░░░░▓▓▒░░░░░░░░░░▓█████▓▒▒▒▒▒▒▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓███████▓░░░░░░▓▓▓▓▓▓▓▓▓░░░░░
░░░░░░░░▒▒▒▓▒░░░░░░░░░░░▒▓██▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓██▓▒░░░░░░░░░█▓▓▓▓▓█▓░░░░░░
░░░░░░░░▓░░▒▒▓▒░░░░░░░░░░░░▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓░░░░░░░░░░░▒▒▓▓▓▓▓█▒░░░░░░
░░░░░░░▓▒▒▒▒▒▓▓▒░░░░░░░░░░░▓▒▒▓████▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓█████▓▓▓▓░░░░░░░░░░░▒▒▒▒▒▒▓▓░░░░░░░
░░░░░░░▒▒░░░░▒▒▓░░░░░░░░░░░▓▒▒▒██▓▓████▓▒▒▒▒▒▒▒▒▒▒▓▓████▓███▓▓▓▒░░░░░░░░░░▒▓▓▓▓▓▒▓▒░░░░░░░
░░░░░░░░▓░░░░░▒▓░░░░░░░░░░░░▓▒▒▒███████▓▒▒▒▒▒▒▒▒▒▒▒▓███████▓▓▓▓░░░░░░░░░░░░░▓▓██▓▓░░░░░░░░
░░░░░░░▒▓▒░░░░▓▓▒▒▒░░░░░░░░░▒▓▒▒▒▓███▓▒▒▓▓▓▓▒▒▒▓▓▓▒▒▒▓████▓▓▓▓░░░░░░░░░░░▒▒▓▓▓█░░░░░░░░░░░
░░░░░░░▒▓▓▒▓▒▒▓▓▓█▓▓░░░░░░░░░░▓▒▒▒▒▒▒▒▒▒▒▒▒▓▓▓▓▓▒▒▒▒▒▒▒▒▒▓▓▓▓░░░░░░░░░░░▓▒▒█▓▓▓░░░░░░░░░░░
░░░░░░░░▒█▒▓▓▓▓▓███▓▒░░░░░░░░▒▓█▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓██▒░░░░░░░░░░░█▓▓█▓█▒▒▒░░░░░░░░░
░░░░░░░░░▓░▓▓▓▒▒▓██▓▓▓▒░░░░▒▓███▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓████▓▒░░░░░░░░▓▓██████▓▒▓░░░░░░░░
░░░░░░░░░▒▓▒▒▒▓▓████▓▓▓▓▒▒▓▓▓▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓▓███▓▒▒░▒▒▓▒▒▓██████▓▒▓░░░░░░░░
░░░░░░░░░░░░░▒████▓██▓▓▓▓▓▓▓▒▒▒▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓▒▒▒▒▒▒▒▒▒▒▓██████▓▒▓▒░░░░░░░░
░░░░░░░░░░░░░░▒████▓▒▓▓▓▓▓▓▓▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▒▒▒▒▒▒▓▓▓▓▓▓▓▓▓▓▓█████▓▒▒░░░░░░░░░░
░░░░░░░░░▒██░░░▓█████▓▒▒▒▒▒▒▒▒▒▒▒▒▓▓█▓▒▒▒▒▒▒▓█▓▓▒▒▒▒▒▒▓█▓▓▒▒▒▒▒▒▒▒▒▒▒▒▓███▓█▓▒▒░░░░░░░░░░░
░░░░░░░░▒██░░░░▒▒████████▓▓▓▓▓▓██████▓▒▒▒▒▒▓█████▓▒▒▒▒▒████████▓▓▓▓▓█████░▒██▓██▓░░░░░░░░░
░░░░░░░░▓██░░░▒░░▒█████████▓▓████████▓▒▒▒▒▓███████▓▒▒▒▒████████████████▓░░░▒▒░▒██▓░░░░░░░░
░░░░░░░░▒███▒░░░▒████▒░██▓███▓███████▒▒▒▒▓█████████▓▒▒▒▒████████▓██▓██▓░░░░░░░▒███░░░░░░░░
░░░░░░░░░▒███████████▒▒█▓▓██▓▓▓█████▒▒▒▒▒███████████▓▒▒▒▒██████▓▓█████▓▒░░░░░░▓██▓░░░░░░░░
░░░░░░░░░░░▒▓▓██████▓▓███▓███▓▒▒▓▓▒▒▒▒▒▓██████████████▒▒▒▒▒▓▓▒▒▒██████▓▓▓▒▒▒▓▓███▒░░░░░░░░
░░░░░░░░░░░░░▓███████████▓▓████▓▓▒▒▒▓▓███████▓▒▓██▓█████▓▒▒▒▒▒▓████████████████▓░░░░░░░░░░
░░░░░░░░░░░░░░▓███████████▓███████████████▒░░░░░░░▓▓██████████████▓█████████▓▒░░░░░░░░░░░░
░░░░░░░░░░░░░░░▒▓▓██████▓░░▒█████████████▒░░░░░░░░░▓█▓███████████▒░░▓▓█▓▓▓▓▒░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░▒░░░░░░░▒▓██▓██▓███▓▒░░░░░░░░░░░░▓██▓█████▓▒░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒▒▒░░░░░░░░░░░░░░░░░░░░▒▒▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░"""

INDEX = """
{% extends "base.html" %}
{% set active_page = "plugins" %}
{% block title %}
    Windows
{% endblock %}
{% block meta %}
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, user-scalable=0" />
{% endblock %}
{% block styles %}
{{ super() }}
<style>
    .ui-image {
        width: 100%;
        max-width: 400px;
        border: 1px solid #ccc;
    }
    .pixelated {
        image-rendering: pixelated;
        image-rendering: -moz-crisp-edges;
        image-rendering: crisp-edges;
    }
    .container {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 20px;
        margin-top: 20px;
    }
    .column {
        flex: 1;
        min-width: 300px;
        max-width: 400px;
        text-align: center;
    }
</style>
{% endblock %}
{% block content %}
    <div data-role="navbar">
        <ul>
            <li><a href="#" onclick="display_hijack(); this.blur(); return false;" data-icon="eye">Second hardware display</a></li>
            <li><a href="#" onclick="display_pwny(); this.blur(); return false;" data-icon="home">Pwnagotchi hardware display</a></li>
        </ul>
    </div>
    <div data-role="navbar">
        <ul>
            <li><a href="#" onclick="display_previous(); this.blur(); return false;" data-icon="arrow-l">Previous Mode</a></li>
            <li><a href="#" onclick="display_next(); this.blur(); return false;" data-icon="arrow-r">Next Mode</a></li>
        </ul>
    </div>
    <div data-role="navbar">
        <ul>
            <li><a href="#" onclick="screen_saver_previous(); this.blur(); return false;" data-icon="back">Prev Saver</a></li>
            <li><a href="#" onclick="screen_saver_next(); this.blur(); return false;" data-icon="forward">Next Saver</a></li>
        </ul>
    </div>

    <div class="container">
        <div class="column">
            <h3>Pwnagotchi UI</h3>
            <img class="ui-image pixelated" src="/ui" id="ui" alt="Pwnagotchi UI" />
        </div>
        <div class="column">
            <h3>Second Screen</h3>
            <img class="ui-image pixelated" src="/plugins/windows/ui2" id="ui2" alt="Second Screen" />
        </div>
    </div>
{% endblock %}
{% block script %}
$(document).ready(function() {
    $("[data-role='navbar'] a").click(function() {
        setTimeout(function() {
            $("[data-role='navbar'] a").removeClass("ui-btn-active");
        }, 100);
    });
});

function loadJSON(url, callback) {
    var xobj = new XMLHttpRequest();
    xobj.overrideMimeType("application/json");
    xobj.open('GET', url, true);
    xobj.onreadystatechange = function () {
        if (xobj.readyState == 4 && xobj.status == "200") {
            callback(JSON.parse(xobj.responseText));
        }
    };
    xobj.send(null);
}

function display_hijack() {
    loadJSON("windows/display_hijack", function(response) {
        console.log(response.message);
    });
}
function display_pwny() {
    loadJSON("windows/display_pwny", function(response) {
        console.log(response.message);
    });
}
function display_next() {
    loadJSON("windows/display_next", function(response) {
        console.log(response.message);
    });
}
function display_previous() {
    loadJSON("windows/display_previous", function(response) {
        console.log(response.message);
    });
}
function screen_saver_next() {
    loadJSON("windows/screen_saver_next", function(response) {
        console.log(response.message);
    });
}
function screen_saver_previous() {
    loadJSON("windows/screen_saver_previous", function(response) {
        console.log(response.message);
    });
}

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
    var image2 = document.getElementById("ui2");
    
    loadCachedImage("ui_cache", image);
    loadCachedImage("ui2_cache", image2);

    function updateImage() {
        var tmp_image = new Image();
        tmp_image.src = "/ui?" + new Date().getTime();
        tmp_image.onload = function() {
            image.src = this.src;
            cacheImage(this, "ui_cache");
        }
        var tmp_image2 = new Image();
        tmp_image2.src = "/plugins/windows/ui2?" + new Date().getTime();
        tmp_image2.onload = function() {
            image2.src = this.src;
            cacheImage(this, "ui2_cache");
        }
    }
    setInterval(updateImage, 1000);
}
{% endblock %}
"""

# Use /dev/shm if available to avoid SD card wear and IO errors
if os.path.exists('/dev/shm'):
    FANCYDISPLAY = '/dev/shm/pwnagotchi/Windows.png'
else:
    FANCYDISPLAY = '/var/tmp/pwnagotchi/Windows.png'

class FancyDisplay:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FancyDisplay, cls).__new__(cls)
        return cls._instance

    def __init__(self, enabled=False, fps=24, th_path='', mode='screen_saver', sub_mode='show_logo', config={}):
        self.enabled = enabled
        self.image_lock = threading.Lock()
        self.is_image_locked = False
        self.th_path = th_path
        self.displayImpl = None
        self.hijack_frame = None
        self.task = None
        self.loop = None
        self.thread = None
        self.is_running_event = asyncio.Event()
        self.stop_event = threading.Event()
        self.running = False
        self.fps = fps
        self.fb = self.find_fb_device()
        self.current_mode = mode
        self.current_screen_saver = sub_mode
        self.modes = ['screen_saver', 'auxiliary', 'terminal']
        self.screen_saver_modes = ['show_logo', 'moving_shapes', 'random_colors', 'hyper_drive', 'show_animation']
        if config: self.screen_data = config
        else: self.screen_data = {}
        self.set_mode(mode, sub_mode)

    def _start_loop(self):
        logging.info("[FancyDisplay] Starting the asyncio event loop in a new thread.")
        asyncio.set_event_loop(self.loop)
        self.is_running_event.set()
        try:
            self.loop.run_until_complete(self.screen_controller())
        except asyncio.CancelledError:
            pass
        finally:
            self.loop.close()
            self.is_running_event.clear()

    def start(self, res, rot, col):
        logging.debug("[FancyDisplay] Starting display controller.")
        self._res = res
        self._rot = rot
        self._col = col
        self.displayImpl = self.display_hijack()

        if self.loop is None or self.loop.is_closed():
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self._start_loop, daemon=True)
            self.thread.start()

        while not self.is_running_event.is_set():
            time.sleep(0.1)

    def stop(self):
        self.running = False
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join()
        self.loop = None
        self.thread = None
        logging.debug("[FancyDisplay] Display controller stopped.")

    async def screen_controller(self):
        self.running = True
        while self.running:
            await self.refacer()
            await asyncio.sleep(0.1)

    def is_running(self):
        if self.is_running_event is not None:
            return self.is_running_event.is_set()
        logging.error("[FancyDisplay] is_running_event is not initialized.")
        return False

    def cleanup(self):
        logging.debug("[FancyDisplay] Cleaning up the FancyDisplay resources.")
        self.task = None
        if self.loop is not None:
            if not self.loop.is_closed():
                logging.debug("[FancyDisplay] Closing event loop.")
                self.loop.close()
        self.loop = None
        self.thread = None
        self.displayImpl = None
        self.hijack_frame = None
        self.screen_data = {}
      
    def _calculate_aspect_ratio(self, width, height, aspect_ratio):
        if width < height:
            new_width = width
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = height
            new_width = int(new_height * aspect_ratio)
        return new_width, new_height

    def screen(self):
        return  self.hijack_frame

    async def refacer(self):
        try: 
            fps = 1 / self.fps 
            refresh_interval = 1
            iteration = 0
            while self.running:
                if iteration % refresh_interval == 0:
                    self.hijack_frame = self.get_mode_image()

                if self.hijack_frame is not None:
                    canvas = self.hijack_frame
                    if self._rot == 90:
                        canvas = canvas.rotate(90, expand=True)
                    elif self._rot == 180:
                        canvas = canvas.rotate(180, expand=True)
                    elif self._rot == 270:
                        canvas = canvas.rotate(270, expand=True)

                    canvas.save(FANCYDISPLAY)
                    if self.enabled:
                        canvas = canvas.resize((self._res[0], self._res[1])).convert(self._col)
                        self.displayImpl.render(canvas)
                else:
                    logging.warning("[FancyDisplay] No image to display.")
                
                await asyncio.sleep(fps)
                iteration += 1

        except asyncio.CancelledError:
            logging.warning("[FancyDisplay] refacer cancelled.")
    def display_hijack(self):
        try:
            args = argparse.Namespace(
                config='/etc/pwnagotchi/default.toml', 
                user_config='/etc/pwnagotchi/config.toml', 
                do_manual=False, 
                skip_session=False, 
                do_clear=False, 
                debug=False, 
                version=False, 
                print_config=False, 
                wizard=False, 
                check_update=False, 
                donate=False
            )
            config = utils.load_config(args)
            display_type = config['ui']['display']['type']
            display = config['ui']['display']['enabled']
            self.displayImpl = None

            displayImpl = getattr(self, 'displayImpl', None)
            if not displayImpl or not displayImpl.config.get('enabled', False):
                self.displayImpl = display_for(config)
                self.displayImpl.config['rotation'] = 0
                logging.debug(self.displayImpl.config)

                if hasattr(self.displayImpl, 'initialize') or not self.enabled:
                    logging.debug('[Windows] Initializing display')
                    if self.enabled:
                        self.displayImpl.initialize()
                    self.displayImpl.config['enabled'] = True
                    return self.displayImpl
                else:
                    logging.debug('[Windows] Failed to initialize display: No initialization method found.')
            else:
                logging.debug('[Windows] Display is already initialized.')

        except KeyError as e:
            logging.error(f'[FancyDisplay] KeyError while display hijacking: {e}')
            logging.error(traceback.format_exc())
            
    def glitch_text_effect(self, text, glitch_chance=0.2, max_spaces=3):
        lines = text.split('\n')
        glitched_lines = []

        for line in lines:
            if random.random() < glitch_chance: 
                num_spaces = random.randint(1, max_spaces) 
                line = ' ' * num_spaces + line 

            glitched_lines.append(line)

        return '\n'.join(glitched_lines)

    def set_mode(self, mode, sub_mode=None, config={}):
        if mode in self.modes:
            logging.debug(f"[FancyDisplay] Switching to mode: {mode}")
            self.current_mode = mode
            if mode == "screen_saver":
                self.set_screen_saver_mode(sub_mode)
                self.screen_cdata = config
            elif mode == "auxiliary":
                self.screen_data = config
            elif mode == "terminal":
                self.screen_data = config 
        else:
            logging.warning(f"[FancyDisplay] Invalid mode: {mode}. Available modes are: {self.modes}")
    
    def switch_mode(self, direction='next'):
        current_index = self.modes.index(self.current_mode)
        sub_mode = None
        if direction == 'next':
            next_index = (current_index + 1) % len(self.modes)
        elif direction == 'previous':
            next_index = (current_index - 1) % len(self.modes)
        else:
            logging.warning(f"[FancyDisplay] Invalid direction: {direction}. Using 'next' as default.")
            next_index = (current_index + 1) % len(self.modes)
        
        next_mode = self.modes[next_index]
        
        logging.debug(f"[FancyDisplay] Switching to the {direction} mode: {next_mode}")
        if next_mode == "screen_saver": 
            sub_mode = self.current_screen_saver
        self.set_mode(next_mode, sub_mode)
        self.set_screen_saver_mode(sub_mode)
        self.current_mode = next_mode
        return next_mode

    def find_fb_device(self):
        for i in range(10): 
            fb_device = f"/dev/fb{i}"
            if os.path.exists(fb_device):
                return fb_device
        return None

    def get_fb_size(self):
        import subprocess
        output = subprocess.check_output(['fbset', '-s']).decode('utf-8')
        for line in output.split('\n'):
            if 'geometry' in line:
                parts = line.split()
                return int(parts[1]), int(parts[2])
        return self._res[0], self._res[1] 

    def read_fb(self, width, height):
        with open(self.fb, "rb") as fb:
                return memoryview(fb.read(width * height * 2))

    def terminal_mode(self):
        if self.fb is None:
            return self.show_logo()

        fb_width, fb_height = self.get_fb_size()
        fb_data = self.read_fb(fb_width, fb_height)
        
        rgb_image = self.convert_to_rgb(fb_data, fb_width, fb_height)
        image = Image.fromarray(rgb_image, mode='RGB')
        
        width, height = self._res
        resized_image = image.resize((width, height), Image.BILINEAR)
        
        return resized_image

    def convert_to_rgb(self, fb_data, width, height):
        rgb_array = np.zeros((height, width, 3), dtype=np.uint8)
        pixels = np.frombuffer(fb_data, dtype=np.uint16)
        
        r = ((pixels >> 11) & 0x1F) << 3
        g = ((pixels >> 5) & 0x3F) << 2
        b = (pixels & 0x1F) << 3
        
        rgb_array[..., 0] = r.reshape(height, width)
        rgb_array[..., 1] = g.reshape(height, width)
        rgb_array[..., 2] = b.reshape(height, width)
        
        return rgb_array

    def set_screen_saver_mode(self, sub_mode):
        if sub_mode is None:
            sub_mode = self.current_screen_saver
        if sub_mode in self.screen_saver_modes:
            logging.debug(f"[FancyDisplay] Switching screen_saver to: {sub_mode}")
            self.current_screen_saver = sub_mode
            if sub_mode == 'show_logo':
                options = {}
            elif sub_mode == 'moving_shapes':
                options = {
                    "shape_type": "text", 
                    "text": "Windows", 
                    "font_path": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 
                    "color": "red", 
                    "speed": 10, 
                    "font_size": 15,
                }
            elif sub_mode == 'random_colors':
                options = {
                    "speed": 1,
                }
            elif sub_mode == 'hyper_drive':
                num_stars = 100 
                options = {
                    'stars': [
                        {
                            'position': [random.randint(-self._res[0]//2, self._res[0]//2), random.randint(-self._res[1]//2, self._res[1]//2)],
                            'velocity': random.uniform(2, 5),  
                            'size': random.uniform(1, 3),
                            'streak_length': random.uniform(5, 20),
                            'color': 'white'
                        } for _ in range(num_stars)
                    ],
                    'speed': 1.0 
                }
            elif sub_mode == 'show_animation':
                options = {
                    'frames_path': os.path.join(self.th_path, 'img', 'boot'),
                    'max_loops': 1,
                    'total_duration': 10,
                }
            self.screen_data.update(options)
        else:
            logging.warning(f"[FancyDisplay] Invalid screen_saver sub-mode: {sub_mode}. Available sub-modes are: {self.screen_saver_modes}")

    
    def switch_screen_saver_submode(self, direction='next'):
        if self.current_mode != 'screen_saver':
            logging.warning(f"[FancyDisplay] Not in screen_saver mode. Current mode is: {self.current_mode}")
            return self.current_mode
        
        current_index = self.screen_saver_modes.index(self.current_screen_saver)
        
        if direction == 'next':
            next_index = (current_index + 1) % len(self.screen_saver_modes) 
        elif direction == 'previous':
            next_index = (current_index - 1) % len(self.screen_saver_modes)  
        else:
            logging.error(f"[FancyDisplay] Invalid direction: {direction}. Must be 'next' or 'previous'.")
            return self.current_mode
        
        next_submode = self.screen_saver_modes[next_index]
        logging.warning(f"[FancyDisplay] Switching to the {direction} screen_saver sub-mode: {next_submode}")
        self.set_screen_saver_mode(next_submode)
        return next_submode

    def get_mode_image(self):
        logging.debug(f"[FancyDisplay] Getting mode image: {self.current_mode}")
        if self.current_mode == 'screen_saver':
            return self.get_screen_saver_image()
        elif self.current_mode == 'auxiliary':
            return self.auxiliary_image()
        elif self.current_mode == 'terminal':
            return self.terminal_mode()
        else:
            logging.warning(f"[FancyDisplay] Unknown mode: {self.current_mode}. Falling back to default.")
            return self.show_logo()

    def get_screen_saver_image(self):
        if self.current_screen_saver == 'show_logo':
            return self.show_logo() 
        elif self.current_screen_saver == 'moving_shapes':
            return self.moving_shapes_screen_saver()
        elif self.current_screen_saver == 'random_colors':
            return self.random_colors_screen_saver()
        elif self.current_screen_saver == 'hyper_drive':
            return self.hyperdrive_screen_saver()
        elif self.current_screen_saver == 'show_animation':
            return self.show_animation_screen_saver()
        else:
            logging.warning(f"[FancyDisplay] Unknown screen_saver sub-mode: {self.current_screen_saver}.")
            self.current_screen_saver = 'show_logo'
            return self.show_logo() 


    def auxiliary_image(self):
        image = self.show_logo()
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
        text = "Auxiliary mode"
        text_color = (255, 0, 0) 
        image_width, image_height = image.size
        try:
            text_width, text_height = draw.textsize(text, font)
        except:
            _, _, text_width, text_height = draw.textbbox((0, 0),text, font)
        position = ((image_width - text_width) // 2, 10)
        draw.text(position, text, font=font, fill=text_color)
        return image

    def show_logo(self):
        try:
            width = self._res[0]
            height = self._res[1]
            canvas = Image.new('RGBA', (width, height), 'black')
            draw = ImageDraw.Draw(canvas)
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 3)
            text = self.glitch_text_effect(LOGO, glitch_chance=0.25, max_spaces=5)
            try:
                text_width, text_height = draw.textsize(text, font=font)
            except:
                _, _, text_width, text_height = draw.textbbox((0, 0), text, font=font)
            logo_img = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
            draw_logo = ImageDraw.Draw(logo_img)
            draw_logo.text((0, 0), text, fill='lime', font=font)
            aspect_ratio = text_width / text_height
            new_width, new_height = self._calculate_aspect_ratio(width, height, aspect_ratio)
            resized_logo = logo_img.resize((new_width, new_height))
            x = (width - new_width) // 2
            y = (height - new_height) // 2
            canvas.paste(resized_logo, (x, y), resized_logo)
            self.hijack_frame = canvas
            return canvas
        except KeyError as e:
            logging.debug(f'[FancyDisplay] KeyError while showing logo: {e}')
            logging.debug(traceback.format_exc())

    def moving_shapes_screen_saver(self):
        try:
            font_path = self.screen_data.get('font_path')
            font_size = self.screen_data.get('font_size')
            shape_type = self.screen_data.get('shape_type')
            text = self.screen_data.get('text')
            color = self.screen_data.get('color')
            speed = self.screen_data.get('speed')

            width, height = self._res
            font = ImageFont.truetype(font_path, font_size)

            if shape_type == "text":
                try:
                    shape_width, shape_height = font.getsize(text)
                except:
                    _, _, shape_width, shape_height = font.getbbox(text)
            else:
                shape_width = shape_height = shape_size 
            if not hasattr(self, 'shape_position'):
                self.shape_position = [random.randint(0, width - shape_width), random.randint(0, height - shape_height)]
                self.shape_velocity = [random.choice([-1, 1]) * speed, random.choice([-1, 1]) * speed] 
            x, y = self.shape_position
            vx, vy = self.shape_velocity
            if x + shape_width >= width or x <= 0:
                vx = -vx
            if y + shape_height >= height or y <= 0:
                vy = -vy
            x += vx
            y += vy
            self.shape_position = [x, y]
            self.shape_velocity = [vx, vy]

            canvas = Image.new('RGBA', (width, height), 'black')
            draw = ImageDraw.Draw(canvas)

            if shape_type == "text":
                draw.text((x, y), text, font=font, fill=color)
            else:
                draw.ellipse((x, y, x + shape_width, y + shape_height), fill=color)
            return canvas
        except KeyError as e:
            logging.error(f'[FancyDisplay] KeyError while moving shapes: {e}')
            logging.error(traceback.format_exc())

    def random_colors_screen_saver(self):
        speed = self.screen_data.get('speed')
        width, height = self._res
        canvas = Image.new('RGBA', (width, height), (
            random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 255))
        time.sleep(speed)
        return canvas

    def hyperdrive_screen_saver(self):
        width, height = self._res
        canvas = Image.new('RGBA', (width, height), 'black')
        draw = ImageDraw.Draw(canvas)
        
        center_x, center_y = width // 2, height // 2
        speed = self.screen_data.get('speed', 1.0)
        
        stars = self.screen_data['stars']
        
        for star in stars:
            pos_x, pos_y = star['position']
            velocity = star['velocity'] * speed 
            size = star['size']
            streak_length = star['streak_length']
            
            pos_x *= (1 + velocity / 100)
            pos_y *= (1 + velocity / 100)
            
            streak_end_x = pos_x * (1 + streak_length / 100)
            streak_end_y = pos_y * (1 + streak_length / 100)

            size = min(size * (1 + velocity / 10), 10)
            
            draw.line([(center_x + streak_end_x, center_y + streak_end_y), 
                    (center_x + pos_x, center_y + pos_y)], fill=star['color'], width=int(size))
            
            if abs(pos_x) > width // 2 or abs(pos_y) > height // 2:
                star['position'] = [random.randint(-50, 50), random.randint(-50, 50)]
                star['velocity'] = random.uniform(2, 5)
                star['size'] = random.uniform(1, 3)
                star['streak_length'] = random.uniform(5, 20)
                
                pos_x, pos_y = star['position']
                velocity = star['velocity'] * speed
                pos_x *= (1 + velocity / 100)
                pos_y *= (1 + velocity / 100)
                streak_end_x = pos_x * (1 + star['streak_length'] / 100)
                streak_end_y = pos_y * (1 + star['streak_length'] / 100)
                
                draw.line([(center_x + streak_end_x, center_y + streak_end_y), 
                        (center_x + pos_x, center_y + pos_y)], fill=star['color'], width=int(star['size']))

            star['position'] = [pos_x, pos_y]
        
        return canvas

    def show_animation_screen_saver(self):
        try:
            if self.screen_data is None:
                logging.error("[FancyDisplay] screen_data is None. Unable to show animation screen saver.")
                return self.show_logo() 
                
            frames_path = self.screen_data.get('frames_path', '')
            max_loops = self.screen_data.get('max_loops', 1)
            total_duration = self.screen_data.get('total_duration', 10)
            target_fps = 24
            frame_duration = 0.2

            if not os.path.exists(frames_path):
                image = self.show_logo()
                return image

            valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
            frames = sorted([f for f in os.listdir(frames_path) if f.lower().endswith(valid_extensions)])
            
            if not frames:
                logging.error("[FancyDisplay] No valid frames found in the specified directory")
                return None

            if not hasattr(self, 'animation_state'):
                self.animation_state = {
                    'start_time': time.time(),
                    'loop_count': 0,
                    'extracted_frames': []
                }

            current_time = time.time()
            elapsed_time = current_time - self.animation_state['start_time']

            if (self.animation_state['loop_count'] >= max_loops):
                self.animation_state['start_time'] = current_time
                self.animation_state['loop_count'] = 0
                self.animation_state['extracted_frames'] = []

            if not self.animation_state['extracted_frames']:
                for frame in frames:
                    frame_path = os.path.join(frames_path, frame)
                    if frame.lower().endswith('.gif'):
                        with Image.open(frame_path) as img:
                            for gif_frame in ImageSequence.Iterator(img):
                                self.animation_state['extracted_frames'].append(copy.deepcopy(gif_frame))
                    else:
                        self.animation_state['extracted_frames'].append(Image.open(frame_path))
                
                logging.debug(f"[FancyDisplay] Extracted {len(self.animation_state['extracted_frames'])} frames")

            total_frames = len(self.animation_state['extracted_frames'])
            current_frame_index = int((elapsed_time / frame_duration) % total_frames)

            current_frame = self.animation_state['extracted_frames'][current_frame_index]

            image = current_frame.resize((self._res[0], self._res[1])).convert(self._col)

            if current_frame_index == 0 and elapsed_time > 0: 
                self.animation_state['loop_count'] += 1

            if image is None:
                image = self.show_logo()
            return image

        except Exception as ex:
            logging.error(f"[FancyDisplay] Error in show_animation_screen_saver: {ex}")
            logging.error(traceback.format_exc())
            return None

class Windows(plugins.Plugin):
    __author__ = 'V0rT3x'
    __github__ = 'https://github.com/V0r-T3x/'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Standalone Second Screen & Display Hijacker'
    def __init__(self):
        self._config = pwnagotchi.config
        self.second_screen = Image.new('RGBA', (1,1), 'black')
        self.display_config = {'mode': 'screen_saver', 'sub_mode': 'show_logo'}
        self.screen_modes = ['screen_saver', 'auxiliary', 'terminal']
        self.screen_saver_modes = ['show_logo', 'moving_shapes', 'random_colors', 'hyper_drive', 'show_animation']
        self.dispHijack = False
        self.loop = None
        self.refacer_thread = None
        self._stop_event = threading.Event()
        self._agent = None
        self.ready = False
        self._pwny_root = os.path.dirname(pwnagotchi.__file__)
        self._plug_root = os.path.dirname(os.path.realpath(__file__))
        self.display_controller = None
        self.fps = 24
        self._th_path = ''
        self._res = [128, 64]
        self._color_mode = ['P', 'P']
        if not os.path.exists(os.path.dirname(FANCYDISPLAY)):
            os.makedirs(os.path.dirname(FANCYDISPLAY))

        if self.fps_check(): rst = 1
        self.check_and_fix_fb()

    def pos_convert(self, x, y, w, h, r=None, r0=None, r1=None):
        rot = self._config.get('ui', {}).get('display', {}).get('rotation', 0) if r is None else r

    def fps_check(self):
        rst = 0
        if 'ui' in self._config and 'fps' in self._config['ui']:
            fps_value = int(self._config['ui']['fps'])
            if fps_value == 0:
                self._config['ui']['fps'] = 1
                save_config(self._config, '/etc/pwnagotchi/config.toml')
                rst = 1
        return rst

    def check_and_fix_fb(self):
        config_paths = [
            "/boot/firmware/config.txt",
            "/boot/config.txt"
        ]
        correct_overlay = "dtoverlay=vc4-fkms-v3d"
        wrong_overlay = "dtoverlay=vc4-kms-v3d"

        fb_device_exists = any(os.path.exists(f"/dev/fb{i}") for i in range(10))
        logging.info(f"[Windows] Framebuffer device exists: {fb_device_exists}")
        config_file = None
        for path in config_paths:
            if os.path.exists(path):
                config_file = path
                break

        if not config_file:
            return

        with open(config_file, 'r') as file:
            lines = file.readlines()

        found_correct_overlay = any(correct_overlay in line for line in lines)

        if fb_device_exists:
            logging.info("[Windows] Framebuffer device exists. No reboot needed.")
            return
        elif found_correct_overlay:
            logging.info("[Windows] config.txt already contains the correct overlay. No reboot needed.")
            return
        else:
            logging.info("[Windows] Framebuffer device does not exist config.txt already don't contain the correct overlay. Rebooting system to apply changes...")

        backup_path = config_file + ".bak"
        shutil.copy(config_file, backup_path)
        with open(config_file, 'r') as file:
            lines = file.readlines()
        found_wrong_overlay = False
        found_correct_overlay = False
        new_lines = []
        for line in lines:
            if wrong_overlay in line:
                found_wrong_overlay = True
                new_lines.append(line.replace(wrong_overlay, correct_overlay))
            elif correct_overlay in line:
                found_correct_overlay = True
                new_lines.append(line)
            else:
                new_lines.append(line)
        if not found_correct_overlay:
            new_lines.append(f"\n{correct_overlay}\n")
            logging.info(f"{correct_overlay} added to {config_file}")
        with open(config_file, 'w') as file:
            file.writelines(new_lines)
        logging.info("Rebooting system to apply changes...")
        subprocess.run(["sudo", "reboot"])

    def on_ui_setup(self, ui):
        self._res = [ui._width, ui._height]

    def on_ready(self, agent):
        self._agent = agent

    def on_loaded(self):
        logging.info("[Windows] Loaded")
        self.ready = True

    def on_unload(self, ui):
        with ui._lock:
            self.cleanup_display()
            self.dispHijack = False
            if not self.dispHijack:
                if hasattr(self, 'display_controller') and self.display_controller:
                    self.display_controller.stop()
                if hasattr(ui, '_enabled') and not ui._enabled:
                    ui._enabled = True
                    logging.info("[Windows] Switched back to the original display.")
        if self._config['ui']['display']['enabled']:
            ui._enabled = True
            ui.init_display()

            self.cleanup_display()

        logging.info('[Windows] Unloaded')

    def cleanup_display(self):
        if hasattr(self, 'display_controller') and self.display_controller:
            if self.display_controller.is_running():
                self.display_controller.stop()
            self.display_controller = None
            del self.display_controller

    def on_ui_update(self, ui):
        try:
            if not self.dispHijack:
                if hasattr(self, 'display_controller') and self.display_controller:
                    self.display_controller.stop()
                    self.display_controller = None
                
                image = Image.new('RGBA', (ui._width, ui._height), 'black')
                image.save(FANCYDISPLAY)

                if self._config['ui']['display']['enabled']:
                    if hasattr(ui, '_enabled') and not ui._enabled:
                        ui._enabled = True
                        ui.init_display()
                        logging.info("[Windows] Switched back to the original display.")
            else:
                ui._enabled = False
                if hasattr(self, 'display_controller') and not self.display_controller:
                    logging.info("[Windows] Starting display hijack.")
                    self.display_controller = FancyDisplay(self._config['ui']['display']['enabled'], self.fps, self._th_path)
                    self.display_controller.start(self._res, self.options.get('rotation', 0), self._color_mode[1])
                    mode = self.display_config.get('mode', 'screen_saver')
                    submode = self.display_config.get('sub_mode', 'show_logo')
                    config = self.display_config.get('config', {})
                    self.display_controller.set_mode(mode, submode, config)
                #else:
                #    logging.info("[Windows] Display controller is already running.")

        except Exception as e:
            logging.info("non fatal error while updating Windows: %s" % e)
            logging.info(traceback.format_exc())

    def process_actions(self, command):
        if command is None:
            logging.error("[Fancygotchi] Action is None, unable to process.")
            return
        try:
            action = command.get('action')
            mode = command.get('mode', 'manu')
            logging.info(f'Action: {action}')
            if action == 'switch_screen_mode':
                try:
                    self.display_config['mode'] = self.display_controller.switch_mode()
                except:
                    self.display_config['mode'] = self.screen_modes[(self.screen_modes.index(self.display_config['mode']) + 1) % len(self.screen_modes)]
            elif action == 'switch_screen_mode_reverse':
                try:
                    self.display_config['mode'] = self.display_controller.switch_mode('previous')
                except:
                    self.display_config['mode'] = self.screen_modes[(self.screen_modes.index(self.display_config['mode']) - 1) % len(self.screen_modes)]
            elif action == 'enable_second_screen':
                self.dispHijack = True
                self.fancy_menu.active = False
            elif action == 'disable_second_screen':
                logging.info('disable second screen')
                self.dispHijack = False
            elif action == 'next_screen_saver':
                logging.info('next screen saver')
                try:
                    self.display_config['sub_mode'] = self.display_controller.switch_screen_saver_submode('next')
                except:
                    self.display_config['sub_mode'] = self.screen_saver_modes[(self.screen_saver_modes.index(self.display_config['sub_mode']) + 1) % len(self.screen_saver_modes)]
            elif action == 'previous_screen_saver':
                logging.info('previous screen saver')
                try:
                    self.display_config['sub_mode'] =  self.display_controller.switch_screen_saver_submode('previous')
                except:
                    self.display_config['sub_mode'] = self.screen_saver_modes[(self.screen_saver_modes.index(self.display_config['sub_mode']) + 1) % len(self.screen_saver_modes)]

        except Exception as e:
            logging.error(f'error while processing menu command: {e}')

    def ui2(self):
        try:
            if os.path.exists(FANCYDISPLAY):
                return send_file(FANCYDISPLAY, mimetype='image/png')
            image = self.second_screen
            if hasattr(self, 'display_controller') and self.display_controller:
                image = self.display_controller.screen() or image
            img_io = BytesIO()
            image.save(img_io, 'PNG')
            img_io.seek(0) 
            return send_file(img_io, mimetype='image/png'), 200

        except Exception as ex:
            image = self.second_screen
            img_io = BytesIO()
            image.save(img_io, 'PNG')
            img_io.seek(0) 
            return send_file(img_io, mimetype='image/png'), 200
        
    def on_webhook(self, path, request):
        try:
            if not self.ready:
                return "Plugin not ready"
            if request.method == "GET":
                if path == "/" or not path:
                    return render_template_string(
                        INDEX,)
                elif path == "ui2":
                    return self.ui2()
                elif path == "display_hijack":
                    try:
                        self.dispHijack = True
                        return json.dumps({"message": "Hijack display successful!", "status": 200})
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display hijacking error", 500 
                elif path == "display_pwny":
                    try:
                        self.dispHijack = False
                        return json.dumps({"message": "Pwny change successful!", "status": 200})
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display Pwny error", 500
                elif path == "second_screen":
                    logging.warning("second_screen")
                    try:
                        self.dispHijack = not self.dispHijack
                        return json.dumps({"message": "Second screen change successful!", "status": 200})
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display Pwny error", 500
                elif path == "display_next":
                    try:
                        self.process_actions({"action": "switch_screen_mode"})
                        return json.dumps({"message": "Display change successful!", "status": 200})
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display next error", 500
                elif path == "display_previous":
                    try:
                        self.process_actions({"action": "switch_screen_mode_reverse"})
                        return json.dumps({"message": "Display change successful!", "status": 200})
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display previous error", 500
                elif path == "screen_saver_next":
                    try:
                        self.process_actions({"action": "next_screen_saver"})
                        return json.dumps({"message": "Screen saver change successful!", "status": 200})
                    except Exception as ex:
                            logging.error(ex)
                            logging.error(traceback.format_exc())
                            return "Next screen saver error", 500
                elif path == "screen_saver_previous":
                    try:
                        self.process_actions({"action": "previous_screen_saver"})
                        return json.dumps({"message": "Screen saver change successful!", "status": 200})
                    except Exception as ex:
                            logging.error(ex)
                            logging.error(traceback.format_exc())
                            return "previous screen saver error", 500
                    
            #elif request.method == "POST":

        except Exception as e:
            logging.info(f"Error in webhook: {str(e)}")
            logging.info(traceback.format_exc())
            return None