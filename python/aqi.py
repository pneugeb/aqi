#!/usr/bin/python -u
# coding=utf-8
# "DATASHEET": http://cl.ly/ekot
# https://gist.github.com/kadamski/92653913a53baf9dd1a8

import serial, struct, sys, time, json, subprocess, datetime
import board, adafruit_lps2x, adafruit_dht
import sqlite3, os
import requests
from requests.auth import HTTPBasicAuth
import traceback


# init lists for air quality calculation
pm25_avg_10 = []
pm10_avg_10 = []

# active hours config
# after these hours the script will not run
active_hour_start = 7
active_hour_end = 23


# Shelly bulb configs
shelly_login = HTTPBasicAuth('user', 'password')
ip_shelly_p = "192.168.178.1"
ip_shelly_t = "192.168.178.1"
# modes; using ip/light/0? endpoint
off_mode = "turn=off"
smoke_mode = "turn=on&mode=color&red=255&green=0&blue=0&gain=20"
high_humid_mode = "turn=on&mode=color&red=155&green=175&blue=255&gain=1"
crashed_mode = "turn=on&mode=color&red=255&green=17&blue=249&gain=20"



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

JSON_FILE = "/var/www/html/aqi.json"
SHELLY_TIME_FILE = "/home/smoke/shelly_active_times.json"

MQTT_HOST = ''
MQTT_TOPIC = ''

# initialize SDS011 port
ser = serial.Serial()
ser.port = "/dev/ttyUSB0"
ser.baudrate = 9600
ser.timeout = 5
#print(ser)

ser.open()
# ser.flushInput() depricated, now:
ser.reset_input_buffer()


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
    # encode to byte
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
        # sometimes when putting sds011 to work mode (cmd_set_sleep(0)) ser.read() returns b'' but 
        # mode seems to have been changed successfully. returns error
        if (byte == b''):
            print("ser.read() resulted in b''")
            return "ser.read() error: read b''"

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
    values = [0, 0]
    # for some reason d[1] is viewed as decimal int not hex; 192 == \xc0
    if d[1] == 192:
        values = process_data(d)
    return values

# sleep = 0 -> work; 1/else -> sleep
def cmd_set_sleep(sleep):
    if DEBUG:
        print("cmd_set_sleep " + str(sleep))
    # mode 0 = sleep; 1 = work
    mode = 0 if sleep else 1
    ser.write(construct_command(CMD_SLEEP, [0x1, mode]))
    global nova_is_asleep
    nova_is_asleep = sleep
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

def shelly_lamp_control(shelly_ip, mode):
    # used to turn shelly on and off, use off_mode
    try:
        shelly_resp = requests.get("http://" + shelly_ip + "/light/0?" + mode, auth=shelly_login)
        if (shelly_resp.status_code == 200):
            print(str(shelly_ip) + ": turned on " + str([mode_name for mode_name in globals() if globals()[mode_name] is mode]))
        else:
            print(str(shelly_ip) + ": " + shelly_resp.text)
    except Exception as e:
        print(str(shelly_ip) + ":\n" + str(e)) 

def turn_shelly_on(mode):
    # don't turn on during scheduled off time
    try:
        with open(SHELLY_TIME_FILE) as json_data:
            dec_data = json.load(json_data)
            p_start = dec_data["p_start"]
            p_end = dec_data["p_end"]
            t_start = dec_data["t_start"]
            t_end = dec_data["t_end"]
    except Exception as e:
        print(e)
        p_start = "0:00"
        p_end = "23:59"
        t_start = "0:00"
        t_end = "23:59"
    # turn into hours and minutes
    p_start_hour, sep, p_start_minutes = p_start.partition(":")
    p_end_hour, sep, p_end_minutes = p_end.partition(":")
    t_start_hour, sep, t_start_minutes = t_start.partition(":")
    t_end_hour, sep, t_end_minutes = t_end.partition(":")

    # turn into datetime object that can be used for comparing
    dt_now = datetime.datetime.now()
    p_start_dt = dt_now.replace(hour=int(p_start_hour), minute=int(p_start_minutes), second=0, microsecond=0)
    p_end_dt = dt_now.replace(hour=int(p_end_hour), minute=int(p_end_minutes), second=0, microsecond=0)
    t_start_dt = dt_now.replace(hour=int(t_start_hour), minute=int(t_start_minutes), second=0, microsecond=0)
    t_end_dt = dt_now.replace(hour=int(t_end_hour), minute=int(t_end_minutes), second=0, microsecond=0)

    # turn lamps off if after that time
    if (dt_now < p_start_dt or dt_now > p_end_dt):
        print("lamp stays off, active hours: {} - {}".format(p_start, p_end))
        shelly_lamp_control(ip_shelly_p, off_mode)
    else:
        shelly_lamp_control(ip_shelly_p, mode)

    if (dt_now < t_start_dt or dt_now > t_end_dt):
        print("lamp stays off, active hours: {} - {}".format(t_start, t_end))
        shelly_lamp_control(ip_shelly_t, off_mode)
    else:
        shelly_lamp_control(ip_shelly_t, mode)

    

