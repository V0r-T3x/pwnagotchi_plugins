# Crack_house
#
# Inspiration:
# educational-purposes-only.py
# by @cnagy
# https://github.com/c-nagy/pwnagotchi-educational-purposes-only-plugin/blob/main/educational-purposes-only.py
# 
# display-password.py
# @abros0000
# https://github.com/abros0000/pwnagotchi-display-password-plugin/blob/master/display-password.py
#
# If their is no cracked network nearby the plugins show the last cracked password by wpa-sec
# If a cracked networks are nearby it will she the nearest on the screen

from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins
import pwnagotchi
import logging
import os
import subprocess
import requests
import time
from pwnagotchi.ai.reward import RewardFunction

READY = 0

#list of all file paths with cracked passwords
FP_WPA_SEC = ['/root/handshakes/wpa-sec.cracked.potfile','/root/handshakes/my.potfile','/root/handshakes/OnlineHashCrack.potfile']
#crack house filtered list potfile path
FP_CH = '/root/handshakes/crackhouse.potfile'
#the list with hostname:password without duplicate for the plugin
CRACK_MENU = list()

BEST_RSSI = -1000
BEST_CRACK = ['']

class CrackHouse(plugins.Plugin):
    __author__ = '@V0rT3x'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin to display closest cracked network & it password'
    
    def on_loaded(self):
        global READY
        global FP_WPA_SEC
        global FP_CH
        global CRACK_MENU
        tmp_line = ''
        tmp_list = list()
        crack_line = list()
        

#       loop to retreive all passwords of all files into a big list without dulicate
        for file_path in FP_WPA_SEC:
            with open(file_path) as f:
                for line in f:
#                    logging.info(line.rstrip().split(':', 2)[-1:])
                    tmp_line = str(line.rstrip().split(':',2)[-1:])[2:-2]
                    tmp_list.append(tmp_line)
#                    logging.info(len(tmp_list))
        CRACK_MENU = list(set(tmp_list))
#       write all name:password inside a file as backup for the run
        with open(FP_CH, 'w') as f:
            for crack in CRACK_MENU:
#                logging.info(crack)
                f.write(crack + '\n')
        READY = 1
        logging.info("[CRACK HOUSE] Successfully loaded")
        logging.info('[CRACK HOUSE] all paths: ' + str(FP_WPA_SEC))

    def on_ui_setup(self, ui):
        if ui.is_waveshare_v2():
            h_pos = (0, 95)
            v_pos = (180, 61)
        elif ui.is_waveshare_v1():
            h_pos = (0, 95)
            v_pos = (170, 61)
        elif ui.is_waveshare144lcd():
            h_pos = (0, 92)
            v_pos = (78, 67)
        elif ui.is_lcdhat():
            h_pos = (0, 203)
            v_pos = (-10, 185)
        elif ui.is_waveshare27inch():
            h_pos = (0, 153)
            v_pos = (216, 122)
        else:
            h_pos = (0, 91)
            v_pos = (180, 61)

        if self.options['orientation'] == "vertical":
            ui.add_element('crack_house', LabeledValue(color=BLACK, label='', value='',
                                                   position=v_pos,
                                                   label_font=fonts.Bold, text_font=fonts.Small))

        else:
            # default to horizontal
            ui.add_element('crack_house', LabeledValue(color=BLACK, label='', value='',
                                                   position=h_pos,
                                                   label_font=fonts.Bold, text_font=fonts.Small))

    def on_unload(self, ui):
        with ui._lock:
            ui.remove_element('crack_house')
    
    def on_wifi_update(self, agent, access_points):
        global READY
        global CRACK_MENU
        global BEST_RSSI
        global BEST_CRACK
        status = 0
        tmp_crack = list()
        tmp_menu = list()
        logging.info("[CRACK HOUSE] Total cracks: %d" % (len(CRACK_MENU)))
#        logging.info(os.popen('iwconfig wlan0').read())

        if READY == 1 and "Not-Associated" in os.popen('iwconfig wlan0').read():
            BEST_RSSI = -1000
            for network in access_points:
                hn = str(network['hostname'])
                ssi = network['rssi']
#                logging.info(ssi)
#                logging.info(hn)
                for crack in CRACK_MENU:
                    tmp_crack = crack.rstrip().split(':')
#                    logging.info(str(tmp_crack[0]))
                    tc = str(tmp_crack[0])
                    if hn == tc:
                        logging.info('[CRACK HOUSE] %s, pass: %s, RSSI: %d' % (tmp_crack[0], tmp_crack[1], ssi))
                        if ssi > BEST_RSSI:
                            BEST_RSSI = ssi
                            BEST_CRACK = tmp_crack
                            status = 1
            logging.info('\n !!!! BEST CRACK HOUSE !!!! \n [CRACK HOUSE] %s, pass: %s, RSSI: %d' % (BEST_CRACK[0], BEST_CRACK[1], BEST_RSSI))

    def on_ui_update(self, ui):
        global BEST_RSSI
        global BEST_CRACK

        if BEST_RSSI != -1000:
            msg_ch = str(BEST_CRACK[0] + '\n' + BEST_CRACK[1])
#            logging.info(msg_ch)
#            logging.info(msg_ch)
            ui.set('crack_house',
                        '%s' % (msg_ch))
        else:
            last_line = 'tail -n 1 /root/handshakes/wpa-sec.cracked.potfile | awk -F: \'{printf $3 "\\n" $4}\''
            ui.set('crack_house',
                        "%s" % (os.popen(last_line).read().rstrip()))
                            


