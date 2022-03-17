#!/usr/bin/python -u
# coding=utf-8
# "DATASHEET": http://cl.ly/ekot
# https://gist.github.com/kadamski/92653913a53baf9dd1a8

from re import A
import serial, struct, sys, time, json, subprocess, datetime
import board, adafruit_lps2x, adafruit_dht
import sqlite3, os
import requests
from requests.auth import HTTPBasicAuth


# active hours config
# after these houres the script will not run
active_hour_start = 6
active_hour_end = 22
sleeptime = (24 - active_hour_end + active_hour_start) * 3600


# Shelly bulb configs
shelly_login = HTTPBasicAuth('user', 'password')
ip_shelly_p = "192.168.0.1"
ip_shelly_t = "192.168.0.1"
pm25_limit = 30
pm10_limit = 50

try:
    shelly_p_init = requests.get("http://"+ip_shelly_p+"/light/0?turn=off&mode=color&red=255&green=0&blue=0&gain=10", auth=shelly_login)
    shelly_t_init = requests.get("http://"+ip_shelly_t+"/light/0?turn=off&mode=color&red=255&green=0&blue=0&gain=10", auth=shelly_login)
    if (shelly_p_init.response_code != 200 or shelly_t_init.response_code != 200):
        print("Error in initializing shelly:")
        print(shelly_p_init.text)
        print(shelly_t_init.text)
except Exception as e:
    print(e)


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

ser.open()
ser.flushInput()

byte, data = 0, ""

# initialize LPS25
i2c = board.I2C()
lps = adafruit_lps2x.LPS25(i2c)

# Initial the dht device, with data pin connected to:
dhtDevice = adafruit_dht.DHT22(board.D4, use_pulseio=False)

# Initialize sqlite3 db
con = sqlite3.connect("aqi.db")
cur = con.cursor()
# will create db on first run and then say db exists already
try:
    cur.execute('''CREATE TABLE data
    (ID INTEGER PRIMARY KEY AUTOINCREMENT,
    DATE TEXT,
    PM25 REAL,
    PM10 REAL,
    LPS_TEMP REAL,
    LPS_PRESSURE REAL,
    DHT_TEMP REAL,
    DHT_HUMIDITY REAL);''')

except Exception as e:
    print(e)


# nova SDS011 functions
#
# print all data d in hex
def dump(d, prefix=''):
    print(prefix + ' '.join(x.encode('hex') for x in d))

# build command to give to port
def construct_command(cmd, data=[]):
    assert len(data) <= 12
    data += [0,]*(12-len(data))
    checksum = (sum(data)+cmd-2)%256
    ret = "\xaa\xb4" + chr(cmd)
    ret += ''.join(chr(x) for x in data)
    ret += "\xff\xff" + chr(checksum) + "\xab"

    if DEBUG:
        dump(ret, '> ')
    return ret

# processes input data d and returns pm25 and pm10
def process_data(d):
    r = struct.unpack('<HHxxBB', d[2:])
    pm25 = r[0]/10.0
    pm10 = r[1]/10.0
    checksum = sum(ord(v) for v in d[2:8])%256
    return [pm25, pm10]
    #print("PM 2.5: {} μg/m^3  PM 10: {} μg/m^3 CRC={}".format(pm25, pm10, "OK" if (checksum==r[2] and r[3]==0xab) else "NOK"))

# print software version; used in cmd_firmware_ver()
def process_version(d):
    r = struct.unpack('<BBBHBB', d[3:])
    checksum = sum(ord(v) for v in d[2:8])%256
    print("Y: {}, M: {}, D: {}, ID: {}, CRC={}".format(r[0], r[1], r[2], hex(r[3]), "OK" if (checksum==r[4] and r[5]==0xab) else "NOK"))

# read response from serial port
def read_response():
    byte = 0
    while byte != "\xaa":
        byte = ser.read(size=1)

    d = ser.read(size=9)

    if DEBUG:
        dump(d, '< ')
    return byte + d

# multiple commands to interact with sensor firmware
#
def cmd_set_mode(mode=MODE_QUERY):
    ser.write(construct_command(CMD_MODE, [0x1, mode]))
    read_response()

def cmd_query_data():
    ser.write(construct_command(CMD_QUERY_DATA))
    d = read_response()
    values = []
    if d[1] == "\xc0":
        values = process_data(d)
    return values

# sleep = 0 -> work; else -> sleep
def cmd_set_sleep(sleep):
    mode = 0 if sleep else 1
    ser.write(construct_command(CMD_SLEEP, [0x1, mode]))
    read_response()

def cmd_set_working_period(period):
    ser.write(construct_command(CMD_WORKING_PERIOD, [0x1, period]))
    read_response()