def get_lps25():
    print("LPS25:")
    global lps_temp
    global lps_pressure
    lps_temp = 0
    lps_pressure = 0
    # try 2x bc first one is sometimes way off
    repeat_amount = 2
    for x in range(repeat_amount):
        lps_temp = float("{:.2f}".format(lps.temperature))
        lps_pressure = float("{:.2f}".format(lps.pressure))
        print(
            "Temp: {:.2f} C    Pressure: {:.2f} hPa".format(
                lps_temp, lps_pressure
                )
            )
        # skip sleep on last readout
        if (x < (repeat_amount - 1)):
            time.sleep(2)

def get_dht():
    print("DHT:")
    global dht_temp
    global dht_humidity
    dht_temp = 0
    dht_humidity = 0
    # try 5 times if can't read
    repeat_amount = 5
    for x in range(repeat_amount):
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
        except TypeError as error:
            # happens if the first readout goes worng
            print(error)
            time.sleep(1)
            # if we never get a good result just set 0 so it doesnt crash
            dht_temp = 0
            dht_humidity = 0
            continue
        except Exception as error:
            print("==========")
            print(error)
            print("==========")
            time.sleep(1)
        # skip sleep on last readout
        if (x < (repeat_amount - 1)):
            time.sleep(1)

def get_sds011():
    global pm25
    global pm10
    pm25 = 0
    pm10 = 0
    # give it 30s to get going
    print("giving SDS011 30s to get going")
    time.sleep(30)
    # get NOVA SDS011 pm2.5 and pm10, uses last one
    print("NOVA SDS011:")
    for t in range(2):
        values = cmd_query_data()
        if values is not None and len(values) == 2:
            pm25 = values[0]
            pm10 = values[1]
            print("PM2.5: ", values[0], ", PM10: ", values[1])
            # don't sleep on last run
            if (t < 1):
                time.sleep(5)

def calc_pm25_avg():
    # pm25 calc average over last 10
    global pm25_avg
    global pm25_avg_10
    pm25_avg = 0

    if len(pm25_avg_10) == 10:
        pm25_avg_10.pop(0)
    pm25_avg_10.append(pm25)

    for i in pm25_avg_10:
        pm25_avg += i
    pm25_avg /= len(pm25_avg_10)

def calc_pm10_avg():
    # pm10 average calc over last 10
    global pm10_avg
    global pm10_avg_10
    pm10_avg = 0

    if len(pm10_avg_10) == 10:
        pm10_avg_10.pop(0)
    pm10_avg_10.append(pm10)

    for i in pm10_avg_10:
        pm10_avg += i
    pm10_avg /= len(pm10_avg_10)

def check_humidity():
    # get LPS25
    get_lps25()

    # get DHT
    get_dht()

    # also don't run if humidity > 70% or temp < -10 or > +50°C, will screw data or damage device
    # https://forum.sensor.community/t/dehumidifier-for-pm-measurements/364/3
    if (dht_humidity >= 70 or lps_temp <= -10 or lps_temp >= 45):
        while True:
            print("\nTime: " + str(time.strftime("%H:%M:%S")))
            print("WARNING: \ndht_humidity: " + str(dht_humidity) + "%\nlps_temp: " + str(lps_temp) + "°C")
            turn_shelly_on(high_humid_mode)
            print("Turning off for 3min")
            time.sleep(180)
            get_dht()
            get_lps25()
            # values always -1 to give it small buffer so if does't switch often
            if (dht_humidity < 69 and lps_temp > -9 and lps_temp < 44):
                print("\Exiting loop: \ndht_humidity: " + str(dht_humidity) + "\nlps_temp: " + str(lps_temp))
                turn_shelly_on(off_mode)
                # reset lists for avg calc if normal values have significantly risen during the high humidity period
                global pm25_avg_10
                global pm10_avg_10
                pm25_avg_10 = []
                pm10_avg_10 = []
                break

