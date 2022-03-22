#!/usr/bin/python -u
# coding=utf-8
# "DATASHEET": http://cl.ly/ekot
# https://gist.github.com/kadamski/92653913a53baf9dd1a8

import serial, struct, sys, time, json, subprocess, datetime
import board, adafruit_lps2x, adafruit_dht
import sqlite3, os
import requests
from requests.auth import HTTPBasicAuth


# SDS011 configs
#
# 0 == off, else == on
DEBUG = 0
# Data byte number for each setting, is used to let sensor know which setting we want to tweak
CMD_MODE = 2
CMD_QUERY_DATA = 4
CMD_DEVICE_ID = 5
CMD_SLEEP = 6
CMD_FIRMWARE = 7
CMD_WORKING_PERIOD = 8
# Modes for cmd_configs
MODE_ACTIVE = 0 # doesnt get used?
MODE_QUERY = 1
    # 1 = Report query mode：Sensor received query data command to report a measurement data.
    # 0 = Report active mode：Sensor automatically reports a measurement data in a work period.
PERIOD_CONTINUOUS = 0

JSON_FILE = '/var/www/html/aqi.json'

MQTT_HOST = ''
MQTT_TOPIC = ''

# initialize SDS011 port
ser = serial.Serial()
ser.port = "/dev/ttyUSB0"
ser.baudrate = 9600
#print(ser)

ser.open()
# ser.flushInput() depricated, now:
# ser.reset_input_buffer()


byte, data = 0, ""


# nova SDS011 functions
#
# print all data d in hex
def dump(d, prefix=''):
    print(prefix + ' '.join(str(x).encode('utf-8').hex() for x in d))

# build command to give to port
def construct_command(cmd, data=[]):
    if DEBUG:
        print("construct_command")
        print("cmd: " + str(cmd) + "    data: " + str(data))
    assert len(data) <= 12
    data += [0,]*(12-len(data))
    checksum = (sum(data)+cmd-2)%256
    ret = "\xaa\xb4" + chr(cmd)
    ret += ''.join(chr(x) for x in data)
    ret += "\xff\xff" + chr(checksum) + "\xab"

    if DEBUG:
        dump(ret, 'ser.write(): ')
    ret_b = ret.encode('raw_unicode_escape')
    return ret_b

# processes input data d and returns pm25 and pm10
def process_data(d):
    if DEBUG:
        print("process_data")
    r = struct.unpack('<HHxxBB', d[2:])
    pm25 = r[0]/10.0
    pm10 = r[1]/10.0
    # old: checksum = sum(ord(v) for v in d[2:8])%256
    checksum = sum(v for v in d[2:8])%256
    return [pm25, pm10]
    #print("PM 2.5: {} μg/m^3  PM 10: {} μg/m^3 CRC={}".format(pm25, pm10, "OK" if (checksum==r[2] and r[3]==0xab) else "NOK"))

# print software version; used in cmd_firmware_ver()
def process_version(d):
    if DEBUG:
        print("process_version")
    r = struct.unpack('<BBBHBB', d[3:])
    # old: checksum = sum(ord(v) for v in d[2:8])%256
    checksum = sum(v for v in d[2:8])%256
    print("Y: {}, M: {}, D: {}, ID: {}, CRC={}".format(r[0], r[1], r[2], hex(r[3]), "OK" if (checksum==r[4] and r[5]==0xab) else "NOK"))

# read response from serial port
def read_response():
    if DEBUG:
        print("read_response")
        print("while byte != b'\\xaa':")
    byte = 0
    while byte != b"\xaa":
        if DEBUG:
            print("byte: " + str(byte))
        byte = ser.read(size=1)
        if DEBUG:
            print("after ser.read(): " + str(byte))

    d = ser.read(size=9)

    if DEBUG:
        dump(d, 'ser.read(): ')
    return byte + d

# multiple commands to interact with sensor firmware
#
def cmd_set_mode(mode=MODE_QUERY):
    if DEBUG:
        print("cmd_set_mode " + str(mode))
    ser.write(construct_command(CMD_MODE, [0x1, mode]))
    read_response()

def cmd_query_data():
    if DEBUG:
        print("cmd_query_data")
    ser.write(construct_command(CMD_QUERY_DATA))
    d = read_response()
    if DEBUG:
        print(d)
    values = []
    # for some reason d[1] is viewed as decimal int not hex; 192 == \xc0
    if d[1] == 192:
        values = process_data(d)
    return values

# sleep = 0 -> work; else -> sleep
def cmd_set_sleep(sleep):
    if DEBUG:
        print("cmd_set_sleep " + str(sleep))
    mode = 0 if sleep else 1
    ser.write(construct_command(CMD_SLEEP, [0x1, mode]))
    read_response()

def cmd_set_working_period(period):
    if DEBUG:
        print("cmd_set_working_period " + str(period))
    ser.write(construct_command(CMD_WORKING_PERIOD, [0x1, period]))
    read_response()

def cmd_firmware_ver():
    if DEBUG:
        print("cmd_firmware_ver")
    ser.write(construct_command(CMD_FIRMWARE))
    d = read_response()
    process_version(d)

def cmd_set_id(id):
    if DEBUG:
        print("cmd_set_id " + str(id))
    id_h = (id>>8) % 256
    id_l = id % 256
    ser.write(construct_command(CMD_DEVICE_ID, [0]*10+[id_l, id_h]))
    read_response()

# if you want to publish data via MQTT, needs host to run
def pub_mqtt(jsonrow):
    cmd = ['mosquitto_pub', '-h', MQTT_HOST, '-t', MQTT_TOPIC, '-s']
    print('Publishing using:', cmd)
    with subprocess.Popen(cmd, shell=False, bufsize=0, stdin=subprocess.PIPE).stdin as f:
        json.dump(jsonrow, f)

def turn_shelly_off(shelly_ip):
    try:
        shelly_resp = requests.get("http://"+shelly_ip+"/light/0?turn=off", auth=shelly_login)
        if (shelly_resp.status_code != 200):
            print(str(shelly_ip) + ": " + shelly_resp.text)
        else:
            print(str(shelly_ip) + ": turned off") 
    except Exception as e:
        print(str(shelly_ip) + ":\n" + str(e))

def turn_shelly_on(shelly_ip):
    try:
        shelly_resp = requests.get("http://"+shelly_ip+"/light/0?turn=on", auth=shelly_login)
        if (shelly_resp.status_code != 200):
            print(str(shelly_ip) + ": " + shelly_resp.text)
        else:
            print(str(shelly_ip) + ": turned on") 
    except Exception as e:
        print(str(shelly_ip) + ":\n" + str(e))

# main
if __name__ == "__main__":
    print("Starting...")
    print(read_response())
    input()