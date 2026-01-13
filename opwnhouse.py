from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins
import pwnagotchi
import pwnagotchi.agent
import logging
import os
import subprocess
import time
import json
from flask import render_template_string, jsonify, request
import threading
from pwnagotchi.utils import save_config
import toml
import math
from werkzeug.utils import secure_filename

INDEX = """
{% extends "base.html" %}
{% set active_page = "plugins" %}
{% block title %}Pwnagotchi House - Cracked Networks{% endblock %}
{% block meta %}
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
{% endblock %}
{% block styles %}

{{ super() }}
<style>
    #filter {
        width: 100%;
        font-size: 16px;
        padding: 12px 20px 12px 40px;
        border: 1px solid #ddd;
        margin-bottom: 12px;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        border: 1px solid #ddd;
    }
    th, td {
        text-align: left;
        padding: 12px;
    }
    tr {
        border-bottom: 1px solid #ddd;
    }
    tr.header, tr:hover {
        background-color: #f1f1f1;
    }
    .table-container {
        overflow-x: auto;
        width: 100%;
    }

    /* ASCII Scene Styles */
    #ascii-scene-container {
        position: relative;
        width: 100%;
        height: 200px;
        background-color: black;
        border: 1px solid #ccc;
        overflow-x: auto;
        white-space: nowrap;
        font-family: 'monospace', monospace;
        font-size: 12px;
        margin-bottom: 20px;
        color: lime;
        text-shadow: none !important;
    }
    #pwnagotchi-container {
        position: absolute;
        left: 2%;
        bottom: 10px;
    }
    #pwnagotchi-face {
        position: absolute;
        top: 3.25em;
        left: 2.25em;
        font-weight: bold;
    }
    .house-wrapper {
        position: absolute;
        bottom: 10px;
        text-align: center;
    }
    .tree-wrapper {
        position: absolute;
        top: -2px;
        text-align: center;
    }
    #horizon-container {
        position: absolute;
        top: 10px;
        left: 0;
        min-width: 100%;
        white-space: pre;
        z-index: 0;
    }
        .house-wrapper[data-password] {
        cursor: pointer;
    }
    tr[data-password] {
        cursor: pointer;
    }
    /* QR Code Modal Styles */
    #qr-modal {
        display: none;
        position: fixed;
        z-index: 1000;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        overflow: auto;
        background-color: rgba(0,0,0,0.6);
        justify-content: center;
        align-items: center;
    }
    .modal-content {
        background-color: #fefefe;
        margin: auto;
        padding: 20px;
        border: 1px solid #888;
        width: 80%;
        max-width: 300px;
        text-align: center;
        position: relative;
    }
    .close-button {
        color: #aaa;
        position: absolute;
        top: 10px;
        right: 15px;
        font-size: 28px;
        font-weight: bold;
        cursor: pointer;
    }
    .pagination {
        text-align: center;
        margin-top: 15px;
    }
    /* Edit Modal Styles */
    #edit-modal {
        display: none;
        position: fixed;
        z-index: 1001;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        overflow: auto;
        background-color: rgba(0,0,0,0.6);
        justify-content: center;
        align-items: center;
    }
    #edit-form-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    #edit-form-container input {
        width: 100%;
    }
    .password-chip {
        display: inline-block;
        background-color: #e0e0e0;
        padding: 5px 10px;
        border-radius: 15px;
        margin: 2px;
        cursor: pointer;
        font-family: monospace;
    }
    .password-chip:hover {
        background-color: #d0d0d0;
    }
    
    /* Radar View Styles */
    .view-mode-btn {
        padding: 5px 10px;
        margin-left: 5px;
        cursor: pointer;
        background-color: #f1f1f1;
        border: 1px solid #ccc;
        border-radius: 3px;
        font-size: 0.9em;
    }
    .view-mode-btn.active-mode {
        background-color: #333;
        color: white;
        border-color: #333;
    }
    #radar-scene-container {
        position: relative;
        width: 100%;
        height: 300px;
        background-color: #001100;
        border: 1px solid #ccc;
        overflow: hidden;
        margin-bottom: 20px;
        font-family: 'monospace', monospace;
    }
    .radar-ring {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        border: 1px dashed #004400;
        border-radius: 50%;
        pointer-events: none;
    }
    .radar-axis {
        position: absolute;
        background-color: #004400;
        pointer-events: none;
    }
    .radar-blip {
        position: absolute;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        cursor: pointer;
        z-index: 10;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 10px;
        color: black;
        font-weight: bold;
        border: 1px solid rgba(255,255,255,0.3);
    }
    .radar-blip:hover {
        z-index: 20;
        border: 1px solid white;
        transform: translate(-50%, -50%) scale(1.2);
    }
    .radar-blip.cracked { background-color: #00ff00; box-shadow: 0 0 8px #00ff00; }
    .radar-blip.locked { background-color: #ff0000; box-shadow: 0 0 5px #ff0000; }
    .radar-label {
        position: absolute;
        color: #00ff00;
        font-size: 10px;
        white-space: nowrap;
        pointer-events: none;
        text-shadow: 1px 1px 0 #000;
        transform: translate(-50%, -100%);
        margin-top: -10px;
        z-index: 15;
    }
</style>
{% endblock %}
{% block content %}
    <div data-role="navbar" data-iconpos="left">
        <ul>
            <li><a href="#" onclick="openTab(event, 'Proximity')" class="tablinks ui-btn-active" data-icon="bars">Proximity</a></li>
            <li><a href="#" onclick="openTab(event, 'CrackedList')" class="tablinks" data-icon="lock">Cracked List</a></li>
            <li><a href="#" onclick="openTab(event, 'Configuration')" class="tablinks" data-icon="gear">Configuration</a></li>
        </ul>
    </div>

    <input type="text" id="filter" onkeyup="filterTable()" placeholder="Filter by ESSID, BSSID, or password...">

    <div id="Proximity" class="tabcontent">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3>Nearby Scene</h3>
            <div>
                <button class="view-mode-btn active-mode" id="btn-landscape" onclick="switchViewMode('landscape')">Landscape</button>
                <button class="view-mode-btn" id="btn-radar" onclick="switchViewMode('radar')">Radar</button>
            </div>
        </div>
        <div id="ascii-scene-container">
            <div id="horizon-container">
                <!-- ASCII horizon will be generated here -->
            </div>
            <div id="pwnagotchi-container">
                <pre id="pwnagotchi-box">
_____________
| |         |
| |         |
|_|_________|
                </pre>
                <div id="pwnagotchi-face"></div>
            </div>
            <div id="houses-container">
                <!-- ASCII houses will be dynamically generated here -->
            </div>
            <div id="trees-container">
                <!-- ASCII trees will be dynamically generated here -->
            </div>
        </div>
        <div id="radar-scene-container" style="display:none;">
            <!-- Radar content generated by JS -->
        </div>
        <h3>Nearby Networks (List) <span id="proximity-count" style="font-weight: normal; font-size: 0.8em;"></span></h3>
        <div class="table-container">
            <table id="proximity_table"></table> <!-- Kept the table for detailed view -->
        </div>
    </div>

    <div id="CrackedList" class="tabcontent" style="display:none;">
        <h3>Complete Cracked List</h3>
        <div style="text-align: center; margin-bottom: 10px;">
            <button onclick="refreshData()" style="cursor: pointer;">Refresh Data</button>
        </div>
        <div id="cracked-list-info" style="text-align: center; margin-bottom: 10px;"></div>
        <div class="table-container">
            <table id="cracked_list_table">
                {{ cracked_list_table | safe }}
            </table>
        </div>
        <div id="cracked_list_pagination" class="pagination"></div>
    </div>

    <!-- QR Code Modal -->
    <div id="qr-modal">
        <div class="modal-content">
            <span class="close-button">&times;</span>
            <div id="qr-code-container"></div>
            <div id="qr-info" style="margin-top: 10px; font-family: monospace;"></div>
        </div>
    </div>

    <!-- Edit Network Modal -->
    <div id="edit-modal">
        <div class="modal-content">
            <span class="close-button" id="edit-close-button">&times;</span>
            <h4>Edit Network</h4>
            <div id="edit-form-container">
                <input type="hidden" id="edit-original-bssid">
                <label for="edit-essid">ESSID:</label>
                <input type="text" id="edit-essid">
                <label for="edit-bssid">BSSID:</label>
                <input type="text" id="edit-bssid">
                <label for="edit-stamac">STAMAC:</label>
                <input type="text" id="edit-stamac">
                <div id="edit-password-list-container" style="display: none; margin-top: 5px; margin-bottom: 5px;">
                    <label style="font-size: 0.9em; color: #555;">Known Passwords (click to use):</label>
                    <div id="edit-password-list"></div>
                </div>
                <label for="edit-password">Password:</label>
                <input type="text" id="edit-password">
                <button type="button" onclick="saveNetworkEdit()">Save Changes</button>
                <button type="button" onclick="refreshGps()" style="background-color: #5bc0de; color: white;">Refresh GPS</button>
                <button type="button" onclick="deleteNetwork()" style="background-color: #d9534f; color: white; margin-top: 5px;">Delete Network</button>
            </div>
            <div id="edit-status" style="margin-top: 10px;"></div>
        </div>
    </div>

    <div id="Configuration" class="tabcontent" style="display:none;">
        <h3>Plugin Configuration</h3>
        <p>Changes saved here will be written to your Pwnagotchi's main config.toml file. A restart is required for some changes to take effect.</p>
        <form id="config-form">
            <div class="config-item">
                <label for="per_page">Items per Page (Cracked List):</label>
                <input type="number" id="per_page" name="per_page"><br><br>
            </div>
            <div class="config-item">
                <label for="hunter_mode">Hunter Mode (Hot/Cold Feedback):</label>
                <select name="hunter_mode" id="hunter_mode" data-role="flipswitch">
                    <option value="false">Off</option>
                    <option value="true">On</option>
                </select><br><br>
            </div>
            <div class="config-item">
                <label for="display_stats">Display On-Screen Stats (e.g., 3/150):</label>
                <select name="display_stats" id="display_stats" data-role="flipswitch">
                    <option value="false">Off</option>
                    <option value="true">On</option>
                </select><br><br>
            </div>
            <div class="config-item">
                <label for="orientation">On-Screen Orientation:</label>
                <select id="orientation" name="orientation">
                    <option value="vertical">Vertical</option>
                    <option value="horizontal">Horizontal</option>
                </select><br><br>
            </div>
            <div class="config-item">
                <label for="position">On-Screen Position (X,Y):</label>
                <input type="text" id="position" name="position" placeholder="e.g., 0, 91"><br><br>
            </div>
            <div class="config-item">
                <label for="stats_position">Stats Position (X,Y):</label>
                <input type="text" id="stats_position" name="stats_position" placeholder="e.g., 0, 61"><br><br>
            </div>
            <div class="config-item">
                <label for="custom_dir">Custom Handshakes Directory:</label>
                <input type="text" id="custom_dir" name="custom_dir" placeholder="e.g., /path/to/handshakes"><br><br>
            </div>
            <div class="config-item">
                <label for="save_path">Consolidated Potfile Path:</label>
                <input type="text" id="save_path" name="save_path" placeholder="e.g., /root/handshakes/opwnhouse.potfile"><br><br>
            </div>

            <button type="button" onclick="saveConfiguration()">Save Configuration</button>
        </form>
        <hr>
        <h3>Import / Export</h3>
        <div class="config-item">
            <label>Export all cracked networks to a single potfile:</label>
            <a href="/plugins/opwnhouse/export" download="opwnhouse.potfile" class="ui-btn ui-corner-all ui-icon-arrow-d ui-btn-icon-left">Export Potfile</a>
        </div>
        <div class="config-item">
            <label for="import_file">Import a .potfile or .cracked file:</label>
            <form id="import-form" method="post" enctype="multipart/form-data" data-ajax="false">
                 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                 <input type="file" id="import_file" name="import_file" accept=".potfile,.cracked">
                 <button type="submit">Import File</button>
            </form>
        </div>
        <div id="import-status" style="margin-top: 15px;"></div>
        <div id="config-status" style="margin-top: 15px;"></div><hr>
        <h3>File Management</h3>
        <div class="config-item">
            <label for="delete_files">Delete .potfile or .cracked files:</label>
            <form id="delete-form" method="post" data-ajax="false">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <select name="delete_files" id="delete_files" multiple="multiple" data-native-menu="false" style="min-height: 150px;">
                    {% for file in found_files %}
                        <option value="{{ file }}">{{ file.split('/')[-1] }}</option>
                    {% endfor %}
                </select>
                <button type="submit">Delete Selected Files</button>
            </form>
            <div id="delete-status" style="margin-top: 15px;"></div>
        </div>
    </div>
{% endblock %}
{% block script %}
function refreshData() {
    const statusDiv = document.getElementById('cracked-list-info');
    statusDiv.textContent = 'Refreshing data...';
    statusDiv.style.color = 'orange';

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    fetch('/plugins/opwnhouse/refresh', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken }
    })
    .then(response => response.json())
    .then(data => {
        statusDiv.textContent = data.message;
        statusDiv.style.color = data.success ? 'green' : 'red';
        if (data.success) {
            setTimeout(() => location.reload(), 1000);
        }
    })
    .catch(error => {
        console.error('Error refreshing data:', error);
        statusDiv.textContent = 'Error refreshing data.';
        statusDiv.style.color = 'red';
    });
}

function filterTable() {
    var input, filter, table, tr, td, i, txtValue;
    input = document.getElementById("filter");
    filter = input.value.toUpperCase();

    const configTab = document.getElementById('Configuration');
    const proximityTab = document.getElementById('Proximity');
    const crackedTab = document.getElementById('CrackedList');

    if (configTab.style.display === 'block') {
        const configItems = document.querySelectorAll('#config-form .config-item');
        configItems.forEach(item => {
            const label = item.querySelector('label');
            if (label && label.textContent.toUpperCase().indexOf(filter) > -1) {
                item.style.display = "";
            } else {
                item.style.display = "none";
            }
        });
    } else {
        filter = filter.replace(/:/g, '');
        table = document.querySelector(".tabcontent[style*='display: block'] table");
        if (!table) return;
        tr = table.getElementsByTagName("tr");
        for (i = 1; i < tr.length; i++) {
            tds = tr[i].getElementsByTagName("td");
            var found = false;
            for (var j = 0; j < tds.length; j++) {
                td = tds[j];
                if (td) {
                    txtValue = (td.textContent || td.innerText).replace(/:/g, '');
                    if (txtValue.toUpperCase().indexOf(filter) > -1) {
                        found = true;
                        break;
                    }
                }
            }
            if (found) {
                tr[i].style.display = "";
            } else {
                tr[i].style.display = "none";
            }
        }
        if (table.id === 'cracked_list_table') {
            setupCrackedListPagination();
            showCrackedListPage(1);
        }
    }
}

function openTab(evt, tabName) {
    var i, tabcontent, tablinks;
    const filterInput = document.getElementById('filter');

    tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].classList.remove("ui-btn-active");
    }
    document.getElementById(tabName).style.display = "block";
    if(evt) {
      evt.currentTarget.classList.add("ui-btn-active");
    }

    if (tabName === 'Configuration') {
        filterInput.placeholder = "Filter by option...";
        setTimeout(loadConfiguration, 50);
        if (window.jQuery && window.jQuery.fn.selectmenu) {
            setTimeout(() => jQuery('#delete_files').selectmenu('refresh'), 100);
        }
    } else {
        filterInput.placeholder = "Filter by ESSID, BSSID, or password...";
    }
}

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('Proximity').style.display = 'block';
});


const crackedTable = document.getElementById('cracked_list_table');
const paginationContainer = document.getElementById('cracked_list_pagination');
const crackedListInfo = document.getElementById('cracked-list-info');
const itemsPerPage = {{ per_page }};
let currentPage = 1;

function showCrackedListPage(page) {
    const allRows = crackedTable.querySelectorAll('tbody tr');
    const filter = document.getElementById("filter").value.toUpperCase().replace(/:/g, '');
    const visibleRows = Array.from(allRows).filter(row => {
        const txtValue = (row.textContent || row.innerText).replace(/:/g, '');
        return txtValue.toUpperCase().indexOf(filter) > -1;
    });

    currentPage = page;
    allRows.forEach(row => row.style.display = 'none');
    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    visibleRows.slice(startIndex, endIndex).forEach(row => {
        row.style.display = ''; 
    });

    const startItem = visibleRows.length > 0 ? startIndex + 1 : 0;
    const endItem = Math.min(endIndex, visibleRows.length);
    if (crackedListInfo) {
        crackedListInfo.textContent = `Showing ${startItem} to ${endItem} of ${visibleRows.length} networks`;
    }

    const prevButton = document.getElementById('prevPageBtn');
    const nextButton = document.getElementById('nextPageBtn');
    if (prevButton) prevButton.disabled = (currentPage === 1);
    if (nextButton) nextButton.disabled = (currentPage === Math.ceil(visibleRows.length / itemsPerPage));


    const paginationButtons = paginationContainer.querySelectorAll('button');
    paginationButtons.forEach(button => {
        button.classList.remove('active');
        if (parseInt(button.textContent) === page) {
            button.classList.add('active');
        }
    });

    const pageInput = document.getElementById('pageInput');
    if (pageInput) {
        pageInput.value = currentPage;
    }
}

function setupCrackedListPagination() {
    const allRows = crackedTable.querySelectorAll('tbody tr');
    const filter = document.getElementById("filter").value.toUpperCase().replace(/:/g, '');
    const visibleRows = Array.from(allRows).filter(row => {
        const txtValue = (row.textContent || row.innerText).replace(/:/g, '');
        return txtValue.toUpperCase().indexOf(filter) > -1;
    });
    const pageCount = Math.ceil(visibleRows.length / itemsPerPage);
    paginationContainer.innerHTML = '';

    if (pageCount > 1) {
        const prevButton = document.createElement('button');
        prevButton.id = 'prevPageBtn';
        prevButton.textContent = 'Previous';
        prevButton.onclick = () => showCrackedListPage(currentPage - 1);
        paginationContainer.appendChild(prevButton);

        if (pageCount > 10) {
            const pageInput = document.createElement('input');
            pageInput.type = 'number';
            pageInput.id = 'pageInput';
            pageInput.min = 1;
            pageInput.max = pageCount;
            pageInput.style.width = '60px';
            pageInput.style.textAlign = 'center';

            const goButton = document.createElement('button');
            goButton.textContent = 'Go';
            goButton.onclick = () => {
                const pageNum = parseInt(pageInput.value, 10);
                if (pageNum >= 1 && pageNum <= pageCount) {
                    showCrackedListPage(pageNum);
                }
            };
            paginationContainer.appendChild(pageInput);
            paginationContainer.appendChild(goButton);
        } else {
            for (let i = 1; i <= pageCount; i++) {
                const btn = document.createElement('button');
                btn.innerText = i;
                btn.addEventListener('click', () => showCrackedListPage(i));
                paginationContainer.appendChild(btn);
            }
        }
        const nextButton = document.createElement('button');
        nextButton.id = 'nextPageBtn';
        nextButton.textContent = 'Next';
        nextButton.onclick = () => showCrackedListPage(currentPage + 1);
        paginationContainer.appendChild(nextButton);
    }
}


document.addEventListener('DOMContentLoaded', () => {
    setupCrackedListPagination();
    showCrackedListPage(1);
    generateHorizon();
});

function generateHorizon() {
    const horizonContainer = document.getElementById('horizon-container');
    const treesContainer = document.getElementById('trees-container');
    const sceneContainer = document.getElementById('ascii-scene-container');

    treesContainer.innerHTML = '';

    const tempSpan = document.createElement('span');
    tempSpan.textContent = 'M';
    sceneContainer.appendChild(tempSpan);
    const charWidth = tempSpan.offsetWidth;
    sceneContainer.removeChild(tempSpan);

    const sceneWidthPx = sceneContainer.scrollWidth;
    const numChars = charWidth > 0 ? Math.ceil(sceneWidthPx / charWidth) : 200;

    const trees = [
        "__\\n(__)\\n_Y_",
        "__\\n{__}\\n_|_",
        " \\n/\\\ \\n/\\\/\\\ ",
        "/\\\ \\n/\\\/\\\ \\n|",
    ];

    for (let i = 0; i < numChars; i++) {
        if (Math.random() < 0.05) { 
            const treeArt = trees[Math.floor(Math.random() * trees.length)];
            const treeWrapper = document.createElement('div');
            treeWrapper.className = 'tree-wrapper';
            const treePre = document.createElement('pre');
            treePre.textContent = treeArt;
            treeWrapper.appendChild(treePre);

            const positionPx = i * charWidth;
            treeWrapper.style.left = `${positionPx}px`;
            treesContainer.appendChild(treeWrapper);

            const treeWidthChars = Math.max(...treeArt.split('\\n').map(line => line.length));
            i += treeWidthChars;
        }
    }

    const details = ['__', '___','____', '________', '_\\\!/_', '_/\\\_', '_.*._'];
    let groundLine = '';
    let i = 0;
    while (i < numChars) {
        const detail = details[Math.floor(Math.random() * details.length)];
        groundLine += detail;
        i += detail.length;
    }
    horizonContainer.style.width = `${numChars * charWidth}px`;
    horizonContainer.textContent = `\n\n${groundLine}`;
}

function showQrCode(essid, password) {
    if (!password) return;

    const modal = document.getElementById('qr-modal');
    const qrContainer = document.getElementById('qr-code-container');
    const qrInfo = document.getElementById('qr-info');
    const closeBtn = document.querySelector('.close-button');

    qrContainer.innerHTML = '';
    qrInfo.textContent = '';

    const wifiString = `WIFI:T:WPA;S:${essid};P:${password};;`;

    qrContainer.appendChild(kjua({
        text: wifiString,
        render: 'svg',
        size: 256,
    }));
    qrInfo.textContent = `SSID: ${essid}`;

    modal.style.display = 'flex';

    closeBtn.onclick = () => modal.style.display = 'none';

    window.onclick = (event) => {
        if (event.target == modal) modal.style.display = 'none';
    };
}

function showEditModal(essid, bssid, stamac, password) {
    const modal = document.getElementById('edit-modal');
    const closeBtn = document.getElementById('edit-close-button');

    document.getElementById('edit-original-bssid').value = bssid;
    document.getElementById('edit-essid').value = essid;
    document.getElementById('edit-bssid').value = bssid;
    document.getElementById('edit-stamac').value = stamac;
    document.getElementById('edit-password').value = password;
    document.getElementById('edit-password-list-container').style.display = 'none';
    document.getElementById('edit-status').textContent = '';

    modal.style.display = 'flex';

    closeBtn.onclick = () => modal.style.display = 'none';

    window.onclick = (event) => {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    };

    // Fetch details (passwords, etc)
    fetch('/plugins/opwnhouse/details?bssid=' + encodeURIComponent(bssid))
        .then(response => response.json())
        .then(data => {
            if (data.success && data.data && data.data.passwords && data.data.passwords.length > 0) {
                const listContainer = document.getElementById('edit-password-list');
                listContainer.innerHTML = '';
                const uniquePasswords = [...new Set(data.data.passwords)];
                
                uniquePasswords.forEach(pwd => {
                    const chip = document.createElement('span');
                    chip.className = 'password-chip';
                    chip.textContent = pwd;
                    chip.onclick = function() {
                        document.getElementById('edit-password').value = pwd;
                    };
                    listContainer.appendChild(chip);
                });
                document.getElementById('edit-password-list-container').style.display = 'block';
            }
        });
}

function deleteNetwork() {
    const bssid = document.getElementById('edit-original-bssid').value;
    if (!confirm('Are you sure you want to delete this network? This will remove it from all potfiles.')) {
        return;
    }

    const statusDiv = document.getElementById('edit-status');
    statusDiv.textContent = 'Deleting...';
    statusDiv.style.color = 'orange';

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    const formData = new FormData();
    formData.append('bssid', bssid);

    fetch('/plugins/opwnhouse/delete_network', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: formData,
    })
    .then(response => response.json())
    .then(result => {
        statusDiv.textContent = result.message;
        statusDiv.style.color = result.success ? 'green' : 'red';
        if (result.success) {
            setTimeout(() => {
                document.getElementById('edit-modal').style.display = 'none';
                location.reload();
            }, 1500);
        }
    })
    .catch(error => {
        statusDiv.textContent = 'Error deleting network: ' + error;
        statusDiv.style.color = 'red';
    });
}

function saveNetworkEdit() {
    const statusDiv = document.getElementById('edit-status');
    const original_bssid = document.getElementById('edit-original-bssid').value;
    const data = {
        essid: document.getElementById('edit-essid').value,
        bssid: document.getElementById('edit-bssid').value,
        stamac: document.getElementById('edit-stamac').value,
        password: document.getElementById('edit-password').value,
    };

    statusDiv.textContent = 'Saving...';
    statusDiv.style.color = 'orange';

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    const formData = new FormData();
    formData.append('original_bssid', original_bssid);
    for (const key in data) {
        formData.append(key, data[key]);
    }

    fetch('/plugins/opwnhouse/edit', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: formData,
    })
    .then(response => response.json())
    .then(result => {
        statusDiv.textContent = result.message;
        statusDiv.style.color = result.success ? 'green' : 'red';
        if (result.success) {
            setTimeout(() => {
                document.getElementById('edit-modal').style.display = 'none';
                // This is a simple way to refresh the page and see the changes.
                // A more advanced implementation could update the table row directly.
                location.reload();
            }, 1500);
        }
    })
    .catch(error => {
        statusDiv.textContent = 'Error saving network: ' + error;
        statusDiv.style.color = 'red';
    });
}

function refreshGps() {
    const bssid = document.getElementById('edit-original-bssid').value;
    if (!bssid) {
        alert('BSSID not found.');
        return;
    }

    const statusDiv = document.getElementById('edit-status');
    statusDiv.textContent = 'Refreshing GPS data...';
    statusDiv.style.color = 'orange';

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    const formData = new FormData();
    formData.append('bssid', bssid);

    fetch('/plugins/opwnhouse/refresh_gps', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: formData,
    })
    .then(response => response.json())
    .then(result => {
        statusDiv.textContent = result.message;
        statusDiv.style.color = result.success ? 'green' : 'red';
        if (result.success) {
            setTimeout(() => {
                document.getElementById('edit-modal').style.display = 'none';
                location.reload();
            }, 1500);
        }
    })
    .catch(error => {
        statusDiv.textContent = 'Error refreshing GPS: ' + error;
        statusDiv.style.color = 'red';
    });
}

function loadConfiguration() {
    fetch('/plugins/opwnhouse/config')
        .then(response => response.json())
        .then(config => {
            console.log('Config loaded:', config);

            const flipswitch = document.getElementById('display_stats');
            if (flipswitch) {
                flipswitch.value = String(!!config.display_stats);
                if (window.jQuery && window.jQuery.fn.flipswitch) {
                    jQuery(flipswitch).flipswitch('refresh');
                }
            }

            const hunterSwitch = document.getElementById('hunter_mode');
            if (hunterSwitch) {
                hunterSwitch.value = String(!!config.hunter_mode);
                if (window.jQuery && window.jQuery.fn.flipswitch) {
                    jQuery(hunterSwitch).flipswitch('refresh');
                }
            }

            const orientationSelect = document.getElementById('orientation');
            if (orientationSelect) {
                orientationSelect.value = config.orientation || 'vertical';
                if (window.jQuery && window.jQuery.fn.selectmenu) {
                    jQuery(orientationSelect).selectmenu('refresh');
                }
            }

            document.getElementById('per_page').value = config.per_page || 20;
            document.getElementById('position').value = Array.isArray(config.position) ? config.position.join(', ') : (config.position || '');
            document.getElementById('stats_position').value = Array.isArray(config.stats_position) ? config.stats_position.join(', ') : (config.stats_position || '');
            document.getElementById('custom_dir').value = config.custom_dir || '';
            document.getElementById('save_path').value = config.save_path || '';
        })
        .catch(error => console.error('Error loading config:', error));
}

function saveConfiguration() {
    const form = document.getElementById('config-form');
    const statusDiv = document.getElementById('config-status');
    const data = {
        per_page: parseInt(document.getElementById('per_page').value, 10),
        display_stats: document.getElementById('display_stats').value === 'true',
        hunter_mode: document.getElementById('hunter_mode').value === 'true',
        orientation: document.getElementById('orientation').value,
        position: document.getElementById('position').value,
        stats_position: document.getElementById('stats_position').value,
        custom_dir: document.getElementById('custom_dir').value,
        save_path: document.getElementById('save_path').value,
    };

    statusDiv.textContent = 'Saving...';
    statusDiv.style.color = 'orange';

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    const formData = new FormData();
    for (const key in data) {
        formData.append(key, data[key]);
    }

    fetch('/plugins/opwnhouse/config', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        },
        body: formData,
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status} - ${response.statusText}`);
        }
        return response.json();
    })
    .then(result => {
        statusDiv.textContent = result.message;
        statusDiv.style.color = result.success ? 'green' : 'red';
    })
    .catch(error => {
        statusDiv.textContent = 'Error saving configuration: ' + error;
        statusDiv.style.color = 'red';
    });
}

function updateFileList() {
    const statusDiv = document.getElementById('delete-status');
    statusDiv.textContent = 'Refreshing file list...';
    statusDiv.style.color = 'orange';

    fetch('/plugins/opwnhouse/files')
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('delete_files');
            select.innerHTML = ''; 
            if (data.files && data.files.length > 0) {
                data.files.forEach(file => {
                    const option = document.createElement('option');
                    option.value = file;
                    option.textContent = file.split('/').pop();
                    select.appendChild(option);
                });
            } else {
                const option = document.createElement('option');
                option.textContent = 'No files found';
                option.disabled = true;
                select.appendChild(option);
            }
            if (window.jQuery && window.jQuery.fn.selectmenu) {
                jQuery(select).selectmenu('refresh');
            }
            statusDiv.textContent = 'File list updated.';
            statusDiv.style.color = 'green';
            setTimeout(() => { statusDiv.textContent = ''; }, 3000);
        })
        .catch(error => {
            console.error('Error updating file list:', error);
            statusDiv.textContent = 'Error refreshing file list.';
            statusDiv.style.color = 'red';
        });
}

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('import-form').addEventListener('submit', function(event) {
        event.preventDefault();
        const statusDiv = document.getElementById('import-status');
        const formData = new FormData(this);
        const fileInput = document.getElementById('import_file');

        if (!fileInput.files || fileInput.files.length === 0) {
            statusDiv.textContent = 'Please select a file to import.';
            statusDiv.style.color = 'red';
            return;
        }

        statusDiv.textContent = 'Importing...';
        statusDiv.style.color = 'orange';

        fetch('/plugins/opwnhouse/import', {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': formData.get('csrf_token') }
        })
        .then(response => response.json())
        .then(data => {
            statusDiv.textContent = data.message;
            statusDiv.style.color = data.success ? 'green' : 'red';
            if (data.success) {
                updateFileList();
            }
        })
        .catch(error => {
            console.error('Error importing file:', error);
            statusDiv.textContent = 'An unexpected error occurred during import.';
            statusDiv.style.color = 'red';
        });
    });

    document.getElementById('delete-form').addEventListener('submit', function(event) {
        event.preventDefault();
        const statusDiv = document.getElementById('delete-status');
        const selectedOptions = Array.from(document.getElementById('delete_files').selectedOptions);

        if (selectedOptions.length === 0) {
            alert('Please select at least one file to delete.');
            return;
        }

        if (!confirm(`Are you sure you want to permanently delete ${selectedOptions.length} file(s)?`)) {
            return;
        }

        statusDiv.textContent = 'Deleting...';
        statusDiv.style.color = 'orange';
        const formData = new FormData(this);

        fetch('/plugins/opwnhouse/delete', { method: 'POST', body: formData, headers: { 'X-CSRFToken': formData.get('csrf_token') }})
        .then(response => response.json())
        .then(data => {
            statusDiv.textContent = data.message;
            statusDiv.style.color = data.success ? 'green' : 'red';
            if (data.success) {
                updateFileList();
            }
        });
    });
});

let currentViewMode = 'landscape';

function switchViewMode(mode) {
    currentViewMode = mode;
    document.getElementById('ascii-scene-container').style.display = mode === 'landscape' ? 'block' : 'none';
    document.getElementById('radar-scene-container').style.display = mode === 'radar' ? 'block' : 'none';
    document.getElementById('btn-landscape').className = mode === 'landscape' ? 'view-mode-btn active-mode' : 'view-mode-btn';
    document.getElementById('btn-radar').className = mode === 'radar' ? 'view-mode-btn active-mode' : 'view-mode-btn';
    updateProximityTable();
}

function updateProximityTable() {
    fetch('/plugins/opwnhouse/json')
        .then(response => response.json())
        .then(data => {
            const table = document.getElementById('proximity_table');
            let tableContent = '<thead><tr><th>ESSID</th><th>BSSID</th><th>STAMAC</th><th>Password</th><th>GPS</th><th>RSSI</th><th>Trend</th><th>Actions</th></tr></thead><tbody>';
            if (!data.nearby_aps || data.nearby_aps.length === 0) {
                tableContent += '<tr><td colspan="8">No networks detected in proximity.</td></tr>';
            } else {
                data.nearby_aps.forEach(net => {
                    const essid = net.essid || '';
                    const bssid = net.bssid || '';
                    const password = net.password || '';
                    const stamac = net.stamac || '';
                    const passwordDisplay = password ? password : '<em>N/A</em>';
                    const stamacDisplay = stamac ? stamac : '<em>N/A</em>';
                    const gpsDisplay = net.gps || '<em>N/A</em>';
                    
                    let trendDisplay = '-';
                    if (net.trend === 'HOTTER') trendDisplay = '<span style="color:red; font-weight:bold;">HOTTER 🔥</span>';
                    else if (net.trend === 'COLDER') trendDisplay = '<span style="color:blue; font-weight:bold;">COLDER 🥶</span>';
                    else if (net.trend === 'STEADY') trendDisplay = '<span style="color:gray;">STEADY</span>';

                    const js_essid = essid.replace(/'/g, "\\'");
                    const js_bssid = bssid.replace(/'/g, "\\'");
                    const js_password = password.replace(/'/g, "\\'");
                    const js_stamac = stamac.replace(/'/g, "\\'");

                    if (net.password) {
                        tableContent += `<tr data-password="true" onclick="showQrCode('${js_essid}', '${js_password}')">`;
                    } else {
                        tableContent += '<tr>';
                    }
                    const editButton = `<button onclick="event.stopPropagation(); showEditModal('${js_essid}', '${js_bssid}', '${js_stamac}', '${js_password}')">Edit</button>`;
                    tableContent += `<td>${essid}</td><td>${bssid}</td><td>${stamacDisplay}</td><td>${passwordDisplay}</td><td>${gpsDisplay}</td><td>${net.rssi}</td><td>${trendDisplay}</td><td>${editButton}</td></tr>`;
                });
            }
            tableContent += '</tbody>';
            table.innerHTML = tableContent;
            document.getElementById('proximity-count').textContent = `(${data.total_nearby_cracked} cracked / ${data.total_cracked} total)`;
            if (document.getElementById('Proximity').style.display === 'block') {
                filterTable();
            }

            // Filter APs for scenes based on the search bar
            let filtered_aps = data.nearby_aps;
            const filterInput = document.getElementById("filter");
            if (filterInput && filterInput.value) {
                const filter = filterInput.value.toUpperCase().replace(/:/g, '');
                if (filter) {
                    filtered_aps = data.nearby_aps.filter(net => {
                        const essid = (net.essid || '').toUpperCase();
                        const bssid = (net.bssid || '').replace(/:/g, '').toUpperCase();
                        const password = (net.password || '').toUpperCase();
                        return essid.includes(filter) || bssid.includes(filter) || password.includes(filter);
                    });
                }
            }

            if (currentViewMode === 'radar') {
                generateRadar(filtered_aps, data.pwnagotchi_face, data.movement_bearing);
                return;
            }

            const scene = document.getElementById('houses-container');
            scene.innerHTML = ''; 
            const pwnagotchiFaceEl = document.getElementById('pwnagotchi-face');
            pwnagotchiFaceEl.innerText = data.pwnagotchi_face || '(◕‿‿◕)';

            const houseCracked = `    _____\n     / \\\   \\\|\n     /   \\\___\\\ \n    _|🔓|__|_`;
            const houseLocked = `    _____\n     / \\\   \\\|\n     /   \\\___\\\ \n    _|🔒|__|_`;

            let lastPositionPx = 0;
            const sceneWidthPx = scene.clientWidth;

            filtered_aps.forEach(net => {
                if (net.rssi >= -90 && (net.essid && net.essid.trim() !== '<hidden>' || net.password)) {
                    const tempHouseWrapper = document.createElement('div');
                    tempHouseWrapper.className = 'house-wrapper';
                    tempHouseWrapper.style.visibility = 'hidden';
                    const houseArt = document.createElement('pre');
                    houseArt.textContent = net.password ? houseCracked : houseLocked;
                    tempHouseWrapper.appendChild(houseArt);
                    scene.appendChild(tempHouseWrapper);
                    const houseWidthPx = tempHouseWrapper.offsetWidth;
                    scene.removeChild(tempHouseWrapper);

                    const houseWrapper = document.createElement('div');
                    houseWrapper.className = 'house-wrapper';

                    const finalHouseArt = document.createElement('pre');
                    finalHouseArt.textContent = net.password ? houseCracked : houseLocked;

                    const essidLabel = document.createElement('div');
                    let trendSymbol = '';
                    if (net.trend === 'HOTTER') {
                        trendSymbol = '🔥 ';
                    } else if (net.trend === 'COLDER') {
                        trendSymbol = '🥶 ';
                    }
                    essidLabel.textContent = `${trendSymbol}${net.essid}`;

                    if (net.password) {
                        houseWrapper.dataset.essid = net.essid;
                        houseWrapper.dataset.password = net.password;
                        houseWrapper.onclick = () => showQrCode(net.essid, net.password);
                    }
                    const minRssi = -90, maxRssi = -29;
                    const minPosPercent = 15, maxPosPercent = 95;
                    const normalizedRssi = Math.max(0, Math.min(1, (net.rssi - minRssi) / (maxRssi - minRssi)));
                    let idealPositionPx = (maxPosPercent - (normalizedRssi * (maxPosPercent - minPosPercent))) / 100 * sceneWidthPx;

                    if (idealPositionPx < lastPositionPx) {
                        idealPositionPx = lastPositionPx;
                    }

                    houseWrapper.style.left = `${idealPositionPx}px`;
                    houseWrapper.appendChild(finalHouseArt);
                    houseWrapper.appendChild(essidLabel);
                    scene.appendChild(houseWrapper);

                    lastPositionPx = idealPositionPx + houseWidthPx + 10; 
                }
            });
            generateHorizon();
        })
        .catch(error => console.error('Error fetching proximity data:', error));
}

function generateRadar(aps, pwnFace, bearing) {
    const container = document.getElementById('radar-scene-container');
    container.innerHTML = '';
    
    const width = container.clientWidth;
    const height = container.clientHeight;
    const centerX = width / 2;
    const centerY = height / 2;
    const minRadius = 30; // Keep blips out of the very center
    const maxRadius = Math.min(width, height) / 2 - 20;

    // Draw rings
    [0.25, 0.5, 0.75, 1].forEach(scale => {
        const ring = document.createElement('div');
        ring.className = 'radar-ring';
        ring.style.width = `${maxRadius * 2 * scale}px`;
        ring.style.height = `${maxRadius * 2 * scale}px`;
        container.appendChild(ring);
    });
    
    // Draw axes
    const hAxis = document.createElement('div');
    hAxis.className = 'radar-axis';
    hAxis.style.width = '100%';
    hAxis.style.height = '1px';
    hAxis.style.top = '50%';
    container.appendChild(hAxis);
    
    const vAxis = document.createElement('div');
    vAxis.className = 'radar-axis';
    vAxis.style.width = '1px';
    vAxis.style.height = '100%';
    vAxis.style.left = '50%';
    container.appendChild(vAxis);

    // Draw cardinal points
    const h_padding = (width - (2 * maxRadius)) / 2;
    const cardinal_pos = Math.max(5, h_padding - 15); // Position from edge, accounting for char width + 5px margin from circle

    const cardinals = {
        'N': { top: '5px', left: '50%', transform: 'translateX(-50%)' },
        'S': { bottom: '5px', left: '50%', transform: 'translateX(-50%)' },
        'W': { top: '50%', left: `${cardinal_pos}px`, transform: 'translateY(-50%)' },
        'E': { top: '50%', right: `${cardinal_pos}px`, transform: 'translateY(-50%)' }
    };

    for (const dir in cardinals) {
        const label = document.createElement('div');
        label.textContent = dir;
        label.style.position = 'absolute';
        label.style.color = 'white';
        label.style.textShadow = '1px 1px 0 #000';
        label.style.fontSize = '12px';
        label.style.fontWeight = 'bold';
        Object.assign(label.style, cardinals[dir]);
        container.appendChild(label);
    }

    // Center Face
    const centerEl = document.createElement('div');
    centerEl.style.position = 'absolute';
    centerEl.style.top = '50%';
    centerEl.style.left = '50%';
    centerEl.style.transform = 'translate(-50%, -50%)';
    centerEl.style.color = 'white';
    centerEl.style.fontWeight = 'bold';
    centerEl.innerText = pwnFace || '(◕‿‿◕)';
    container.appendChild(centerEl);

    // Draw movement arrow if bearing is available
    if (bearing !== null && bearing !== undefined) {
        const arrow = document.createElement('div');
        arrow.style.position = 'absolute';
        arrow.style.width = '0';
        arrow.style.height = '0';
        arrow.style.borderLeft = '8px solid transparent';
        arrow.style.borderRight = '8px solid transparent';
        arrow.style.borderBottom = '16px solid #00ffff';
        arrow.style.zIndex = '5';

        const rad = bearing * (Math.PI / 180);
        const r = maxRadius + 10;
        const arrowX = centerX + r * Math.sin(rad);
        const arrowY = centerY - r * Math.cos(rad);

        arrow.style.left = `${arrowX}px`;
        arrow.style.top = `${arrowY}px`;
        arrow.style.transform = `translate(-50%, -50%) rotate(${bearing}deg)`;
        container.appendChild(arrow);
    }

    aps.forEach(net => {
        const minRssi = -95;
        const maxRssi = -30;
        let normalized = (net.rssi - minRssi) / (maxRssi - minRssi);
        normalized = Math.max(0, Math.min(1, normalized));
        const distance = minRadius + (1 - normalized) * (maxRadius - minRadius);
        
        // Deterministic angle based on BSSID
        const bssidHex = (net.bssid || '').replace(/:/g, '').substr(-6);
        const angleDeg = parseInt(bssidHex || '0', 16) % 360;
        const angleRad = angleDeg * (Math.PI / 180);
        
        const x = centerX + distance * Math.cos(angleRad);
        const y = centerY + distance * Math.sin(angleRad);
        
        const blip = document.createElement('div');
        blip.className = `radar-blip ${net.password ? 'cracked' : 'locked'}`;
        blip.style.left = `${x}px`;
        blip.style.top = `${y}px`;
        blip.title = `${net.essid} (${net.rssi} dBm)`;
        blip.innerText = net.password ? '🔓' : '🔒';
        if (net.password) blip.onclick = () => showQrCode(net.essid, net.password);
        
        const label = document.createElement('div');
        label.className = 'radar-label';
        label.style.left = `${x}px`;
        label.style.top = `${y}px`;
        let trendSymbol = net.trend === 'HOTTER' ? '🔥' : (net.trend === 'COLDER' ? '🥶' : '');
        label.innerText = `${trendSymbol} ${net.essid}`;
        
        container.appendChild(blip);
        container.appendChild(label);
    });
}

setInterval(updateProximityTable, 5000);
document.addEventListener('DOMContentLoaded', updateProximityTable);
window.addEventListener('resize', () => {
    if (currentViewMode === 'landscape') generateHorizon();
    else updateProximityTable(); // Redraw radar on resize
});
{% endblock %}
"""