def main():
    # globals
    global pm25_avg_10
    global pm10_avg_10
    # init shelly
    print("Initializing shelly...")
    turn_shelly_on(off_mode)
    lamp_is_on = 0
    # init SDS011
    print("Starting...")
    cmd_set_sleep(0)
    print("firmware:")
    cmd_firmware_ver()
    cmd_set_working_period(PERIOD_CONTINUOUS)
    cmd_set_mode(MODE_QUERY)
    while True:
        print("\nNew readout starting at " + str(time.strftime("%d.%m.%Y %H:%M:%S")))

        # pause if high humidity
        # get DHT & LPS25 sensors via this function, results set to global
        check_humidity()

        # at night, don't run to save sensor life 
        dt_now = datetime.datetime.now()
        if (dt_now.hour >= active_hour_end or dt_now.hour < active_hour_start):
            print("Going to sleep...")
            print("Turning off all shelly lamps...")
            turn_shelly_on(off_mode)
            # putting it to sleep while its already sleeping often causes system to be stuck
            if nova_is_asleep:
                print("SDS011 is already asleep")
            else:
                print("Putting SDS011 to sleep...")
                cmd_set_sleep(1)
            
            # calculates seconds till next morning start time
            sec_till_start_today = int((datetime.datetime(dt_now.year, dt_now.month, dt_now.day, active_hour_start) - dt_now).total_seconds())
            # test if dt_now.day + 1 is out of range, if so go to new month
            try:
                sec_till_start_tomorrow = int((datetime.datetime(dt_now.year, dt_now.month, (dt_now.day + 1), active_hour_start) - dt_now).total_seconds())
            except ValueError:
                sec_till_start_tomorrow = int((datetime.datetime(dt_now.year, (dt_now.month + 1), 1, active_hour_start) - dt_now).total_seconds())
            sleeptime = sec_till_start_today if (dt_now.hour < active_hour_start) else sec_till_start_tomorrow
            # convert seconds to hh.mm.ss
            print("Sleeping for " + str(datetime.timedelta(seconds=sleeptime)) + "h")
            time.sleep(sleeptime)
            # reset lists for avg calc if normal values have significantly risen during sleep
            pm25_avg_10 = []
            pm10_avg_10 = []
            # pause if high humidity
            check_humidity()
        
        # wake SDS011 up
        cmd_set_sleep(0)
        
        get_sds011()
        
        # put SDS011 to sleep
        cmd_set_sleep(1)

        # config fpr turning lamps on
        print("AVGS:")
        if lamp_is_on:
            # wenn Werte wieder gefallen sind, lampen wieder aus und mit avg calc weitermachen
            if (pm25 < (2 * pm25_avg) and pm10 < (2 * pm10_avg)):
                # check if values are low for two consecutive measurements
                if sds011_low_twice_in_row:
                    print("Low again\npm25_avg = {}\npm10_avg = {}".format(
                        pm25_avg, pm10_avg
                        )
                    )
                    turn_shelly_on(off_mode)
                    lamp_is_on = 0
                    # add latest pm25 & pm10 to avg list
                    calc_pm25_avg()
                    calc_pm10_avg()
                else:
                    print("Low again, waiting for second measurement confirmation\npm25_avg = {}\npm10_avg = {}".format(
                        pm25_avg, pm10_avg
                        )
                    )
                    sds011_low_twice_in_row = 1
            # wenn Werte noch hoch sind bleiben die Lampen an
            else:
                turn_shelly_on(smoke_mode)
                print("Limit still exceeded\npm25_avg = {}\npm10_avg = {}\nturning lamps on".format(
                    pm25_avg, pm10_avg
                    )
                )
                sds011_low_twice_in_row = 0
        else:
            # if lamp is off, calc avgs. If it turns out there is a high measurment, the last element added to pm25_avg_10 will be removed
            calc_pm25_avg()
            calc_pm10_avg()
            # if lamp is off, calc averages and check if lamp needs to be turned on
            #   only turn on for pm25, pm10 values tend to fluctuate quite a bit
            if (pm25 >= (2 * pm25_avg)):
                print("Limit exceeded\npm25_avg = {}\npm10_avg = {}\nturning lamps on".format(
                    pm25_avg, pm10_avg
                    )
                )
                turn_shelly_on(smoke_mode)
                # pop last element, which is measurment of high aqi
                pm25_avg_10.pop()
                pm10_avg_10.pop()
                # is_on switch sodass erst wieder aus wenn alte werte erreicht werden
                lamp_is_on = 1
                sds011_low_twice_in_row = 0
            else:
                turn_shelly_on(off_mode)
                print("Low averages\npm25_avg = {}\npm10_avg = {}".format(
                    pm25_avg, pm10_avg
                    )
                )
        
        # save to sqlite3 db
        # logs time in UTC i think: 5 - 21 o'clock in DB
        cur.execute('''INSERT INTO data (date,pm25,pm10,lps_temp,lps_pressure,dht_temp,dht_humidity) 
            VALUES (datetime('now'), ?, ?, ?, ?, ?, ?)''', 
            (pm25, pm10, lps_temp, lps_pressure, dht_temp, dht_humidity)
            )
        con.commit()
        print("commited data to aqi.db")
        if DEBUG:
            print("pm25, pm10, lps_temp, lps_pressure, dht_temp, dht_humidity")
            print(pm25, pm10, lps_temp, lps_pressure, dht_temp, dht_humidity)

        # get db size
        db_size = os.path.getsize("aqi.db")

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

# main
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n\n== RIP ==\n")
        print(e)
        traceback.print_exc()
        # if it crashed turns lamps on, try this regularly if wifi can't connect
        while True:
            turn_shelly_on(crashed_mode)
            time.sleep(600)
