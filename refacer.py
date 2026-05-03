import copy
import fnmatch
import hashlib
import html
import json
import logging
import mimetypes
import os
import pathlib
import re
import shutil
import tempfile
import threading
import time
import unicodedata
import zipfile
from html.parser import HTMLParser
from textwrap import TextWrapper
from io import BytesIO
from urllib.parse import quote

from PIL import ImageChops
import requests
import toml
from flask import jsonify, render_template_string, request, send_file
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps, ImageSequence
try:
    from fontTools.ttLib import TTFont
except Exception:
    TTFont = None

import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.faces as faces
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.ui.view as view
from pwnagotchi.utils import save_config

THEMES_REPO = "https://api.github.com/repos/V0r-T3x/Fancygotchi_themes/contents/fancygotchi_2.0/themes"
DEFAULT_THEME_INFO = {
    "author": "Default",
    "version": "builtin",
    "display": "main",
    "plugins": "refacer",
    "notes": "Built-in render defaults.",
}
# TODO Phase 2: detect actual jQM filenames under pwnagotchi/ui/web/static/js and css at startup;
# current hardcoded names (jquery.mobile-1.4.5.min.js, jquery.js) match the conventional
# pwnagotchi layout but may be wrong on exotic installs.

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
    #refacer-manager { padding: 15px; }
    .refacer-card { border: 1px solid #ccc; padding: 15px; margin-bottom: 15px; border-radius: 5px; background-color: #f9f9f9; }
    .refacer-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 15px; }
    .refacer-preview { width: 100%; max-width: 420px; border: 1px solid #bbb; background: #fff; }
    .refacer-textarea { width: 100%; min-height: 180px; font-family: monospace; resize: vertical; }
    .refacer-status { min-height: 20px; font-weight: bold; }
    .refacer-muted { color: #555; font-size: 0.9em; }
    .refacer-actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    .refacer-list { margin: 0; padding-left: 18px; }
    .refacer-list li { margin-bottom: 4px; }
    .refacer-diagnostics { font-family: monospace; white-space: pre-wrap; }
    .refacer-editor-layout { display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(280px, 0.9fr); gap: 15px; align-items: start; }
    .refacer-editor-workspace { min-height: 520px; }
    .refacer-editor-sidebar { min-width: 0; }
    .refacer-editor-panel { min-height: 180px; border: 1px dashed #b8b8b8; border-radius: 5px; background: #fff; padding: 15px; }
    #editor-preview-panel { min-height: 180px; display: flex; flex-direction: column; gap: 10px; }
    .refacer-editor-stack { display: grid; gap: 15px; }
    .refacer-editor-stage { position: relative; width: 100%; max-width: 720px; border: 1px solid #bbb; background: #fff; overflow: hidden; }
    .refacer-editor-stage img { display: block; width: 100%; height: auto; image-rendering: pixelated; }
    .refacer-editor-overlay { position: absolute; inset: 0; pointer-events: none; }
    .refacer-editor-box { position: absolute; border: 1px solid rgba(40, 90, 180, 0.8); background: rgba(40, 90, 180, 0.12); box-sizing: border-box; pointer-events: auto; cursor: pointer; }
    .refacer-editor-box.is-draggable { cursor: grab; }
    .refacer-editor-overlay.is-hidden { opacity: 0; visibility: hidden; }
    .refacer-editor-overlay.is-dragging .refacer-editor-box:not(.is-dragging) { pointer-events: none; }
    .refacer-editor-box.is-dragging { cursor: grabbing; }
    .refacer-editor-box.is-selected { border-color: rgba(190, 60, 20, 0.95); background: rgba(190, 60, 20, 0.18); }
    .refacer-editor-box-label { position: absolute; top: -18px; left: 0; max-width: 180px; padding: 1px 4px; font-size: 11px; line-height: 1.3; background: rgba(255, 255, 255, 0.92); border: 1px solid rgba(40, 90, 180, 0.35); color: #222; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .refacer-editor-box.is-selected .refacer-editor-box-label { border-color: rgba(190, 60, 20, 0.5); }
    .refacer-editor-detail { margin: 0; white-space: pre-wrap; font-family: monospace; font-size: 12px; color: #222; }
    .refacer-editor-empty { color: #666; font-size: 0.92em; }
    .refacer-editor-summary { display: grid; gap: 6px; }
    .refacer-editor-row { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 10px; align-items: start; font-size: 0.92em; }
    .refacer-editor-row strong { color: #333; }
    .refacer-editor-form { display: grid; gap: 10px; margin-top: 10px; }
    .refacer-editor-form label { display: block; font-size: 0.9em; color: #333; margin-bottom: 3px; }
    .refacer-editor-form input[type='text'], .refacer-editor-form input[type='number'], .refacer-editor-form select { width: 100%; box-sizing: border-box; }
    .refacer-editor-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .refacer-editor-note { color: #666; font-size: 0.86em; }
    .refacer-editor-list { margin: 0; padding-left: 18px; }
    .refacer-editor-inline-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
    .refacer-editor-list li { margin-bottom: 4px; }
    .refacer-editor-box.is-hidden-widget { border-color: rgba(120, 120, 120, 0.6); background: rgba(120, 120, 120, 0.08); border-style: dashed; }
    .refacer-editor-box.is-hidden-widget .refacer-editor-box-label { color: #888; background: rgba(240,240,240,0.92); border-color: rgba(120,120,120,0.35); }
    .refacer-editor-box.is-negative-z { border-color: rgba(160, 60, 200, 0.65); background: rgba(160, 60, 200, 0.1); border-style: dotted; }
    .refacer-editor-box.is-negative-z .refacer-editor-box-label { color: #7a2a9a; border-color: rgba(160,60,200,0.4); }
    .refacer-widget-selector-wrap { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
    .refacer-widget-selector-wrap label { margin: 0; font-size: 0.9em; white-space: nowrap; }
    .refacer-widget-selector-wrap select { min-width: 200px; }
    .refacer-asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; margin-top: 6px; }
    .refacer-asset-tile { border: 1px solid #ddd; padding: 4px; background: #fafafa; font-size: 11px; position: relative; }
    .refacer-asset-tile a { display: block; text-decoration: none; }
    .refacer-asset-check { display: block; margin-bottom: 4px; }
    .refacer-asset-group summary { cursor: pointer; padding: 4px 0; }
    .refacer-asset-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 6px 0; padding: 4px 0; border-bottom: 1px dashed #eee; }
    .refacer-asset-selectall { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; margin: 0; }
    .css-editor-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); gap: 15px; align-items: start; margin-top: 10px; }
    #css-editor-swatch-fields { max-height: 60vh; overflow-y: auto; padding-right: 4px; }
    .css-editor-role-block { margin-bottom: 12px; padding: 6px 8px; border: 1px solid #e0e0e0; background: #fafafa; border-radius: 4px; }
    .css-editor-role-block h5 { margin: 0 0 6px; font-size: 0.92em; border-bottom: 1px solid #ddd; padding-bottom: 3px; }
    .css-editor-field-row { display: grid; grid-template-columns: 140px minmax(0, 1fr); gap: 6px; margin-bottom: 4px; align-items: center; }
    .css-editor-field-row label { font-size: 0.86em; color: #333; }
    .css-editor-field-inputs { display: flex; align-items: center; gap: 5px; width: 100%; }
    .css-color-picker { width: 34px; height: 28px; padding: 1px; border: 1px solid #bbb; border-radius: 3px; cursor: pointer; flex-shrink: 0; }
    .css-color-text { font-family: monospace; font-size: 0.9em; padding: 3px 6px; box-sizing: border-box; flex: 1; min-width: 0; }
    @media (max-width: 900px) { .css-editor-layout { grid-template-columns: 1fr; } }
    .refacer-editor-widgetgroup { margin-top: 10px; padding: 6px 8px; border: 1px solid #e0e0e0; background: #fafafa; border-radius: 4px; }
    .refacer-editor-widgetgroup > summary { cursor: pointer; padding: 4px 0; font-size: 0.92em; }
    .refacer-editor-asset-picker { margin-top: 6px; }
    .refacer-editor-asset-picker select { width: 100%; }
    .refacer-editor-tabcard { padding: 0; }
    .refacer-editor-tabbar { display: flex; gap: 4px; padding: 8px 8px 0; border-bottom: 1px solid #ddd; background: #f4f4f4; flex-wrap: wrap; }
    .refacer-editor-tab { margin: 0; flex: 1 1 auto; min-width: 0; text-align: center; }
    .refacer-editor-tab.is-active { background: #fff; border-color: #bbb; border-bottom-color: #fff; font-weight: bold; }
    .refacer-editor-tabpanels { padding: 12px; }
    .refacer-editor-tabpanel { display: none; max-height: 70vh; overflow-y: auto; padding-bottom: 4px; }
    .refacer-editor-tabpanel.is-active { display: block; }
    .refacer-glyph-browser { position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 9999; display: none; align-items: center; justify-content: center; padding: 16px; }
    .refacer-glyph-browser.is-open { display: flex; }
    .refacer-glyph-browser-card { width: min(960px, 100%); max-height: 85vh; overflow: hidden; background: #fff; border-radius: 6px; border: 1px solid #bbb; display: flex; flex-direction: column; }
    .refacer-glyph-browser-head { display: flex; gap: 10px; align-items: center; justify-content: space-between; padding: 10px 12px; border-bottom: 1px solid #ddd; background: #f5f5f5; }
    .refacer-glyph-browser-body { padding: 12px; overflow: auto; }
    .refacer-glyph-browser-toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
    .refacer-glyph-browser-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(88px, 1fr)); gap: 8px; }
    .refacer-glyph-browser-item { border: 1px solid #d5d5d5; background: #fafafa; border-radius: 4px; padding: 8px 6px; text-align: center; cursor: pointer; }
    .refacer-glyph-browser-item:hover { border-color: #7aa0d6; background: #eef5ff; }
    .refacer-glyph-preview { font-size: 28px; line-height: 1.2; min-height: 38px; display: flex; align-items: center; justify-content: center; }
    .refacer-glyph-code { font-family: monospace; font-size: 11px; color: #444; margin-top: 4px; }
    @media (max-width: 900px) {
        .refacer-editor-layout { grid-template-columns: 1fr; }
        .refacer-editor-form-grid { grid-template-columns: 1fr; }
        .refacer-editor-tabpanel { max-height: 50vh; }
    }
</style>
{% endblock %}
{% block script %}
var refacerPreviewTimer = null;
var refacerInitialized = false;
var refacerBootstrapReached = false;
var refacerStatusEl = null;
var refacerEditorSnapshot = null;
var refacerEditorDragJustEnded = false;
var refacerEditorOverlayVisible = true;
var refacerPreviewEnabled = true;
var refacerEditorSelectedKey = null;
var refacerEditorActiveTab = "widget";
var refacerEditorAssetSelections = {};
var refacerEditorFontSizes = ["", "Small", "Medium", "BoldSmall", "Bold", "BoldBig", "Huge"];
var refacerEditorDragState = null;
var refacerExperimentalNonNativeSelects = {% if options.get('experimental_non_native_selects') %}true{% else %}false{% endif %};

function refacerRawRequest(method, path, payload) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, refacerPath(path), true);
    xhr.setRequestHeader("X-CSRFToken", "{{ csrf_token() }}");
    if (payload !== undefined && payload !== null) {
        xhr.setRequestHeader("Content-Type", "application/json");
    }
    xhr.send(payload !== undefined && payload !== null ? JSON.stringify(payload) : null);
}

// Keep this first so we can verify the script parsed and started executing at all.
refacerRawRequest("GET", "debug/js_ping");

function refacerPath(path) {
    var base = window.location.pathname.replace(/\/+$/, "");
    return base + (path ? "/" + path : "");
}
function currentRefacerPage() {
    return document.getElementById("refacer-manager");
}
function refacerNonNativeSelectsEnabled() {
    var el = document.getElementById("cfg-experimental-non-native-selects");
    if (el) return el.value === "true";
    return !!refacerExperimentalNonNativeSelects;
}
function onExperimentalNonNativeSelectsChanged() {
    refacerExperimentalNonNativeSelects = refacerNonNativeSelectsEnabled();
    console.info("[Refacer][ui] dropdown enhancement mode=" + (refacerExperimentalNonNativeSelects ? "non-native experimental" : "native/default"));
    enhanceRefacerWidgets();
}
function setFrontendStatus(message, isError) {
    refacerStatusEl = refacerStatusEl || document.getElementById("frontend-status");
    if (!refacerStatusEl) return;
    refacerStatusEl.textContent = message || "";
    refacerStatusEl.style.color = isError ? "#a40000" : "#1f5f1f";
}
window.onerror = function(message, source, lineno, colno) {
    refacerRawRequest("POST", "debug/js_error", {
        message: String(message),
        source: source || "",
        lineno: lineno || 0,
        colno: colno || 0
    });
    setFrontendStatus("Init failed: " + message, true);
};
window.addEventListener("unhandledrejection", function(event) {
    var reason = event && event.reason ? String(event.reason) : "Unhandled promise rejection";
    refacerRawRequest("POST", "debug/js_error", {
        message: reason,
        source: "unhandledrejection",
        lineno: 0,
        colno: 0
    });
    setFrontendStatus("Init failed: " + reason, true);
});
function enhanceRefacerWidgets() {
    var page = currentRefacerPage();
    if (!page || typeof window.jQuery === "undefined") return;
    var $page = window.jQuery(page);
    var forceNonNative = refacerNonNativeSelectsEnabled();
    console.debug("[Refacer][ui] enhancing selects mode=" + (forceNonNative ? "non-native experimental" : "native/default"));
    try {
        $page.find("select").not("[data-role='flipswitch']").each(function() {
            var $select = window.jQuery(this);
            if (forceNonNative) {
                $select.attr("data-native-menu", "false");
                if ($select.data("mobile-selectmenu")) $select.selectmenu("refresh", true);
                else $select.selectmenu({ nativeMenu: false });
            } else {
                $select.removeAttr("data-native-menu");
                if ($select.data("mobile-selectmenu")) $select.selectmenu("refresh", true);
                else $select.selectmenu();
            }
        });
    } catch (e) {}
    try { $page.find("select[data-role='flipswitch']").flipswitch("refresh"); } catch (e) {}
    try { $page.find("[data-role='navbar']").navbar(); } catch (e) {}
    try { $page.find("[data-role='tabs']").tabs(); } catch (e) {}
    try { $page.enhanceWithin(); } catch (e) {}
}
function setStatus(id, message, isError) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = message || "";
    el.style.color = isError ? "#a40000" : "#1f5f1f";
}
function setPreviewEnabled(enabled) {
    refacerPreviewEnabled = !!enabled;
    var btn = document.getElementById("preview-toggle-btn");
    if (btn) btn.textContent = "Preview: " + (refacerPreviewEnabled ? "Live" : "Paused");
    if (refacerPreviewEnabled) {
        startPreviewRefresh();
    } else {
        stopPreviewRefresh();
        refreshPreview();
    }
}
function togglePreview() {
    setPreviewEnabled(!refacerPreviewEnabled);
}
function setEditorOverlayVisible(visible) {
    refacerEditorOverlayVisible = !!visible;
    var overlay = document.getElementById("editor-preview-overlay");
    var toggle = document.getElementById("editor-overlay-toggle");
    if (overlay) {
        if (refacerEditorOverlayVisible) overlay.classList.remove("is-hidden");
        else overlay.classList.add("is-hidden");
    }
    if (toggle) {
        toggle.textContent = "Widget Boxes: " + (refacerEditorOverlayVisible ? "On" : "Off");
        toggle.dataset.overlayVisible = refacerEditorOverlayVisible ? "1" : "0";
    }
}
function toggleEditorOverlay() {
    if (refacerEditorDragState) return;
    setEditorOverlayVisible(!refacerEditorOverlayVisible);
}
function syncEditorOverlayVisibility() {
    setEditorOverlayVisible(refacerEditorOverlayVisible);
}

function requestJSON(method, path, data, onSuccess, statusId) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, refacerPath(path), true);
    xhr.setRequestHeader("X-CSRFToken", "{{ csrf_token() }}");
    if (data !== null) xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function() {
        if (xhr.readyState !== 4) return;
        var body = {};
        try { body = xhr.responseText ? JSON.parse(xhr.responseText) : {}; } catch (e) { body = {}; }
        if (xhr.status >= 200 && xhr.status < 300) {
            if (onSuccess) onSuccess(body);
        } else if (statusId) {
            setStatus(statusId, body.message || body.error || ("Request failed (" + xhr.status + ")"), true);
        }
    };
    xhr.send(data === null ? null : JSON.stringify(data));
}
function refreshPreview() {
    var img = document.getElementById("main-preview");
    if (img) {
        img.src = refacerPath("preview_frame") + "?t=" + Date.now();
        setStatus("preview-status", "Preview auto-refresh active.", false);
    }
}
function startPreviewRefresh() {
    stopPreviewRefresh();
    var fps = parseInt((document.getElementById("cfg-fps") || {}).value || "{{ options.get('fps', 30) }}", 10);
    var interval = Math.max(1000, Math.floor(4000 / Math.max(1, fps || 1)));
    refacerPreviewTimer = window.setInterval(refreshPreview, interval);
    refreshPreview();
}
function stopPreviewRefresh() {
    if (refacerPreviewTimer) {
        window.clearInterval(refacerPreviewTimer);
        refacerPreviewTimer = null;
    }
}
function setStealthButton(enabled) {
    var btn = document.getElementById("stealth-toggle-btn");
    if (!btn) return;
    btn.textContent = "Stealth Mode: " + (enabled ? "On" : "Off");
    btn.dataset.stealthEnabled = enabled ? "1" : "0";
}
function toggleStealthMode() {
    var btn = document.getElementById("stealth-toggle-btn");
    var nextEnabled = !(btn && btn.dataset.stealthEnabled === "1");
    requestJSON("POST", "stealth_toggle", {enabled: nextEnabled}, function(body) {
        setStealthButton(!!body.stealth_mode);
        setStatus("stealth-status", body.message || ("Stealth mode " + (body.stealth_mode ? "enabled." : "disabled.")), false);
        refreshPreview();
        loadConfiguration(document.getElementById("theme-selector").value || document.getElementById("cfg-theme").value || "Default");
    }, "stealth-status");
}
function renderDisplayStatus(body) {
    body = body || {};
    var btn = document.getElementById("display-toggle-btn");
    if (btn) {
        btn.textContent = "Display: " + (body.enabled ? "On" : "Off");
        btn.dataset.displayEnabled = body.enabled ? "1" : "0";
    }
    var timer = body.auto_off_seconds > 0 ? (body.auto_off_seconds + "s") : "Off";
    var state = body.enabled ? "On" : "Off";
    var backend = body.sleep_backend_active || body.backend || body.sleep_backend || "blank";
    var reason = body.sleep_reason || "none";
    var msg = "State: " + state + " | Backend: " + backend + " | Timer: " + timer + " | Reason: " + reason;
    if (body.windows_error) msg += " | Windows: " + body.windows_error;
    setStatus("display-control-status", msg, body.status === "error");
}
function loadDisplayStatus() {
    requestJSON("GET", "display_status", null, renderDisplayStatus, "display-control-status");
}
function setDisplayPower(enabled) {
    requestJSON("POST", enabled ? "display_on" : "display_off", {}, function(body) {
        renderDisplayStatus(body);
        refreshPreview();
    }, "display-control-status");
}
function toggleDisplayPower() {
    var btn = document.getElementById("display-toggle-btn");
    var enabled = !(btn && btn.dataset.displayEnabled === "1");
    setDisplayPower(enabled);
}
function clearDisplay() {
    requestJSON("POST", "display_clear", {}, function(body) {
        renderDisplayStatus(body);
    }, "display-control-status");
}
function setDisplayTimer(seconds) {
    requestJSON("POST", "display_timer", {seconds: seconds}, function(body) {
        renderDisplayStatus(body);
    }, "display-control-status");
}
function renderThemeInfo(info) {
    var target = document.getElementById("theme-info");
    var screenshot = document.getElementById("theme-screenshot");
    var screenshotWrap = document.getElementById("theme-screenshot-wrap");
    target.innerHTML = "";
    [["Author", info.author || "Unknown"], ["Version", info.version || "Unknown"], ["Display", info.display || "main"], ["Plugins", info.plugins || "refacer"]].forEach(function(row) {
        var item = document.createElement("li");
        item.innerHTML = "<strong>" + row[0] + ":</strong> " + (row[1] || "");
        target.appendChild(item);
    });
    var notes = document.createElement("li");
    notes.style.whiteSpace = "pre-wrap";
    notes.innerHTML = "<strong>Notes:</strong> " + (info.notes || "None");
    target.appendChild(notes);
    if (info.screenshot_url) {
        var joiner = info.screenshot_url.indexOf("?") === -1 ? "?" : "&";
        screenshot.src = info.screenshot_url + joiner + "_ts=" + Date.now();
        screenshot.style.display = "";
        screenshotWrap.style.display = "";
    } else {
        screenshot.removeAttribute("src");
        screenshot.style.display = "none";
        screenshotWrap.style.display = "none";
    }
}
function loadThemeInfo(theme) {
    requestJSON("POST", "theme_info", {theme: theme}, function(body) { renderThemeInfo(body); }, "theme-status");
}
function populateThemeSelect(select, themes, selectedTheme) {
    if (!select) return "Default";
    select.innerHTML = "";
    var resolvedTheme = selectedTheme || "Default";
    if (themes.indexOf(resolvedTheme) === -1) {
        resolvedTheme = themes.indexOf("Default") !== -1
            ? "Default"
            : (themes.length ? themes[0] : "Default");
    }
    themes.forEach(function(theme) {
        var option = document.createElement("option");
        option.value = theme;
        option.textContent = theme;
        if (theme === resolvedTheme) option.selected = true;
        select.appendChild(option);
    });
    if (select.options.length) {
        select.value = resolvedTheme;
        if (select.value !== resolvedTheme) {
            for (var i = 0; i < select.options.length; i++) {
                if (select.options[i].value === resolvedTheme) {
                    select.selectedIndex = i;
                    break;
                }
            }
        }
    }
    return select.value || resolvedTheme || "Default";
}
function escapeEditorHtml(value) {
    var text = String(value == null ? "" : value);
    var map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '\\\"': '&quot;'};
    return text.replace(/[&<>"]/g, function(ch) { return map[ch] || ch; });
}
function editorDisplayValue(value) {
    if (value === null || value === undefined || value === "") return "None";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "boolean") return value ? "Yes" : "No";
    return String(value);
}
function renderEditorRows(rows) {
    var html = "<div class='refacer-editor-summary'>";
    rows.forEach(function(row) {
        html += "<div class='refacer-editor-row'><strong>" + escapeEditorHtml(row[0]) + "</strong><span>" + escapeEditorHtml(editorDisplayValue(row[1])) + "</span></div>";
    });
    html += "</div>";
    return html;
}
function renderEditorSelectedWidgetSummary(widget) {
    var panel = document.getElementById("editor-selected-widget");
    if (!panel) return;
    if (!widget) {
        panel.innerHTML = "<h4>Selected Widget</h4><p class='refacer-editor-empty'>Click a widget overlay box to inspect its runtime details.</p>";
        return;
    }
    panel.innerHTML = "<h4>Selected Widget</h4>" + renderEditorRows([
        ["Key", widget.key],
        ["Type", widget.widget_type],
        ["Origin", widget.origin],
        ["Render Mode", widget.render_mode],
        ["Z Axis", widget.z_axis],
        ["Visible", widget.visible !== false ? "Yes" : "No"],
        ["Hidden Reason", widget.hidden_reason || "None"],
        ["Theme Override", widget.has_theme_override ? "Yes" : "No"]
    ]) + (widget.preview_text ? "<p class='refacer-editor-note' style='margin-top:10px;'>Preview: " + escapeEditorHtml(widget.preview_text) + "</p>" : "");
}
var PLACEMENT_MODES = ["normal", "stretch", "fit", "fill", "center", "tile"];
var COLOR_MODES_PIL = ["P", "L", "RGB", "RGBA", "1"];
function goptEl(id) { return document.getElementById(id); }
function goptVal(id) { var el = goptEl(id); return el ? el.value : ""; }
function goptChecked(id) { var el = goptEl(id); return el ? el.checked : false; }
function buildModeSelect(id, selected, modes) {
    var opts = modes.map(function(m) {
        return "<option value='" + escapeEditorHtml(m) + "'" + (m === selected ? " selected" : "") + ">" + escapeEditorHtml(m) + "</option>";
    }).join("");
    return "<select id='" + id + "'" + (refacerNonNativeSelectsEnabled() ? " data-native-menu='false'" : "") + ">" + opts + "</select>";
}
function editorAssetGroupLabel(group) {
    var labels = {
        backgrounds: "Backgrounds",
        foregrounds: "Foregrounds",
        faces: "Faces",
        friend_faces: "Friend Faces",
        widgets: "Widgets",
        icons: "Icons",
        fonts: "Fonts"
    };
    return labels[group] || String(group || "").replace(/_/g, " ");
}
function buildAssetPicker(selectId, groups, selectedValue, snapshot, disabledAttr, labelText, noteText) {
    var assets = (snapshot && snapshot.assets) || {};
    var current = String(selectedValue || "");
    var html = "<div class='refacer-editor-asset-picker'>" +
        "<label for='" + selectId + "'>" + escapeEditorHtml(labelText || "Theme asset") + "</label>" +
        "<select id='" + selectId + "'" + (refacerNonNativeSelectsEnabled() ? " data-native-menu='false'" : "") + (disabledAttr || "") + ">" +
        "<option value=''>Custom / none</option>";
    groups.forEach(function(group) {
        var files = Array.isArray(assets[group]) ? assets[group] : [];
        if (!files.length) return;
        html += "<optgroup label='" + escapeEditorHtml(editorAssetGroupLabel(group)) + "'>";
        files.forEach(function(rel) {
            var safeRel = String(rel || "");
            var filename = safeRel.split(/[\\\\/]/).pop() || safeRel;
            html += "<option value='" + escapeEditorHtml(safeRel) + "'" + (safeRel === current ? " selected" : "") + ">" +
                escapeEditorHtml(filename) + "</option>";
        });
        html += "</optgroup>";
    });
    html += "</select>" +
        "<p class='refacer-editor-note'>" + escapeEditorHtml(noteText || "Pick from local theme assets or type a custom relative path.") + "</p>" +
        "</div>";
    return html;
}
function buildFontPicker(selectId, selectedValue, snapshot, disabledAttr) {
    var assets = (snapshot && snapshot.assets) || {};
    var current = String(selectedValue || "");
    var html = "<div class='refacer-editor-asset-picker'>" +
        "<label for='" + selectId + "'>Theme font</label>" +
        "<select id='" + selectId + "'" + (refacerNonNativeSelectsEnabled() ? " data-native-menu='false'" : "") + (disabledAttr || "") + ">" +
        "<option value=''>Custom / none</option>";
    (Array.isArray(assets.fonts) ? assets.fonts : []).forEach(function(rel) {
        var safeRel = String(rel || "");
        var filename = safeRel.split(/[\\\\/]/).pop() || safeRel;
        html += "<option value='" + escapeEditorHtml(filename) + "'" + ((current === filename || current === safeRel) ? " selected" : "") + ">" +
            escapeEditorHtml(filename) + "</option>";
    });
    html += "</select>" +
        "<p class='refacer-editor-note'>Pick from local theme fonts or type a custom font name/path.</p>" +
        "</div>";
    return html;
}
function bindAssetPicker(selectId, inputId) {
    var select = document.getElementById(selectId);
    var input = document.getElementById(inputId);
    if (!select || !input) return;
    function syncFromInput() {
        var value = String(input.value || "");
        var match = false;
        Array.prototype.forEach.call(select.options || [], function(option) {
            if (String(option.value || "") === value) match = true;
        });
        select.value = match ? value : "";
    }
    if (select.dataset.refacerAssetBound !== "1") {
        select.addEventListener("change", function() {
            input.value = select.value || "";
        });
        input.addEventListener("input", syncFromInput);
        select.dataset.refacerAssetBound = "1";
    }
    syncFromInput();
}
var refacerGlyphBrowserState = {
    theme: null,
    fontInputId: null,
    targetInputId: null,
    insertMode: "glyph-char",
    glyphs: [],
    fontAssetPath: "",
    fontName: ""
};
function glyphBrowserLabelToken(entry) {
    return String((entry && entry.hex) || "").trim().toLowerCase();
}
function ensureGlyphBrowser() {
    var existing = document.getElementById("refacer-glyph-browser");
    if (existing) return existing;
    var wrap = document.createElement("div");
    wrap.id = "refacer-glyph-browser";
    wrap.className = "refacer-glyph-browser";
    wrap.innerHTML =
        "<div class='refacer-glyph-browser-card'>" +
            "<div class='refacer-glyph-browser-head'>" +
                "<div><strong>Font Awesome Glyph Browser</strong><div id='refacer-glyph-browser-subtitle' class='refacer-editor-note'></div></div>" +
                "<button type='button' id='refacer-glyph-browser-close' class='ui-btn ui-mini ui-corner-all'>Close</button>" +
            "</div>" +
            "<div class='refacer-glyph-browser-body'>" +
                "<p class='refacer-editor-note'>Glyph browser shows available codepoints from the selected Font Awesome font. Friendly icon names appear only when metadata is available.</p>" +
                "<div class='refacer-glyph-browser-toolbar'>" +
                    "<input type='text' id='refacer-glyph-browser-filter' placeholder='Filter by hex or character' style='flex:1; min-width:220px;'>" +
                    "<span id='refacer-glyph-browser-status' class='refacer-editor-note'></span>" +
                "</div>" +
                "<style id='refacer-glyph-browser-font-style'></style>" +
                "<div id='refacer-glyph-browser-grid' class='refacer-glyph-browser-grid'></div>" +
            "</div>" +
        "</div>";
    document.body.appendChild(wrap);
    wrap.addEventListener("click", function(event) {
        if (event.target === wrap) closeGlyphBrowser();
    });
    document.getElementById("refacer-glyph-browser-close").addEventListener("click", function() {
        closeGlyphBrowser();
    });
    document.getElementById("refacer-glyph-browser-filter").addEventListener("input", function() {
        renderGlyphBrowserGrid();
    });
    return wrap;
}
function closeGlyphBrowser() {
    var wrap = document.getElementById("refacer-glyph-browser");
    if (wrap) wrap.classList.remove("is-open");
}
function renderGlyphBrowserGrid() {
    var grid = document.getElementById("refacer-glyph-browser-grid");
    var filterEl = document.getElementById("refacer-glyph-browser-filter");
    var statusEl = document.getElementById("refacer-glyph-browser-status");
    if (!grid) return;
    var filter = String((filterEl && filterEl.value) || "").trim().toLowerCase();
    var glyphs = (refacerGlyphBrowserState.glyphs || []).filter(function(entry) {
        if (!filter) return true;
        return String(entry.hex || "").toLowerCase().indexOf(filter) >= 0
            || String(entry.char || "").toLowerCase().indexOf(filter) >= 0;
    });
    grid.innerHTML = "";
    if (!glyphs.length) {
        grid.innerHTML = "<p class='refacer-editor-empty'>No glyphs match the current filter.</p>";
        if (statusEl) statusEl.textContent = "0 glyphs";
        return;
    }
    glyphs.forEach(function(entry) {
        var labelToken = glyphBrowserLabelToken(entry);
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "refacer-glyph-browser-item";
        btn.innerHTML = "<div class='refacer-glyph-preview'>" + escapeEditorHtml(entry.char || "") + "</div>" +
            "<div class='refacer-glyph-code'>" + escapeEditorHtml(entry.hex || "") + "</div>" +
            "<div class='refacer-glyph-code'>" + escapeEditorHtml(labelToken || "") + "</div>";
        btn.addEventListener("click", function() {
            var targetId = refacerGlyphBrowserState.targetInputId;
            var target = targetId ? document.getElementById(targetId) : null;
            if (target) {
                target.value = refacerGlyphBrowserState.insertMode === "label-code" ? labelToken : (entry.char || "");
                target.dispatchEvent(new Event("input", {bubbles: true}));
                target.dispatchEvent(new Event("change", {bubbles: true}));
            }
            if (statusEl) statusEl.textContent = "Selected " + (entry.hex || "");
            if (target) closeGlyphBrowser();
        });
        grid.appendChild(btn);
    });
    if (statusEl) statusEl.textContent = glyphs.length + " glyphs";
}
function openGlyphBrowser(options) {
    var wrap = ensureGlyphBrowser();
    var subtitle = document.getElementById("refacer-glyph-browser-subtitle");
    var statusEl = document.getElementById("refacer-glyph-browser-status");
    var filterEl = document.getElementById("refacer-glyph-browser-filter");
    var fontInput = options.fontInputId ? document.getElementById(options.fontInputId) : null;
    var fontName = fontInput ? String(fontInput.value || "").trim() : String(options.fontName || "").trim();
    var theme = options.theme || ((refacerEditorSnapshot && (refacerEditorSnapshot.requested_theme || refacerEditorSnapshot.theme)) || (document.getElementById("editor-theme-selector") || {}).value || "Default");
    refacerGlyphBrowserState.theme = theme;
    refacerGlyphBrowserState.fontInputId = options.fontInputId || null;
    refacerGlyphBrowserState.targetInputId = options.targetInputId || null;
    refacerGlyphBrowserState.insertMode = options.insertMode === "label-code" ? "label-code" : "glyph-char";
    refacerGlyphBrowserState.glyphs = [];
    refacerGlyphBrowserState.fontAssetPath = "";
    refacerGlyphBrowserState.fontName = fontName;
    if (filterEl) filterEl.value = "";
    if (subtitle) subtitle.textContent = fontName ? ("Font: " + fontName) : "No Font Awesome font selected.";
    if (statusEl) statusEl.textContent = "Loading glyphs...";
    document.getElementById("refacer-glyph-browser-grid").innerHTML = "<p class='refacer-editor-empty'>Loading glyphs...</p>";
    wrap.classList.add("is-open");
    requestJSON("POST", "editor/font_glyphs", {theme: theme, font_name: fontName}, function(body) {
        refacerGlyphBrowserState.glyphs = body.glyphs || [];
        refacerGlyphBrowserState.fontAssetPath = body.font_asset_path || "";
        refacerGlyphBrowserState.fontName = body.font_name || fontName;
        if (subtitle) subtitle.textContent = (body.font_name || fontName || "Unknown font") + (body.source ? (" (" + body.source + ")") : "");
        var styleEl = document.getElementById("refacer-glyph-browser-font-style");
        if (styleEl) {
            if (body.font_asset_path) {
                var fontUrl = refacerPath("theme_asset") + "?theme=" + encodeURIComponent(theme) + "&path=" + encodeURIComponent(body.font_asset_path);
                styleEl.textContent = "@font-face{font-family:'RefacerGlyphBrowserPreview';src:url('" + fontUrl.replace(/'/g, "%27") + "');}" +
                    ".refacer-glyph-preview{font-family:'RefacerGlyphBrowserPreview', monospace;}";
            } else {
                styleEl.textContent = ".refacer-glyph-preview{font-family:monospace;}";
            }
        }
        renderGlyphBrowserGrid();
    }, "editor-status");
}
function buildColorSequenceArea(id, value) {
    var text = Array.isArray(value) ? value.join(String.fromCharCode(10)) : (value || "");
    var parsed = editorParseColorSequence(text);
    return "<textarea id='" + id + "' rows='3' class='refacer-textarea' style='min-height:60px;'>" + escapeEditorHtml(text) + "</textarea>" +
        "<p class='refacer-editor-note'>One color per line.</p>" +
        "<div id='" + id + "-preview'>" + renderEditorColorSequencePreview(parsed) + "</div>";
}
function parseColorSeqFromEl(id) {
    var el = goptEl(id);
    var text = el ? el.value : "";
    return editorParseColorSequence(text);
}
function renderEditorThemeSummary(snapshot) {
    var panel = document.getElementById("editor-theme-properties");
    if (!panel) return;
    var snap = snapshot || {};
    var gopt = (snap.theme_global_options || {});
    var opts = gopt.options || {};
    var dev  = gopt.dev   || {};
    var isDefault = !!gopt.is_default;
    var fontSizes = Array.isArray(opts.font_sizes) ? opts.font_sizes : [14, 9, 14, 25, 19, 9];
    while (fontSizes.length < 6) fontSizes.push(fontSizes[fontSizes.length - 1] || 12);
    var colorMode = Array.isArray(opts.color_mode) ? opts.color_mode : (opts.color_mode ? [opts.color_mode] : ["P", "P"]);
    var disAttr = isDefault ? " disabled" : "";
    var disNote = isDefault ? "<p class='refacer-editor-note' style='color:#a00;margin-bottom:8px;'>Default theme: options are read-only. Copy the theme to edit.</p>" : "";
    var html = "<h4>Theme / Global Properties</h4>";
    html += renderEditorRows([
        ["Active Theme",    snap.active_theme || "Default"],
        ["Canvas",          snap.canvas ? (snap.canvas.width + " x " + snap.canvas.height) : "Unknown"],
        ["Physical Canvas", snap.physical_canvas ? (snap.physical_canvas.width + " x " + snap.physical_canvas.height) : "Unknown"],
        ["Rotation",        snap.rotation != null ? snap.rotation : 0],
        ["Render Tier",     snap.render_stats ? snap.render_stats.current_tier : "full"],
        ["Widget Count",    snap.widgets ? snap.widgets.length : 0],
        ["Draft Dirty",     snap.draft_dirty ? "Yes" : "No"]
    ]);
    html += "<form id='editor-global-form' class='refacer-editor-form' style='margin-top:14px;'>";
    html += disNote;

    // --- Background & Foreground ---
    html += "<h5 style='margin:10px 0 4px;border-bottom:1px solid #ddd;padding-bottom:3px;'>Background &amp; Foreground</h5>";
    html += "<div class='refacer-editor-form-grid'>";
    html += "<div><label for='gopt-bg-color'>BG Color</label><input type='text' id='gopt-bg-color' value='" + escapeEditorHtml(opts.bg_color || "white") + "'" + disAttr + "></div>";
    html += "<div><label for='gopt-boot-bg-color'>Boot BG Color</label><input type='text' id='gopt-boot-bg-color' value='" + escapeEditorHtml(opts.boot_bg_color || "") + "'" + disAttr + "></div>";
    html += "<div><label for='gopt-bg-image'>BG Image</label><input type='text' id='gopt-bg-image' value='" + escapeEditorHtml(opts.bg_image || "") + "'" + disAttr + ">" + buildAssetPicker("gopt-bg-image-picker", ["backgrounds"], opts.bg_image || "", snapshot, disAttr) + "</div>";
    html += "<div><label for='gopt-bg-anim-image'>BG Anim Image (GIF)</label><input type='text' id='gopt-bg-anim-image' value='" + escapeEditorHtml(opts.bg_anim_image || "") + "'" + disAttr + ">" + buildAssetPicker("gopt-bg-anim-image-picker", ["backgrounds"], opts.bg_anim_image || "", snapshot, disAttr) + "</div>";
    html += "<div><label for='gopt-fg-image'>FG Image</label><input type='text' id='gopt-fg-image' value='" + escapeEditorHtml(opts.fg_image || "") + "'" + disAttr + ">" + buildAssetPicker("gopt-fg-image-picker", ["foregrounds"], opts.fg_image || "", snapshot, disAttr) + "</div>";
    html += "<div><label for='gopt-bg-fg-select'>BG/FG Select</label>" + buildModeSelect("gopt-bg-fg-select", opts.bg_fg_select || "manu", ["manu", "auto"]) + "</div>";
    html += "<div><label for='gopt-bg-mode'>BG Mode</label>" + buildModeSelect("gopt-bg-mode", opts.bg_mode || "normal", PLACEMENT_MODES) + "</div>";
    html += "<div><label for='gopt-fg-mode'>FG Mode</label>" + buildModeSelect("gopt-fg-mode", opts.fg_mode || "normal", PLACEMENT_MODES) + "</div>";
    html += "</div>";

    // --- Colors ---
    html += "<h5 style='margin:10px 0 4px;border-bottom:1px solid #ddd;padding-bottom:3px;'>Colors</h5>";
    html += "<div><label for='gopt-main-text-color'>Main Text Colors</label>" + buildColorSequenceArea("gopt-main-text-color", opts.main_text_color) + "</div>";
    html += "<div><label for='gopt-base-text-color'>Base Text Colors</label>" + buildColorSequenceArea("gopt-base-text-color", opts.base_text_color) + "</div>";
    html += "<div class='refacer-editor-form-grid'>";
    html += "<div><label for='gopt-color-mode-static'>Color Mode (static)</label>" + buildModeSelect("gopt-color-mode-static", colorMode[0] || "P", COLOR_MODES_PIL) + "</div>";
    html += "<div><label for='gopt-color-mode-anim'>Color Mode (anim)</label>" + buildModeSelect("gopt-color-mode-anim", colorMode[1] || "P", COLOR_MODES_PIL) + "</div>";
    html += "</div>";

    // --- Fonts ---
    html += "<h5 style='margin:10px 0 4px;border-bottom:1px solid #ddd;padding-bottom:3px;'>Fonts</h5>";
    html += "<div class='refacer-editor-form-grid'>";
    html += "<div><label for='gopt-font'>Font</label><input type='text' id='gopt-font' value='" + escapeEditorHtml(opts.font || "") + "'" + disAttr + ">" + buildFontPicker("gopt-font-picker", opts.font || "", snapshot, disAttr) + "</div>";
    html += "<div><label for='gopt-font-bold'>Font Bold</label><input type='text' id='gopt-font-bold' value='" + escapeEditorHtml(opts.font_bold || "") + "'" + disAttr + ">" + buildFontPicker("gopt-font-bold-picker", opts.font_bold || "", snapshot, disAttr) + "</div>";
    html += "<div><label for='gopt-font-awesome'>Font Awesome</label><input type='text' id='gopt-font-awesome' value='" + escapeEditorHtml(opts.font_awesome || "") + "'" + disAttr + ">" + buildFontPicker("gopt-font-awesome-picker", opts.font_awesome || "", snapshot, disAttr) + "<button type='button' id='gopt-font-awesome-browse-btn' class='ui-btn ui-mini ui-corner-all' style='margin-top:6px;'>Browse FA glyphs</button></div>";
    html += "<div><label for='gopt-size-offset'>Size Offset</label><input type='number' id='gopt-size-offset' value='" + escapeEditorHtml(String(opts.size_offset != null ? opts.size_offset : 5)) + "'" + disAttr + "></div>";
    html += "<div><label for='gopt-font-spacing'>Font Spacing</label><input type='number' id='gopt-font-spacing' value='" + escapeEditorHtml(String(opts.font_spacing != null ? opts.font_spacing : 0)) + "'" + disAttr + "></div>";
    html += "</div>";
    html += "<p class='refacer-editor-note'>Pick from local theme fonts or type a custom font name/path.</p>";
    html += "<div><label>Font Sizes <span class='refacer-editor-note'>[Small, BoldSmall, Medium, Huge, BoldBig, Status]</span></label>";
    html += "<div class='refacer-editor-form-grid'>";
    ["Small", "BoldSmall", "Medium", "Huge", "BoldBig", "Status"].forEach(function(name, i) {
        html += "<div><label for='gopt-font-size-" + i + "'>" + name + "</label><input type='number' id='gopt-font-size-" + i + "' value='" + escapeEditorHtml(String(fontSizes[i] != null ? fontSizes[i] : 12)) + "'" + disAttr + "></div>";
    });
    html += "</div></div>";

    // --- Text Layout ---
    html += "<h5 style='margin:10px 0 4px;border-bottom:1px solid #ddd;padding-bottom:3px;'>Text &amp; Layout</h5>";
    html += "<div class='refacer-editor-form-grid'>";
    html += "<div><label for='gopt-cursor'>Cursor Char</label><input type='text' id='gopt-cursor' value='" + escapeEditorHtml(opts.cursor != null ? String(opts.cursor) : "|") + "' maxlength='3'" + disAttr + "></div>";
    html += "<div><label for='gopt-label-spacing'>Label Spacing</label><input type='number' id='gopt-label-spacing' value='" + escapeEditorHtml(String(opts.label_spacing != null ? opts.label_spacing : 9)) + "'" + disAttr + "></div>";
    html += "<div><label for='gopt-label-line-spacing'>Label Line Spacing</label><input type='number' id='gopt-label-line-spacing' value='" + escapeEditorHtml(String(opts.label_line_spacing != null ? opts.label_line_spacing : 0)) + "'" + disAttr + "></div>";
    html += "<div><label for='gopt-friend-bars'>Friend Bars Char</label><input type='text' id='gopt-friend-bars' value='" + escapeEditorHtml(opts.friend_bars != null ? String(opts.friend_bars) : "|") + "' maxlength='3'" + disAttr + "></div>";
    html += "<div><label for='gopt-friend-no-bars'>Friend Empty Bars Char</label><input type='text' id='gopt-friend-no-bars' value='" + escapeEditorHtml(opts.friend_no_bars != null ? String(opts.friend_no_bars) : "|") + "' maxlength='3'" + disAttr + "></div>";
    html += "</div>";
    html += "<div style='margin-top:6px;'><label><input type='checkbox' id='gopt-stealth-mode'" + (opts.stealth_mode ? " checked" : "") + (disAttr) + "> Stealth Mode (hide widgets with z &lt; 100)</label></div>";

    // --- Boot Animation ---
    html += "<h5 style='margin:10px 0 4px;border-bottom:1px solid #ddd;padding-bottom:3px;'>Boot Animation</h5>";
    html += "<div style='margin-bottom:6px;'><label><input type='checkbox' id='gopt-boot-animation'" + (opts.boot_animation ? " checked" : "") + (disAttr) + "> Enable Boot Animation</label></div>";
    html += "<div class='refacer-editor-form-grid'>";
    html += "<div><label for='gopt-boot-mode'>Boot Mode</label>" + buildModeSelect("gopt-boot-mode", opts.boot_mode || "stretch", PLACEMENT_MODES) + "</div>";
    html += "<div><label for='gopt-boot-max-loops'>Max Loops</label><input type='number' id='gopt-boot-max-loops' value='" + escapeEditorHtml(String(opts.boot_max_loops != null ? opts.boot_max_loops : 1)) + "'" + disAttr + "></div>";
    html += "<div><label for='gopt-boot-total-duration'>Total Duration (s)</label><input type='number' id='gopt-boot-total-duration' step='0.1' value='" + escapeEditorHtml(String(opts.boot_total_duration != null ? opts.boot_total_duration : 5)) + "'" + disAttr + "></div>";
    html += "</div>";
    html += "<div class='refacer-actions' style='margin-top:8px;'>";
    html += "<button type='button' id='editor-test-boot-anim-btn' class='ui-btn ui-corner-all'>Test Boot Animation</button>";
    html += "<span id='editor-test-boot-anim-status' class='refacer-editor-note' style='margin-left:8px;'></span>";
    html += "</div>";

    // --- Dev options ---
    html += "<h5 style='margin:10px 0 4px;border-bottom:1px solid #ddd;padding-bottom:3px;'>Dev Options</h5>";
    html += "<div class='refacer-editor-form-grid'>";
    html += "<div><label for='gopt-dev-refresh'>Dev Refresh Frame (-1 = off)</label><input type='number' id='gopt-dev-refresh' value='" + escapeEditorHtml(String(dev.refresh != null ? dev.refresh : -1)) + "'" + disAttr + "></div>";
    html += "<div style='display:flex;gap:12px;align-items:center;padding-top:18px;'>";
    html += "<label><input type='checkbox' id='gopt-dev-log'" + (dev.log !== false ? " checked" : "") + (disAttr) + "> Log</label>";
    html += "<label><input type='checkbox' id='gopt-dev-debug'" + (dev.debug ? " checked" : "") + (disAttr) + "> Debug</label>";
    html += "</div></div>";

    // --- Actions ---
    if (!isDefault) {
        html += "<div class='refacer-actions' style='margin-top:12px;'>";
        html += "<button type='button' id='editor-global-apply-btn' class='ui-btn ui-btn-b ui-corner-all'>Apply to Preview</button>";
        html += "<button type='button' id='editor-global-apply-theme-btn' class='ui-btn ui-corner-all'>Apply to Theme</button>";
        html += "</div>";
        html += "<div id='editor-global-status' class='refacer-status'></div>";
    }
    html += "</form>";
    panel.innerHTML = html;
    enhanceRefacerWidgets();
    [["gopt-bg-image-picker", "gopt-bg-image"], ["gopt-bg-anim-image-picker", "gopt-bg-anim-image"], ["gopt-fg-image-picker", "gopt-fg-image"]].forEach(function(pair) {
        bindAssetPicker(pair[0], pair[1]);
    });
    [["gopt-font-picker", "gopt-font"], ["gopt-font-bold-picker", "gopt-font-bold"], ["gopt-font-awesome-picker", "gopt-font-awesome"]].forEach(function(pair) {
        bindAssetPicker(pair[0], pair[1]);
    });
    var faBrowseBtn = document.getElementById("gopt-font-awesome-browse-btn");
    if (faBrowseBtn && faBrowseBtn.dataset.refacerBound !== "1") {
        faBrowseBtn.addEventListener("click", function(event) {
            event.preventDefault();
            openGlyphBrowser({theme: snap.requested_theme || snap.theme || snap.active_theme || "Default", fontInputId: "gopt-font-awesome"});
        });
        faBrowseBtn.dataset.refacerBound = "1";
    }
    ["gopt-main-text-color", "gopt-base-text-color"].forEach(function(tid) {
        var ta = document.getElementById(tid);
        var preview = document.getElementById(tid + "-preview");
        if (ta && preview) {
            ta.addEventListener("input", function() {
                preview.innerHTML = renderEditorColorSequencePreview(editorParseColorSequence(ta.value));
            });
        }
    });
    var applyBtn = goptEl("editor-global-apply-btn");
    if (applyBtn && applyBtn.dataset.refacerBound !== "1") {
        applyBtn.addEventListener("click", function(e) { e.preventDefault(); applyEditorGlobalOptionsDraft(); });
        applyBtn.dataset.refacerBound = "1";
    }
    var applyThemeBtn = goptEl("editor-global-apply-theme-btn");
    if (applyThemeBtn && applyThemeBtn.dataset.refacerBound !== "1") {
        applyThemeBtn.addEventListener("click", function(e) { e.preventDefault(); applyEditorDraftToTheme(); });
        applyThemeBtn.dataset.refacerBound = "1";
    }
    var testBootBtn = goptEl("editor-test-boot-anim-btn");
    if (testBootBtn && testBootBtn.dataset.refacerBound !== "1") {
        testBootBtn.addEventListener("click", function(e) { e.preventDefault(); testBootAnimation(); });
        testBootBtn.dataset.refacerBound = "1";
    }
}
function collectEditorGlobalForm() {
    var fontSizes = [];
    for (var i = 0; i < 6; i++) {
        var v = parseInt(goptVal("gopt-font-size-" + i), 10);
        fontSizes.push(isNaN(v) ? 12 : v);
    }
    var mainColors = parseColorSeqFromEl("gopt-main-text-color");
    var baseColors = parseColorSeqFromEl("gopt-base-text-color");
    var options = {
        bg_color:           goptVal("gopt-bg-color") || "white",
        boot_bg_color:      goptVal("gopt-boot-bg-color") || null,
        bg_image:           goptVal("gopt-bg-image") || null,
        bg_anim_image:      goptVal("gopt-bg-anim-image") || null,
        fg_image:           goptVal("gopt-fg-image") || null,
        bg_fg_select:       goptVal("gopt-bg-fg-select") || "manu",
        bg_mode:            goptVal("gopt-bg-mode") || "normal",
        fg_mode:            goptVal("gopt-fg-mode") || "normal",
        main_text_color:    mainColors.length ? mainColors : null,
        base_text_color:    baseColors.length ? baseColors : ["black"],
        color_mode:         [goptVal("gopt-color-mode-static") || "P", goptVal("gopt-color-mode-anim") || "P"],
        font:               goptVal("gopt-font") || null,
        font_bold:          goptVal("gopt-font-bold") || null,
        font_awesome:       goptVal("gopt-font-awesome") || null,
        size_offset:        parseInt(goptVal("gopt-size-offset"), 10) || 0,
        font_spacing:       parseInt(goptVal("gopt-font-spacing"), 10) || 0,
        font_sizes:         fontSizes,
        cursor:             goptVal("gopt-cursor") || "|",
        label_spacing:      parseInt(goptVal("gopt-label-spacing"), 10) || 9,
        label_line_spacing: parseInt(goptVal("gopt-label-line-spacing"), 10) || 0,
        friend_bars:        goptVal("gopt-friend-bars") || "|",
        friend_no_bars:     goptVal("gopt-friend-no-bars") || "|",
        stealth_mode:       goptChecked("gopt-stealth-mode"),
        boot_animation:     goptChecked("gopt-boot-animation"),
        boot_mode:          goptVal("gopt-boot-mode") || "stretch",
        boot_max_loops:     parseInt(goptVal("gopt-boot-max-loops"), 10) || 1,
        boot_total_duration: parseFloat(goptVal("gopt-boot-total-duration")) || 5
    };
    var dev = {
        refresh: parseInt(goptVal("gopt-dev-refresh"), 10),
        log:     goptChecked("gopt-dev-log"),
        debug:   goptChecked("gopt-dev-debug")
    };
    if (isNaN(dev.refresh)) dev.refresh = -1;
    return {options: options, dev: dev};
}
function testBootAnimation() {
    var statusEl = document.getElementById("editor-test-boot-anim-status");
    var btn = document.getElementById("editor-test-boot-anim-btn");
    if (statusEl) {
        statusEl.textContent = "Triggering...";
        statusEl.style.color = "#555";
    }
    if (btn) btn.disabled = true;
    requestJSON("POST", "editor/test_boot_animation", {}, function(body) {
        if (statusEl) {
            var msg = (body && body.message) || "Done.";
            var isNoop = body && body.status === "noop";
            statusEl.textContent = msg;
            statusEl.style.color = isNoop ? "#a40000" : "#1f5f1f";
        }
        if (btn) btn.disabled = false;
    }, null);
}
function applyEditorGlobalOptionsDraft() {
    if (!refacerEditorSnapshot) return;
    var theme = (refacerEditorSnapshot.requested_theme) || (goptEl("editor-theme-selector") || {}).value || "Default";
    if (theme === "Default") {
        setStatus("editor-global-status", "Cannot edit Default theme global options.", true);
        return;
    }
    var payload = collectEditorGlobalForm();
    requestJSON("POST", "editor/update_global_options", {
        theme: theme,
        options: payload.options,
        dev: payload.dev
    }, function(body) {
        refacerEditorSnapshot = body.snapshot || body || {};
        refreshEditorPreviewImage(refacerEditorSnapshot, function() {
            renderEditorOverlay(refacerEditorSnapshot);
            setStatus("editor-global-status", body.message || "Global options updated.", false);
        });
    }, "editor-global-status");
}
function renderEditorAssetsSummary(snapshot) {
    var panel = document.getElementById("editor-assets");
    if (!panel) return;
    var themeName = (snapshot && snapshot.active_theme) || (snapshot && snapshot.theme) || "Default";
    var isDefault = themeName === "Default";
    var assets = (snapshot && snapshot.assets) || {};
    var groups = [
        ["backgrounds",  "Backgrounds"],
        ["foregrounds",  "Foregrounds"],
        ["faces",        "Faces"],
        ["friend_faces", "Friend Faces"],
        ["widgets",      "Widgets"],
        ["icons",        "Icons"],
        ["fonts",        "Fonts"],
    ];
    var html = "<h4>Assets</h4>";
    if (isDefault) {
        html += "<p class='refacer-editor-note' style='color:#a00;margin-bottom:8px;'>Default theme is read-only. Copy it first to manage assets.</p>";
    }
    groups.forEach(function(g) {
        var key = g[0], label = g[1];
        var files = assets[key] || [];
        html += "<details class='refacer-asset-group' open data-asset-group='" + key + "'>";
        html += "<summary><strong>" + escapeEditorHtml(label) + "</strong>"
              + " <span class='refacer-editor-note'>(" + files.length + ")</span></summary>";
        if (!isDefault) {
            var acceptAttr = key === "fonts" ? ".ttf,.otf,.woff,.woff2,.fon" : "image/*";
            html += "<div class='refacer-asset-actions'>"
                  + "<label class='refacer-asset-selectall'><input type='checkbox' data-asset-selectall='" + key + "'> Select all</label>"
                  + "<button type='button' class='ui-btn ui-mini ui-corner-all' style='margin:0;' data-asset-download-bulk='" + key + "' disabled>Download Selected</button>"
                  + "<button type='button' class='ui-btn ui-mini ui-corner-all' style='margin:0;' data-asset-delete-bulk='" + key + "' disabled>Delete Selected</button>"
                  + "</div>";
            html += "<div class='refacer-asset-upload' style='margin:6px 0;display:flex;align-items:center;gap:6px;'>"
                  + "<input type='file' accept='" + acceptAttr + "' id='asset-upload-" + key + "' style='font-size:12px;'>"
                  + "<button type='button' class='ui-btn ui-mini ui-corner-all' style='margin:0;' data-asset-upload='" + key + "'>Upload</button>"
                  + "</div>";
        }
        if (!files.length) {
            html += "<p class='refacer-editor-empty'>No files.</p>";
        } else {
            html += "<div class='refacer-asset-grid'>";
            files.forEach(function(rel) {
                var assetUrl = refacerPath("theme_asset") + "?theme=" + encodeURIComponent(themeName) + "&path=" + encodeURIComponent(rel);
                var filename = rel.split("/").pop();
                html += "<div class='refacer-asset-tile' data-asset-path='" + escapeEditorHtml(rel) + "' data-asset-group='" + key + "'>";
                if (!isDefault) {
                    html += "<label class='refacer-asset-check'><input type='checkbox' data-asset-select='" + escapeEditorHtml(rel) + "' data-asset-group='" + key + "'></label>";
                }
                if (key === "fonts") {
                    html += "<a href='" + assetUrl + "' target='_blank' rel='noopener' style='display:block;padding:10px 6px;border:1px solid #ccc;background:#fff;text-decoration:none;font-weight:bold;'>"
                          + "FONT"
                          + "</a>";
                } else {
                    html += "<a href='" + assetUrl + "' target='_blank' rel='noopener'>"
                          + "<img src='" + assetUrl + "' alt='" + escapeEditorHtml(filename) + "' style='max-width:80px;max-height:80px;display:block;border:1px solid #ccc;background:#fff;'>"
                          + "</a>";
                }
                html += "<div class='refacer-editor-note' style='word-break:break-all;font-size:11px;margin-top:2px;'>" + escapeEditorHtml(filename) + "</div>";
                html += "</div>";
            });
            html += "</div>";
        }
        html += "</details>";
    });
    html += "<div id='editor-assets-status' class='refacer-status'></div>";
    panel.innerHTML = html;

    // Reset selections on every (re)render — the DOM was rebuilt.
    refacerEditorAssetSelections = {};

    // Bind upload buttons.
    panel.querySelectorAll("[data-asset-upload]").forEach(function(btn) {
        btn.addEventListener("click", function(e) {
            e.preventDefault();
            var group = btn.getAttribute("data-asset-upload");
            var input = document.getElementById("asset-upload-" + group);
            var file = input && input.files && input.files[0];
            if (!file) {
                setStatus("editor-assets-status", "Choose a file first.", true);
                return;
            }
            var fd = new FormData();
            fd.append("theme", themeName);
            fd.append("group", group);
            fd.append("asset", file);
            var xhr = new XMLHttpRequest();
            xhr.open("POST", refacerPath("editor/assets/upload"), true);
            xhr.setRequestHeader("X-CSRFToken", "{{ csrf_token() }}");
            xhr.onload = function() {
                var body = {};
                try { body = JSON.parse(xhr.responseText || "{}"); } catch (err) {}
                if (xhr.status >= 200 && xhr.status < 300) {
                    setStatus("editor-assets-status", body.message || "Uploaded.", false);
                    loadEditorSnapshot();
                } else {
                    setStatus("editor-assets-status", body.error || "Upload failed.", true);
                }
            };
            xhr.onerror = function() { setStatus("editor-assets-status", "Network error.", true); };
            xhr.send(fd);
        });
    });

    // Per-tile checkbox selection.
    panel.querySelectorAll("[data-asset-select]").forEach(function(cb) {
        cb.addEventListener("change", function() {
            var rel = cb.getAttribute("data-asset-select");
            var group = cb.getAttribute("data-asset-group");
            if (!refacerEditorAssetSelections[group]) refacerEditorAssetSelections[group] = new Set();
            if (cb.checked) { refacerEditorAssetSelections[group].add(rel); }
            else { refacerEditorAssetSelections[group].delete(rel); }
            refreshAssetGroupBar(group);
        });
    });

    // "Select all" master checkbox.
    panel.querySelectorAll("[data-asset-selectall]").forEach(function(master) {
        master.addEventListener("change", function() {
            var group = master.getAttribute("data-asset-selectall");
            var groupCbs = panel.querySelectorAll("[data-asset-select][data-asset-group='" + group + "']");
            if (!refacerEditorAssetSelections[group]) refacerEditorAssetSelections[group] = new Set();
            var set = refacerEditorAssetSelections[group];
            groupCbs.forEach(function(cb) {
                cb.checked = master.checked;
                var rel = cb.getAttribute("data-asset-select");
                if (master.checked) { set.add(rel); } else { set.delete(rel); }
            });
            refreshAssetGroupBar(group);
        });
    });

    // Bulk download.
    panel.querySelectorAll("[data-asset-download-bulk]").forEach(function(btn) {
        btn.addEventListener("click", function(e) {
            e.preventDefault();
            var group = btn.getAttribute("data-asset-download-bulk");
            var set = refacerEditorAssetSelections[group];
            if (!set || !set.size) return;
            var paths = Array.from(set);
            setStatus("editor-assets-status", "Preparing " + paths.length + " file(s)...", false);
            fetch(refacerPath("editor/assets/download_bulk"), {
                method: "POST",
                headers: {"Content-Type": "application/json", "X-CSRFToken": "{{ csrf_token() }}"},
                body: JSON.stringify({theme: themeName, paths: paths}),
            }).then(function(resp) {
                if (!resp.ok) {
                    return resp.json().then(function(body) { throw new Error(body.error || "Download failed."); });
                }
                return resp.blob().then(function(blob) {
                    var url = URL.createObjectURL(blob);
                    var a = document.createElement("a");
                    a.href = url;
                    a.download = themeName + "_assets.zip";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    setStatus("editor-assets-status", "Downloaded " + paths.length + " file(s).", false);
                });
            }).catch(function(err) {
                setStatus("editor-assets-status", err.message || "Download failed.", true);
            });
        });
    });

    // Bulk delete.
    panel.querySelectorAll("[data-asset-delete-bulk]").forEach(function(btn) {
        btn.addEventListener("click", function(e) {
            e.preventDefault();
            var group = btn.getAttribute("data-asset-delete-bulk");
            var set = refacerEditorAssetSelections[group];
            if (!set || !set.size) return;
            var paths = Array.from(set);
            if (!confirm("Delete " + paths.length + " asset(s)?")) return;
            requestJSON("POST", "editor/assets/delete_bulk", {theme: themeName, paths: paths}, function(body) {
                var isError = body.status === "partial" || body.status === "error";
                setStatus("editor-assets-status", body.message || "Deleted.", isError);
                loadEditorSnapshot();
            }, "editor-assets-status");
        });
    });
}
function refreshAssetGroupBar(groupKey) {
    var selected = refacerEditorAssetSelections[groupKey];
    var count = selected ? selected.size : 0;
    var page = currentRefacerPage();
    if (!page) return;
    var dlBtn = page.querySelector("[data-asset-download-bulk='" + groupKey + "']");
    var delBtn = page.querySelector("[data-asset-delete-bulk='" + groupKey + "']");
    if (dlBtn) {
        dlBtn.disabled = count === 0;
        dlBtn.textContent = count > 0 ? ("Download Selected (" + count + ")") : "Download Selected";
    }
    if (delBtn) {
        delBtn.disabled = count === 0;
        delBtn.textContent = count > 0 ? ("Delete Selected (" + count + ")") : "Delete Selected";
    }
    var masterCb = page.querySelector("[data-asset-selectall='" + groupKey + "']");
    if (masterCb) {
        var groupCbs = page.querySelectorAll("[data-asset-select][data-asset-group='" + groupKey + "']");
        var total = groupCbs.length;
        if (total === 0 || count === 0) {
            masterCb.checked = false; masterCb.indeterminate = false;
        } else if (count === total) {
            masterCb.checked = true; masterCb.indeterminate = false;
        } else {
            masterCb.checked = false; masterCb.indeterminate = true;
        }
    }
}
function setEditorActiveTab(tabName) {
    if (!tabName) return;
    refacerEditorActiveTab = tabName;
    var page = currentRefacerPage();
    if (!page) return;
    page.querySelectorAll("[data-editor-tab]").forEach(function(tab) {
        var active = tab.getAttribute("data-editor-tab") === tabName;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    page.querySelectorAll("[data-editor-tabpanel]").forEach(function(panel) {
        panel.classList.toggle("is-active", panel.getAttribute("data-editor-tabpanel") === tabName);
    });
}
function bindEditorTabs() {
    var page = currentRefacerPage();
    if (!page) return;
    page.querySelectorAll("[data-editor-tab]").forEach(function(tab) {
        if (tab.dataset.refacerBound === "1") return;
        tab.addEventListener("click", function(e) {
            e.preventDefault();
            setEditorActiveTab(tab.getAttribute("data-editor-tab"));
        });
        tab.dataset.refacerBound = "1";
    });
    setEditorActiveTab(refacerEditorActiveTab);
}
function editorNormalizeNewlines(text) {
    text = String(text == null ? "" : text);
    text = text.split(String.fromCharCode(13, 10)).join(String.fromCharCode(10));
    text = text.split(String.fromCharCode(13)).join(String.fromCharCode(10));
    return text;
}
function editorColorSequenceValue(colorValue) {
    if (Array.isArray(colorValue)) {
        return colorValue.join(String.fromCharCode(10));
    }
    return editorNormalizeNewlines(colorValue);
}
function editorParseColorSequence(text) {
    var normalized = editorNormalizeNewlines(text);
    var rows = normalized.split(String.fromCharCode(10));
    var values = [];
    rows.forEach(function(row) {
        String(row || "").split(",").forEach(function(part) {
            String(part || "").split(";").forEach(function(token) {
                token = String(token || "").trim();
                if (token) values.push(token);
            });
        });
    });
    return values;
}
function renderEditorColorSequencePreview(colorValue) {
    if (!Array.isArray(colorValue) || !colorValue.length) {
        return "<p class='refacer-editor-empty'>No color sequence configured.</p>";
    }
    var html = "<div class='refacer-editor-inline-list'>";
    colorValue.forEach(function(entry, index) {
        var safeText = escapeEditorHtml(entry);
        var safeCss = escapeEditorHtml(entry);
        html += "<span class='ui-mini ui-btn ui-corner-all' " +
            "style='margin:0; cursor:default; min-width:auto; padding:4px 8px;'>" +
            "<span style='display:inline-block; width:12px; height:12px; vertical-align:-1px; " +
            "margin-right:6px; border:1px solid #777; background:" + safeCss + ";'></span>" +
            safeText + " <strong>#" + (index + 1) + "</strong></span>";
    });
    html += "</div>";
    return html;
}
function renderEditorWidgetForm(widget, snapshot) {
    var panel = document.getElementById("editor-widget-properties");
    if (!panel) return;
    if (!widget) {
        panel.innerHTML = "<h4>Widget Properties</h4><p class='refacer-editor-empty'>Select a widget to inspect its editable draft fields.</p>";
        return;
    }
    var editable = widget.editable || {};
    var position = Array.isArray(editable.position) ? editable.position : [];
    var positionMode = editable.position_mode || position.length || 0;
    var colorValue = Array.isArray(editable.color) ? editable.color : (editable.color ? [editable.color] : []);
    var fontOptions = refacerEditorFontSizes.map(function(name) {
        var sel = String(editable.text_font_size || "") === name ? " selected" : "";
        return "<option value='" + escapeEditorHtml(name) + "'" + sel + ">" + escapeEditorHtml(name || "Default") + "</option>";
    }).join("");
    var labelFontOptions = refacerEditorFontSizes.map(function(name) {
        var sel = String(editable.label_font_size || "") === name ? " selected" : "";
        return "<option value='" + escapeEditorHtml(name) + "'" + sel + ">" + escapeEditorHtml(name || "Default") + "</option>";
    }).join("");
    var html = "<h4>Widget Properties</h4>";
    html += renderEditorRows([
        ["Widget Type", editable.widget_type || "Unknown"],
        ["Theme Fields", (widget.theme_fields || []).join(", ") || "None"],
        ["Position", position.join(", ") || "None"],
        ["BBox", widget.bbox ? widget.bbox.join(", ") : "None"]
    ]);
    html += "<form id='editor-widget-form' class='refacer-editor-form'>";
    html += "<p class='refacer-editor-note'>Draft preview only. Changes here are not saved to theme files yet.</p>";

    // --- Layout section (always visible, no details wrapper) ---
    if (positionMode >= 4) {
        html += "<div><label for='editor-position-raw'>Position</label><input type='text' id='editor-position-raw' value='" + escapeEditorHtml(position.join(", ")) + "'></div>";
    } else {
        html += "<div class='refacer-editor-form-grid'>";
        html += "<div><label for='editor-position-x'>X</label><input type='text' id='editor-position-x' value='" + escapeEditorHtml(position[0] != null ? position[0] : "") + "'></div>";
        html += "<div><label for='editor-position-y'>Y</label><input type='text' id='editor-position-y' value='" + escapeEditorHtml(position[1] != null ? position[1] : "") + "'></div>";
        html += "</div>";
    }
    html += "<div><label for='editor-color-sequence'>Color Sequence</label>" +
        "<textarea id='editor-color-sequence' rows='3' class='refacer-textarea' " +
        "style='min-height:86px; white-space:pre-wrap;'>" + escapeEditorHtml(editorColorSequenceValue(colorValue)) + "</textarea>" +
        "<p class='refacer-editor-note'>One color per line. You can also use commas on one line.</p>" +
        renderEditorColorSequencePreview(colorValue) + "</div>";
    html += "<div class='refacer-editor-form-grid'>";
    html += "<div><label for='editor-z-axis'>Z Axis</label><input type='number' id='editor-z-axis' value='" + escapeEditorHtml(editable.z_axis != null ? editable.z_axis : 0) + "'></div>";
    if (editable.width !== undefined) {
        html += "<div><label for='editor-width'>Width</label><input type='number' id='editor-width' value='" + escapeEditorHtml(editable.width != null ? editable.width : "") + "'></div>";
    }
    if (editable.height !== undefined) {
        html += "<div><label for='editor-height'>Height</label><input type='number' id='editor-height' value='" + escapeEditorHtml(editable.height != null ? editable.height : "") + "'></div>";
    }
    html += "</div>";

    // --- Text section ---
    if (editable.text_font_size !== undefined) {
        html += "<details class='refacer-editor-widgetgroup' open>";
        html += "<summary><strong>Text</strong></summary>";
        html += "<div class='refacer-editor-form-grid'>";
        html += "<div><label for='editor-text-font-size'>Font Size</label><select id='editor-text-font-size'>" + fontOptions + "</select></div>";
        if (editable.text_font !== undefined) {
            html += "<div><label for='editor-text-font'>Font File</label><input type='text' id='editor-text-font' value='" + escapeEditorHtml(editable.text_font || "") + "'>" + buildFontPicker("editor-text-font-picker", editable.text_font || "", snapshot, "") + "</div>";
        }
        if (editable.size_offset !== undefined) {
            html += "<div><label for='editor-size-offset'>Size Offset</label><input type='number' id='editor-size-offset' value='" + escapeEditorHtml(String(editable.size_offset != null ? editable.size_offset : 0)) + "'></div>";
        }
        if (editable.font_spacing !== undefined) {
            html += "<div><label for='editor-font-spacing'>Font Spacing</label><input type='number' id='editor-font-spacing' value='" + escapeEditorHtml(String(editable.font_spacing != null ? editable.font_spacing : 0)) + "'></div>";
        }
        if (editable.max_length !== undefined) {
            html += "<div><label for='editor-max-length'>Max Length</label><input type='number' id='editor-max-length' value='" + escapeEditorHtml(String(editable.max_length != null ? editable.max_length : 0)) + "'></div>";
        }
        html += "</div>";
        if (editable.wrap !== undefined) {
            html += "<div><label><input type='checkbox' id='editor-wrap'" + (editable.wrap ? " checked" : "") + "> Wrap Text</label></div>";
        }
        html += "</details>";
    }

    // --- Label section ---
    if (editable.label_font_size !== undefined) {
        html += "<details class='refacer-editor-widgetgroup'>";
        html += "<summary><strong>Label</strong></summary>";
        if (editable.label !== undefined) {
            html += "<div><label for='editor-label'>Label Text</label><input type='text' id='editor-label' value='" + escapeEditorHtml(editable.label || "") + "'><button type='button' id='editor-label-fa-browse-btn' class='ui-btn ui-mini ui-corner-all' style='margin-top:6px;'>Pick FA label glyph</button><p class='refacer-editor-note'>For label icons, the picker inserts the Font Awesome code token expected by the renderer.</p></div>";
        }
        html += "<div class='refacer-editor-form-grid'>";
        html += "<div><label for='editor-label-font-size'>Label Font Size</label><select id='editor-label-font-size'>" + labelFontOptions + "</select></div>";
        if (editable.label_font !== undefined) {
            html += "<div><label for='editor-label-font'>Label Font File</label><input type='text' id='editor-label-font' value='" + escapeEditorHtml(editable.label_font || "") + "'>" + buildFontPicker("editor-label-font-picker", editable.label_font || "", snapshot, "") + "</div>";
        }
        if (editable.label_spacing !== undefined) {
            html += "<div><label for='editor-label-spacing'>Label Spacing</label><input type='number' id='editor-label-spacing' value='" + escapeEditorHtml(String(editable.label_spacing != null ? editable.label_spacing : 9)) + "'></div>";
        }
        if (editable.label_line_spacing !== undefined) {
            html += "<div><label for='editor-label-line-spacing'>Label Line Spacing</label><input type='number' id='editor-label-line-spacing' value='" + escapeEditorHtml(String(editable.label_line_spacing != null ? editable.label_line_spacing : 0)) + "'></div>";
        }
        html += "</div>";
        html += "</details>";
    }

    // --- Image / Icon section ---
    var hasImageBlock = (editable.image_type !== undefined || editable.icon !== undefined || editable.invert !== undefined);
    if (hasImageBlock) {
        var widgetAssetFields = [
            { key: "bg_image", inputId: "editor-bg-image", pickerId: "editor-bg-image-picker", label: "BG Image", groups: ["backgrounds"] },
            { key: "button_bg_image", inputId: "editor-button-bg-image", pickerId: "editor-button-bg-image-picker", label: "Button BG Image", groups: ["widgets", "backgrounds"] },
            { key: "highlight_button_bg_image", inputId: "editor-highlight-button-bg-image", pickerId: "editor-highlight-button-bg-image-picker", label: "Highlight Button BG Image", groups: ["widgets", "backgrounds"] }
        ];
        html += "<details class='refacer-editor-widgetgroup'>";
        html += "<summary><strong>Image / Icon</strong></summary>";

        if (editable.icon !== undefined) {
            var iconEnabled = editable.icon !== false && editable.icon !== "" && editable.icon != null;
            var iconValue = iconEnabled ? String(editable.icon) : "";
            html += "<div class='refacer-editor-form-grid'>";
            html += "<div><label><input type='checkbox' id='editor-icon-enable'" + (iconEnabled ? " checked" : "") + "> Enable Icon</label></div>";
            html += "<div><label for='editor-icon'>Icon Path/Name</label><input type='text' id='editor-icon' value='" + escapeEditorHtml(iconValue) + "'>" + buildAssetPicker("editor-icon-picker", ["widgets", "icons"], iconValue, snapshot, "") + "</div>";
            html += "</div>";
        }
        widgetAssetFields.forEach(function(field) {
            if (editable[field.key] === undefined) return;
            html += "<div><label for='" + field.inputId + "'>" + field.label + "</label><input type='text' id='" + field.inputId + "' value='" + escapeEditorHtml(editable[field.key] || "") + "'>" + buildAssetPicker(field.pickerId, field.groups, editable[field.key] || "", snapshot, "") + "</div>";
        });

        if (editable.f_awesome !== undefined) {
            var faEnabled = editable.f_awesome !== false && editable.f_awesome !== "" && editable.f_awesome != null;
            var faValue = faEnabled ? String(editable.f_awesome) : "";
            html += "<div class='refacer-editor-form-grid'>";
            html += "<div><label><input type='checkbox' id='editor-f-awesome-enable'" + (faEnabled ? " checked" : "") + "> Enable Font Awesome</label></div>";
            html += "<div><label for='editor-f-awesome'>Glyph</label><input type='text' id='editor-f-awesome' value='" + escapeEditorHtml(faValue) + "'><button type='button' id='editor-f-awesome-browse-btn' class='ui-btn ui-mini ui-corner-all' style='margin-top:6px;'>Pick glyph</button></div>";
            if (editable.f_awesome_size !== undefined) {
                html += "<div><label for='editor-f-awesome-size'>FA Size</label><input type='number' id='editor-f-awesome-size' value='" + escapeEditorHtml(String(editable.f_awesome_size != null ? editable.f_awesome_size : 0)) + "'></div>";
            }
            html += "</div>";
        }

        html += "<div class='refacer-editor-form-grid'>";
        if (editable.icon_color !== undefined) {
            html += "<div><label><input type='checkbox' id='editor-icon-color'" + (editable.icon_color ? " checked" : "") + "> Icon Color</label></div>";
        }
        if (editable.invert !== undefined) {
            html += "<div><label><input type='checkbox' id='editor-invert'" + (editable.invert ? " checked" : "") + "> Invert</label></div>";
        }
        if (editable.alpha !== undefined) {
            html += "<div><label><input type='checkbox' id='editor-alpha'" + (editable.alpha ? " checked" : "") + "> Alpha</label></div>";
        }
        if (editable.mask !== undefined) {
            html += "<div><label><input type='checkbox' id='editor-mask'" + (editable.mask ? " checked" : "") + "> Mask</label></div>";
        }
        html += "</div>";

        if (editable.crop !== undefined) {
            var crop = Array.isArray(editable.crop) ? editable.crop : [0, 0, 0, 0];
            html += "<div><label>Crop [left, top, right, bottom]</label>";
            html += "<div class='refacer-editor-form-grid' style='grid-template-columns: repeat(4, 1fr);'>";
            [0, 1, 2, 3].forEach(function(i) {
                html += "<input type='number' id='editor-crop-" + i + "' value='" + escapeEditorHtml(String(crop[i] != null ? crop[i] : 0)) + "' style='min-width:0;'>";
            });
            html += "</div></div>";
        }

        html += "<div class='refacer-editor-form-grid'>";
        if (editable.refine !== undefined) {
            html += "<div><label for='editor-refine'>Refine (0-255)</label><input type='number' id='editor-refine' min='0' max='255' value='" + escapeEditorHtml(String(editable.refine != null ? editable.refine : 150)) + "'></div>";
        }
        if (editable.zoom !== undefined) {
            html += "<div><label for='editor-zoom'>Zoom</label><input type='number' id='editor-zoom' step='0.1' value='" + escapeEditorHtml(String(editable.zoom != null ? editable.zoom : 1)) + "'></div>";
        }
        if (editable.image_type !== undefined) {
            var imgTypes = ['png', 'jpg', 'jpeg', 'bmp', 'gif', 'webp'];
            var imgOptions = imgTypes.map(function(t) {
                var sel = String(editable.image_type || "").toLowerCase() === t ? " selected" : "";
                return "<option value='" + t + "'" + sel + ">" + t + "</option>";
            }).join("");
            html += "<div><label for='editor-image-type'>Image Type</label><select id='editor-image-type'>" + imgOptions + "</select></div>";
        }
        html += "</div>";

        html += "</details>";
    }

    html += "<div class='refacer-actions'>" +
        "<button type='button' id='editor-apply-btn' class='ui-btn ui-btn-b ui-corner-all'>Apply to Preview</button>" +
        "<button type='button' id='editor-apply-theme-btn' class='ui-btn ui-corner-all'>Apply to Theme</button>" +
        "<button type='button' id='editor-reset-draft-btn' class='ui-btn ui-corner-all'>Reset Draft</button>" +
        "</div>";
    html += "</form>";
    panel.innerHTML = html;
    enhanceRefacerWidgets();
    [["editor-icon-picker", "editor-icon"], ["editor-bg-image-picker", "editor-bg-image"], ["editor-button-bg-image-picker", "editor-button-bg-image"], ["editor-highlight-button-bg-image-picker", "editor-highlight-button-bg-image"]].forEach(function(pair) {
        bindAssetPicker(pair[0], pair[1]);
    });
    [["editor-text-font-picker", "editor-text-font"], ["editor-label-font-picker", "editor-label-font"]].forEach(function(pair) {
        bindAssetPicker(pair[0], pair[1]);
    });
    var faPickBtn = document.getElementById("editor-f-awesome-browse-btn");
    if (faPickBtn && faPickBtn.dataset.refacerBound !== "1") {
        faPickBtn.addEventListener("click", function(event) {
            event.preventDefault();
            openGlyphBrowser({
                theme: (snapshot && (snapshot.requested_theme || snapshot.theme || snapshot.active_theme)) || "Default",
                fontInputId: "gopt-font-awesome",
                targetInputId: "editor-f-awesome",
                insertMode: "glyph-char"
            });
        });
        faPickBtn.dataset.refacerBound = "1";
    }
    var faLabelPickBtn = document.getElementById("editor-label-fa-browse-btn");
    if (faLabelPickBtn && faLabelPickBtn.dataset.refacerBound !== "1") {
        faLabelPickBtn.addEventListener("click", function(event) {
            event.preventDefault();
            openGlyphBrowser({
                theme: (snapshot && (snapshot.requested_theme || snapshot.theme || snapshot.active_theme)) || "Default",
                fontInputId: "gopt-font-awesome",
                targetInputId: "editor-label",
                insertMode: "label-code"
            });
        });
        faLabelPickBtn.dataset.refacerBound = "1";
    }
    var applyBtn = document.getElementById("editor-apply-btn");
    if (applyBtn && applyBtn.dataset.refacerBound !== "1") {
        applyBtn.addEventListener("click", function(event) {
            event.preventDefault();
            applyEditorWidgetDraft();
        });
        applyBtn.dataset.refacerBound = "1";
    }
    var applyThemeBtn = document.getElementById("editor-apply-theme-btn");
    if (applyThemeBtn && applyThemeBtn.dataset.refacerBound !== "1") {
        applyThemeBtn.addEventListener("click", function(event) {
            event.preventDefault();
            applyEditorDraftToTheme();
        });
        applyThemeBtn.dataset.refacerBound = "1";
    }
    var resetBtn = document.getElementById("editor-reset-draft-btn");
    if (resetBtn && resetBtn.dataset.refacerBound !== "1") {
        resetBtn.addEventListener("click", function(event) {
            event.preventDefault();
            resetEditorDraft();
        });
        resetBtn.dataset.refacerBound = "1";
    }
}
function renderSelectedWidgetInspector(widget, snapshot) {
    renderEditorSelectedWidgetSummary(widget);
    renderEditorWidgetForm(widget, snapshot || {});
    renderEditorThemeSummary(snapshot || {});
    renderEditorAssetsSummary(snapshot || {});
}
function collectEditorWidgetFormPatch(widget) {
    if (!widget) return {};
    var patch = {};
    var editable = widget.editable || {};

    function readText(id) { var el = document.getElementById(id); return el ? el.value : undefined; }
    function readCheck(id) { var el = document.getElementById(id); return el ? !!el.checked : undefined; }
    function setIf(key, value) { if (value !== undefined) patch[key] = value; }

    // Position
    if ((editable.position_mode || 0) >= 4) {
        patch.position = readText("editor-position-raw") || "";
    } else {
        patch.position = [readText("editor-position-x"), readText("editor-position-y")];
    }

    // Color
    patch.color = editorParseColorSequence((document.getElementById("editor-color-sequence") || {}).value || "");

    // Layout
    setIf("z_axis",  readText("editor-z-axis"));
    setIf("width",   readText("editor-width"));
    setIf("height",  readText("editor-height"));

    // Text
    setIf("text_font_size", readText("editor-text-font-size"));
    setIf("text_font",      readText("editor-text-font"));
    setIf("size_offset",    readText("editor-size-offset"));
    setIf("font_spacing",   readText("editor-font-spacing"));
    setIf("max_length",     readText("editor-max-length"));
    setIf("wrap",           readCheck("editor-wrap"));

    // Label
    setIf("label",               readText("editor-label"));
    setIf("label_font_size",     readText("editor-label-font-size"));
    setIf("label_font",          readText("editor-label-font"));
    setIf("label_spacing",       readText("editor-label-spacing"));
    setIf("label_line_spacing",  readText("editor-label-line-spacing"));

    // Icon tri-state
    var iconEnable = document.getElementById("editor-icon-enable");
    if (iconEnable) {
        var iconText = readText("editor-icon");
        patch.icon = iconEnable.checked ? (iconText || true) : false;
    }

    // Font Awesome tri-state
    var faEnable = document.getElementById("editor-f-awesome-enable");
    if (faEnable) {
        var faText = readText("editor-f-awesome");
        patch.f_awesome = faEnable.checked ? (faText || true) : false;
    }
    setIf("f_awesome_size", readText("editor-f-awesome-size"));

    // Boolean image flags
    setIf("icon_color", readCheck("editor-icon-color"));
    setIf("invert",     readCheck("editor-invert"));
    setIf("alpha",      readCheck("editor-alpha"));
    setIf("mask",       readCheck("editor-mask"));

    // Crop
    if (document.getElementById("editor-crop-0")) {
        patch.crop = [0, 1, 2, 3].map(function(i) { return readText("editor-crop-" + i); });
    }

    // Image controls
    setIf("refine",      readText("editor-refine"));
    setIf("zoom",        readText("editor-zoom"));
    setIf("image_type",  readText("editor-image-type"));
    setIf("bg_image",    readText("editor-bg-image"));
    setIf("button_bg_image", readText("editor-button-bg-image"));
    setIf("highlight_button_bg_image", readText("editor-highlight-button-bg-image"));

    return patch;
}
function editorFindSelectedWidget() {
    if (!refacerEditorSnapshot || !refacerEditorSelectedKey) return null;
    for (var i = 0; i < (refacerEditorSnapshot.widgets || []).length; i++) {
        if (refacerEditorSnapshot.widgets[i].key === refacerEditorSelectedKey) {
            return refacerEditorSnapshot.widgets[i];
        }
    }
    return null;
}
function editorWidgetIsDraggable(widget) {
    if (!widget || !widget.editable) return false;
    var position = widget.editable.position;
    if (!Array.isArray(position) || position.length !== 2) return false;
    var x = position[0];
    var y = position[1];
    return !isNaN(parseFloat(x)) && isFinite(x) && !isNaN(parseFloat(y)) && isFinite(y);
}
function editorGetStageMetrics() {
    var image = document.getElementById("editor-preview-image");
    var overlay = document.getElementById("editor-preview-overlay");
    if (!image || !overlay || !refacerEditorSnapshot || !refacerEditorSnapshot.canvas) return null;
    var rect = overlay.getBoundingClientRect();
    var canvasWidth = Math.max(1, parseInt(refacerEditorSnapshot.canvas.width || 1, 10));
    var canvasHeight = Math.max(1, parseInt(refacerEditorSnapshot.canvas.height || 1, 10));
    var displayWidth = image.clientWidth || image.naturalWidth || canvasWidth;
    var displayHeight = image.clientHeight || image.naturalHeight || canvasHeight;
    return {
        rect: rect,
        scaleX: displayWidth / canvasWidth,
        scaleY: displayHeight / canvasHeight
    };
}
function editorUpdateDraggedPositionPreview(nextX, nextY) {
    var xInput = document.getElementById("editor-position-x");
    var yInput = document.getElementById("editor-position-y");
    if (xInput) xInput.value = String(nextX);
    if (yInput) yInput.value = String(nextY);
}
function editorUpdateDraggedBoxPreview(nextX, nextY) {
    if (!refacerEditorDragState || !refacerEditorDragState.boxEl) return;
    var box = refacerEditorDragState.boxEl;
    var width = Math.max(1, refacerEditorDragState.boxWidth || 1);
    var height = Math.max(1, refacerEditorDragState.boxHeight || 1);
    var left = Math.round(nextX * refacerEditorDragState.scaleX);
    var top = Math.round(nextY * refacerEditorDragState.scaleY);
    box.style.left = left + "px";
    box.style.top = top + "px";
    box.style.width = width + "px";
    box.style.height = height + "px";
}
function editorApplyDragPreview(nextX, nextY) {
    editorUpdateDraggedPositionPreview(nextX, nextY);
    editorUpdateDraggedBoxPreview(nextX, nextY);
}
function editorConsumeDragClick() {
    if (!refacerEditorDragJustEnded) return false;
    refacerEditorDragJustEnded = false;
    return true;
}
function editorDragDistance(clientX, clientY) {
    if (!refacerEditorDragState) return 0;
    var dx = clientX - refacerEditorDragState.startClientX;
    var dy = clientY - refacerEditorDragState.startClientY;
    return Math.sqrt((dx * dx) + (dy * dy));
}
function editorMarkOverlayDragging(enabled) {
    var overlay = document.getElementById("editor-preview-overlay");
    if (!overlay) return;
    if (enabled) overlay.classList.add("is-dragging");
    else overlay.classList.remove("is-dragging");
}
function beginEditorWidgetDrag(event, widget) {
    if (!editorWidgetIsDraggable(widget)) return;
    var metrics = editorGetStageMetrics();
    if (!metrics) return;
    var position = widget.editable.position;
    refacerEditorDragState = {
        widgetKey: widget.key,
        startClientX: event.clientX,
        startClientY: event.clientY,
        startX: parseFloat(position[0]),
        startY: parseFloat(position[1]),
        liveX: parseFloat(position[0]),
        liveY: parseFloat(position[1]),
        scaleX: metrics.scaleX,
        scaleY: metrics.scaleY,
        moved: false,
        pointerId: event.pointerId,
        boxEl: event.currentTarget || null,
        boxWidth: event.currentTarget ? event.currentTarget.offsetWidth : 0,
        boxHeight: event.currentTarget ? event.currentTarget.offsetHeight : 0
    };
    document.body.classList.add("refacer-editor-dragging");
    var box = event.currentTarget;
    if (box) box.classList.add("is-dragging");
    editorMarkOverlayDragging(true);
    if (box && box.setPointerCapture && event.pointerId != null) {
        try { box.setPointerCapture(event.pointerId); } catch (e) {}
    }
    event.preventDefault();
    event.stopPropagation();
}
function updateEditorWidgetDrag(event) {
    if (!refacerEditorDragState) return;
    if (event.pointerId != null && refacerEditorDragState.pointerId != null && event.pointerId !== refacerEditorDragState.pointerId) return;
    var deltaX = (event.clientX - refacerEditorDragState.startClientX) / Math.max(0.0001, refacerEditorDragState.scaleX);
    var deltaY = (event.clientY - refacerEditorDragState.startClientY) / Math.max(0.0001, refacerEditorDragState.scaleY);
    var nextX = Math.round(refacerEditorDragState.startX + deltaX);
    var nextY = Math.round(refacerEditorDragState.startY + deltaY);
    refacerEditorDragState.liveX = nextX;
    refacerEditorDragState.liveY = nextY;
    if (editorDragDistance(event.clientX, event.clientY) >= 2) {
        refacerEditorDragState.moved = true;
    }
    editorApplyDragPreview(nextX, nextY);
    event.preventDefault();
    event.stopPropagation();
}
function endEditorWidgetDrag(event) {
    if (!refacerEditorDragState) return;
    if (event && event.pointerId != null && refacerEditorDragState.pointerId != null && event.pointerId !== refacerEditorDragState.pointerId) return;
    var dragState = refacerEditorDragState;
    var draggedKey = refacerEditorDragState.widgetKey;
    var boxEl = dragState.boxEl;
    if (boxEl && boxEl.releasePointerCapture && dragState.pointerId != null) {
        try { boxEl.releasePointerCapture(dragState.pointerId); } catch (e) {}
    }
    refacerEditorDragState = null;
    document.body.classList.remove("refacer-editor-dragging");
    editorMarkOverlayDragging(false);
    var draggingBox = document.querySelector(".refacer-editor-box.is-dragging");
    if (draggingBox) draggingBox.classList.remove("is-dragging");
    refacerEditorDragJustEnded = !!dragState.moved;
    if (draggedKey && draggedKey === refacerEditorSelectedKey && dragState.moved) {
        applyEditorWidgetDraft();
    }
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
}
function cancelEditorWidgetDrag() {
    if (!refacerEditorDragState) return;
    refacerEditorDragState = null;
    document.body.classList.remove("refacer-editor-dragging");
    editorMarkOverlayDragging(false);
    var draggingBox = document.querySelector(".refacer-editor-box.is-dragging");
    if (draggingBox) draggingBox.classList.remove("is-dragging");
}
function bindEditorGlobalDragHandlers() {
    if (document.body.dataset.refacerEditorDragBound === "1") return;
    document.addEventListener("pointermove", function(event) {
        if (!refacerEditorDragState) return;
        updateEditorWidgetDrag(event);
    }, true);
    document.addEventListener("dragstart", function(event) {
        if (!refacerEditorDragState) return;
        event.preventDefault();
    });
    document.addEventListener("pointerup", function(event) {
        if (!refacerEditorDragState) return;
        endEditorWidgetDrag(event);
    }, true);
    document.addEventListener("pointercancel", function() {
        cancelEditorWidgetDrag();
    });
    document.body.dataset.refacerEditorDragBound = "1";
}
function refreshEditorPreviewImage(snapshot, onReady) {
    var preview = document.getElementById("editor-preview-image");
    if (!preview) {
        if (onReady) onReady();
        return;
    }
    var stage = preview.parentElement;
    if (snapshot && snapshot.canvas) {
        var logicalWidth = Math.max(1, parseInt(snapshot.canvas.width || 1, 10));
        var logicalHeight = Math.max(1, parseInt(snapshot.canvas.height || 1, 10));
        preview.width = logicalWidth;
        preview.height = logicalHeight;
        preview.setAttribute("width", String(logicalWidth));
        preview.setAttribute("height", String(logicalHeight));
        preview.style.aspectRatio = logicalWidth + " / " + logicalHeight;
        if (stage) {
            stage.style.aspectRatio = logicalWidth + " / " + logicalHeight;
        }
    }
    var previewPath = (snapshot && snapshot.preview_url) || "preview_frame";
    preview.onload = function() {
        preview.onload = null;
        if (onReady) onReady();
    };
    preview.src = refacerPath(previewPath) + (previewPath.indexOf("?") === -1 ? "?t=" : "&t=") + Date.now();
}
function applyEditorWidgetDraft() {
    if (!refacerEditorSnapshot || !refacerEditorSelectedKey) return;
    var widget = null;
    for (var i = 0; i < (refacerEditorSnapshot.widgets || []).length; i++) {
        if (refacerEditorSnapshot.widgets[i].key === refacerEditorSelectedKey) {
            widget = refacerEditorSnapshot.widgets[i];
            break;
        }
    }
    if (!widget) return;
    requestJSON("POST", "editor/update_widget_draft", {
        theme: (refacerEditorSnapshot && refacerEditorSnapshot.requested_theme) || (document.getElementById("editor-theme-selector") || {}).value || "Default",
        widget: widget.key,
        patch: collectEditorWidgetFormPatch(widget)
    }, function(body) {
        refacerEditorSnapshot = body.snapshot || body || {};
        refreshEditorPreviewImage(refacerEditorSnapshot, function() {
            renderEditorOverlay(refacerEditorSnapshot);
            setStatus("editor-status", body.message || "Draft updated for preview.", false);
        });
    }, "editor-status");
}
function applyEditorDraftToTheme() {
    var theme = (refacerEditorSnapshot && refacerEditorSnapshot.requested_theme) || (document.getElementById("editor-theme-selector") || {}).value || "Default";
    requestJSON("POST", "editor/apply_draft", {theme: theme}, function(body) {
        refacerEditorSnapshot = body.snapshot || body || {};
        if (body.selected_widget_key) {
            refacerEditorSelectedKey = body.selected_widget_key;
        }
        refreshEditorPreviewImage(refacerEditorSnapshot, function() {
            renderEditorOverlay(refacerEditorSnapshot);
            setStatus("editor-status", body.message || "Theme draft applied.", false);
        });
        var managerSelector = document.getElementById("theme-selector");
        if (managerSelector) managerSelector.value = theme;
        document.getElementById("active-theme").textContent = theme;
        loadConfiguration(theme);
        loadThemeInfo(theme);
        loadDiagnostics();
        refreshPreview();
    }, "editor-status");
}
function resetEditorDraft() {
    var theme = (document.getElementById("editor-theme-selector") || {}).value || "Default";
    requestJSON("POST", "editor/reset_draft", {theme: theme}, function(body) {
        refacerEditorSnapshot = body.snapshot || body || {};
        refacerEditorSelectedKey = null;
        if (refacerEditorKeyMoveState && refacerEditorKeyMoveState.timer) clearTimeout(refacerEditorKeyMoveState.timer);
        refacerEditorKeyMoveState = null;
        refreshEditorPreviewImage(refacerEditorSnapshot, function() {
            renderEditorOverlay(refacerEditorSnapshot);
        });
        refacerEditorDragJustEnded = false;
        syncEditorOverlayVisibility();
        cancelEditorWidgetDrag();
        setStatus("editor-status", body.message || "Draft reset.", false);
    }, "editor-status");
}
function selectEditorWidget(widgetKey) {
    if (refacerEditorKeyMoveState && refacerEditorKeyMoveState.timer) {
        clearTimeout(refacerEditorKeyMoveState.timer);
    }
    refacerEditorKeyMoveState = null;
    refacerEditorSelectedKey = widgetKey || null;
    renderEditorOverlay(refacerEditorSnapshot);
    if (widgetKey) setEditorActiveTab("widget");
}
function renderEditorOverlay(snapshot) {
    refacerEditorSnapshot = snapshot || null;
    var image = document.getElementById("editor-preview-image");
    var overlay = document.getElementById("editor-preview-overlay");
    syncEditorOverlayVisibility();
    if (!image || !overlay) return;
    overlay.innerHTML = "";
    if (!snapshot || !snapshot.canvas || !snapshot.widgets) {
        renderSelectedWidgetInspector(null, snapshot || {});
        return;
    }
    var canvasWidth = Math.max(1, parseInt(snapshot.canvas.width || 1, 10));
    var canvasHeight = Math.max(1, parseInt(snapshot.canvas.height || 1, 10));
    var displayWidth = image.clientWidth || image.naturalWidth || canvasWidth;
    var displayHeight = image.clientHeight || image.naturalHeight || canvasHeight;
    var scaleX = displayWidth / canvasWidth;
    var scaleY = displayHeight / canvasHeight;
    renderEditorWidgetDropdown(snapshot);
    var selected = null;
    snapshot.widgets.forEach(function(widget) {
        if (!widget || !widget.bbox || widget.bbox.length !== 4) return;
        var isHiddenWidget = widget.visible === false;
        var isNegativeZ = !isHiddenWidget && widget.z_axis != null && parseFloat(widget.z_axis) < 0;
        var x1 = Math.max(0, widget.bbox[0] * scaleX);
        var y1 = Math.max(0, widget.bbox[1] * scaleY);
        var x2 = Math.max(x1 + 1, widget.bbox[2] * scaleX);
        var y2 = Math.max(y1 + 1, widget.bbox[3] * scaleY);
        var box = document.createElement("div");
        box.className = "refacer-editor-box"
            + (widget.key === refacerEditorSelectedKey ? " is-selected" : "")
            + (isHiddenWidget ? " is-hidden-widget" : "")
            + (isNegativeZ ? " is-negative-z" : "");
        box.style.left = x1 + "px";
        box.style.top = y1 + "px";
        box.style.width = Math.max(1, x2 - x1) + "px";
        box.style.height = Math.max(1, y2 - y1) + "px";
        box.dataset.widgetKey = widget.key;
        box.title = widget.key + " (" + (widget.widget_type || "Widget") + ")";
        box.dataset.x1 = String(widget.bbox[0]);
        box.dataset.y1 = String(widget.bbox[1]);
        if (editorWidgetIsDraggable(widget)) {
            box.className += " is-draggable";
            box.dataset.draggable = "1";
            box.addEventListener("pointerdown", function(event) {
                if (widget.key !== refacerEditorSelectedKey) {
                    refacerEditorDragJustEnded = false;
                    selectEditorWidget(widget.key);
                    return;
                }
                beginEditorWidgetDrag(event, widget);
            });
        }
        box.addEventListener("click", function(event) {
            if (refacerEditorDragState || editorConsumeDragClick()) return;
            event.preventDefault();
            event.stopPropagation();
            selectEditorWidget(widget.key);
        });
        var label = document.createElement("div");
        label.className = "refacer-editor-box-label";
        label.style.pointerEvents = "none";
        label.textContent = widget.key;
        box.appendChild(label);
        overlay.appendChild(box);
        if (widget.key === refacerEditorSelectedKey) selected = widget;
    });
    if (!selected && snapshot.widgets.length) {
        selected = null;
        for (var i = 0; i < snapshot.widgets.length; i++) {
            var candidate = snapshot.widgets[i];
            if (candidate && candidate.visible !== false && candidate.bbox && candidate.bbox.length === 4) {
                selected = candidate;
                break;
            }
        }
    }
    if (!selected && snapshot.widgets.length) {
        renderSelectedWidgetInspector(null, snapshot);
        return;
    }
    if (!selected && !snapshot.widgets.length) {
        renderSelectedWidgetInspector(null, snapshot);
        return;
    }
    if (selected && selected.key !== refacerEditorSelectedKey) {
        refacerEditorSelectedKey = selected.key;
        renderEditorOverlay(snapshot);
        return;
    }
    renderSelectedWidgetInspector(selected, snapshot);
}
function renderEditorWidgetDropdown(snapshot) {
    var select = document.getElementById("editor-widget-selector");
    if (!select) return;
    var previousKey = refacerEditorSelectedKey;
    select.innerHTML = "";
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "\u2014 Select widget \u2014";
    select.appendChild(placeholder);
    if (!snapshot || !snapshot.widgets || !snapshot.widgets.length) return;
    snapshot.widgets.forEach(function(widget) {
        if (!widget || !widget.key) return;
        var option = document.createElement("option");
        option.value = widget.key;
        var label = widget.key;
        var flags = [];
        if (widget.visible === false) flags.push("hidden");
        if (widget.z_axis != null && parseFloat(widget.z_axis) < 0) flags.push("z<0");
        if (flags.length) label += " [" + flags.join(", ") + "]";
        option.textContent = label;
        if (widget.key === previousKey) option.selected = true;
        select.appendChild(option);
    });
    if (previousKey) select.value = previousKey;
}
var refacerEditorKeyMoveState = null;
function editorKeyboardMove(dx, dy) {
    if (!refacerEditorSelectedKey || !refacerEditorSnapshot) return;
    var widget = editorFindSelectedWidget();
    if (!widget || !editorWidgetIsDraggable(widget)) return;
    var xInput = document.getElementById("editor-position-x");
    var yInput = document.getElementById("editor-position-y");
    if (!xInput || !yInput) return;
    if (!refacerEditorKeyMoveState || refacerEditorKeyMoveState.widgetKey !== refacerEditorSelectedKey) {
        refacerEditorKeyMoveState = {
            widgetKey: refacerEditorSelectedKey,
            liveX: parseFloat(xInput.value) || parseFloat((widget.editable.position || [])[0]) || 0,
            liveY: parseFloat(yInput.value) || parseFloat((widget.editable.position || [])[1]) || 0,
            timer: null
        };
    }
    refacerEditorKeyMoveState.liveX = Math.round(refacerEditorKeyMoveState.liveX + dx);
    refacerEditorKeyMoveState.liveY = Math.round(refacerEditorKeyMoveState.liveY + dy);
    xInput.value = String(refacerEditorKeyMoveState.liveX);
    yInput.value = String(refacerEditorKeyMoveState.liveY);
    var metrics = editorGetStageMetrics();
    if (metrics) {
        var selectedBox = document.querySelector(".refacer-editor-box.is-selected");
        if (selectedBox) {
            selectedBox.style.left = (parseFloat(selectedBox.style.left) || 0) + dx * metrics.scaleX + "px";
            selectedBox.style.top  = (parseFloat(selectedBox.style.top)  || 0) + dy * metrics.scaleY + "px";
        }
    }
    if (refacerEditorKeyMoveState.timer) clearTimeout(refacerEditorKeyMoveState.timer);
    refacerEditorKeyMoveState.timer = setTimeout(function() {
        refacerEditorKeyMoveState = null;
        applyEditorWidgetDraft();
    }, 420);
}
function bindEditorKeyboardHandlers() {
    if (document.body.dataset.refacerEditorKeyBound === "1") return;
    document.addEventListener("keydown", function(event) {
        var editorTab = document.getElementById("refacer-theme-editor-tab");
        if (!editorTab || getComputedStyle(editorTab).display === "none") return;
        if (!refacerEditorSelectedKey) return;
        if (refacerEditorDragState) return;
        var tag = (document.activeElement || {}).tagName || "";
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        var step = event.shiftKey ? 10 : 1;
        var handled = true;
        if (event.key === "ArrowLeft")  editorKeyboardMove(-step, 0);
        else if (event.key === "ArrowRight") editorKeyboardMove(step, 0);
        else if (event.key === "ArrowUp")    editorKeyboardMove(0, -step);
        else if (event.key === "ArrowDown")  editorKeyboardMove(0, step);
        else handled = false;
        if (handled) { event.preventDefault(); event.stopPropagation(); }
    });
    document.body.dataset.refacerEditorKeyBound = "1";
}
function loadEditorSnapshot(themeName) {
    bindEditorTabs();
    var selector = document.getElementById("editor-theme-selector");
    var theme = themeName || (selector ? selector.value : null) || "Default";
    var preview = document.getElementById("editor-preview-image");
    var status = document.getElementById("editor-status");
    requestJSON("GET", "debug/editor_snapshot?theme=" + encodeURIComponent(theme), null, function(body) {
        refacerEditorSnapshot = body || {};
        if (selector && body && body.theme) selector.value = body.theme;
        if (preview) {
            preview.onload = function() { renderEditorOverlay(refacerEditorSnapshot); };
            var previewPath = (body && body.preview_url) || "preview_frame";
            preview.src = refacerPath(previewPath) + (previewPath.indexOf("?") === -1 ? "?t=" : "&t=") + Date.now();
        } else {
            renderEditorOverlay(refacerEditorSnapshot);
        }
        if (status) status.textContent = "Inspection snapshot ready for theme: " + (body.theme || theme);
    }, "editor-status");
}
function loadEditorBase(selectedTheme, themes) {
    var selector = document.getElementById("editor-theme-selector");
    var themeList = Array.isArray(themes) ? themes : [];
    var resolvedTheme = themeList.length ? populateThemeSelect(selector, themeList, selectedTheme) : (selectedTheme || "Default");
    var status = document.getElementById("editor-status");
    if (status) {
        status.textContent = "Loading inspection snapshot for theme: " + resolvedTheme;
    }
    renderSelectedWidgetInspector(null, {theme: resolvedTheme, requested_theme: resolvedTheme, widgets: [], assets: {}});
    loadEditorSnapshot(resolvedTheme);
    enhanceRefacerWidgets();
}
function loadThemeSelector(selectedTheme, sharedThemes) {
    if (Array.isArray(sharedThemes)) {
        var managerTheme = populateThemeSelect(document.getElementById("theme-selector"), sharedThemes, selectedTheme);
        loadThemeInfo(managerTheme);
        loadEditorBase(managerTheme, sharedThemes);
        enhanceRefacerWidgets();
        return;
    }
    requestJSON("GET", "theme_list", null, function(body) {
        var themes = body.themes || [];
        var managerTheme = populateThemeSelect(document.getElementById("theme-selector"), themes, selectedTheme);
        loadEditorBase(managerTheme, themes);
        enhanceRefacerWidgets();
        loadThemeInfo(managerTheme);
    }, "theme-status");
}
function loadDiagnostics() {
    requestJSON("GET", "debug/theme_inventory", null, function(body) {
        var diagnostics = [];
        diagnostics.push("Local themes: " + (body.local_theme_count || 0));
        diagnostics.push("Candidate roots:");
        (body.candidate_roots || []).forEach(function(root) { diagnostics.push("  - " + root); });
        diagnostics.push("Active theme: " + (body.active_theme || "Default"));
        var resolved = body.active_paths || {};
        diagnostics.push("Resolved paths:");
        diagnostics.push("  config: " + (resolved.config || "None"));
        diagnostics.push("  css: " + (resolved.css || "None"));
        diagnostics.push("  info: " + (resolved.info || "None"));
        diagnostics.push("Remote cached count: " + (body.remote_count || 0));
        if (body.remote_error) diagnostics.push("Remote error: " + body.remote_error);
        document.getElementById("diagnostics-output").textContent = diagnostics.join("\\n");
        enhanceRefacerWidgets();
    }, "diagnostics-status");
    requestJSON("GET", "debug/remote_status", null, function(body) {
        var remoteStatus = body.last_remote_status ? ("Remote status: " + body.last_remote_status) : "Remote status: not fetched yet";
        if (body.last_remote_error) {
            remoteStatus += " | Error: " + body.last_remote_error;
        }
        setStatus("diagnostics-status", remoteStatus, !!body.last_remote_error);
    }, "diagnostics-status");
}
function loadManagerData() {
    requestJSON("GET", "active_theme", null, function(body) {
        var activeTheme = body.theme || "Default";
        document.getElementById("active-theme").textContent = activeTheme;
        document.getElementById("cfg-theme").value = activeTheme;
        setStealthButton(!!body.stealth_mode);
        loadThemeSelector(activeTheme);
        loadConfiguration(activeTheme);
        loadDiagnostics();
        if (body.fallback_notice) {
            setStatus("theme-status", body.fallback_notice, false);
        }
    }, "theme-status");
}
function selectTheme() {
    var theme = document.getElementById("theme-selector").value;
    requestJSON("POST", "theme_select", {theme: theme}, function(body) {
        setStatus("theme-status", body.message || "Theme updated.", false);
        if (body.fallback_notice) {
            setStatus("theme-status", body.fallback_notice, false);
        }
        document.getElementById("active-theme").textContent = theme;
        document.getElementById("theme-selector").value = theme;
        var editorThemeSelector = document.getElementById("editor-theme-selector");
        if (editorThemeSelector) editorThemeSelector.value = theme;
        loadConfiguration(theme);
        loadThemeInfo(theme);
        loadEditorSnapshot(theme);
        refreshPreview();
    }, "theme-status");
}
function selectEditorTheme() {
    var selector = document.getElementById("editor-theme-selector");
    if (!selector) return;
    var theme = selector.value || "Default";
    requestJSON("POST", "theme_select", {theme: theme}, function(body) {
        document.getElementById("active-theme").textContent = theme;
        var managerSelector = document.getElementById("theme-selector");
        if (managerSelector) managerSelector.value = theme;
        setStatus("theme-status", body.message || "Theme updated.", false);
        loadConfiguration(theme);
        loadThemeInfo(theme);
        loadEditorSnapshot(theme);
        refreshPreview();
    }, "editor-status");
}

function promptForThemeName(message, defaultValue) {
    var value = window.prompt(message, defaultValue || "");
    if (value == null) return null;
    value = String(value).trim();
    return value || null;
}
function copyTheme() {
    var theme = document.getElementById("theme-selector").value;
    if (!theme || theme === "Default") {
        setStatus("theme-tools-status", "Select a non-default theme to copy.", true);
        return;
    }
    var newName = promptForThemeName("Copy theme as:", theme + "-copy");
    if (!newName) return;
    requestJSON("POST", "theme_copy", {theme: theme, new_name: newName}, function(body) {
        setStatus("theme-tools-status", body.message || "Theme copied.", false);
        loadManagerData();
        refreshPreview();
    }, "theme-tools-status");
}
function renameTheme() {
    var theme = document.getElementById("theme-selector").value;
    var activeTheme = document.getElementById("active-theme").textContent || "Default";
    if (!theme || theme === "Default") {
        setStatus("theme-tools-status", "Default theme cannot be renamed.", true);
        return;
    }
    if (theme === activeTheme) {
        setStatus("theme-tools-status", "Active theme cannot be renamed.", true);
        return;
    }
    var newName = promptForThemeName("Rename theme to:", theme);
    if (!newName || newName === theme) return;
    requestJSON("POST", "theme_rename", {theme: theme, new_name: newName}, function(body) {
        setStatus("theme-tools-status", body.message || "Theme renamed.", false);
        loadManagerData();
    }, "theme-tools-status");
}
function deleteTheme() {
    var theme = document.getElementById("theme-selector").value;
    var activeTheme = document.getElementById("active-theme").textContent || "Default";
    if (!theme || theme === "Default") {
        setStatus("theme-tools-status", "Default theme cannot be deleted.", true);
        return;
    }
    if (theme === activeTheme) {
        setStatus("theme-tools-status", "Active theme cannot be deleted.", true);
        return;
    }
    if (!window.confirm("Delete theme '" + theme + "'?")) return;
    requestJSON("POST", "theme_delete", {theme: theme}, function(body) {
        setStatus("theme-tools-status", body.message || "Theme deleted.", false);
        loadManagerData();
    }, "theme-tools-status");
}
function uploadThemeZip(event) {
    if (event) event.preventDefault();
    var input = document.getElementById("theme-zip-file");
    if (!input || !input.files || !input.files.length) {
        setStatus("theme-tools-status", "Choose a zip file first.", true);
        return;
    }
    var formData = new FormData();
    formData.append("zipFile", input.files[0]);
    var xhr = new XMLHttpRequest();
    xhr.open("POST", refacerPath("theme_upload"), true);
    xhr.setRequestHeader("X-CSRFToken", "{{ csrf_token() }}");
    xhr.onreadystatechange = function() {
        if (xhr.readyState !== 4) return;
        var body = {};
        try { body = xhr.responseText ? JSON.parse(xhr.responseText) : {}; } catch (e) { body = {}; }
        if (xhr.status >= 200 && xhr.status < 300) {
            setStatus("theme-tools-status", body.message || "Theme zip uploaded.", false);
            input.value = "";
            loadManagerData();
        } else {
            setStatus("theme-tools-status", body.message || body.error || ("Upload failed (" + xhr.status + ")"), true);
        }
    };
    xhr.send(formData);
}
function newTheme() {
    var newName = promptForThemeName("New theme name:", "theme-new");
    if (!newName) return;
    requestJSON("POST", "theme_new", {new_name: newName}, function(body) {
        setStatus("theme-tools-status", body.message || "Theme created.", false);
        loadManagerData();
    }, "theme-tools-status");
}
function exportTheme() {
    var select = document.getElementById("theme-selector");
    var theme = select ? select.value : "";
    if (!theme || theme === "Default") {
        setStatus("theme-tools-status", "Select a non-default theme to export.", true);
        return;
    }
    setStatus("theme-tools-status", "Preparing " + theme + ".zip ...", false);
    window.location.href = refacerPath("theme_export/" + encodeURIComponent(theme));
}
function loadConfiguration(theme) {
    requestJSON("GET", "load_config?theme=" + encodeURIComponent(theme || document.getElementById("theme-selector").value || "Default"), null, function(body) {
        var render = body.render || {};
        var displayOutputMode = render.display_output_mode || (render["1bit"] ? "1bit" : "theme");
        document.getElementById("cfg-theme").value = body.theme || "Default";
        document.getElementById("cfg-toml").value = body.config_toml || "";
        document.getElementById("cfg-css").value = body.css || "";
        document.getElementById("cfg-info").value = body.info || "";
        document.getElementById("cfg-display-output-mode").value = displayOutputMode;
        document.getElementById("cfg-save-images").value = render.save_images ? "true" : "false";
        document.getElementById("cfg-experimental-non-native-selects").value = render.experimental_non_native_selects ? "true" : "false";
        document.getElementById("cfg-save-interval").value = render.save_interval || 10;
        document.getElementById("cfg-fps").value = render.fps || 30;
        document.getElementById("cfg-rotation").value = String(render.rotation != null ? render.rotation : 0);
        document.getElementById("cfg-display-control-enabled").value = render.display_control_enabled ? "true" : "false";
        document.getElementById("cfg-display-auto-off-seconds").value = render.display_auto_off_seconds || 0;
        document.getElementById("cfg-display-blank-color").value = render.display_blank_color || "black";
        document.getElementById("cfg-display-sleep-backend").value = render.display_sleep_backend || "auto";
        document.getElementById("cfg-display-sleep-windows-restore").value = render.display_sleep_windows_restore ? "true" : "false";
        document.getElementById("cfg-display-sleep-windows-restore-previous").value = render.display_sleep_windows_restore_previous ? "true" : "false";
        document.getElementById("cfg-display-sleep-windows-mode").value = render.display_sleep_windows_mode || "screen_saver";
        document.getElementById("cfg-display-sleep-windows-sub-mode").value = render.display_sleep_windows_sub_mode || "";
        refacerExperimentalNonNativeSelects = !!render.experimental_non_native_selects;
        document.getElementById("config-theme-name").textContent = body.theme || "Default";
        var isDefault = (body.theme || "Default") === "Default";
        document.getElementById("cfg-toml").disabled = isDefault;
        document.getElementById("cfg-css").disabled = isDefault;
        document.getElementById("cfg-info").disabled = isDefault;
        enhanceRefacerWidgets();
    }, "config-status");
}
function saveConfiguration() {
    requestJSON("POST", "save_config", {
        theme: document.getElementById("cfg-theme").value,
        config_toml: document.getElementById("cfg-toml").value,
        css: document.getElementById("cfg-css").value,
        info: document.getElementById("cfg-info").value,
        render: {
            display_output_mode: document.getElementById("cfg-display-output-mode").value || "theme",
            "1bit": (document.getElementById("cfg-display-output-mode").value || "theme") === "1bit",
            save_images: document.getElementById("cfg-save-images").value === "true",
            experimental_non_native_selects: document.getElementById("cfg-experimental-non-native-selects").value === "true",
            save_interval: parseInt(document.getElementById("cfg-save-interval").value, 10),
            fps: parseInt(document.getElementById("cfg-fps").value, 10),
            rotation: parseInt(document.getElementById("cfg-rotation").value, 10),
            display_control_enabled: document.getElementById("cfg-display-control-enabled").value === "true",
            display_auto_off_seconds: parseInt(document.getElementById("cfg-display-auto-off-seconds").value, 10),
            display_blank_color: document.getElementById("cfg-display-blank-color").value || "black",
            display_sleep_backend: document.getElementById("cfg-display-sleep-backend").value || "auto",
            display_sleep_windows_restore: document.getElementById("cfg-display-sleep-windows-restore").value === "true",
            display_sleep_windows_restore_previous: document.getElementById("cfg-display-sleep-windows-restore-previous").value === "true",
            display_sleep_windows_mode: document.getElementById("cfg-display-sleep-windows-mode").value || "screen_saver",
            display_sleep_windows_sub_mode: document.getElementById("cfg-display-sleep-windows-sub-mode").value || ""
        }
    }, function(body) {
        setStatus("config-status", body.message || "Configuration saved.", false);
        document.getElementById("active-theme").textContent = document.getElementById("cfg-theme").value;
        startPreviewRefresh();
        refreshPreview();
        loadConfiguration(document.getElementById("cfg-theme").value);
        loadDisplayStatus();
        loadDiagnostics();
        enhanceRefacerWidgets();
    }, "config-status");
}
function loadDownloadList() {
    setStatus("download-status", "Loading GitHub theme list...", false);
    requestJSON("GET", "theme_download_list", null, function(body) {
        var select = document.getElementById("download-selector");
        select.innerHTML = "";
        (body.themes || []).forEach(function(theme) {
            var option = document.createElement("option");
            option.value = theme.name;
            option.textContent = theme.name + " (" + (theme.version || "unknown") + ")";
            option.setAttribute("data-version", theme.version || "");
            option.setAttribute("data-author", theme.author || "");
            option.setAttribute("data-notes", theme.notes || "");
            select.appendChild(option);
        });
        updateDownloadInfo();
        setStatus("download-status", "GitHub theme list updated.", false);
        loadDiagnostics();
        enhanceRefacerWidgets();
    }, "download-status");
}
function updateDownloadInfo() {
    var select = document.getElementById("download-selector");
    var info = document.getElementById("download-info");
    info.innerHTML = "";
    if (!select || !select.options.length) {
        info.innerHTML = "<li>No remote themes loaded.</li>";
        return;
    }
    var option = select.options[select.selectedIndex];
    ["Author: " + (option.getAttribute("data-author") || "Unknown"), "Version: " + (option.getAttribute("data-version") || "Unknown"), "Notes: " + (option.getAttribute("data-notes") || "None")].forEach(function(text) {
        var item = document.createElement("li");
        item.textContent = text;
        info.appendChild(item);
    });
}
function compareRemoteVersion() {
    var select = document.getElementById("download-selector");
    if (!select || !select.value) return;
    var option = select.options[select.selectedIndex];
    requestJSON("POST", "version_compare", {theme: select.value, version: option.getAttribute("data-version") || ""}, function(body) {
        var localVersion = body.local_version || "not installed";
        var newer = body.is_newer ? "Update available." : "Already current or not installed.";
        setStatus("download-status", "Local: " + localVersion + ". " + newer, false);
    }, "download-status");
}
function downloadTheme() {
    var select = document.getElementById("download-selector");
    if (!select || !select.value) return;
    requestJSON("POST", "theme_download_select", {theme: select.value}, function(body) {
        setStatus("download-status", body.message || "Theme downloaded.", false);
        loadManagerData();
    }, "download-status");
}
function bindRefacerActions() {
    var page = currentRefacerPage();
    if (!page) return;
    [
        ["refresh-preview-btn", refreshPreview],
        ["apply-theme-btn", selectTheme],
        ["refresh-manager-btn", loadManagerData],
        ["reload-theme-files-btn", function() { loadConfiguration(document.getElementById("theme-selector").value); }],
        ["new-theme-btn", newTheme],
        ["copy-theme-btn", copyTheme],
        ["rename-theme-btn", renameTheme],
        ["delete-theme-btn", deleteTheme],
        ["upload-theme-btn", uploadThemeZip],
        ["export-theme-btn", exportTheme],
        ["load-theme-list-btn", loadDownloadList],
        ["compare-version-btn", compareRemoteVersion],
        ["download-theme-btn", downloadTheme],
        ["save-config-btn", saveConfiguration],
        ["reload-config-btn", function() { loadConfiguration(document.getElementById("theme-selector").value); }],
        ["stealth-toggle-btn", toggleStealthMode],
        ["display-toggle-btn", toggleDisplayPower],
        ["display-clear-btn", clearDisplay],
        ["editor-refresh-btn", function() { loadEditorSnapshot(); }],
        ["editor-overlay-toggle", toggleEditorOverlay],
        ["preview-toggle-btn", togglePreview]
    ].forEach(function(binding) {
        var el = document.getElementById(binding[0]);
        if (!el || el.dataset.refacerBound === "1") return;
        el.addEventListener("click", function(event) {
            event.preventDefault();
            binding[1]();
        });
        el.dataset.refacerBound = "1";
    });
    var editorSelector = document.getElementById("editor-theme-selector");
    if (editorSelector && editorSelector.dataset.refacerBound !== "1") {
        editorSelector.addEventListener("change", function() { selectEditorTheme(); });
        editorSelector.dataset.refacerBound = "1";
    }
    var widgetSelector = document.getElementById("editor-widget-selector");
    if (widgetSelector && widgetSelector.dataset.refacerBound !== "1") {
        widgetSelector.addEventListener("change", function() {
            if (this.value) selectEditorWidget(this.value);
        });
        widgetSelector.dataset.refacerBound = "1";
    }
    var editorTabLink = document.querySelector('a[href="#refacer-theme-editor-tab"]');
    if (editorTabLink && editorTabLink.dataset.refacerBound !== "1") {
        editorTabLink.addEventListener("click", function() {
            window.setTimeout(function() { loadEditorSnapshot(); }, 50);
        });
        editorTabLink.dataset.refacerBound = "1";
    }
    var cssEditorTabLink = document.querySelector('a[href="#refacer-css-editor-tab"]');
    if (cssEditorTabLink && cssEditorTabLink.dataset.refacerBound !== "1") {
        cssEditorTabLink.addEventListener("click", function() {
            window.setTimeout(function() { initCssEditor(); }, 50);
        });
        cssEditorTabLink.dataset.refacerBound = "1";
    }
    bindEditorTabs();
}
function initializeRefacerPage() {
    if (!currentRefacerPage()) return;
    setFrontendStatus("JS bootstrap reached", false);
    if (!refacerInitialized) {
        refacerInitialized = true;
    }
    bindRefacerActions();
    setFrontendStatus("Init running", false);
    bindEditorGlobalDragHandlers();
    bindEditorKeyboardHandlers();
    loadManagerData();
    loadDisplayStatus();
    enhanceRefacerWidgets();
    startPreviewRefresh();
    syncEditorOverlayVisibility();
    setFrontendStatus("Init ok", false);
}
// ------------------------------------------------------------------ CSS Editor
var cssEditorState = null;
var cssEditorPreviewReady = false;
var cssEditorSwatchSchema = {
    bar:          ['background-color', 'border', 'color', 'shadow-color'],
    page:         ['background-color', 'border', 'color', 'shadow-color'],
    body:         ['background-color', 'border', 'color', 'shadow-color'],
    button_up:    ['background-color', 'border', 'color', 'shadow-color'],
    button_hover: ['background-color', 'border', 'color', 'shadow-color'],
    button_down:  ['background-color', 'border', 'color', 'shadow-color'],
    active:       ['background-color', 'border', 'color', 'shadow-color'],
    link:         ['base', 'visited', 'hover', 'active'],
    focus:        [],
    extras:       ['nav-active-bg', 'nav-active-text',
                   'flipswitch-on-bg', 'flipswitch-on-text',
                   'flipswitch-off-bg', 'flipswitch-off-text',
                   'input-bg', 'input-border', 'input-text',
                   'listitem-bg', 'listitem-text',
                   'plugin-box-bg', 'plugin-box-border', 'plugin-box-text',
                   'tooltip-bg', 'tooltip-text', 'tooltip-border',
                   'table-header-bg', 'table-header-text',
                   'table-row-bg', 'table-row-text', 'table-alt-row-bg',
                   'table-row-hover-bg',
                   'body-font', 'heading-font', 'button-font', 'mono-font',
                   'select-bg', 'select-text', 'select-border',
                  'select-hover-bg', 'select-hover-text',
                  'select-active-bg', 'select-active-text',
                   'icon-disc-bg', 'icon-color',
                   'focus-shadow',
                   'body-bg', 'body-text'],
};
var cssEditorFontOptions = [
    {label: "Default / inherit", value: ""},
    {label: "Sans Serif", value: "Arial, Helvetica, sans-serif"},
    {label: "Serif", value: 'Georgia, "Times New Roman", serif'},
    {label: "Monospace", value: '"Courier New", Courier, monospace'},
    {label: "System UI", value: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'},
    {label: "Verdana", value: "Verdana, Geneva, sans-serif"},
    {label: "Tahoma", value: "Tahoma, Geneva, sans-serif"},
    {label: "Trebuchet", value: '"Trebuchet MS", Helvetica, sans-serif'},
    {label: "Times New Roman", value: '"Times New Roman", Times, serif'}
];
var cssEditorRoleLabels = {
    bar:          'Bar (toolbars, header, dividers, slider track)',
    page:         'Page / Overlay',
    body:         'Body (lists, inputs, collapsibles)',
    button_up:    'Button \u2014 Up (resting state)',
    button_hover: 'Button \u2014 Hover',
    button_down:  'Button \u2014 Down (pressed)',
    active:       'Active (selected, checkbox-on, radio-on, flipswitch)',
    link:         'Links',
    focus:        'Focus (no fields \u2014 see extras \u2192 focus-shadow)',
    extras:       'Pwnagotchi extras (plugin cards, tables, icons, body)',
};
var cssEditorFieldLabels = {
    extras: {
        "body-font": "body-font",
        "heading-font": "heading-font",
        "button-font": "button-font",
        "mono-font": "mono-font",
        "select-hover-bg": "select-list-hover-bg",
        "select-hover-text": "select-list-hover-text",
        "select-active-bg": "select-list-active-bg",
        "select-active-text": "select-list-active-text"
    }
};
function cssEditorIsFontField(role, field) {
    return role === "extras" && ["body-font", "heading-font", "button-font", "mono-font"].indexOf(field) >= 0;
}
function initCssEditor() {
    refreshCssEditorThemeList();
    var iframe = document.getElementById("css-editor-preview-iframe");
    if (iframe && !iframe.dataset.refacerBound) {
        iframe.addEventListener("load", function() {
            cssEditorPreviewReady = true;
            pushCssToPreview();
        });
        iframe.src = refacerPath("editor/css/preview_page");
        iframe.dataset.refacerBound = "1";
    }
    bindCssEditorActions();
}
function refreshCssEditorThemeList() {
    requestJSON("GET", "theme_list", null, function(body) {
        var sel = document.getElementById("css-editor-theme-select");
        if (!sel) return;
        requestJSON("GET", "active_theme", null, function(atBody) {
            var active = (atBody && atBody.theme) || "";
            sel.innerHTML = "";
            (body.themes || []).forEach(function(name) {
                var opt = document.createElement("option");
                opt.value = name;
                opt.textContent = name;
                if (name === active) opt.selected = true;
                sel.appendChild(opt);
            });
            enhanceRefacerWidgets();
            loadCssEditorState();
        });
    }, "css-editor-status");
}
function bindCssEditorActions() {
    [["css-editor-load-btn", loadCssEditorState], ["css-editor-save-btn", saveCssEditorState]].forEach(function(p) {
        var btn = document.getElementById(p[0]);
        if (!btn || btn.dataset.refacerBound === "1") return;
        btn.addEventListener("click", function(e) { e.preventDefault(); p[1](); });
        btn.dataset.refacerBound = "1";
    });
    var prevBtn = document.getElementById("css-editor-preview-btn");
    if (prevBtn && prevBtn.dataset.refacerBound !== "1") {
        prevBtn.addEventListener("click", function(e) {
            e.preventDefault();
            updateSwatchFromForm();
            pushCssToPreview();
        });
        prevBtn.dataset.refacerBound = "1";
    }
}
function loadCssEditorState() {
    var sel = document.getElementById("css-editor-theme-select");
    var theme = sel ? sel.value : null;
    if (!theme) { setStatus("css-editor-status", "Select a theme first.", true); return; }
    requestJSON("POST", "editor/css/load", {theme: theme}, function(body) {
        cssEditorState = body;
        renderCssEditorSwatch(body.swatch || {});
        var rawEl = document.getElementById("css-editor-raw");
        if (rawEl) {
            rawEl.value = body.raw_css || "";
            if (!rawEl.dataset.refacerBound) {
                rawEl.addEventListener("input", function() {
                    if (cssEditorState) cssEditorState.raw_css = this.value;
                    pushCssToPreview();
                });
                rawEl.dataset.refacerBound = "1";
            }
        }
        var warn = document.getElementById("css-editor-annotation-warning");
        if (warn) warn.style.display = body.has_annotations ? "none" : "block";
        var saveBtn = document.getElementById("css-editor-save-btn");
        if (saveBtn) saveBtn.disabled = !!body.is_default;
        pushCssToPreview();
        setStatus("css-editor-status", body.injection_error ? "Loaded. Note: " + body.injection_error : "Loaded.", !!body.injection_error);
    }, "css-editor-status");
}
function cssColorToHex(color) {
    if (!color || !color.trim()) return "";
    try {
        var canvas = document.createElement("canvas");
        canvas.width = canvas.height = 1;
        var ctx = canvas.getContext("2d");
        ctx.fillStyle = "#000000";
        ctx.fillStyle = color.trim();
        var computed = ctx.fillStyle;
        // ctx.fillStyle normalises to #rrggbb or rgba(...); if it stayed
        // #000000 and input wasn't black, the color was invalid.
        return computed;
    } catch (e) { return ""; }
}
function renderCssEditorSwatch(swatch) {
    var container = document.getElementById("css-editor-swatch-fields");
    if (!container) return;
    var html = "";
    Object.keys(cssEditorSwatchSchema).forEach(function(role) {
        html += "<div class='css-editor-role-block'>";
        html += "<h5>" + escapeEditorHtml(cssEditorRoleLabels[role] || role) + "</h5>";
        cssEditorSwatchSchema[role].forEach(function(field) {
            var current = ((swatch[role] || {})[field]) || "";
            var inputId = "css-swatch-" + role + "-" + field;
            var pickerId = inputId + "-picker";
            var hexVal = cssColorToHex(current);
            var fieldLabel = (((cssEditorFieldLabels[role] || {})[field]) || field);
            html += "<div class='css-editor-field-row'>";
            html += "<label for='" + inputId + "'>" + escapeEditorHtml(fieldLabel) + "</label>";
            html += "<span class='css-editor-field-inputs'>";
            if (cssEditorIsFontField(role, field)) {
                html += "<select id='" + inputId + "' class='css-font-select' data-css-role='" + role + "' data-css-field='" + field + "'>";
                cssEditorFontOptions.forEach(function(option) {
                    html += "<option value='" + escapeEditorHtml(option.value) + "'" + (option.value === current ? " selected" : "") + ">" + escapeEditorHtml(option.label) + "</option>";
                });
                html += "</select>";
            } else {
                html += "<input type='color' id='" + pickerId + "' class='css-color-picker' value='" + escapeEditorHtml(hexVal || "#000000") + "' title='Color picker'>";
                html += "<input type='text' id='" + inputId + "' class='css-color-text' data-css-role='" + role + "' data-css-field='" + field + "' data-picker='" + pickerId + "' value='" + escapeEditorHtml(current) + "' placeholder='e.g. black, #149900, rgb(0,0,0)'>";
            }
            html += "</span>";
            html += "</div>";
        });
        if (role === "extras") {
            html += "<p class='refacer-editor-note'>Closed select/button styling is themeable, and current/selected rows may be themeable. Native browser open-dropdown hover/highlight may ignore CSS depending on engine/browser; these select-list hover fields mainly affect HTML-rendered or jQM dropdown/list states. Enabling experimental non-native dropdowns can improve theming on Refacer-owned pages.</p>";
            html += "<p class='refacer-editor-note'>Basic WebUI font stacks can be selected here; raw CSS is still available for custom families.</p>";
        }
        html += "</div>";
    });
    container.innerHTML = html;
    // Text input → update picker + preview
    container.querySelectorAll("input.css-color-text").forEach(function(input) {
        input.addEventListener("input", function() {
            var hex = cssColorToHex(this.value);
            var picker = document.getElementById(this.getAttribute("data-picker"));
            if (picker && hex) picker.value = hex;
            updateSwatchFromForm();
            pushCssToPreview();
        });
    });
    // Color picker → update text input + preview
    container.querySelectorAll("input.css-color-picker").forEach(function(picker) {
        picker.addEventListener("input", function() {
            // Find the paired text input by id convention (pickerId = inputId + "-picker")
            var textId = this.id.replace(/-picker$/, "");
            var textInput = document.getElementById(textId);
            if (textInput) {
                textInput.value = this.value;
                updateSwatchFromForm();
                pushCssToPreview();
            }
        });
    });
    container.querySelectorAll("select.css-font-select").forEach(function(select) {
        select.addEventListener("change", function() {
            updateSwatchFromForm();
            pushCssToPreview();
        });
    });
    enhanceRefacerWidgets();
}
function updateSwatchFromForm() {
    if (!cssEditorState) cssEditorState = {swatch: {}};
    cssEditorState.swatch = cssEditorState.swatch || {};
    document.querySelectorAll("#css-editor-swatch-fields [data-css-role]").forEach(function(input) {
        var role = input.getAttribute("data-css-role");
        var field = input.getAttribute("data-css-field");
        if (!cssEditorState.swatch[role]) cssEditorState.swatch[role] = {};
        cssEditorState.swatch[role][field] = input.value;
    });
}
function pushCssToPreview() {
    if (!cssEditorPreviewReady) return;
    var iframe = document.getElementById("css-editor-preview-iframe");
    if (!iframe || !iframe.contentWindow) return;
    var raw = (cssEditorState && cssEditorState.raw_css) ? cssEditorState.raw_css : "";
    // TODO Phase 2: render the actual _write_css_swatch output in the preview via a client-side
    // port, for exact save parity. Current implementation emits a simplified !important overlay
    // that approximates the final result, and native open <select>/<option> hover painting may
    // still differ because browser/engine popup rendering is not fully CSS-controlled.
    var overlay = buildPreviewOverlayCss();
    iframe.contentWindow.postMessage({type: "refacer-css", css: raw + "\\n" + overlay}, "*");
}
function buildPreviewOverlayCss() {
    if (!cssEditorState || !cssEditorState.swatch) return "";
    var s = cssEditorState.swatch;
    var css = "";
    function pick(role, field) { return ((s[role] || {})[field]) || ""; }
    // UI polish only: suppress Chrome/Android tap flash on page-owned interactive elements.
    // This does not guarantee control over native open <select>/<option> hover/highlight painting.
    css += "a,button,input,select,textarea,label,.ui-btn{-webkit-tap-highlight-color:transparent !important;}\\n";
    // Bar
    if (pick("bar","background-color")) {
        css += ".ui-bar-a,.ui-page-theme-a .ui-bar-inherit{"
            + "background-color:" + pick("bar","background-color") + " !important;"
            + "border-color:" + pick("bar","border") + " !important;"
            + "color:" + pick("bar","color") + " !important;"
            + (pick("bar","shadow-color") ? "text-shadow:0 1px 0 " + pick("bar","shadow-color") + " !important;" : "")
            + "}\\n";
    }
    // Page
    if (pick("page","background-color")) {
        css += ".ui-overlay-a,.ui-page-theme-a,.ui-page-theme-a .ui-panel-wrapper{"
            + "background-color:" + pick("page","background-color") + " !important;"
            + "border-color:" + pick("page","border") + " !important;"
            + "color:" + pick("page","color") + " !important;"
            + (pick("page","shadow-color") ? "text-shadow:0 1px 0 " + pick("page","shadow-color") + " !important;" : "")
            + "}\\n";
    }
    // Body
    if (pick("body","background-color")) {
        css += ".ui-body-a,.ui-page-theme-a .ui-body-inherit,html .ui-panel-page-container-a{"
            + "background-color:" + pick("body","background-color") + " !important;"
            + "border-color:" + pick("body","border") + " !important;"
            + "color:" + pick("body","color") + " !important;"
            + (pick("body","shadow-color") ? "text-shadow:0 1px 0 " + pick("body","shadow-color") + " !important;" : "")
            + "}\\n";
    }
    // Button up
    if (pick("button_up","background-color")) {
        css += ".ui-page-theme-a .ui-btn,html .ui-bar-a .ui-btn,html .ui-body-a .ui-btn,html head+body .ui-btn.ui-btn-a{"
            + "background-color:" + pick("button_up","background-color") + " !important;"
            + "border-color:" + pick("button_up","border") + " !important;"
            + "color:" + pick("button_up","color") + " !important;"
            + (pick("button_up","shadow-color") ? "text-shadow:0 1px 0 " + pick("button_up","shadow-color") + " !important;" : "")
            + "}\\n";
    }
    // Button hover
    if (pick("button_hover","background-color")) {
        css += ".ui-page-theme-a .ui-btn:hover,html .ui-bar-a .ui-btn:hover,html head+body .ui-btn.ui-btn-a:hover{"
            + "background-color:" + pick("button_hover","background-color") + " !important;"
            + "border-color:" + pick("button_hover","border") + " !important;"
            + "color:" + pick("button_hover","color") + " !important;"
            + "}\\n";
    }
    // Button down
    if (pick("button_down","background-color")) {
        css += ".ui-page-theme-a .ui-btn:active,html .ui-bar-a .ui-btn:active,html head+body .ui-btn.ui-btn-a:active{"
            + "background-color:" + pick("button_down","background-color") + " !important;"
            + "border-color:" + pick("button_down","border") + " !important;"
            + "color:" + pick("button_down","color") + " !important;"
            + "}\\n";
    }
    // Active: button-active, checkbox-on, radio-on, flipswitch, slider
    if (pick("active","background-color")) {
        css += ".ui-page-theme-a .ui-btn.ui-btn-active,"
            + "html .ui-bar-a .ui-btn.ui-btn-active,"
            + "html .ui-body-a .ui-btn.ui-btn-active,"
            + "html head+body .ui-btn.ui-btn-a.ui-btn-active,"
            + ".ui-page-theme-a .ui-checkbox-on:after,"
            + "html .ui-bar-a .ui-checkbox-on:after,"
            + "html .ui-body-a .ui-checkbox-on:after,"
            + ".ui-page-theme-a .ui-flipswitch-active,"
            + "html .ui-bar-a .ui-flipswitch-active,"
            + "html .ui-body-a .ui-flipswitch-active,"
            + ".ui-page-theme-a .ui-slider-track .ui-btn-active,"
            + "html body div.ui-slider-track.ui-body-a .ui-btn-active{"
            + "background-color:" + pick("active","background-color") + " !important;"
            + "border-color:" + pick("active","border") + " !important;"
            + "color:" + pick("active","color") + " !important;"
            + "}\\n";
        css += ".ui-page-theme-a .ui-radio-on:after,html .ui-bar-a .ui-radio-on:after,html .ui-body-a .ui-radio-on:after{"
            + "border-color:" + pick("active","background-color") + " !important;"
            + "}\\n";
    }
    // Links
    if (pick("link","base"))
        css += ".ui-page-theme-a a,html .ui-bar-a a,html .ui-body-a a{color:" + pick("link","base") + " !important;}\\n";
    if (pick("link","visited"))
        css += ".ui-page-theme-a a:visited{color:" + pick("link","visited") + " !important;}\\n";
    if (pick("link","hover"))
        css += ".ui-page-theme-a a:hover{color:" + pick("link","hover") + " !important;}\\n";
    if (pick("link","active"))
        css += ".ui-page-theme-a a:active{color:" + pick("link","active") + " !important;}\\n";
    // Focus glow (stored in extras.focus-shadow)
    if (pick("extras","focus-shadow")) {
        css += ".ui-page-theme-a .ui-btn:focus,html .ui-bar-a .ui-btn:focus,"
            + "html .ui-body-a .ui-btn:focus,.ui-page-theme-a .ui-focus{"
            + "-webkit-box-shadow:0 0 12px " + pick("extras","focus-shadow") + " !important;"
            + "-moz-box-shadow:0 0 12px " + pick("extras","focus-shadow") + " !important;"
            + "box-shadow:0 0 12px " + pick("extras","focus-shadow") + " !important;}\\n";
    }
    // Extras: body base
    if (pick("extras","body-bg") || pick("extras","body-text")) {
        css += "body{"
            + (pick("extras","body-bg") ? "background-color:" + pick("extras","body-bg") + " !important;" : "")
            + (pick("extras","body-text") ? "color:" + pick("extras","body-text") + " !important;" : "")
            + "}\\n";
    }
    if (pick("extras","body-font")) {
        css += "body,.ui-page-theme-a,.ui-body-a,.ui-overlay-a{font-family:" + pick("extras","body-font") + " !important;}\\n";
    }
    if (pick("extras","heading-font")) {
        css += "h1,h2,h3,h4,h5,h6,.ui-header .ui-title{font-family:" + pick("extras","heading-font") + " !important;}\\n";
    }
    if (pick("extras","button-font")) {
        css += ".ui-btn,button,input[type='button'],input[type='submit']{font-family:" + pick("extras","button-font") + " !important;}\\n";
    }
    if (pick("extras","mono-font")) {
        css += "code,pre,textarea,.refacer-diagnostics,.refacer-textarea{font-family:" + pick("extras","mono-font") + " !important;}\\n";
    }
    // Extras: nav active tab (overrides the general active color for navbar specifically)
    if (pick("extras","nav-active-bg") || pick("extras","nav-active-text")) {
        css += ".ui-navbar .ui-btn-active,.ui-footer .ui-navbar .ui-btn-active{"
            + (pick("extras","nav-active-bg") ? "background-color:" + pick("extras","nav-active-bg") + " !important;" : "")
            + (pick("extras","nav-active-text") ? "color:" + pick("extras","nav-active-text") + " !important;" : "")
            + "}\\n";
    }
    // Extras: flipswitch on state (specificity 0,2,0+ beats active rule 0,2,0 via later order + also targets inner btn)
    if (pick("extras","flipswitch-on-bg") || pick("extras","flipswitch-on-text")) {
        css += ".ui-page-theme-a .ui-flipswitch-active,"
            + "html .ui-bar-a .ui-flipswitch-active,"
            + "html .ui-body-a .ui-flipswitch-active,"
            + ".ui-page-theme-a .ui-flipswitch-active .ui-btn,"
            + "html .ui-bar-a .ui-flipswitch-active .ui-btn,"
            + "html .ui-body-a .ui-flipswitch-active .ui-btn{"
            + (pick("extras","flipswitch-on-bg") ? "background-color:" + pick("extras","flipswitch-on-bg") + " !important;" : "")
            + (pick("extras","flipswitch-on-text") ? "color:" + pick("extras","flipswitch-on-text") + " !important;" : "")
            + "}\\n";
    }
    // Extras: flipswitch off state (also target inner .ui-btn so the thumb matches the track)
    if (pick("extras","flipswitch-off-bg") || pick("extras","flipswitch-off-text")) {
        css += ".ui-page-theme-a .ui-flipswitch:not(.ui-flipswitch-active),"
            + "html .ui-bar-a .ui-flipswitch:not(.ui-flipswitch-active),"
            + "html .ui-body-a .ui-flipswitch:not(.ui-flipswitch-active),"
            + ".ui-page-theme-a .ui-flipswitch:not(.ui-flipswitch-active) .ui-btn,"
            + "html .ui-bar-a .ui-flipswitch:not(.ui-flipswitch-active) .ui-btn,"
            + "html .ui-body-a .ui-flipswitch:not(.ui-flipswitch-active) .ui-btn{"
            + (pick("extras","flipswitch-off-bg") ? "background-color:" + pick("extras","flipswitch-off-bg") + " !important;" : "")
            + (pick("extras","flipswitch-off-text") ? "color:" + pick("extras","flipswitch-off-text") + " !important;" : "")
            + "}\\n";
    }
    // Extras: text inputs and selects
    if (pick("extras","input-bg") || pick("extras","input-border") || pick("extras","input-text")) {
        css += ".ui-input-text input,.ui-input-search input,.ui-select .ui-btn,.ui-slider-input{"
            + (pick("extras","input-bg") ? "background-color:" + pick("extras","input-bg") + " !important;" : "")
            + (pick("extras","input-border") ? "border-color:" + pick("extras","input-border") + " !important;" : "")
            + (pick("extras","input-text") ? "color:" + pick("extras","input-text") + " !important;" : "")
            + "}\\n";
    }
    // Extras: listview items
    if (pick("extras","listitem-bg") || pick("extras","listitem-text")) {
        css += ".ui-listview li,.ui-listview .ui-li-static{"
            + (pick("extras","listitem-bg") ? "background-color:" + pick("extras","listitem-bg") + " !important;" : "")
            + (pick("extras","listitem-text") ? "color:" + pick("extras","listitem-text") + " !important;" : "")
            + "}\\n";
    }
    // Extras: plugin cards
    if (pick("extras","plugin-box-bg") || pick("extras","plugin-box-border") || pick("extras","plugin-box-text")) {
        css += ".plugins-box{"
            + (pick("extras","plugin-box-bg") ? "background-color:" + pick("extras","plugin-box-bg") + " !important;" : "")
            + (pick("extras","plugin-box-border") ? "border-color:" + pick("extras","plugin-box-border") + " !important;" : "")
            + (pick("extras","plugin-box-text") ? "color:" + pick("extras","plugin-box-text") + " !important;" : "")
            + "}\\n";
    }
    // Extras: tooltip
    if (pick("extras","tooltip-bg") || pick("extras","tooltip-text") || pick("extras","tooltip-border")) {
        css += ".tooltip .tooltiptext{"
            + (pick("extras","tooltip-bg") ? "background-color:" + pick("extras","tooltip-bg") + " !important;" : "")
            + (pick("extras","tooltip-text") ? "color:" + pick("extras","tooltip-text") + " !important;" : "")
            + (pick("extras","tooltip-border") ? "border-color:" + pick("extras","tooltip-border") + " !important;" : "")
            + "}\\n";
    }
    // Extras: table header
    if (pick("extras","table-header-bg")) {
        css += "thead{"
            + "background-color:" + pick("extras","table-header-bg") + " !important;"
            + (pick("extras","table-header-text") ? "color:" + pick("extras","table-header-text") + " !important;" : "")
            + "}\\n";
    }
    // Extras: table body rows
    if (pick("extras","table-row-bg") || pick("extras","table-row-text")) {
        css += "tbody tr{"
            + (pick("extras","table-row-bg") ? "background-color:" + pick("extras","table-row-bg") + " !important;" : "")
            + (pick("extras","table-row-text") ? "color:" + pick("extras","table-row-text") + " !important;" : "")
            + "}\\n";
    }
    if (pick("extras","table-alt-row-bg")) {
        css += "tbody tr:nth-child(even){background-color:" + pick("extras","table-alt-row-bg") + " !important;}\\n";
    }
    // Extras: table row hover (tbody only so thead is unaffected)
    if (pick("extras","table-row-hover-bg")) {
        css += "tbody tr:hover{background-color:" + pick("extras","table-row-hover-bg") + " !important;}\\n";
    }
    // Extras: select / dropdown base
    if (pick("extras","select-bg") || pick("extras","select-text") || pick("extras","select-border")) {
        css += "select,option,.ui-selectmenu-list li,.ui-selectmenu-list .ui-btn,.ui-selectmenu-menu .ui-btn,.ui-selectmenu-menu .ui-listview li,.ui-popup .ui-listview li,.ui-popup .ui-listview .ui-btn{"
            + (pick("extras","select-bg") ? "background-color:" + pick("extras","select-bg") + " !important;" : "")
            + (pick("extras","select-text") ? "color:" + pick("extras","select-text") + " !important;" : "")
            + (pick("extras","select-border") ? "border-color:" + pick("extras","select-border") + " !important;" : "")
            + "}\\n";
    }
    // Extras: select / dropdown item hover.
    // Native/browser popup rendering may override CSS for open dropdown hover/highlight.
    // Refacer's current support is best-effort for page-owned HTML/jQM dropdown states.
    // Phase later: optional modern select experiment using appearance: base-select and
    // ::picker(select) when browser support and host UI compatibility are sufficient.
    if (pick("extras","select-hover-bg") || pick("extras","select-hover-text")) {
        css += "option:hover,option:focus,.ui-selectmenu-list .ui-btn:hover,.ui-selectmenu-list .ui-btn:focus,.ui-selectmenu-list .ui-btn.ui-state-hover,.ui-selectmenu-list .ui-btn.ui-state-focus,.ui-selectmenu-list .ui-btn.ui-state-active,.ui-selectmenu-list .ui-btn.ui-btn-active,.ui-selectmenu-list li:hover > .ui-btn,.ui-selectmenu-list li.ui-focus > .ui-btn,.ui-selectmenu-list li.ui-state-focus > .ui-btn,.ui-selectmenu-list li.ui-state-active > .ui-btn,.ui-selectmenu-list .ui-focus,.ui-selectmenu-list .ui-state-focus,.ui-selectmenu-list .ui-state-active,.ui-selectmenu-menu .ui-btn:hover,.ui-selectmenu-menu .ui-btn:focus,.ui-selectmenu-menu .ui-btn.ui-state-hover,.ui-selectmenu-menu .ui-btn.ui-state-focus,.ui-selectmenu-menu .ui-btn.ui-state-active,.ui-selectmenu-menu .ui-btn.ui-btn-active,.ui-selectmenu-menu .ui-listview .ui-btn:hover,.ui-selectmenu-menu .ui-listview .ui-btn:focus,.ui-selectmenu-menu .ui-listview .ui-btn.ui-state-hover,.ui-selectmenu-menu .ui-listview .ui-btn.ui-state-focus,.ui-selectmenu-menu .ui-listview .ui-btn.ui-state-active,.ui-selectmenu-menu .ui-listview .ui-btn.ui-btn-active,.ui-popup .ui-listview .ui-btn:hover,.ui-popup .ui-listview .ui-btn:focus,.ui-popup .ui-listview .ui-btn.ui-state-hover,.ui-popup .ui-listview .ui-btn.ui-state-focus,.ui-popup .ui-listview .ui-btn.ui-state-active,.ui-popup .ui-listview .ui-btn.ui-btn-active{"
            + (pick("extras","select-hover-bg") ? "background:" + pick("extras","select-hover-bg") + " !important;background-color:" + pick("extras","select-hover-bg") + " !important;background-image:none !important;" : "")
            + (pick("extras","select-hover-text") ? "color:" + pick("extras","select-hover-text") + " !important;" : "")
            + "text-shadow:none !important;box-shadow:none !important;-webkit-box-shadow:none !important;"
            + "}\\n";
    }
    if (pick("extras","select-active-bg") || pick("extras","select-active-text")) {
        css += "option:checked,option[selected],.ui-selectmenu-list .ui-btn.ui-btn-active,.ui-selectmenu-menu .ui-btn.ui-btn-active,.ui-selectmenu-menu .ui-listview .ui-btn.ui-btn-active,.ui-popup .ui-listview .ui-btn.ui-btn-active,.ui-selectmenu-list .ui-btn[aria-selected=\\"true\\"],.ui-selectmenu-menu .ui-btn[aria-selected=\\"true\\"],.ui-popup .ui-listview .ui-btn[aria-selected=\\"true\\"]{"
            + (pick("extras","select-active-bg") ? "background:" + pick("extras","select-active-bg") + " !important;background-color:" + pick("extras","select-active-bg") + " !important;background-image:none !important;" : "")
            + (pick("extras","select-active-text") ? "color:" + pick("extras","select-active-text") + " !important;" : "")
            + "text-shadow:none !important;box-shadow:none !important;-webkit-box-shadow:none !important;"
            + "}\\n";
    }
    // Extras: icons — disc bg and filter (jQM uses PNG background-image so filter changes icon appearance)
    if (pick("extras","icon-disc-bg")) {
        css += ".ui-icon-disc{background-color:" + pick("extras","icon-disc-bg") + " !important;}\\n";
    }
    if (pick("extras","icon-color")) {
        css += ".ui-page-theme-a .ui-icon::after,.ui-bar-a .ui-icon::after,"
            + ".ui-body-a .ui-icon::after,.ui-btn-a .ui-icon::after{"
            + "background-color:" + pick("extras","icon-color") + " !important;}\\n";
    }
    return css;
}
function saveCssEditorState() {
    var sel = document.getElementById("css-editor-theme-select");
    var theme = sel ? sel.value : null;
    if (!theme || theme === "Default") { setStatus("css-editor-status", "Cannot save to Default theme.", true); return; }
    updateSwatchFromForm();
    var rawEl = document.getElementById("css-editor-raw");
    var details = rawEl ? rawEl.closest("details") : null;
    var rawIsOpen = details && details.open;
    var payload = {theme: theme, reinject: true};
    if (rawIsOpen && rawEl && cssEditorState && rawEl.value !== cssEditorState.raw_css) {
        payload.raw_css = rawEl.value;
    } else {
        payload.swatch = (cssEditorState && cssEditorState.swatch) || {};
    }
    requestJSON("POST", "editor/css/save", payload, function(body) {
        var msg = body.injected ? "Saved and applied to live UI." : "Saved. " + (body.injection_error || "Not the active theme \u2014 apply via Theme Manager.");
        setStatus("css-editor-status", msg, !body.injected);
        loadCssEditorState();
    }, "css-editor-status");
}
// TODO Phase 2: add undo/redo stack specific to CSS editor, separate from the theme-draft undo.

document.addEventListener("DOMContentLoaded", initializeRefacerPage);
document.addEventListener("pageshow", function(event) {
    if (event.target && event.target.id === "refacer-manager") {
        initializeRefacerPage();
    } else if (currentRefacerPage()) {
        initializeRefacerPage();
    }
});
document.addEventListener("pagehide", function(event) {
    if ((event.target && event.target.id === "refacer-manager") || currentRefacerPage()) {
        stopPreviewRefresh();
    }
});
{% endblock %}
{% block content %}
<div id="refacer-manager">
    <h2>Refacer Theme and Render Manager</h2>
    <p class="refacer-muted">Theme selection, theme package editing, GitHub downloads, and main-screen render settings only.</p>
    <div id="frontend-status" class="refacer-status">Waiting for JS bootstrap...</div>
    <div data-role="tabs" id="refacer-main-tabs">
        <div data-role="navbar">
            <ul>
                <li><a href="#refacer-manager-tab" class="ui-btn-active">Manager</a></li>
                <li><a href="#refacer-theme-editor-tab">Theme Editor</a></li>
                <li><a href="#refacer-css-editor-tab">CSS Editor</a></li>
            </ul>
        </div>
        <div id="refacer-manager-tab" class="ui-content">
    <div class="refacer-grid">
        <div class="refacer-card">
            <h3>Main Preview</h3>
            <img class="refacer-preview pixelated" id="main-preview" alt="Main UI preview" />
            <div class="refacer-actions" style="margin-top:10px;">
                <button id="preview-toggle-btn" class="ui-btn ui-btn-inline ui-corner-all">Preview: Live</button>
                <button id="refresh-preview-btn" class="ui-btn ui-btn-inline ui-corner-all">Refresh Preview</button>
                <button id="stealth-toggle-btn" class="ui-btn ui-corner-all">Stealth Mode: Off</button>
                <button id="display-toggle-btn" class="ui-btn ui-btn-inline ui-corner-all">Display: On</button>
                <button id="display-clear-btn" class="ui-btn ui-btn-inline ui-corner-all">Clear Display</button>
                <span class="refacer-muted">Active theme: <strong id="active-theme">{{ active_theme }}</strong></span>
            </div>
            <div id="preview-status" class="refacer-status"></div>
            <div id="stealth-status" class="refacer-status"></div>
            <div id="display-control-status" class="refacer-status"></div>
        </div>
        <div class="refacer-card">
            <h3>Theme Manager</h3>
            <div class="ui-field-contain">
                <label for="theme-selector">Installed themes</label>
                <select id="theme-selector" onchange="loadThemeInfo(this.value); loadConfiguration(this.value);"></select>
            </div>
            <div class="refacer-actions">
                <button id="apply-theme-btn" class="ui-btn ui-btn-b ui-corner-all">Apply Theme</button>
                <button id="refresh-manager-btn" class="ui-btn ui-corner-all">Refresh</button>
            </div>
            <div id="theme-status" class="refacer-status"></div>
            <ul id="theme-info" class="refacer-list"></ul>
            <div id="theme-screenshot-wrap" style="display:none; margin-top:12px;">
                <img id="theme-screenshot" class="refacer-preview" alt="Theme screenshot" style="display:none;" />
            </div>
        </div>
    </div>
    <div class="refacer-card">
        <h3>Diagnostics</h3>
        <div id="diagnostics-status" class="refacer-status"></div>
        <div id="diagnostics-output" class="refacer-diagnostics"></div>
    </div>
    <div data-role="tabs" id="refacer-tabs">
        <div data-role="navbar">
            <ul>
                <li><a href="#theme-manager-tab" class="ui-btn-active">Theme Manager</a></li>
                <li><a href="#theme-downloader-tab">Theme Downloader</a></li>
                <li><a href="#configuration-tab">Configuration</a></li>
            </ul>
        </div>
        <div id="theme-manager-tab" class="ui-content">
            <div class="refacer-card">
                <h3>Theme Package</h3>
                <p class="refacer-muted">Manage installed local theme packages.</p>
                <div class="refacer-actions">
                    <button id="new-theme-btn" class="ui-btn ui-corner-all">New Theme</button>
                    <button id="reload-theme-files-btn" class="ui-btn ui-corner-all">Reload Theme Files</button>
                    <button id="copy-theme-btn" class="ui-btn ui-corner-all">Copy Theme</button>
                    <button id="rename-theme-btn" class="ui-btn ui-corner-all">Rename Theme</button>
                    <button id="delete-theme-btn" class="ui-btn ui-corner-all">Delete Theme</button>
                    <button id="export-theme-btn" class="ui-btn ui-corner-all">Export Theme (.zip)</button>
                </div>
                <div class="ui-field-contain" style="margin-top:12px;">
                    <label for="theme-zip-file">Upload theme zip</label>
                    <input type="file" id="theme-zip-file" accept=".zip,application/zip">
                </div>
                <div class="refacer-actions">
                    <button id="upload-theme-btn" class="ui-btn ui-corner-all">Upload Theme Zip</button>
                </div>
                <div id="theme-tools-status" class="refacer-status"></div>
            </div>
        </div>
        <div id="theme-downloader-tab" class="ui-content">
            <div class="refacer-card">
                <h3>GitHub Theme Downloader</h3>
                <div class="ui-field-contain">
                    <label for="download-selector">Remote themes</label>
                    <select id="download-selector" onchange="updateDownloadInfo()"></select>
                </div>
                <div class="refacer-actions">
                    <button id="load-theme-list-btn" class="ui-btn ui-btn-b ui-corner-all">Load Theme List</button>
                    <button id="compare-version-btn" class="ui-btn ui-corner-all">Compare Version</button>
                    <button id="download-theme-btn" class="ui-btn ui-corner-all">Download Theme</button>
                </div>
                <div id="download-status" class="refacer-status"></div>
                <ul id="download-info" class="refacer-list">
                    <li>No remote themes loaded.</li>
                </ul>
            </div>
        </div>
        <div id="configuration-tab" class="ui-content">
            <div class="refacer-card">
                <h3>Theme Config and Render Settings</h3>
                <p class="refacer-muted">Editing theme package: <strong id="config-theme-name">{{ active_theme }}</strong></p>
                <input type="hidden" id="cfg-theme" value="{{ active_theme }}">
                <div class="ui-field-contain">
                    <label for="cfg-display-output-mode">Display output mode</label>
                    <select id="cfg-display-output-mode">
                        <option value="theme" {% if options.get('display_output_mode', 'theme') == 'theme' %}selected{% endif %}>Theme (follow theme color_mode)</option>
                        <option value="rgba" {% if options.get('display_output_mode') == 'rgba' %}selected{% endif %}>RGBA</option>
                        <option value="palette" {% if options.get('display_output_mode') == 'palette' %}selected{% endif %}>Palette</option>
                        <option value="1bit" {% if options.get('display_output_mode') == '1bit' or (options.get('display_output_mode') is none and options.get('1bit')) %}selected{% endif %}>1-bit</option>
                    </select>
                    <p class="refacer-editor-note">Theme respects legacy theme intent such as ['P','P']. Palette is best for old Fancygotchi theme fidelity. RGBA uses the modern full-color path. 1-bit forces monochrome output.</p>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-save-images">Save frames for web snapshots</label>
                    <select id="cfg-save-images" data-role="flipswitch">
                        <option value="false" {% if not options.get('save_images') %}selected{% endif %}>Off</option>
                        <option value="true" {% if options.get('save_images') %}selected{% endif %}>On</option>
                    </select>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-experimental-non-native-selects">Experimental non-native dropdowns</label>
                    <select id="cfg-experimental-non-native-selects" data-role="flipswitch" onchange="onExperimentalNonNativeSelectsChanged()">
                        <option value="false" {% if not options.get('experimental_non_native_selects') %}selected{% endif %}>Off</option>
                        <option value="true" {% if options.get('experimental_non_native_selects') %}selected{% endif %}>On</option>
                    </select>
                    <p class="refacer-editor-note">Uses jQuery Mobile HTML-rendered menus for Refacer-owned dropdowns. Improves theming in Chromium/WebView but may change behavior.</p>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-save-interval">Snapshot interval</label>
                    <input type="number" id="cfg-save-interval" value="{{ options.get('save_interval', 10) }}">
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-fps">Target FPS</label>
                    <input type="number" id="cfg-fps" value="{{ options.get('fps', 30) }}">
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-rotation">Display Rotation</label>
                    <select id="cfg-rotation">
                        <option value="0">0°</option>
                        <option value="90">90°</option>
                        <option value="180">180°</option>
                        <option value="270">270°</option>
                    </select>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-display-control-enabled">Display control</label>
                    <select id="cfg-display-control-enabled" data-role="flipswitch">
                        <option value="false" {% if not options.get('display_control_enabled', True) %}selected{% endif %}>Off</option>
                        <option value="true" {% if options.get('display_control_enabled', True) %}selected{% endif %}>On</option>
                    </select>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-display-auto-off-seconds">Display auto-off seconds</label>
                    <input type="number" id="cfg-display-auto-off-seconds" value="{{ options.get('display_auto_off_seconds', 0) }}">
                    <p class="refacer-editor-note">0 disables automatic display sleep.</p>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-display-blank-color">Display blank color</label>
                    <input type="text" id="cfg-display-blank-color" value="{{ options.get('display_blank_color', 'black') }}">
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-display-sleep-backend">Display sleep backend</label>
                    <select id="cfg-display-sleep-backend">
                        <option value="blank" {% if options.get('display_sleep_backend') == 'blank' %}selected{% endif %}>Blank</option>
                        <option value="auto" {% if options.get('display_sleep_backend', 'auto') == 'auto' %}selected{% endif %}>Auto</option>
                        <option value="windows" {% if options.get('display_sleep_backend') == 'windows' %}selected{% endif %}>Windows</option>
                    </select>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-display-sleep-windows-restore">Windows sleep restore</label>
                    <select id="cfg-display-sleep-windows-restore" data-role="flipswitch">
                        <option value="false" {% if not options.get('display_sleep_windows_restore', True) %}selected{% endif %}>Off</option>
                        <option value="true" {% if options.get('display_sleep_windows_restore', True) %}selected{% endif %}>On</option>
                    </select>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-display-sleep-windows-restore-previous">Restore previous Windows runtime on wake</label>
                    <select id="cfg-display-sleep-windows-restore-previous" data-role="flipswitch">
                        <option value="false" {% if not options.get('display_sleep_windows_restore_previous', False) %}selected{% endif %}>Off</option>
                        <option value="true" {% if options.get('display_sleep_windows_restore_previous', False) %}selected{% endif %}>On</option>
                    </select>
                    <p class="refacer-editor-note">Off returns wake to the normal GUI.</p>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-display-sleep-windows-mode">Windows sleep mode</label>
                    <select id="cfg-display-sleep-windows-mode">
                        <option value="screen_saver" {% if options.get('display_sleep_windows_mode', 'screen_saver') == 'screen_saver' %}selected{% endif %}>screen_saver</option>
                        <option value="auxiliary" {% if options.get('display_sleep_windows_mode') == 'auxiliary' %}selected{% endif %}>auxiliary</option>
                        <option value="terminal" {% if options.get('display_sleep_windows_mode') == 'terminal' %}selected{% endif %}>terminal</option>
                    </select>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-display-sleep-windows-sub-mode">Windows screen saver sub-mode</label>
                    <input type="text" id="cfg-display-sleep-windows-sub-mode" value="{{ options.get('display_sleep_windows_sub_mode', '') }}">
                    <p class="refacer-editor-note">Empty keeps the Windows configured saver.</p>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-toml">Theme config.toml</label>
                    <textarea id="cfg-toml" class="refacer-textarea"></textarea>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-css">Theme style.css</label>
                    <textarea id="cfg-css" class="refacer-textarea"></textarea>
                </div>
                <div class="ui-field-contain">
                    <label for="cfg-info">Theme info.json</label>
                    <textarea id="cfg-info" class="refacer-textarea"></textarea>
                </div>
                <div class="refacer-actions">
                    <button id="save-config-btn" class="ui-btn ui-btn-b ui-corner-all">Save Theme and Render Settings</button>
                    <button id="reload-config-btn" class="ui-btn ui-corner-all">Reload</button>
                </div>
                <div id="config-status" class="refacer-status"></div>
            </div>
        </div>
    </div>
        </div>
        <div id="refacer-theme-editor-tab" class="ui-content">
            <div id="refacer-theme-editor" class="refacer-card">
                <h3>Theme Editor</h3>
                <div class="ui-field-contain">
                    <label for="editor-theme-selector">Editor theme</label>
                    <select id="editor-theme-selector"></select>
                </div>
                <div id="editor-status" class="refacer-status"></div>
                <div class="refacer-editor-layout">
                    <div class="refacer-editor-workspace">
                        <div id="editor-preview-panel" class="refacer-card">
                            <h4>Preview Panel</h4>
                        <p class="refacer-muted">Read-only inspection preview from the live Refacer compositor.</p>
                        <div class="refacer-actions">
                            <button id="editor-refresh-btn" class="ui-btn ui-corner-all">Refresh Inspection</button>
                            <button id="editor-overlay-toggle" class="ui-btn ui-corner-all" data-overlay-visible="1">Widget Boxes: On</button>
                        </div>
                        <div class="refacer-widget-selector-wrap">
                            <label for="editor-widget-selector">Widget:</label>
                            <select id="editor-widget-selector"><option value="">— Select widget —</option></select>
                            <span class="refacer-muted" style="font-size:0.82em;">[hidden] = not visible &nbsp; [z&lt;0] = negative z-index</span>
                        </div>
                        <div class="refacer-editor-stage">
                            <img id="editor-preview-image" class="pixelated" alt="Theme Editor preview" />
                                <div id="editor-preview-overlay" class="refacer-editor-overlay"></div>
                            </div>
                        <p class="refacer-muted" style="margin-top:6px;font-size:0.83em;">&#8592;&#8593;&#8594;&#8595; Arrow keys move selected widget 1px &nbsp;|&nbsp; Shift+Arrow = 10px &nbsp;(focus must be outside any input)</p>
                        </div>
                    </div>
                    <div class="refacer-editor-sidebar">
                        <div class="refacer-editor-stack">
                            <div class="refacer-card refacer-editor-tabcard">
                                <div class="refacer-editor-tabbar" role="tablist">
                                    <button type="button" class="ui-btn ui-mini ui-corner-all refacer-editor-tab is-active" data-editor-tab="widget" role="tab" aria-selected="true">Widget</button>
                                    <button type="button" class="ui-btn ui-mini ui-corner-all refacer-editor-tab" data-editor-tab="theme" role="tab" aria-selected="false">Theme Options</button>
                                    <button type="button" class="ui-btn ui-mini ui-corner-all refacer-editor-tab" data-editor-tab="assets" role="tab" aria-selected="false">Assets</button>
                                </div>
                                <div class="refacer-editor-tabpanels">
                                    <div class="refacer-editor-tabpanel is-active" data-editor-tabpanel="widget" role="tabpanel">
                                        <div id="editor-selected-widget">
                                            <h4>Selected Widget</h4>
                                            <p class="refacer-muted">Click a widget overlay box to inspect its runtime details.</p>
                                        </div>
                                        <div id="editor-widget-properties" style="margin-top:10px;">
                                            <h4>Widget Properties</h4>
                                            <p class="refacer-muted">Read-only widget properties will appear here after selection.</p>
                                        </div>
                                    </div>
                                    <div class="refacer-editor-tabpanel" data-editor-tabpanel="theme" role="tabpanel">
                                        <div id="editor-theme-properties">
                                            <h4>Theme / Global Properties</h4>
                                            <p class="refacer-muted">Theme-wide runtime inspection data will appear here.</p>
                                        </div>
                                    </div>
                                    <div class="refacer-editor-tabpanel" data-editor-tabpanel="assets" role="tabpanel">
                                        <div id="editor-assets">
                                            <h4>Assets</h4>
                                            <p class="refacer-muted">Theme asset inventory will be listed here.</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div id="refacer-css-editor-tab" class="ui-content">
            <div class="refacer-card">
                <h3>CSS Editor</h3>
                <p class="refacer-muted">Edit the active theme's style.css via a structured swatch form with live preview. Saves to the theme's <code>style.css</code> and applies the change to the live web UI.</p>
                <div class="refacer-actions">
                    <label for="css-editor-theme-select">Theme:</label>
                    <select id="css-editor-theme-select"></select>
                    <button type="button" id="css-editor-load-btn" class="ui-btn ui-corner-all">Load</button>
                    <button type="button" id="css-editor-preview-btn" class="ui-btn ui-corner-all">Push to Preview</button>
                    <button type="button" id="css-editor-save-btn" class="ui-btn ui-btn-b ui-corner-all" disabled>Save &amp; Apply</button>
                </div>
                <div id="css-editor-status" class="refacer-status"></div>
                <div id="css-editor-annotation-warning" class="refacer-editor-note" style="display:none; color:#a40000; margin:6px 0;">
                    This theme's CSS has no <code>{a-*}</code> annotations. Only raw editing is available.
                </div>
                <div class="css-editor-layout">
                    <div id="css-editor-swatch-panel" class="refacer-card">
                        <h4>Swatch</h4>
                        <p class="refacer-editor-note">Any CSS color value: named (<code>lime</code>), hex (<code>#149900</code>), or rgb().</p>
                        <p class="refacer-editor-note">Select hover/current swatches are best-effort for page-owned HTML or jQM dropdown/list states. Native browser open-dropdown hover/highlight may ignore CSS. Experimental non-native dropdowns can improve theming on Refacer-owned pages.</p>
                        <div id="css-editor-swatch-fields"></div>
                    </div>
                    <div id="css-editor-preview-panel" class="refacer-card">
                        <h4>Live Preview</h4>
                        <iframe id="css-editor-preview-iframe" src="" style="width:100%; height:500px; border:1px solid #bbb; background:#fff;"></iframe>
                    </div>
                </div>
                <details style="margin-top:10px;">
                    <summary><strong>Raw CSS (advanced)</strong></summary>
                    <textarea id="css-editor-raw" rows="18" class="refacer-textarea" style="font-family:monospace; min-height:300px;" placeholder="No CSS file for this theme yet."></textarea>
                    <p class="refacer-editor-note">Editing raw CSS overrides the swatch on save.</p>
                </details>
            </div>
        </div>
</div>
</div>
{% endblock %}
"""


class _ThemeMetadataHTMLSanitizer(HTMLParser):
    ALLOWED_TAGS = {'a', 'b', 'strong', 'i', 'em', 'br', 'span'}
    ALLOWED_ATTRS = {'href', 'style', 'target', 'rel'}
    SAFE_STYLE_RE = re.compile(r"^\s*([a-zA-Z-]+\s*:\s*[^;<>]+;?\s*)*$")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = (tag or '').lower()
        if tag not in self.ALLOWED_TAGS:
            return
        cleaned = []
        for key, value in attrs:
            key = (key or '').lower()
            if key not in self.ALLOWED_ATTRS:
                continue
            value = '' if value is None else str(value)
            if key == 'href':
                if not re.match(r'^(https?:|mailto:|/)', value, re.IGNORECASE):
                    continue
            elif key == 'target':
                if value not in ('_blank', '_self'):
                    continue
            elif key == 'rel':
                allowed_rel = {'noopener', 'noreferrer', 'nofollow'}
                tokens = [token for token in value.split() if token in allowed_rel]
                if not tokens:
                    continue
                value = ' '.join(tokens)
            elif key == 'style':
                if not self.SAFE_STYLE_RE.match(value):
                    continue
            cleaned.append(f' {key}="{html.escape(value, quote=True)}"')
        self.parts.append(f"<{tag}{''.join(cleaned)}>")

    def handle_endtag(self, tag):
        tag = (tag or '').lower()
        if tag in self.ALLOWED_TAGS and tag != 'br':
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(html.escape(data or ''))

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def get_html(self):
        return ''.join(self.parts)


class Refacer(plugins.Plugin):
    __author__ = 'V0rT3x'
    __version__ = '1.3.0'
    __license__ = 'GPL3'
    __description__ = 'Render-only main-screen UI interceptor with a focused theme and render manager UI.'
    BOOT_DEFAULT_DURATION = 5
    BOOT_ALLOWED_MODES = ('normal', 'stretch', 'fit', 'fill', 'center', 'tile')
    BOOT_ALLOWED_IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
    THEME_ALLOWED_FONT_EXTS = ('.ttf', '.otf', '.woff', '.woff2', '.fon')
    _ASSET_GROUP_DIRS = {
        'backgrounds':  'img/bg',
        'foregrounds':  'img/fg',
        'faces':        'img/face',
        'friend_faces': 'img/friend_face',
        'widgets':      'img/widgets',
        'icons':        'img/icons',
        'fonts':        'fonts',
    }
    DEFAULT_OPTIONS = {
        'fps': 30,
        '1bit': False,
        'display_output_mode': 'theme',
        'save_images': False,
        'experimental_non_native_selects': False,
        'save_interval': 10,
        'theme': 'Default',
        'github_token': '',
        'rotation': 0,
        'default_stealth_mode': False,
        'display_control_enabled': True,
        'display_auto_off_seconds': 0,
        'display_blank_color': 'black',
        'display_sleep_backend': 'auto',
        'display_sleep_windows_restore': True,
        'display_sleep_windows_restore_previous': False,
        'display_sleep_windows_mode': 'screen_saver',
        'display_sleep_windows_sub_mode': '',
        # TODO: surface these two options in the theme editor UI (config.toml works today)
        'boot_animation_on_startup': True,
        'boot_animation_on_theme_switch': False,
    }
    DEFAULT_THEME_MODEL = {
        'theme': {
            'options': {
                'bg_fg_select': 'manu',
                'bg_mode': 'normal',
                'fg_mode': 'normal',
                'boot_animation': False,
                'boot_mode': 'stretch',
                'boot_max_loops': 1,
                'boot_bg_color': '',
                'boot_total_duration': 5,
                'fg_image': '',
                'bg_color': 'white',
                'bg_image': '',
                'bg_anim_image': '',
                'font_sizes': [14, 9, 14, 25, 19, 9],
                'font': 'DejaVuSansMono',
                'font_bold': 'DejaVuSansMono-Bold',
                'status_font': 'DejaVuSansMono',
                'font_awesome': '',
                'size_offset': 5,
                'label_spacing': 9,
                'label_line_spacing': 0,
                'font_spacing': 0,
                'cursor': '|',
                'stealth_mode': False,
                'friend_bars': '|',
                'friend_no_bars': '|',
                'base_text_color': ['black'],
                'main_text_color': [],
                'color_mode': ['P', 'P'],
                'faces': {},
            },
            'widget': {},
        }
    }
    WIDGET_DEFAULTS = {
        'Text': {
            'position': [0, 0],
            'color': ['black'],
            'z_axis': 0,
            'text_font': '',
            'text_font_size': 'Medium',
            'size_offset': 0,
            'font_spacing': 0,
            'icon': False,
            'icon_color': False,
            'invert': False,
            'alpha': False,
            'crop': [0, 0, 0, 0],
            'mask': False,
            'refine': 150,
            'zoom': 1,
            'image_type': 'png',
            'wrap': False,
            'max_length': 0,
            'f_awesome': False,
            'f_awesome_size': 0,
            'width': None,
            'height': None,
        },
        'LabeledValue': {
            'position': [0, 0],
            'color': ['black'],
            'z_axis': 0,
            'text_font': '',
            'text_font_size': 'Medium',
            'size_offset': 0,
            'font_spacing': 0,
            'icon': False,
            'icon_color': False,
            'invert': False,
            'alpha': False,
            'crop': [0, 0, 0, 0],
            'mask': False,
            'refine': 150,
            'zoom': 1,
            'label': '',
            'label_font': '',
            'label_font_size': 'Bold',
            'label_spacing': 9,
            'label_line_spacing': 0,
            'image_type': 'png',
            'wrap': False,
            'max_length': 0,
            'f_awesome': False,
            'f_awesome_size': 0,
            'width': None,
            'height': None,
        },
        'Line': {
            'position': [0, 0, 0, 0],
            'color': ['black'],
            'z_axis': 0,
            'width': 1,
        },
        'Rect': {
            'position': [0, 0, 0, 0],
            'color': ['black'],
            'z_axis': 0,
            'width': 1,
        },
        'FilledRect': {
            'position': [0, 0, 0, 0],
            'color': ['black'],
            'z_axis': 0,
        },
        'Bitmap': {
            'position': [0, 0],
            'color': ['black'],
            'z_axis': 0,
            'icon': '',
            'invert': False,
            'alpha': False,
            'crop': [0, 0, 0, 0],
            'mask': False,
            'refine': 150,
            'zoom': 1,
            'icon_color': False,
            'image_type': 'png',
            'width': None,
            'height': None,
            'image': None,
            'image_dict': {},
            'themed_static_image': None,
            'live_bitmap_cache': {},
        },
    }
    _WIDGET_RUNTIME_ONLY_FIELDS = {
        'image', 'image_dict', 'themed_static_image', 'live_bitmap_cache',
    }
    # TODO Phase 2+: expose non-color tokens (font family, corner radii, icons, shadows).
    CSS_SWATCH_FIELDS = {
        'bar':          {'background-color': 'a-bar-background-color', 'border': 'a-bar-border', 'color': 'a-bar-color', 'shadow-color': 'a-bar-shadow-color'},
        'page':         {'background-color': 'a-page-background-color', 'border': 'a-page-border', 'color': 'a-page-color', 'shadow-color': 'a-page-shadow-color'},
        'body':         {'background-color': 'a-body-background-color', 'border': 'a-body-border', 'color': 'a-body-color', 'shadow-color': 'a-body-shadow-color'},
        'button_up':    {'background-color': 'a-bup-background-color', 'border': 'a-bup-border', 'color': 'a-bup-color', 'shadow-color': 'a-bup-shadow-color'},
        'button_hover': {'background-color': 'a-bhover-background-color', 'border': 'a-bhover-border', 'color': 'a-bhover-color', 'shadow-color': 'a-bhover-shadow-color'},
        'button_down':  {'background-color': 'a-bdown-background-color', 'border': 'a-bdown-border', 'color': 'a-bdown-color', 'shadow-color': 'a-bdown-shadow-color'},
        'active':       {'background-color': 'a-active-background-color', 'border': 'a-active-border', 'color': 'a-active-color', 'shadow-color': 'a-active-shadow-color'},
        'link':         {'base': 'a-link-color', 'visited': 'a-link-visited', 'hover': 'a-link-hover', 'active': 'a-link-active'},
        'focus':        {},
        'extras':       {
            'nav-active-bg':       None,
            'nav-active-text':     None,
            'flipswitch-on-bg':    None,
            'flipswitch-on-text':  None,
            'flipswitch-off-bg':   None,
            'flipswitch-off-text': None,
            'input-bg':            None,
            'input-border':        None,
            'input-text':          None,
            'listitem-bg':         None,
            'listitem-text':       None,
            'plugin-box-bg':       None,
            'plugin-box-border':   None,
            'plugin-box-text':     None,
            'tooltip-bg':          None,
            'tooltip-text':        None,
            'tooltip-border':      None,
            'table-header-bg':     None,
            'table-header-text':   None,
            'table-row-bg':        None,
            'table-row-text':      None,
            'table-alt-row-bg':    None,
            'table-row-hover-bg':  None,
            'body-font':           None,
            'heading-font':        None,
            'button-font':         None,
            'mono-font':           None,
            'select-bg':           None,
            'select-text':         None,
            'select-border':       None,
            'select-hover-bg':     None,
            'select-hover-text':   None,
            'select-active-bg':    None,
            'select-active-text':  None,
            'icon-disc-bg':        None,
            'icon-color':          None,
            'focus-shadow':        None,
            'body-bg':             None,
            'body-text':           None,
        },
    }
    CURSOR_MARKERS = ['█', '-']

    BITMAP_WIDGET_TYPES = (
        'Bitmap', 'WardriverIcon', 'InetIcon', 'Frame',
        'Image', 'ImageWidget', 'CustomImage'
    )

    def __init__(self):
        self._running = False
        self._render_thread = None
        self._view_instance = None
        self._boot_anim_enabled = False
        self._boot_anim_done = True
        self._boot_anim_started_ts = None
        self._boot_anim_last_frame_ts = None
        self._boot_anim_loop_index = 0
        self._boot_anim_frame_index = 0
        self._boot_anim_delay_s = 0.0
        self._boot_anim_frames = []
        self._boot_anim_total_loops = 0
        self._boot_anim_total_duration = 0.0
        self._boot_anim_bg_color = None
        self._boot_anim_first_frame_published = True
        self._boot_anim_loading = False
        self._boot_anim_load_thread = None
        self.fps = self.DEFAULT_OPTIONS['fps']
        self._lock = threading.Lock()
        self._agent = None
        self._old_update = None
        self.enabled = True
        self._pwny_root = os.path.dirname(pwnagotchi.__file__)
        self._plug_root = os.path.dirname(os.path.realpath(__file__))
        self._themes_root = os.path.join(self._plug_root, 'themes')
        self._pwnagotchi_static_css_path = None
        self._pwnagotchi_css_backup_path = None
        self._css_injection_last_error = None
        self._repo_screenshots_path = os.path.join(self._pwny_root, 'ui', 'web', 'static', 'img')
        self._repo_screenshots_index_path = os.path.join(self._repo_screenshots_path, '.refacer-theme-mirrors.json')
        self._theme_name = 'Default'
        self._theme_path = None
        self._theme_bundle = {}
        self._theme_model = copy.deepcopy(self.DEFAULT_THEME_MODEL)
        self._theme_assets = {'background': None, 'foreground': None, 'animated_background': []}
        self._asset_cache = {}
        self._anim_frame_index = 0
        self._menu_scroll_state = {}
        self._render_cycle_lock = threading.Lock()
        self._last_render_progress_ts = 0.0
        self._last_compose_success_ts = 0.0
        self._last_publish_web_ts = 0.0
        self._last_publish_hw_ts = 0.0
        self._last_watchdog_check_ts = 0.0
        self._watchdog_recoveries = 0
        self._watchdog_last_reason = ''
        self._watchdog_fallback_active = False
        self._watchdog_last_recovery_ts = 0.0
        self._last_successful_hardware_publish_ts = 0.0
        self._consecutive_hardware_publish_failures = 0
        self._display_recovery_in_progress = False
        self._last_display_reinit_ts = 0.0
        self._display_reinit_count = 0
        self._last_known_good_canvas = None
        self._display_wedge_suspected = False
        self._display_recovery_lock = threading.Lock()
        self._display_enabled = True
        self._display_sleep_reason = ''
        self._display_auto_off_seconds = self.DEFAULT_OPTIONS['display_auto_off_seconds']
        self._display_auto_off_deadline = 0.0
        self._display_control_lock = threading.RLock()
        self._last_display_control_ts = 0.0
        self._display_sleep_backend_active = ''
        self._display_windows_sleep_active = False
        self._display_windows_previous_config = None
        self._display_windows_previous_hijack = None
        self._display_windows_previous_state = None
        self._display_windows_last_error = ''
        self._display_reinit_skip_logged = False
        self._driver_reset_count = 0
        self._last_driver_reset_ts = 0.0
        self._last_driver_reset_capability = ''
        self._reset_generation = 0
        self._render_generation = 0
        self._fresh_publishes_since_recovery = 0
        self._post_reset_quarantine_until = 0.0
        self._post_reset_quarantine_logged = False
        self._last_direct_fallback_publish_attempt_ts = 0.0
        self._last_direct_fallback_keepalive_log_ts = 0.0
        self._last_tier_change_ts = 0.0
        self._recovery_cache_active = False
        self._recovery_cache_started_ts = 0.0
        self._recovery_cache_max_age_s = 2.0
        self._fresh_publish_streak_after_recovery = 0
        self._last_emergency_display_reinit_bypass_ts = 0.0
        self._last_live_compose_id = 0
        self._watchdog_warned_stale = False
        self._watchdog_in_recovery = False
        self._render_stats = {
            'frames_ok': 0,
            'frames_dropped_busy': 0,
            'frames_over_budget': 0,
            'last_frame_ms': 0.0,
            'avg_frame_ms': 0.0,
            'last_publish_ms': 0.0,
            'avg_publish_ms': 0.0,
            'current_tier': 'full',
            'degrade_reason': '',
            'last_progress_ts': 0.0,
            'last_compose_success_ts': 0.0,
            'last_publish_web_ts': 0.0,
            'last_publish_hw_ts': 0.0,
            'watchdog_recoveries': 0,
            'watchdog_last_reason': '',
            'watchdog_fallback_active': False,
            'last_successful_hardware_publish_ts': 0.0,
            'consecutive_hardware_publish_failures': 0,
            'last_display_reinit_ts': 0.0,
            'display_reinit_count': 0,
            'display_wedge_suspected': False,
            'driver_reset_count': 0,
            'last_driver_reset_ts': 0.0,
            'last_driver_reset_capability': '',
            'reset_generation': 0,
            'display_enabled': True,
            'display_sleep_reason': '',
            'display_auto_off_seconds': 0,
            'display_auto_off_deadline': 0.0,
            'last_display_control_ts': 0.0,
            'display_sleep_backend': 'auto',
            'display_sleep_backend_active': '',
            'display_windows_sleep_active': False,
            'display_windows_last_error': '',
        }
        self._render_pressure = {
            'busy_drop_streak': 0,
            'over_budget_streak': 0,
            'recovery_streak': 0,
        }
        self._font_cache = {}
        self.font_name = 'DejaVuSansMono'
        self.font_bold_name = 'DejaVuSansMono-Bold'
        self.font_status_name = 'DejaVuSansMono'
        self.f_awesome_name = ''
        self.Small = None
        self.Medium = None
        self.BoldSmall = None
        self.Bold = None
        self.BoldBig = None
        self.Huge = None
        self._theme_fallback_notice = None
        self._render_palette_debug = {}
        self._last_render_canvas = None
        self._last_stock_canvas = None
        self._last_remote_status = None
        self._last_remote_error = None
        self._theme_cache = None
        self._theme_runtime_version = 0
        self._theme_runtime = {
            'theme_name': 'Default',
            'theme_path': None,
            'theme_bundle': copy.deepcopy(self.DEFAULT_THEME_MODEL),
            'assets': {'background': None, 'foreground': None, 'animated_background': []},
            'asset_cache': {},
            'font_cache': {},
            'anim_frame_index': 0,
            'runtime_version': 0,
            'font_name': 'DejaVuSansMono',
            'font_bold_name': 'DejaVuSansMono-Bold',
            'font_status_name': 'DejaVuSansMono',
            'f_awesome_name': '',
            'Small': None,
            'Medium': None,
            'BoldSmall': None,
            'Bold': None,
            'BoldBig': None,
            'Huge': None,
        }
        self._editor_draft_theme_name = None
        self._editor_draft_bundle = None
        self._editor_draft_dirty = False
        self._editor_selected_widget_key = None

    def _theme_menu(self, theme_source=None):
        if isinstance(theme_source, dict) and 'theme_bundle' in theme_source:
            bundle = theme_source.get('theme_bundle') or {}
        else:
            bundle = self._theme_bundle if theme_source is None else theme_source
        return bundle.get('theme', {}).get('menu', {})

    def _lightmenu_snapshot(self):
        lightmenu = plugins.loaded.get('lightmenu')
        if not lightmenu or not hasattr(lightmenu, 'get_menu_snapshot'):
            return None
        try:
            return lightmenu.get_menu_snapshot()
        except Exception as exc:
            logging.debug(f"[Refacer][menu] lightmenu snapshot unavailable: {exc}")
            return None

    def _theme_menu_options(self, theme_source=None):
        menu = self._theme_menu(theme_source)
        options = menu.get('options', {}) if isinstance(menu, dict) else {}
        if not isinstance(options, dict):
            return {}
        resolved = dict(options)
        orientation_suffix = '-v' if self._theme_orientation() == 'v' else '-h'
        for key, value in options.items():
            if not isinstance(key, str) or not key.endswith(('-h', '-v')):
                continue
            base_key = key[:-2]
            if not base_key:
                continue
            if key.endswith(orientation_suffix):
                resolved[base_key] = value
        return resolved

    def _theme_menu_submenus(self, theme_source=None):
        menu = self._theme_menu(theme_source)
        if not isinstance(menu, dict):
            return {}
        return {k: v for k, v in menu.items() if k != 'options' and isinstance(v, dict)}

    def _update_moving_average(self, current, new_value, weight=0.2):
        new_value = float(new_value or 0.0)
        current = float(current or 0.0)
        if current <= 0.0:
            return new_value
        return (current * (1.0 - weight)) + (new_value * weight)

    def _effective_fps(self):
        configured = max(1, int(self.fps or 1))
        base = max(1, min(configured, 12))
        if time.time() < self._post_reset_quarantine_until:
            return min(base, 5)
        return base

    def _watchdog_warn_threshold_s(self):
        return 8.0

    def _watchdog_recover_threshold_s(self):
        return 15.0

    def _watchdog_cooldown_s(self):
        return 15.0

    def _display_reinit_cooldown_s(self):
        return 60.0

    def _display_reinit_emergency_bypass_cooldown_s(self):
        return 6.0

    def _display_reinit_threshold_s(self):
        return 20.0

    def _display_publish_failure_threshold(self):
        return 3

    def _driver_reset_cooldown_s(self):
        return 30.0

    def _watchdog_terminal_threshold(self):
        return 3

    def _watchdog_health_publishes(self):
        return 300

    def _post_reset_quarantine_s(self):
        return 10.0

    def _direct_fallback_publish_interval_s(self):
        return 2.0

    def _direct_fallback_keepalive_log_interval_s(self):
        return 20.0

    def _clear_recovery_cache_handoff(self):
        self._recovery_cache_active = False
        self._recovery_cache_started_ts = 0.0
        self._fresh_publish_streak_after_recovery = 0


    def _current_render_generation(self):
        return int(self._render_generation or 0)

    def _next_render_generation(self):
        self._render_generation = self._current_render_generation() + 1
        self._render_stats['render_generation'] = self._render_generation
        return self._render_generation

    def _invalidate_render_generation(self, reason=''):
        old_generation = self._current_render_generation()
        new_generation = self._next_render_generation()
        logging.warning(
            f"[Refacer][recovery] invalidated render generation old={old_generation} "
            f"new={new_generation} reason={reason or 'unspecified'}"
        )
        return new_generation

    def _render_generation_is_active(self, generation):
        return self._running and int(generation or 0) == self._current_render_generation()

    def _render_generation_became_stale(self, generation, *, where='render'):
        if self._render_generation_is_active(generation):
            return False
        logging.info(f"[Refacer][{where}] generation={generation} became stale; exiting loop")
        return True

    def _expire_recovery_cache_handoff_if_needed(self, now=None):
        if not self._recovery_cache_active:
            return False
        now = float(now if now is not None else time.time())
        age = now - float(self._recovery_cache_started_ts or 0.0)
        if age <= float(self._recovery_cache_max_age_s or 0.0):
            return False
        self._clear_recovery_cache_handoff()
        logging.info("[Refacer][recovery] cached-frame handoff expired by age=%.1fs" % age)
        return True

    def _mark_render_progress(self, now=None, *, composed=False, published_web=False, published_hw=False, generation=None):
        if generation is not None and not self._render_generation_is_active(generation):
            return False
        now = float(now if now is not None else time.time())
        self._expire_recovery_cache_handoff_if_needed(now)
        self._last_render_progress_ts = now
        self._render_stats['last_progress_ts'] = now
        self._watchdog_warned_stale = False
        self._display_reinit_skip_logged = False
        if composed:
            self._last_compose_success_ts = now
            self._last_live_compose_id = int(self._last_live_compose_id or 0) + 1
            self._render_stats['last_compose_success_ts'] = now
        if published_web:
            self._last_publish_web_ts = now
            self._render_stats['last_publish_web_ts'] = now
        if published_hw:
            self._last_publish_hw_ts = now
            self._render_stats['last_publish_hw_ts'] = now
            self._last_successful_hardware_publish_ts = now
            self._render_stats['last_successful_hardware_publish_ts'] = now
            if self._consecutive_hardware_publish_failures > 0 or self._display_wedge_suspected:
                logging.info("[Refacer][watchdog] hardware publish heartbeat refreshed")
            self._consecutive_hardware_publish_failures = 0
            self._render_stats['consecutive_hardware_publish_failures'] = 0
            self._display_wedge_suspected = False
            self._render_stats['display_wedge_suspected'] = False
        return True

    def _note_hardware_publish_failure(self):
        self._consecutive_hardware_publish_failures = int(self._consecutive_hardware_publish_failures or 0) + 1
        self._render_stats['consecutive_hardware_publish_failures'] = self._consecutive_hardware_publish_failures

    def _hardware_publish_age(self, now=None):
        now = float(now if now is not None else time.time())
        if self._last_successful_hardware_publish_ts > 0:
            return max(0.0, now - self._last_successful_hardware_publish_ts)
        if self._last_publish_hw_ts > 0:
            return max(0.0, now - self._last_publish_hw_ts)
        return None

    def _sync_display_control_stats(self):
        self._render_stats['display_enabled'] = bool(self._display_enabled)
        self._render_stats['display_sleep_reason'] = self._display_sleep_reason or ''
        self._render_stats['display_auto_off_seconds'] = int(self._display_auto_off_seconds or 0)
        self._render_stats['display_auto_off_deadline'] = float(self._display_auto_off_deadline or 0.0)
        self._render_stats['last_display_control_ts'] = float(self._last_display_control_ts or 0.0)
        self._render_stats['display_sleep_backend'] = self._display_sleep_backend()
        self._render_stats['display_sleep_backend_active'] = self._display_sleep_backend_active or ''
        self._render_stats['display_windows_sleep_active'] = bool(self._display_windows_sleep_active)
        self._render_stats['display_windows_last_error'] = self._display_windows_last_error or ''

    def _reset_display_auto_off_deadline_locked(self, now=None):
        now = float(now if now is not None else time.time())
        seconds = int(self._display_auto_off_seconds or 0)
        self._display_auto_off_deadline = now + seconds if seconds > 0 else 0.0
        return self._display_auto_off_deadline

    def _display_control_is_enabled(self):
        return bool(self.options.get('display_control_enabled', self.DEFAULT_OPTIONS['display_control_enabled']))

    def _display_control_disabled_status(self):
        status = self.display_status()
        status.update({'status': 'disabled', 'message': 'Display control is disabled in Refacer config.'})
        return status

    def _get_windows_plugin(self):
        plugin = plugins.loaded.get('windows')
        if not plugin:
            return None
        if hasattr(plugin, 'ready') and not plugin.ready:
            return None
        return plugin

    def _display_sleep_backend(self):
        backend = str(self.options.get('display_sleep_backend', 'auto') or 'auto').strip().lower()
        if backend not in ('blank', 'windows', 'auto'):
            backend = 'auto'
        return backend

    def _try_windows_sleep_start(self, reason='manual'):
        backend = self._display_sleep_backend()
        if backend == 'blank':
            return {'used': False, 'reason': 'blank_backend'}
        windows = self._get_windows_plugin()
        if windows is None:
            result = {'used': False, 'reason': 'windows_missing'}
            if backend == 'windows':
                result['error'] = 'windows_missing'
            return result
        try:
            mode = str(self.options.get('display_sleep_windows_mode') or 'screen_saver').strip() or 'screen_saver'
            sub_mode = str(self.options.get('display_sleep_windows_sub_mode') or '').strip() or None
            self._display_windows_previous_hijack = bool(getattr(windows, 'dispHijack', False))
            self._display_windows_previous_config = copy.deepcopy(getattr(windows, 'display_config', {}))
            if mode == 'screen_saver' and hasattr(windows, 'start_screen_saver'):
                previous = windows.start_screen_saver(sub_mode=sub_mode)
            else:
                previous = {
                    'dispHijack': self._display_windows_previous_hijack,
                    'display_config': copy.deepcopy(self._display_windows_previous_config),
                }
                windows.display_config['mode'] = mode
                if sub_mode:
                    windows.display_config['sub_mode'] = sub_mode
                windows.process_actions({'action': 'enable_second_screen'})
                controller = getattr(windows, 'display_controller', None)
                if controller is not None:
                    controller.set_mode(
                        windows.display_config.get('mode', mode),
                        windows.display_config.get('sub_mode', 'show_logo'),
                        windows.display_config.get('config', {}),
                    )
            self._display_windows_previous_state = previous
            self._display_windows_sleep_active = True
            self._display_sleep_backend_active = 'windows'
            self._display_windows_last_error = ''
            logging.info(f"[Refacer][display] windows sleep start reason={reason}")
            return {'used': True, 'backend': 'windows'}
        except Exception as exc:
            self._display_windows_last_error = str(exc)
            logging.warning(f"[Refacer][display] windows sleep start failed: {exc}")
            return {'used': False, 'error': str(exc)}

    def _wait_windows_handoff(self, windows, timeout=1.5):
        start = time.time()
        last = {
            'waited': 0.0,
            'dispHijack': None,
            'controller_present': None,
            'pending_restore_pwny': None,
            'controller_running': None,
            'timeout': False,
        }
        while time.time() - start < timeout:
            try:
                if hasattr(windows, 'status_payload'):
                    payload = windows.status_payload() or {}
                    disp_hijack = bool(payload.get('dispHijack', False))
                    controller_present = bool(payload.get('controller_present', False))
                    pending_restore = bool(payload.get('pending_restore_pwny', False))
                    controller_running = bool(payload.get('controller_running', False))
                else:
                    disp_hijack = bool(getattr(windows, 'dispHijack', False))
                    controller_present = getattr(windows, 'display_controller', None) is not None
                    pending_restore = False
                    controller_running = controller_present
                last.update({
                    'waited': time.time() - start,
                    'dispHijack': disp_hijack,
                    'controller_present': controller_present,
                    'pending_restore_pwny': pending_restore,
                    'controller_running': controller_running,
                    'timeout': False,
                })
                if (not disp_hijack and not controller_present) or (not disp_hijack and pending_restore):
                    return last
            except Exception as exc:
                last['error'] = str(exc)
                break
            time.sleep(0.05)
        last['waited'] = time.time() - start
        last['timeout'] = True
        return last

    def _try_windows_sleep_stop(self, reason='manual'):
        if not self._display_windows_sleep_active and self._display_sleep_backend_active != 'windows':
            return {'used': False, 'reason': 'not_active'}
        windows = self._get_windows_plugin()
        previous = self._display_windows_previous_state
        try:
            if windows is not None:
                if hasattr(windows, 'stop_screen_saver'):
                    restore_previous = previous if self.options.get('display_sleep_windows_restore_previous', False) else None
                    windows.stop_screen_saver(restore_previous)
                elif hasattr(windows, 'disable_second_screen'):
                    windows.disable_second_screen()
                else:
                    windows.process_actions({'action': 'disable_second_screen'})
                    if self.options.get('display_sleep_windows_restore_previous', False) and isinstance(previous, dict):
                        windows.display_config = previous.get('display_config', getattr(windows, 'display_config', {}))
                handoff = self._wait_windows_handoff(windows)
            else:
                handoff = {'timeout': False, 'windows_missing': True}
            logging.info(f"[Refacer][display] windows sleep stop reason={reason}")
            result = {'used': True, 'backend': 'windows', 'handoff': handoff}
            if handoff.get('timeout'):
                self._display_windows_last_error = 'windows handoff still active'
                result['warning'] = self._display_windows_last_error
        except Exception as exc:
            self._display_windows_last_error = str(exc)
            logging.warning(f"[Refacer][display] windows sleep stop failed: {exc}")
            result = {'used': True, 'backend': 'windows', 'error': str(exc)}
        self._display_windows_sleep_active = False
        self._display_sleep_backend_active = ''
        self._display_windows_previous_state = None
        self._display_windows_previous_config = None
        self._display_windows_previous_hijack = None
        return result

    def _blank_canvas(self):
        width, height = self._canvas_size()
        color = self.options.get('display_blank_color', self.DEFAULT_OPTIONS['display_blank_color']) or 'black'
        try:
            ImageColor.getcolor(str(color), 'RGBA')
        except Exception:
            color = self.DEFAULT_OPTIONS['display_blank_color']
        return Image.new('RGBA', (width, height), color)

    def _publish_control_canvas(self, canvas, *, reason='manual'):
        if canvas is None:
            return False, 'no canvas available'
        try:
            with self._display_recovery_lock:
                sink = None
                if self._view_instance is not None:
                    sink = getattr(self._view_instance, '_implementation', None)
                if sink is None:
                    return False, 'no display implementation available'
                frame = self._prepare_hardware_frame(canvas)
                sink.render(frame)
            self._mark_render_progress(time.time(), published_hw=True)
            return True, ''
        except Exception as exc:
            logging.warning(f"[Refacer][display] publish failed reason={reason}: {exc}")
            return False, str(exc)

    def _publish_blank_frame(self, reason='manual_clear'):
        canvas = self._blank_canvas()
        ok, error = self._publish_control_canvas(canvas, reason=reason)
        if ok:
            logging.info(f"[Refacer][display] blank frame published reason={reason}")
        return ok, error

    def display_status(self):
        with self._display_control_lock:
            now = time.time()
            deadline = float(self._display_auto_off_deadline or 0.0)
            remaining = max(0.0, deadline - now) if deadline > 0 else 0.0
            status = {
                'status': 'success',
                'control_enabled': self._display_control_is_enabled(),
                'enabled': bool(self._display_enabled),
                'off': not bool(self._display_enabled),
                'state': 'on' if self._display_enabled else 'off',
                'sleep_reason': self._display_sleep_reason or '',
                'timer_seconds': int(self._display_auto_off_seconds or 0),
                'auto_off_seconds': int(self._display_auto_off_seconds or 0),
                'auto_off_deadline': deadline,
                'auto_off_remaining': remaining,
                'last_control_ts': float(self._last_display_control_ts or 0.0),
                'sleep_backend': self._display_sleep_backend(),
                'sleep_backend_active': self._display_sleep_backend_active or ('windows' if self._display_windows_sleep_active else ''),
                'windows_sleep_active': bool(self._display_windows_sleep_active),
                'windows_error': self._display_windows_last_error or '',
                'windows_handoff_pending': False,
                'windows_disp_hijack': None,
                'windows_controller_present': None,
                'windows_controller_running': None,
            }
            windows = self._get_windows_plugin()
            if windows is not None:
                try:
                    if hasattr(windows, 'status_payload'):
                        payload = windows.status_payload() or {}
                        status['windows_disp_hijack'] = bool(payload.get('dispHijack', False))
                        status['windows_controller_present'] = bool(payload.get('controller_present', False))
                        status['windows_controller_running'] = bool(payload.get('controller_running', False))
                        status['windows_handoff_pending'] = bool(payload.get('pending_restore_pwny', False))
                    else:
                        status['windows_disp_hijack'] = bool(getattr(windows, 'dispHijack', False))
                        status['windows_controller_present'] = getattr(windows, 'display_controller', None) is not None
                        status['windows_controller_running'] = bool(status['windows_controller_present'])
                except Exception:
                    pass
            self._sync_display_control_stats()
            return status

    def display_on(self, reason='manual'):
        if not self._display_control_is_enabled():
            return self._display_control_disabled_status()
        backend_result = self._try_windows_sleep_stop(reason=reason)
        with self._display_control_lock:
            now = time.time()
            self._display_enabled = True
            self._display_sleep_reason = ''
            self._display_sleep_backend_active = ''
            self._last_display_control_ts = now
            self._reset_display_auto_off_deadline_locked(now)
            self._sync_display_control_stats()
            canvas = None if backend_result.get('backend') == 'windows' else (
                self._last_known_good_canvas.copy() if self._last_known_good_canvas is not None else self._best_cached_canvas()
            )
        if canvas is not None:
            ok, error = self._publish_control_canvas(canvas, reason=reason)
            if not ok:
                status = self.display_status()
                status.update({'status': 'error', 'message': error})
                return status
        logging.info(f"[Refacer][display] on reason={reason}")
        status = self.display_status()
        status['message'] = 'Display on.'
        status['backend_result'] = backend_result
        return status

    def display_off(self, reason='manual'):
        if not self._display_control_is_enabled():
            return self._display_control_disabled_status()
        backend_result = self._try_windows_sleep_start(reason=reason)
        if backend_result.get('used'):
            with self._display_control_lock:
                now = time.time()
                self._display_enabled = False
                self._display_sleep_reason = str(reason or 'manual')
                self._last_display_control_ts = now
                self._sync_display_control_stats()
            status = self.display_status()
            status.update({'message': 'Display off.', 'backend': 'windows', 'backend_result': backend_result})
            return status
        with self._display_control_lock:
            now = time.time()
            self._display_enabled = False
            self._display_sleep_reason = str(reason or 'manual')
            self._display_sleep_backend_active = 'blank'
            self._last_display_control_ts = now
            self._sync_display_control_stats()
        ok, error = self._publish_blank_frame(reason='display_off:%s' % (reason or 'manual'))
        logging.info(f"[Refacer][display] off reason={reason}")
        status = self.display_status()
        if ok:
            status['message'] = 'Display off.'
        else:
            status.update({'status': 'error', 'message': error})
        status['backend'] = 'blank'
        status['backend_result'] = backend_result
        if backend_result.get('error') and self._display_sleep_backend() == 'windows':
            status.update({'status': 'error', 'message': backend_result.get('error')})
        return status

    def display_toggle(self, reason='manual'):
        with self._display_control_lock:
            enabled = bool(self._display_enabled)
        return self.display_off(reason=reason) if enabled else self.display_on(reason=reason)

    def display_clear(self, reason='manual'):
        if not self._display_control_is_enabled():
            return self._display_control_disabled_status()
        ok, error = self._publish_blank_frame(reason='manual_clear:%s' % (reason or 'manual'))
        with self._display_control_lock:
            self._last_display_control_ts = time.time()
            self._sync_display_control_stats()
        logging.info(f"[Refacer][display] clear reason={reason}")
        status = self.display_status()
        if ok:
            status['message'] = 'Display cleared.'
        else:
            status.update({'status': 'error', 'message': error})
        return status

    def display_set_timer(self, seconds):
        if not self._display_control_is_enabled():
            return self._display_control_disabled_status()
        seconds = self._sanitize_int(seconds, 0, minimum=0)
        with self._display_control_lock:
            now = time.time()
            self._display_auto_off_seconds = seconds
            self.options['display_auto_off_seconds'] = seconds
            self._last_display_control_ts = now
            self._reset_display_auto_off_deadline_locked(now)
            self._sync_display_control_stats()
        logging.info(f"[Refacer][display] timer seconds={seconds}")
        status = self.display_status()
        status['message'] = 'Display timer %s.' % ('off' if seconds <= 0 else f'{seconds}s')
        return status

    def _display_timer_due(self, now=None):
        if not self._display_control_is_enabled():
            return False
        now = float(now if now is not None else time.time())
        with self._display_control_lock:
            return bool(self._display_enabled and self._display_auto_off_deadline > 0 and now >= self._display_auto_off_deadline)

    def _display_hardware_publish_allowed(self):
        if not self._display_control_is_enabled():
            return True
        with self._display_control_lock:
            return bool(self._display_enabled)

    def _display_timer_seconds_from_request(self, req):
        data = {}
        try:
            data = req.get_json(silent=True) or {}
        except TypeError:
            try:
                data = req.get_json() or {}
            except Exception:
                data = {}
        value = data.get('seconds') if isinstance(data, dict) else None
        if value is None:
            value = req.values.get('seconds')
        return value if value is not None else 0

    def _prepare_hardware_frame(self, canvas):
        frame = canvas.copy()
        rotation = self._current_rotation()
        if rotation == 90:
            frame = frame.rotate(90, expand=True)
        elif rotation == 180:
            frame = frame.rotate(180, expand=True)
        elif rotation == 270:
            frame = frame.rotate(270, expand=True)

        physical_width, physical_height = self._physical_canvas_size()
        if frame.size != (physical_width, physical_height):
            frame = frame.resize((physical_width, physical_height), Image.NEAREST)

        theme_declared = self._theme_declared_color_mode()
        resolved_mode = self._resolve_display_output_mode()
        preview_mode = getattr(canvas, 'mode', None)
        frame = self._convert_frame_to_display_mode(frame, resolved_mode)
        self._render_palette_debug['display_output'] = {
            'theme_declared_color_mode': theme_declared,
            'resolved_mode': resolved_mode,
            'final_frame_mode': getattr(frame, 'mode', None),
            'preview_frame_mode': preview_mode,
        }
        logging.debug(
            f"[Refacer][render] theme color_mode={theme_declared!r} resolved display mode={resolved_mode}"
        )
        logging.debug(
            f"[Refacer][render] final display frame mode={getattr(frame, 'mode', None)} "
            f"preview frame mode={preview_mode}"
        )
        return frame

    def _best_cached_canvas(self):
        if self._last_render_canvas is not None:
            return self._last_render_canvas.copy()
        if self._recovery_cache_active and self._last_known_good_canvas is not None:
            return self._last_known_good_canvas.copy()
        return None

    def _kick_display_backlight(self, implementation):
        if implementation is None:
            return
        try:
            if hasattr(implementation, 'set_backlight'):
                implementation.set_backlight(1)
                return
        except Exception:
            pass
        try:
            display_device = getattr(implementation, '_display', None)
            if display_device is not None and hasattr(display_device, 'set_backlight'):
                display_device.set_backlight(1)
        except Exception:
            pass

    def _republish_cached_frame(self, canvas=None, implementation=None):
        self._expire_recovery_cache_handoff_if_needed()
        if not self._recovery_cache_active and self._last_render_canvas is not None:
            logging.info("[Refacer][recovery] cached republish skipped because fresh live frame is available")
            canvas = canvas.copy() if canvas is not None else self._last_render_canvas.copy()
        else:
            canvas = canvas.copy() if canvas is not None else self._best_cached_canvas()
        if canvas is None:
            return None

        self._last_render_canvas = canvas.copy()
        if self._view_instance is not None:
            try:
                self._view_instance._refacer_web_canvas = canvas.copy()
            except Exception:
                pass
        try:
            import pwnagotchi.ui.web as web
            web.update_frame(canvas.copy())
        except Exception:
            pass

        republish_now = time.time()
        self._last_known_good_canvas = canvas.copy()
        self._recovery_cache_active = True
        self._recovery_cache_started_ts = republish_now
        self._fresh_publish_streak_after_recovery = 0
        logging.info("[Refacer][recovery] cached-frame handoff activated")
        logging.info("[Refacer][recovery] cached frame prepared for recovery handoff; awaiting confirmed hardware publish")
        return canvas

    def _attempt_direct_fallback_publish(self, canvas=None, implementation=None, *, reason='', now=None, enforce_interval=True, initial=False):
        now = float(now if now is not None else time.time())
        if enforce_interval and (now - float(self._last_direct_fallback_publish_attempt_ts or 0.0)) < self._direct_fallback_publish_interval_s():
            return False
        self._last_direct_fallback_publish_attempt_ts = now

        canvas = canvas.copy() if canvas is not None else self._best_cached_canvas()
        if canvas is None:
            return False

        try:
            with self._display_recovery_lock:
                sink = implementation
                if sink is None and self._view_instance is not None:
                    sink = getattr(self._view_instance, '_implementation', None)
                if sink is None:
                    return False
                frame = self._prepare_hardware_frame(canvas)
                sink.render(frame)
            self._last_known_good_canvas = canvas.copy()
            self._mark_render_progress(now, published_hw=True)
            if self._watchdog_recoveries > 0:
                self._fresh_publishes_since_recovery += 1
            self._set_render_tier('reduced', 'direct_fallback_publish')
            if initial:
                logging.info("[Refacer][recovery] direct fallback publish succeeded after display reinit")
                self._last_direct_fallback_keepalive_log_ts = now
            elif (now - float(self._last_direct_fallback_keepalive_log_ts or 0.0)) >= self._direct_fallback_keepalive_log_interval_s():
                logging.info(
                    "[Refacer][recovery] direct fallback publish keeping display alive while waiting for normal render publish"
                )
                self._last_direct_fallback_keepalive_log_ts = now
            return True
        except Exception as exc:
            self._note_hardware_publish_failure()
            logging.warning(f"[Refacer][recovery] direct fallback publish failed: {exc}")
            return False

    def _attempt_display_reinit(self):
        with self._display_recovery_lock:
            if self._display_recovery_in_progress:
                return False
            self._display_recovery_in_progress = True

        try:
            now = time.time()
            self._clear_recovery_cache_handoff()
            self._fresh_publishes_since_recovery = 0
            self._last_direct_fallback_publish_attempt_ts = 0.0
            self._last_direct_fallback_keepalive_log_ts = 0.0
            self._post_reset_quarantine_logged = False
            self._last_display_reinit_ts = now
            self._display_reinit_count = int(self._display_reinit_count or 0) + 1
            self._render_stats['last_display_reinit_ts'] = now
            self._render_stats['display_reinit_count'] = self._display_reinit_count
            logging.warning(f"[Refacer][recovery] display reinit attempt #{self._display_reinit_count}")

            self._invalidate_render_generation(reason='display_reinit')
            render_thread = self._render_thread
            current_thread = threading.current_thread()
            restart_render_thread = True
            if render_thread and render_thread.is_alive() and render_thread is not current_thread:
                self._running = False
                render_thread.join(timeout=1.0)
                if render_thread.is_alive():
                    logging.warning(
                        "[Refacer][recovery] stale render thread generation=%s ignored after timeout"
                        % getattr(render_thread, '_refacer_generation', 'unknown')
                    )
                    logging.warning("[Refacer][recovery] continuing display reinit with stale thread logically invalidated")

            implementation = None
            try:
                from pwnagotchi.ui.hw import display_for

                config = self._plugin_config()
                display_cfg = config.setdefault('ui', {}).setdefault('display', {})
                display_cfg['enabled'] = True
                display_cfg['rotation'] = 0

                implementation = display_for(config)
                if implementation is None:
                    logging.warning("[Refacer][recovery] display reinit failed: no display backend")
                    return False

                if hasattr(implementation, 'config') and isinstance(implementation.config, dict):
                    implementation.config['enabled'] = True
                    implementation.config['rotation'] = 0

                if hasattr(implementation, 'initialize'):
                    implementation.initialize()
                self._kick_display_backlight(implementation)

                if self._view_instance is not None and hasattr(self._view_instance, '_implementation'):
                    self._view_instance._implementation = implementation
                    if hasattr(self._view_instance, '_enabled'):
                        self._view_instance._enabled = True
                logging.info("[Refacer][recovery] display object recreated and initialized")
            except Exception as exc:
                logging.warning(f"[Refacer][recovery] display reinit failed: {exc}")
                return False

            staged_canvas = self._republish_cached_frame(implementation=implementation)
            if staged_canvas is None:
                logging.warning("[Refacer][recovery] display reinit has no cached frame available for fallback publish")
            elif not self._attempt_direct_fallback_publish(
                canvas=staged_canvas,
                implementation=implementation,
                reason='display_reinit',
                now=time.time(),
                enforce_interval=False,
                initial=True,
            ):
                logging.warning("[Refacer][recovery] display reinit awaiting normal render publish after direct fallback failure")

            self._render_pressure['busy_drop_streak'] = 0
            self._render_pressure['over_budget_streak'] = 0
            self._render_pressure['recovery_streak'] = 0
            self._set_render_tier('reduced', 'display_reinit')
            logging.info("[Refacer][recovery] forcing tier=reduced after display reinit")

            if restart_render_thread:
                try:
                    self._start_render_thread()
                except Exception as exc:
                    logging.warning(f"[Refacer][recovery] render thread restart after display reinit failed: {exc}")
                    return False

            self._reset_generation += 1
            self._render_stats['reset_generation'] = self._reset_generation
            self._post_reset_quarantine_until = time.time() + self._post_reset_quarantine_s()
            self._post_reset_quarantine_logged = False
            return True
        finally:
            self._display_recovery_in_progress = False


    def _driver_reset_capability(self, implementation):
        try:
            display = getattr(implementation, '_display', None)
            has_reset = display is not None and callable(getattr(display, 'reset', None))
            has_init = display is not None and callable(getattr(display, 'init', None))
            has_impl_init = callable(getattr(implementation, 'initialize', None))
            if has_reset and has_init:
                def _hw_reset_fn():
                    display.reset()
                    time.sleep(0.05)
                    display.init()
                    if has_impl_init:
                        implementation.initialize()
                return ('hw_reset', _hw_reset_fn)
            if has_init:
                def _driver_init_fn():
                    display.init()
                    if has_impl_init:
                        implementation.initialize()
                return ('driver_init', _driver_init_fn)
            if has_impl_init:
                return ('impl_initialize', implementation.initialize)
            return ('none', None)
        except Exception:
            return ('none', None)

    def _attempt_driver_reset(self):
        with self._display_recovery_lock:
            if self._display_recovery_in_progress:
                return False
            self._display_recovery_in_progress = True

        try:
            now = time.time()
            self._fresh_publishes_since_recovery = 0
            if (now - self._last_driver_reset_ts) < self._driver_reset_cooldown_s():
                remaining = self._driver_reset_cooldown_s() - (now - self._last_driver_reset_ts)
                logging.debug(f"[Refacer][recovery] driver reset cooldown skip remaining={remaining:.1f}s")
                return False

            self._invalidate_render_generation(reason='driver_reset')
            render_thread = self._render_thread
            current_thread = threading.current_thread()
            restart_render_thread = True
            if render_thread and render_thread.is_alive() and render_thread is not current_thread:
                self._running = False
                render_thread.join(timeout=1.0)
                if render_thread.is_alive():
                    logging.warning(
                        "[Refacer][recovery] stale render thread generation=%s ignored after timeout"
                        % getattr(render_thread, '_refacer_generation', 'unknown')
                    )
                    logging.warning("[Refacer][recovery] continuing driver reset with stale thread logically invalidated")

            if self._view_instance is None or not hasattr(self._view_instance, '_implementation'):
                logging.debug("[Refacer][recovery] driver reset skipped: no view implementation")
                return False

            implementation = self._view_instance._implementation
            capability, reset_fn = self._driver_reset_capability(implementation)

            if capability == 'none':
                logging.warning("[Refacer][recovery] driver reset unavailable for this display type")
                return False

            try:
                reset_fn()
                self._kick_display_backlight(implementation)
            except Exception as exc:
                logging.warning(f"[Refacer][recovery] driver reset via {capability} failed: {exc}")
                return False

            self._driver_reset_count = int(self._driver_reset_count or 0) + 1
            self._last_driver_reset_ts = now
            self._last_driver_reset_capability = capability
            self._render_stats['driver_reset_count'] = self._driver_reset_count
            self._render_stats['last_driver_reset_ts'] = now
            self._render_stats['last_driver_reset_capability'] = capability
            logging.warning(f"[Refacer][recovery] driver reset via capability={capability} succeeded")

            self._republish_cached_frame(implementation=implementation)
            self._render_pressure['busy_drop_streak'] = 0
            self._render_pressure['over_budget_streak'] = 0
            self._render_pressure['recovery_streak'] = 0
            self._set_render_tier('reduced', 'driver_reset')
            self._display_wedge_suspected = False
            self._render_stats['display_wedge_suspected'] = False

            if restart_render_thread:
                try:
                    self._start_render_thread()
                except Exception as exc:
                    logging.warning(f"[Refacer][recovery] render thread restart after driver reset failed: {exc}")
                    return False

            self._reset_generation += 1
            self._render_stats['reset_generation'] = self._reset_generation
            self._post_reset_quarantine_until = time.time() + self._post_reset_quarantine_s()
            return True
        except Exception as exc:
            logging.warning(f"[Refacer][recovery] driver reset unexpected error: {exc}")
            return False
        finally:
            self._display_recovery_in_progress = False

    def _start_render_thread(self):
        self._watchdog_fallback_active = False
        self._render_stats['watchdog_fallback_active'] = False
        self._running = True
        generation = self._next_render_generation()
        self._render_thread = threading.Thread(
            target=self._render_loop,
            args=(generation,),
            daemon=True,
            name=f"RefacerRender-{generation}",
        )
        self._render_thread._refacer_generation = generation
        self._render_thread.start()
        logging.info(f"[Refacer] Render loop started at {self.fps} FPS generation={generation}.")

    def _evaluate_render_watchdog(self, now=None):
        if not self.enabled or not self._running:
            return
        if self._watchdog_in_recovery:
            return
        if self._display_recovery_in_progress:
            return
        if self._view_instance is None:
            return

        now = float(now if now is not None else time.time())
        self._last_watchdog_check_ts = now
        if self._display_control_is_enabled() and not self._display_hardware_publish_allowed():
            # Intentional Refacer screen sleep lets hardware publish age grow; do not treat it as a display wedge.
            self._watchdog_warned_stale = False
            self._display_wedge_suspected = False
            self._render_stats['display_wedge_suspected'] = False
            self._sync_display_control_stats()
            return

        if self._last_compose_success_ts <= 0:
            return
        compose_age = max(0.0, now - self._last_compose_success_ts)
        hw_age = self._hardware_publish_age(now)

        warn_threshold = self._watchdog_warn_threshold_s()
        recover_threshold = self._watchdog_recover_threshold_s()
        display_reinit_threshold = self._display_reinit_threshold_s()
        render_stalled = compose_age > warn_threshold
        hardware_stale = hw_age is None or hw_age > warn_threshold

        if not render_stalled and not hardware_stale:
            self._watchdog_warned_stale = False
            self._display_wedge_suspected = False
            self._render_stats['display_wedge_suspected'] = False
            return

        if render_stalled and compose_age <= recover_threshold:
            if not self._watchdog_warned_stale:
                logging.warning(
                    "[Refacer][watchdog] render stalled age=%.2f hw_age=%s compose_age=%s"
                    % (
                        compose_age,
                        "n/a" if hw_age is None else f"{hw_age:.2f}",
                        f"{compose_age:.2f}",
                    )
                )
                self._watchdog_warned_stale = True
            return

        if render_stalled:
            if (now - float(self._watchdog_last_recovery_ts or 0.0)) <= self._watchdog_cooldown_s():
                return
            self._recover_from_render_stall(reason='compose_progress_stale')
            return

        self._display_wedge_suspected = True
        self._render_stats['display_wedge_suspected'] = True
        stale_age = hw_age if hw_age is not None else compose_age
        if not self._watchdog_warned_stale:
            logging.warning("[Refacer][watchdog] hardware publish stale age=%.2fs" % stale_age)
            self._watchdog_warned_stale = True

        soft_recovery_has_not_helped = (
            self._watchdog_last_recovery_ts > 0
            and self._watchdog_last_recovery_ts >= float(self._last_successful_hardware_publish_ts or 0.0)
        )
        should_reinit = (
            stale_age > display_reinit_threshold
            or self._consecutive_hardware_publish_failures >= self._display_publish_failure_threshold()
            or soft_recovery_has_not_helped
        )
        if not should_reinit:
            if stale_age > recover_threshold and (now - float(self._watchdog_last_recovery_ts or 0.0)) > self._watchdog_cooldown_s():
                self._recover_from_render_stall(reason='hardware_publish_stale')
            return

        if now < float(self._post_reset_quarantine_until or 0.0):
            if not self._post_reset_quarantine_logged:
                remaining = max(0.0, float(self._post_reset_quarantine_until or 0.0) - now)
                logging.info("[Refacer][recovery] post-reinit grace active remaining=%.1fs" % remaining)
                self._post_reset_quarantine_logged = True
            self._attempt_direct_fallback_publish(reason='post_reinit_grace', now=now)
            return

        self._post_reset_quarantine_logged = False
        allow_reinit = self._last_successful_hardware_publish_ts <= 0 or (
            (now - float(self._last_display_reinit_ts or 0.0)) >= self._display_reinit_cooldown_s()
        )
        if not allow_reinit:
            if not self._display_reinit_skip_logged:
                remaining = max(0.0, self._display_reinit_cooldown_s() - (now - float(self._last_display_reinit_ts or 0.0)))
                logging.info("[Refacer][recovery] display reinit cooldown skip remaining=%.1fs" % remaining)
                self._display_reinit_skip_logged = True
            self._attempt_direct_fallback_publish(reason='display_reinit_cooldown', now=now)
            return

        logging.warning("[Refacer][watchdog] escalating to display reinit")
        if self._attempt_display_reinit():
            return
        if self._watchdog_recoveries >= 2:
            self._fallback_to_stock_renderer(reason='hardware_publish_stale')

    def _recover_from_render_stall(self, reason=''):
        if self._watchdog_in_recovery:
            return

        self._watchdog_in_recovery = True
        try:
            now = time.time()
            self._fresh_publishes_since_recovery = 0
            self._watchdog_recoveries += 1
            self._watchdog_last_reason = str(reason or '')
            self._watchdog_last_recovery_ts = now
            self._render_stats['watchdog_recoveries'] = self._watchdog_recoveries
            self._render_stats['watchdog_last_reason'] = self._watchdog_last_reason
            self._render_stats['watchdog_fallback_active'] = self._watchdog_fallback_active
            self._watchdog_warned_stale = False
            logging.warning(
                f"[Refacer][watchdog] recovering from render stall reason={self._watchdog_last_reason or 'unknown'} count={self._watchdog_recoveries}"
            )

            if self._watchdog_recoveries >= 2:
                if reason in ('hardware_publish_stale', 'compose_progress_stale'):
                    logging.warning("[Refacer][watchdog] escalating to display reinit")
                    if self._attempt_display_reinit():
                        return
                    logging.warning("[Refacer][watchdog] display reinit failed, trying driver reset")
                    if self._attempt_driver_reset():
                        return
            if self._watchdog_recoveries >= self._watchdog_terminal_threshold():
                self._fallback_to_stock_renderer(reason=reason)
                return

            render_thread = self._render_thread
            self._invalidate_render_generation(reason=f"watchdog_restart:{reason or 'unknown'}")
            self._running = False
            if render_thread and render_thread.is_alive() and render_thread is not threading.current_thread():
                render_thread.join(timeout=1.0)
                if render_thread.is_alive():
                    logging.warning(
                        "[Refacer][recovery] stale render thread generation=%s ignored after timeout"
                        % getattr(render_thread, '_refacer_generation', 'unknown')
                    )

            self._clear_recovery_cache_handoff()
            self._last_render_canvas = None
            self._render_cycle_lock = threading.Lock()
            self._render_pressure['busy_drop_streak'] = 0
            self._render_pressure['over_budget_streak'] = 0
            self._render_pressure['recovery_streak'] = 0
            self._set_render_tier('full', '')

            try:
                self._start_render_thread()
            except Exception as exc:
                logging.warning(f"[Refacer][watchdog] render thread restart failed: {exc}")
                self._fallback_to_stock_renderer(reason=reason)
                return

            self._reset_generation += 1
            self._render_stats['reset_generation'] = self._reset_generation
            self._render_stats['watchdog_fallback_active'] = False
            logging.warning("[Refacer][watchdog] render thread restarted")
        finally:
            self._watchdog_in_recovery = False

    def _fallback_to_stock_renderer(self, reason=''):
        self._invalidate_render_generation(reason=f"fallback:{reason or 'unknown'}")
        self._clear_recovery_cache_handoff()
        self._watchdog_fallback_active = True
        self._render_stats['watchdog_fallback_active'] = True
        self._running = False
        render_thread = self._render_thread
        if render_thread and render_thread.is_alive() and render_thread is not threading.current_thread():
            render_thread.join(timeout=1.0)
        self._render_thread = None

        view_instance = self._view_instance
        if self._old_update is not None:
            view.View.update = self._old_update
        self._detach_refacer_view_state()
        if view_instance is not None and self._old_update is not None:
            try:
                self._old_update(view_instance, force=True, new_data={})
            except Exception as exc:
                logging.warning(f"[Refacer][watchdog] stock redraw failed during fallback: {exc}")
        logging.warning(f"[Refacer][watchdog] fallback to stock ui reason={reason or 'unknown'}")

    def _record_publish_timing(self, publish_ms):
        publish_ms = float(max(0.0, publish_ms))
        stats = self._render_stats
        stats['last_publish_ms'] = publish_ms
        stats['avg_publish_ms'] = self._update_moving_average(stats.get('avg_publish_ms', 0.0), publish_ms)

    def _set_render_tier(self, tier, reason='', generation=None):
        if generation is not None and not self._render_generation_is_active(generation):
            return
        tier = tier if tier in ('full', 'reduced', 'minimal') else 'full'
        stats = self._render_stats
        previous = stats.get('current_tier', 'full')
        stats['current_tier'] = tier
        stats['degrade_reason'] = str(reason or '')
        if tier == previous:
            return
        self._last_tier_change_ts = time.time()
        if tier in ('reduced', 'minimal'):
            logging.warning(f"[Refacer][render] degraded tier={tier} reason={stats['degrade_reason'] or 'pressure'}")
        else:
            logging.info(f"[Refacer][render] recovered tier={tier}")

    def _update_render_tier(self, *, over_budget=False, busy_drop=False, successful=False, generation=None):
        if generation is not None and not self._render_generation_is_active(generation):
            return
        pressure = self._render_pressure
        stats = self._render_stats
        current = stats.get('current_tier', 'full')

        if busy_drop:
            pressure['busy_drop_streak'] = int(pressure.get('busy_drop_streak', 0)) + 1
            pressure['recovery_streak'] = 0
        else:
            pressure['busy_drop_streak'] = 0

        if over_budget:
            pressure['over_budget_streak'] = int(pressure.get('over_budget_streak', 0)) + 1
            pressure['recovery_streak'] = 0
        elif successful:
            pressure['over_budget_streak'] = 0
            pressure['recovery_streak'] = int(pressure.get('recovery_streak', 0)) + 1

        if current == 'full':
            if pressure['busy_drop_streak'] >= 4:
                self._set_render_tier('reduced', 'busy_drops')
                pressure['recovery_streak'] = 0
            elif pressure['over_budget_streak'] >= 6:
                self._set_render_tier('reduced', 'over_budget')
                pressure['recovery_streak'] = 0
        elif current == 'reduced':
            cooldown_ok = (time.time() - self._last_tier_change_ts) >= 60.0
            if cooldown_ok and (pressure['busy_drop_streak'] >= 8 or pressure['over_budget_streak'] >= 10):
                self._set_render_tier('minimal', 'sustained_pressure')
                pressure['recovery_streak'] = 0
            elif successful and pressure['recovery_streak'] >= 40:
                self._set_render_tier('full', 'stable')
        elif current == 'minimal':
            if successful and pressure['recovery_streak'] >= 30:
                self._set_render_tier('reduced', 'stable')

    def on_ready(self, agent):
        self._agent = agent
        logging.debug("[Refacer] Agent ready.")
        # Re-resolve the theme now that the agent config (and display resolution) is available.
        # Themes with only resolution-specific configs (no config/config.toml) need this.
        if self._theme_name and self._theme_name != 'Default':
            self._reload_theme_state()
            self._maybe_play_boot_animation('startup')

    def on_loaded(self):
        self._load_render_options()
        self._ensure_theme_root()
        self._rebuild_repo_screenshots_tree()

        # Minimal: one synchronous black frame to whatever callbacks exist right now.
        # No state mutation, no thread coordination, no hardware path changes.
        try:
            root = getattr(view, 'ROOT', None)
            if root is not None:
                w = int(getattr(root, '_width', 250))
                h = int(getattr(root, '_height', 122))
                black = Image.new('1', (w, h), 0)
                for cb in (getattr(root, '_render_cbs', None) or []):
                    try:
                        cb(black)
                    except Exception:
                        pass
        except Exception:
            pass

        if not hasattr(view, 'View'):
            logging.error("[Refacer] View class not found, delaying patch.")
            return

        # Capture the view instance before loading the theme so _current_resolution()
        # can return the correct dimensions. Themes with only resolution-specific configs
        # (e.g. config/250x122/config.toml) would silently fall back to Default otherwise.
        if self._view_instance is None and getattr(view, 'ROOT', None) is not None:
            self._view_instance = view.ROOT
            logging.debug("[Refacer][boot] view instance captured eagerly from view.ROOT")

        self._reload_theme_state()
        self._maybe_play_boot_animation('startup')
        self._inject_theme_css(self._theme_name or 'Default')

        if self._old_update is None:
            self._old_update = view.View.update

        if not hasattr(view.View, '_refacer_patched'):
            def get_web(instance):
                return getattr(instance, '_refacer_web_canvas', None)

            def set_web(instance, value):
                if getattr(instance, '_refacer_block_web', False):
                    return
                setattr(instance, '_refacer_web_canvas', value)

            if view.ROOT and '_web_canvas' in view.ROOT.__dict__:
                setattr(view.ROOT, '_refacer_web_canvas', view.ROOT.__dict__['_web_canvas'])
                del view.ROOT.__dict__['_web_canvas']

            view.View._web_canvas = property(get_web, set_web)
            view.View._refacer_patched = True

        refacer = self

        def wrapped_update(view_instance, force=False, new_data=None):
            if new_data is None:
                new_data = {}

            if refacer.enabled and refacer._running:
                logging.debug("[Refacer][lock] update snapshot start")
                refacer._view_instance = view_instance
                view_instance._refacer_hidden_cbs = list(view_instance._render_cbs or [])
                view_instance._render_cbs = []
                view_instance._refacer_block_web = True
                logging.debug("[Refacer][web] suppressed stock web publish during capture")

                try:
                    refacer._update_view_state_only(view_instance, force=force, new_data=new_data)
                    refacer._last_stock_canvas = None
                    if refacer._theme_name == 'Default':
                        logging.debug("[Refacer][core] default theme using state-only bypass")
                    else:
                        logging.debug("[Refacer][core] non-default theme using state-only bypass")
                finally:
                    view_instance._render_cbs = view_instance._refacer_hidden_cbs
                    view_instance._refacer_block_web = False
                    if hasattr(view_instance, '_refacer_hidden_cbs'):
                        del view_instance._refacer_hidden_cbs
                    logging.debug("[Refacer][lock] update snapshot end")
            else:
                refacer._old_update(view_instance, force=force, new_data=new_data)

        view.View.update = wrapped_update

        if not self._render_thread or not self._render_thread.is_alive():
            self._start_render_thread()

    # Keep stock state/plugin updates, but bypass stock canvas generation while Refacer owns rendering.
    def _update_view_state_only(self, view_instance, force=False, new_data=None):
        new_data = new_data or {}
        for key, val in new_data.items():
            view_instance.set(key, val)

        with view_instance._lock:
            if view_instance._frozen:
                return False

            state = view_instance._state
            changes = state.changes(ignore=getattr(view_instance, '_ignore_changes', ()))
            if force or len(changes):
                plugins.on('ui_update', view_instance)
                state.reset()
                logging.debug("[Refacer][core] stock render bypassed")
                return True
        return False

    def on_unload(self, ui):
        logging.info("[Refacer][lifecycle] unload start")
        try:
            self._restore_original_pwnagotchi_css()
        except Exception as e:
            logging.error(f"[Refacer][css] on_unload restore error: {e}")
        self.enabled = False
        self._clear_recovery_cache_handoff()
        self._running = False
        if self._boot_anim_load_thread and self._boot_anim_load_thread.is_alive():
            self._boot_anim_load_thread.join(timeout=0.5)
        self._boot_anim_load_thread = None
        if self._render_thread:
            logging.debug("[Refacer][lifecycle] unload waiting for render thread")
            self._render_thread.join(timeout=1)
            if self._render_thread.is_alive():
                logging.warning("[Refacer][lifecycle] render thread still alive after timeout")
        self._render_thread = None
        view_instance = self._view_instance
        if self._old_update is not None:
            view.View.update = self._old_update
            if view_instance is not None:
                try:
                    self._old_update(view_instance, force=True, new_data={})
                    logging.debug("[Refacer][lifecycle] restored stock renderer")
                except Exception as exc:
                    logging.warning(f"[Refacer][lifecycle] stock redraw failed during unload: {exc}")
        self._detach_refacer_view_state()
        self._cleanup_repo_screenshots_tree()
        self._reset_runtime_render_state(clear_theme=False)
        logging.info("[Refacer][lifecycle] unload complete")

    def on_webhook(self, path, request):
        path = (path or '').strip('/')
        action = path.lower()
        logging.debug(f"[Refacer][webui] webhook {request.method} {path or '/'}")

        if request.method == "GET":
            if not path:
                return render_template_string(
                    TEMPLATE,
                    options=self.options,
                    active_theme=self._theme_name,
                )
            if path == "debug/js_ping":
                logging.debug("[Refacer][webui] js bootstrap reached")
                return jsonify({'status': 'ok'})
            if path == "editor/css/preview_page":
                return self._build_css_preview_html(), 200, \
                       {'Content-Type': 'text/html; charset=utf-8'}
            if path == "active_theme":
                return jsonify({'theme': self._theme_name, 'fallback_notice': self._theme_fallback_notice, 'stealth_mode': self._theme_stealth_mode(self._theme_bundle)})
            if action == "display_status":
                return jsonify(self.display_status())
            if path == "preview_frame":
                return self._preview_frame_response()
            if path == "theme_list":
                themes = self._theme_list()
                logging.debug(f"[Refacer][themes] theme_list called -> {len(themes)} themes")
                return jsonify({'themes': themes})
            if path == "load_config":
                theme = request.args.get('theme') or self._theme_name
                logging.debug(f"[Refacer][themes] load_config called for theme={theme}")
                return jsonify(self._load_theme_editor_payload(theme))
            if path == "theme_download_list":
                try:
                    logging.debug("[Refacer][remote] theme_download_list called")
                    return jsonify({'themes': self._fetch_remote_themes()})
                except Exception as e:
                    logging.error(f"[Refacer][remote] Theme download list error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "debug/theme_inventory":
                return jsonify(self._debug_theme_inventory())
            if path == "debug/remote_status":
                return jsonify(self._debug_remote_status())
            if path == "debug/render_palette":
                return jsonify(self._debug_render_palette())
            if path == "debug/render_stats":
                return jsonify(dict(self._render_stats))
            if path == "debug/editor_snapshot":
                theme = request.args.get('theme') or self._theme_name
                return jsonify(self._build_editor_snapshot(theme))
            if path == "debug/editor_preview_frame":
                theme = request.args.get('theme') or self._theme_name
                return self._editor_preview_frame_response(theme)
            if path == "theme_asset":
                try:
                    theme = request.args.get('theme') or self._theme_name
                    asset_path = request.args.get('path') or ''
                    return self._theme_asset_response(theme, asset_path)
                except Exception as e:
                    logging.error(f"[Refacer][asset] theme asset error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path and path.startswith("theme_export/"):
                try:
                    theme_name = path.split("/", 1)[1]
                    zip_path = self._export_theme(theme_name)
                    fname = os.path.basename(zip_path)
                    try:
                        return send_file(
                            zip_path,
                            as_attachment=True,
                            download_name=fname,
                            mimetype='application/zip',
                        )
                    except TypeError:
                        return send_file(
                            zip_path,
                            as_attachment=True,
                            attachment_filename=fname,
                            mimetype='application/zip',
                        )
                except Exception as e:
                    logging.error(f"[Refacer] Theme export error: {e}")
                    return jsonify({'error': str(e)}), 500
        if request.method == "POST":
            if action == "display_status":
                return jsonify(self.display_status())
            if action == "display_on":
                return jsonify(self.display_on(reason='webui'))
            if action == "display_off":
                return jsonify(self.display_off(reason='webui'))
            if action == "display_toggle":
                return jsonify(self.display_toggle(reason='webui'))
            if action == "display_clear":
                return jsonify(self.display_clear(reason='webui'))
            if action == "display_timer":
                return jsonify(self.display_set_timer(self._display_timer_seconds_from_request(request)))
            if path == "theme_info":
                try:
                    data = request.get_json() or {}
                    return jsonify(self._theme_info(data.get('theme')))
                except Exception as e:
                    logging.error(f"[Refacer] Theme info error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "theme_select":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme', 'Default')
                    logging.debug(f"[Refacer][themes] theme_select called for theme={theme}")
                    self._set_active_theme(theme)
                    message = f"Theme '{self._theme_name}' applied."
                    if self._theme_fallback_notice:
                        message = f"{message} {self._theme_fallback_notice}"
                    return jsonify({'status': 'success', 'message': message, 'fallback_notice': self._theme_fallback_notice, 'stealth_mode': self._theme_stealth_mode(self._theme_bundle)})
                except Exception as e:
                    logging.error(f"[Refacer][themes] Theme select error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/reset_draft":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme') or self._theme_name
                    self._reset_editor_draft(theme)
                    return jsonify({'status': 'success', 'message': f"Draft reset for theme '{theme}'.", 'snapshot': self._build_editor_snapshot(theme)})
                except Exception as e:
                    logging.error(f"[Refacer][editor] reset draft error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/update_widget_draft":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme') or self._theme_name
                    widget_key = data.get('widget')
                    patch = data.get('patch') or {}
                    self._update_editor_widget_draft(widget_key, patch, theme_name=theme)
                    return jsonify({'status': 'success', 'message': f"Draft updated for widget '{widget_key}'.", 'snapshot': self._build_editor_snapshot(theme)})
                except Exception as e:
                    logging.error(f"[Refacer][editor] update widget draft error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/update_global_options":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme') or self._theme_name
                    self._update_editor_global_options_draft(data.get('options') or {}, data.get('dev') or {}, theme_name=theme)
                    return jsonify({'status': 'success', 'message': f"Global options draft updated for theme '{theme}'.", 'snapshot': self._build_editor_snapshot(theme)})
                except Exception as e:
                    logging.error(f"[Refacer][editor] update global options error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/apply_draft":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme') or self._editor_draft_theme_name or self._theme_name
                    snapshot = self._apply_editor_draft(theme)
                    return jsonify({'status': 'success',
                                    'message': f"Editor draft applied to theme '{theme}'.",
                                    'selected_widget_key': self._editor_selected_widget_key,
                                    'snapshot': snapshot})
                except Exception as e:
                    logging.error(f"[Refacer][editor] apply draft error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/test_boot_animation":
                try:
                    cache_ready = self._prepare_boot_animation_cache()
                    played = self._maybe_play_boot_animation('manual')
                    if not played:
                        return jsonify({
                            'status': 'noop',
                            'message': 'No boot animation configured for the active theme, '
                                       'or the source asset is missing. Check theme options.',
                            'cache_prepared': bool(cache_ready),
                            'played': False,
                        })
                    return jsonify({
                        'status': 'success',
                        'message': 'Boot animation cache warmed and playback triggered on device.',
                        'cache_prepared': bool(cache_ready),
                        'played': True,
                    })
                except Exception as e:
                    logging.error(f"[Refacer] Test boot animation error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/assets/upload":
                try:
                    theme = request.form.get('theme') or self._theme_name
                    group = request.form.get('group') or ''
                    uploaded = request.files.get('asset')
                    result = self._upload_theme_asset(theme, group, uploaded)
                    return jsonify({'status': 'success',
                                    'message': f"Uploaded {result['filename']} to {group}.",
                                    **result})
                except Exception as e:
                    logging.error(f"[Refacer] Asset upload error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/font_glyphs":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme') or self._theme_name
                    font_name = data.get('font_name') or ''
                    return jsonify(self._editor_font_glyphs_payload(theme, font_name=font_name))
                except Exception as e:
                    logging.error(f"[Refacer][font] glyph browser error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/assets/delete":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme') or self._theme_name
                    rel = data.get('path') or ''
                    result = self._delete_theme_asset(theme, rel)
                    return jsonify({'status': 'success',
                                    'message': f"Deleted {result['path']}.",
                                    **result})
                except Exception as e:
                    logging.error(f"[Refacer] Asset delete error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/css/load":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme') or self._theme_name
                    payload = self._load_css_editor_state(theme)
                    return jsonify({'status': 'success', **payload})
                except Exception as e:
                    logging.error(f"[Refacer][css] load error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/css/save":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme')
                    swatch = data.get('swatch') or None
                    raw_css = data.get('raw_css') or None
                    reinject = bool(data.get('reinject', True))
                    result = self._save_css_editor_state(
                        theme, swatch=swatch, raw_css=raw_css, reinject=reinject
                    )
                    return jsonify({'status': 'success', **result})
                except Exception as e:
                    logging.error(f"[Refacer][css] save error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/assets/delete_bulk":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme') or self._theme_name
                    paths = data.get('paths') or []
                    if not isinstance(paths, list):
                        return jsonify({'error': 'paths must be a list'}), 400
                    result = self._delete_theme_assets_bulk(theme, paths)
                    return jsonify({'status': 'success', **result})
                except Exception as e:
                    logging.error(f"[Refacer] Asset bulk-delete error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "editor/assets/download_bulk":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme') or self._theme_name
                    paths = data.get('paths') or []
                    if not isinstance(paths, list) or not paths:
                        return jsonify({'error': 'paths must be a non-empty list'}), 400
                    zip_path = self._zip_theme_assets_bulk(theme, paths)
                    zip_name = f"{theme}_assets.zip"
                    try:
                        return send_file(zip_path, as_attachment=True,
                                         download_name=zip_name,
                                         mimetype='application/zip')
                    except TypeError:
                        return send_file(zip_path, as_attachment=True,
                                         attachment_filename=zip_name,
                                         mimetype='application/zip')
                except Exception as e:
                    logging.error(f"[Refacer] Asset bulk-download error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "theme_new":
                try:
                    data = request.get_json() or {}
                    created = self._new_theme(data.get('new_name'))
                    return jsonify({'status': 'success',
                                    'message': f"Theme '{created}' created."})
                except Exception as e:
                    logging.error(f"[Refacer] Theme new error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "theme_copy":
                try:
                    data = request.get_json() or {}
                    created = self._copy_theme(data.get('theme'), data.get('new_name'))
                    return jsonify({'status': 'success', 'message': f"Theme '{data.get('theme')}' copied to '{created}'."})
                except Exception as e:
                    logging.error(f"[Refacer] Theme copy error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "theme_rename":
                try:
                    data = request.get_json() or {}
                    renamed = self._rename_theme(data.get('theme'), data.get('new_name'))
                    return jsonify({'status': 'success', 'message': f"Theme renamed to '{renamed}'."})
                except Exception as e:
                    logging.error(f"[Refacer] Theme rename error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "theme_delete":
                try:
                    data = request.get_json() or {}
                    deleted = self._delete_theme(data.get('theme'))
                    return jsonify({'status': 'success', 'message': f"Theme '{deleted}' deleted."})
                except Exception as e:
                    logging.error(f"[Refacer] Theme delete error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "theme_upload":
                try:
                    uploaded = request.files.get('zipFile')
                    installed = self._upload_theme_zip(uploaded)
                    return jsonify({'status': 'success', 'message': f"Theme zip installed: {', '.join(installed)}."})
                except Exception as e:
                    logging.error(f"[Refacer] Theme upload error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "save_config":
                try:
                    data = request.get_json() or {}
                    self._save_theme_editor_payload(data)
                    return jsonify({'status': 'success', 'message': 'Theme package and render settings saved.'})
                except Exception as e:
                    logging.error(f"[Refacer] Save config error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "version_compare":
                try:
                    data = request.get_json() or {}
                    return jsonify(self._compare_theme_version(data.get('theme'), data.get('version')))
                except Exception as e:
                    logging.error(f"[Refacer] Version compare error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "stealth_toggle":
                try:
                    data = request.get_json() or {}
                    enabled = bool(data.get('enabled', not self._theme_stealth_mode(self._theme_bundle)))
                    self._set_active_theme_stealth_mode(enabled)
                    return jsonify({'status': 'success', 'message': f"Stealth mode {'enabled' if enabled else 'disabled'}.", 'stealth_mode': enabled})
                except Exception as e:
                    logging.error(f"[Refacer] Stealth toggle error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "theme_download_select":
                try:
                    data = request.get_json() or {}
                    theme = data.get('theme')
                    self._download_theme(theme)
                    return jsonify({'status': 'success', 'message': f"Theme '{theme}' downloaded."})
                except Exception as e:
                    logging.error(f"[Refacer] Theme download error: {e}")
                    return jsonify({'error': str(e)}), 500
            if path == "debug/js_error":
                data = request.get_json() or {}
                logging.error(
                    "[Refacer][webui] js error: "
                    f"message={data.get('message')} source={data.get('source')} "
                    f"line={data.get('lineno')} col={data.get('colno')}"
                )
                return jsonify({'status': 'logged'})

        return "Not Found", 404

    def _ensure_theme_root(self):
        if not os.path.isdir(self._themes_root):
            os.makedirs(self._themes_root, exist_ok=True)
            self._invalidate_theme_inventory()

    def _candidate_theme_roots(self):
        roots = [self._themes_root]
        # Legacy themes often live in the shared Fancygotchi theme repos, not beside the plugin itself.
        siblings = (
            os.path.join(os.path.dirname(self._plug_root), 'Fancygotchi_themes', 'fancygotchi_2.0', 'themes'),
            os.path.join(os.path.dirname(self._plug_root), 'Fancygotchi_themes', 'fancygotchi_1.0', 'themes'),
        )
        for root in siblings:
            if root not in roots:
                roots.append(root)
        logging.debug(f"[Refacer] Plugin path resolved to {self._plug_root}")
        logging.debug(f"[Refacer] Candidate theme roots: {roots}")
        return roots

    def _current_rotation(self):
        try:
            return self._sanitize_rotation(self.options.get('rotation', 0), 0)
        except Exception as e:
            logging.debug(f"[Refacer] Rotation lookup fallback: {e}")
        return 0

    def _current_resolution(self):
        if self._view_instance:
            return f"{self._view_instance._width}x{self._view_instance._height}"
        try:
            if self._agent:
                config = self._agent.config()
                display_cfg = config.get('ui', {}).get('display', {})
                width = display_cfg.get('width')
                height = display_cfg.get('height')
                if width and height:
                    return f"{width}x{height}"
        except Exception as e:
            logging.debug(f"[Refacer] Resolution lookup fallback: {e}")
        return None

    def _theme_is_valid(self, theme_path):
        markers = {
            'info.json': os.path.exists(os.path.join(theme_path, 'info.json')),
            'info.md': os.path.exists(os.path.join(theme_path, 'info.md')),
            'style.css': os.path.exists(os.path.join(theme_path, 'style.css')),
            'config/': os.path.isdir(os.path.join(theme_path, 'config')),
            'config.toml': os.path.exists(os.path.join(theme_path, 'config.toml')),
        }
        valid = any(markers.values())
        logging.debug(f"[Refacer] Theme validation for {theme_path}: valid={valid}, markers={markers}")
        return valid

    def _theme_inventory(self):
        if isinstance(self._theme_cache, dict):
            return self._theme_cache
        inventory = {}
        for root in self._candidate_theme_roots():
            if not os.path.isdir(root):
                logging.debug(f"[Refacer] Theme root missing: {root}")
                continue
            found = []
            for item in sorted(os.listdir(root)):
                theme_path = os.path.join(root, item)
                if not os.path.isdir(theme_path):
                    logging.debug(f"[Refacer] Rejecting theme candidate {theme_path}: not a directory")
                    continue
                if not self._theme_is_valid(theme_path):
                    logging.debug(f"[Refacer] Rejecting theme candidate {theme_path}: no compatible theme markers")
                    continue
                found.append(item)
                inventory.setdefault(item, {'name': item, 'path': theme_path, 'root': root})
                logging.debug(f"[Refacer] Accepted theme candidate {theme_path}")
            logging.debug(f"[Refacer] Theme directories found in {root}: {found}")
        self._theme_cache = inventory
        return inventory

    def _debug_theme_inventory(self):
        inventory = self._theme_inventory()
        active_paths = self._resolve_theme_paths(self._theme_name) if self._theme_name else {'config': None, 'css': None, 'info': None}
        details = {}
        for name, meta in inventory.items():
            details[name] = {
                'path': meta['path'],
                'root': meta['root'],
                'markers': {
                    'info_json': os.path.exists(os.path.join(meta['path'], 'info.json')),
                    'info_md': os.path.exists(os.path.join(meta['path'], 'info.md')),
                    'style_css': os.path.exists(os.path.join(meta['path'], 'style.css')),
                    'config_dir': os.path.isdir(os.path.join(meta['path'], 'config')),
                    'config_toml': os.path.exists(os.path.join(meta['path'], 'config.toml')),
                },
            }
        return {
            'plugin_path': self._plug_root,
            'candidate_roots': self._candidate_theme_roots(),
            'active_theme': self._theme_name,
            'active_paths': active_paths,
            'local_theme_count': len(inventory),
            'inventory': details,
            'remote_count': getattr(self, '_last_remote_count', 0),
            'remote_error': self._last_remote_error,
        }

    def _debug_remote_status(self):
        return {
            'repo_url': THEMES_REPO,
            'github_token_set': bool(self.options.get('github_token')),
            'last_remote_status': self._last_remote_status,
            'last_remote_error': self._last_remote_error,
            'last_remote_count': getattr(self, '_last_remote_count', 0),
        }

    def _debug_render_palette(self):
        return dict(self._render_palette_debug)

    def _theme_meta(self, theme_name):
        return self._theme_inventory().get(theme_name)

    def _sanitize_int(self, value, default, minimum=0):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, value)

    def _sanitize_rotation(self, value, default=0):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return default
        return value if value in (0, 90, 180, 270) else default

    def _load_render_options(self):
        for key, default in self.DEFAULT_OPTIONS.items():
            self.options.setdefault(key, default)

        self.options['fps'] = self._sanitize_int(self.options.get('fps'), self.DEFAULT_OPTIONS['fps'], minimum=1)
        self.options['save_interval'] = self._sanitize_int(
            self.options.get('save_interval'),
            self.DEFAULT_OPTIONS['save_interval'],
            minimum=1,
        )
        legacy_1bit = bool(self.options.get('1bit'))
        display_output_mode = self._sanitize_display_output_mode(self.options.get('display_output_mode'), None)
        if display_output_mode is None:
            display_output_mode = '1bit' if legacy_1bit else self.DEFAULT_OPTIONS['display_output_mode']
        self.options['display_output_mode'] = display_output_mode
        self.options['1bit'] = display_output_mode == '1bit'
        self.options['save_images'] = bool(self.options.get('save_images'))
        self.options['experimental_non_native_selects'] = bool(self.options.get('experimental_non_native_selects', False))
        self.options['theme'] = self.options.get('theme') or 'Default'
        self.options['github_token'] = self.options.get('github_token') or ''
        self.options['default_stealth_mode'] = bool(self.options.get('default_stealth_mode', False))
        self.options['rotation'] = self._sanitize_rotation(self.options.get('rotation', 0), 0)
        self.options['display_control_enabled'] = bool(
            self.options.get('display_control_enabled', self.DEFAULT_OPTIONS['display_control_enabled'])
        )
        self.options['display_auto_off_seconds'] = self._sanitize_int(
            self.options.get('display_auto_off_seconds'),
            self.DEFAULT_OPTIONS['display_auto_off_seconds'],
            minimum=0,
        )
        self.options['display_blank_color'] = self.options.get('display_blank_color') or self.DEFAULT_OPTIONS['display_blank_color']
        backend = str(self.options.get('display_sleep_backend', self.DEFAULT_OPTIONS['display_sleep_backend']) or 'auto').strip().lower()
        self.options['display_sleep_backend'] = backend if backend in ('blank', 'windows', 'auto') else 'auto'
        self.options['display_sleep_windows_restore'] = bool(
            self.options.get('display_sleep_windows_restore', self.DEFAULT_OPTIONS['display_sleep_windows_restore'])
        )
        self.options['display_sleep_windows_restore_previous'] = bool(
            self.options.get('display_sleep_windows_restore_previous', self.DEFAULT_OPTIONS['display_sleep_windows_restore_previous'])
        )
        mode = str(self.options.get('display_sleep_windows_mode', self.DEFAULT_OPTIONS['display_sleep_windows_mode']) or 'screen_saver').strip()
        self.options['display_sleep_windows_mode'] = mode or 'screen_saver'
        self.options['display_sleep_windows_sub_mode'] = str(self.options.get('display_sleep_windows_sub_mode') or '').strip()
        with self._display_control_lock:
            self._display_auto_off_seconds = int(self.options['display_auto_off_seconds'])
            self._reset_display_auto_off_deadline_locked()
            self._sync_display_control_stats()
        self.fps = self.options['fps']

    def _invalidate_theme_inventory(self):
        self._theme_cache = None

    def _detach_refacer_view_state(self):
        view_instance = self._view_instance
        if view_instance is None:
            return
        stock_canvas = getattr(view_instance, '_canvas', None)
        if stock_canvas is not None:
            view_instance._refacer_web_canvas = stock_canvas.copy()
            try:
                import pwnagotchi.ui.web as web
                web.update_frame(stock_canvas)
            except Exception as exc:
                logging.warning(f"[Refacer][web] failed restoring OG web frame: {exc}")
            logging.debug("[Refacer][lifecycle] restored OG render ownership")
        for attr in ('_refacer_hidden_cbs',):
            if hasattr(view_instance, attr):
                try:
                    delattr(view_instance, attr)
                except Exception:
                    setattr(view_instance, attr, None)
        view_instance._refacer_block_web = False
        if hasattr(view_instance, '_refacer_web_canvas') and stock_canvas is None:
            try:
                delattr(view_instance, '_refacer_web_canvas')
            except Exception:
                view_instance._refacer_web_canvas = None
        if hasattr(view_instance, '_render_cbs') and getattr(view_instance, '_render_cbs', None) is None:
            view_instance._render_cbs = []
        self._view_instance = None

    def _reset_runtime_render_state(self, clear_theme=False):
        self._last_render_canvas = None
        self._last_stock_canvas = None
        self._render_palette_debug = {}
        self._asset_cache = {}
        self._theme_assets = {'background': None, 'foreground': None, 'animated_background': []}
        self._anim_frame_index = 0
        self._theme_fallback_notice = None
        if clear_theme:
            self._theme_bundle = {}
            self._theme_model = copy.deepcopy(self.DEFAULT_THEME_MODEL)
            self._theme_runtime = {
                'theme_name': 'Default',
                'theme_path': None,
                'theme_bundle': copy.deepcopy(self.DEFAULT_THEME_MODEL),
                'assets': {'background': None, 'foreground': None, 'animated_background': []},
                'asset_cache': {},
                'font_cache': {},
                'anim_frame_index': 0,
                'runtime_version': 0,
                'font_name': 'DejaVuSansMono',
                'font_bold_name': 'DejaVuSansMono-Bold',
                'font_status_name': 'DejaVuSansMono',
                'f_awesome_name': '',
                'Small': None,
                'Medium': None,
                'BoldSmall': None,
                'Bold': None,
                'BoldBig': None,
                'Huge': None,
            }
        logging.debug("[Refacer][themes] cache invalidated on switch")

    def _theme_snapshot_id(self):
        return f"{self._theme_name}:{self._theme_runtime_version}"

    def _build_theme_runtime(self, theme_name, theme_path, theme_bundle):
        runtime = {
            'theme_name': theme_name,
            'theme_path': theme_path,
            'theme_bundle': theme_bundle,
            'assets': {'background': None, 'foreground': None, 'animated_background': []},
            'asset_cache': {},
            'font_cache': {},
            'anim_frame_index': 0,
            'runtime_version': 0,
            'font_name': 'DejaVuSansMono',
            'font_bold_name': 'DejaVuSansMono-Bold',
            'font_status_name': 'DejaVuSansMono',
            'f_awesome_name': '',
            'Small': None,
            'Medium': None,
            'BoldSmall': None,
            'Bold': None,
            'BoldBig': None,
            'Huge': None,
        }
        runtime['assets'] = self._load_theme_assets(runtime)
        return runtime

    def _plugin_config(self):
        config_path = '/etc/pwnagotchi/config.toml'
        # Always start from the on-disk config to preserve all other keys
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = toml.load(f)
        except Exception:
            config = {}

        # Merge in any live agent config keys that may be newer in memory
        if self._agent:
            try:
                live = self._agent.config()
                if isinstance(live, dict):
                    # Deep-merge live into on-disk config, live takes precedence
                    def deep_merge(base, override):
                        for k, v in override.items():
                            if isinstance(v, dict) and isinstance(base.get(k), dict):
                                deep_merge(base[k], v)
                            else:
                                base[k] = v
                    deep_merge(config, live)
            except Exception as exc:
                logging.warning(f"[Refacer][config] could not merge live agent config: {exc}")

        config.setdefault('main', {}).setdefault('plugins', {})
        config['main']['plugins'].setdefault('refacer', {})
        return config

    def _persist_plugin_options(self):
        config = self._plugin_config()
        plugin_cfg = config['main']['plugins']['refacer']
        for key in self.DEFAULT_OPTIONS:
            plugin_cfg[key] = self.options.get(key, self.DEFAULT_OPTIONS[key])
        save_config(config, '/etc/pwnagotchi/config.toml')

    def _set_display_rotation(self, rotation):
        rotation = self._sanitize_rotation(rotation, self._current_rotation())
        self.options['rotation'] = rotation

        config = self._plugin_config()
        config.setdefault('ui', {}).setdefault('display', {})
        if config['ui']['display'].get('rotation', 0) != 0:
            config['ui']['display']['rotation'] = 0
        plugin_cfg = config.setdefault('main', {}).setdefault('plugins', {}).setdefault('refacer', {})
        plugin_cfg['rotation'] = rotation

        try:
            pwnagotchi.config.setdefault('ui', {}).setdefault('display', {})
            if pwnagotchi.config['ui']['display'].get('rotation', 0) != 0:
                pwnagotchi.config['ui']['display']['rotation'] = 0
            pwnagotchi.config.setdefault('main', {}).setdefault('plugins', {}).setdefault('refacer', {})['rotation'] = rotation
        except Exception:
            pass

        if self._agent:
            try:
                agent_config = self._agent.config()
                agent_config.setdefault('ui', {}).setdefault('display', {})
                if agent_config['ui']['display'].get('rotation', 0) != 0:
                    agent_config['ui']['display']['rotation'] = 0
                agent_config.setdefault('main', {}).setdefault('plugins', {}).setdefault('refacer', {})['rotation'] = rotation
                if hasattr(self._agent, '_config') and isinstance(self._agent._config, dict):
                    self._agent._config.setdefault('ui', {}).setdefault('display', {})
                    if self._agent._config['ui']['display'].get('rotation', 0) != 0:
                        self._agent._config['ui']['display']['rotation'] = 0
                    self._agent._config.setdefault('main', {}).setdefault('plugins', {}).setdefault('refacer', {})['rotation'] = rotation
            except Exception as exc:
                logging.warning(f"[Refacer][config] failed updating live agent rotation: {exc}")

        save_config(config, '/etc/pwnagotchi/config.toml')
        logging.info(f"[Refacer][config] plugin rotation set to {rotation}")
        self._prepare_boot_animation_cache()
        return rotation

    def _theme_list(self):
        self._ensure_theme_root()
        themes = ['Default']
        themes.extend(self._theme_inventory().keys())
        theme_names = sorted(set(themes), key=lambda value: value.lower())
        logging.info(f"[Refacer] Discovered theme names: {theme_names}")
        return theme_names

    def _theme_path_for(self, theme_name):
        if not theme_name or theme_name == 'Default':
            return None
        meta = self._theme_meta(theme_name)
        return meta['path'] if meta else os.path.join(self._themes_root, theme_name)

    def _theme_config_path(self, theme_name):
        return self._resolve_theme_paths(theme_name)['config']

    def _theme_orientation(self):
        return 'v' if self._current_rotation() in (90, 270) else 'h'

    def _physical_canvas_size(self):
        if self._view_instance is not None:
            return int(self._view_instance._width), int(self._view_instance._height)
        resolution = self._current_resolution()
        if resolution and 'x' in resolution:
            try:
                width, height = resolution.split('x', 1)
                return int(width), int(height)
            except (TypeError, ValueError):
                pass
        return 320, 240

    # Compose in logical orientation space first.
    # 0/180 => X,Y
    # 90/270 => Y,X
    # The final hardware sink rotates the composed frame back to the physical panel.
    def _canvas_size(self):
        width, height = self._physical_canvas_size()
        if self._current_rotation() in (90, 270):
            return int(height), int(width)
        return int(width), int(height)

    def _deep_merge(self, base, update):
        merged = copy.deepcopy(base)
        for key, value in (update or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    def _resolve_theme_paths(self, theme_name):
        theme_path = self._theme_path_for(theme_name)
        if not theme_path:
            return {'root': None, 'config': None, 'css': None, 'info': None}

        resolution = self._current_resolution()
        rotation = self._current_rotation()
        orientation = self._theme_orientation()
        orientation_file = f'config-{orientation}.toml'
        generic_file = 'config.toml'
        config_path = None
        config_dir = os.path.join(theme_path, 'config')

        def _pick_toml(folder):
            """Return best matching toml path from folder, or None."""
            try:
                files = [f for f in os.listdir(folder) if f.endswith('.toml') and os.path.isfile(os.path.join(folder, f))]
            except OSError:
                return None
            if orientation_file in files:
                return os.path.join(folder, orientation_file)
            if generic_file in files:
                return os.path.join(folder, generic_file)
            # Single toml at this level → use it for both orientations (Fancygotchi compat)
            if len(files) == 1:
                return os.path.join(folder, files[0])
            return None

        if os.path.isdir(config_dir):
            # 1. config/ root files take priority over any resolution subfolder
            config_path = _pick_toml(config_dir)

            # 2. Resolution subfolder is the fallback for the right display size
            if config_path is None:
                if resolution:
                    res_dir = os.path.join(config_dir, resolution)
                    if os.path.isdir(res_dir):
                        config_path = _pick_toml(res_dir)

                # 3. Scan for any WxH subdir when resolution is unknown or unmatched
                if config_path is None:
                    try:
                        for sub in sorted(os.listdir(config_dir)):
                            sub_dir = os.path.join(config_dir, sub)
                            if re.match(r'^\d+x\d+$', sub) and os.path.isdir(sub_dir):
                                config_path = _pick_toml(sub_dir)
                                if config_path:
                                    break
                    except OSError:
                        pass

        # 4. Root theme-level files as last resort (no config/ subfolder)
        if config_path is None:
            for candidate in [
                os.path.join(theme_path, orientation_file),
                os.path.join(theme_path, generic_file),
            ]:
                if os.path.exists(candidate):
                    config_path = candidate
                    break

        if config_path is None:
            config_path = os.path.join(theme_path, generic_file)

        css_path = os.path.join(theme_path, 'style.css')
        info_candidates = [
            os.path.join(theme_path, 'info.json'),
            os.path.join(theme_path, 'info.md'),
        ]
        info_path = next((c for c in info_candidates if os.path.exists(c)), info_candidates[0])
        logging.debug(
            f"[Refacer][themes] resolved config priority theme={theme_name} "
            f"rotation={rotation} orientation={orientation} resolution={resolution} "
            f"chosen={config_path}"
        )
        return {
            'root': theme_path,
            'config': config_path,
            'css': css_path,
            'info': info_path,
        }

    def _theme_bundle_from_config(self, theme_config):
        theme_body = theme_config.get('theme', {}) if isinstance(theme_config, dict) else {}
        widgets = theme_body.get('widget')
        if widgets is None:
            widgets = theme_config.get('widgets')
        if widgets is None:
            widgets = theme_config.get('widget', {})
        merged = self._deep_merge(self.DEFAULT_THEME_MODEL, theme_config or {})
        merged.setdefault('theme', {})
        merged['theme']['widget'] = widgets if isinstance(widgets, dict) else {}
        return merged

    def _read_theme_config(self, theme_name):
        if not theme_name or theme_name == 'Default':
            return {'theme': {'options': {'stealth_mode': bool(self.options.get('default_stealth_mode', False))}}}
        cfg_path = self._theme_config_path(theme_name)
        if not cfg_path or not os.path.exists(cfg_path):
            logging.debug(f"[Refacer] No theme config found for {theme_name} at {cfg_path}")
            return {}
        logging.debug(f"[Refacer] Loading theme config for {theme_name} from {cfg_path}")
        with open(cfg_path, 'r', encoding='utf-8') as handle:
            return toml.load(handle)

    def _write_text_file(self, path, content):
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(content)

    def _read_text_file(self, path):
        if not path or not os.path.exists(path):
            return ''
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()

    def _plain_metadata_value(self, value):
        if value is None:
            return ''
        text = str(value)
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()

    def _sanitize_metadata_html(self, value, field='notes', theme_name='Default'):
        if value is None:
            return ''
        sanitizer = _ThemeMetadataHTMLSanitizer()
        sanitizer.feed(str(value))
        sanitizer.close()
        cleaned = sanitizer.get_html().strip()
        logging.debug(f"[Refacer][webui] sanitized theme metadata html field={field} theme={theme_name}")
        return cleaned

    def _find_theme_screenshot_path(self, theme_name):
        theme_path = self._theme_path_for(theme_name)
        if not theme_path or not os.path.isdir(theme_path):
            logging.debug(f"[Refacer][webui] theme screenshot missing theme={theme_name}")
            return None
        candidates = [
            os.path.join(theme_path, 'img', 'screenshot.png'),
            os.path.join(theme_path, 'img', 'screenshot.jpg'),
            os.path.join(theme_path, 'img', 'screenshot.jpeg'),
            os.path.join(theme_path, 'img', 'screenshot.webp'),
            os.path.join(theme_path, 'screenshot.png'),
            os.path.join(theme_path, 'screenshots', 'screenshot.png'),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                logging.debug(f"[Refacer][webui] theme screenshot found theme={theme_name} path={candidate}")
                return candidate
        logging.debug(f"[Refacer][webui] theme screenshot missing theme={theme_name}")
        return None

    def _relative_theme_screenshot_path(self, theme_name):
        screenshot_path = self._find_theme_screenshot_path(theme_name)
        if not screenshot_path:
            return None
        theme_root = self._theme_path_for(theme_name)
        try:
            return os.path.relpath(screenshot_path, theme_root).replace('\\', '/')
        except Exception:
            return None

    def _repo_theme_mirror_path(self, theme_name):
        return os.path.join(self._repo_screenshots_path, theme_name)

    def _repo_theme_screenshot_url(self, theme_name):
        return f"/img/{quote(str(theme_name or ''))}/screenshot.png"

    # Resolve only expected theme asset paths and reject traversal outside the theme root.
    def _resolve_theme_asset_path(self, theme_name, relative_path):
        theme_root = self._theme_path_for(theme_name)
        if not theme_root or not os.path.isdir(theme_root):
            return None
        normalized = (relative_path or '').replace('\\', '/').lstrip('/')
        normalized = os.path.normpath(normalized).replace('\\', '/')
        if normalized in ('', '.'):
            return None
        if normalized.startswith('../') or normalized == '..' or os.path.isabs(normalized):
            logging.warning(f"[Refacer][asset] rejected traversal theme={theme_name} path={relative_path}")
            return None
        allowed = (
            normalized.startswith('img/') or
            normalized.startswith('icons/') or
            normalized.startswith('fonts/') or
            normalized.startswith('screenshots/') or
            normalized == 'screenshot.png'
        )
        if not allowed:
            logging.warning(f"[Refacer][asset] rejected path theme={theme_name} path={relative_path}")
            return None
        theme_root_real = os.path.realpath(theme_root)
        fs_path = os.path.realpath(os.path.join(theme_root_real, normalized))
        if fs_path != theme_root_real and not fs_path.startswith(theme_root_real + os.sep):
            logging.warning(f"[Refacer][asset] rejected traversal theme={theme_name} path={relative_path}")
            return None
        return fs_path if os.path.isfile(fs_path) else None

    def _theme_asset_response(self, theme_name, relative_path):
        fs_path = self._resolve_theme_asset_path(theme_name, relative_path)
        if not fs_path:
            logging.debug(f"[Refacer][asset] missing theme={theme_name} path={relative_path}")
            return jsonify({'error': 'not found'}), 404
        logging.debug(f"[Refacer][asset] serving theme={theme_name} path={relative_path} fs={fs_path}")
        return send_file(fs_path, mimetype=mimetypes.guess_type(fs_path)[0])

    def _theme_asset_inventory(self, theme_name):
        screenshot = self._relative_theme_screenshot_path(theme_name)
        inventory = {'screenshot': screenshot}
        for group in self._ASSET_GROUP_DIRS:
            inventory[group] = []
        theme_root = self._theme_path_for(theme_name)
        if not theme_root or not os.path.isdir(theme_root):
            return inventory
        for key, rel_dir in self._ASSET_GROUP_DIRS.items():
            folder = os.path.join(theme_root, rel_dir)
            if os.path.isdir(folder):
                inventory[key] = sorted(
                    os.path.relpath(os.path.join(folder, name), theme_root).replace('\\', '/')
                    for name in os.listdir(folder)
                    if os.path.isfile(os.path.join(folder, name))
                )
        return inventory

    def _sanitize_asset_filename(self, filename, group=None):
        if not filename:
            raise ValueError('Filename is required.')
        base = os.path.basename(str(filename).replace('\\', '/'))
        base = base.strip().lstrip('.')
        if not base or base in ('.', '..'):
            raise ValueError('Filename is invalid.')
        stem, ext = os.path.splitext(base)
        ext = ext.lower()
        allowed_exts = self.THEME_ALLOWED_FONT_EXTS if group == 'fonts' else self.BOOT_ALLOWED_IMAGE_EXTS
        if ext not in allowed_exts:
            raise ValueError(
                f"Unsupported extension '{ext}'. Allowed: "
                + ', '.join(allowed_exts)
            )
        safe_stem = re.sub(r'[^A-Za-z0-9._-]', '_', stem)
        if not safe_stem:
            raise ValueError('Filename has no valid characters.')
        return safe_stem + ext

    def _resolve_editor_font_file(self, theme_name, font_name=''):
        requested_theme = theme_name or self._theme_name or 'Default'
        draft_bundle = self._editor_runtime_theme_bundle(requested_theme)
        theme_options = self._theme_options(draft_bundle)
        chosen = str(font_name or theme_options.get('font_awesome') or '').strip()
        if not chosen:
            raise ValueError('No Font Awesome font configured.')
        theme_root = self._theme_path_for(requested_theme)
        inventory = self._theme_asset_inventory(requested_theme).get('fonts', [])
        for rel in inventory:
            if chosen == rel or chosen == os.path.basename(rel):
                fs_path = self._resolve_theme_asset_path(requested_theme, rel)
                if fs_path:
                    return fs_path, rel, chosen
        if chosen.replace('\\', '/').startswith('fonts/'):
            rel = chosen.replace('\\', '/')
            fs_path = self._resolve_theme_asset_path(requested_theme, rel)
            if fs_path:
                return fs_path, rel, chosen
        runtime = {'theme_path': theme_root}
        fs_path = self._font_name_to_path(chosen, theme_runtime=runtime)
        if fs_path and os.path.isfile(fs_path):
            rel = ''
            if theme_root:
                theme_root_real = os.path.realpath(theme_root)
                fs_real = os.path.realpath(fs_path)
                if fs_real.startswith(theme_root_real + os.sep):
                    rel = os.path.relpath(fs_real, theme_root_real).replace('\\', '/')
            return fs_path, rel, chosen
        raise ValueError(f"Font file not found for '{chosen}'.")

    def _font_glyph_scan_signature(self, font, glyph):
        try:
            mask = font.getmask(glyph)
            return (getattr(mask, 'size', None), getattr(mask, 'getbbox', lambda: None)())
        except Exception:
            return None

    def _enumerate_font_glyphs(self, font_path):
        entries = []
        seen = set()
        if TTFont is not None:
            try:
                with TTFont(font_path, lazy=True) as font_file:
                    cmap = font_file.getBestCmap() or {}
                    for codepoint in sorted(cmap.keys()):
                        if codepoint in seen:
                            continue
                        try:
                            glyph = chr(int(codepoint))
                        except Exception:
                            continue
                        if glyph.isspace() or unicodedata.category(glyph).startswith('C'):
                            continue
                        entries.append({
                            'codepoint': int(codepoint),
                            'hex': format(int(codepoint), 'x'),
                            'char': glyph,
                        })
                        seen.add(codepoint)
                return entries
            except Exception as exc:
                logging.warning(f"[Refacer][font] fontTools glyph enumeration failed path={font_path} error={exc}")
        try:
            font = ImageFont.truetype(font_path, 24)
            missing = self._font_glyph_scan_signature(font, '\uffff')
            for start, end in ((0x20, 0x7E), (0xA0, 0x024F), (0xE000, 0xF8FF)):
                for codepoint in range(start, end + 1):
                    if codepoint in seen:
                        continue
                    glyph = chr(codepoint)
                    if glyph.isspace() or unicodedata.category(glyph).startswith('C'):
                        continue
                    sig = self._font_glyph_scan_signature(font, glyph)
                    if sig is None or sig == missing:
                        continue
                    entries.append({
                        'codepoint': int(codepoint),
                        'hex': format(int(codepoint), 'x'),
                        'char': glyph,
                    })
                    seen.add(codepoint)
        except Exception as exc:
            logging.warning(f"[Refacer][font] fallback glyph scan failed path={font_path} error={exc}")
        return entries

    def _editor_font_glyphs_payload(self, theme_name, font_name=''):
        font_path, rel_path, chosen_name = self._resolve_editor_font_file(theme_name, font_name)
        glyphs = self._enumerate_font_glyphs(font_path)
        logging.info(
            f"[Refacer][font] glyph browser theme={theme_name} font={chosen_name} "
            f"path={font_path} count={len(glyphs)}"
        )
        return {
            'theme': theme_name,
            'font_name': chosen_name,
            'font_asset_path': rel_path,
            'glyphs': glyphs,
            'count': len(glyphs),
            'source': 'codepoints',
        }

    def _upload_theme_asset(self, theme_name, group, uploaded_file):
        if not theme_name or theme_name == 'Default':
            raise ValueError('Default theme is read-only; copy it first.')
        if group not in self._ASSET_GROUP_DIRS:
            raise ValueError(f"Unknown asset group '{group}'.")
        if uploaded_file is None or not getattr(uploaded_file, 'filename', ''):
            raise ValueError('No file uploaded.')
        theme_root = self._theme_path_for(theme_name)
        if not theme_root or not os.path.isdir(theme_root):
            raise ValueError(f"Theme '{theme_name}' not found.")
        filename = self._sanitize_asset_filename(uploaded_file.filename, group=group)
        group_rel = self._ASSET_GROUP_DIRS[group]
        group_dir = os.path.join(theme_root, group_rel)
        os.makedirs(group_dir, exist_ok=True)
        dest_path = os.path.join(group_dir, filename)
        if os.path.exists(dest_path):
            raise ValueError(
                f"Asset '{filename}' already exists in '{group}'. "
                f"Delete it first to replace."
            )
        theme_root_real = os.path.realpath(theme_root)
        dest_real = os.path.realpath(dest_path)
        if not dest_real.startswith(theme_root_real + os.sep):
            raise ValueError('Refusing to write outside theme directory.')
        uploaded_file.save(dest_path)
        self._mirror_theme_img_tree(theme_name)
        logging.info(
            f"[Refacer][asset] uploaded theme={theme_name} group={group} file={filename}"
        )
        relative = (group_rel + '/' + filename).replace('\\', '/')
        return {'group': group, 'path': relative, 'filename': filename}

    def _delete_theme_asset(self, theme_name, relative_path):
        if not theme_name or theme_name == 'Default':
            raise ValueError('Default theme is read-only; copy it first.')
        fs_path = self._resolve_theme_asset_path(theme_name, relative_path)
        if not fs_path:
            raise ValueError(
                f"Asset not found or path not allowed: {relative_path}"
            )
        theme_root_real = os.path.realpath(self._theme_path_for(theme_name))
        group_roots = tuple(
            os.path.realpath(os.path.join(theme_root_real, rel)) + os.sep
            for rel in self._ASSET_GROUP_DIRS.values()
        )
        if not any(fs_path.startswith(gr) for gr in group_roots):
            raise ValueError(
                'This endpoint only deletes managed theme asset-group files.'
            )
        os.remove(fs_path)
        self._mirror_theme_img_tree(theme_name)
        logging.info(
            f"[Refacer][asset] deleted theme={theme_name} path={relative_path}"
        )
        return {'path': relative_path}

    def _delete_theme_assets_bulk(self, theme_name, relative_paths):
        if not theme_name or theme_name == 'Default':
            raise ValueError('Default theme is read-only; copy it first.')
        deleted = []
        failed = []
        for rel in relative_paths:
            try:
                self._delete_theme_asset(theme_name, rel)
                deleted.append(rel)
            except Exception as e:
                failed.append({'path': rel, 'error': str(e)})
        return {'deleted': deleted, 'failed': failed}

    def _zip_theme_assets_bulk(self, theme_name, relative_paths):
        import tempfile, zipfile as _zipfile
        if not theme_name:
            raise ValueError('No theme specified.')
        resolved = []
        for rel in relative_paths:
            fs_path = self._resolve_theme_asset_path(theme_name, rel)
            if not fs_path:
                raise ValueError(f"Asset not found or path not allowed: {rel}")
            resolved.append((rel, fs_path))
        tmp = tempfile.mkdtemp()
        zip_path = os.path.join(tmp, f"{theme_name}_assets.zip")
        with _zipfile.ZipFile(zip_path, 'w', _zipfile.ZIP_DEFLATED) as zf:
            for rel, fs_path in resolved:
                arcname = os.path.join('img', *rel.lstrip('/').split('/')[1:])
                zf.write(fs_path, arcname)
        return zip_path

    def _read_repo_screenshots_index(self):
        if not os.path.exists(self._repo_screenshots_index_path):
            return []
        try:
            with open(self._repo_screenshots_index_path, 'r', encoding='utf-8') as handle:
                payload = json.load(handle)
            names = payload.get('themes', [])
            return names if isinstance(names, list) else []
        except Exception:
            return []

    def _write_repo_screenshots_index(self, theme_names):
        os.makedirs(self._repo_screenshots_path, exist_ok=True)
        with open(self._repo_screenshots_index_path, 'w', encoding='utf-8') as handle:
            json.dump({'themes': sorted(set(theme_names))}, handle)

    def _remove_repo_theme_mirror(self, theme_name):
        mirror_path = self._repo_theme_mirror_path(theme_name)
        if os.path.lexists(mirror_path):
            if os.path.isdir(mirror_path) and not os.path.islink(mirror_path):
                shutil.rmtree(mirror_path, ignore_errors=True)
            else:
                try:
                    os.unlink(mirror_path)
                except OSError:
                    os.remove(mirror_path)
            logging.debug(f"[Refacer][webui] removed stale mirrored theme={theme_name}")

    # Mirror the whole theme img tree into repo_screenshots/<theme>/ so every image becomes web-visible.
    def _mirror_theme_img_tree(self, theme_name):
        theme_path = self._theme_path_for(theme_name)
        if not theme_path or not os.path.isdir(theme_path):
            return False
        src_img_path = os.path.join(theme_path, 'img')
        if not os.path.isdir(src_img_path):
            self._remove_repo_theme_mirror(theme_name)
            return False
        dst_path = self._repo_theme_mirror_path(theme_name)
        self._remove_repo_theme_mirror(theme_name)
        os.makedirs(self._repo_screenshots_path, exist_ok=True)
        try:
            os.symlink(src_img_path, dst_path, target_is_directory=True)
        except Exception:
            shutil.copytree(src_img_path, dst_path)
        logging.debug(f"[Refacer][webui] mirrored theme img tree theme={theme_name} src={src_img_path} dst={dst_path}")
        screenshot_path = os.path.join(dst_path, 'screenshot.png')
        if os.path.exists(screenshot_path):
            logging.debug(f"[Refacer][webui] mirrored screenshot theme={theme_name} path={screenshot_path}")
        return True

    def _rebuild_repo_screenshots_tree(self):
        os.makedirs(self._repo_screenshots_path, exist_ok=True)
        current_themes = []
        for theme_name in self._theme_list():
            if self._mirror_theme_img_tree(theme_name):
                current_themes.append(theme_name)
        previous_themes = set(self._read_repo_screenshots_index())
        for stale_theme in sorted(previous_themes - set(current_themes)):
            self._remove_repo_theme_mirror(stale_theme)
        self._write_repo_screenshots_index(current_themes)

    def _cleanup_repo_screenshots_tree(self):
        for theme_name in self._read_repo_screenshots_index():
            mirror_path = self._repo_theme_mirror_path(theme_name)
            if os.path.lexists(mirror_path):
                if os.path.isdir(mirror_path) and not os.path.islink(mirror_path):
                    shutil.rmtree(mirror_path, ignore_errors=True)
                else:
                    try:
                        os.unlink(mirror_path)
                    except OSError:
                        os.remove(mirror_path)
                logging.debug(f"[Refacer][webui] unload cleanup removed mirrored theme={theme_name}")
        if os.path.exists(self._repo_screenshots_index_path):
            try:
                os.remove(self._repo_screenshots_index_path)
                logging.debug("[Refacer][webui] unload cleanup removed mirror index")
            except OSError:
                pass
        logging.debug("[Refacer][webui] unload cleanup complete")

    # ------------------------------------------------------------------ CSS injection

    def _build_css_preview_html(self):
        # Real pwnagotchi URL scheme: jQuery at /js/, jQM at /js/jquery.mobile/, style at /css/
        jq_js = "jquery-1.12.4.min.js"
        jqm_js = "jquery.mobile-1.4.5.min.js"
        jqm_css = "jquery.mobile-1.4.5.min.css"
        try:
            import pwnagotchi as _pwny
            pkg_dir = os.path.dirname(os.path.realpath(_pwny.__file__))
            static_base = os.path.join(pkg_dir, 'ui', 'web', 'static')
            js_dir = os.path.join(static_base, 'js')
            jqm_dir = os.path.join(js_dir, 'jquery.mobile')
            if os.path.isdir(js_dir):
                files = os.listdir(js_dir)
                for pat in ['jquery-*.min.js', 'jquery.min.js', 'jquery.js']:
                    hit = next((f for f in sorted(files) if fnmatch.fnmatch(f, pat)), None)
                    if hit:
                        jq_js = hit
                        break
            if os.path.isdir(jqm_dir):
                files = os.listdir(jqm_dir)
                for pat in ['jquery.mobile-*.min.js', 'jquery.mobile.min.js', 'jquery.mobile*.js']:
                    hit = next((f for f in sorted(files) if fnmatch.fnmatch(f, pat)), None)
                    if hit:
                        jqm_js = hit
                        break
                for pat in ['jquery.mobile-*.min.css', 'jquery.mobile.min.css', 'jquery.mobile*.css']:
                    hit = next((f for f in sorted(files) if fnmatch.fnmatch(f, pat)), None)
                    if hit:
                        jqm_css = hit
                        break
            logging.debug(
                f"[Refacer][css-preview] resolved assets: jq={jq_js} jqm_js={jqm_js} jqm_css={jqm_css}"
            )
        except Exception as e:
            logging.warning(f"[Refacer][css-preview] asset resolve failed: {e}")
        return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CSS Preview</title>
<link rel="stylesheet" href="/js/jquery.mobile/{jqm_css}">
<link rel="stylesheet" href="/css/style.css">
<style id="candidate-style"></style>
<style id="base-extras-style">
  table {{ border-collapse:collapse; width:100%; margin-top:4px; }}
  thead {{ background-color:#0070c0; color:#fff; }}
  tbody tr:hover {{ background-color:#d0e8ff; }}
  td, th {{ padding:4px 8px; border:1px solid #ccc; }}
  #prev-filter {{ width:100%; padding:6px 10px; box-sizing:border-box; margin-bottom:6px; }}
  .tooltip {{ position:relative; display:inline-block; }}
  .tooltip .tooltiptext {{
    visibility:hidden; width:200px; background-color:#3388cc; color:#fff;
    text-align:center; border-radius:10px; border:2px solid black; padding:20px 0;
    position:absolute; z-index:1; top:100%; left:50%; margin-left:-100px;
  }}
  .tooltip:hover .tooltiptext {{ visibility:visible; }}
</style>
</head>
<body>
<div data-role="page">

  <div data-role="footer">
    <div data-role="navbar" data-iconpos="left">
      <ul>
        <li class="navitem"><a href="#" data-icon="eye" class="ui-btn-active">Home</a></li>
        <li class="navitem"><a href="#" data-icon="bars">Inbox</a></li>
        <li class="navitem"><a href="#" data-icon="mail">New</a></li>
        <li class="navitem"><a href="#" data-icon="info">Profile</a></li>
        <li class="navitem"><a href="#" data-icon="user">Peers</a></li>
        <li class="navitem"><a href="#" data-icon="grid">Plugins</a></li>
      </ul>
    </div>
  </div>

  <div class="ui-content">

    <p>Body text and <a href="javascript:void(0)">a link</a>. <a href="javascript:void(0)" class="read">Visited link</a>.</p>

    <a href="javascript:void(0)" class="ui-btn ui-corner-all">Button (up)</a>
    <a href="javascript:void(0)" class="ui-btn ui-corner-all ui-btn-active">Button (active)</a>

    <div data-role="fieldcontain">
      <label for="prev-txt">Text input:</label>
      <input id="prev-txt" type="text" value="Sample text">
    </div>

    <div data-role="fieldcontain">
      <label for="prev-sel">Dropdown:</label>
      <select id="prev-sel">
        <option>Option 1</option>
        <option selected>Option 2</option>
        <option>Option 3</option>
      </select>
    </div>

    <div data-role="fieldcontain">
      <label for="prev-slide">Slider:</label>
      <input id="prev-slide" type="range" value="60" min="0" max="100" data-highlight="true">
    </div>

    <fieldset data-role="controlgroup" data-type="horizontal">
      <legend>Checkboxes</legend>
      <input type="checkbox" id="chk1" checked>
      <label for="chk1">On</label>
      <input type="checkbox" id="chk2">
      <label for="chk2">Off</label>
    </fieldset>

    <fieldset data-role="controlgroup" data-type="horizontal">
      <legend>Radio</legend>
      <input type="radio" name="r" id="rad1" checked>
      <label for="rad1">On</label>
      <input type="radio" name="r" id="rad2">
      <label for="rad2">Off</label>
    </fieldset>

    <div data-role="fieldcontain">
      <label for="prev-flip">Flipswitch (on):</label>
      <input type="checkbox" id="prev-flip" data-role="flipswitch"
             data-on-text="Enabled" data-off-text="Disabled"
             data-wrapper-class="custom-size-flipswitch" checked>
    </div>
    <div data-role="fieldcontain">
      <label for="prev-flip2">Flipswitch (off):</label>
      <input type="checkbox" id="prev-flip2" data-role="flipswitch"
             data-on-text="Enabled" data-off-text="Disabled"
             data-wrapper-class="custom-size-flipswitch">
    </div>

    <h3 style="margin-top:14px;">Plugin cards</h3>
    <div id="container">
      <div class="plugins-box">
        <div class="tooltip">
          <h4><a href="javascript:void(0)">auto-update</a></h4>
          <span class="tooltiptext">Automatically updates pwnagotchi plugins.</span>
        </div>
        <form onsubmit="return false;" style="margin:0;">
          <input type="checkbox" id="pv-f1" data-role="flipswitch"
                 data-on-text="Enabled" data-off-text="Disabled"
                 data-wrapper-class="custom-size-flipswitch">
          <button type="button" class="ui-btn ui-mini ui-corner-all" style="width:auto;margin:4px auto 0;">Upgrade</button>
        </form>
      </div>
      <div class="plugins-box">
        <div class="tooltip">
          <h4><a href="javascript:void(0)">bt-tether</a></h4>
          <span class="tooltiptext">Bluetooth tethering plugin for internet access.</span>
        </div>
        <form onsubmit="return false;" style="margin:0;">
          <input type="checkbox" id="pv-f2" data-role="flipswitch"
                 data-on-text="Enabled" data-off-text="Disabled"
                 data-wrapper-class="custom-size-flipswitch" checked>
          <button type="button" class="ui-btn ui-mini ui-corner-all" style="width:auto;margin:4px auto 0;">Upgrade</button>
        </form>
      </div>
      <div class="plugins-box">
        <div class="tooltip">
          <h4><a href="javascript:void(0)">refacer</a></h4>
          <span class="tooltiptext">Theme and render manager for pwnagotchi.</span>
        </div>
        <form onsubmit="return false;" style="margin:0;">
          <input type="checkbox" id="pv-f3" data-role="flipswitch"
                 data-on-text="Enabled" data-off-text="Disabled"
                 data-wrapper-class="custom-size-flipswitch" checked>
          <button type="button" class="ui-btn ui-mini ui-corner-all" style="width:auto;margin:4px auto 0;">Upgrade</button>
        </form>
      </div>
    </div>

    <div data-role="collapsible" style="margin-top:14px;">
      <h3>Collapsible section</h3>
      <ul data-role="listview" data-inset="true">
        <li data-role="list-divider">List header</li>
        <li>Read-only item</li>
        <li><a href="javascript:void(0)">Linked item</a></li>
      </ul>
    </div>

    <ul data-role="listview" data-filter="true"
        data-filter-placeholder="Search peers..."
        data-inset="true" style="margin-top:14px;">
      <li class="peer"><a href="javascript:void(0)"><h2>(^_^) pwnagotchi@aabbccdd</h2><p>Pwned 42 networks, 7 encounters.</p></a></li>
      <li class="peer"><a href="javascript:void(0)"><h2>(-.-) unit-b@11223344</h2><p>Pwned 18 networks, 3 encounters.</p></a></li>
    </ul>

    <h3 style="margin-top:14px;">Table</h3>
    <input id="prev-filter" type="text" placeholder="Filter...">
    <table>
      <thead><tr><th>Name</th><th>SSID</th><th>Status</th></tr></thead>
      <tbody>
        <tr><td>device-a</td><td>HomeNet</td><td>Active</td></tr>
        <tr><td>device-b</td><td>Office</td><td>Idle</td></tr>
        <tr><td>device-c</td><td>CafeWifi</td><td>Active</td></tr>
      </tbody>
    </table>

  </div>
</div>
<script src="/js/{jq_js}"></script>
<script>
$(document).on('mobileinit', function() {{
    $.mobile.ajaxEnabled = false;
    $.mobile.pushStateEnabled = false;
    $.mobile.linkBindingEnabled = false;
    $.mobile.hashListeningEnabled = false;
    $.mobile.ignoreContentEnabled = false;
}});
</script>
<script src="/js/jquery.mobile/{jqm_js}"></script>
<script>
$(document).on('click', 'a[href="javascript:void(0)"]', function(e) {{ e.preventDefault(); }});
$(document).on('submit', 'form', function(e) {{ e.preventDefault(); }});
window.addEventListener('message', function(ev) {{
    if (!ev.data || ev.data.type !== 'refacer-css') return;
    var el = document.getElementById('candidate-style');
    if (el) el.textContent = ev.data.css || '';
}});
</script>
</body>
</html>""".format(jq_js=jq_js, jqm_js=jqm_js, jqm_css=jqm_css)

    def _resolve_pwnagotchi_css_paths(self):
        if self._pwnagotchi_static_css_path is not None:
            return (self._pwnagotchi_static_css_path, self._pwnagotchi_css_backup_path)
        try:
            import pwnagotchi as _pwny
            pkg_dir = os.path.dirname(os.path.realpath(_pwny.__file__))
            target = os.path.join(pkg_dir, 'ui', 'web', 'static', 'css', 'style.css')
            if not os.path.isfile(target):
                logging.warning(f"[Refacer][css] pwnagotchi static style.css not found at: {target}")
                return (None, None)
            backup = target + '.refacer-original'
            self._pwnagotchi_static_css_path = target
            self._pwnagotchi_css_backup_path = backup
            return (target, backup)
        except Exception as e:
            logging.warning(f"[Refacer][css] could not resolve pwnagotchi static path: {e}")
            return (None, None)

    def _ensure_pwnagotchi_css_backup(self):
        target, backup = self._resolve_pwnagotchi_css_paths()
        if not target or not backup:
            return False
        if os.path.isfile(backup):
            return True
        try:
            shutil.copy2(target, backup)
            logging.info(f"[Refacer][css] original pwnagotchi CSS backed up to {backup}")
            return True
        except Exception as e:
            self._css_injection_last_error = f"Could not back up original CSS: {e}"
            logging.error(f"[Refacer][css] backup failed: {e}")
            return False

    def _inject_theme_css(self, theme_name):
        self._css_injection_last_error = None
        target, backup = self._resolve_pwnagotchi_css_paths()
        if not target:
            self._css_injection_last_error = "pwnagotchi static CSS path could not be resolved"
            return False
        if not self._ensure_pwnagotchi_css_backup():
            return False
        theme_css_path = None
        if theme_name and theme_name != 'Default':
            theme_root = self._theme_path_for(theme_name)
            if theme_root:
                candidate = os.path.join(theme_root, 'style.css')
                if os.path.isfile(candidate):
                    theme_css_path = candidate
        try:
            if theme_css_path:
                shutil.copy2(theme_css_path, target)
                logging.info(f"[Refacer][css] injected theme CSS theme={theme_name} src={theme_css_path} dst={target}")
            else:
                shutil.copy2(backup, target)
                logging.info(f"[Refacer][css] no theme CSS; restored original theme={theme_name}")
            return True
        except Exception as e:
            self._css_injection_last_error = f"Write to {target} failed: {e}"
            logging.error(f"[Refacer][css] inject failed: {e}")
            return False

    def _restore_original_pwnagotchi_css(self):
        target, backup = self._resolve_pwnagotchi_css_paths()
        if not target or not backup or not os.path.isfile(backup):
            return False
        try:
            shutil.copy2(backup, target)
            logging.info("[Refacer][css] original CSS restored on unload")
            return True
        except Exception as e:
            logging.error(f"[Refacer][css] restore on unload failed: {e}")
            return False

    # ------------------------------------------------------------------ CSS swatch parser/writer

    def _css_token_to_field(self, token):
        for role, fields in self.CSS_SWATCH_FIELDS.items():
            for field, tok in fields.items():
                if tok == token:
                    return (role, field)
        return None

    # TODO Phase 2: heuristic parsing for unannotated CSS (fabricate annotations or extract
    # values from known jQM selectors). Currently falls through to raw-text mode.
    def _parse_css_swatch(self, css_text):
        swatch = {role: {field: '' for field in fields} for role, fields in self.CSS_SWATCH_FIELDS.items()}
        parsed_any = False
        if not css_text:
            return (swatch, parsed_any)
        pattern = re.compile(r'/\*[^{*]*?\{(a-[a-z0-9-]+)\}\s*\*/')
        for match in pattern.finditer(css_text):
            token = match.group(1)
            mapping = self._css_token_to_field(token)
            if not mapping:
                continue
            role, field = mapping
            before = css_text[:match.start()]
            last_break = max(before.rfind(';'), before.rfind('{'), before.rfind('}'))
            if last_break < 0:
                last_break = 0
            decl_head = before[last_break:]
            colon_at = decl_head.find(':')
            if colon_at < 0:
                continue
            value = decl_head[colon_at + 1:].strip()
            if value:
                swatch[role][field] = value
                parsed_any = True
        extras_match = re.search(r'/\*\s*refacer-extras\s*\{([\s\S]*?)\}\s*\*/', css_text)
        if extras_match:
            for ln in extras_match.group(1).splitlines():
                ln = ln.strip().rstrip(';')
                if ':' in ln:
                    k, _, v = ln.partition(':')
                    k, v = k.strip(), v.strip()
                    if k in swatch.get('extras', {}):
                        swatch['extras'][k] = v
                        parsed_any = True
        return (swatch, parsed_any)

    def _write_css_swatch(self, css_text, new_swatch):
        if not new_swatch:
            return css_text or ''
        result = css_text or ''
        pattern = re.compile(r'/\*[^{*]*?\{(a-[a-z0-9-]+)\}\s*\*/')
        for match in reversed(list(pattern.finditer(result))):
            token = match.group(1)
            mapping = self._css_token_to_field(token)
            if not mapping:
                continue
            role, field = mapping
            new_value = ((new_swatch.get(role) or {}).get(field) or '').strip()
            if not new_value:
                continue
            before = result[:match.start()]
            last_break = max(before.rfind(';'), before.rfind('{'), before.rfind('}'))
            if last_break < 0:
                continue
            colon_at = result.find(':', last_break)
            if colon_at < 0 or colon_at >= match.start():
                continue
            i = colon_at + 1
            while i < match.start() and result[i] in ' \t':
                i += 1
            j = match.start()
            while j > i and result[j - 1] in ' \t':
                j -= 1
            result = result[:i] + new_value + result[j:]
        extras = new_swatch.get('extras') or {}
        non_empty = {k: v for k, v in extras.items() if v and v.strip()}
        extras_block = ''
        rules_block = ''
        if non_empty:
            lines = '\n'.join(f'    {k}: {v};' for k, v in non_empty.items())
            extras_block = f'/* refacer-extras {{\n{lines}\n}} */'
            rule_parts = []
            # UI polish only: suppress Chrome/Android tap flash on clickable HTML elements.
            # This does not guarantee control over native open <select>/<option> hover/highlight painting.
            rule_parts.append('a,button,input,select,textarea,label,.ui-btn{-webkit-tap-highlight-color:transparent;}')
            body_parts = []
            if non_empty.get('body-bg'):
                body_parts.append(f"background-color:{non_empty['body-bg']};")
            if non_empty.get('body-text'):
                body_parts.append(f"color:{non_empty['body-text']};")
            if body_parts:
                rule_parts.append('body{' + ''.join(body_parts) + '}')
            if non_empty.get('body-font'):
                rule_parts.append(f"body,.ui-page-theme-a,.ui-body-a,.ui-overlay-a{{font-family:{non_empty['body-font']};}}")
            if non_empty.get('heading-font'):
                rule_parts.append(f"h1,h2,h3,h4,h5,h6,.ui-header .ui-title{{font-family:{non_empty['heading-font']};}}")
            if non_empty.get('button-font'):
                rule_parts.append(f".ui-btn,button,input[type='button'],input[type='submit']{{font-family:{non_empty['button-font']};}}")
            if non_empty.get('mono-font'):
                rule_parts.append(f"code,pre,textarea,.refacer-diagnostics,.refacer-textarea{{font-family:{non_empty['mono-font']};}}")
            nav_parts = []
            if non_empty.get('nav-active-bg'):
                nav_parts.append(f"background-color:{non_empty['nav-active-bg']};")
            if non_empty.get('nav-active-text'):
                nav_parts.append(f"color:{non_empty['nav-active-text']};")
            if nav_parts:
                rule_parts.append('.ui-navbar .ui-btn-active,.ui-footer .ui-navbar .ui-btn-active{' + ''.join(nav_parts) + '}')
            fs_on_parts = []
            if non_empty.get('flipswitch-on-bg'):
                fs_on_parts.append(f"background-color:{non_empty['flipswitch-on-bg']};")
            if non_empty.get('flipswitch-on-text'):
                fs_on_parts.append(f"color:{non_empty['flipswitch-on-text']};")
            if fs_on_parts:
                rule_parts.append(
                    '.ui-page-theme-a .ui-flipswitch-active,'
                    'html .ui-bar-a .ui-flipswitch-active,'
                    'html .ui-body-a .ui-flipswitch-active,'
                    '.ui-page-theme-a .ui-flipswitch-active .ui-btn,'
                    'html .ui-bar-a .ui-flipswitch-active .ui-btn,'
                    'html .ui-body-a .ui-flipswitch-active .ui-btn{'
                    + ''.join(fs_on_parts) + '}'
                )
            fs_off_parts = []
            if non_empty.get('flipswitch-off-bg'):
                fs_off_parts.append(f"background-color:{non_empty['flipswitch-off-bg']};")
            if non_empty.get('flipswitch-off-text'):
                fs_off_parts.append(f"color:{non_empty['flipswitch-off-text']};")
            if fs_off_parts:
                rule_parts.append(
                    '.ui-page-theme-a .ui-flipswitch:not(.ui-flipswitch-active),'
                    'html .ui-bar-a .ui-flipswitch:not(.ui-flipswitch-active),'
                    'html .ui-body-a .ui-flipswitch:not(.ui-flipswitch-active),'
                    '.ui-page-theme-a .ui-flipswitch:not(.ui-flipswitch-active) .ui-btn,'
                    'html .ui-bar-a .ui-flipswitch:not(.ui-flipswitch-active) .ui-btn,'
                    'html .ui-body-a .ui-flipswitch:not(.ui-flipswitch-active) .ui-btn{'
                    + ''.join(fs_off_parts) + '}'
                )
            inp_parts = []
            if non_empty.get('input-bg'):
                inp_parts.append(f"background-color:{non_empty['input-bg']};")
            if non_empty.get('input-border'):
                inp_parts.append(f"border-color:{non_empty['input-border']};")
            if non_empty.get('input-text'):
                inp_parts.append(f"color:{non_empty['input-text']};")
            if inp_parts:
                rule_parts.append('.ui-input-text input,.ui-input-search input,.ui-select .ui-btn,.ui-slider-input{' + ''.join(inp_parts) + '}')
            li_parts = []
            if non_empty.get('listitem-bg'):
                li_parts.append(f"background-color:{non_empty['listitem-bg']};")
            if non_empty.get('listitem-text'):
                li_parts.append(f"color:{non_empty['listitem-text']};")
            if li_parts:
                rule_parts.append('.ui-listview li,.ui-listview .ui-li-static{' + ''.join(li_parts) + '}')
            pb_parts = []
            if non_empty.get('plugin-box-bg'):
                pb_parts.append(f"background-color:{non_empty['plugin-box-bg']};")
            if non_empty.get('plugin-box-border'):
                pb_parts.append(f"border-color:{non_empty['plugin-box-border']};")
            if non_empty.get('plugin-box-text'):
                pb_parts.append(f"color:{non_empty['plugin-box-text']};")
            if pb_parts:
                rule_parts.append('.plugins-box{' + ''.join(pb_parts) + '}')
            tt_parts = []
            if non_empty.get('tooltip-bg'):
                tt_parts.append(f"background-color:{non_empty['tooltip-bg']} !important;")
            if non_empty.get('tooltip-text'):
                tt_parts.append(f"color:{non_empty['tooltip-text']} !important;")
            if non_empty.get('tooltip-border'):
                tt_parts.append(f"border-color:{non_empty['tooltip-border']} !important;")
            if tt_parts:
                rule_parts.append('.tooltip .tooltiptext{' + ''.join(tt_parts) + '}')
            th_parts = []
            if non_empty.get('table-header-bg'):
                th_parts.append(f"background-color:{non_empty['table-header-bg']};")
            if non_empty.get('table-header-text'):
                th_parts.append(f"color:{non_empty['table-header-text']};")
            if th_parts:
                rule_parts.append('thead{' + ''.join(th_parts) + '}')
            tr_parts = []
            if non_empty.get('table-row-bg'):
                tr_parts.append(f"background-color:{non_empty['table-row-bg']};")
            if non_empty.get('table-row-text'):
                tr_parts.append(f"color:{non_empty['table-row-text']};")
            if tr_parts:
                rule_parts.append('tbody tr{' + ''.join(tr_parts) + '}')
            if non_empty.get('table-alt-row-bg'):
                rule_parts.append(f"tbody tr:nth-child(even){{background-color:{non_empty['table-alt-row-bg']};}}")
            if non_empty.get('table-row-hover-bg'):
                rule_parts.append(f"tbody tr:hover{{background-color:{non_empty['table-row-hover-bg']};}}")
            sel_parts = []
            if non_empty.get('select-bg'):
                sel_parts.append(f"background-color:{non_empty['select-bg']};")
            if non_empty.get('select-text'):
                sel_parts.append(f"color:{non_empty['select-text']};")
            if non_empty.get('select-border'):
                sel_parts.append(f"border-color:{non_empty['select-border']};")
            if sel_parts:
                rule_parts.append('select,option,.ui-selectmenu-list li,.ui-selectmenu-list .ui-btn,.ui-selectmenu-menu .ui-btn,.ui-selectmenu-menu .ui-listview li,.ui-popup .ui-listview li,.ui-popup .ui-listview .ui-btn{' + ''.join(sel_parts) + '}')
            sel_hover_parts = []
            if non_empty.get('select-hover-bg'):
                sel_hover_parts.append(f"background:{non_empty['select-hover-bg']};")
                sel_hover_parts.append(f"background-color:{non_empty['select-hover-bg']};")
                sel_hover_parts.append("background-image:none;")
            if non_empty.get('select-hover-text'):
                sel_hover_parts.append(f"color:{non_empty['select-hover-text']};")
            if sel_hover_parts:
                sel_hover_parts.append("text-shadow:none;")
                sel_hover_parts.append("box-shadow:none;")
                sel_hover_parts.append("-webkit-box-shadow:none;")
                rule_parts.append('option:hover,option:focus,.ui-selectmenu-list .ui-btn:hover,.ui-selectmenu-list .ui-btn:focus,.ui-selectmenu-list .ui-btn.ui-state-hover,.ui-selectmenu-list .ui-btn.ui-state-focus,.ui-selectmenu-list .ui-btn.ui-state-active,.ui-selectmenu-list .ui-btn.ui-btn-active,.ui-selectmenu-list li:hover > .ui-btn,.ui-selectmenu-list li.ui-focus > .ui-btn,.ui-selectmenu-list li.ui-state-focus > .ui-btn,.ui-selectmenu-list li.ui-state-active > .ui-btn,.ui-selectmenu-list .ui-focus,.ui-selectmenu-list .ui-state-focus,.ui-selectmenu-list .ui-state-active,.ui-selectmenu-menu .ui-btn:hover,.ui-selectmenu-menu .ui-btn:focus,.ui-selectmenu-menu .ui-btn.ui-state-hover,.ui-selectmenu-menu .ui-btn.ui-state-focus,.ui-selectmenu-menu .ui-btn.ui-state-active,.ui-selectmenu-menu .ui-btn.ui-btn-active,.ui-selectmenu-menu .ui-listview .ui-btn:hover,.ui-selectmenu-menu .ui-listview .ui-btn:focus,.ui-selectmenu-menu .ui-listview .ui-btn.ui-state-hover,.ui-selectmenu-menu .ui-listview .ui-btn.ui-state-focus,.ui-selectmenu-menu .ui-listview .ui-btn.ui-state-active,.ui-selectmenu-menu .ui-listview .ui-btn.ui-btn-active,.ui-popup .ui-listview .ui-btn:hover,.ui-popup .ui-listview .ui-btn:focus,.ui-popup .ui-listview .ui-btn.ui-state-hover,.ui-popup .ui-listview .ui-btn.ui-state-focus,.ui-popup .ui-listview .ui-btn.ui-state-active,.ui-popup .ui-listview .ui-btn.ui-btn-active{' + ''.join(sel_hover_parts) + '}')
            sel_active_parts = []
            if non_empty.get('select-active-bg'):
                sel_active_parts.append(f"background:{non_empty['select-active-bg']};")
                sel_active_parts.append(f"background-color:{non_empty['select-active-bg']};")
                sel_active_parts.append("background-image:none;")
            if non_empty.get('select-active-text'):
                sel_active_parts.append(f"color:{non_empty['select-active-text']};")
            if sel_active_parts:
                sel_active_parts.append("text-shadow:none;")
                sel_active_parts.append("box-shadow:none;")
                sel_active_parts.append("-webkit-box-shadow:none;")
                rule_parts.append('option:checked,option[selected],.ui-selectmenu-list .ui-btn.ui-btn-active,.ui-selectmenu-menu .ui-btn.ui-btn-active,.ui-selectmenu-menu .ui-listview .ui-btn.ui-btn-active,.ui-popup .ui-listview .ui-btn.ui-btn-active,.ui-selectmenu-list .ui-btn[aria-selected="true"],.ui-selectmenu-menu .ui-btn[aria-selected="true"],.ui-popup .ui-listview .ui-btn[aria-selected="true"]{' + ''.join(sel_active_parts) + '}')
            if non_empty.get('icon-disc-bg'):
                rule_parts.append(f".ui-page-theme-a .ui-icon-disc,.ui-bar-a .ui-icon-disc,.ui-body-a .ui-icon-disc,.ui-btn-a .ui-icon-disc{{background-color:{non_empty['icon-disc-bg']};}}")
            if non_empty.get('icon-color'):
                rule_parts.append(f".ui-page-theme-a .ui-icon::after,.ui-bar-a .ui-icon::after,.ui-body-a .ui-icon::after,.ui-btn-a .ui-icon::after{{background-color:{non_empty['icon-color']};}}")
            if non_empty.get('focus-shadow'):
                v = non_empty['focus-shadow']
                rule_parts.append(f".ui-page-theme-a .ui-btn:focus,html .ui-bar-a .ui-btn:focus,html .ui-body-a .ui-btn:focus,.ui-page-theme-a .ui-focus{{box-shadow:0 0 12px {v};-webkit-box-shadow:0 0 12px {v};}}")
            if rule_parts:
                rules_block = '/* refacer-extras-rules */\n' + '\n'.join(rule_parts) + '\n/* end refacer-extras-rules */'
        extras_re = re.compile(r'/\*\s*refacer-extras\s*\{[\s\S]*?\}\s*\*/')
        rules_re = re.compile(r'/\*\s*refacer-extras-rules\s*\*/[\s\S]*?/\*\s*end\s+refacer-extras-rules\s*\*/')
        if extras_block:
            if extras_re.search(result):
                result = extras_re.sub(extras_block, result)
            else:
                result = result.rstrip() + '\n\n' + extras_block + '\n'
            if rules_block:
                if rules_re.search(result):
                    result = rules_re.sub(rules_block, result)
                else:
                    result = result.rstrip() + '\n' + rules_block + '\n'
        else:
            result = extras_re.sub('', result)
            result = rules_re.sub('', result)
        return result

    # ------------------------------------------------------------------ CSS editor state

    def _load_css_editor_state(self, theme_name):
        if not theme_name or theme_name == 'Default':
            target, _ = self._resolve_pwnagotchi_css_paths()
            raw = ''
            if target and os.path.isfile(target):
                try:
                    with open(target, 'r', encoding='utf-8') as fh:
                        raw = fh.read()
                except Exception as e:
                    logging.warning(f"[Refacer][css] could not read default css: {e}")
            swatch, parsed_any = self._parse_css_swatch(raw)
            return {'theme': 'Default', 'raw_css': raw, 'swatch': swatch,
                    'has_annotations': parsed_any, 'is_default': True,
                    'injection_error': self._css_injection_last_error}
        theme_root = self._theme_path_for(theme_name)
        if not theme_root:
            raise ValueError(f"Theme '{theme_name}' not found.")
        css_path = os.path.join(theme_root, 'style.css')
        raw = ''
        if os.path.isfile(css_path):
            with open(css_path, 'r', encoding='utf-8') as fh:
                raw = fh.read()
        swatch, parsed_any = self._parse_css_swatch(raw)
        return {'theme': theme_name, 'raw_css': raw, 'swatch': swatch,
                'has_annotations': parsed_any, 'is_default': False,
                'injection_error': self._css_injection_last_error}

    def _save_css_editor_state(self, theme_name, swatch=None, raw_css=None, reinject=True):
        if not theme_name or theme_name == 'Default':
            raise ValueError('Default theme is read-only.')
        theme_root = self._theme_path_for(theme_name)
        if not theme_root:
            raise ValueError(f"Theme '{theme_name}' not found.")
        os.makedirs(theme_root, exist_ok=True)
        css_path = os.path.join(theme_root, 'style.css')
        base_css = ''
        if os.path.isfile(css_path):
            with open(css_path, 'r', encoding='utf-8') as fh:
                base_css = fh.read()
        if raw_css is not None:
            final_css = raw_css
        elif swatch is not None:
            final_css = self._write_css_swatch(base_css, swatch)
        else:
            raise ValueError('Either swatch or raw_css is required.')
        self._write_text_file(css_path, final_css)
        injected = False
        if reinject and theme_name == self._theme_name:
            injected = self._inject_theme_css(theme_name)
        return {'theme': theme_name, 'injected': injected,
                'injection_error': self._css_injection_last_error}

    def _theme_info(self, theme_name):
        if not theme_name or theme_name == 'Default':
            info = dict(DEFAULT_THEME_INFO)
            info['screenshot_url'] = None
            return info
        screenshot_url = None
        if self._mirror_theme_img_tree(theme_name) and os.path.exists(os.path.join(self._repo_theme_mirror_path(theme_name), 'screenshot.png')):
            screenshot_url = self._repo_theme_screenshot_url(theme_name)
        info_path = self._resolve_theme_paths(theme_name)['info']
        if not os.path.exists(info_path):
            return {
                'author': 'Unknown',
                'version': 'Unknown',
                'display': 'main',
                'plugins': 'refacer',
                'notes': 'No theme metadata found.',
                'screenshot_url': screenshot_url,
            }
        logging.debug(f"[Refacer] Loading theme info for {theme_name} from {info_path}")
        if info_path.endswith('.md'):
            return {
                'author': 'Unknown',
                'version': 'Unknown',
                'display': 'main',
                'plugins': 'refacer',
                'notes': self._sanitize_metadata_html(self._read_text_file(info_path), field='notes', theme_name=theme_name),
                'screenshot_url': screenshot_url,
            }
        with open(info_path, 'r', encoding='utf-8') as handle:
            info = json.load(handle)
        for key in ('author', 'version', 'display', 'plugins', 'notes'):
            if key in info:
                info[key] = self._sanitize_metadata_html(info[key], field=key, theme_name=theme_name)
        info['screenshot_url'] = screenshot_url
        return info

    def _load_theme_editor_payload(self, theme_name):
        theme_name = theme_name or self._theme_name
        resolved = self._resolve_theme_paths(theme_name)
        return {
            'theme': theme_name,
            'config_toml': self._read_text_file(resolved['config']),
            'css': self._read_text_file(resolved['css']),
            'info': self._read_text_file(resolved['info']),
            'render': {
                'display_output_mode': self.options.get('display_output_mode', self.DEFAULT_OPTIONS['display_output_mode']),
                '1bit': self.options.get('1bit', False),
                'save_images': self.options.get('save_images', False),
                'experimental_non_native_selects': self.options.get('experimental_non_native_selects', self.DEFAULT_OPTIONS['experimental_non_native_selects']),
                'save_interval': self.options.get('save_interval', self.DEFAULT_OPTIONS['save_interval']),
                'fps': self.options.get('fps', self.DEFAULT_OPTIONS['fps']),
                'rotation': self._current_rotation(),
                'display_control_enabled': self.options.get('display_control_enabled', self.DEFAULT_OPTIONS['display_control_enabled']),
                'display_auto_off_seconds': self.options.get('display_auto_off_seconds', self.DEFAULT_OPTIONS['display_auto_off_seconds']),
                'display_blank_color': self.options.get('display_blank_color', self.DEFAULT_OPTIONS['display_blank_color']),
                'display_sleep_backend': self.options.get('display_sleep_backend', self.DEFAULT_OPTIONS['display_sleep_backend']),
                'display_sleep_windows_restore': self.options.get('display_sleep_windows_restore', self.DEFAULT_OPTIONS['display_sleep_windows_restore']),
                'display_sleep_windows_restore_previous': self.options.get('display_sleep_windows_restore_previous', self.DEFAULT_OPTIONS['display_sleep_windows_restore_previous']),
                'display_sleep_windows_mode': self.options.get('display_sleep_windows_mode', self.DEFAULT_OPTIONS['display_sleep_windows_mode']),
                'display_sleep_windows_sub_mode': self.options.get('display_sleep_windows_sub_mode', self.DEFAULT_OPTIONS['display_sleep_windows_sub_mode']),
            },
        }

    def _reload_theme_state(self):
        theme_name = self.options.get('theme') or 'Default'
        theme_path = self._theme_path_for(theme_name)
        theme_config = self._read_theme_config(theme_name)
        raw_bundle = self._theme_bundle_from_config(theme_config)
        sanitized_bundle = self._sanitize_theme_bundle(raw_bundle)
        new_runtime = self._build_theme_runtime(theme_name, theme_path, sanitized_bundle)
        with self._lock:
            self._reset_runtime_render_state(clear_theme=True)
            next_version = self._theme_runtime_version + 1
            new_runtime['runtime_version'] = next_version
            self._theme_name = theme_name
            self._theme_path = theme_path
            self._theme_bundle = sanitized_bundle
            self._theme_assets = new_runtime['assets']
            self._theme_runtime = new_runtime
            self._theme_runtime_version = next_version
            self._anim_frame_index = new_runtime.get('anim_frame_index', 0)
            self.font_name = new_runtime.get('font_name', self.font_name)
            self.font_bold_name = new_runtime.get('font_bold_name', self.font_bold_name)
            self.font_status_name = new_runtime.get('font_status_name', self.font_status_name)
            self.f_awesome_name = new_runtime.get('f_awesome_name', self.f_awesome_name)
            self.Small = new_runtime.get('Small')
            self.Medium = new_runtime.get('Medium')
            self.BoldSmall = new_runtime.get('BoldSmall')
            self.Bold = new_runtime.get('Bold')
            self.BoldBig = new_runtime.get('BoldBig')
            self.Huge = new_runtime.get('Huge')
            snapshot_id = self._theme_snapshot_id()
            options = self._theme_options(new_runtime)
        logging.info(
            f"[Refacer][themes] theme activated name={theme_name} "
            f"fallback={self._theme_fallback_notice or 'none'}"
        )
        self._reset_editor_draft(theme_name)
        self._mirror_theme_img_tree(theme_name)

    def _set_active_theme(self, theme_name):
        if not theme_name or theme_name == 'Default':
            self.options['theme'] = 'Default'
        else:
            if theme_name not in self._theme_list():
                raise ValueError(f"Theme '{theme_name}' not found.")
        self.options['theme'] = theme_name
        self._persist_plugin_options()
        self._reload_theme_state()
        played_boot = self._maybe_play_boot_animation('theme_switch')
        if not played_boot and self._display_control_is_enabled() and not self._display_hardware_publish_allowed():
            logging.info("[Refacer][display] theme switch kept display off")
        self._prepare_boot_animation_cache()
        self._inject_theme_css(theme_name)

    def _save_theme_editor_payload(self, payload):
        render = payload.get('render', {})
        selected_output_mode = self._sanitize_display_output_mode(
            render.get('display_output_mode', self.options.get('display_output_mode', self.DEFAULT_OPTIONS['display_output_mode'])),
            self.options.get('display_output_mode', self.DEFAULT_OPTIONS['display_output_mode']),
        )
        if 'display_output_mode' not in render and render.get('1bit') is True:
            selected_output_mode = '1bit'
        self.options['display_output_mode'] = selected_output_mode
        self.options['1bit'] = selected_output_mode == '1bit'
        self.options['save_images'] = bool(render.get('save_images', self.options.get('save_images', self.DEFAULT_OPTIONS['save_images'])))
        self.options['experimental_non_native_selects'] = bool(
            render.get(
                'experimental_non_native_selects',
                self.options.get('experimental_non_native_selects', self.DEFAULT_OPTIONS['experimental_non_native_selects'])
            )
        )
        self.options['save_interval'] = self._sanitize_int(
            render.get('save_interval', self.options.get('save_interval', self.DEFAULT_OPTIONS['save_interval'])),
            self.DEFAULT_OPTIONS['save_interval'],
            minimum=1,
        )
        self.options['fps'] = self._sanitize_int(
            render.get('fps', self.options.get('fps', self.DEFAULT_OPTIONS['fps'])),
            self.DEFAULT_OPTIONS['fps'],
            minimum=1,
        )
        self.fps = self.options['fps']
        self._set_display_rotation(render.get('rotation', self._current_rotation()))
        self.options['display_control_enabled'] = bool(
            render.get(
                'display_control_enabled',
                self.options.get('display_control_enabled', self.DEFAULT_OPTIONS['display_control_enabled'])
            )
        )
        self.options['display_blank_color'] = (
            render.get('display_blank_color')
            or self.options.get('display_blank_color')
            or self.DEFAULT_OPTIONS['display_blank_color']
        )
        backend = str(render.get('display_sleep_backend', self.options.get('display_sleep_backend', 'auto')) or 'auto').strip().lower()
        self.options['display_sleep_backend'] = backend if backend in ('blank', 'windows', 'auto') else 'auto'
        self.options['display_sleep_windows_restore'] = bool(
            render.get(
                'display_sleep_windows_restore',
                self.options.get('display_sleep_windows_restore', self.DEFAULT_OPTIONS['display_sleep_windows_restore'])
            )
        )
        self.options['display_sleep_windows_restore_previous'] = bool(
            render.get(
                'display_sleep_windows_restore_previous',
                self.options.get('display_sleep_windows_restore_previous', self.DEFAULT_OPTIONS['display_sleep_windows_restore_previous'])
            )
        )
        self.options['display_sleep_windows_mode'] = (
            str(render.get('display_sleep_windows_mode') or self.options.get('display_sleep_windows_mode') or 'screen_saver').strip()
            or 'screen_saver'
        )
        self.options['display_sleep_windows_sub_mode'] = str(
            render.get('display_sleep_windows_sub_mode', self.options.get('display_sleep_windows_sub_mode', '')) or ''
        ).strip()
        seconds = self._sanitize_int(
            render.get('display_auto_off_seconds', self.options.get('display_auto_off_seconds', self.DEFAULT_OPTIONS['display_auto_off_seconds'])),
            self.DEFAULT_OPTIONS['display_auto_off_seconds'],
            minimum=0,
        )
        with self._display_control_lock:
            self._display_auto_off_seconds = seconds
            self.options['display_auto_off_seconds'] = seconds
            self._reset_display_auto_off_deadline_locked()
            self._sync_display_control_stats()

        theme_name = payload.get('theme') or self._theme_name or 'Default'
        self.options['theme'] = theme_name
        self._persist_plugin_options()

        if theme_name != 'Default':
            theme_path = self._theme_path_for(theme_name)
            os.makedirs(theme_path, exist_ok=True)

            config_toml = payload.get('config_toml', '')
            css = payload.get('css', '')
            info = payload.get('info', '')

            resolved = self._resolve_theme_paths(theme_name)
            config_path = resolved['config'] or os.path.join(theme_path, 'config.toml')
            css_path = resolved['css'] or os.path.join(theme_path, 'style.css')
            info_path = resolved['info'] or os.path.join(theme_path, 'info.json')
            logging.debug(
                f"[Refacer] Saving theme payload for {theme_name}: "
                f"config={config_path}, css={css_path}, info={info_path}"
            )

            for parent in (os.path.dirname(config_path), os.path.dirname(css_path), os.path.dirname(info_path)):
                if parent:
                    os.makedirs(parent, exist_ok=True)

            if config_toml.strip():
                toml.loads(config_toml)
                self._write_text_file(config_path, config_toml)
            elif os.path.exists(config_path):
                os.remove(config_path)

            if css.strip():
                self._write_text_file(css_path, css)
            elif os.path.exists(css_path):
                os.remove(css_path)

            if info.strip():
                if info_path.endswith('.json'):
                    json.loads(info)
                self._write_text_file(info_path, info)
            elif os.path.exists(info_path):
                os.remove(info_path)

        self._invalidate_theme_inventory()
        self._rebuild_repo_screenshots_tree()
        self._invalidate_boot_animation_cache(theme_name=theme_name)
        self._reload_theme_state()
        self._prepare_boot_animation_cache()

    def _github_headers(self):
        token = self.options.get('github_token') or ''
        headers = {'Accept': 'application/vnd.github+json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def _fetch_remote_themes(self):
        logging.debug(f"[Refacer][remote] Fetching remote themes from {THEMES_REPO}")
        self._last_remote_error = None
        try:
            response = requests.get(THEMES_REPO, headers=self._github_headers(), timeout=10)
            self._last_remote_status = response.status_code
            logging.debug(f"[Refacer][remote] Remote theme list status: {response.status_code}")
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as e:
            self._last_remote_error = "GitHub theme list timed out."
            logging.error(f"[Refacer][remote] Remote theme list timeout: {e}")
            raise RuntimeError(self._last_remote_error)
        except requests.HTTPError as e:
            self._last_remote_error = f"GitHub theme list failed with HTTP {response.status_code}."
            logging.error(f"[Refacer][remote] Remote theme list HTTP error: {e}")
            raise RuntimeError(self._last_remote_error)
        except requests.RequestException as e:
            self._last_remote_error = "GitHub theme list request failed."
            logging.error(f"[Refacer][remote] Remote theme list request error: {e}")
            raise RuntimeError(self._last_remote_error)
        except ValueError as e:
            self._last_remote_error = "GitHub theme list returned invalid JSON."
            logging.error(f"[Refacer][remote] Remote theme list JSON error: {e}")
            raise RuntimeError(self._last_remote_error)

        remote_themes = []
        if not isinstance(payload, list):
            self._last_remote_error = "GitHub theme list returned an unexpected response shape."
            logging.error(f"[Refacer][remote] Remote theme list shape mismatch: {type(payload).__name__}")
            raise RuntimeError(self._last_remote_error)

        for item in payload:
            if item.get('type') != 'dir':
                continue
            theme_name = item.get('name')
            theme_info = {
                'name': theme_name,
                'author': 'Unknown',
                'version': 'Unknown',
                'notes': 'No metadata.',
            }
            detail_response = requests.get(item['url'], headers=self._github_headers(), timeout=10)
            detail_response.raise_for_status()
            for child in detail_response.json():
                if child.get('name') == 'info.json' and child.get('download_url'):
                    info_response = requests.get(child['download_url'], headers=self._github_headers(), timeout=10)
                    info_response.raise_for_status()
                    info = info_response.json()
                    theme_info['author'] = info.get('author', 'Unknown')
                    theme_info['version'] = info.get('version', 'Unknown')
                    theme_info['notes'] = info.get('notes', 'No metadata.')
                    break
            remote_themes.append(theme_info)

        remote_themes = sorted(remote_themes, key=lambda item: item['name'].lower())
        self._last_remote_count = len(remote_themes)
        logging.info(f"[Refacer][remote] Remote themes refreshed: {len(remote_themes)} themes")
        return remote_themes

    def _download_theme_contents(self, contents, current_path):
        for item in contents:
            item_path = os.path.join(current_path, item['name'])
            if item['type'] == 'dir':
                os.makedirs(item_path, exist_ok=True)
                dir_response = requests.get(item['url'], headers=self._github_headers(), timeout=10)
                dir_response.raise_for_status()
                self._download_theme_contents(dir_response.json(), item_path)
            elif item.get('download_url'):
                file_response = requests.get(item['download_url'], headers=self._github_headers(), timeout=10)
                file_response.raise_for_status()
                with open(item_path, 'wb') as handle:
                    handle.write(file_response.content)

    def _download_theme(self, theme_name):
        if not theme_name:
            raise ValueError('No theme selected.')

        theme_contents_url = os.path.join(THEMES_REPO, theme_name)
        logging.info(f"[Refacer][remote] Downloading theme '{theme_name}'")
        response = requests.get(theme_contents_url, headers=self._github_headers(), timeout=10)
        response.raise_for_status()
        contents = response.json()

        temp_dir = tempfile.mkdtemp(prefix='refacer-theme-')
        try:
            temp_theme_path = os.path.join(temp_dir, theme_name)
            os.makedirs(temp_theme_path, exist_ok=True)
            self._download_theme_contents(contents, temp_theme_path)

            final_path = os.path.join(self._themes_root, theme_name)
            if os.path.exists(final_path):
                shutil.rmtree(final_path)
            shutil.move(temp_theme_path, final_path)
            top_level = sorted(os.listdir(final_path))
            logging.info(f"[Refacer][remote] Theme '{theme_name}' downloaded")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        self._invalidate_theme_inventory()
        self._theme_list()
        self._rebuild_repo_screenshots_tree()

    def _sanitize_theme_name(self, name):
        value = '' if name is None else str(name).strip()
        if not value:
            raise ValueError('Theme name is required.')
        if value == 'Default':
            raise ValueError('Default theme cannot be modified.')
        safe = re.sub(r'[^A-Za-z0-9._-]+', '-', value).strip('.-')
        if not safe:
            raise ValueError('Theme name is invalid.')
        return safe

    def _assert_theme_exists(self, theme_name):
        safe = self._sanitize_theme_name(theme_name)
        meta = self._theme_meta(safe)
        if not meta or not os.path.isdir(meta['path']):
            raise ValueError(f"Theme '{safe}' not found.")
        return safe, meta['path']

    def _refresh_theme_storage(self):
        self._invalidate_theme_inventory()
        self._theme_list()
        self._rebuild_repo_screenshots_tree()

    def _copy_theme(self, theme_name, new_name):
        theme_name, src_path = self._assert_theme_exists(theme_name)
        target_name = self._sanitize_theme_name(new_name)
        if target_name == theme_name:
            raise ValueError('New theme name must be different.')
        dst_path = os.path.join(self._themes_root, target_name)
        if os.path.exists(dst_path):
            raise ValueError(f"Theme '{target_name}' already exists.")
        shutil.copytree(src_path, dst_path, symlinks=True)
        self._refresh_theme_storage()
        return target_name

    def _export_theme(self, theme_name):
        if not theme_name or theme_name == 'Default':
            raise ValueError('Default theme cannot be exported.')
        theme_name, src_path = self._assert_theme_exists(theme_name)
        zip_path = os.path.join(tempfile.gettempdir(), f"{theme_name}_export.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for dirpath, _dirnames, filenames in os.walk(src_path):
                for filename in filenames:
                    abs_path = os.path.join(dirpath, filename)
                    relpath = os.path.relpath(abs_path, src_path)
                    zf.write(abs_path, arcname=os.path.join(theme_name, relpath))
        return zip_path

    def _new_theme(self, new_name):
        target_name = self._sanitize_theme_name(new_name)
        dst_path = os.path.join(self._themes_root, target_name)
        if os.path.exists(dst_path):
            raise ValueError(f"Theme '{target_name}' already exists.")
        import copy
        bundle = copy.deepcopy(self.DEFAULT_THEME_MODEL)
        state_map = {}
        if getattr(self, '_view_instance', None) is not None:
            try:
                state_map = self._state_mapping(self._view_instance._state).copy()
            except Exception:
                state_map = {}
        widgets = bundle.setdefault('theme', {}).setdefault('widget', {})
        for key in state_map:
            if key not in widgets:
                widgets[key] = {}
        os.makedirs(dst_path, exist_ok=True)
        config_path = os.path.join(dst_path, 'config.toml')
        self._write_text_file(config_path, toml.dumps(bundle))
        info = dict(DEFAULT_THEME_INFO)
        info.update({'author': 'user', 'version': '1.0', 'notes': 'Created from defaults.'})
        info_path = os.path.join(dst_path, 'info.json')
        self._write_text_file(info_path, json.dumps(info, indent=2))
        self._refresh_theme_storage()
        return target_name

    def _rename_theme(self, theme_name, new_name):
        theme_name, src_path = self._assert_theme_exists(theme_name)
        if theme_name == self._theme_name:
            raise ValueError('Active theme cannot be renamed.')
        target_name = self._sanitize_theme_name(new_name)
        if target_name == theme_name:
            return target_name
        dst_path = os.path.join(os.path.dirname(src_path), target_name)
        if os.path.exists(dst_path):
            raise ValueError(f"Theme '{target_name}' already exists.")
        os.rename(src_path, dst_path)
        self._refresh_theme_storage()
        return target_name

    def _delete_theme(self, theme_name):
        theme_name, src_path = self._assert_theme_exists(theme_name)
        if theme_name == self._theme_name:
            raise ValueError('Active theme cannot be deleted.')
        if os.path.commonpath([os.path.realpath(src_path), os.path.realpath(self._themes_root)]) != os.path.realpath(self._themes_root):
            raise ValueError('Only local themes inside Refacer themes/ can be deleted.')
        shutil.rmtree(src_path)
        self._refresh_theme_storage()
        return theme_name

    def _iter_theme_dirs_from_extracted_root(self, root_dir):
        theme_dirs = []
        if self._theme_is_valid(root_dir):
            theme_dirs.append(root_dir)
        for name in sorted(os.listdir(root_dir)):
            candidate = os.path.join(root_dir, name)
            if os.path.isdir(candidate) and self._theme_is_valid(candidate):
                theme_dirs.append(candidate)
        seen = set()
        ordered = []
        for item in theme_dirs:
            real = os.path.realpath(item)
            if real not in seen:
                seen.add(real)
                ordered.append(item)
        return ordered

    def _upload_theme_zip(self, uploaded_file):
        if uploaded_file is None or not getattr(uploaded_file, 'filename', ''):
            raise ValueError('No zip file uploaded.')
        filename = str(uploaded_file.filename)
        if not filename.lower().endswith('.zip'):
            raise ValueError('Only zip files are supported.')
        temp_dir = tempfile.mkdtemp(prefix='refacer-upload-')
        installed = []
        try:
            archive_path = os.path.join(temp_dir, 'theme.zip')
            uploaded_file.save(archive_path)
            with zipfile.ZipFile(archive_path, 'r') as zf:
                bad = [name for name in zf.namelist() if name.startswith('/') or '..' in pathlib.PurePosixPath(name).parts]
                if bad:
                    raise ValueError('Zip contains unsafe paths.')
                extract_dir = os.path.join(temp_dir, 'extract')
                os.makedirs(extract_dir, exist_ok=True)
                zf.extractall(extract_dir)
            theme_dirs = self._iter_theme_dirs_from_extracted_root(extract_dir)
            if not theme_dirs:
                raise ValueError('No valid theme folder found in zip.')
            os.makedirs(self._themes_root, exist_ok=True)
            for theme_dir in theme_dirs:
                theme_name = self._sanitize_theme_name(os.path.basename(theme_dir))
                dst_path = os.path.join(self._themes_root, theme_name)
                if os.path.exists(dst_path):
                    shutil.rmtree(dst_path)
                shutil.copytree(theme_dir, dst_path, symlinks=True)
                installed.append(theme_name)
            self._refresh_theme_storage()
            return installed
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _compare_theme_version(self, theme_name, remote_version):
        if not theme_name:
            raise ValueError('No theme selected.')
        local_info = self._theme_info(theme_name)
        local_version = local_info.get('version')
        return {
            'theme': theme_name,
            'local_version': local_version,
            'remote_version': remote_version,
            'is_newer': bool(remote_version and local_version and remote_version != local_version),
        }

    def get_refacer_theme(self, view_instance=None, state=None):
        return dict(self._theme_bundle)

    def _theme_options(self, theme_source=None):
        if isinstance(theme_source, dict) and 'theme_bundle' in theme_source:
            bundle = theme_source.get('theme_bundle') or {}
        else:
            bundle = self._theme_bundle if theme_source is None else theme_source
        return bundle.get('theme', {}).get('options', {})

    def _sanitize_display_output_mode(self, value, default='theme'):
        if value is None:
            return default
        mode = str(value).strip().lower()
        if mode in ('theme', 'rgba', 'palette', '1bit'):
            return mode
        return default

    def _theme_declared_color_mode(self, theme_source=None):
        return self._theme_options(theme_source).get('color_mode')

    def _coerce_theme_color_mode_tokens(self, raw_value):
        if isinstance(raw_value, (list, tuple)):
            values = list(raw_value)
        elif raw_value in (None, ''):
            values = []
        else:
            values = [raw_value]
        tokens = []
        for value in values:
            if value in (None, ''):
                continue
            token = str(value).strip().upper()
            if token:
                tokens.append(token)
        return tokens

    def _display_mode_from_theme_color_mode(self, raw_value):
        tokens = self._coerce_theme_color_mode_tokens(raw_value)
        if not tokens:
            return 'RGBA'
        for token in tokens:
            if token in ('P', 'PALETTE', 'INDEXED'):
                return 'P'
            if token in ('1', '1BIT', 'MONO', 'MONOCHROME'):
                return '1'
            if token == 'L':
                return 'L'
            if token == 'LA':
                return 'L'
            if token == 'RGB':
                return 'RGB'
            if token == 'RGBA':
                return 'RGBA'
        return 'RGBA'

    def _resolve_display_output_mode(self, theme_source=None):
        override = self._sanitize_display_output_mode(
            self.options.get('display_output_mode', self.DEFAULT_OPTIONS['display_output_mode']),
            self.DEFAULT_OPTIONS['display_output_mode'],
        )
        if override == 'rgba':
            return 'RGBA'
        if override == 'palette':
            return 'P'
        if override == '1bit':
            return '1'
        if override != 'theme':
            return 'RGBA'
        return self._display_mode_from_theme_color_mode(self._theme_declared_color_mode(theme_source))

    def _convert_frame_to_display_mode(self, frame, pil_mode):
        normalized_mode = str(pil_mode or 'RGBA').strip().upper()
        if normalized_mode == '1':
            return frame.convert('1')
        if normalized_mode == 'P':
            return frame.convert('P')
        if normalized_mode == 'L':
            return frame.convert('L')
        if normalized_mode == 'RGB':
            return frame.convert('RGB')
        return frame.convert('RGBA')

    def _theme_widgets(self, theme_source=None):
        if isinstance(theme_source, dict) and 'theme_bundle' in theme_source:
            bundle = theme_source.get('theme_bundle') or {}
        else:
            bundle = self._theme_bundle if theme_source is None else theme_source
        return bundle.get('theme', {}).get('widget', {})

    def _theme_stealth_mode(self, theme_source=None):
        options = self._theme_options(theme_source)
        return bool(options.get('stealth_mode', False))

    def _set_active_theme_stealth_mode(self, enabled):
        enabled = bool(enabled)
        theme_name = self._theme_name or self.options.get('theme') or 'Default'
        if theme_name == 'Default':
            self.options['default_stealth_mode'] = enabled
            self._persist_plugin_options()
            self._reload_theme_state()
            return

        theme_config = self._read_theme_config(theme_name) or {}
        theme_config.setdefault('theme', {}).setdefault('options', {})['stealth_mode'] = enabled
        resolved = self._resolve_theme_paths(theme_name)
        config_path = resolved['config'] or os.path.join(self._theme_path_for(theme_name), 'config.toml')
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        self._write_text_file(config_path, toml.dumps(theme_config))
        self._reload_theme_state()

    def _theme_asset_roots(self, theme_runtime=None):
        roots = []
        theme_path = self._theme_path if theme_runtime is None else theme_runtime.get('theme_path')
        if theme_path:
            roots.extend([
                theme_path,
                os.path.join(theme_path, 'img'),
                os.path.join(theme_path, 'img', 'bg'),
                os.path.join(theme_path, 'img', 'widgets'),
                os.path.join(theme_path, 'fonts'),
            ])
        return roots

    def _theme_asset_path(self, asset_name, folders=None, theme_runtime=None):
        if not asset_name:
            return None
        if os.path.isabs(asset_name) and os.path.exists(asset_name):
            return asset_name
        search_roots = []
        folders = folders or ['']
        for root in self._theme_asset_roots(theme_runtime):
            for folder in folders:
                search_roots.append(os.path.join(root, folder) if folder else root)
        for root in search_roots:
            candidate = os.path.join(root, asset_name)
            if os.path.exists(candidate):
                return candidate
        return None

    def _auto_asset_path(self, prefix, extensions, theme_runtime=None):
        theme_path = self._theme_path if theme_runtime is None else theme_runtime.get('theme_path')
        if not theme_path:
            return None
        resolution = self._current_resolution() or f"{self._canvas_size()[0]}x{self._canvas_size()[1]}"
        search_dir = self._theme_asset_path('', folders=['img/bg'], theme_runtime=theme_runtime) or os.path.join(theme_path, 'img', 'bg')
        if not os.path.isdir(search_dir):
            return None
        candidates = []
        for name in sorted(os.listdir(search_dir)):
            lowered = name.lower()
            if not lowered.endswith(tuple(ext.lower() for ext in extensions)):
                continue
            if lowered.startswith(f"{resolution}{prefix}".lower()) or lowered.startswith(prefix.lower()):
                candidates.append(os.path.join(search_dir, name))
        return candidates[0] if candidates else None

    def _font_name_to_path(self, font_name, theme_runtime=None):
        if not font_name:
            return None
        font_name = str(font_name)
        if os.path.isabs(font_name) and os.path.exists(font_name):
            return font_name
        if '.' in font_name:
            theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
            theme_path = theme_runtime.get('theme_path')
            if theme_path:
                return os.path.join(theme_path, 'fonts', font_name)
        return font_name

    def _setup_theme_fonts(self, theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        options = self._theme_options(theme_runtime)
        sizes = list(options.get('font_sizes', [14, 9, 14, 25, 19, 9]))
        while len(sizes) < 6:
            sizes.append(sizes[-1] if sizes else 12)
        role_sizes = {
            'Bold': int(sizes[0] or 14),
            'BoldSmall': int(sizes[1] or 9),
            'Medium': int(sizes[2] or 14),
            'Huge': int(sizes[3] or 25),
            'BoldBig': int(sizes[4] or 19),
            'Small': int(sizes[5] or 9),
        }
        theme_runtime['font_name'] = options.get('font') or 'DejaVuSansMono'
        theme_runtime['font_bold_name'] = options.get('font_bold') or theme_runtime['font_name']
        theme_runtime['font_status_name'] = options.get('status_font') or theme_runtime['font_name']
        theme_runtime['f_awesome_name'] = options.get('font_awesome') or ''
        theme_runtime['font_cache'] = {}
        theme_runtime['font_role_sizes'] = role_sizes
        theme_runtime['Small'] = self._get_font_from_name(theme_runtime['font_name'], role_sizes['Small'], theme_runtime=theme_runtime)
        theme_runtime['Medium'] = self._get_font_from_name(theme_runtime['font_name'], role_sizes['Medium'], theme_runtime=theme_runtime)
        theme_runtime['BoldSmall'] = self._get_font_from_name(theme_runtime['font_bold_name'], role_sizes['BoldSmall'], theme_runtime=theme_runtime)
        theme_runtime['Bold'] = self._get_font_from_name(theme_runtime['font_bold_name'], role_sizes['Bold'], theme_runtime=theme_runtime)
        theme_runtime['BoldBig'] = self._get_font_from_name(theme_runtime['font_bold_name'], role_sizes['BoldBig'], theme_runtime=theme_runtime)
        theme_runtime['Huge'] = self._get_font_from_name(theme_runtime['font_bold_name'], role_sizes['Huge'], theme_runtime=theme_runtime)

    def _get_font_from_name(self, font_name, size, theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        key = (font_name or '', int(size or 12))
        font_cache = theme_runtime.setdefault('font_cache', {})
        if key in font_cache:
            return font_cache[key]
        font = None
        resolved_font = None
        try:
            if font_name:
                resolved_font = self._font_name_to_path(font_name, theme_runtime=theme_runtime)
                font = ImageFont.truetype(resolved_font, int(size))
        except Exception as exc:
            logging.warning(
                f"[Refacer][font] load failed name={font_name} "
                f"resolved={resolved_font if resolved_font is not None else font_name} "
                f"size={int(size or 12)} error={exc}"
            )
            font = None
        if font is None:
            font = ImageFont.load_default()
        font_cache[key] = font
        return font

    def _font_role(self, role, theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        mapping = {
            'Small': theme_runtime.get('Small'),
            'Medium': theme_runtime.get('Medium'),
            'BoldSmall': theme_runtime.get('BoldSmall'),
            'Bold': theme_runtime.get('Bold'),
            'BoldBig': theme_runtime.get('BoldBig'),
            'Huge': theme_runtime.get('Huge'),
        }
        return mapping.get(role, theme_runtime.get('Medium') or ImageFont.load_default())

    def _resolve_font_size_spec(self, size_spec, fallback_role='Medium', theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        role_sizes = theme_runtime.get('font_role_sizes', {})
        if size_spec in (None, '', 0, '0'):
            return role_sizes.get(fallback_role, role_sizes.get('Medium', 14))
        if isinstance(size_spec, str):
            normalized = size_spec.strip()
            if normalized in role_sizes:
                return role_sizes[normalized]
            try:
                return max(1, int(float(normalized)))
            except ValueError:
                return role_sizes.get(fallback_role, role_sizes.get('Medium', 14))
        if isinstance(size_spec, (int, float)):
            return max(1, int(size_spec))
        return role_sizes.get(fallback_role, role_sizes.get('Medium', 14))

    def _theme_font_family_for(self, widget_state, field='text', theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        widget_key = widget_state.get('widget_key')
        role = widget_state.get(f'{field}_font_size', 'Medium') or 'Medium'
        if field == 'label':
            return theme_runtime.get('font_bold_name') or theme_runtime.get('font_name')
        if widget_key == 'status':
            return theme_runtime.get('font_status_name') or theme_runtime.get('font_name')
        if isinstance(role, str) and role.startswith('Bold'):
            return theme_runtime.get('font_bold_name') or theme_runtime.get('font_name')
        return theme_runtime.get('font_name')

    def _change_font(self, base_font, new_font=None, size_offset=None, theme_runtime=None, resolved_size=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        options = self._theme_options(theme_runtime)
        if base_font is None and resolved_size is None:
            return None
        font_name = new_font or options.get('status_font') or theme_runtime.get('font_status_name')
        offset = options.get('size_offset', 0) if size_offset is None else size_offset
        base_size = resolved_size if resolved_size is not None else getattr(base_font, 'size', 12)
        size = max(1, int(base_size + (offset or 0)))
        return self._get_font_from_name(font_name, size, theme_runtime=theme_runtime)

    def _load_image_asset(self, asset_name, folders=None, theme_runtime=None):
        if not asset_name:
            return None
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        path = self._theme_asset_path(asset_name, folders=folders, theme_runtime=theme_runtime)
        if not path:
            return None
        cache_key = ('image', path)
        asset_cache = theme_runtime.setdefault('asset_cache', {})
        if cache_key in asset_cache:
            cached = asset_cache[cache_key]
            return cached.copy() if isinstance(cached, Image.Image) else cached
        try:
            image = Image.open(path).convert('RGBA')
            asset_cache[cache_key] = image.copy()
            return image
        except Exception as exc:
            logging.error(f"[Refacer][render] image load failed path={path} error={exc}")
            return None

    def _load_animated_asset(self, asset_name, mode, theme_runtime=None, bg_color=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        path = self._theme_asset_path(asset_name, folders=['img/bg', 'img', ''], theme_runtime=theme_runtime)
        if not path:
            return []
        bg_color = self._normalize_color(bg_color or 'white')
        cache_key = ('anim', path, mode, self._canvas_size(), bg_color)
        asset_cache = theme_runtime.setdefault('asset_cache', {})
        if cache_key in asset_cache:
            return [frame.copy() for frame in asset_cache[cache_key]]
        frames = []
        try:
            width, height = self._canvas_size()
            base = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            accumulator = Image.new('RGBA', (width, height), bg_color)
            with Image.open(path) as gif:
                for frame in ImageSequence.Iterator(gif):
                    disposal = frame.info.get('disposal', 0)
                    prepared = self._image_mode(base, frame.convert('RGBA'), mode)
                    if prepared is None:
                        continue
                    if disposal == 2:
                        accumulator = Image.new('RGBA', (width, height), bg_color)
                    accumulator.alpha_composite(prepared)
                    flat = Image.new('RGBA', (width, height), bg_color)
                    flat.alpha_composite(accumulator)
                    frames.append(flat)
        except Exception as exc:
            logging.error(f"[Refacer][render] animated asset load failed path={path} error={exc}")
            frames = []
        asset_cache[cache_key] = [frame.copy() for frame in frames]
        return frames

    def _load_theme_assets(self, theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        self._setup_theme_fonts(theme_runtime)
        options = self._theme_options(theme_runtime)
        width, height = self._canvas_size()
        canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        assets = {'background': None, 'foreground': None, 'animated_background': []}
        bg_name = options.get('bg_image')
        fg_name = options.get('fg_image')
        anim_name = options.get('bg_anim_image')
        if options.get('bg_fg_select', 'manu') == 'auto':
            bg_name = bg_name or self._auto_asset_path('bg', ('.png', '.jpg', '.jpeg', '.bmp'), theme_runtime=theme_runtime)
            fg_name = fg_name or self._auto_asset_path('fg', ('.png', '.jpg', '.jpeg', '.bmp'), theme_runtime=theme_runtime)
        bg_asset = self._load_image_asset(bg_name, folders=['img/bg', 'img', ''], theme_runtime=theme_runtime) if bg_name else None
        fg_asset = self._load_image_asset(fg_name, folders=['img/bg', 'img', ''], theme_runtime=theme_runtime) if fg_name else None
        if bg_asset is not None:
            assets['background'] = self._image_mode(canvas, bg_asset, options.get('bg_mode', 'normal'))
        if fg_asset is not None:
            assets['foreground'] = self._image_mode(canvas, fg_asset, options.get('fg_mode', 'normal'))
        # Animation is explicit for the base compositor contract; do not infer it from the asset folder.
        if options.get('bg_anim_image'):
            assets['animated_background'] = self._load_animated_asset(
                anim_name,
                options.get('bg_mode', 'normal'),
                theme_runtime=theme_runtime,
                bg_color=options.get('bg_color') or 'white',
            )
        logging.debug(
            f"[Refacer][render] assets theme={theme_runtime.get('theme_name', self._theme_name)} "
            f"bg={'yes' if assets['background'] is not None else 'no'} "
            f"bga={len(assets['animated_background'])} "
            f"fg={'yes' if assets['foreground'] is not None else 'no'} "
            f"bg_mode={options.get('bg_mode', 'normal')} "
            f"fg_mode={options.get('fg_mode', 'normal')} "
            f"font={theme_runtime.get('font_name')} bold={theme_runtime.get('font_bold_name')} awesome={theme_runtime.get('f_awesome_name') or 'none'}"
        )
        return assets

    def _display_enabled(self):
        try:
            config = self._plugin_config()
            return bool(config.get('ui', {}).get('display', {}).get('enabled', False))
        except Exception:
            return False

    def _boot_animation_source_path(self, theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        theme_path = theme_runtime.get('theme_path')
        if not theme_path:
            return None

        boot_dir = os.path.join(theme_path, 'img', 'boot')
        if os.path.isdir(boot_dir):
            entries = [
                name for name in sorted(os.listdir(boot_dir))
                if os.path.isfile(os.path.join(boot_dir, name))
                and os.path.splitext(name)[1].lower() in self.BOOT_ALLOWED_IMAGE_EXTS
            ]
            if entries:
                return boot_dir

        options = self._theme_options(theme_runtime)
        anim_name = options.get('bg_anim_image')
        if anim_name:
            anim_path = self._theme_asset_path(anim_name, folders=['img/bg', 'img', ''], theme_runtime=theme_runtime)
            if anim_path and os.path.exists(anim_path):
                return anim_path
        return None

    def _boot_animation_config(self, theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        options = self._theme_options(theme_runtime)
        if options.get('boot_animation') is not True:
            return None

        source_path = self._boot_animation_source_path(theme_runtime=theme_runtime)
        if not source_path:
            logging.warning(
                f"[Refacer][boot] no boot source found for theme={theme_runtime.get('theme_name', self._theme_name)} "
                f"boot_dir={os.path.join(theme_runtime.get('theme_path') or '', 'img', 'boot')} "
                f"bg_anim_image={options.get('bg_anim_image') or ''}"
            )
            return None

        boot_mode = str(options.get('boot_mode') or options.get('bg_mode') or 'stretch').strip().lower()
        if boot_mode not in self.BOOT_ALLOWED_MODES:
            boot_mode = str(options.get('bg_mode') or 'stretch').strip().lower()
        if boot_mode not in self.BOOT_ALLOWED_MODES:
            boot_mode = 'stretch'

        return {
            'source_path': source_path,
            'mode': boot_mode,
            'bg_color': options.get('boot_bg_color') or options.get('bg_color') or 'white',
            'max_loops': self._sanitize_int(options.get('boot_max_loops'), 1, minimum=1),
            'total_duration': self._sanitize_int(
                options.get('boot_total_duration'),
                self.BOOT_DEFAULT_DURATION,
                minimum=1,
            ),
            'theme_name': str(theme_runtime.get('theme_name') or self._theme_name or 'Default'),
        }

    # ------------------------------------------------------------------ cache

    _BOOT_CACHE_SCHEMA = 2

    def _boot_anim_cache_dir(self, config):
        """Return the cache directory path for the given boot-animation config."""
        theme_name = str(config.get('theme_name') or 'Default')
        width, height = self._canvas_size()
        rotation = self._current_rotation()
        boot_mode = str(config.get('mode') or 'stretch').strip().lower()
        slot = f"{rotation}_{width}x{height}_{boot_mode}"
        return os.path.join(self._plug_root, '.boot_anim_cache', theme_name, slot)

    def _boot_anim_source_hash(self, source_path):
        """SHA-1 of file mtimes + sizes for the source path (file or dir)."""
        h = hashlib.sha1()
        if os.path.isdir(source_path):
            for name in sorted(os.listdir(source_path)):
                child = os.path.join(source_path, name)
                if os.path.isfile(child) and os.path.splitext(child)[1].lower() in self.BOOT_ALLOWED_IMAGE_EXTS:
                    st = os.stat(child)
                    h.update(f"{name}:{st.st_mtime}:{st.st_size}".encode())
        elif os.path.isfile(source_path):
            st = os.stat(source_path)
            h.update(f"{os.path.basename(source_path)}:{st.st_mtime}:{st.st_size}".encode())
        return h.hexdigest()

    def _prepare_boot_animation_cache(self, theme_runtime=None):
        """Pre-render boot frames to disk so on_loaded can load them without compositing."""
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        config = self._boot_animation_config(theme_runtime=theme_runtime)
        if config is None:
            return False

        cache_dir = self._boot_anim_cache_dir(config)
        manifest_path = os.path.join(cache_dir, 'manifest.json')

        source_path = config.get('source_path')
        if source_path:
            try:
                source_hash = self._boot_anim_source_hash(source_path)
            except Exception:
                source_hash = ''
        else:
            source_hash = ''

        # Check if cache is already valid.
        if os.path.isdir(cache_dir) and os.path.isfile(manifest_path):
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                if (manifest.get('schema') == self._BOOT_CACHE_SCHEMA
                        and manifest.get('source_hash') == source_hash
                        and manifest.get('frame_count', 0) > 0):
                    existing = [
                        n for n in sorted(os.listdir(cache_dir))
                        if n.startswith('frame_') and n.endswith('.png')
                    ]
                    if len(existing) == manifest['frame_count']:
                        logging.debug(
                            f"[Refacer][boot-cache] cache valid, skipping render "
                            f"theme={config.get('theme_name')} dir={cache_dir}"
                        )
                        return True
            except Exception:
                pass

        # Build source file list.
        source_files = []
        if source_path and os.path.isdir(source_path):
            for name in sorted(os.listdir(source_path)):
                child = os.path.join(source_path, name)
                if os.path.isfile(child) and os.path.splitext(child)[1].lower() in self.BOOT_ALLOWED_IMAGE_EXTS:
                    source_files.append(child)
        elif source_path and os.path.isfile(source_path):
            source_files.append(source_path)

        if not source_files:
            logging.warning(
                f"[Refacer][boot-cache] no source files theme={config.get('theme_name')}"
            )
            return False

        width, height = self._canvas_size()
        boot_mode = str(config.get('mode') or 'stretch').strip().lower()
        bg_color = self._normalize_color(config.get('bg_color') or 'white')
        base_canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        prepared_frames = []

        try:
            for source_file in source_files:
                with Image.open(source_file) as image:
                    frames = [frame.copy().convert('RGBA') for frame in ImageSequence.Iterator(image)]
                    if not frames:
                        frames = [image.convert('RGBA')]
                for frame in frames:
                    prepared = self._image_mode(base_canvas, frame.convert('RGBA'), boot_mode)
                    if prepared is None:
                        continue
                    alpha = prepared.getchannel('A') if 'A' in prepared.getbands() else None
                    if alpha is None or alpha.getbbox() is None:
                        continue
                    visible = sum(alpha.histogram()[8:])
                    total = max(1, prepared.size[0] * prepared.size[1])
                    if (float(visible) / float(total)) < 0.002:
                        continue
                    # Composite each frame onto a fresh background to prevent overlapping transparency/ghosting.
                    flattened = Image.new('RGBA', (width, height), bg_color)
                    flattened.alpha_composite(prepared)
                    prepared_frames.append(flattened)
        except Exception as exc:
            logging.warning(f"[Refacer][boot-cache] compositing failed: {exc}")
            return False

        if not prepared_frames:
            logging.warning(
                f"[Refacer][boot-cache] no prepared frames theme={config.get('theme_name')}"
            )
            return False

        total_loops = max(1, int(config.get('max_loops') or 1))
        total_duration = max(1.0, float(config.get('total_duration') or self.BOOT_DEFAULT_DURATION))
        delay = max(0.02, total_duration / float(max(1, len(prepared_frames))))

        # Atomically write to a temp dir then rename.
        tmp_dir = cache_dir + '.tmp'
        try:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)
            os.makedirs(tmp_dir, exist_ok=True)
            for idx, frame in enumerate(prepared_frames):
                frame.save(os.path.join(tmp_dir, f'frame_{idx:04d}.png'))
            manifest = {
                'schema': self._BOOT_CACHE_SCHEMA,
                'frame_count': len(prepared_frames),
                'delay': delay,
                'total_loops': total_loops,
                'total_duration': total_duration,
                'bg_color': list(bg_color) if isinstance(bg_color, tuple) else bg_color,
                'source_hash': source_hash,
            }
            with open(os.path.join(tmp_dir, 'manifest.json'), 'w') as f:
                json.dump(manifest, f)
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
            os.rename(tmp_dir, cache_dir)
        except Exception as exc:
            logging.warning(f"[Refacer][boot-cache] failed writing cache: {exc}")
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
            return False

        logging.info(
            f"[Refacer][boot-cache] cache written theme={config.get('theme_name')} "
            f"frames={len(prepared_frames)} delay={delay:.3f}s dir={cache_dir}"
        )
        return True

    def _invalidate_boot_animation_cache(self, theme_name=None):
        """Remove cached frames for a theme (or all themes if theme_name is None)."""
        base = os.path.join(self._plug_root, '.boot_anim_cache')
        if not os.path.isdir(base):
            return
        if theme_name:
            target = os.path.join(base, str(theme_name))
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
                logging.debug(f"[Refacer][boot-cache] invalidated cache for theme={theme_name}")
        else:
            shutil.rmtree(base, ignore_errors=True)
            logging.debug("[Refacer][boot-cache] invalidated all boot animation caches")

    # ------------------------------------------------------------------ runtime loader

    def _maybe_play_boot_animation(self, trigger, theme_runtime=None):
        """Fire the boot animation only if the user enabled it for this trigger.

        trigger: 'startup', 'theme_switch', or 'manual'.
        'manual' always plays regardless of user flags — used by the editor's
        "Test Boot Animation" button (editor/test_boot_animation endpoint).
        """
        if trigger == 'manual':
            pass
        elif trigger == 'startup':
            if not self.options.get('boot_animation_on_startup', True):
                logging.debug("[Refacer][boot] startup trigger disabled by user option")
                return False
        elif trigger == 'theme_switch':
            if not self.options.get('boot_animation_on_theme_switch', False):
                logging.debug("[Refacer][boot] theme-switch trigger disabled by user option")
                return False
        else:
            logging.warning(f"[Refacer][boot] unknown trigger={trigger}, skipping")
            return False
        if self._display_control_is_enabled() and not self._display_hardware_publish_allowed():
            self.display_on(reason='boot_animation')
        return self._prepare_startup_boot_animation_runtime(theme_runtime=theme_runtime)

    def _prepare_startup_boot_animation_runtime(self, theme_runtime=None):
        """Return immediately after launching a background load thread. Never blocks."""
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        self._boot_anim_enabled = False
        self._boot_anim_done = True
        self._boot_anim_started_ts = None
        self._boot_anim_last_frame_ts = None
        self._boot_anim_loop_index = 0
        self._boot_anim_frame_index = 0
        self._boot_anim_delay_s = 0.0
        self._boot_anim_frames = []
        self._boot_anim_total_loops = 0
        self._boot_anim_total_duration = 0.0
        self._boot_anim_bg_color = None
        self._boot_anim_first_frame_published = True
        self._boot_anim_loading = False

        config = self._boot_animation_config(theme_runtime=theme_runtime)
        if config is None:
            logging.info("[Refacer][boot] startup boot animation disabled for current theme")
            return False

        self._boot_anim_loading = True
        self._boot_anim_done = False
        t = threading.Thread(
            target=self._load_boot_animation_frames_async,
            args=(config,),
            daemon=True,
        )
        self._boot_anim_load_thread = t
        t.start()
        logging.debug(
            f"[Refacer][boot] async frame load started theme={config.get('theme_name')}"
        )
        return True

    def _load_boot_animation_frames_async(self, config):
        """Background thread: load or composite frames, then atomically install them."""
        theme_name = config.get('theme_name', 'unknown')
        cache_dir = self._boot_anim_cache_dir(config)
        manifest_path = os.path.join(cache_dir, 'manifest.json')
        loaded_frames = None
        total_loops = 1
        total_duration = float(self.BOOT_DEFAULT_DURATION)
        delay = 0.1
        bg_color = (255, 255, 255, 255)

        # Fast path: cache hit.
        if os.path.isdir(cache_dir) and os.path.isfile(manifest_path):
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                if manifest.get('schema') != self._BOOT_CACHE_SCHEMA:
                    raise ValueError(f"schema mismatch: {manifest.get('schema')} != {self._BOOT_CACHE_SCHEMA}")
                frame_count = int(manifest['frame_count'])
                frame_files = sorted(
                    n for n in os.listdir(cache_dir)
                    if n.startswith('frame_') and n.endswith('.png')
                )
                if len(frame_files) != frame_count:
                    raise ValueError(f"frame count mismatch: {len(frame_files)} != {frame_count}")
                frames = []
                for name in frame_files:
                    img = Image.open(os.path.join(cache_dir, name)).convert('RGBA')
                    img.load()
                    frames.append(img)
                bg_raw = manifest.get('bg_color', (255, 255, 255, 255))
                bg_color = tuple(bg_raw) if isinstance(bg_raw, list) else bg_raw
                total_loops = int(manifest['total_loops'])
                total_duration = float(manifest['total_duration'])
                delay = float(manifest['delay'])
                loaded_frames = frames
                logging.info(
                    f"[Refacer][boot] async load from cache theme={theme_name} "
                    f"frames={frame_count} delay={delay:.3f}s"
                )
            except Exception as exc:
                logging.warning(
                    f"[Refacer][boot] async cache load failed, falling back to compositing: {exc}"
                )

        # Slow fallback: composite in-place.
        if loaded_frames is None:
            width, height = self._canvas_size()
            source_path = config.get('source_path')
            source_files = []
            if source_path and os.path.isdir(source_path):
                for name in sorted(os.listdir(source_path)):
                    child = os.path.join(source_path, name)
                    if os.path.isfile(child) and os.path.splitext(child)[1].lower() in self.BOOT_ALLOWED_IMAGE_EXTS:
                        source_files.append(child)
            elif source_path and os.path.isfile(source_path):
                source_files.append(source_path)

            if not source_files:
                logging.warning(
                    f"[Refacer][boot] async load: no source files theme={theme_name}"
                )
                with self._lock:
                    self._boot_anim_loading = False
                    self._boot_anim_done = True
                return

            boot_mode = str(config.get('mode') or 'stretch').strip().lower()
            bg_color = self._normalize_color(config.get('bg_color') or 'white')
            prepared_frames = []
            base_canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))

            try:
                for source_file in source_files:
                    with Image.open(source_file) as image:
                        frames = [frame.copy().convert('RGBA') for frame in ImageSequence.Iterator(image)]
                        if not frames:
                            frames = [image.convert('RGBA')]
                    for frame in frames:
                        prepared = self._image_mode(base_canvas, frame.convert('RGBA'), boot_mode)
                        if prepared is None:
                            continue
                        alpha = prepared.getchannel('A') if 'A' in prepared.getbands() else None
                        if alpha is None or alpha.getbbox() is None:
                            continue
                        visible = sum(alpha.histogram()[8:])
                        total = max(1, prepared.size[0] * prepared.size[1])
                        if (float(visible) / float(total)) < 0.002:
                            continue
                        # Composite each frame onto a fresh background to prevent overlapping transparency/ghosting.
                        flattened = Image.new('RGBA', (width, height), bg_color)
                        flattened.alpha_composite(prepared)
                        prepared_frames.append(flattened)
            except Exception as exc:
                logging.warning(f"[Refacer][boot] async compositing failed: {exc}")
                with self._lock:
                    self._boot_anim_loading = False
                    self._boot_anim_done = True
                return

            if not prepared_frames:
                logging.warning(
                    f"[Refacer][boot] async load: no prepared frames theme={theme_name}"
                )
                with self._lock:
                    self._boot_anim_loading = False
                    self._boot_anim_done = True
                return

            total_loops = max(1, int(config.get('max_loops') or 1))
            total_duration = max(1.0, float(config.get('total_duration') or self.BOOT_DEFAULT_DURATION))
            delay = max(0.02, total_duration / float(max(1, len(prepared_frames))))
            loaded_frames = prepared_frames
            logging.info(
                f"[Refacer][boot] async compositing done theme={theme_name} "
                f"frames={len(loaded_frames)} delay={delay:.3f}s"
            )

        # Atomically install frames; reset timing so animation starts from the first post-load tick.
        with self._lock:
            self._boot_anim_frames = loaded_frames
            self._boot_anim_total_loops = total_loops
            self._boot_anim_total_duration = total_duration
            self._boot_anim_delay_s = delay
            self._boot_anim_bg_color = bg_color
            self._boot_anim_enabled = True
            self._boot_anim_loading = False
            self._boot_anim_started_ts = None

    def _startup_boot_animation_active(self):
        return bool(
            self._boot_anim_loading
            or (self._boot_anim_enabled and not self._boot_anim_done and self._boot_anim_frames)
        )

    def _publish_startup_boot_frame_immediately(self, view_instance=None, theme_runtime=None):
        if not self._startup_boot_animation_active():
            return False
        if self._boot_anim_first_frame_published:
            return False

        view_instance = view_instance or self._view_instance
        if view_instance is None:
            return False

        frame = self._boot_anim_frames[0].copy().convert('RGBA')
        now = time.monotonic()
        if self._boot_anim_started_ts is None:
            self._boot_anim_started_ts = now
        if self._boot_anim_last_frame_ts is None:
            self._boot_anim_last_frame_ts = now
        self._boot_anim_frame_index = 0

        self._view_instance = view_instance
        self._last_render_canvas = frame.copy()
        view_instance._refacer_web_canvas = frame.copy()
        self._publish_final_frame(frame, 0)
        self._boot_anim_first_frame_published = True
        logging.debug("[Refacer][boot] startup boot frame 0 published immediately on takeover")
        return True

    def _render_startup_boot_animation_frame(self, canvas, now=None, theme_runtime=None):
        if not self._startup_boot_animation_active():
            return False

        # Frames still loading — render solid black and hold.
        if self._boot_anim_loading and not self._boot_anim_frames:
            canvas.alpha_composite(Image.new('RGBA', canvas.size, (0, 0, 0, 255)))
            return True

        now = float(now if now is not None else time.monotonic())
        # First tick after frames arrive — start timing from now.
        if self._boot_anim_started_ts is None:
            self._boot_anim_started_ts = now
            self._boot_anim_last_frame_ts = now

        delay = max(0.02, float(self._boot_anim_delay_s or 0.02))
        while (
            self._startup_boot_animation_active()
            and self._boot_anim_last_frame_ts is not None
            and (now - self._boot_anim_last_frame_ts) >= delay
        ):
            self._boot_anim_last_frame_ts += delay
            self._boot_anim_frame_index += 1
            if self._boot_anim_frame_index >= len(self._boot_anim_frames):
                self._boot_anim_frame_index = 0
                self._boot_anim_loop_index += 1
                if self._boot_anim_loop_index >= self._boot_anim_total_loops:
                    self._boot_anim_done = True
                    break

        if not self._startup_boot_animation_active():
            logging.info("[Refacer][boot] startup boot animation complete")
            return False

        frame = self._boot_anim_frames[self._boot_anim_frame_index].convert('RGBA')
        canvas.paste(frame, (0, 0))
        return True

    def _is_valid_color_value(self, color):
        if color is None or color == '':
            return False
        if isinstance(color, (tuple, list)):
            if len(color) == 1:
                return self._is_valid_color_value(color[0])
            if len(color) not in (3, 4):
                return False
            return all(isinstance(channel, (int, float)) for channel in color)
        if isinstance(color, str):
            try:
                ImageColor.getrgb(color)
                return True
            except ValueError:
                return False
        return isinstance(color, (int, float))

    def _sanitize_theme_bundle(self, theme_bundle):
        theme = self._deep_merge(self.DEFAULT_THEME_MODEL, theme_bundle or {})
        fallback_used = False
        options = theme.get('theme', {}).get('options', {})
        bg_color = options.get('bg_color')
        if bg_color not in (None, '') and not self._is_valid_color_value(bg_color):
            options['bg_color'] = 'white'
            fallback_used = True
        widgets = theme.get('theme', {}).get('widget', {})
        for key, widget in list(widgets.items()):
            if not isinstance(widget, dict):
                widgets[key] = {}
                fallback_used = True
                continue
            if 'color' in widget:
                colors = widget.get('color')
                if not isinstance(colors, list):
                    colors = [colors]
                filtered = [value for value in colors if self._is_valid_color_value(value)]
                if filtered:
                    widget['color'] = filtered
                else:
                    widget.pop('color', None)
                    fallback_used = True

        bg_mode = options.get('bg_mode')
        if bg_mode in (None, ''):
            options['bg_mode'] = 'normal'
        elif str(bg_mode).strip().lower() not in self.BOOT_ALLOWED_MODES:
            options['bg_mode'] = 'normal'
            fallback_used = True
        else:
            options['bg_mode'] = str(bg_mode).strip().lower()

        boot_mode = options.get('boot_mode')
        if boot_mode in (None, ''):
            options['boot_mode'] = options.get('bg_mode', 'stretch')
        elif str(boot_mode).strip().lower() not in self.BOOT_ALLOWED_MODES:
            options['boot_mode'] = options.get('bg_mode', 'stretch')
            fallback_used = True
        else:
            options['boot_mode'] = str(boot_mode).strip().lower()
        if str(options.get('boot_mode') or '').strip().lower() not in self.BOOT_ALLOWED_MODES:
            options['boot_mode'] = 'stretch'
            fallback_used = True

        options['boot_animation'] = options.get('boot_animation') is True
        if options.get('boot_bg_color') in (None, ''):
            options['boot_bg_color'] = options.get('bg_color', 'white')
        options['boot_max_loops'] = self._sanitize_int(options.get('boot_max_loops'), 1, minimum=1)
        options['boot_total_duration'] = self._sanitize_int(
            options.get('boot_total_duration'),
            self.BOOT_DEFAULT_DURATION,
            minimum=1,
        )
        self._theme_fallback_notice = "Theme applied with readability fallback." if fallback_used else None
        return theme

    def _relative_luminance(self, rgba):
        r, g, b = [max(0.0, min(255.0, float(channel))) / 255.0 for channel in rgba[:3]]
        def channel_luminance(value):
            return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
        return 0.2126 * channel_luminance(r) + 0.7152 * channel_luminance(g) + 0.0722 * channel_luminance(b)

    def _contrast_ratio(self, color_a, color_b):
        lum_a = self._relative_luminance(color_a)
        lum_b = self._relative_luminance(color_b)
        lighter = max(lum_a, lum_b)
        darker = min(lum_a, lum_b)
        return (lighter + 0.05) / (darker + 0.05)

    def _safe_contrast_color(self, bg_rgba):
        return (255, 255, 255, 255) if self._relative_luminance(bg_rgba) < 0.35 else (0, 0, 0, 255)

    def _resolve_render_palette(self, theme_bundle, theme_name=None):
        options = theme_bundle.get('theme', {}).get('options', {}) if isinstance(theme_bundle, dict) else {}
        raw_bg = options.get('bg_color', getattr(self._view_instance, '_backgroundcolor', 255))
        bg_rgba = self._normalize_color(raw_bg)
        main_colors = [self._normalize_color(value) for value in options.get('main_text_color', []) if self._is_valid_color_value(value)]
        base_colors = [self._normalize_color(value) for value in options.get('base_text_color', []) if self._is_valid_color_value(value)]
        safe_fg = main_colors[0] if main_colors else (base_colors[0] if base_colors else self._safe_contrast_color(bg_rgba))
        fallback_used = False

        if self._contrast_ratio(bg_rgba, safe_fg) < 2.5:
            safe_fg = self._safe_contrast_color(bg_rgba)
            fallback_used = True

        if bg_rgba[:3] == safe_fg[:3]:
            safe_fg = self._safe_contrast_color(bg_rgba)
            fallback_used = True

        palette = {
            'theme': theme_name or self._theme_name,
            'raw_background': raw_bg,
            'normalized_background': bg_rgba,
            'default_foreground': safe_fg,
            'fallback_triggered': fallback_used,
            'sample_widget_colors': [],
            'theme_options': {
                'bg_mode': options.get('bg_mode', 'normal'),
                'fg_mode': options.get('fg_mode', 'normal'),
                'bg_image': options.get('bg_image', ''),
                'bg_anim_image': options.get('bg_anim_image', ''),
                'fg_image': options.get('fg_image', ''),
                'main_text_color': options.get('main_text_color', []),
                'base_text_color': options.get('base_text_color', []),
            },
            'resolved_main_text_colors': [list(color) for color in main_colors],
            'resolved_base_text_colors': [list(color) for color in base_colors],
        }
        return palette

    def _preview_frame_response(self):
        canvas = self._last_render_canvas.copy() if self._last_render_canvas is not None else None
        if canvas is None and self._view_instance is not None:
            canvas = getattr(self._view_instance, '_refacer_web_canvas', None)
            if canvas is not None:
                canvas = canvas.copy()
        if canvas is None:
            placeholder = Image.new('RGBA', (1, 1), (255, 255, 255, 255))
            buffer = BytesIO()
            placeholder.save(buffer, format='PNG')
            buffer.seek(0)
            return send_file(buffer, mimetype='image/png')
        buffer = BytesIO()
        canvas.save(buffer, format='PNG')
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')

    def _editor_preview_url(self, theme_name=None):
        theme = quote(str(theme_name or self._editor_draft_theme_name or self._theme_name or 'Default'))
        return f"debug/editor_preview_frame?theme={theme}&_ts={int(time.time() * 1000)}"

    def _editor_preview_frame_response(self, theme_name=None):
        canvas = self._render_editor_preview_canvas(theme_name)
        if canvas is None:
            placeholder = Image.new('RGBA', (1, 1), (255, 255, 255, 255))
            buffer = BytesIO()
            placeholder.save(buffer, format='PNG')
            buffer.seek(0)
            return send_file(buffer, mimetype='image/png')
        buffer = BytesIO()
        canvas.save(buffer, format='PNG')
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')

    def _editor_runtime_theme_bundle(self, theme_name=None):
        requested_theme = theme_name or self._theme_name or 'Default'
        if self._editor_draft_bundle is None or self._editor_draft_theme_name != requested_theme:
            self._reset_editor_draft(requested_theme)
        return copy.deepcopy(self._editor_draft_bundle or self._theme_bundle)

    def _editor_font_size_choices(self):
        return ('Small', 'Medium', 'BoldSmall', 'Bold', 'BoldBig', 'Huge')

    def _sanitize_editor_position_value(self, value):
        if isinstance(value, (list, tuple)):
            cleaned = []
            for item in value:
                if item in (None, ''):
                    continue
                text = str(item).strip()
                if text == '':
                    continue
                try:
                    cleaned.append(int(text))
                except (TypeError, ValueError):
                    cleaned.append(text)
            return cleaned or None
        text = '' if value is None else str(value).strip()
        if text == '':
            return None
        parts = [part.strip() for part in text.split(',')]
        cleaned = []
        for part in parts:
            if part == '':
                continue
            try:
                cleaned.append(int(part))
            except (TypeError, ValueError):
                cleaned.append(part)
        return cleaned or None

    def _sanitize_editor_dimension_value(self, value):
        if value in (None, '', 'None'):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _sanitize_editor_float_value(self, value):
        if value in (None, '', 'None'):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _sanitize_editor_string_value(self, value):
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    def _sanitize_editor_label_value(self, value):
        if value is None:
            return None
        # Preserve a blank label as an explicit "no label" override instead of
        # dropping back to the live widget label on the next snapshot.
        return str(value).strip()

    def _sanitize_editor_crop_value(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, str):
            parts = [p.strip() for p in re.split(r'[\s,;]+', value) if p.strip()]
        elif isinstance(value, (list, tuple)):
            parts = list(value)
        else:
            return None
        if len(parts) != 4:
            return None
        out = []
        for p in parts:
            try:
                out.append(int(p))
            except (TypeError, ValueError):
                return None
        return out

    def _sanitize_editor_color_value(self, value):
        if isinstance(value, (list, tuple)):
            values = []
            for item in value:
                text = '' if item is None else str(item)
                parts = re.split(r'[\r\n,;]+', text)
                values.extend(part.strip() for part in parts if part.strip())
            return values or None
        text = '' if value is None else str(value).strip()
        if text == '':
            return None
        parts = [part.strip() for part in re.split(r'[\r\n,;]+', text) if part.strip()]
        return parts or None

    def _editor_color_preview_css(self, value):
        try:
            return ImageColor.getrgb(str(value))
        except Exception:
            return None

    def _normalize_editor_widget_patch(self, widget_key, patch_dict):
        _allowed_image_types = ('png', 'jpg', 'jpeg', 'bmp', 'gif', 'webp')
        normalized = {}
        for key, value in (patch_dict or {}).items():
            if key == 'position':
                normalized[key] = self._sanitize_editor_position_value(value)
            elif key == 'color':
                normalized[key] = self._sanitize_editor_color_value(value)
            elif key in ('text_font_size', 'label_font_size'):
                text = '' if value is None else str(value).strip()
                normalized[key] = text if text in self._editor_font_size_choices() else None
            elif key in ('z_axis', 'max_length', 'width', 'height'):
                normalized[key] = self._sanitize_editor_dimension_value(value)
            elif key == 'wrap':
                normalized[key] = bool(value)
            elif key in ('size_offset', 'label_spacing', 'label_line_spacing', 'font_spacing', 'refine', 'f_awesome_size'):
                normalized[key] = self._sanitize_editor_dimension_value(value)
            elif key == 'zoom':
                normalized[key] = self._sanitize_editor_float_value(value)
            elif key in ('invert', 'alpha', 'icon_color', 'mask'):
                normalized[key] = bool(value)
            elif key in ('text_font', 'label_font'):
                normalized[key] = self._sanitize_editor_string_value(value)
            elif key == 'label':
                normalized[key] = self._sanitize_editor_label_value(value)
            elif key == 'image_type':
                text = (value or '').strip().lower()
                normalized[key] = text if text in _allowed_image_types else None
            elif key == 'crop':
                normalized[key] = self._sanitize_editor_crop_value(value)
            elif key in ('icon', 'f_awesome'):
                if value in (False, None, '', 'false', 'False'):
                    normalized[key] = False
                else:
                    text = str(value).strip()
                    normalized[key] = text if text else False
        return normalized

    def _extract_widget_editable_fields(self, widget_key, runtime_state, theme_bundle):
        widget_type = runtime_state.get('widget_type', 'Text')
        schema = copy.deepcopy(
            self.WIDGET_DEFAULTS.get(widget_type, self.WIDGET_DEFAULTS['Text'])
        )
        color_value = runtime_state.get('color') or []
        if not isinstance(color_value, list):
            color_value = [color_value]
        position = runtime_state.get('position') or []
        editable = {
            'widget_type': widget_type,
            'position': self._editor_serialize_sequence(position),
            'position_mode': len(position),
            'color': [str(v) for v in self._editor_serialize_sequence(color_value) if str(v).strip()],
        }
        for key, default in schema.items():
            if key in self._WIDGET_RUNTIME_ONLY_FIELDS:
                continue
            if key in ('position', 'color'):
                continue
            raw = runtime_state.get(key, default)
            editable[key] = raw
        return editable

    def _reset_editor_draft(self, theme_name=None):
        requested_theme = theme_name or self._theme_name or 'Default'
        if requested_theme == self._theme_name:
            bundle = copy.deepcopy(self._theme_bundle)
        else:
            bundle = self._sanitize_theme_bundle(self._theme_bundle_from_config(self._read_theme_config(requested_theme)))
        self._editor_draft_theme_name = requested_theme
        self._editor_draft_bundle = bundle
        self._editor_draft_dirty = False
        self._editor_selected_widget_key = None
        return bundle

    def _get_editor_theme_bundle(self, theme_name=None):
        requested_theme = theme_name or self._theme_name or 'Default'
        if self._editor_draft_bundle is None or self._editor_draft_theme_name != requested_theme:
            return self._reset_editor_draft(requested_theme)
        return self._editor_draft_bundle

    def _update_editor_widget_draft(self, widget_key, patch_dict, theme_name=None):
        if not widget_key:
            raise ValueError('Missing widget key.')
        bundle = copy.deepcopy(self._get_editor_theme_bundle(theme_name))
        widgets = bundle.setdefault('theme', {}).setdefault('widget', {})
        widget_config = copy.deepcopy(widgets.get(widget_key, {}))
        for key, value in self._normalize_editor_widget_patch(widget_key, patch_dict).items():
            if value is None:
                widget_config.pop(key, None)
            else:
                widget_config[key] = value
        widgets[widget_key] = widget_config
        self._editor_draft_bundle = self._sanitize_theme_bundle(bundle)
        self._editor_draft_theme_name = theme_name or self._theme_name or 'Default'
        self._editor_draft_dirty = True
        self._editor_selected_widget_key = widget_key
        return self._editor_draft_bundle

    def _update_editor_global_options_draft(self, options_patch, dev_patch=None, theme_name=None):
        requested_theme = theme_name or self._theme_name or 'Default'
        if requested_theme == 'Default':
            raise ValueError('Default theme global options cannot be modified from the editor.')
        bundle = copy.deepcopy(self._get_editor_theme_bundle(requested_theme))
        theme_section = bundle.setdefault('theme', {})
        if options_patch and isinstance(options_patch, dict):
            opts = theme_section.setdefault('options', {})
            for k, v in options_patch.items():
                if v is None:
                    opts.pop(k, None)
                else:
                    opts[k] = v
        if dev_patch and isinstance(dev_patch, dict):
            dev = theme_section.setdefault('dev', {})
            for k, v in dev_patch.items():
                if v is None:
                    dev.pop(k, None)
                else:
                    dev[k] = v
        self._editor_draft_bundle = self._sanitize_theme_bundle(bundle)
        self._editor_draft_theme_name = requested_theme
        self._editor_draft_dirty = True
        return self._editor_draft_bundle

    def _write_theme_bundle_to_config(self, theme_name, theme_bundle):
        if not theme_name:
            raise ValueError('Missing theme name.')
        theme_name = str(theme_name).strip() or 'Default'
        if theme_name == 'Default':
            raise ValueError('Default theme cannot be written from the editor draft.')

        theme_path = self._theme_path_for(theme_name)
        if not theme_path:
            theme_path = os.path.join(self._themes_root, theme_name)
        os.makedirs(theme_path, exist_ok=True)

        raw_config = self._read_theme_config(theme_name) or {}
        raw_config['theme'] = copy.deepcopy((theme_bundle or {}).get('theme', {}))

        resolved = self._resolve_theme_paths(theme_name)
        config_path = resolved.get('config') or os.path.join(theme_path, 'config.toml')
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        self._write_text_file(config_path, toml.dumps(raw_config))
        return config_path

    def _apply_editor_draft(self, theme_name=None):
        requested_theme = theme_name or self._editor_draft_theme_name or self._theme_name or 'Default'
        bundle = copy.deepcopy(self._get_editor_theme_bundle(requested_theme))
        bundle = self._sanitize_theme_bundle(bundle)

        self._write_theme_bundle_to_config(requested_theme, bundle)
        self._invalidate_theme_inventory()
        self._rebuild_repo_screenshots_tree()

        if requested_theme == self._theme_name:
            self._reload_theme_state()
        else:
            self._reset_editor_draft(requested_theme)
        self._editor_draft_dirty = False
        return self._build_editor_snapshot(requested_theme)

    def _render_editor_preview_canvas(self, theme_name=None):
        requested_theme = theme_name or self._theme_name or 'Default'
        bundle = self._editor_runtime_theme_bundle(requested_theme)
        theme_path = self._theme_path_for(requested_theme)
        runtime = self._build_theme_runtime(requested_theme, theme_path, bundle)
        width, height = self._canvas_size()
        rotation = self._current_rotation()
        physical_width, physical_height = self._physical_canvas_size()
        canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        palette = self._resolve_render_palette(bundle, theme_name=requested_theme)
        state_map = {}
        if self._view_instance is not None:
            try:
                with self._view_instance._lock:
                    state_map = self._state_mapping(self._view_instance._state).copy()
            except Exception:
                state_map = {}
        self.render_refaced_frame(
            canvas,
            state_map,
            theme_bundle=bundle,
            palette=palette,
            theme_assets=runtime.get('assets', self._theme_assets),
            theme_name=requested_theme,
            anim_frame_index=runtime.get('anim_frame_index', 0),
            runtime_version=runtime.get('runtime_version', 0),
            theme_runtime=runtime,
            frame_index=0,
        )
        logging.debug(
            f"[Refacer][editor] rotation={rotation} physical_canvas=({physical_width},{physical_height}) "
            f"logical_canvas=({width},{height}) preview_frame={canvas.size}"
        )
        return canvas

    def _editor_serialize_sequence(self, value):
        if isinstance(value, tuple):
            return [self._editor_serialize_sequence(v) for v in value]
        if isinstance(value, list):
            return [self._editor_serialize_sequence(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._editor_serialize_sequence(v) for k, v in value.items()}
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def _editor_preview_text(self, widget_key, widget_state, value='', label=''):
        text = value if value not in (None, '') else widget_state.get('text', '')
        if label and widget_state.get('widget_type') == 'LabeledValue':
            text = f"{label}: {text}" if text not in (None, '') else str(label)
        text = '' if text is None else str(text)
        return text[:180]

    def _editor_resolved_color(self, widget_key, widget_state, palette, frame_index=0):
        main_text_color = palette['theme_options'].get('main_text_color')
        base_text_color = palette['theme_options'].get('base_text_color')

        if main_text_color:
            raw_color_source = main_text_color
        elif widget_state.get('color'):
            raw_color_source = widget_state.get('color')
        elif base_text_color:
            raw_color_source = base_text_color
        else:
            raw_color_source = [palette['default_foreground']]

        raw_color = self._pick_color(raw_color_source, index=frame_index)
        return self._normalize_color(raw_color or palette['default_foreground'])

    def _editor_text_payload(self, widget_key, widget, widget_state, theme_bundle=None, theme_runtime=None):
        value = self._widget_text_value(widget_key, widget, widget_state, theme_bundle=theme_bundle)
        label = widget_state.get('label', '')
        wrap = bool(widget_state.get('wrap'))
        max_length = int(widget_state.get('max_length') or 0)
        position = widget_state.get('position', [0, 0])
        text_font = self._widget_font(widget_state, 'text', theme_runtime=theme_runtime)
        label_font = self._widget_font(widget_state, 'label', theme_runtime=theme_runtime)
        is_multiline_input = '\n' in value

        if widget_key == 'status':
            value = self._prepare_status_value(value, widget_state, position, text_font)
        elif is_multiline_input:
            if max_length > 0:
                processed_lines = []
                for line in value.splitlines():
                    line = '' if line is None else str(line)
                    if wrap:
                        wrapped = TextWrapper(
                            width=max_length,
                            replace_whitespace=False,
                            drop_whitespace=False,
                        ).wrap(line) or ['']
                        processed_lines.extend(wrapped)
                    else:
                        if len(line) > max_length:
                            line = line[:max_length] + '...'
                        processed_lines.append(line)
                value = '\n'.join(processed_lines)
        else:
            if max_length > 0 and len(value) > max_length:
                value = value[:max_length] + '...'
            if wrap and max_length > 0:
                value = '\n'.join(TextWrapper(width=max_length, replace_whitespace=False).wrap(value))
        return value, label, text_font, label_font

    def _editor_widget_bbox(self, widget_key, widget, widget_state, palette, theme_bundle=None, theme_runtime=None, frame_index=0):
        widget_type = widget_state.get('widget_type', 'Text')
        position = widget_state.get('position', [0, 0])
        color = self._editor_resolved_color(widget_key, widget_state, palette, frame_index=frame_index)

        if widget_type in ('Line', 'Rect', 'FilledRect') and isinstance(position, (list, tuple)) and len(position) >= 4:
            x1, y1, x2, y2 = self._shape_coords(position)
            return [int(min(x1, x2)), int(min(y1, y2)), int(max(x1, x2)), int(max(y1, y2))], widget_type.lower(), None

        if widget_type == 'Bitmap' and isinstance(position, (list, tuple)) and len(position) >= 2:
            icon_image = self._resolve_bitmap_image(widget_key, widget, widget_state, color=color, theme_runtime=theme_runtime)
            icon_image = self._apply_image_effects(icon_image, widget_state, color=color)
            if icon_image is not None:
                x1, y1, x2, y2 = self._pos_convert(position[0], position[1], icon_image.width, icon_image.height)
                return [x1, y1, x2, y2], 'bitmap-map', None

        value, label, text_font, label_font = self._editor_text_payload(
            widget_key,
            widget,
            widget_state,
            theme_bundle=theme_bundle,
            theme_runtime=theme_runtime,
        )

        icon_image = None
        if widget_state.get('icon') and widget_type != 'LabeledValue':
            if widget_key in ('face', 'friend_face'):
                face_map_key = 'face_map' if widget_key == 'face' else 'friend_face_map'
                mapped = (widget_state.get(face_map_key) or {}).get(value)
                if mapped:
                    icon_image = mapped.get('image')
                    if icon_image is not None:
                        icon_image = icon_image.copy()
                        if widget_state.get('icon_color'):
                            icon_image = self._apply_icon_color(icon_image, color)
            elif icon_image is None:
                icon_image = self._widget_icon_asset(widget_key, widget_state, theme_runtime=theme_runtime)
                icon_image = self._apply_image_effects(icon_image, widget_state, color=color)
            if icon_image is not None and isinstance(position, (list, tuple)) and len(position) >= 2:
                x1, y1, x2, y2 = self._pos_convert(position[0], position[1], icon_image.width, icon_image.height)
                if widget_key in ('face', 'friend_face'):
                    return [x1, y1, x2, y2], 'icon', value

        if label and widget_type == 'LabeledValue' and isinstance(position, (list, tuple)) and len(position) >= 2:
            label_mode = 'text'
            label_icon = None
            resolved_label_font = label_font
            resolved_value_font = text_font
            label_text = '' if label is None else str(label)
            awesome_name = self.f_awesome_name if theme_runtime is None else theme_runtime.get('f_awesome_name', self.f_awesome_name)
            awesome_glyph = None
            if widget_state.get('icon'):
                if widget_state.get('f_awesome') and awesome_name and label_text:
                    awesome_glyph = self._font_awesome_label_glyph(label_text)
                    if awesome_glyph:
                        awesome_size = int(widget_state.get('f_awesome_size') or getattr(label_font, 'size', 16))
                        resolved_label_font = self._get_font_from_name(awesome_name, awesome_size, theme_runtime=theme_runtime)
                        label_mode = 'font_awesome'
                else:
                    label_name = label_text.strip()
                    if '.' in label_name:
                        label_icon = self._load_image_asset(
                            label_name,
                            folders=[os.path.join('img', 'widgets'), os.path.join('img', widget_key), 'img', ''],
                            theme_runtime=theme_runtime,
                        )
                        label_icon = self._apply_image_effects(label_icon, widget_state, color=color)
                        if label_icon is not None:
                            label_mode = 'image'
            if label_mode == 'image' and label_icon is not None:
                lw, lh = label_icon.width, label_icon.height
            else:
                render_label = awesome_glyph if label_mode == 'font_awesome' and awesome_glyph else label_text
                lw, lh = self._text_size(resolved_label_font, render_label)
            line_spacing = int(widget_state.get('label_line_spacing', self._theme_options(theme_bundle).get('label_line_spacing', 0)))
            if '\n' in value:
                value_img = self._multiline_rgba_text(value, resolved_value_font, color, line_spacing=line_spacing)
                vw = value_img.width if value_img is not None else 0
                vh = value_img.height if value_img is not None else 0
            else:
                vw, vh = self._text_size(resolved_value_font, value)
            spacing = int(widget_state.get('label_spacing', self._theme_options(theme_bundle).get('label_spacing', 9)))
            if label_mode == 'text':
                total_width = max(1, lw + spacing + 5 * len(label_text) + vw)
            else:
                total_width = max(1, lw + spacing + vw)
            total_height = max(1, max(lh, vh) + max(0, line_spacing))
            x1, y1, x2, y2 = self._pos_convert(position[0], position[1], total_width, total_height)
            return [x1, y1, x2, y2], 'labeled_text', self._editor_preview_text(widget_key, widget_state, value=value, label=label)

        if isinstance(position, (list, tuple)) and len(position) >= 2:
            text_line_spacing = int(widget_state.get('label_line_spacing', self._theme_options(theme_bundle).get('label_line_spacing', 0)))
            text_img = self._multiline_rgba_text(value, text_font, color, line_spacing=text_line_spacing) if '\n' in value else self.rgba_text(value, text_font, color)
            if text_img is not None:
                x1, y1, x2, y2 = self._pos_convert(position[0], position[1], text_img.width, text_img.height)
                return [x1, y1, x2, y2], 'text', self._editor_preview_text(widget_key, widget_state, value=value, label=label)

        stock_bbox = self._stock_widget_bbox(widget)
        if stock_bbox is not None:
            return [int(v) for v in stock_bbox], 'stock-frame', self._editor_preview_text(widget_key, widget_state, value=value, label=label)
        return None, 'unknown', self._editor_preview_text(widget_key, widget_state, value=value, label=label)

    def _build_editor_snapshot(self, requested_theme=None):
        active_theme = self._theme_name
        theme_name = requested_theme or active_theme
        width, height = self._canvas_size()
        physical_width, physical_height = self._physical_canvas_size()
        theme_bundle = self._editor_runtime_theme_bundle(theme_name)
        theme_runtime = self._build_theme_runtime(theme_name, self._theme_path_for(theme_name), theme_bundle)
        palette = self._resolve_render_palette(theme_bundle, theme_name=theme_name)
        state_map = {}
        if self._view_instance is not None:
            try:
                with self._view_instance._lock:
                    state_map = self._state_mapping(self._view_instance._state).copy()
            except Exception:
                state_map = {}

        widgets = []
        widget_keys = set(self._theme_widgets(theme_bundle).keys()) | set(state_map.keys())
        stealth_mode = self._theme_stealth_mode(theme_bundle)
        for key in sorted(widget_keys):
            widget = state_map.get(key)
            runtime_state = self._widget_runtime_state(
                key,
                widget,
                theme_bundle=theme_bundle,
                theme_name=theme_name,
                theme_runtime=theme_runtime,
            )
            z_axis = int(runtime_state.get('z_axis', 0) or 0)
            hidden_reason = None
            visible = True
            if z_axis < 0:
                visible = False
                hidden_reason = 'negative_z_axis'
            elif stealth_mode and z_axis < 100:
                visible = False
                hidden_reason = 'stealth_mode'
            bbox, render_mode, preview_text = self._editor_widget_bbox(
                key,
                widget,
                runtime_state,
                palette,
                theme_bundle=theme_bundle,
                theme_runtime=theme_runtime,
                frame_index=0,
            )
            widgets.append({
                'key': key,
                'widget_type': runtime_state.get('widget_type', 'Text'),
                'origin': runtime_state.get('origin'),
                'z_axis': z_axis,
                'position': self._editor_serialize_sequence(runtime_state.get('position')),
                'bbox': self._editor_serialize_sequence(bbox),
                'theme_fields': list(runtime_state.get('theme_fields', [])),
                'render_mode': render_mode,
                'preview_text': preview_text,
                'has_theme_override': self._widget_has_theme_override(key, runtime_state, theme_bundle=theme_bundle, theme_name=theme_name),
                'visible': visible,
                'hidden_reason': hidden_reason,
                'editable': self._extract_widget_editable_fields(key, runtime_state, theme_bundle),
                'metadata': {
                    'requested_theme': requested_theme or theme_name,
                    'icon': bool(runtime_state.get('icon')),
                    'wrap': bool(runtime_state.get('wrap')),
                    'max_length': int(runtime_state.get('max_length') or 0),
                    'width': runtime_state.get('width'),
                    'height': runtime_state.get('height'),
                },
            })

        widgets.sort(key=lambda item: (int(item.get('z_axis', 0)), str(item.get('key', ''))))
        theme_section = (theme_bundle or {}).get('theme', {}) or {}
        return {
            'theme': theme_name,
            'active_theme': active_theme,
            'requested_theme': requested_theme or theme_name,
            'preview_url': self._editor_preview_url(theme_name),
            'canvas': {'width': width, 'height': height},
            'physical_canvas': {'width': physical_width, 'height': physical_height},
            'rotation': self._current_rotation(),
            'widgets': widgets,
            'assets': self._theme_asset_inventory(theme_name),
            'render_stats': {'current_tier': self._render_stats.get('current_tier', 'full'), 'degrade_reason': self._render_stats.get('degrade_reason')},
            'draft_dirty': bool(self._editor_draft_dirty and self._editor_draft_theme_name == theme_name),
            'theme_global_options': {
                'options': self._editor_serialize_sequence(theme_section.get('options', {})),
                'dev': self._editor_serialize_sequence(theme_section.get('dev', {})),
                'is_default': theme_name == 'Default',
            },
        }

    # Capture the OG view render as the fidelity base instead of replaying live widgets onto the themed RGBA canvas.
    def _get_stock_render_frame(self):
        canvas = self._last_stock_canvas.copy() if self._last_stock_canvas is not None else None
        if canvas is None and self._view_instance is not None:
            current = getattr(self._view_instance, '_canvas', None)
            if current is not None:
                canvas = current.copy()
        if canvas is None:
            width, height = self._canvas_size()
            return Image.new('RGBA', (width, height), (255, 255, 255, 0))
        return canvas.convert('RGBA')

    def _stock_background_rgba(self):
        if self._view_instance is not None:
            return self._normalize_color(getattr(self._view_instance, '_backgroundcolor', 255))
        return (255, 255, 255, 255)

    def _get_theme_manager(self):
        loaded = getattr(plugins, 'loaded', {}) or {}
        for name in ('theme_manager', 'fancygotchi'):
            manager = loaded.get(name)
            if manager and manager is not self:
                return manager
        return None

    def _get_theme_bundle(self, state):
        if self._theme_bundle:
            return self._theme_bundle
        manager = self._get_theme_manager()
        if manager and hasattr(manager, 'get_refacer_theme'):
            try:
                bundle = manager.get_refacer_theme(self._view_instance, state)
                if isinstance(bundle, dict):
                    return bundle
            except Exception as e:
                logging.error(f"[Refacer] Theme bundle error: {e}")
        return {}

    # Pwnagotchi hands us a State object here, not always a plain dict.
    def _state_mapping(self, state):
        if isinstance(state, dict):
            return state
        nested = getattr(state, '_state', None)
        if isinstance(nested, dict):
            return nested
        if hasattr(state, 'items') and hasattr(state, 'get'):
            try:
                return dict(state.items())
            except Exception:
                return {}
        return {}

    def _resolve_font_override(self, override, fallback):
        if not override:
            return fallback
        if hasattr(fonts, str(override)):
            return getattr(fonts, str(override))
        return fallback

    def _theme_widget_override(self, widget_key, widget, theme_bundle):
        widgets = theme_bundle.get('widgets', {})
        override = widgets.get(widget_key)
        if override is None and hasattr(widget, 'name'):
            override = widgets.get(getattr(widget, 'name'))
        return override if isinstance(override, dict) else {}

    def _push_web_frame(self, canvas, frame_counter, generation=None):
        if generation is not None and not self._render_generation_is_active(generation):
            return False
        final_frame = canvas.copy()
        self._view_instance._refacer_web_canvas = final_frame
        self._last_render_canvas = final_frame.copy()
        if generation is not None and not self._render_generation_is_active(generation):
            return False
        self._mark_render_progress(time.time(), published_web=True, generation=generation)
        logging.debug("[Refacer][sink] final frame stored for preview")

        if self.options.get('save_images', False):
            interval = self.options.get('save_interval', self.DEFAULT_OPTIONS['save_interval'])
            if frame_counter % interval == 0:
                logging.debug("[Refacer][web] save_images snapshot interval reached")
        return True

    def _is_web_render_callback(self, callback):
        module = getattr(callback, '__module__', '') or ''
        name = getattr(callback, '__name__', '') or ''
        qualname = getattr(callback, '__qualname__', '') or ''
        return module.startswith('pwnagotchi.ui.web') or name == 'update_frame' or qualname.endswith('update_frame')

    def _push_render_callbacks(self, canvas, generation=None):
        if generation is not None and not self._render_generation_is_active(generation):
            return False
        self._expire_recovery_cache_handoff_if_needed()
        cbs = getattr(self._view_instance, '_refacer_hidden_cbs', self._view_instance._render_cbs)
        frame = self._prepare_hardware_frame(canvas)
        rotation = self._current_rotation()
        physical_width, physical_height = self._physical_canvas_size()
        published = 0
        callback_errors = 0
        for cb in (cbs or []):
            if self._is_web_render_callback(cb):
                logging.debug("[Refacer][web] skipped callback publish for web sink")
                continue
            if generation is not None and not self._render_generation_is_active(generation):
                return False
            try:
                cb(frame)
                published += 1
            except Exception as e:
                callback_errors += 1
                logging.error(f"[Refacer] Render callback error: {e}")
            if generation is not None and not self._render_generation_is_active(generation):
                return False
        if published > 0:
            if generation is not None and not self._render_generation_is_active(generation):
                return False
            self._last_known_good_canvas = canvas.copy()
            self._mark_render_progress(time.time(), published_hw=True, generation=generation)
            if self._recovery_cache_active:
                self._fresh_publish_streak_after_recovery = int(self._fresh_publish_streak_after_recovery or 0) + 1
                if self._fresh_publish_streak_after_recovery == 1:
                    logging.info("[Refacer][recovery] normal render publish resumed after display reinit")
                logging.info(
                    "[Refacer][recovery] fresh live publish after recovery streak=%d"
                    % self._fresh_publish_streak_after_recovery
                )
                if self._fresh_publish_streak_after_recovery >= 3:
                    self._last_emergency_display_reinit_bypass_ts = 0.0
                    self._clear_recovery_cache_handoff()
                    logging.info("[Refacer][recovery] cached-frame handoff released after fresh live publishes")
            if self._watchdog_recoveries > 0:
                self._fresh_publishes_since_recovery += 1
                if self._fresh_publishes_since_recovery >= self._watchdog_health_publishes():
                    prev = self._watchdog_recoveries
                    self._watchdog_recoveries = 0
                    self._fresh_publishes_since_recovery = 0
                    self._watchdog_last_recovery_ts = 0.0
                    self._last_emergency_display_reinit_bypass_ts = 0.0
                    self._render_stats['watchdog_recoveries'] = 0
                    logging.info(
                        f"[Refacer][watchdog] recovery counter reset after "
                        f"{self._watchdog_health_publishes()} healthy publishes (was {prev})"
                    )
        else:
            self._note_hardware_publish_failure()
        if callback_errors > 0 and published == 0:
            self._display_wedge_suspected = True
            self._render_stats['display_wedge_suspected'] = True
        logging.debug(
            f"[Refacer][sink] final frame pushed to hardware count={published} "
            f"gen={generation if generation is not None else self._reset_generation} rotation={rotation} "
            f"composed={canvas.size} physical={(physical_width, physical_height)}"
        )
        return published > 0

    def _publish_final_frame(self, canvas, frame_counter, generation=None):
        if generation is not None and not self._render_generation_is_active(generation):
            return 0.0
        publish_start = time.perf_counter()
        if not self._push_web_frame(canvas, frame_counter, generation=generation):
            return 0.0
        if generation is not None and not self._render_generation_is_active(generation):
            return 0.0
        import pwnagotchi.ui.web as web
        web.update_frame(canvas.copy())
        logging.debug("[Refacer][sink] final frame pushed to web")
        if generation is not None and not self._render_generation_is_active(generation):
            return 0.0
        if not self._display_hardware_publish_allowed():
            # Display-off is an intentional soft sleep: keep preview/cache fresh, suppress hardware publish and recovery.
            self._sync_display_control_stats()
            logging.debug("[Refacer][display] hardware publish skipped while display is off")
        else:
            self._push_render_callbacks(canvas, generation=generation)
        if generation is not None and not self._render_generation_is_active(generation):
            return 0.0
        publish_ms = (time.perf_counter() - publish_start) * 1000.0
        self._record_publish_timing(publish_ms)
        return publish_ms

    def _normalize_color(self, color):
        if isinstance(color, bool):
            return (0, 0, 0, 255) if color else (255, 255, 255, 255)
        if isinstance(color, (tuple, list)):
            if len(color) == 1:
                return self._normalize_color(color[0])
            if len(color) == 3:
                return tuple(color) + (255,)
            if len(color) == 4:
                return tuple(color)
            return tuple(color)

        if isinstance(color, str):
            try:
                rgb = ImageColor.getrgb(color)
                if len(rgb) == 3:
                    return rgb + (255,)
                if len(rgb) == 4:
                    return rgb
                return tuple(rgb[:4]) if len(rgb) > 4 else (0, 0, 0, 255)
            except ValueError:
                return (0, 0, 0, 255)

        return (0, 0, 0, 255)

    # Old Fancygotchi semantics:
    # - mask   -> refine-driven alpha threshold, visible pixels become solid ink
    # - alpha  -> near-white pixels become transparent
    def _alphamask(self, image):
        image = image.convert('RGBA')
        data = []
        for r, g, b, a in image.getdata():
            if r >= 240 and g >= 240 and b >= 240:
                data.append((255, 255, 255, 0))
            else:
                data.append((r, g, b, a))
        masked = Image.new('RGBA', image.size)
        masked.putdata(data)
        return masked

    def _masking(self, image, refine=150):
        image = image.convert('RGBA')
        threshold = max(0, min(255, int(refine if refine not in (None, '') else 150)))
        data = []
        for r, g, b, a in image.getdata():
            if a > threshold:
                data.append((0, 0, 0, 255))
            else:
                data.append((0, 0, 0, 0))
        masked = Image.new('RGBA', image.size)
        masked.putdata(data)
        return masked

    def _apply_icon_color(self, image, color):
        if image is None or color is None:
            return image
        output = image.convert('RGBA')
        alpha = output.getchannel('A') if 'A' in output.getbands() else None
        luminance = output.convert('L')
        tinted = ImageOps.colorize(
            luminance,
            black=self._normalize_color(color)[:3],
            white=(255, 255, 255),
        ).convert('RGBA')
        if alpha is not None:
            tinted.putalpha(alpha)
        return tinted

    def _parse_dimension(self, value, total, default):
        if value in (None, ''):
            return int(default)
        if isinstance(value, str) and value.endswith('%'):
            try:
                return max(1, int((float(value[:-1]) / 100.0) * total))
            except Exception:
                return int(default)
        try:
            return max(1, int(value))
        except Exception:
            return int(default)

    def _menu_visible_capacity(self, options, canvas, title_font):
        rect = self._menu_rect_from_options(options, canvas)
        _x, _y, _w, h = rect
        padding = 4
        title_h = max(18, int(getattr(title_font, 'size', 14)) + 6)
        button_h = self._parse_dimension(options.get('button_height', 15), h, 15)
        available_h = max(0, h - (padding + title_h + 4) - padding)
        if button_h <= 0:
            button_h = 15
        visible = max(1, available_h // button_h)
        return int(visible), int(button_h), rect

    def _menu_rect_from_options(self, options, canvas):
        width = self._parse_dimension(options.get('width', '50%'), canvas.width, max(1, canvas.width // 2))
        height = self._parse_dimension(options.get('height', '100%'), canvas.height, canvas.height)
        pos = options.get('position', ['right', 'bottom'])
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            pos = ['right', 'bottom']

        anchor_x = str(pos[0]).lower()
        anchor_y = str(pos[1]).lower()

        if anchor_x == 'left':
            x = 0
        elif anchor_x == 'center':
            x = (canvas.width - width) // 2
        else:
            x = canvas.width - width

        if anchor_y == 'top':
            y = 0
        elif anchor_y == 'center':
            y = (canvas.height - height) // 2
        else:
            y = canvas.height - height

        x = max(0, min(canvas.width - width, x))
        y = max(0, min(canvas.height - height, y))
        return (x, y, width, height)

    def _scrolling_menu_text_image(self, key, text, font, color, width, step=10):
        text = '' if text is None else str(text)
        if width <= 1:
            return self.rgba_text(text, font, color)
        probe = self.rgba_text(text, font, color)
        if probe is None or probe.width <= width:
            return probe

        state = self._menu_scroll_state.get(key)
        if not state or state.get('text') != text or state.get('width') != probe.width:
            state = {
                'text': text,
                'width': probe.width,
                'position': 8,
            }
            self._menu_scroll_state[key] = state

        pos = int(state.get('position', 8))
        strip = Image.new('RGBA', (width, probe.height), (0, 0, 0, 0))
        strip.paste(probe, (pos, 0), probe)

        gap_text = self.rgba_text(f" - {text}", font, color)
        if gap_text is not None and pos + probe.width < width:
            strip.paste(gap_text, (pos + probe.width, 0), gap_text)

        pos -= max(1, int(step))
        reset_width = probe.width + (gap_text.width if gap_text is not None else 0)
        if pos + reset_width <= 0:
            pos = 8
        self._menu_scroll_state[key]['position'] = pos
        return strip

    def _draw_text_centered_or_scrolling(self, canvas, key, text, font, color, rect, motion_enabled=False, motion_speed=10):
        x, y, w, h = rect
        img = self._scrolling_menu_text_image(key, text, font, color, w, step=motion_speed) if motion_enabled else self.rgba_text(text, font, color)
        if img is None:
            return
        tx = x + max(0, (w - min(img.width, w)) // 2) if not motion_enabled or img.width <= w else x
        ty = y + max(0, (h - img.height) // 2)
        canvas.paste(img, (tx, ty), img)

    def _menu_button_asset(self, name, theme_runtime=None):
        return self._load_image_asset(
            name,
            folders=[os.path.join('img', 'menu'), 'img', ''],
            theme_runtime=theme_runtime,
        )

    def _render_lightmenu_overlay(self, canvas, diagnostics, theme_bundle=None, theme_runtime=None):
        snapshot = self._lightmenu_snapshot()
        if not snapshot or not snapshot.get('visible'):
            return

        options = self._theme_menu_options(theme_bundle)
        rotation = self._current_rotation()
        physical_width, physical_height = self._physical_canvas_size()
        logical_width, logical_height = self._canvas_size()
        logical_menu_canvas = canvas
        if canvas.size != (logical_width, logical_height):
            logical_menu_canvas = Image.new('RGBA', (logical_width, logical_height), (0, 0, 0, 0))
        rect = self._menu_rect_from_options(options, logical_menu_canvas)
        x, y, w, h = rect
        logging.debug(
            f"[Refacer][lightmenu] rotation={rotation} physical=({physical_width},{physical_height}) "
            f"logical_menu_canvas=({logical_width},{logical_height}) canvas_size={canvas.size} menu_rect={rect}"
        )

        border_color = self._normalize_color(options.get('border_color') or 'black')
        title_color = self._normalize_color(options.get('title_color') or options.get('button_text_color') or 'black')
        text_color = self._normalize_color(options.get('button_text_color') or self._theme_options(theme_bundle).get('main_text_color', ['black'])[0] or 'black')
        highlight_color = self._normalize_color(options.get('highlight_color') or border_color)
        highlight_text_color = self._normalize_color(options.get('highlight_text_color') or 'white')
        bg_color = options.get('bg_color')
        button_bg_color = options.get('button_bg_color')
        motion_enabled = bool(options.get('motion_text', True))
        motion_speed = max(1, self._sanitize_int(options.get('motion_text_speed', 10), 10, minimum=1))

        title_font = self._widget_font({
            'widget_key': 'menu_title',
            'text_font': '',
            'text_font_size': options.get('title_font_size', 'BoldBig'),
            'size_offset': 0,
        }, 'text', theme_runtime=theme_runtime)
        item_font = self._widget_font({
            'widget_key': 'menu_item',
            'text_font': '',
            'text_font_size': options.get('text_font_size', 'Medium'),
            'size_offset': 0,
        }, 'text', theme_runtime=theme_runtime)

        visible_capacity, button_h, rect = self._menu_visible_capacity(options, logical_menu_canvas, title_font)
        x, y, w, h = rect

        bg_image = self._menu_button_asset(options.get('bg_image'), theme_runtime=theme_runtime) if options.get('bg_image') else None
        button_bg_image = self._menu_button_asset(options.get('button_bg_image'), theme_runtime=theme_runtime) if options.get('button_bg_image') else None
        highlight_button_bg_image = self._menu_button_asset(options.get('highlight_button_bg_image'), theme_runtime=theme_runtime) if options.get('highlight_button_bg_image') else None

        if bg_color not in (None, ''):
            ImageDraw.Draw(canvas).rectangle((x, y, x + w, y + h), fill=self._normalize_color(bg_color))
        if bg_image is not None:
            bg_panel = self._image_mode(Image.new('RGBA', (w, h), (0, 0, 0, 0)), bg_image, options.get('bg_mode', 'normal'))
            canvas.alpha_composite(bg_panel, (x, y))

        ImageDraw.Draw(canvas).rectangle((x, y, x + w, y + h), outline=border_color, width=1)

        padding = 4
        title_h = max(18, int(getattr(title_font, 'size', 14)) + 6)
        self._draw_text_centered_or_scrolling(
            canvas,
            f"title:{snapshot.get('title', 'Menu')}",
            snapshot.get('title', 'Menu'),
            title_font,
            title_color,
            (x + padding, y + padding, w - (padding * 2), title_h),
            motion_enabled=motion_enabled,
            motion_speed=motion_speed,
        )

        items = snapshot.get('items', [])
        offset = int(snapshot.get('offset', 0))
        index = int(snapshot.get('index', 0))
        label_count = max(1, min(int(snapshot.get('label_count', 1)), visible_capacity))
        max_offset = max(0, len(items) - label_count)
        offset = max(0, min(offset, max_offset))
        if index < offset:
            offset = index
        elif index >= offset + label_count:
            offset = max(0, index - label_count + 1)
        visible_items = items[offset:offset + label_count]
        body_y = y + padding + title_h + 4

        for row, label in enumerate(visible_items):
            by = body_y + (row * button_h)
            if by + button_h > y + h - padding:
                break
            absolute_index = offset + row
            selected = absolute_index == index

            btn_rect = (x + padding, by, w - (padding * 2), button_h - 1)
            bx, by2, bw, bh = btn_rect

            if selected:
                if highlight_button_bg_image is not None:
                    btn_img = self._image_mode(Image.new('RGBA', (bw, bh), (0, 0, 0, 0)), highlight_button_bg_image, 'stretch')
                    canvas.alpha_composite(btn_img, (bx, by2))
                else:
                    ImageDraw.Draw(canvas).rectangle((bx, by2, bx + bw, by2 + bh), fill=highlight_color)
                text_fg = highlight_text_color
            else:
                if button_bg_image is not None:
                    btn_img = self._image_mode(Image.new('RGBA', (bw, bh), (0, 0, 0, 0)), button_bg_image, 'stretch')
                    canvas.alpha_composite(btn_img, (bx, by2))
                elif button_bg_color not in (None, ''):
                    ImageDraw.Draw(canvas).rectangle((bx, by2, bx + bw, by2 + bh), fill=self._normalize_color(button_bg_color))
                text_fg = text_color

            self._draw_text_centered_or_scrolling(
                canvas,
                f"item:{absolute_index}:{label}",
                label,
                item_font,
                text_fg,
                btn_rect,
                motion_enabled=motion_enabled,
                motion_speed=motion_speed,
            )

        show_up_arrow = offset > 0
        show_down_arrow = (offset + label_count) < len(items)
        if show_up_arrow:
            self._draw_text_centered_or_scrolling(
                canvas, 'menu-up', '^', item_font, text_color,
                (x + w - 16, y + 2, 12, 12),
                motion_enabled=False, motion_speed=motion_speed
            )
        if show_down_arrow:
            self._draw_text_centered_or_scrolling(
                canvas, 'menu-down', 'v', item_font, text_color,
                (x + w - 16, y + h - 14, 12, 12),
                motion_enabled=False, motion_speed=motion_speed
            )

        diagnostics.append({
            'widget': 'lightmenu',
            'mode': 'menu-overlay',
            'origin': 'lightmenu-snapshot',
            'position': [x, y],
            'z': 500,
        })

    def on_menu(self):
        return {
            'Refacer': [
                ('Theme Next', {'action': 'pwnctl', 'plugin': 'refacer', 'cmd': 'theme_next'}),
                ('Theme Prev', {'action': 'pwnctl', 'plugin': 'refacer', 'cmd': 'theme_prev'}),
                ('Rotation Next', {'action': 'pwnctl', 'plugin': 'refacer', 'cmd': 'rotation_next'}),
                ('Stealth Toggle', {'action': 'pwnctl', 'plugin': 'refacer', 'cmd': 'stealth_toggle'}),
                ('Display Toggle', {'action': 'pwnctl', 'plugin': 'refacer', 'cmd': 'display_toggle'}),
                ('Display Clear', {'action': 'pwnctl', 'plugin': 'refacer', 'cmd': 'display_clear'}),
            ]
        }

    def on_pwnctl(self, cmd):
        cmd = str(cmd or '').strip().lower()
        if cmd == 'theme_next':
            themes = self._theme_list()
            current = self._theme_name if self._theme_name in themes else 'Default'
            idx = themes.index(current)
            self._set_active_theme(themes[(idx + 1) % len(themes)])
            return 'ok'
        if cmd == 'theme_prev':
            themes = self._theme_list()
            current = self._theme_name if self._theme_name in themes else 'Default'
            idx = themes.index(current)
            self._set_active_theme(themes[(idx - 1) % len(themes)])
            return 'ok'
        if cmd == 'rotation_next':
            rotations = [0, 90, 180, 270]
            cur = self._current_rotation()
            self._set_display_rotation(rotations[(rotations.index(cur) + 1) % len(rotations)])
            return 'ok'
        if cmd == 'rotation_prev':
            rotations = [0, 90, 180, 270]
            cur = self._current_rotation()
            self._set_display_rotation(rotations[(rotations.index(cur) - 1) % len(rotations)])
            return 'ok'
        if cmd == 'stealth_toggle':
            self._set_active_theme_stealth_mode(not self._theme_stealth_mode(self._theme_bundle))
            return 'ok'
        if cmd == 'display_on':
            return self.display_on(reason='pwnctl').get('status', 'ok')
        if cmd == 'display_off':
            return self.display_off(reason='pwnctl').get('status', 'ok')
        if cmd == 'display_toggle':
            return self.display_toggle(reason='pwnctl').get('status', 'ok')
        if cmd == 'display_clear':
            return self.display_clear(reason='pwnctl').get('status', 'ok')
        if cmd == 'theme_refresh':
            self._reload_theme_state()
            return 'ok'
        return 'unknown'

    def _image_mode(self, canvas, image, mode='normal'):
        width, height = canvas.size
        if image is None:
            return None
        if mode == 'normal':
            output = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            output.paste(image, (0, 0), image)
            return output
        if mode == 'stretch':
            return image.resize(canvas.size, Image.LANCZOS)
        if mode == 'fit':
            contained = ImageOps.contain(image, canvas.size, Image.LANCZOS)
            output = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            pos = ((width - contained.width) // 2, (height - contained.height) // 2)
            output.paste(contained, pos, contained)
            return output
        if mode == 'fill':
            return ImageOps.fit(image, canvas.size, Image.LANCZOS)
        if mode == 'center':
            output = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            pos = ((width - image.width) // 2, (height - image.height) // 2)
            output.paste(image, pos, image)
            return output
        if mode == 'tile':
            output = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            for x in range(0, width, max(1, image.width)):
                for y in range(0, height, max(1, image.height)):
                    output.paste(image, (x, y), image)
            return output
        return image

    def _pick_color(self, color_value, index=0):
        if isinstance(color_value, list):
            filtered = [value for value in color_value if value not in ('', None)]
            if not filtered:
                return None
            return filtered[index % len(filtered)]
        return color_value

    def _safe_eval_formula(self, expr):
        if expr is None:
            return 0
        text = str(expr)
        if re.search(r'[^0-9\+\-\*/\(\)\. ]', text):
            return 0
        try:
            return int(round(float(eval(text, {"__builtins__": {}}, {}))))
        except Exception:
            return 0

    def _axis_eval(self, value, axis, extent, span=0):
        values = {
            'left': 0,
            'top': 0,
            'right': extent - span,
            'bottom': extent - span,
            'center': (extent / 2) - (span / 2),
            'center_x': (extent / 2) - (span / 2),
            'center_y': (extent / 2) - (span / 2),
            'width': extent,
            'height': extent,
            'w': span,
            'h': span,
        }
        if isinstance(value, str):
            text = value
            for key, replace in values.items():
                if axis == 'x' and key in ('top', 'bottom', 'center_y', 'height', 'h'):
                    continue
                if axis == 'y' and key in ('left', 'right', 'center_x', 'width', 'w'):
                    continue
                text = text.replace(key, str(replace))
            return self._safe_eval_formula(text)
        result = int(value)
        if result < 0:
            return extent + result
        return result

    # Ported from old Fancygotchi anchor math so percentage and keyword positions still mean the same thing.
    def _pos_convert(self, x, y, w, h):
        width, height = self._canvas_size()
        def normalize_size(value, total):
            if isinstance(value, str) and '%' in value:
                try:
                    return int((float(value.replace('%', '')) / 100.0) * total)
                except ValueError:
                    return 0
            return int(value)

        w = normalize_size(w, width)
        h = normalize_size(h, height)
        x = self._axis_eval(x, 'x', width, w)
        y = self._axis_eval(y, 'y', height, h)
        return int(x), int(y), int(x + w), int(y + h)

    # Line/rect widgets use endpoint semantics in the stock view and legacy themes.
    def _shape_coords(self, position):
        width, height = self._canvas_size()
        x1 = self._axis_eval(position[0], 'x', width, 0)
        y1 = self._axis_eval(position[1], 'y', height, 0)
        x2 = self._axis_eval(position[2], 'x', width, 0)
        y2 = self._axis_eval(position[3], 'y', height, 0)
        return int(x1), int(y1), int(x2), int(y2)

    def _text_size(self, font, text):
        if font is None:
            return 0, 0
        try:
            return font.getsize(text)
        except AttributeError:
            # Mirror Fancygotchi: absolute right/bottom so total_height/width matches.
            _, _, right, bottom = font.getbbox(text)
            return right, bottom

    def _apply_image_effects(self, image, widget_state, color=None, *, apply_icon_color=True, apply_alpha=True):
        if image is None:
            return None
        output = image.convert('RGBA')
        crop = widget_state.get('crop') or [0, 0, 0, 0]
        if isinstance(crop, (list, tuple)) and len(crop) == 4 and any(crop):
            output = output.crop(tuple(crop))
        zoom = widget_state.get('zoom', 1) or 1
        if zoom != 1:
            output = output.resize((max(1, int(output.width * zoom)), max(1, int(output.height * zoom))), Image.LANCZOS)
        if widget_state.get('invert'):
            alpha = output.getchannel('A') if 'A' in output.getbands() else None
            output = ImageOps.invert(output.convert('RGB')).convert('RGBA')
            if alpha is not None:
                output.putalpha(alpha)

        applied = []
        if widget_state.get('mask'):
            output = self._masking(output, widget_state.get('refine', 150))
            applied.append('mask')
        if apply_icon_color and widget_state.get('icon_color') and color is not None:
            output = self._apply_icon_color(output, color)
            applied.append('color')
        if apply_alpha and widget_state.get('alpha'):
            output = self._alphamask(output)
            applied.append('alpha')

        width = widget_state.get('width')
        height = widget_state.get('height')
        if width or height:
            width = int(width or output.width)
            height = int(height or output.height)
            output = output.resize((max(1, width), max(1, height)), Image.LANCZOS)
        logging.debug(
            f"[Refacer][iconfx] widget={widget_state.get('widget_key')} "
            f"mask={bool(widget_state.get('mask'))} "
            f"alpha={bool(widget_state.get('alpha'))} "
            f"icon_color={bool(widget_state.get('icon_color'))} "
            f"refine={widget_state.get('refine', 150)} "
            f"applied={','.join(applied) or 'none'}"
        )
        return output

    def rgba_text(self, text, tfont, color='black', font_spacing=0):
        try:
            color = self._normalize_color(color)
            font_spacing = max(0, int(font_spacing or 0))

            if text is not None and tfont is not None:
                if font_spacing > 0 and text:
                    # Render each character individually and stitch with extra gap.
                    # Uses the same 1-bit mask path as the single-draw code below.
                    char_imgs = [self.rgba_text(ch, tfont, color, font_spacing=0) for ch in text]
                    char_imgs = [c for c in char_imgs if c is not None]
                    if not char_imgs:
                        return None
                    total_w = sum(c.width for c in char_imgs) + font_spacing * (len(char_imgs) - 1)
                    h = max(c.height for c in char_imgs)
                    out = Image.new('RGBA', (max(1, total_w), max(1, h)), (0, 0, 0, 0))
                    x = 0
                    for c in char_imgs:
                        out.paste(c, (x, 0), c)
                        x += c.width + font_spacing
                    return out

                try:
                    w, h = tfont.getsize(text)
                except AttributeError:
                    # Mirror Fancygotchi: use absolute right/bottom from getbbox and draw at (0,0).
                    # This preserves the same top-bearing offset per font so label and value
                    # align consistently with Fancygotchi across all Pillow versions.
                    _, _, w, h = tfont.getbbox(text)
                nb_lines = text.count('\n') + 1
                h = (h + 1) * nb_lines

                if w <= 0 or h <= 0:
                    return None

                mask = Image.new('1', (int(w), int(h)), 0)
                dt = ImageDraw.Draw(mask)
                dt.text((0, 0), text, font=tfont, fill=1)

                img = Image.new('RGBA', (int(w), int(h)), color)
                img.putalpha(mask.convert('L'))
                return img
        except Exception as e:
            logging.error(f"[Refacer] rgba_text error: {e}")
            return None

    def _multiline_rgba_text(self, text, tfont, color='black', line_spacing=0, font_spacing=0):
        try:
            color = self._normalize_color(color)
            font_spacing = max(0, int(font_spacing or 0))
            if text is None or tfont is None:
                return None

            raw_text = str(text)
            lines = raw_text.splitlines() or ['']
            if raw_text.endswith('\n'):
                lines.append('')

            line_metrics = []
            max_width = 0
            total_height = 0

            for line in lines:
                render_line = '' if line is None else str(line)
                probe = render_line if render_line else 'Ag'
                try:
                    w, h = tfont.getsize(probe)
                except AttributeError:
                    # Mirror Fancygotchi: absolute right/bottom, draw at (0, cursor_y).
                    _, _, w, h = tfont.getbbox(probe)
                if font_spacing > 0 and render_line:
                    # Width with per-char gaps: sum of individual char widths + gaps.
                    char_ws = []
                    for ch in render_line:
                        try:
                            cw, _ = tfont.getsize(ch)
                        except AttributeError:
                            _, _, cw, _ = tfont.getbbox(ch)
                        char_ws.append(max(0, cw))
                    w = sum(char_ws) + font_spacing * max(0, len(char_ws) - 1)
                w = max(0, w)
                h = max(1, h + 1)  # +1 per line matches Fancygotchi's (h+1)*nb_lines

                max_width = max(max_width, int(w))
                total_height += int(h)
                line_metrics.append((render_line, int(w), int(h)))

            if not line_metrics:
                return None

            total_height += max(0, int(line_spacing)) * max(0, len(line_metrics) - 1)
            max_width = max(1, int(max_width))
            total_height = max(1, int(total_height))

            if font_spacing > 0:
                # Composite per-line rgba_text images (with font_spacing) into the canvas.
                out = Image.new('RGBA', (max_width, total_height), (0, 0, 0, 0))
                cursor_y = 0
                for render_line, _w, h in line_metrics:
                    if render_line:
                        line_img = self.rgba_text(render_line, tfont, color, font_spacing=font_spacing)
                        if line_img is not None:
                            out.paste(line_img, (0, cursor_y), line_img)
                    cursor_y += h + max(0, int(line_spacing))
                return out

            # Keep multiline text on the same crisp raster path as rgba_text():
            # use a 1-bit glyph mask, not an antialiased L mask.
            mask = Image.new('1', (max_width, total_height), 0)
            dt = ImageDraw.Draw(mask)

            cursor_y = 0
            for render_line, _w, h in line_metrics:
                if render_line != '':
                    dt.text((0, cursor_y), render_line, font=tfont, fill=1)
                cursor_y += h + max(0, int(line_spacing))

            img = Image.new('RGBA', (max_width, total_height), color)
            img.putalpha(mask.convert('L'))
            return img
        except Exception as e:
            logging.error(f"[Refacer] _multiline_rgba_text error: {e}")
            return None

    # Font Awesome labels are configured as hex codepoints like "f1eb" or "0xf1eb".
    def _font_awesome_label_glyph(self, label_value):
        if label_value in (None, ''):
            return None
        try:
            text = str(label_value).strip().lower()
            if text.startswith('0x'):
                text = text[2:]
            return chr(int(text, 16))
        except Exception:
            return None

    def _sanitize_face_key(self, face_value):
        if face_value in (None, ''):
            return ''
        return re.sub(r'[^a-z0-9]+', '_', str(face_value).strip().lower()).strip('_')

    def _face_lookup_variants(self, lookup_key):
        raw = '' if lookup_key is None else str(lookup_key).strip()
        if not raw:
            return []
        variants = [
            raw,
            raw.upper(),
            raw.lower(),
            raw.capitalize(),
            raw.replace('-', '_'),
            raw.replace('_', '-'),
        ]
        variants.extend([
            variants[4].upper(),
            variants[4].lower(),
            variants[5].upper(),
            variants[5].lower(),
        ])
        seen = []
        for variant in variants:
            if variant and variant not in seen:
                seen.append(variant)
        return seen

    def _known_face_registry(self):
        registry = []
        for name in (
            'LOOK_R',
            'LOOK_L',
            'LOOK_R_HAPPY',
            'LOOK_L_HAPPY',
            'SLEEP',
            'SLEEP2',
            'AWAKE',
            'BORED',
            'INTENSE',
            'COOL',
            'HAPPY',
            'EXCITED',
            'GRATEFUL',
            'MOTIVATED',
            'DEMOTIVATED',
            'SMART',
            'LONELY',
            'SAD',
            'ANGRY',
            'FRIEND',
            'BROKEN',
            'DEBUG',
            'UPLOAD',
            'UPLOAD1',
            'UPLOAD2',
        ):
            value = getattr(faces, name, None)
            if value not in (None, ''):
                registry.append((name, str(value)))
        return registry

    # Filename lookup is flexible; logical face value remains the live ASCII face string.
    def _get_face_path(self, lookup_key, widget_key, widget_state, theme_runtime):
        if lookup_key in (None, ''):
            return None, None
        folders = [os.path.join('img', widget_key), 'img']
        image_type = widget_state.get('image_type', 'png')
        for variant in self._face_lookup_variants(lookup_key):
            candidates = [variant]
            if '.' not in variant:
                candidates = [f"{variant}.{image_type}", f"{variant}.png", f"{variant}.jpg", f"{variant}.jpeg", f"{variant}.bmp"]
            for candidate in candidates:
                path = self._theme_asset_path(candidate, folders=folders, theme_runtime=theme_runtime)
                if path:
                    return path, candidate
        return None, None

    def _normalize_widget_type(self, widget_type):
        widget_type = str(widget_type or 'Text')
        bitmap_types = getattr(self, 'BITMAP_WIDGET_TYPES', ('Bitmap',))
        return 'Bitmap' if widget_type in bitmap_types else widget_type

    def _image_difference_is_empty(self, image_a, image_b):
        if image_a is None or image_b is None:
            return False
        try:
            left = image_a.convert('RGBA')
            right = image_b.convert('RGBA')
            if left.size != right.size:
                return False
            return ImageChops.difference(left, right).getbbox() is None
        except Exception:
            return False

    def _bitmap_widget_theme_dir(self, widget_key, theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        theme_path = theme_runtime.get('theme_path')
        if not theme_path:
            return None
        candidate = os.path.join(theme_path, 'img', 'widgets', str(widget_key))
        return candidate if os.path.isdir(candidate) else None

    def _build_bitmap_theme_map(self, widget_key, widget_state, theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        img_dir = self._bitmap_widget_theme_dir(widget_key, theme_runtime=theme_runtime)
        if not img_dir:
            return {'themed_static_image': None, 'image_dict': {}}

        files = sorted(
            name for name in os.listdir(img_dir)
            if os.path.isfile(os.path.join(img_dir, name))
        )
        if not files:
            return {'themed_static_image': None, 'image_dict': {}}

        if len(files) == 1:
            path = os.path.join(img_dir, files[0])
            image = self._load_image_asset(path, folders=[''], theme_runtime=theme_runtime)
            return {
                'themed_static_image': image,
                'image_dict': {}
            }

        image_dict = {}
        by_stem = {}
        for filename in files:
            stem, _ext = os.path.splitext(filename)
            by_stem[stem] = filename

        for stem, original_name in sorted(by_stem.items()):
            if not stem.endswith('A'):
                continue
            pair_id = stem[:-1]
            themed_stem = pair_id + 'B'
            themed_name = by_stem.get(themed_stem)
            if not themed_name:
                continue
            original_path = os.path.join(img_dir, original_name)
            themed_path = os.path.join(img_dir, themed_name)
            try:
                original_img = Image.open(original_path).convert('RGBA')
                themed_img = self._load_image_asset(themed_path, folders=[''], theme_runtime=theme_runtime)
                if themed_img is not None:
                    image_dict[int(pair_id) if str(pair_id).isdigit() else pair_id] = [original_img, themed_img]
            except Exception as exc:
                logging.warning(f"[Refacer][bitmap-map] failed widget={widget_key} pair={pair_id}: {exc}")
        return {'themed_static_image': None, 'image_dict': image_dict}

    def _resolve_bitmap_image(self, widget_key, widget, widget_state, color=None, theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        live_image = widget_state.get('live_image')
        themed_static = widget_state.get('themed_static_image')
        image_dict = widget_state.get('image_dict') or {}

        if widget_state.get('icon') and image_dict and live_image is not None:
            for map_id, pair in image_dict.items():
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    continue
                original_img, themed_img = pair
                if self._image_difference_is_empty(original_img, live_image):
                    logging.debug(f"[Refacer][bitmap-map] matched widget={widget_key} map_id={map_id}")
                    return themed_img.copy() if isinstance(themed_img, Image.Image) else themed_img

        if widget_state.get('icon') and themed_static is not None:
            logging.debug(f"[Refacer][bitmap-map] using static themed image widget={widget_key}")
            return themed_static.copy() if isinstance(themed_static, Image.Image) else themed_static

        if live_image is not None:
            cache = widget_state.setdefault('live_bitmap_cache', {})
            cache_key = id(live_image)
            if cache_key not in cache:
                cache[cache_key] = live_image.copy() if isinstance(live_image, Image.Image) else live_image
            cached = cache[cache_key]
            return cached.copy() if isinstance(cached, Image.Image) else cached

        return None

    def _build_face_map(self, widget_key, widget_state, theme_bundle, theme_runtime):
        options = self._theme_options(theme_bundle)
        configured_faces = options.get('faces', {})
        face_map = {}
        if not widget_state.get('icon'):
            return face_map

        if isinstance(configured_faces, dict) and configured_faces:
            sources = [('explicit', str(face_value), lookup_key) for face_value, lookup_key in configured_faces.items()]
        else:
            # When no explicit map exists, auto-discover assets by known ASCII face identities.
            sources = [('auto', ascii_face, logical_name) for logical_name, ascii_face in self._known_face_registry()]

        for source_kind, face_value, lookup_key in sources:
            path, resolved_name = self._get_face_path(lookup_key, widget_key, widget_state, theme_runtime)
            if not path:
                continue
            asset = self._load_image_asset(path, folders=[''], theme_runtime=theme_runtime)
            # Keep the stored face asset neutral. Old Fancygotchi applied icon_color
            # after the live ASCII face selected the image.
            asset = self._apply_image_effects(asset, widget_state, apply_icon_color=False)
            if asset is None:
                continue
            face_map[str(face_value)] = {'lookup': lookup_key, 'file': resolved_name or os.path.basename(path), 'image': asset}
            if source_kind == 'explicit':
                logging.debug(f"[Refacer][face] explicit-map ascii={face_value} lookup={lookup_key} file={resolved_name or os.path.basename(path)}")
            else:
                logging.debug(f"[Refacer][face] auto-discovered ascii={face_value} lookup={lookup_key} file={resolved_name or os.path.basename(path)}")
        return face_map

    def _widget_text_value(self, widget_key, widget, widget_state, theme_bundle=None):
        value = widget_state.get('value', getattr(widget, 'value', None))
        if value is None and hasattr(widget, 'text'):
            value = getattr(widget, 'text', None)

        # ASCII face override: allow themes to replace face strings without touching global config.
        # This works by mapping the current stock ASCII string back to its mood name (e.g. 'happy')
        # and checking if the theme defines a replacement for that mood.
        if widget_key in ('face', 'friend_face') and not widget_state.get('icon'):
            theme_faces = self._theme_options(theme_bundle).get('faces')
            if isinstance(theme_faces, dict) and theme_faces:
                current_face_str = str(value).strip()
                # Check for direct ASCII string mapping or mood name mapping (e.g. 'happy')
                if current_face_str in theme_faces:
                    value = theme_faces[current_face_str]
                else:
                    for mood, stock_face in pwnagotchi.config.get('ui', {}).get('faces', {}).items():
                        if str(stock_face).strip() == current_face_str and mood in theme_faces:
                            value = theme_faces[mood]
                            break

        if widget_key in ('name', 'status') and value not in (None, ''):
            value = self._apply_theme_cursor(value, theme_bundle=theme_bundle)
        return '' if value is None else str(value)

    def _theme_cursor(self, theme_bundle=None):
        cursor = self._theme_options(theme_bundle).get('cursor', '|')
        cursor = '|' if cursor in (None, '') else str(cursor)
        logging.debug(f"[Refacer][text] using theme cursor={cursor!r}")
        return cursor

    # Only swap the trailing live cursor marker; leave the rest of the text untouched.
    def _apply_theme_cursor(self, value, theme_bundle=None):
        text = '' if value is None else str(value)
        for marker in self.CURSOR_MARKERS:
            if text.endswith(marker):
                return text[:-len(marker)] + ' ' + self._theme_cursor(theme_bundle=theme_bundle)
        return text

    def _widget_runtime_state(self, widget_key, widget, theme_bundle=None, theme_name=None, theme_runtime=None):
        widget_type = self._normalize_widget_type(widget.__class__.__name__ if widget is not None else 'Text')
        themed = copy.deepcopy(self._theme_widgets(theme_bundle).get(widget_key, {}))
        explicit_override = bool(themed) and (theme_name or self._theme_name) != 'Default'
        widget_type = themed.get('type', widget_type)
        state = {
            'widget_key': widget_key,
            'widget_type': widget_type,
            'origin': 'theme' if explicit_override else 'live',
            'theme_fields': sorted(themed.keys()),
            'color_index': 0,
        }
        orientation_key = 'position-v' if self._theme_orientation() == 'v' else 'position-h'
        if themed.get(orientation_key):
            themed = dict(themed)
            themed['position'] = themed.get(orientation_key)
        if widget is not None:
            xy = getattr(widget, 'xy', None)
            if xy is not None:
                state['position'] = list(xy) if isinstance(xy, tuple) else list(xy)
            if getattr(widget, 'color', None) not in (None, ''):
                state['color'] = [getattr(widget, 'color')]
            if hasattr(widget, 'label'):
                state['label'] = getattr(widget, 'label')
            if hasattr(widget, 'text'):
                state['text'] = getattr(widget, 'text')
            if hasattr(widget, 'value'):
                state['value'] = getattr(widget, 'value')
            if hasattr(widget, 'wrap'):
                state['wrap'] = getattr(widget, 'wrap')
            if hasattr(widget, 'max_length'):
                state['max_length'] = getattr(widget, 'max_length')
            if hasattr(widget, 'label_spacing'):
                state['label_spacing'] = getattr(widget, 'label_spacing')
            if hasattr(widget, 'width'):
                state['width'] = getattr(widget, 'width')
            if hasattr(widget, 'height'):
                state['height'] = getattr(widget, 'height')
            if hasattr(widget, 'font'):
                state['live_text_font'] = getattr(widget, 'font')
            if hasattr(widget, 'text_font'):
                state['live_text_font'] = getattr(widget, 'text_font')
            if hasattr(widget, 'label_font'):
                state['live_label_font'] = getattr(widget, 'label_font')
            if hasattr(widget, 'image'):
                state['live_image'] = getattr(widget, 'image')
            elif hasattr(widget, '_image'):
                state['live_image'] = getattr(widget, '_image')
        else:
            state.update(copy.deepcopy(self.WIDGET_DEFAULTS.get(widget_type, self.WIDGET_DEFAULTS['Text'])))
            state['origin'] = 'fallback'
        defaults = copy.deepcopy(self.WIDGET_DEFAULTS.get(widget_type, self.WIDGET_DEFAULTS['Text']))
        for key, value in defaults.items():
            state.setdefault(key, copy.deepcopy(value))
        for key, value in themed.items():
            state[key] = copy.deepcopy(value)
        # Cascade global label_spacing / label_line_spacing to widget state when not overridden per-widget.
        # Mirrors Fancygotchi: widget config > global options > live widget value.
        # NOTE: size_offset is intentionally NOT cascaded globally — Fancygotchi only applies it
        # per-widget, the global option acts as a fallback inside change_font() when called explicitly.
        _global_opts = self._theme_options(theme_bundle)
        _explicit_fields = set(state.get('theme_fields', []))
        for _opt_key in ('label_spacing', 'label_line_spacing', 'font_spacing'):
            if _opt_key not in _explicit_fields:
                _global_val = _global_opts.get(_opt_key)
                if _global_val is not None:
                    state[_opt_key] = _global_val
        if widget is None and explicit_override:
            state['origin'] = 'theme'
        if widget_key in ('face', 'friend_face'):
            map_key = 'face_map' if widget_key == 'face' else 'friend_face_map'
            runtime = self._theme_runtime if theme_runtime is None else theme_runtime
            state[map_key] = self._build_face_map(widget_key, state, theme_bundle, runtime)
        if widget_type == 'Bitmap':
            runtime = self._theme_runtime if theme_runtime is None else theme_runtime
            bitmap_map = self._build_bitmap_theme_map(widget_key, state, theme_runtime=runtime) if state.get('icon') else {}
            if bitmap_map:
                state['themed_static_image'] = bitmap_map.get('themed_static_image')
                state['image_dict'] = bitmap_map.get('image_dict', {})
            state.setdefault('image_dict', {})
            state.setdefault('live_bitmap_cache', {})
        return state

    def _widget_font(self, widget_state, field='text', theme_runtime=None):
        theme_runtime = self._theme_runtime if theme_runtime is None else theme_runtime
        live_font_key = f'live_{field}_font'
        explicit_font_name = widget_state.get(f'{field}_font')
        explicit_size_spec = widget_state.get(f'{field}_font_size')
        explicit_offset = widget_state.get('size_offset')
        explicit_theme_fields = set(widget_state.get('theme_fields', []))
        meaningful_size_override = explicit_size_spec not in (None, '', 0, '0')
        if (
            live_font_key in widget_state
            and not explicit_font_name
            and not meaningful_size_override
            and not explicit_offset
            and f'{field}_font' not in explicit_theme_fields
            and f'{field}_font_size' not in explicit_theme_fields
            and 'size_offset' not in explicit_theme_fields
        ):
            return widget_state.get(live_font_key)
        fallback_role = widget_state.get(f'{field}_font_size') or ('Bold' if field == 'label' else 'Medium')
        resolved_size = self._resolve_font_size_spec(explicit_size_spec, fallback_role=fallback_role, theme_runtime=theme_runtime)
        font_name = explicit_font_name or self._theme_font_family_for(widget_state, field=field, theme_runtime=theme_runtime)
        font = self._get_font_from_name(font_name, resolved_size, theme_runtime=theme_runtime)
        if explicit_offset not in (None, '', 0, '0'):
            font = self._change_font(font, font_name, explicit_offset, theme_runtime=theme_runtime, resolved_size=resolved_size)
        logging.debug(
            f"[Refacer][font] widget={widget_state.get('widget_key')} field={field} "
            f"font={font_name} size={getattr(font, 'size', resolved_size)} "
            f"role={fallback_role} size_offset={explicit_offset or 0}"
        )
        return font

    def _widget_icon_asset(self, widget_key, widget_state, theme_runtime=None):
        icon_name = widget_state.get('icon')
        if isinstance(icon_name, bool):
            if not icon_name:
                return None
            widget_image_name = f"{widget_key}.{widget_state.get('image_type', 'png')}"
            icon_name = widget_image_name
        if not icon_name:
            return None
        folders = [
            os.path.join('img', 'widgets'),
            os.path.join('img', widget_key),
            'img',
            '',
        ]
        return self._load_image_asset(icon_name, folders=folders, theme_runtime=theme_runtime)

    def _widget_has_theme_override(self, widget_key, widget_state, theme_bundle=None, theme_name=None):
        if (theme_name or self._theme_name) == 'Default':
            return False
        if widget_state.get('origin') == 'theme':
            return True
        options = self._theme_options(theme_bundle)
        if widget_key in ('face', 'friend_face') and options.get('faces'):
            return True
        return False

    def _stock_widget_bbox(self, widget):
        if widget is None:
            return None
        try:
            if hasattr(widget, 'get_bb'):
                bb = widget.get_bb()
                if bb and len(bb) == 4:
                    return tuple(int(v) for v in bb)
        except Exception:
            pass
        xy = getattr(widget, 'xy', None)
        if isinstance(xy, (list, tuple)) and len(xy) == 4:
            return tuple(int(v) for v in xy)
        return None

    # Use the already-rendered OG framebuffer region as fallback truth instead of replaying widget.draw on RGBA.
    def _paste_stock_widget_region(self, canvas, stock_frame, widget):
        bbox = self._stock_widget_bbox(widget)
        if bbox is None:
            logging.debug("[Refacer][fallback] stock region paste skipped")
            return False
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(canvas.width, x1))
        y1 = max(0, min(canvas.height, y1))
        x2 = max(0, min(canvas.width, x2))
        y2 = max(0, min(canvas.height, y2))
        if x2 <= x1 or y2 <= y1:
            logging.debug("[Refacer][fallback] stock region paste skipped")
            return False
        region = stock_frame.crop((x1, y1, x2, y2)).convert('RGBA')
        bg = self._stock_background_rgba()
        keyed = []
        changed = False
        threshold = 18
        for pixel in region.getdata():
            is_stock_bg = all(abs(int(pixel[i]) - int(bg[i])) <= threshold for i in range(3))
            is_white_island = pixel[0] >= 240 and pixel[1] >= 240 and pixel[2] >= 240
            if is_stock_bg or is_white_island:
                keyed.append((pixel[0], pixel[1], pixel[2], 0))
                changed = True
            else:
                keyed.append(pixel)
        if changed:
            region.putdata(keyed)
            logging.debug("[Refacer][fallback] stripped stock background from widget region")
        if region.getbbox() is None:
            logging.debug("[Refacer][fallback] stock region paste skipped")
            return False
        canvas.alpha_composite(region, (x1, y1))
        return True

    # Live widget attributes are the primary fallback truth; stock crops are only for edge-case compatibility.
    def _can_render_from_live_state(self, widget, widget_state, theme_bundle=None):
        widget_type = widget_state.get('widget_type', 'Text')
        position = widget_state.get('position', [])
        if widget_type in ('Line', 'Rect', 'FilledRect'):
            return isinstance(position, (list, tuple)) and len(position) >= 4
        if widget_type == 'Bitmap':
            if widget_state.get('live_image') is not None:
                return True
            if widget_state.get('icon'):
                return True
            value = self._widget_text_value(widget_state.get('widget_key'), widget, widget_state, theme_bundle=theme_bundle)
            return bool(value and widget_state.get('widget_key') in ('face', 'friend_face'))
        if widget_type == 'LabeledValue':
            return bool(position) and (
                widget_state.get('value') is not None
                or widget_state.get('label') is not None
                or widget_state.get('text') is not None
            )
        return bool(position) and (
            widget_state.get('value') is not None
            or widget_state.get('text') is not None
            or widget_state.get('label') is not None
            or getattr(widget, 'value', None) is not None
        )

    def _wrap_text_to_pixel_width(self, text, font, max_width_px):
        text = '' if text is None else str(text)
        if not text or font is None or max_width_px <= 0:
            return text

        wrapped_lines = []
        for raw_line in text.splitlines() or ['']:
            words = raw_line.split(' ')
            if not words:
                wrapped_lines.append('')
                continue

            current = words[0]
            for word in words[1:]:
                candidate = current + ' ' + word
                width, _height = self._text_size(font, candidate)
                if width <= max_width_px:
                    current = candidate
                else:
                    wrapped_lines.append(current)
                    current = word
            wrapped_lines.append(current)

        return '\n'.join(wrapped_lines)

    def _status_available_width(self, widget_state, position):
        width_value = widget_state.get('width')
        if width_value not in (None, '', 0, '0'):
            try:
                return max(1, int(width_value))
            except Exception:
                pass

        try:
            if isinstance(position, (list, tuple)) and len(position) >= 4:
                x1, _y1, x2, _y2 = self._shape_coords(position)
                return max(1, int(x2 - x1 - 8))
        except Exception:
            pass

        # Safe fallback for themes that only set x/y and rely on the stock center panel width.
        return max(1, int(self._canvas_size()[0] * 0.55))

    def _prepare_status_value(self, value, widget_state, position, text_font):
        value = '' if value is None else str(value)
        available_width = self._status_available_width(widget_state, position)
        return self._wrap_text_to_pixel_width(value, text_font, available_width)

    def _render_widget_layer(self, canvas, draw, widget_key, widget, widget_state, palette, diagnostics, theme_bundle=None, theme_runtime=None, frame_index=0):
        widget_type = widget_state.get('widget_type', 'Text')

        main_text_color = palette['theme_options'].get('main_text_color')
        base_text_color = palette['theme_options'].get('base_text_color')

        if main_text_color:
            raw_color_source = main_text_color
        elif widget_state.get('color'):
            raw_color_source = widget_state.get('color')
        elif base_text_color:
            raw_color_source = base_text_color
        else:
            raw_color_source = [palette['default_foreground']]

        raw_color = self._pick_color(raw_color_source, index=frame_index)
        color = self._normalize_color(raw_color or palette['default_foreground'])
        position = widget_state.get('position', [0, 0])
        if len(palette['sample_widget_colors']) < 8:
            palette['sample_widget_colors'].append({'widget': widget_key, 'raw': str(raw_color), 'resolved': color})
        logging.debug(f"[Refacer][color] widget={widget_key} index={frame_index} raw={raw_color} resolved={color}")

        if widget_type in ('Line', 'Rect', 'FilledRect'):
            if len(position) < 4:
                return
            x1, y1, x2, y2 = self._shape_coords(position)
            if widget_type == 'Line':
                draw.line([x1, y1, x2, y2], fill=color, width=int(widget_state.get('width', 1)))
            elif widget_type == 'Rect':
                draw.rectangle([x1, y1, x2, y2], outline=color, width=int(widget_state.get('width', 1)))
            else:
                draw.rectangle([x1, y1, x2, y2], fill=color)
            diagnostics.append({'widget': widget_key, 'mode': widget_type.lower(), 'origin': widget_state.get('origin'), 'position': position, 'z': widget_state.get('z_axis', 0)})
            return

        if widget_type == 'Bitmap':
            icon_image = self._resolve_bitmap_image(
                widget_key,
                widget,
                widget_state,
                color=color,
                theme_runtime=theme_runtime,
            )
            icon_image = self._apply_image_effects(icon_image, widget_state, color=color)
            if icon_image is None:
                return
            x, y, _, _ = self._pos_convert(position[0], position[1], icon_image.width, icon_image.height)
            canvas.paste(icon_image, (x, y), icon_image)
            diagnostics.append({'widget': widget_key, 'mode': 'bitmap-map', 'origin': widget_state.get('origin'), 'position': [x, y], 'z': widget_state.get('z_axis', 0)})
            return

        value = self._widget_text_value(widget_key, widget, widget_state, theme_bundle=theme_bundle)
        label = widget_state.get('label', '')
        wrap = bool(widget_state.get('wrap'))
        max_length = int(widget_state.get('max_length') or 0)
        is_multiline_input = '\n' in value

        text_font = self._widget_font(widget_state, 'text', theme_runtime=theme_runtime)
        label_font = self._widget_font(widget_state, 'label', theme_runtime=theme_runtime)

        # Status is special:
        # - never hard-truncate before layout
        # - always wrap from the full payload using pixel width
        # This prevents theme max_length from silently eating the second line.
        if widget_key == 'status':
            value = self._prepare_status_value(value, widget_state, position, text_font)
            is_multiline_input = '\n' in value
        else:
            # Generic non-status behavior keeps the theme's wrap/max_length semantics.
            if is_multiline_input:
                if max_length > 0:
                    processed_lines = []
                    for line in value.splitlines():
                        line = '' if line is None else str(line)
                        if wrap:
                            wrapped = TextWrapper(
                                width=max_length,
                                replace_whitespace=False,
                                drop_whitespace=False,
                            ).wrap(line) or ['']
                            processed_lines.extend(wrapped)
                        else:
                            if len(line) > max_length:
                                line = line[:max_length] + '...'
                            processed_lines.append(line)
                    value = '\n'.join(processed_lines)
            else:
                if max_length > 0 and len(value) > max_length:
                    value = value[:max_length] + '...'
                if wrap and max_length > 0:
                    value = '\n'.join(
                        TextWrapper(width=max_length, replace_whitespace=False).wrap(value)
                    )

        icon_image = None
        if widget_state.get('icon') and widget_type != 'LabeledValue':
            if widget_key in ('face', 'friend_face'):
                face_map_key = 'face_map' if widget_key == 'face' else 'friend_face_map'
                mapped = (widget_state.get(face_map_key) or {}).get(value)
                if mapped:
                    icon_image = mapped.get('image')
                    if icon_image is not None:
                        icon_image = icon_image.copy()
                        if widget_state.get('icon_color'):
                            icon_image = self._apply_icon_color(icon_image, color)
                    logging.debug(f"[Refacer][face] render widget={widget_key} live={value} matched={mapped.get('file')}")
                else:
                    logging.debug(f"[Refacer][face] render widget={widget_key} live={value} matched=none fallback=text")
                    if widget_state.get('icon'):
                        logging.debug(f"[Refacer][face] icon enabled but no image matched, skipping text fallback key={widget_key}")
                        return
            elif icon_image is None:
                icon_image = self._widget_icon_asset(widget_key, widget_state, theme_runtime=theme_runtime)
                icon_image = self._apply_image_effects(icon_image, widget_state, color=color)
        text_line_spacing = int(
            widget_state.get(
                'label_line_spacing',
                self._theme_options(theme_bundle).get('label_line_spacing', 0)
            )
        )
        font_spacing = int(
            widget_state.get(
                'font_spacing',
                self._theme_options(theme_bundle).get('font_spacing', 0)
            )
        )
        is_multiline_value = '\n' in value
        text_size_probe = (
            self._multiline_rgba_text(value, text_font, color, line_spacing=text_line_spacing, font_spacing=font_spacing)
            if is_multiline_value else
            self.rgba_text(value, text_font, color, font_spacing=font_spacing)
        )
        awesome_name = self.f_awesome_name if theme_runtime is None else theme_runtime.get('f_awesome_name', self.f_awesome_name)
        if widget_state.get('f_awesome') and awesome_name and widget_type != 'LabeledValue':
            awesome_size = int(widget_state.get('f_awesome_size') or getattr(text_font, 'size', 16))
            text_font = self._get_font_from_name(awesome_name, awesome_size, theme_runtime=theme_runtime)
            if is_multiline_value:
                text_size_probe = self._multiline_rgba_text(value, text_font, color, line_spacing=text_line_spacing, font_spacing=font_spacing)
            else:
                text_size_probe = self.rgba_text(value, text_font, color, font_spacing=font_spacing)

        if icon_image is not None:
            x, y, _, _ = self._pos_convert(position[0], position[1], icon_image.width, icon_image.height)
            canvas.paste(icon_image, (x, y), icon_image)
            diagnostics.append({'widget': widget_key, 'mode': 'icon', 'origin': widget_state.get('origin'), 'position': [x, y], 'z': widget_state.get('z_axis', 0)})
            if widget_key in ('face', 'friend_face'):
                return

        if label and widget_type == 'LabeledValue':
            label_mode = 'text'
            label_img = None
            label_icon = None
            resolved_label_font = label_font
            resolved_value_font = text_font
            label_text = '' if label is None else str(label)
            awesome_glyph = None

            if widget_state.get('icon'):
                if widget_state.get('f_awesome') and awesome_name and label_text:
                    awesome_glyph = self._font_awesome_label_glyph(label_text)
                    if awesome_glyph:
                        awesome_size = int(widget_state.get('f_awesome_size') or getattr(label_font, 'size', 16))
                        resolved_label_font = self._get_font_from_name(awesome_name, awesome_size, theme_runtime=theme_runtime)
                        label_mode = 'font_awesome'
                    else:
                        label_mode = 'text'
                else:
                    label_name = label_text.strip()
                    if '.' in label_name:
                        label_icon = self._load_image_asset(
                            label_name,
                            folders=[os.path.join('img', 'widgets'), os.path.join('img', widget_key), 'img', ''],
                            theme_runtime=theme_runtime,
                        )
                        label_icon = self._apply_image_effects(label_icon, widget_state, color=color)
                        if label_icon is not None:
                            label_mode = 'image'

            if label_mode == 'image' and label_icon is not None:
                lw, lh = label_icon.width, label_icon.height
            else:
                render_label = awesome_glyph if label_mode == 'font_awesome' and awesome_glyph else label_text
                label_img = self.rgba_text(render_label, resolved_label_font, color, font_spacing=font_spacing)
                lw, lh = self._text_size(resolved_label_font, render_label)
            spacing = int(widget_state.get('label_spacing', self._theme_options(theme_bundle).get('label_spacing', 9)))
            line_spacing = int(widget_state.get('label_line_spacing', self._theme_options(theme_bundle).get('label_line_spacing', 0)))
            if '\n' in value:
                value_img = self._multiline_rgba_text(value, resolved_value_font, color, line_spacing=line_spacing, font_spacing=font_spacing)
                vw = value_img.width if value_img is not None else 0
                vh = value_img.height if value_img is not None else 0
            else:
                value_img = self.rgba_text(value, resolved_value_font, color, font_spacing=font_spacing)
                vw, vh = self._text_size(resolved_value_font, value)
            # For text labels use Fancygotchi's fixed per-char offset so themes align the same way.
            # For image/FA labels use the actual measured width since char-count has no meaning.
            if label_mode == 'text':
                value_x_offset = spacing + 5 * len(label_text)
            else:
                value_x_offset = lw + spacing
            # total_width mirrors Fancygotchi: label area only (not vw) for correct keyword-anchor math.
            # vw is intentionally excluded so 'right'/'center' anchors compute the same x as Fancygotchi.
            if label_mode == 'text':
                total_width = lw + spacing + 5 * len(label_text)
            else:
                total_width = lw + spacing
            total_height = max(lh, vh) + max(0, line_spacing)
            if total_width <= 0:
                total_width = max(lw, vw, 1)
            if total_height <= 0:
                total_height = max(lh, vh, 1)
            x, y, _, _ = self._pos_convert(position[0], position[1], total_width, total_height)
            if label_mode == 'image' and label_icon is not None:
                canvas.paste(label_icon, (x, y), label_icon)
            elif label_img is not None:
                canvas.paste(label_img, (x, y), label_img)
            if value_img is not None:
                # Match Fancygotchi: v_y = y + label_line_spacing (raw, not clamped).
                # Negative line_spacing intentionally moves the value above the label baseline.
                value_y = y + line_spacing
                canvas.paste(value_img, (x + value_x_offset, value_y), value_img)
            logging.debug(
                f"[Refacer][label] widget={widget_key} mode={label_mode} label_y={y} value_y={y + line_spacing} "
                f"label_x={x} value_x={x + value_x_offset} "
                f"lh={lh} vh={vh} lw={lw} vw={vw} spacing={spacing} line_spacing={line_spacing} "
                f"code={label_text} glyph={awesome_glyph or ''} "
                f"label_font_size={getattr(resolved_label_font, 'size', '?')} "
                f"value_font_size={getattr(resolved_value_font, 'size', '?')}"
            )
            diagnostics.append({'widget': widget_key, 'mode': 'labeled_text', 'origin': widget_state.get('origin'), 'position': [x, y], 'z': widget_state.get('z_axis', 0)})
            return

        text_img = text_size_probe
        if text_img is None:
            return
        x, y, _, _ = self._pos_convert(position[0], position[1], text_img.width, text_img.height)
        canvas.paste(text_img, (x, y), text_img)
        diagnostics.append({'widget': widget_key, 'mode': 'text', 'origin': widget_state.get('origin'), 'position': [x, y], 'z': widget_state.get('z_axis', 0)})

    def _render_loop(self, generation):
        frame_counter = 0
        while self._running:
            if self._render_generation_became_stale(generation):
                return
            effective_fps = self._effective_fps()
            frame_budget = 1.0 / float(effective_fps)
            loop_start = time.perf_counter()
            watchdog_now = time.time()
            boot_now = time.monotonic()
            self._expire_recovery_cache_handoff_if_needed(watchdog_now)
            if not self.enabled:
                if self._render_generation_became_stale(generation):
                    return
                self._evaluate_render_watchdog(now=watchdog_now)
                time.sleep(0.5)
                continue

            if not self._view_instance:
                if self._render_generation_became_stale(generation):
                    return
                self._evaluate_render_watchdog(now=watchdog_now)
                time.sleep(0.1)
                continue

            acquired_cycle = self._render_cycle_lock.acquire(blocking=False)
            if not acquired_cycle:
                if self._render_generation_became_stale(generation):
                    return
                self._render_stats['frames_dropped_busy'] = int(self._render_stats.get('frames_dropped_busy', 0)) + 1
                self._update_render_tier(busy_drop=True, generation=generation)
                if self._render_generation_became_stale(generation):
                    return
                self._evaluate_render_watchdog(now=watchdog_now)
                time.sleep(frame_budget)
                continue

            frame_generation = self._reset_generation
            try:
                logging.debug("[Refacer][lock] render snapshot start")
                view_instance = self._view_instance
                with view_instance._lock:
                    if view_instance._frozen:
                        time.sleep(frame_budget)
                        continue
                    state_snapshot = self._state_mapping(view_instance._state).copy()
                    physical_width = int(view_instance._width)
                    physical_height = int(view_instance._height)
                width, height = self._canvas_size()
                logging.debug(
                    f"[Refacer][lock] render snapshot end physical={physical_width}x{physical_height} "
                    f"composed={width}x{height} rotation={self._current_rotation()}"
                )

                with self._lock:
                    theme_runtime = self._theme_runtime
                    theme_bundle = theme_runtime.get('theme_bundle', self._theme_bundle)
                    theme_assets = theme_runtime.get('assets', self._theme_assets)
                    theme_name = theme_runtime.get('theme_name', self._theme_name)
                    runtime_version = theme_runtime.get('runtime_version', self._theme_runtime_version)
                    anim_frame_index = theme_runtime.get('anim_frame_index', self._anim_frame_index)

                palette = self._resolve_render_palette(theme_bundle, theme_name=theme_name)
                self._render_palette_debug = dict(palette)
                if palette['fallback_triggered']:
                    self._theme_fallback_notice = "Theme applied with readability fallback."
                elif self._theme_fallback_notice == "Theme applied with readability fallback.":
                    self._theme_fallback_notice = None
                if palette['fallback_triggered']:
                    logging.debug(
                        f"[Refacer][render] readability fallback active theme={palette['theme']} "
                        f"bg={palette['normalized_background']} fg={palette['default_foreground']}"
                    )
                else:
                    logging.debug(
                        f"[Refacer][render] theme={palette['theme']} "
                        f"bg={palette['normalized_background']} fg={palette['default_foreground']}"
                    )
                logging.debug("[Refacer][lock] compositor start")
                canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                if self._render_startup_boot_animation_frame(canvas, now=boot_now, theme_runtime=theme_runtime):
                    next_anim_index = anim_frame_index
                else:
                    next_anim_index = self.render_refaced_frame(
                        canvas,
                        state_snapshot,
                        theme_bundle=theme_bundle,
                        palette=palette,
                        theme_assets=theme_assets,
                        theme_name=theme_name,
                        anim_frame_index=anim_frame_index,
                        runtime_version=runtime_version,
                        theme_runtime=theme_runtime,
                        frame_index=frame_counter,
                    )
                logging.debug("[Refacer][lock] compositor end")
                if self._render_generation_became_stale(generation):
                    return
                self._mark_render_progress(time.time(), composed=True, generation=generation)
                if next_anim_index is not None:
                    if self._render_generation_became_stale(generation):
                        return
                    with self._lock:
                        if self._theme_runtime.get('runtime_version') == runtime_version:
                            self._theme_runtime['anim_frame_index'] = next_anim_index
                            self._anim_frame_index = next_anim_index
                if palette['fallback_triggered']:
                    if self._render_generation_became_stale(generation):
                        return
                    self._theme_fallback_notice = "Theme applied with readability fallback."

                if self._display_timer_due(time.time()):
                    self.display_off(reason='timer')

                if self._render_generation_became_stale(generation):
                    return
                publish_ms = self._publish_final_frame(canvas, frame_counter, generation=generation)
                if self._render_generation_became_stale(generation):
                    return
                frame_ms = (time.perf_counter() - loop_start) * 1000.0
                self._render_stats['frames_ok'] = int(self._render_stats.get('frames_ok', 0)) + 1
                self._render_stats['last_frame_ms'] = frame_ms
                self._render_stats['avg_frame_ms'] = self._update_moving_average(self._render_stats.get('avg_frame_ms', 0.0), frame_ms)
                self._render_stats['current_tier'] = self._render_stats.get('current_tier', 'full')
                if self._reset_generation != frame_generation:
                    logging.debug(
                        f"[Refacer][recovery] frame {frame_counter} spanned reset generation "
                        f"{frame_generation}→{self._reset_generation}; skipping tier/pressure update"
                    )
                elif time.time() < self._post_reset_quarantine_until:
                    logging.debug(
                        f"[Refacer][recovery] frame {frame_counter} in post-reset quarantine; skipping tier/pressure update"
                    )
                elif frame_ms > (frame_budget * 1000.0):
                    self._render_stats['frames_over_budget'] = int(self._render_stats.get('frames_over_budget', 0)) + 1
                    self._update_render_tier(over_budget=True, generation=generation)
                else:
                    self._update_render_tier(successful=True, generation=generation)
            except Exception as e:
                logging.error(f"[Refacer] Render loop error: {e}")
            finally:
                if acquired_cycle:
                    try:
                        self._render_cycle_lock.release()
                    except RuntimeError:
                        pass
                if self._render_generation_is_active(generation):
                    self._evaluate_render_watchdog(now=time.time())

            frame_counter += 1
            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0.0, frame_budget - elapsed)
            if not self._display_hardware_publish_allowed():
                sleep_time = max(sleep_time, 0.75)
            time.sleep(sleep_time)

    def render_refaced_frame(self, canvas, state, theme_bundle=None, palette=None, theme_assets=None, theme_name=None, anim_frame_index=0, runtime_version=0, theme_runtime=None, frame_index=0):
        theme_bundle = theme_bundle or {}
        palette = palette or self._resolve_render_palette(theme_bundle, theme_name=theme_name)
        theme_assets = theme_assets or {'background': None, 'foreground': None, 'animated_background': []}
        theme_name = theme_name or self._theme_name
        theme_runtime = theme_runtime or self._theme_runtime
        state_map = self._state_mapping(state)
        logging.debug(
            f"[Refacer][render] state_container={type(state).__name__} "
            f"normalized={type(state_map).__name__} entries={len(state_map)}"
        )
        diagnostics = []
        draw = ImageDraw.Draw(canvas)
        stock_frame = self._get_stock_render_frame()
        stock_base_used = False
        bg_color_applied = False
        static_background_used = False
        animated_background_used = False
        foreground_used = False
        face_override_active = bool(self._theme_options(theme_bundle).get('faces')) and theme_name != 'Default'
        next_anim_index = anim_frame_index
        render_tier = self._render_stats.get('current_tier', 'full')

        logging.debug("[Refacer][render] compositor transparent base started")
        if theme_name == 'Default':
            logging.debug("[Refacer][render] default theme rendering live widgets")
        if palette.get('raw_background') not in (None, ''):
            draw.rectangle((0, 0, canvas.width, canvas.height), fill=palette['normalized_background'])
            bg_color_applied = True
        animated = theme_assets.get('animated_background', [])
        if animated:
            # Always fill with bg_color before compositing the frame so transparent
            # GIF pixels show bg_color rather than whatever the display framebuffer
            # holds. Mirrors Fancygotchi: Image.new('RGBA', size, bg_color) + paste.
            bg_fill = palette.get('normalized_background') or (255, 255, 255, 255)
            draw.rectangle((0, 0, canvas.width, canvas.height), fill=bg_fill)
            bg_color_applied = True
            frame = animated[anim_frame_index % len(animated)]
            canvas.alpha_composite(frame.convert('RGBA'))
            advance_every = 1
            if render_tier == 'reduced':
                advance_every = 2
            elif render_tier == 'minimal':
                advance_every = 4
            if (int(frame_index or 0) % advance_every) == 0:
                next_anim_index = (anim_frame_index + 1) % len(animated)
            animated_background_used = True
        if isinstance(theme_assets.get('background'), Image.Image):
            canvas.alpha_composite(theme_assets['background'].convert('RGBA'))
            static_background_used = True
        logging.debug(
            f"[Refacer][render] compositor bg_color={'applied' if bg_color_applied else 'skipped'} "
            f"animated={'applied' if animated_background_used else 'skipped'} "
            f"static={'applied' if static_background_used else 'skipped'} "
            f"bg_mode={palette.get('theme_options', {}).get('bg_mode', 'normal')} "
            f"fg_mode={palette.get('theme_options', {}).get('fg_mode', 'normal')}"
        )

        render_items = []
        widget_keys = set(self._theme_widgets(theme_bundle).keys()) | set(state_map.keys())
        for key in widget_keys:
            widget = state_map.get(key)
            runtime_state = self._widget_runtime_state(
                key,
                widget,
                theme_bundle=theme_bundle,
                theme_name=theme_name,
                theme_runtime=theme_runtime,
            )
            render_items.append((runtime_state.get('z_axis', 0), key, widget, runtime_state))

        stealth_mode = self._theme_stealth_mode(theme_bundle)
        for z_axis, key, widget, runtime_state in sorted(render_items, key=lambda item: item[0]):
            if int(z_axis or 0) < 0:
                logging.debug(f"[Refacer][render] widget hidden by negative z_axis key={key} z={z_axis}")
                continue
            if stealth_mode and int(z_axis or 0) < 100:
                logging.debug(f"[Refacer][render] widget hidden by stealth_mode key={key} z={z_axis}")
                continue
            # Default is fully Refacer-native now: render from live widget state, never from stock framebuffer crops.
            if theme_name == 'Default':
                logging.debug(f"[Refacer][render] default widget rendered from live state key={key}")
                self._render_widget_layer(
                    canvas,
                    draw,
                    key,
                    widget,
                    runtime_state,
                    palette,
                    diagnostics,
                    theme_bundle=theme_bundle,
                    theme_runtime=theme_runtime,
                    frame_index=frame_index,
                )
                continue
            if not self._widget_has_theme_override(key, runtime_state, theme_bundle=theme_bundle, theme_name=theme_name):
                if self._can_render_from_live_state(widget, runtime_state, theme_bundle=theme_bundle):
                    logging.debug(f"[Refacer][render] widget reconstructed from live state key={key}")
                    self._render_widget_layer(
                        canvas,
                        draw,
                        key,
                        widget,
                        runtime_state,
                        palette,
                        diagnostics,
                        theme_bundle=theme_bundle,
                        theme_runtime=theme_runtime,
                        frame_index=frame_index,
                    )
                    continue
                logging.debug(f"[Refacer][render] widget lacked reconstructable live state key={key}")
                if self._paste_stock_widget_region(canvas, stock_frame, widget):
                    logging.debug(f"[Refacer][render] widget used stock crop fallback key={key}")
                    diagnostics.append({'widget': key, 'mode': 'stock-frame', 'origin': 'stock-base', 'position': getattr(widget, 'xy', None), 'z': runtime_state.get('z_axis', 0)})
                    stock_base_used = True
                    continue
                diagnostics.append({'widget': key, 'mode': 'reconstruct', 'origin': 'fallback', 'position': getattr(widget, 'xy', None), 'z': runtime_state.get('z_axis', 0)})
            self._render_widget_layer(
                canvas,
                draw,
                key,
                widget,
                runtime_state,
                palette,
                diagnostics,
                theme_bundle=theme_bundle,
                theme_runtime=theme_runtime,
                frame_index=frame_index,
            )

        self._render_lightmenu_overlay(canvas, diagnostics, theme_bundle=theme_bundle, theme_runtime=theme_runtime)

        if isinstance(theme_assets.get('foreground'), Image.Image):
            canvas.alpha_composite(theme_assets['foreground'].convert('RGBA'))
            foreground_used = True
        logging.debug(f"[Refacer][render] compositor foreground={'applied' if foreground_used else 'skipped'}")

        self._render_palette_debug = {
            'active_theme': theme_name,
            'theme_snapshot_id': f"{theme_name}:{runtime_version}",
            'theme_declared_color_mode': self._theme_declared_color_mode(theme_bundle),
            'resolved_display_output_mode': self._resolve_display_output_mode(theme_bundle),
            'raw_background': palette['raw_background'],
            'normalized_background': list(palette['normalized_background']),
            'fallback_triggered': palette['fallback_triggered'],
            'sample_widget_colors': palette.get('sample_widget_colors', []),
            'assets': {
                'background': bool(theme_assets.get('background')),
                'animated_background_frames': len(theme_assets.get('animated_background', [])),
                'foreground': bool(theme_assets.get('foreground')),
            },
            'frame_sources': {
                'stock_base_used': stock_base_used,
                'bg_color_applied': bg_color_applied,
                'static_background_used': static_background_used,
                'animated_background_used': animated_background_used,
                'foreground_used': foreground_used,
                'face_override_active': face_override_active,
            },
            'fonts': {
                'font': theme_runtime.get('font_name', self.font_name),
                'font_bold': theme_runtime.get('font_bold_name', self.font_bold_name),
                'status_font': theme_runtime.get('font_status_name', self.font_status_name),
                'font_awesome': theme_runtime.get('f_awesome_name', self.f_awesome_name),
            },
            'render_order': diagnostics,
            'theme_options': palette.get('theme_options', {}),
            'resolved_main_text_colors': palette.get('resolved_main_text_colors', []),
            'resolved_base_text_colors': palette.get('resolved_base_text_colors', []),
        }
        return next_anim_index