class OpwnHouse(plugins.Plugin):
    __author__ = '@V0rT3x'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin to display closest cracked networks & their passwords'

    def __init__(self):
        """
        Initializes the OpwnHouse plugin.
        - Sets up initial state variables.
        - ready: A flag to indicate if the plugin has finished its initial loading.
        - cracked_networks: A list to hold all parsed cracked network data.
        - all_nearby_aps: A list to hold all access points seen in the last Wi-Fi scan.
        """
        self.ready = False
        self.cracked_networks = []
        self.nearby_cracks = []
        self.all_found_files = []
        self.all_nearby_aps = []
        self.rssi_history = {}
        self.lock = threading.Lock()
        self.wifi_update_thread = None
        self.latest_access_points = None
        self.stop_thread = threading.Event()
        self.last_wpasec_crack = None
        self._rssi = -1000
        self._bssid = ''
        self._essid = ''
        self._password = ''
        self._trend = 'STEADY'
        self._current_gps = None
        self._ref_gps = None
        self._ref_rssi = None
        self._ref_bssid = None
        self._direction_text = '?'
        self._movement_bearing = None
        self.total_nearby_cracked = 0
        self.last_wifi_update = '00:00'
        self.last_iwconfig_check = 0
        self.is_not_associated = True
        self.pwnagotchi_face = '(◕‿‿◕)'
        self._agent = None
        self.config_path = '/etc/pwnagotchi/config.toml'
        self.companion_data = {}
        self.json_path = ''

    def _format_mac(self, mac_string):
        """Formats a MAC address string into the standard colon-separated format."""
        if not mac_string or not isinstance(mac_string, str) or ':' in mac_string:
            return mac_string
        mac_string = mac_string.replace(':', '').upper()
        return ':'.join(mac_string[i:i+2] for i in range(0, len(mac_string), 2))

    def _is_gps_enabled(self):
        return pwnagotchi.config['main']['plugins'].get('gps', {}).get('enabled', False)

    def _enrich_with_gps(self, search_dirs):
        gps_files = {}
        for d in search_dirs:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith('.gps.json'):
                        try:
                            base = f[:-9]
                            parts = base.split('_')
                            if len(parts) >= 2:
                                bssid_str = parts[-1]
                                if len(bssid_str) == 12:
                                    try:
                                        int(bssid_str, 16)
                                        gps_files[bssid_str.lower()] = os.path.join(d, f)
                                    except ValueError:
                                        pass
                        except Exception:
                            continue
        
        updated_count = 0
        for bssid_plain, filepath in gps_files.items():
            formatted_mac = self._format_mac(bssid_plain)
            
            if formatted_mac in self.companion_data:
                try:
                    with open(filepath, 'r') as f:
                        gps_data = json.load(f)
                    
                    lat = gps_data.get("Latitude")
                    lon = gps_data.get("Longitude")
                    
                    if lat is None or lon is None:
                        continue

                    new_entry = {
                        "latitude": lat,
                        "longitude": lon,
                        "altitude": gps_data.get("Altitude", 0),
                        "timestamp": gps_data.get("Updated", "")
                    }
                    
                    if not new_entry["timestamp"]:
                         mtime = os.path.getmtime(filepath)
                         new_entry['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(mtime))

                    if "gps_locations" not in self.companion_data[formatted_mac]:
                        self.companion_data[formatted_mac]["gps_locations"] = []
                    
                    existing_locs = self.companion_data[formatted_mac]["gps_locations"]
                    
                    is_duplicate = False
                    for loc in existing_locs:
                        if loc.get("latitude") == lat and loc.get("longitude") == lon:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        self.companion_data[formatted_mac]["gps_locations"].append(new_entry)
                        updated_count += 1
                        
                except Exception as e:
                    logging.error(f"[opwnhouse] Error processing GPS file {filepath}: {e}")
        
        if updated_count > 0:
            logging.info(f"[opwnhouse] Enriched {updated_count} networks with GPS data")

    def _ensure_pcap_cracked_files(self, search_dirs):
        cracked_lookup = {net['bssid'].replace(':', '').lower(): net['password'] for net in self.cracked_networks}
        created_count = 0
        
        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            
            for f in os.listdir(d):
                if f.endswith('.pcap'):
                    try:
                        base = f[:-5]
                        parts = base.split('_')
                        if len(parts) >= 2:
                            file_bssid = parts[-1].lower()
                            if len(file_bssid) == 12:
                                password = cracked_lookup.get(file_bssid)
                                if password:
                                    cracked_file_path = os.path.join(d, f + '.cracked')
                                    current_pwd = ""
                                    if os.path.exists(cracked_file_path):
                                        with open(cracked_file_path, 'r') as cf:
                                            current_pwd = cf.read().strip()
                                    
                                    if current_pwd != password:
                                        with open(cracked_file_path, 'w') as cf:
                                            cf.write(password)
                                        created_count += 1
                    except Exception:
                        continue
        
        if created_count > 0:
            logging.info(f"[opwnhouse] Created {created_count} .pcap.cracked files for webgpsmap compatibility")

    def on_ready(self, agent):
        """Called when the plugin is ready."""
        self._agent = agent

    def on_loaded(self):
        self.ready = True
        logging.info("[opwnhouse] Plugin loaded")
        config = pwnagotchi.config
        hs_dir = config.get('bettercap', {}).get('handshakes', '/root/handshakes')
        cus_dir = self.options.get('custom_dir', '')

        handshake_dirs = [hs_dir]
        if cus_dir and os.path.isdir(cus_dir):
            handshake_dirs.append(cus_dir)
        
        other_potfiles = []
        save_path = self.options.get('save_path', os.path.join(hs_dir, 'opwnhouse.potfile'))
        
        self.json_path = os.path.splitext(save_path)[0] + '.json'
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r') as f:
                    self.companion_data = json.load(f)
            except Exception as e:
                logging.error(f"[opwnhouse] Error loading companion JSON: {e}")
                self.companion_data = {}
        else:
            self.companion_data = {}

        for scan_dir in handshake_dirs:
            if not os.path.isdir(scan_dir):
                logging.warning(f"[opwnhouse] Directory {scan_dir} does not exist, skipping...")
                continue
            
            logging.info(f"[opwnhouse] Scanning directory: {scan_dir}")
            for f in os.listdir(scan_dir):
                file_path = os.path.join(scan_dir, f)
                if (f.endswith('.potfile') or f.endswith('.cracked')) and os.path.abspath(file_path) != os.path.abspath(save_path):
                    other_potfiles.append(file_path)

        self.all_found_files = [save_path] + other_potfiles
        
        self.sanitize_files(self.all_found_files)

        if self.all_found_files:
            with open(save_path, 'w') as f:
                for network in self.cracked_networks:
                    bssid_out = network.get('bssid', '').replace(':', '')
                    stamac_out = network.get('stamac', '').replace(':', '')
                    f.write(f"{bssid_out}:{stamac_out}:{network.get('essid', '')}:{network.get('password', '')}\n")
            logging.info(f"[opwnhouse] Found and saved {len(self.cracked_networks)} cracked networks to {save_path}")
            
            if self._is_gps_enabled():
                self._enrich_with_gps(handshake_dirs)

            self.save_companion_json()
            self._ensure_pcap_cracked_files(handshake_dirs)

        # Start background thread
        self.stop_thread.clear()
        self.wifi_update_thread = threading.Thread(target=self._wifi_update_processor)
        self.wifi_update_thread.daemon = True
        self.wifi_update_thread.start()
        logging.info("[opwnhouse] Background processor thread started.")

        if self.cracked_networks:
            last_net = self.cracked_networks[-1]
            self.last_wpasec_crack = {'essid': last_net.get('essid', ''), 'password': last_net.get('password', '')}
            logging.info(f"[opwnhouse] Loaded last crack from master potfile: {self.last_wpasec_crack['essid']}")

    def on_ui_setup(self, ui):
        if ui.is_waveshare_v2():
            h_pos = (0, 95)
            v_pos = (180, 61)
            s_pos = (0, 61)
        elif ui.is_waveshare_v1():
            h_pos = (0, 95)
            v_pos = (170, 61)
            s_pos = (0, 61)
        elif ui.is_waveshare144lcd():
            h_pos = (0, 92)
            v_pos = (78, 67)
            s_pos = (0, 67)
        elif ui.is_inky():
            h_pos = (0, 83)
            v_pos = (165, 54)
            s_pos = (0, 54)
        else: # default
            h_pos = (0, 91)
            v_pos = (180, 61)
            s_pos = (0, 61)

        try:
            if 'position' in self.options:
                pos_option = self.options['position']
                pos_list = []
                if isinstance(pos_option, str):
                    pos_list = [int(x.strip()) for x in pos_option.split(',')]
                elif isinstance(pos_option, list):
                    pos_list = pos_option
                
                if len(pos_list) == 2:
                    if self.options.get('orientation', 'vertical') == "vertical":
                        v_pos = tuple(pos_list)
                    else:
                        h_pos = tuple(pos_list)

            if 'stats_position' in self.options:
                s_pos_option = self.options['stats_position']
                s_pos_list = []
                if isinstance(s_pos_option, str):
                    s_pos_list = [int(x.strip()) for x in s_pos_option.split(',')]
                elif isinstance(s_pos_option, list):
                    s_pos_list = s_pos_option
                
                if len(s_pos_list) == 2:
                    s_pos = tuple(s_pos_list)
        except Exception as e:
            logging.error(f"[opwnhouse] Error parsing position options: {e}")
        if self.options.get('orientation', 'vertical') == "vertical":
            ui.add_element('opwnhouse_display', LabeledValue(color=BLACK, label='', value='', position=v_pos, label_font=fonts.Bold, text_font=fonts.Small))
        else:
            ui.add_element('opwnhouse_display', LabeledValue(color=BLACK, label='', value='', position=h_pos, label_font=fonts.Bold, text_font=fonts.Small))

        if self.options.get('display_stats', False):
            logging.info("[opwnhouse] display stats loaded")
            ui.add_element('opwnhouse_stats', LabeledValue(color=BLACK, label='', value='', position=s_pos, label_font=fonts.Bold, text_font=fonts.Small))

    def on_unload(self, ui):
        with ui._lock:
            try:
                ui.remove_element('opwnhouse_display')
                ui.remove_element('opwnhouse_stats')
            except KeyError:
                pass
        
        self.stop_thread.set()
        if self.wifi_update_thread:
            self.wifi_update_thread.join()
        logging.info("[opwnhouse] Background processor thread stopped.")

    def on_gps_update(self, agent, gps):
        with self.lock:
            if gps:
                if self._current_gps:
                    if isinstance(gps, dict):
                        new_lat = gps.get('latitude', gps.get('Latitude', 0))
                        new_lon = gps.get('longitude', gps.get('Longitude', 0))
                    else:
                        new_lat = getattr(gps, 'latitude', 0)
                        new_lon = getattr(gps, 'longitude', 0)

                    if isinstance(self._current_gps, dict):
                        old_lat = self._current_gps.get('latitude', self._current_gps.get('Latitude', 0))
                        old_lon = self._current_gps.get('longitude', self._current_gps.get('Longitude', 0))
                    else:
                        old_lat = getattr(self._current_gps, 'latitude', 0)
                        old_lon = getattr(self._current_gps, 'longitude', 0)

                    if new_lat != 0 and new_lon != 0 and (abs(new_lat - old_lat) > 0.00001 or abs(new_lon - old_lon) > 0.00001):
                        _, self._movement_bearing = self._calculate_distance_bearing(
                            {'latitude': old_lat, 'longitude': old_lon},
                            {'latitude': new_lat, 'longitude': new_lon}
                        )
                self._current_gps = gps

    def _get_cardinal_direction(self, bearing):
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(bearing / 45) % 8
        return directions[index]

    def _calculate_distance_bearing(self, old_gps, new_gps):
        R = 6371000 
        lat1 = math.radians(old_gps['latitude'])
        lon1 = math.radians(old_gps['longitude'])
        lat2 = math.radians(new_gps['latitude'])
        lon2 = math.radians(new_gps['longitude'])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
        return distance, bearing

    def _wifi_update_processor(self):
        while not self.stop_thread.is_set():
            access_points_to_process = None
            with self.lock:
                if self.latest_access_points is not None:
                    access_points_to_process = self.latest_access_points
                    self.latest_access_points = None

            if access_points_to_process:
                total_nearby_cracked = 0
                all_nearby_aps = []
                best_bssid = ''
                best_rssi = -1000
                best_essid = ''
                best_password = ''
                best_trend = 'STEADY'
                direction_text = self._direction_text

                current_bssids = set()

                now = time.time()
                is_not_associated = self.is_not_associated
                if now - self.last_iwconfig_check > 5:
                    is_not_associated = "Not-Associated" in os.popen('iwconfig wlan0').read()
                    self.last_iwconfig_check = now

                if is_not_associated:
                    cracked_bssid_lookup = {net['bssid'].lower(): net for net in self.cracked_networks}
                    cracked_essid_lookup = {net['essid']: net for net in self.cracked_networks}

                    for ap in access_points_to_process:
                        bssid_lower = ap['mac'].lower()
                        current_bssids.add(bssid_lower)
                        essid = ap['hostname']
                        cracked_net = cracked_bssid_lookup.get(bssid_lower) or cracked_essid_lookup.get(essid)
                        password = cracked_net['password'] if cracked_net else None
                        stamac = cracked_net['stamac'] if cracked_net else None
                        rssi = ap['rssi']

                        trend = 'STEADY'
                        with self.lock:
                            if bssid_lower in self.rssi_history:
                                prev_rssi = self.rssi_history[bssid_lower]
                                diff = rssi - prev_rssi
                                if diff >= 4:
                                    trend = 'HOTTER'
                                elif diff <= -4:
                                    trend = 'COLDER'
                            self.rssi_history[bssid_lower] = rssi

                        all_nearby_aps.append({
                            'essid': essid, 'bssid': ap['mac'], 'stamac': stamac,
                            'rssi': rssi, 'password': password, 'trend': trend
                        })

                    with self.lock:
                        for bssid in list(self.rssi_history.keys()):
                            if bssid not in current_bssids:
                                del self.rssi_history[bssid]

                    all_nearby_aps.sort(key=lambda x: (-x['rssi'], x['essid']))
                    nearby_cracks = [ap for ap in all_nearby_aps if ap['password']]
                    total_nearby_cracked = len(nearby_cracks)

                    if nearby_cracks:
                        best_crack = nearby_cracks[0]
                        best_rssi = best_crack.get('rssi', -1000)
                        best_bssid = best_crack.get('bssid', '')
                        best_essid = best_crack.get('essid', '')
                        best_password = best_crack.get('password', '')
                        best_trend = best_crack.get('trend', 'STEADY')

                        if self.options.get('hunter_mode', False):
                            with self.lock:
                                if self._current_gps:
                                    lat = 0
                                    lon = 0
                                    if isinstance(self._current_gps, dict):
                                        lat = self._current_gps.get('latitude', self._current_gps.get('Latitude', 0))
                                        lon = self._current_gps.get('longitude', self._current_gps.get('Longitude', 0))
                                    else:
                                        lat = getattr(self._current_gps, 'latitude', 0)
                                        lon = getattr(self._current_gps, 'longitude', 0)

                                    if lat != 0 and lon != 0:
                                        current_gps_dict = {'latitude': lat, 'longitude': lon}
                                        if best_bssid != self._ref_bssid:
                                            self._ref_gps = current_gps_dict
                                            self._ref_rssi = best_rssi
                                            self._ref_bssid = best_bssid
                                            direction_text = ''
                                        elif self._ref_gps:
                                            dist, bearing = self._calculate_distance_bearing(self._ref_gps, current_gps_dict)
                                            if dist >= 5:
                                                rssi_diff = best_rssi - self._ref_rssi
                                                if rssi_diff >= 3:
                                                    direction_text = f"->{self._get_cardinal_direction(bearing)}"
                                                elif rssi_diff <= -3:
                                                    direction_text = f"->{self._get_cardinal_direction((bearing + 180) % 360)}"
                                                self._ref_gps = current_gps_dict
                                                self._ref_rssi = best_rssi
                                        else:
                                            self._ref_gps = current_gps_dict
                                            self._ref_rssi = best_rssi
                                            self._ref_bssid = best_bssid

                with self.lock:
                    self.all_nearby_aps = all_nearby_aps
                    self.total_nearby_cracked = total_nearby_cracked
                    self.nearby_cracks = [ap for ap in all_nearby_aps if ap['password']]
                    self.is_not_associated = is_not_associated
                    if self.nearby_cracks:
                        self._rssi, self._bssid, self._essid, self._password, self._trend, self._direction_text = \
                            best_rssi, best_bssid, best_essid, best_password, best_trend, direction_text
                    else:
                        self._bssid = ''

            time.sleep(1)

    def on_wifi_update(self, agent, access_points):
        with self.lock:
            self.latest_access_points = access_points
        self.last_wifi_update = time.strftime("%H:%M")
        
    def on_ui_update(self, ui):
        with self.lock:
            if self._bssid:
                trend_indicator = ""
                dir_text = ""
                if self.options.get('hunter_mode', False):
                    if self._trend == 'HOTTER':
                        trend_indicator = " HOT!"
                    elif self._trend == 'COLDER':
                        trend_indicator = " COLD!"
                    dir_text = " " + self._direction_text

                if self.options.get('orientation', 'vertical') == "vertical":
                    msg = f"{self._essid}({self._rssi}){trend_indicator}{dir_text}\n{self._password}"
                else:
                    msg = f"{self._essid}: {self._password}{trend_indicator}{dir_text}"
                ui.set('opwnhouse_display', msg)
            elif self.last_wpasec_crack:
                if self.options.get('orientation', 'vertical') == "vertical":
                    msg = f"{self.last_wpasec_crack['essid']}\n{self.last_wpasec_crack['password']}"
                else:
                    msg = f"{self.last_wpasec_crack['essid']}: {self.last_wpasec_crack['password']}"
                ui.set('opwnhouse_display', msg)
            else:
                ui.set('opwnhouse_display', "No cracked APs")

            if self.options.get('display_stats', False):
                msg_stats = f"{self.total_nearby_cracked}/{len(self.cracked_networks)}"
                ui.set('opwnhouse_stats', msg_stats)
            
            self.pwnagotchi_face = ui.get('face')

    def sanitize_files(self, file_list):
        hs_dir = pwnagotchi.config.get('bettercap', {}).get('handshakes', '/root/handshakes')
        master_potfile_path = os.path.abspath(self.options.get('save_path', os.path.join(hs_dir, 'opwnhouse.potfile')))
        
        temp_cracks = {}
        logging.info("[opwnhouse] Sanitizing files...")

        sorted_file_list = sorted(file_list, key=lambda x: os.path.abspath(x) != master_potfile_path)

        for file_path in file_list:
            is_master = os.path.abspath(file_path) == master_potfile_path
            if not os.path.exists(file_path):
                logging.warning(f"[opwnhouse] File not found during sanitization, skipping: {file_path}")
                continue

            logging.info(f"[opwnhouse] Processing {'MASTER' if is_master else 'source'} file: {os.path.basename(file_path)}")
            with open(file_path, 'r', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    bssid, essid, password, stamac = None, None, None, None
                    
                    if file_path.lower().endswith('.potfile'):
                        parts = line.split(':')
                        if len(parts) >= 3:
                            bssid = self._format_mac(parts[0])
                            stamac = self._format_mac(parts[1])
                            essid = parts[2]
                            password = ':'.join(parts[3:]) if len(parts) > 3 else ''

                    elif file_path.lower().endswith('.cracked'):
                        parts = line.split(',')
                        if len(parts) >= 5 and parts[4]:
                            essid = parts[1]
                            bssid = parts[2]
                            stamac = parts[3]
                            password = parts[4]
                    
                    if bssid and essid and password:
                        stamac = stamac or '00:00:00:00:00:00'
                        key = bssid.lower().replace(':', '')
                        
                        json_key = self._format_mac(bssid).upper()
                        if json_key not in self.companion_data:
                            self.companion_data[json_key] = {
                                "essid": essid,
                                "passwords": [],
                                "gps_locations": [],
                                "notes": ""
                            }
                        if not self.companion_data[json_key].get("essid"):
                            self.companion_data[json_key]["essid"] = essid
                        if password not in self.companion_data[json_key]["passwords"]:
                            self.companion_data[json_key]["passwords"].append(password)

                        if key not in temp_cracks:
                            temp_cracks[key] = {'bssid': bssid, 'stamac': stamac, 'essid': essid, 'password': password}
        
        self.cracked_networks = list(temp_cracks.values())

    def save_companion_json(self):
        try:
            with open(self.json_path, 'w') as f:
                json.dump(self.companion_data, f, indent=2)
            logging.info(f"[opwnhouse] Saved companion data to {self.json_path}")
        except Exception as e:
            logging.error(f"[opwnhouse] Error saving companion JSON: {e}")

    def on_webhook(self, path, request):
        if not self.ready:
            return "Plugin not ready yet."

        if path == "edit" and request.method == "POST":
            try:
                original_bssid = request.form.get('original_bssid')
                updated_network = {
                    'essid': request.form.get('essid'),
                    'bssid': request.form.get('bssid'),
                    'stamac': request.form.get('stamac'),
                    'password': request.form.get('password')
                }

                if not all(updated_network.values()) or not original_bssid:
                    raise ValueError("Missing data for network update.")

                network_found = False
                for i, net in enumerate(self.cracked_networks):
                    if net['bssid'].lower() == original_bssid.lower():
                        logging.info(f"[opwnhouse] Found existing network to update: {original_bssid}")
                        self.cracked_networks[i] = updated_network
                        network_found = True
                        break
                
                if not network_found:
                    logging.info(f"[opwnhouse] Adding new network: {updated_network['bssid']}")
                    self.cracked_networks.append(updated_network)

                json_key = self._format_mac(updated_network['bssid']).upper()
                if json_key not in self.companion_data:
                    self.companion_data[json_key] = {
                        "essid": updated_network['essid'],
                        "passwords": [],
                        "gps_locations": [],
                        "notes": ""
                    }
                self.companion_data[json_key]['essid'] = updated_network['essid']
                if updated_network['password'] not in self.companion_data[json_key]['passwords']:
                    self.companion_data[json_key]['passwords'].append(updated_network['password'])
                self.save_companion_json()

                hs_dir = pwnagotchi.config.get('bettercap', {}).get('handshakes', '/root/handshakes')
                self._ensure_pcap_cracked_files([hs_dir])
                save_path = self.options.get('save_path', os.path.join(hs_dir, 'opwnhouse.potfile'))
                with open(save_path, 'w') as f:
                    for network in self.cracked_networks:
                        bssid_out = network.get('bssid', '').replace(':', '')
                        stamac_out = network.get('stamac', '').replace(':', '')
                        f.write(f"{bssid_out}:{stamac_out}:{network.get('essid', '')}:{network.get('password', '')}\n")
                
                logging.info(f"[opwnhouse] Saved network data for {updated_network['bssid']} to {save_path}")
                return jsonify({'success': True, 'message': 'Network updated successfully!'})

            except Exception as e:
                logging.error(f"[opwnhouse] Error editing network: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500

        if path == "delete_network" and request.method == "POST":
            try:
                bssid = request.form.get('bssid')
                if not bssid:
                    return jsonify({'success': False, 'message': 'BSSID required'}), 400
                
                normalized_bssid = bssid.replace(':', '').lower()
                files_modified = 0

                for file_path in self.all_found_files:
                    if not os.path.exists(file_path):
                        continue
                    
                    lines = []
                    modified = False
                    try:
                        with open(file_path, 'r', errors='ignore') as f:
                            for line in f:
                                line_strip = line.strip()
                                if not line_strip:
                                    lines.append(line)
                                    continue
                                
                                current_bssid = None
                                if file_path.endswith('.potfile'):
                                    parts = line_strip.split(':')
                                    if len(parts) >= 1:
                                        current_bssid = parts[0].replace(':', '').lower()
                                elif file_path.endswith('.cracked'):
                                    parts = line_strip.split(',')
                                    if len(parts) >= 3:
                                        current_bssid = parts[2].replace(':', '').lower()
                                
                                if current_bssid == normalized_bssid:
                                    modified = True
                                else:
                                    lines.append(line)
                        
                        if modified:
                            with open(file_path, 'w') as f:
                                f.writelines(lines)
                            files_modified += 1
                            logging.info(f"[opwnhouse] Removed {bssid} from {file_path}")
                    except Exception as e:
                        logging.error(f"[opwnhouse] Error processing file {file_path}: {e}")

                json_key = self._format_mac(bssid).upper()
                if json_key in self.companion_data:
                    del self.companion_data[json_key]
                    self.save_companion_json()

                config = pwnagotchi.config
                hs_dir = config.get('bettercap', {}).get('handshakes', '/root/handshakes')
                cus_dir = self.options.get('custom_dir', '')
                dirs_to_check = [hs_dir]
                if cus_dir and os.path.isdir(cus_dir):
                    dirs_to_check.append(cus_dir)
                
                for d in dirs_to_check:
                    if os.path.isdir(d):
                        for f in os.listdir(d):
                            if f.endswith('.pcap.cracked'):
                                if normalized_bssid in f.replace(':', '').lower():
                                    try:
                                        os.remove(os.path.join(d, f))
                                        logging.info(f"[opwnhouse] Deleted cracked pcap marker: {f}")
                                    except OSError as e:
                                        logging.error(f"[opwnhouse] Error deleting {f}: {e}")

                self.on_loaded()
                return jsonify({'success': True, 'message': f'Network deleted from {files_modified} files.'})

            except Exception as e:
                logging.error(f"[opwnhouse] Error deleting network: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500

        if path == "refresh" and request.method == "POST":
            try:
                self.on_loaded()
                return jsonify({'success': True, 'message': f'Data refreshed. Loaded {len(self.cracked_networks)} networks.'})
            except Exception as e:
                logging.error(f"[opwnhouse] Error refreshing data: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500

        if path == "refresh_gps" and request.method == "POST":
            try:
                bssid = request.form.get('bssid')
                if not bssid:
                    return jsonify({'success': False, 'message': 'BSSID is required.'}), 400

                success, message = self._refresh_single_gps(bssid)
                
                return jsonify({'success': success, 'message': message})
            except Exception as e:
                logging.error(f"[opwnhouse] Error refreshing single GPS: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500

        if path == "import" and request.method == "POST":
            try:
                if 'import_file' not in request.files:
                    raise ValueError("No file part in the request.")
                file = request.files['import_file']
                if file.filename == '':
                    raise ValueError("No file selected for uploading.")

                if file and (file.filename.endswith('.potfile') or file.filename.endswith('.cracked')):
                    filename = secure_filename(file.filename)
                    hs_dir = pwnagotchi.config.get('bettercap', {}).get('handshakes', '/root/handshakes')
                    save_path = os.path.join(hs_dir, filename)
                    file.save(save_path)
                    logging.info(f"[opwnhouse] Imported file saved to {save_path}")

                    self.on_loaded()

                    message = f"Successfully imported {filename} and reloaded {len(self.cracked_networks)} total networks."
                    return jsonify({'success': True, 'message': message})
                else:
                    raise ValueError("Invalid file type. Only .potfile and .cracked are allowed.")

            except Exception as e:
                logging.error(f"[opwnhouse] Error importing file: {e}")
                message = f"Error importing file: {e}"
                return jsonify({'success': False, 'message': message}), 500

        if path == "delete" and request.method == "POST":
            try:
                files_to_delete = request.form.getlist('delete_files')
                if not files_to_delete:
                    raise ValueError("No files selected for deletion.")

                known_files = set(self.all_found_files)
                deleted_count = 0
                
                for file_path in files_to_delete:
                    if file_path in known_files:
                        os.remove(file_path)
                        logging.info(f"[opwnhouse] Deleted file: {file_path}")
                        deleted_count += 1
                    else:
                        logging.warning(f"[opwnhouse] Security warning: Attempted to delete non-whitelisted file: {file_path}")

                self.on_loaded()

                message = f"Successfully deleted {deleted_count} file(s) and reloaded data."
                return jsonify({'success': True, 'message': message})

            except Exception as e:
                logging.error(f"[opwnhouse] Error deleting files: {e}")
                message = f"Error deleting files: {e}"
                return jsonify({'success': False, 'message': f"Error: {e}"}), 500

        if path == "export" and request.method == "GET":
            from flask import send_file
            hs_dir = pwnagotchi.config.get('bettercap', {}).get('handshakes', '/root/handshakes')
            potfile_path = self.options.get('save_path', os.path.join(hs_dir, 'opwnhouse.potfile'))
            logging.info(f"[opwnhouse] Exporting consolidated potfile from {potfile_path}")
            return send_file(potfile_path, as_attachment=True, download_name='opwnhouse.potfile')

        if path == "config" and request.method == "POST":
            try:
                if not self._agent:
                    return jsonify({'success': False, 'message': 'Agent not ready, cannot save config.'}), 503

                form_data = request.form.to_dict()
                new_config = {}
                for k, v in form_data.items():
                    if not v:
                        continue
                    if k in ('position', 'stats_position'):
                        try:
                            new_config[k] = [int(x.strip()) for x in v.split(',')]
                        except (ValueError, AttributeError):
                            logging.warning(f"[opwnhouse] Invalid position format for {k}: '{v}'. Skipping.")
                    elif k == 'display_stats':
                        new_config[k] = (v.lower() in ['true', 'on'])
                    elif k == 'per_page':
                        new_config[k] = int(v)
                    else:
                        new_config[k] = v

                logging.info(f"[opwnhouse] Received new config to save: {new_config}")

                config = self._agent.config()

                if 'opwnhouse' not in config['main']['plugins']:
                    config['main']['plugins']['opwnhouse'] = {}

                for key, value in new_config.items():
                    config['main']['plugins']['opwnhouse'][key] = value
                    self.options[key] = value

                save_config(config, self.config_path)

                self._agent._config = config

                logging.info("[opwnhouse] Successfully saved config to /etc/pwnagotchi/config.toml")
                return jsonify({'success': True, 'message': 'Configuration saved successfully! Restart Pwnagotchi for all changes to take effect.'})

            except Exception as e:
                logging.error(f"[opwnhouse] Error saving config: {e}")
                return jsonify({'success': False, 'message': f'Error saving configuration: {e}'}), 500

        if path == "details" and request.method == "GET":
            bssid = request.args.get('bssid')
            if not bssid:
                return jsonify({'success': False, 'message': 'BSSID required'}), 400
            
            json_key = self._format_mac(bssid).upper()
            data = self.companion_data.get(json_key, {})
            return jsonify({'success': True, 'data': data})

        if request.method == "GET":
            if path == "/" or not path:
                cracked_header = "<thead><tr><th>ESSID</th><th>BSSID</th><th>STAMAC</th><th>Password</th><th>GPS</th><th>Actions</th></tr></thead>"
                cracked_body = "<tbody>"
                sorted_networks = sorted(self.cracked_networks, key=lambda x: x['essid'].lower())
                for network in sorted_networks:
                    essid = network.get('essid', 'N/A')
                    bssid = self._format_mac(network.get('bssid', 'N/A'))
                    stamac = self._format_mac(network.get('stamac', 'N/A'))
                    password = network.get('password', 'N/A')
                    
                    gps_text = "N/A"
                    json_key = self._format_mac(bssid).upper()
                    if json_key in self.companion_data:
                        locs = self.companion_data[json_key].get('gps_locations', [])
                        if locs and len(locs) > 0:
                            last_loc = locs[-1]
                            if 'latitude' in last_loc and 'longitude' in last_loc:
                                gps_text = f"{last_loc['latitude']:.4f}, {last_loc['longitude']:.4f}"

                    if password and password != 'N/A':
                        js_essid = essid.replace("'", "\\'")
                        js_password = password.replace("'", "\\'")
                        cracked_body += f"<tr data-password='true' onclick=\"showQrCode('{js_essid}', '{js_password}')\">"
                    else:
                        cracked_body += "<tr>"
                    
                    js_stamac = stamac.replace("'", "\\'")
                    js_bssid = bssid.replace("'", "\\'")
                    edit_button = f"<button onclick=\"event.stopPropagation(); showEditModal('{js_essid}', '{js_bssid}', '{js_stamac}', '{js_password}')\">Edit</button>"
                    cracked_body += f"<td>{essid}</td><td>{bssid}</td><td>{stamac}</td><td>{password}</td><td>{gps_text}</td><td>{edit_button}</td></tr>"
                cracked_body += "</tbody>"
                cracked_list_table = cracked_header + cracked_body

                return render_template_string(INDEX,
                    cracked_list_table=cracked_list_table,
                    per_page=self.options.get('per_page', 20),
                    found_files=self.all_found_files
                )
            elif path == "json":
                with self.lock:
                    all_nearby_aps_copy = [ap.copy() for ap in self.all_nearby_aps]
                    total_nearby_cracked_copy = self.total_nearby_cracked
                    total_cracked_copy = len(self.cracked_networks)
                    pwnagotchi_face_copy = self.pwnagotchi_face
                    movement_bearing_copy = self._movement_bearing

                formatted_aps = []
                for ap in all_nearby_aps_copy:
                    bssid = self._format_mac(ap.get('bssid'))
                    json_key = bssid.upper()
                    gps_text = None
                    if json_key in self.companion_data:
                        locs = self.companion_data[json_key].get('gps_locations', [])
                        if locs and len(locs) > 0:
                            last_loc = locs[-1]
                            if 'latitude' in last_loc and 'longitude' in last_loc:
                                gps_text = f"{last_loc['latitude']:.4f}, {last_loc['longitude']:.4f}"
                    
                    formatted_aps.append({
                        **ap, 
                        'bssid': bssid, 
                        'stamac': self._format_mac(ap.get('stamac')),
                        'gps': gps_text
                    })
                
                response_data = {
                    'pwnagotchi_face': pwnagotchi_face_copy,
                    'nearby_aps': formatted_aps,
                    'total_nearby_cracked': total_nearby_cracked_copy,
                    'total_cracked': total_cracked_copy,
                    'movement_bearing': movement_bearing_copy
                }
                return jsonify(response_data)
            elif path == "config":
                config_options = self.options.copy()
                display_stats_val = config_options.get('display_stats')
                hunter_mode_val = config_options.get('hunter_mode')

                if isinstance(display_stats_val, str):
                    config_options['display_stats'] = display_stats_val.lower() in ['true', 'on', '1', 'yes']
                if isinstance(hunter_mode_val, str):
                    config_options['hunter_mode'] = hunter_mode_val.lower() in ['true', 'on', '1', 'yes']
                    
                return jsonify(config_options)
            elif path == "files" and request.method == "GET":
                return jsonify({'files': self.all_found_files})

        return "Not Found", 404