def cmd_firmware_ver():
    ser.write(construct_command(CMD_FIRMWARE))
    d = read_response()
    process_version(d)

def cmd_set_id(id):
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

# main
if __name__ == "__main__":
    cmd_set_sleep(0)
    cmd_firmware_ver()
    cmd_set_working_period(PERIOD_CONTINUOUS)
    cmd_set_mode(MODE_QUERY);
    while True:
        # at night, don't run to save sensor life 
        if (datetime.datetime.now().hour >= active_hour_end):
            print("Sleeping for " + (sleeptime/3600) + "h")
            time.sleep(sleeptime)
        # wake SDS011 up
        cmd_set_sleep(0)
        # get NOVA SDS011 pm2.5 and pm10
        print("NOVA SDS011:")
        for t in range(15):
            values = cmd_query_data();
            if values is not None and len(values) == 2:
                pm25 = values[0]
                pm10 = values[1]
                print("PM2.5: ", pm25, ", PM10: ", pm10)
                time.sleep(2)
        
        # put SDS011 to sleep
        cmd_set_sleep(1)
        
        # get LPS25
        print("LPS25:")
        # try 2x bc first one is sometimes way off
        for x in range(2):
            lps_temp = lps.temperature
            lps_pressure = lps.pressure
            print(
                "Temp: {:.1f} C    Pressure: {:.1f} hPa".format(
                    lps_temp, lps_pressure
                    )
                )
            time.sleep(1)

        # get DHT
        print("DHT:")
        # try 5 times if can't read
        dht_temp = 0
        dht_humidity = 0
        for x in range(5):
            try:
                # Print the values to the serial port
                dht_temp = dhtDevice.temperature
                dht_humidity = dhtDevice.humidity
                print(
                    "Temp: {:.1f} C    Humidity: {}% ".format(
                        dht_temp, dht_humidity
                    )
                )

            except RuntimeError as error:
                # Errors happen fairly often, DHT's are hard to read, just keep going
                print(error.args[0])
                time.sleep(1)
                continue
            except Exception as error:
                dhtDevice.exit()
                con.commit()
                con.close()
                raise error
        
        # turn light bulb on if limits exceeded
        try:
            if (pm25 > pm25_limit or pm10 > pm10_limit):
                shelly_p_resp = requests.get("http://"+ip_shelly_p+"/light/0?turn=on", auth=shelly_login)
                shelly_t_resp = requests.get("http://"+ip_shelly_t+"/light/0?turn=on", auth=shelly_login)
                if (shelly_p_resp.response_code != 200 or shelly_t_resp.response_code != 200):
                    print("Shelly error:")
                    print(shelly_p_resp.text)
                    print(shelly_t_resp.text)
            else:
                shelly_p_resp = requests.get("http://"+ip_shelly_p+"/light/0?turn=off", auth=shelly_login)
                shelly_t_resp = requests.get("http://"+ip_shelly_t+"/light/0?turn=off", auth=shelly_login)
                if (shelly_p_resp.response_code != 200 or shelly_t_resp.response_code != 200):
                    print("Shelly error:")
                    print(shelly_p_resp.text)
                    print(shelly_t_resp.text)
        except Exception as e:
            print("Shelly error:")
            print(e)

        # save to sqlite3 db
        cur.execute('''INSERT INTO data (date,pm25,pm10,lps_temp,lps_pressure,dht_temp,dht_humidity) 
            VALUES (datetime('now'), ?, ?, ?, ?, ?, ?)''', 
            (pm25, pm10, lps_temp, lps_pressure, dht_temp, dht_humidity)
            )
        con.commit()
        print("pm25, pm10, lps_temp, lps_pressure, dht_temp, dht_humidity")
        print(pm25, pm10, lps_temp, lps_pressure, dht_temp, dht_humidity)

        # get db size
        db_size = os.path.getsize("test.db")

        # load stored data for website
        try:
            with open(JSON_FILE) as json_data:
                data = json.load(json_data)
        except IOError as e:
            print(e)
            data = []

        # check if length is more than 100 and delete first element
        if len(data) > 100:
            data.pop(0)

        # append new values
        jsonrow = {'time': time.strftime("%d.%m.%Y %H:%M:%S"), 'pm25': pm25, 'pm10': pm10, 'lps_temp': lps_temp, 'lps_pressure': lps_pressure, 'dht_temp': dht_temp, 'dht_humidity': dht_humidity, 'db_size': db_size}
        data.append(jsonrow)

        # save it
        with open(JSON_FILE, 'w') as outfile:
            json.dump(data, outfile)

        # add MQTT_HOST if you want to publish via MQTT
        if MQTT_HOST != '':
            pub_mqtt(jsonrow)

        # sleep    
        print("Going to sleep for 30 secs...")
        time.sleep(30)
