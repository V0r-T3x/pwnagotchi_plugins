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
{% block title %}Windows{% endblock %}
{% block meta %}
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, user-scalable=0" />
    <meta name="csrf-token" content="{{ csrf_token() if csrf_token is defined else '' }}">
{% endblock %}
{% block styles %}
{{ super() }}
<style>
    #windows-manager { padding: 15px; }
    .windows-card { border: 1px solid #ccc; padding: 15px; margin-bottom: 15px; border-radius: 5px; background: #f9f9f9; }
    .windows-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; }
    .windows-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 8px 0; }
    .windows-preview { width: 100%; max-width: 420px; border: 1px solid #bbb; background: #fff; image-rendering: pixelated; }
    .windows-status { min-height: 20px; font-weight: bold; white-space: pre-wrap; }
    .windows-muted { color: #555; font-size: 0.9em; }
    .windows-form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
    .windows-form-grid label { display: block; font-weight: bold; margin-bottom: 3px; }
    .windows-form-grid input, .windows-form-grid select { width: 100%; box-sizing: border-box; }
    .windows-list { margin: 0; padding-left: 18px; }
</style>
{% endblock %}
{% block content %}
<div id="windows-manager">
    <h2>Windows Manager</h2>
    <div id="windows-main-status" class="windows-status">Loading...</div>
    <div data-role="tabs" id="windows-tabs">
        <div data-role="navbar">
            <ul>
                <li><a href="#windows-manager-tab" class="ui-btn-active">Manager</a></li>
                <li><a href="#windows-saver-tab">Screen Saver</a></li>
                <li><a href="#windows-aux-tab">Aux</a></li>
                <li><a href="#windows-config-tab">Configuration</a></li>
            </ul>
        </div>
        <div id="windows-manager-tab" class="ui-content">
            <div class="windows-grid">
                <div class="windows-card">
                    <h3>Pwnagotchi UI</h3>
                    <img class="windows-preview" src="/ui" id="windows-ui" alt="Pwnagotchi UI">
                </div>
                <div class="windows-card">
                    <h3>Second Screen</h3>
                    <img class="windows-preview" src="/plugins/windows/ui2" id="windows-ui2" alt="Second Screen">
                </div>
            </div>
            <div class="windows-card">
                <h3>Runtime Controls</h3>
                <div class="windows-actions">
                    <button id="windows-second-screen-btn" class="ui-btn ui-btn-inline ui-corner-all">Second Screen: Off</button>
                    <button id="windows-pwny-btn" class="ui-btn ui-btn-inline ui-corner-all">Pwny Screen</button>
                    <button id="windows-start-saver-btn" class="ui-btn ui-btn-inline ui-corner-all">Start Screen Saver</button>
                    <button id="windows-stop-saver-btn" class="ui-btn ui-btn-inline ui-corner-all">Stop Screen Saver</button>
                    <button id="windows-reset-runtime-btn" class="ui-btn ui-corner-all">Reset Runtime to Defaults</button>
                    <button id="windows-refresh-btn" class="ui-btn ui-corner-all">Refresh</button>
                </div>
                <ul id="windows-status-list" class="windows-list"></ul>
            </div>
        </div>
        <div id="windows-saver-tab" class="ui-content">
            <div class="windows-card">
                <h3>Screen Saver Runtime</h3>
                <div class="windows-form-grid">
                    <div><label for="windows-runtime-saver">Current screen saver</label><select id="windows-runtime-saver"></select></div>
                </div>
                <div class="windows-actions">
                    <button id="windows-apply-saver-btn" class="ui-btn ui-btn-inline ui-corner-all">Apply Now</button>
                    <button id="windows-start-this-saver-btn" class="ui-btn ui-btn-inline ui-corner-all">Start This Saver Now</button>
                    <button id="windows-prev-saver-btn" class="ui-btn ui-corner-all">Previous Saver</button>
                    <button id="windows-next-saver-btn" class="ui-btn ui-corner-all">Next Saver</button>
                </div>
            </div>
            <div class="windows-card">
                <h3>Screen Saver Defaults</h3>
                <div class="windows-form-grid">
                    <div><label for="windows-default-saver">Default screen saver</label><select id="windows-default-saver"></select></div>
                </div>
                <div class="windows-actions">
                    <button id="windows-save-saver-default-btn" class="ui-btn ui-btn-inline ui-corner-all">Save as Default</button>
                    <button id="windows-save-saver-apply-btn" class="ui-btn ui-btn-inline ui-corner-all">Save as Default + Apply Now</button>
                </div>
            </div>
            <div class="windows-card">
                <h3>Screen Saver Options</h3>
                <div class="windows-form-grid">
                    <div><label for="opt-moving-shapes-text">Moving text</label><input id="opt-moving-shapes-text" type="text"></div>
                    <div><label for="opt-moving-shapes-color">Moving color</label><input id="opt-moving-shapes-color" type="text"></div>
                    <div><label for="opt-moving-shapes-speed">Moving speed</label><input id="opt-moving-shapes-speed" type="number"></div>
                    <div><label for="opt-moving-shapes-font-size">Moving font size</label><input id="opt-moving-shapes-font-size" type="number"></div>
                    <div><label for="opt-moving-shapes-font-path">Moving font path</label><input id="opt-moving-shapes-font-path" type="text"></div>
                    <div><label for="opt-random-colors-speed">Random colors speed</label><input id="opt-random-colors-speed" type="number"></div>
                    <div><label for="opt-hyper-drive-stars">Hyper drive stars</label><input id="opt-hyper-drive-stars" type="number"></div>
                    <div><label for="opt-hyper-drive-speed">Hyper drive speed</label><input id="opt-hyper-drive-speed" type="number" step="0.1"></div>
                    <div><label for="opt-animation-frames-path">Animation frames path</label><input id="opt-animation-frames-path" type="text"></div>
                    <div><label for="opt-animation-max-loops">Animation max loops</label><input id="opt-animation-max-loops" type="number"></div>
                    <div><label for="opt-animation-total-duration">Animation total duration</label><input id="opt-animation-total-duration" type="number"></div>
                </div>
            </div>
        </div>
        <div id="windows-aux-tab" class="ui-content">
            <div class="windows-card">
                <h3>Aux Runtime</h3>
                <div class="windows-form-grid">
                    <div><label for="windows-runtime-aux">Current aux plugin</label><select id="windows-runtime-aux"></select></div>
                </div>
                <div class="windows-actions">
                    <button id="windows-apply-aux-btn" class="ui-btn ui-btn-inline ui-corner-all">Apply Aux Plugin</button>
                    <button id="windows-start-aux-btn" class="ui-btn ui-btn-inline ui-corner-all">Start Auxiliary Mode</button>
                    <button id="windows-prev-aux-btn" class="ui-btn ui-corner-all">Previous Aux</button>
                    <button id="windows-next-aux-btn" class="ui-btn ui-corner-all">Next Aux</button>
                </div>
            </div>
            <div class="windows-card">
                <h3>Aux Defaults</h3>
                <div class="windows-form-grid">
                    <div><label for="windows-default-aux">Default aux plugin</label><select id="windows-default-aux"></select></div>
                </div>
                <div class="windows-actions">
                    <button id="windows-save-aux-default-btn" class="ui-btn ui-btn-inline ui-corner-all">Save Default Aux</button>
                    <button id="windows-save-aux-apply-btn" class="ui-btn ui-btn-inline ui-corner-all">Save Default Aux + Apply Now</button>
                </div>
                <div id="windows-aux-status" class="windows-status"></div>
            </div>
        </div>
        <div id="windows-config-tab" class="ui-content">
            <div class="windows-card">
                <h3>Runtime</h3>
                <div class="windows-form-grid">
                    <div><label for="windows-runtime-fps">FPS</label><input id="windows-runtime-fps" type="number"></div>
                    <div><label for="windows-runtime-mode">Mode</label><select id="windows-runtime-mode"></select></div>
                </div>
                <div class="windows-actions">
                    <button id="windows-apply-fps-btn" class="ui-btn ui-btn-inline ui-corner-all">Apply FPS Now</button>
                    <button id="windows-apply-mode-btn" class="ui-btn ui-btn-inline ui-corner-all">Apply Mode Now</button>
                </div>
            </div>
            <div class="windows-card">
                <h3>Defaults</h3>
                <div class="windows-form-grid">
                    <div><label for="windows-default-fps">Default FPS</label><input id="windows-default-fps" type="number"></div>
                    <div><label for="windows-default-rotation">Default rotation</label><input id="windows-default-rotation" type="number"></div>
                    <div><label for="windows-default-mode">Default mode</label><select id="windows-default-mode"></select></div>
                    <div><label for="windows-default-saver-config">Default screen saver</label><select id="windows-default-saver-config"></select></div>
                    <div><label for="windows-default-aux-config">Default aux plugin</label><select id="windows-default-aux-config"></select></div>
                </div>
                <div class="windows-actions">
                    <button id="windows-save-config-btn" class="ui-btn ui-btn-inline ui-corner-all">Save Defaults</button>
                    <button id="windows-save-config-reset-btn" class="ui-btn ui-btn-inline ui-corner-all">Save Defaults + Reset Runtime</button>
                    <button id="windows-reload-config-btn" class="ui-btn ui-corner-all">Reload</button>
                </div>
                <div id="windows-config-status" class="windows-status"></div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
{% block script %}
var windowsStatus = null;
var windowsPreviewTimer = null;
function windowsPath(path) {
    var base = window.location.pathname.replace(/\/+$/, "");
    return base + (path ? "/" + path : "");
}
function requestJSON(method, path, data, onSuccess, statusId) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, windowsPath(path), true);
    var tokenEl = document.querySelector("meta[name='csrf-token']");
    if (tokenEl && tokenEl.content) xhr.setRequestHeader("X-CSRFToken", tokenEl.content);
    if (data !== null) xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function() {
        if (xhr.readyState !== 4) return;
        var body = {};
        try { body = xhr.responseText ? JSON.parse(xhr.responseText) : {}; } catch (e) { body = {}; }
        if (xhr.status >= 200 && xhr.status < 300) {
            if (onSuccess) onSuccess(body);
        } else if (statusId) {
            setStatus(statusId, body.error || body.message || ("Request failed (" + xhr.status + ")"), true);
        }
    };
    xhr.send(data === null ? null : JSON.stringify(data));
}
function setStatus(id, msg, isError) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg || "";
    el.style.color = isError ? "#a40000" : "#1f5f1f";
}
function fillSelect(id, values, selected, includeBlank) {
    var el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = "";
    if (includeBlank) {
        var blank = document.createElement("option");
        blank.value = "";
        blank.textContent = "None";
        el.appendChild(blank);
    }
    (values || []).forEach(function(value) {
        var opt = document.createElement("option");
        opt.value = value;
        opt.textContent = value;
        if (value === selected) opt.selected = true;
        el.appendChild(opt);
    });
}
function optionValue(id, fallback) {
    var el = document.getElementById(id);
    return el ? el.value : fallback;
}
function optionInt(id, fallback) {
    var v = parseInt(optionValue(id, fallback), 10);
    return isNaN(v) ? fallback : v;
}
function optionFloat(id, fallback) {
    var v = parseFloat(optionValue(id, fallback));
    return isNaN(v) ? fallback : v;
}
function collectOptionsPatch() {
    return {
        moving_shapes_text: optionValue("opt-moving-shapes-text", "Windows"),
        moving_shapes_color: optionValue("opt-moving-shapes-color", "red"),
        moving_shapes_speed: optionInt("opt-moving-shapes-speed", 10),
        moving_shapes_font_size: optionInt("opt-moving-shapes-font-size", 15),
        moving_shapes_font_path: optionValue("opt-moving-shapes-font-path", ""),
        random_colors_speed: optionInt("opt-random-colors-speed", 1),
        hyper_drive_stars: optionInt("opt-hyper-drive-stars", 100),
        hyper_drive_speed: optionFloat("opt-hyper-drive-speed", 1.0),
        animation_frames_path: optionValue("opt-animation-frames-path", ""),
        animation_max_loops: optionInt("opt-animation-max-loops", 1),
        animation_total_duration: optionInt("opt-animation-total-duration", 10)
    };
}
function renderStatus(body) {
    windowsStatus = body || {};
    var modes = windowsStatus.screen_modes || [];
    var savers = windowsStatus.screen_saver_modes || [];
    var aux = windowsStatus.aux_plugins || [];
    fillSelect("windows-runtime-mode", modes, windowsStatus.current_mode, false);
    fillSelect("windows-default-mode", modes, windowsStatus.default_mode, false);
    fillSelect("windows-runtime-saver", savers, windowsStatus.current_screen_saver, false);
    fillSelect("windows-default-saver", savers, windowsStatus.default_screen_saver, false);
    fillSelect("windows-default-saver-config", savers, windowsStatus.default_screen_saver, false);
    fillSelect("windows-runtime-aux", aux, windowsStatus.current_aux_plugin || "", true);
    fillSelect("windows-default-aux", aux, windowsStatus.default_aux_plugin || "", true);
    fillSelect("windows-default-aux-config", aux, windowsStatus.default_aux_plugin || "", true);
    document.getElementById("windows-runtime-fps").value = windowsStatus.fps || 24;
    document.getElementById("windows-default-fps").value = (windowsStatus.options || {}).fps || windowsStatus.fps || 24;
    document.getElementById("windows-default-rotation").value = (windowsStatus.options || {}).rotation || 0;
    var opts = windowsStatus.options || {};
    document.getElementById("opt-moving-shapes-text").value = opts.moving_shapes_text || "Windows";
    document.getElementById("opt-moving-shapes-color").value = opts.moving_shapes_color || "red";
    document.getElementById("opt-moving-shapes-speed").value = opts.moving_shapes_speed || 10;
    document.getElementById("opt-moving-shapes-font-size").value = opts.moving_shapes_font_size || 15;
    document.getElementById("opt-moving-shapes-font-path").value = opts.moving_shapes_font_path || "";
    document.getElementById("opt-random-colors-speed").value = opts.random_colors_speed || 1;
    document.getElementById("opt-hyper-drive-stars").value = opts.hyper_drive_stars || 100;
    document.getElementById("opt-hyper-drive-speed").value = opts.hyper_drive_speed || 1.0;
    document.getElementById("opt-animation-frames-path").value = opts.animation_frames_path || "";
    document.getElementById("opt-animation-max-loops").value = opts.animation_max_loops || 1;
    document.getElementById("opt-animation-total-duration").value = opts.animation_total_duration || 10;
    var btn = document.getElementById("windows-second-screen-btn");
    if (btn) {
        btn.textContent = "Second Screen: " + (windowsStatus.dispHijack ? "On" : "Off");
        btn.dataset.enabled = windowsStatus.dispHijack ? "1" : "0";
    }
    var rows = [
        ["Hijack", windowsStatus.dispHijack ? "On" : "Off"],
        ["Controller", windowsStatus.controller_running ? "Running" : "Stopped"],
        ["Current mode", windowsStatus.current_mode || ""],
        ["Current saver", windowsStatus.current_screen_saver || ""],
        ["Current aux", windowsStatus.current_aux_plugin || "None"],
        ["Default mode", windowsStatus.default_mode || ""],
        ["Default saver", windowsStatus.default_screen_saver || ""],
        ["Default aux", windowsStatus.default_aux_plugin || "None"]
    ];
    var list = document.getElementById("windows-status-list");
    if (list) {
        list.innerHTML = "";
        rows.forEach(function(row) {
            var li = document.createElement("li");
            li.textContent = row[0] + ": " + row[1];
            list.appendChild(li);
        });
    }
    setStatus("windows-main-status", "Runtime " + (windowsStatus.current_mode || "unknown") + " / " + (windowsStatus.current_screen_saver || "none"), false);
    setStatus("windows-aux-status", "Runtime aux: " + (windowsStatus.current_aux_plugin || "None") + " | Default aux: " + (windowsStatus.default_aux_plugin || "None"), false);
}
function refreshStatus() { requestJSON("GET", "status", null, renderStatus, "windows-main-status"); }
function refreshPreviews() {
    var ui = document.getElementById("windows-ui");
    var ui2 = document.getElementById("windows-ui2");
    if (ui) ui.src = "/ui?t=" + Date.now();
    if (ui2) ui2.src = windowsPath("ui2") + "?t=" + Date.now();
}
function startPreviewRefresh() {
    if (windowsPreviewTimer) window.clearInterval(windowsPreviewTimer);
    windowsPreviewTimer = window.setInterval(refreshPreviews, 1000);
    refreshPreviews();
}
function setSecondScreen(enabled) {
    requestJSON("GET", enabled ? "display_hijack" : "display_pwny", null, function(body) { renderStatus(body); refreshPreviews(); }, "windows-main-status");
}
function startScreenSaver(subMode) {
    requestJSON("GET", "screen_saver_start", null, function(body) { renderStatus(body); refreshPreviews(); }, "windows-main-status");
}
function stopScreenSaver() {
    requestJSON("GET", "screen_saver_stop", null, function(body) { renderStatus(body); refreshPreviews(); }, "windows-main-status");
}
function applyRuntimeMode(mode) {
    requestJSON("POST", "set_mode", {mode: mode, apply_now: true}, renderStatus, "windows-config-status");
}
function applyRuntimeSaver(subMode) {
    requestJSON("POST", "set_screen_saver", {sub_mode: subMode, apply_now: true, options_patch: collectOptionsPatch()}, renderStatus, "windows-main-status");
}
function applyRuntimeAux(name) {
    requestJSON("POST", "set_aux", {plugin: name, apply_now: true}, renderStatus, "windows-aux-status");
}
function saveDefaults(applyNow) {
    var patch = collectOptionsPatch();
    patch.fps = optionInt("windows-default-fps", 24);
    patch.rotation = optionInt("windows-default-rotation", 0);
    patch.default_mode = optionValue("windows-default-mode", "screen_saver");
    patch.default_screen_saver = optionValue("windows-default-saver-config", optionValue("windows-default-saver", "show_logo"));
    patch.default_aux_plugin = optionValue("windows-default-aux-config", optionValue("windows-default-aux", ""));
    requestJSON("POST", "save_config", {options: patch, reset_runtime: !!applyNow}, function(body) {
        renderStatus(body);
        setStatus("windows-config-status", "Defaults saved.", false);
    }, "windows-config-status");
}
function saveSaverDefault(applyNow) {
    requestJSON("POST", "set_screen_saver", {
        sub_mode: optionValue("windows-default-saver", "show_logo"),
        persist: true,
        apply_now: !!applyNow,
        options_patch: collectOptionsPatch()
    }, renderStatus, "windows-main-status");
}
function saveAuxDefault(applyNow) {
    requestJSON("POST", "set_aux", {plugin: optionValue("windows-default-aux", ""), persist: true, apply_now: !!applyNow}, renderStatus, "windows-aux-status");
}
function resetRuntimeToDefaults() {
    requestJSON("POST", "reset_runtime_defaults", {}, function(body) { renderStatus(body); refreshPreviews(); }, "windows-main-status");
}
function bindWindowsActions() {
    var bindings = [
        ["windows-second-screen-btn", function() { setSecondScreen(!(this.dataset.enabled === "1")); }],
        ["windows-pwny-btn", function() { setSecondScreen(false); }],
        ["windows-start-saver-btn", function() { startScreenSaver(); }],
        ["windows-stop-saver-btn", stopScreenSaver],
        ["windows-reset-runtime-btn", resetRuntimeToDefaults],
        ["windows-refresh-btn", function() { refreshStatus(); refreshPreviews(); }],
        ["windows-apply-saver-btn", function() { applyRuntimeSaver(optionValue("windows-runtime-saver", "show_logo")); }],
        ["windows-start-this-saver-btn", function() { startScreenSaver(optionValue("windows-runtime-saver", "show_logo")); }],
        ["windows-prev-saver-btn", function() { requestJSON("GET", "screen_saver_previous", null, renderStatus, "windows-main-status"); }],
        ["windows-next-saver-btn", function() { requestJSON("GET", "screen_saver_next", null, renderStatus, "windows-main-status"); }],
        ["windows-save-saver-default-btn", function() { saveSaverDefault(false); }],
        ["windows-save-saver-apply-btn", function() { saveSaverDefault(true); }],
        ["windows-apply-aux-btn", function() { applyRuntimeAux(optionValue("windows-runtime-aux", "")); }],
        ["windows-start-aux-btn", function() { applyRuntimeMode("auxiliary"); }],
        ["windows-prev-aux-btn", function() { requestJSON("GET", "aux_prev", null, renderStatus, "windows-aux-status"); }],
        ["windows-next-aux-btn", function() { requestJSON("GET", "aux_next", null, renderStatus, "windows-aux-status"); }],
        ["windows-save-aux-default-btn", function() { saveAuxDefault(false); }],
        ["windows-save-aux-apply-btn", function() { saveAuxDefault(true); }],
        ["windows-apply-fps-btn", function() { requestJSON("POST", "apply_runtime", {fps: optionInt("windows-runtime-fps", 24)}, renderStatus, "windows-config-status"); }],
        ["windows-apply-mode-btn", function() { applyRuntimeMode(optionValue("windows-runtime-mode", "screen_saver")); }],
        ["windows-save-config-btn", function() { saveDefaults(false); }],
        ["windows-save-config-reset-btn", function() { saveDefaults(true); }],
        ["windows-reload-config-btn", refreshStatus]
    ];
    bindings.forEach(function(binding) {
        var el = document.getElementById(binding[0]);
        if (!el || el.dataset.windowsBound === "1") return;
        el.addEventListener("click", function(event) { event.preventDefault(); binding[1].call(el); });
        el.dataset.windowsBound = "1";
    });
}
document.addEventListener("DOMContentLoaded", function() {
    bindWindowsActions();
    refreshStatus();
    startPreviewRefresh();
    try { if (window.jQuery) window.jQuery("#windows-manager").enhanceWithin(); } catch (e) {}
});
{% endblock %}
"""

# Use /dev/shm if available to avoid SD card wear and IO errors
if os.path.exists('/dev/shm'):
    WINDOWS = '/dev/shm/pwnagotchi/Windows.png'
else:
    WINDOWS = '/var/tmp/pwnagotchi/Windows.png'

class Window:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Window, cls).__new__(cls)
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
        self.active_aux_plugin = None
        if config: self.screen_data = config
        else: self.screen_data = {}
        self.set_mode(mode, sub_mode)

    def _start_loop(self):
        logging.info("[Windows] Starting the asyncio event loop in a new thread.")
        asyncio.set_event_loop(self.loop)
        self.is_running_event.set()
        try:
            self.loop.run_until_complete(self.screen_controller())
        except asyncio.CancelledError:
            pass
        except RuntimeError as ex:
            logging.debug("[Windows] Display controller loop stopped: %s", ex)
        finally:
            self.loop.close()
            self.is_running_event.clear()

    def start(self, res, rot, col):
        logging.debug("[Windows] Starting display controller.")
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
        loop = self.loop
        thread = self.thread
        if loop and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(lambda: None)
            except RuntimeError:
                pass
        if thread and threading.current_thread() is not thread:
            thread.join(timeout=2.0)
            if thread.is_alive():
                logging.warning("[Windows] Display controller thread did not stop cleanly; forcing loop stop.")
                if loop and not loop.is_closed():
                    try:
                        loop.call_soon_threadsafe(loop.stop)
                    except RuntimeError:
                        pass
                thread.join(timeout=1.0)
                if thread.is_alive():
                    logging.warning("[Windows] Display controller thread is still alive after forced stop.")
        self.loop = None
        self.thread = None
        self.is_running_event.clear()
        logging.debug("[Windows] Display controller stopped.")

    async def screen_controller(self):
        self.running = True
        try:
            await self.render_loop()
        finally:
            self.is_running_event.clear()

    def is_running(self):
        if self.is_running_event is not None:
            return self.is_running_event.is_set()
        logging.error("[Windows] is_running_event is not initialized.")
        return False

    def cleanup(self):
        logging.debug("[Windows] Cleaning up the Window resources.")
        self.task = None
        if self.loop is not None:
            if not self.loop.is_closed():
                logging.debug("[Windows] Closing event loop.")
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

    async def render_loop(self):
        try:
            refresh_interval = 1
            iteration = 0
            while self.running:
                delay = 1.0 / max(1, int(self.fps or 1))
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

                    canvas.save(WINDOWS)
                    if self.running and self.enabled and self.displayImpl is not None:
                        canvas = canvas.resize((self._res[0], self._res[1])).convert(self._col)
                        self.displayImpl.render(canvas)
                else:
                    logging.warning("[Windows] No image to display.")
                
                await asyncio.sleep(delay)
                iteration += 1

        except asyncio.CancelledError:
            logging.warning("[Windows] render loop cancelled.")
        except Exception as ex:
            logging.error("[Windows] render loop error: %s", ex)
            logging.error(traceback.format_exc())
            self.running = False
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
            logging.error(f'[Windows] KeyError while display hijacking: {e}')
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

    def set_mode(self, mode, sub_mode=None, config=None):
        if mode in self.modes:
            logging.debug(f"[Windows] Switching to mode: {mode}")
            self.current_mode = mode
            self.screen_data = copy.deepcopy(config or {})
            if mode == "screen_saver":
                self.set_screen_saver_mode(sub_mode)
            elif mode == "auxiliary":
                pass
            elif mode == "terminal":
                pass
        else:
            logging.warning(f"[Windows] Invalid mode: {mode}. Available modes are: {self.modes}")
    
    def switch_mode(self, direction='next'):
        current_index = self.modes.index(self.current_mode)
        sub_mode = None
        if direction == 'next':
            next_index = (current_index + 1) % len(self.modes)
        elif direction == 'previous':
            next_index = (current_index - 1) % len(self.modes)
        else:
            logging.warning(f"[Windows] Invalid direction: {direction}. Using 'next' as default.")
            next_index = (current_index + 1) % len(self.modes)
        
        next_mode = self.modes[next_index]
        
        logging.debug(f"[Windows] Switching to the {direction} mode: {next_mode}")
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
            logging.debug(f"[Windows] Switching screen_saver to: {sub_mode}")
            self.current_screen_saver = sub_mode
            base = copy.deepcopy(self.screen_data or {})
            if sub_mode == 'show_logo':
                options = {k: v for k, v in base.items() if k in ()}
            elif sub_mode == 'moving_shapes':
                options = {
                    "shape_type": "text", 
                    "text": base.get("text", "Windows"), 
                    "font_path": base.get("font_path", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), 
                    "color": base.get("color", "red"), 
                    "speed": base.get("speed", 10), 
                    "font_size": base.get("font_size", 15),
                }
            elif sub_mode == 'random_colors':
                options = {
                    "speed": base.get("speed", 1),
                }
            elif sub_mode == 'hyper_drive':
                num_stars = int(base.get("star_count", base.get("stars_count", 100)) or 100)
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
                    'speed': base.get("speed", 1.0),
                    'star_count': num_stars,
                }
            elif sub_mode == 'show_animation':
                options = {
                    'frames_path': base.get('frames_path') or os.path.join(self.th_path, 'img', 'boot'),
                    'max_loops': base.get('max_loops', 1),
                    'total_duration': base.get('total_duration', 10),
                }
            self.screen_data = options
        else:
            logging.warning(f"[Windows] Invalid screen_saver sub-mode: {sub_mode}. Available sub-modes are: {self.screen_saver_modes}")

    
    def switch_screen_saver_submode(self, direction='next'):
        if self.current_mode != 'screen_saver':
            logging.warning(f"[Windows] Not in screen_saver mode. Current mode is: {self.current_mode}")
            return self.current_mode
        
        current_index = self.screen_saver_modes.index(self.current_screen_saver)
        
        if direction == 'next':
            next_index = (current_index + 1) % len(self.screen_saver_modes) 
        elif direction == 'previous':
            next_index = (current_index - 1) % len(self.screen_saver_modes)  
        else:
            logging.error(f"[Windows] Invalid direction: {direction}. Must be 'next' or 'previous'.")
            return self.current_mode
        
        next_submode = self.screen_saver_modes[next_index]
        logging.warning(f"[Windows] Switching to the {direction} screen_saver sub-mode: {next_submode}")
        self.set_screen_saver_mode(next_submode)
        return next_submode

    def get_mode_image(self):
        logging.debug(f"[Windows] Getting mode image: {self.current_mode}")
        if self.current_mode == 'screen_saver':
            return self.get_screen_saver_image()
        elif self.current_mode == 'auxiliary':
            return self.auxiliary_image()
        elif self.current_mode == 'terminal':
            return self.terminal_mode()
        else:
            logging.warning(f"[Windows] Unknown mode: {self.current_mode}. Falling back to default.")
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
            logging.warning(f"[Windows] Unknown screen_saver sub-mode: {self.current_screen_saver}.")
            self.current_screen_saver = 'show_logo'
            return self.show_logo() 


    def get_aux_plugins(self):
        return sorted([name for name, plugin in plugins.loaded.items() if hasattr(plugin, 'on_aux')])

    def switch_aux(self, direction='next'):
        aux_list = self.get_aux_plugins()
        if not aux_list:
            return None
        
        if self.active_aux_plugin not in aux_list:
            self.active_aux_plugin = aux_list[0]
            return self.active_aux_plugin

        idx = aux_list.index(self.active_aux_plugin)
        if direction == 'next':
            idx = (idx + 1) % len(aux_list)
        else:
            idx = (idx - 1) % len(aux_list)
        
        self.active_aux_plugin = aux_list[idx]
        return self.active_aux_plugin

    def auxiliary_image(self):
        aux_list = self.get_aux_plugins()
        if not aux_list:
            image = self.show_logo()
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
            text = "No Aux Source"
            text_color = (255, 0, 0) 
            image_width, image_height = image.size
            try:
                text_width, text_height = draw.textsize(text, font)
            except:
                _, _, text_width, text_height = draw.textbbox((0, 0),text, font)
            position = ((image_width - text_width) // 2, 10)
            draw.text(position, text, font=font, fill=text_color)
            return image
        
        if self.active_aux_plugin not in aux_list:
            self.active_aux_plugin = aux_list[0]

        try:
            plugin = plugins.loaded[self.active_aux_plugin]
            aux_context = {
                "active": True,
                "plugin": self.active_aux_plugin,
                "mode": self.current_mode,
                "width": self._res[0],
                "height": self._res[1],
                "rotation": self._rot,
                "color": self._col,
                "fps": self.fps,
                "timestamp": time.time(),
            }
            try:
                content = plugin.on_aux(aux_context)
            except TypeError:
                content = plugin.on_aux()
            if isinstance(content, dict):
                content = content.get("image")
            if isinstance(content, str):
                if os.path.exists(content):
                    with Image.open(content) as img:
                        return img.copy()
            elif isinstance(content, Image.Image):
                return content
        except Exception as e:
            logging.error(f"[Windows] Error in on_aux for {self.active_aux_plugin}: {e}")
        
        return self.show_logo()

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
            logging.debug(f'[Windows] KeyError while showing logo: {e}')
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
            logging.error(f'[Windows] KeyError while moving shapes: {e}')
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
                logging.error("[Windows] screen_data is None. Unable to show animation screen saver.")
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
                logging.error("[Windows] No valid frames found in the specified directory")
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
                
                logging.debug(f"[Windows] Extracted {len(self.animation_state['extracted_frames'])} frames")

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
            logging.error(f"[Windows] Error in show_animation_screen_saver: {ex}")
            logging.error(traceback.format_exc())
            return None

class Windows(plugins.Plugin):
    __author__ = 'V0rT3x'
    __github__ = 'https://github.com/V0r-T3x/'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Standalone Second Screen & Display Hijacker'
    DEFAULT_OPTIONS = {
        'fps': 24,
        'rotation': 0,
        'default_mode': 'screen_saver',
        'default_screen_saver': 'show_logo',
        'default_aux_plugin': '',
        'animation_frames_path': '',
        'animation_max_loops': 1,
        'animation_total_duration': 10,
        'moving_shapes_text': 'Windows',
        'moving_shapes_color': 'red',
        'moving_shapes_speed': 10,
        'moving_shapes_font_size': 15,
        'moving_shapes_font_path': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        'random_colors_speed': 1,
        'hyper_drive_stars': 100,
        'hyper_drive_speed': 1.0,
    }

    def __init__(self):
        self._config = pwnagotchi.config
        self.second_screen = Image.new('RGBA', (1,1), 'black')
        self.screen_modes = ['screen_saver', 'auxiliary', 'terminal']
        self.screen_saver_modes = ['show_logo', 'moving_shapes', 'random_colors', 'hyper_drive', 'show_animation']
        self.dispHijack = False
        self.loop = None
        self.render_thread = None
        self._stop_event = threading.Event()
        self._agent = None
        self.ready = False
        self._pwny_root = os.path.dirname(pwnagotchi.__file__)
        self._plug_root = os.path.dirname(os.path.realpath(__file__))
        self.display_controller = None
        self._pending_restore_pwny = False
        if not isinstance(getattr(self, 'options', None), dict):
            self.options = copy.deepcopy(
                self._config.get('main', {}).get('plugins', {}).get('windows', {})
            ) if isinstance(self._config, dict) else {}
        for key, value in self.DEFAULT_OPTIONS.items():
            self.options.setdefault(key, value)
        self.default_mode = self._valid_mode(self.options.get('default_mode'), 'screen_saver')
        self.default_screen_saver = self._valid_screen_saver(self.options.get('default_screen_saver'), 'show_logo')
        self.default_aux_plugin = str(self.options.get('default_aux_plugin') or '')
        self.current_mode = self.default_mode
        self.current_screen_saver = self.default_screen_saver
        self.current_aux_plugin = self.default_aux_plugin or None
        self.runtime_config = {}
        self.display_config = {}
        self._sync_display_config_from_runtime()
        self.fps = self._sanitize_int(self.options.get('fps'), 24, minimum=1)
        self._th_path = ''
        self._res = [128, 64]
        self._color_mode = ['P', 'P']
        if not os.path.exists(os.path.dirname(WINDOWS)):
            os.makedirs(os.path.dirname(WINDOWS))

        if self.fps_check(): rst = 1
        self.check_and_fix_fb()

    def on_v0rt3x_actions(self):
        actions = {
            "windows.status": ("status", "Windows status"),
            "windows.second_screen": ("second_screen", "Toggle second screen"),
            "windows.display_pwny": ("display_pwny", "Display pwny"),
            "windows.display_hijack": ("display_hijack", "Display hijack"),
            "windows.display_next": ("display_next", "Next display"),
            "windows.display_previous": ("display_previous", "Previous display"),
            "windows.screen_saver_start": ("screen_saver_start", "Start screen saver"),
            "windows.screen_saver_stop": ("screen_saver_stop", "Stop screen saver"),
            "windows.screen_saver_next": ("screen_saver_next", "Next screen saver"),
            "windows.screen_saver_previous": ("screen_saver_previous", "Previous screen saver"),
            "windows.aux_next": ("aux_next", "Next auxiliary"),
            "windows.aux_prev": ("aux_prev", "Previous auxiliary"),
            "windows.reset_runtime_defaults": ("reset_runtime_defaults", "Reset runtime defaults"),
            "windows.set_mode:screen_saver": ("set_mode:screen_saver", "Set screen saver mode"),
            "windows.set_mode:auxiliary": ("set_mode:auxiliary", "Set auxiliary mode"),
            "windows.set_mode:terminal": ("set_mode:terminal", "Set terminal mode"),
        }
        return {
            action_id: {
                "label": label,
                "plugin": "windows",
                "cmd": cmd,
                "category": "windows",
                "risk": "safe",
            }
            for action_id, (cmd, label) in actions.items()
        }

    def on_v0rt3x_contexts(self):
        return {
            "windows_second_screen": {
                "label": "Windows second screen active",
                "priority": 70,
                "owner": "windows",
            },
            "windows_saver": {
                "label": "Windows screen saver active",
                "priority": 80,
                "owner": "windows",
            },
            "windows_aux": {
                "label": "Windows auxiliary active",
                "priority": 75,
                "owner": "windows",
            },
        }

    def _pwnctl(self):
        return plugins.loaded.get("pwnctl")

    def _emit_pwnctl_event(self, event, context=None, payload=None):
        try:
            pwnctl = self._pwnctl()
            if pwnctl and hasattr(pwnctl, "emit_event"):
                pwnctl.emit_event("windows", event, context=context, payload=payload or {})
        except Exception as e:
            logging.debug(f"[Windows] pwnctl event emit failed: {e}")

    def _claim_pwnctl_context(self, context_id, priority=None, payload=None):
        try:
            pwnctl = self._pwnctl()
            if pwnctl and hasattr(pwnctl, "claim_context"):
                pwnctl.claim_context("windows", context_id, priority=priority, payload=payload or self.status_payload())
        except Exception as e:
            logging.debug(f"[Windows] pwnctl context claim failed: {e}")

    def _release_pwnctl_context(self, context_id):
        try:
            pwnctl = self._pwnctl()
            if pwnctl and hasattr(pwnctl, "release_context"):
                pwnctl.release_context("windows", context_id)
        except Exception as e:
            logging.debug(f"[Windows] pwnctl context release failed: {e}")

    def _sync_pwnctl_contexts(self, reason="sync"):
        try:
            context = None
            payload = {
                "reason": reason,
                "dispHijack": bool(self.dispHijack),
                "current_mode": self.current_mode,
                "current_screen_saver": self.current_screen_saver,
                "current_aux_plugin": self.current_aux_plugin,
            }
            if self.dispHijack:
                self._claim_pwnctl_context("windows_second_screen", priority=70, payload=payload)
            else:
                self._release_pwnctl_context("windows_second_screen")
                self._release_pwnctl_context("windows_saver")
                self._release_pwnctl_context("windows_aux")
                self._emit_pwnctl_event("context_sync", context=None, payload=payload)
                return

            if self.current_mode == "screen_saver":
                context = "windows_saver"
                self._claim_pwnctl_context("windows_saver", priority=80, payload=payload)
                self._release_pwnctl_context("windows_aux")
            elif self.current_mode == "auxiliary":
                context = "windows_aux"
                self._claim_pwnctl_context("windows_aux", priority=75, payload=payload)
                self._release_pwnctl_context("windows_saver")
            else:
                self._release_pwnctl_context("windows_saver")
                self._release_pwnctl_context("windows_aux")
            self._emit_pwnctl_event("context_sync", context=context, payload=payload)
        except Exception as e:
            logging.debug(f"[Windows] pwnctl context sync failed: {e}")

    def _sanitize_int(self, value, default, minimum=None):
        try:
            value = int(value)
        except Exception:
            value = default
        if minimum is not None:
            value = max(minimum, value)
        return value

    def _sanitize_float(self, value, default, minimum=None):
        try:
            value = float(value)
        except Exception:
            value = default
        if minimum is not None:
            value = max(minimum, value)
        return value

    def _valid_mode(self, mode, default=None):
        mode = str(mode or '').strip()
        return mode if mode in self.screen_modes else (default or self.screen_modes[0])

    def _valid_screen_saver(self, sub_mode, default=None):
        sub_mode = str(sub_mode or '').strip()
        return sub_mode if sub_mode in self.screen_saver_modes else (default or self.screen_saver_modes[0])

    def get_aux_plugins(self):
        if getattr(self, 'display_controller', None) and hasattr(self.display_controller, 'get_aux_plugins'):
            try:
                return self.display_controller.get_aux_plugins()
            except Exception:
                pass
        return sorted([name for name, plugin in plugins.loaded.items() if hasattr(plugin, 'on_aux')])

    def _valid_aux_plugin(self, plugin_name, default=''):
        plugin_name = str(plugin_name or '').strip()
        if not plugin_name:
            return default
        return plugin_name if plugin_name in self.get_aux_plugins() else default

    def _sync_display_config_from_runtime(self):
        self.display_config['mode'] = self.current_mode
        self.display_config['sub_mode'] = self.current_screen_saver
        self.display_config['config'] = copy.deepcopy(self.runtime_config)

    def _apply_runtime_state(self, mode=None, sub_mode=None, aux_plugin=None, config=None):
        if mode is not None:
            self.current_mode = self._valid_mode(mode, self.current_mode)
        if sub_mode is not None:
            self.current_screen_saver = self._valid_screen_saver(sub_mode, self.current_screen_saver)
        if aux_plugin is not None:
            self.current_aux_plugin = self._valid_aux_plugin(aux_plugin, '') or None
        if config is not None:
            self.runtime_config = copy.deepcopy(config or {})
        self._sync_display_config_from_runtime()
        controller = getattr(self, 'display_controller', None)
        if controller is not None:
            if self.current_aux_plugin and hasattr(controller, 'active_aux_plugin'):
                controller.active_aux_plugin = self.current_aux_plugin
            controller.set_mode(
                self.current_mode,
                self.current_screen_saver if self.current_mode == 'screen_saver' else None,
                self.runtime_config,
            )
        self._sync_pwnctl_contexts(reason="apply_runtime_state")
        return self.status_payload()

    def _apply_defaults_from_options(self):
        for key, value in self.DEFAULT_OPTIONS.items():
            self.options.setdefault(key, value)
        self.default_mode = self._valid_mode(self.options.get('default_mode'), 'screen_saver')
        self.default_screen_saver = self._valid_screen_saver(self.options.get('default_screen_saver'), 'show_logo')
        self.default_aux_plugin = str(self.options.get('default_aux_plugin') or '')
        self.fps = self._sanitize_int(self.options.get('fps'), self.DEFAULT_OPTIONS['fps'], minimum=1)

    def _safe_options(self):
        return {key: copy.deepcopy(self.options.get(key, default)) for key, default in self.DEFAULT_OPTIONS.items()}

    def build_screen_saver_config(self, sub_mode=None, overrides=None):
        sub_mode = self._valid_screen_saver(sub_mode or self.current_screen_saver or self.default_screen_saver, 'show_logo')
        if sub_mode == 'moving_shapes':
            config = {
                'shape_type': 'text',
                'text': self.options.get('moving_shapes_text', 'Windows'),
                'font_path': self.options.get('moving_shapes_font_path', self.DEFAULT_OPTIONS['moving_shapes_font_path']),
                'color': self.options.get('moving_shapes_color', 'red'),
                'speed': self._sanitize_int(self.options.get('moving_shapes_speed'), 10, minimum=1),
                'font_size': self._sanitize_int(self.options.get('moving_shapes_font_size'), 15, minimum=1),
            }
        elif sub_mode == 'random_colors':
            config = {'speed': self._sanitize_int(self.options.get('random_colors_speed'), 1, minimum=1)}
        elif sub_mode == 'hyper_drive':
            count = self._sanitize_int(self.options.get('hyper_drive_stars'), 100, minimum=1)
            config = {
                'stars': [
                    {
                        'position': [random.randint(-self._res[0]//2, self._res[0]//2), random.randint(-self._res[1]//2, self._res[1]//2)],
                        'velocity': random.uniform(2, 5),
                        'size': random.uniform(1, 3),
                        'streak_length': random.uniform(5, 20),
                        'color': 'white',
                    } for _ in range(count)
                ],
                'speed': self._sanitize_float(self.options.get('hyper_drive_speed'), 1.0, minimum=0.1),
                'star_count': count,
            }
        elif sub_mode == 'show_animation':
            config = {
                'frames_path': self.options.get('animation_frames_path') or os.path.join(self._th_path, 'img', 'boot'),
                'max_loops': self._sanitize_int(self.options.get('animation_max_loops'), 1, minimum=1),
                'total_duration': self._sanitize_int(self.options.get('animation_total_duration'), 10, minimum=1),
            }
        else:
            config = {}
        if overrides:
            config.update(copy.deepcopy(overrides))
        return config

    def reset_runtime_to_defaults(self):
        self._apply_defaults_from_options()
        config = self.build_screen_saver_config(self.default_screen_saver) if self.default_mode == 'screen_saver' else {}
        payload = self._apply_runtime_state(
            mode=self.default_mode,
            sub_mode=self.default_screen_saver,
            aux_plugin=self.default_aux_plugin,
            config=config,
        )
        self._sync_pwnctl_contexts(reason="reset_runtime_to_defaults")
        return payload

    def set_display_mode(self, mode, apply_now=True):
        mode = self._valid_mode(mode, self.current_mode)
        if apply_now:
            config = self.build_screen_saver_config(self.current_screen_saver) if mode == 'screen_saver' else {}
            payload = self._apply_runtime_state(mode=mode, config=config)
            self._sync_pwnctl_contexts(reason="set_display_mode")
            return payload
        self._sync_pwnctl_contexts(reason="set_display_mode")
        return self.status_payload()

    def set_screen_saver(self, sub_mode, apply_now=True, options_patch=None):
        sub_mode = self._valid_screen_saver(sub_mode, self.current_screen_saver)
        if apply_now:
            payload = self._apply_runtime_state(
                mode='screen_saver',
                sub_mode=sub_mode,
                config=self.build_screen_saver_config(sub_mode, options_patch),
            )
            self._emit_pwnctl_event("screen_saver_set", context="windows_saver", payload={"sub_mode": sub_mode})
            self._sync_pwnctl_contexts(reason="set_screen_saver")
            return payload
        self._emit_pwnctl_event("screen_saver_set", context="windows_saver", payload={"sub_mode": sub_mode})
        self._sync_pwnctl_contexts(reason="set_screen_saver")
        return self.status_payload()

    def set_aux_plugin(self, plugin_name, apply_now=True):
        plugin_name = self._valid_aux_plugin(plugin_name, '')
        if apply_now:
            payload = self._apply_runtime_state(mode='auxiliary', aux_plugin=plugin_name, config={})
            self._emit_pwnctl_event("aux_set", context="windows_aux", payload={"plugin": plugin_name})
            self._sync_pwnctl_contexts(reason="set_aux_plugin")
            return payload
        self._emit_pwnctl_event("aux_set", context="windows_aux", payload={"plugin": plugin_name})
        self._sync_pwnctl_contexts(reason="set_aux_plugin")
        return self.status_payload()

    def set_fps(self, fps, apply_now=True):
        self.fps = self._sanitize_int(fps, self.fps, minimum=1)
        controller = getattr(self, 'display_controller', None)
        if apply_now and controller is not None:
            controller.fps = self.fps
        return self.status_payload()

    def apply_display_config(self, mode=None, sub_mode=None, config=None):
        if sub_mode is not None:
            config = self.build_screen_saver_config(sub_mode, config)
        elif mode is not None:
            mode = self._valid_mode(mode, self.current_mode)
            if mode == 'screen_saver':
                config = self.build_screen_saver_config(self.current_screen_saver, config)
            elif config is None:
                config = {}
        return self._apply_runtime_state(mode=mode, sub_mode=sub_mode, config=config)

    def save_defaults(self, patch, apply_now=False):
        clean = self._save_plugin_options(patch)
        if apply_now:
            return self.reset_runtime_to_defaults()
        payload = self.status_payload()
        payload['saved'] = clean
        return payload

    def _plugin_config(self):
        try:
            with open('/etc/pwnagotchi/config.toml', 'r', encoding='utf-8') as f:
                config = toml.load(f)
        except Exception:
            config = copy.deepcopy(self._config) if isinstance(self._config, dict) else {}
        config.setdefault('main', {}).setdefault('plugins', {}).setdefault('windows', {})
        return config

    def _save_plugin_options(self, patch):
        config = self._plugin_config()
        plugin_cfg = config['main']['plugins']['windows']
        clean = {}
        for key, value in (patch or {}).items():
            if key in self.DEFAULT_OPTIONS:
                clean[key] = value
        plugin_cfg.update(clean)
        save_config(config, '/etc/pwnagotchi/config.toml')
        self.options.update(clean)
        self._apply_defaults_from_options()
        return clean

    def status_payload(self):
        controller = getattr(self, 'display_controller', None)
        controller_running = False
        if controller is not None:
            try:
                controller_running = bool(controller.is_running())
            except Exception:
                controller_running = True
        return {
            'ready': bool(self.ready),
            'dispHijack': bool(self.dispHijack),
            'current_mode': self.current_mode,
            'current_screen_saver': self.current_screen_saver,
            'current_aux_plugin': self.current_aux_plugin,
            'runtime_config': copy.deepcopy(self.runtime_config),
            'mode': self.display_config.get('mode', self.current_mode),
            'sub_mode': self.display_config.get('sub_mode', self.current_screen_saver),
            'default_mode': self.default_mode,
            'default_screen_saver': self.default_screen_saver,
            'default_aux_plugin': self.default_aux_plugin,
            'options': self._safe_options(),
            'screen_modes': list(self.screen_modes),
            'screen_saver_modes': list(self.screen_saver_modes),
            'aux_plugins': self.get_aux_plugins(),
            'fps': self.fps,
            'rotation': self.options.get('rotation', 0),
            'controller_running': controller_running,
            'controller_present': controller is not None,
            'pending_restore_pwny': bool(self._pending_restore_pwny),
            'windows_image_path': WINDOWS,
        }

    def config_payload(self):
        return {
            'defaults': self._safe_options(),
            'runtime': {
                'current_mode': self.current_mode,
                'current_screen_saver': self.current_screen_saver,
                'current_aux_plugin': self.current_aux_plugin,
                'runtime_config': copy.deepcopy(self.runtime_config),
            },
            'capabilities': {
                'screen_modes': list(self.screen_modes),
                'screen_saver_modes': list(self.screen_saver_modes),
                'aux_plugins': self.get_aux_plugins(),
            },
        }

    def enable_second_screen(self):
        self.dispHijack = True
        self._pending_restore_pwny = False
        self._emit_pwnctl_event("second_screen_enabled", context="windows_second_screen", payload=self.status_payload())
        self._sync_pwnctl_contexts(reason="enable_second_screen")
        return self.status_payload()

    def disable_second_screen(self):
        self.dispHijack = False
        self._pending_restore_pwny = True
        controller = getattr(self, 'display_controller', None)
        if controller is not None:
            try:
                controller.stop()
            except Exception:
                logging.debug("[Windows] display controller stop failed", exc_info=True)
            self.display_controller = None
        self._sync_pwnctl_contexts(reason="disable_second_screen")
        self._emit_pwnctl_event("second_screen_disabled", context="windows_second_screen", payload=self.status_payload())
        return self.status_payload()

    def toggle_second_screen(self):
        payload = self.disable_second_screen() if self.dispHijack else self.enable_second_screen()
        self._sync_pwnctl_contexts(reason="toggle_second_screen")
        return payload

    def _restore_pwny_display(self, ui=None, reason="manual"):
        self.dispHijack = False
        controller = getattr(self, 'display_controller', None)
        if controller is not None:
            try:
                controller.stop()
            except Exception:
                logging.debug("[Windows] display controller stop failed during restore", exc_info=True)
            self.display_controller = None
        if ui is not None:
            try:
                image = Image.new('RGBA', (ui._width, ui._height), 'black')
                image.save(WINDOWS)
            except Exception:
                pass
            if hasattr(ui, '_enabled') and not ui._enabled:
                ui._enabled = True
            if self._config['ui']['display']['enabled']:
                try:
                    ui.init_display()
                except Exception:
                    logging.debug("[Windows] normal display init failed during restore", exc_info=True)
                try:
                    ui.update(force=True)
                except TypeError:
                    try:
                        ui.update()
                    except Exception:
                        pass
                except Exception:
                    pass
        self._pending_restore_pwny = False
        logging.info("[Windows] Restored normal display (%s)", reason)
        self._sync_pwnctl_contexts(reason="_restore_pwny_display")
        return self.status_payload()

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
        self._apply_defaults_from_options()
        self.reset_runtime_to_defaults()
        self.ready = True
        self._sync_pwnctl_contexts(reason="on_loaded")
        try:
            pwnctl = self._pwnctl()
            if pwnctl and hasattr(pwnctl, "refresh_registry"):
                pwnctl.refresh_registry()
        except Exception as e:
            logging.debug(f"[Windows] pwnctl registry refresh failed: {e}")

    def on_unload(self, ui):
        with ui._lock:
            self._restore_pwny_display(ui, reason="unload")
            self.cleanup_display()

        logging.info('[Windows] Unloaded')

    def cleanup_display(self):
        if hasattr(self, 'display_controller') and self.display_controller:
            if self.display_controller.is_running():
                self.display_controller.stop()
            self.display_controller = None

    def on_ui_update(self, ui):
        try:
            if not self.dispHijack:
                if self._pending_restore_pwny or getattr(ui, '_enabled', True) is False or getattr(self, 'display_controller', None):
                    self._restore_pwny_display(ui, reason="handoff")
                return

            if getattr(ui, '_enabled', True):
                ui._enabled = False
            if not getattr(self, 'display_controller', None):
                try:
                    logging.info("[Windows] Starting display hijack.")
                    self.display_controller = Window(self._config['ui']['display']['enabled'], self.fps, self._th_path)
                    self.display_controller.start(self._res, self.options.get('rotation', 0), self._color_mode[1])
                    self.display_controller.set_mode(
                        self.current_mode,
                        self.current_screen_saver if self.current_mode == 'screen_saver' else None,
                        self.runtime_config,
                    )
                    if self.current_aux_plugin and hasattr(self.display_controller, 'active_aux_plugin'):
                        self.display_controller.active_aux_plugin = self.current_aux_plugin
                except Exception:
                    logging.error("[Windows] Failed to start display hijack.")
                    logging.error(traceback.format_exc())
                    self.dispHijack = False
                    self._pending_restore_pwny = True
                    self._restore_pwny_display(ui, reason="hijack_start_failed")

        except Exception as e:
            logging.info("non fatal error while updating Windows: %s" % e)
            logging.info(traceback.format_exc())
            if self.dispHijack and not getattr(self, 'display_controller', None):
                self.dispHijack = False
                self._pending_restore_pwny = True
                self._restore_pwny_display(ui, reason="ui_update_error")

    def process_actions(self, command):
        if command is None:
            logging.error("[Windows] Action is None, unable to process.")
            return
        try:
            action = command.get('action')
            mode = command.get('mode', 'manu')
            logging.info(f'Action: {action}')
            if action == 'switch_screen_mode':
                try:
                    mode = self.display_controller.switch_mode()
                except:
                    mode = self.screen_modes[(self.screen_modes.index(self.current_mode) + 1) % len(self.screen_modes)]
                self._apply_runtime_state(mode=mode)
            elif action == 'switch_screen_mode_reverse':
                try:
                    mode = self.display_controller.switch_mode('previous')
                except:
                    mode = self.screen_modes[(self.screen_modes.index(self.current_mode) - 1) % len(self.screen_modes)]
                self._apply_runtime_state(mode=mode)
            elif action == 'enable_second_screen':
                self.enable_second_screen()
            elif action == 'disable_second_screen':
                logging.info('disable second screen')
                self.disable_second_screen()
            elif action == 'next_screen_saver':
                logging.info('next screen saver')
                try:
                    sub_mode = self.display_controller.switch_screen_saver_submode('next')
                except:
                    sub_mode = self.screen_saver_modes[(self.screen_saver_modes.index(self.current_screen_saver) + 1) % len(self.screen_saver_modes)]
                self.set_screen_saver(sub_mode, apply_now=True)
            elif action == 'previous_screen_saver':
                logging.info('previous screen saver')
                try:
                    sub_mode = self.display_controller.switch_screen_saver_submode('previous')
                except:
                    sub_mode = self.screen_saver_modes[(self.screen_saver_modes.index(self.current_screen_saver) - 1) % len(self.screen_saver_modes)]
                self.set_screen_saver(sub_mode, apply_now=True)
            elif action == 'next_aux':
                logging.info('next aux')
                try:
                    aux = self.display_controller.switch_aux('next')
                except Exception as e:
                    logging.error(f"Error switching aux: {e}")
                    aux_list = self.get_aux_plugins()
                    aux = aux_list[0] if aux_list else ''
                self.set_aux_plugin(aux, apply_now=True)
            elif action == 'previous_aux':
                logging.info('previous aux')
                try:
                    aux = self.display_controller.switch_aux('previous')
                except Exception as e:
                    logging.error(f"Error switching aux: {e}")
                    aux_list = self.get_aux_plugins()
                    aux = aux_list[-1] if aux_list else ''
                self.set_aux_plugin(aux, apply_now=True)
            self._sync_pwnctl_contexts(reason="process_actions")
            self._emit_pwnctl_event("action_processed", payload={
                "action": action,
                "mode": mode,
                "dispHijack": bool(self.dispHijack),
                "current_mode": self.current_mode,
                "current_screen_saver": self.current_screen_saver,
                "current_aux_plugin": self.current_aux_plugin,
            })

        except Exception as e:
            logging.error(f'error while processing menu command: {e}')

    def start_screen_saver(self, sub_mode=None, config=None):
        previous = {
            'dispHijack': bool(self.dispHijack),
            'current_mode': self.current_mode,
            'current_screen_saver': self.current_screen_saver,
            'current_aux_plugin': self.current_aux_plugin,
            'runtime_config': copy.deepcopy(self.runtime_config),
            'display_config': copy.deepcopy(self.display_config),
        }
        chosen_sub_mode = self._valid_screen_saver(
            sub_mode or self.default_screen_saver or self.current_screen_saver or 'show_logo',
            'show_logo',
        )
        runtime_config = self.build_screen_saver_config(chosen_sub_mode, config)
        self.dispHijack = True
        self._pending_restore_pwny = False
        self._apply_runtime_state(mode='screen_saver', sub_mode=chosen_sub_mode, config=runtime_config)
        self._sync_pwnctl_contexts(reason="start_screen_saver")
        logging.info("[Windows] Screen saver started")
        return previous

    def stop_screen_saver(self, previous=None):
        if previous and isinstance(previous, dict):
            self.dispHijack = bool(previous.get('dispHijack', False))
            self.current_mode = self._valid_mode(previous.get('current_mode'), self.default_mode)
            self.current_screen_saver = self._valid_screen_saver(previous.get('current_screen_saver'), self.default_screen_saver)
            self.current_aux_plugin = previous.get('current_aux_plugin', self.default_aux_plugin or None)
            self.runtime_config = copy.deepcopy(previous.get('runtime_config', {}))
            self._sync_display_config_from_runtime()
            if self.dispHijack:
                self._pending_restore_pwny = False
            else:
                self.disable_second_screen()
            if self.dispHijack and getattr(self, 'display_controller', None):
                if self.current_aux_plugin and hasattr(self.display_controller, 'active_aux_plugin'):
                    self.display_controller.active_aux_plugin = self.current_aux_plugin
                self.display_controller.set_mode(
                    self.current_mode,
                    self.current_screen_saver if self.current_mode == 'screen_saver' else None,
                    self.runtime_config,
                )
        else:
            self.disable_second_screen()
        self._sync_pwnctl_contexts(reason="stop_screen_saver")
        logging.info("[Windows] Screen saver stopped")
        return True

    def ui2(self):
        try:
            if os.path.exists(WINDOWS):
                return send_file(WINDOWS, mimetype='image/png')
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

    def on_pwnctl(self, cmd):
        if cmd == 'help':
            return "Windows commands: status, second_screen, display_pwny, display_next, display_previous, screen_saver_next, screen_saver_previous, screen_saver_start, screen_saver_stop, aux_next, aux_prev, set_mode:<mode>, set_saver:<sub_mode>, set_aux:<plugin>, reset_runtime_defaults"
        if cmd == 'status':
            return json.dumps(self.status_payload())
        if cmd and cmd.startswith('set_mode:'):
            self.set_display_mode(cmd.split(':', 1)[1], apply_now=True)
            return "OK"
        if cmd and cmd.startswith('set_saver:'):
            self.set_screen_saver(cmd.split(':', 1)[1], apply_now=True)
            return "OK"
        if cmd and cmd.startswith('set_aux:'):
            self.set_aux_plugin(cmd.split(':', 1)[1], apply_now=True)
            return "OK"
        if cmd == 'reset_runtime_defaults':
            self.reset_runtime_to_defaults()
            return "OK"
        
        if cmd == 'second_screen':
             self.toggle_second_screen()
             return "Second screen toggled"
        elif cmd == 'display_pwny':
             self.disable_second_screen()
             return "Pwny screen enabled"
        elif cmd == 'display_hijack':
             self.enable_second_screen()
             return "Second screen enabled"
        elif cmd == 'screen_saver_start':
             self.start_screen_saver()
             return "Screen saver started"
        elif cmd == 'screen_saver_stop':
             self.stop_screen_saver()
             return "Screen saver stopped"
        
        action_map = {
            'display_next': 'switch_screen_mode',
            'display_previous': 'switch_screen_mode_reverse',
            'screen_saver_next': 'next_screen_saver',
            'screen_saver_previous': 'previous_screen_saver',
            'aux_next': 'next_aux',
            'aux_prev': 'previous_aux'
        }
        
        if cmd in action_map:
            self.process_actions({'action': action_map[cmd]})
            return "OK"
            
        return "Unknown command"

    def on_menu(self):
        return {
            'Windows': [
                ("Second Screen", {"action": "pwnctl", "plugin": "windows", "cmd": "second_screen"}),
                ("Pwny Screen", {"action": "pwnctl", "plugin": "windows", "cmd": "display_pwny"}),
                ("Next Mode", {"action": "pwnctl", "plugin": "windows", "cmd": "display_next"}),
                ("Prev Mode", {"action": "pwnctl", "plugin": "windows", "cmd": "display_previous"}),
                ("Next Saver", {"action": "pwnctl", "plugin": "windows", "cmd": "screen_saver_next"}),
                ("Prev Saver", {"action": "pwnctl", "plugin": "windows", "cmd": "screen_saver_previous"}),
                ("Start Saver", {"action": "pwnctl", "plugin": "windows", "cmd": "screen_saver_start"}),
                ("Stop Saver", {"action": "pwnctl", "plugin": "windows", "cmd": "screen_saver_stop"}),
                ("Reset Defaults", {"action": "pwnctl", "plugin": "windows", "cmd": "reset_runtime_defaults"}),
                ("Next Aux", {"action": "pwnctl", "plugin": "windows", "cmd": "aux_next"}),
                ("Prev Aux", {"action": "pwnctl", "plugin": "windows", "cmd": "aux_prev"}),
            ]
        }
        
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
                elif path == "status":
                    return jsonify(self.status_payload())
                elif path == "config":
                    return jsonify(self.config_payload())
                elif path == "display_hijack":
                    try:
                        payload = self.enable_second_screen()
                        payload.update({"message": "Hijack display successful!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display hijacking error", 500 
                elif path == "display_pwny":
                    try:
                        payload = self.disable_second_screen()
                        payload.update({"message": "Pwny change successful!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display Pwny error", 500
                elif path == "second_screen":
                    logging.warning("second_screen")
                    try:
                        payload = self.toggle_second_screen()
                        payload.update({"message": "Second screen change successful!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display Pwny error", 500
                elif path == "display_next":
                    try:
                        self.process_actions({"action": "switch_screen_mode"})
                        payload = self.status_payload()
                        payload.update({"message": "Display change successful!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display next error", 500
                elif path == "display_previous":
                    try:
                        self.process_actions({"action": "switch_screen_mode_reverse"})
                        payload = self.status_payload()
                        payload.update({"message": "Display change successful!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Display previous error", 500
                elif path == "screen_saver_next":
                    try:
                        self.process_actions({"action": "next_screen_saver"})
                        payload = self.status_payload()
                        payload.update({"message": "Screen saver change successful!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                            logging.error(ex)
                            logging.error(traceback.format_exc())
                            return "Next screen saver error", 500
                elif path == "screen_saver_previous":
                    try:
                        self.process_actions({"action": "previous_screen_saver"})
                        payload = self.status_payload()
                        payload.update({"message": "Screen saver change successful!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                            logging.error(ex)
                            logging.error(traceback.format_exc())
                            return "previous screen saver error", 500
                elif path == "screen_saver_start":
                    try:
                        self.start_screen_saver()
                        payload = self.status_payload()
                        payload.update({"message": "Screen saver started!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Screen saver start error", 500
                elif path == "screen_saver_stop":
                    try:
                        self.stop_screen_saver()
                        payload = self.status_payload()
                        payload.update({"message": "Screen saver stopped!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Screen saver stop error", 500
                elif path == "aux_next":
                    try:
                        self.process_actions({"action": "next_aux"})
                        payload = self.status_payload()
                        payload.update({"message": "Aux change successful!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Aux next error", 500
                elif path == "aux_prev":
                    try:
                        self.process_actions({"action": "previous_aux"})
                        payload = self.status_payload()
                        payload.update({"message": "Aux change successful!", "status": 200})
                        return jsonify(payload)
                    except Exception as ex:
                        logging.error(ex)
                        logging.error(traceback.format_exc())
                        return "Aux previous error", 500
                    
            elif request.method == "POST":
                try:
                    data = request.get_json(silent=True) or {}
                except TypeError:
                    data = request.get_json() or {}
                if path == "save_config":
                    patch = data.get('options') or data
                    return jsonify(self.save_defaults(patch, apply_now=bool(data.get('reset_runtime') or data.get('apply_now'))))
                elif path == "set_mode":
                    mode = data.get('mode')
                    if data.get('persist'):
                        self._save_plugin_options({'default_mode': self._valid_mode(mode, self.default_mode)})
                    payload = self.set_display_mode(mode, apply_now=bool(data.get('apply_now', True)))
                    return jsonify(payload)
                elif path == "set_screen_saver":
                    sub_mode = self._valid_screen_saver(data.get('sub_mode'), self.current_screen_saver)
                    patch = data.get('options_patch') or {}
                    if data.get('persist'):
                        patch['default_screen_saver'] = sub_mode
                        self._save_plugin_options(patch)
                    if data.get('apply_now', True):
                        return jsonify(self.set_screen_saver(sub_mode, apply_now=True, options_patch=patch))
                    return jsonify(self.status_payload())
                elif path == "set_aux":
                    plugin_name = self._valid_aux_plugin(data.get('plugin'), '')
                    if data.get('persist'):
                        self._save_plugin_options({'default_aux_plugin': plugin_name})
                    if data.get('apply_now', True):
                        return jsonify(self.set_aux_plugin(plugin_name, apply_now=True))
                    return jsonify(self.status_payload())
                elif path == "set_second_screen":
                    payload = self.enable_second_screen() if data.get('enabled') else self.disable_second_screen()
                    return jsonify(payload)
                elif path == "screen_saver_start":
                    self.start_screen_saver(sub_mode=data.get('sub_mode'), config=data.get('config'))
                    return jsonify(self.status_payload())
                elif path == "screen_saver_stop":
                    self.stop_screen_saver()
                    return jsonify(self.status_payload())
                elif path == "reset_runtime_defaults":
                    return jsonify(self.reset_runtime_to_defaults())
                elif path == "apply_runtime":
                    if 'fps' in data:
                        self.set_fps(data.get('fps'), apply_now=True)
                    return jsonify(self.apply_display_config(
                        mode=data.get('mode'),
                        sub_mode=data.get('sub_mode'),
                        config=data.get('config'),
                    ))
            return jsonify({"error": "unknown route", "path": path}), 404

        except Exception as e:
            logging.info(f"Error in webhook: {str(e)}")
            logging.info(traceback.format_exc())
            return jsonify({"error": str(e), "path": path}), 500
