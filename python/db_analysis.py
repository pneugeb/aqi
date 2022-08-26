#!/usr/bin/python -u
# coding=utf-8

import sqlite3
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


DEBUG = 1

# Initialize sqlite3 db
con = sqlite3.connect("aqi.db")
cur = con.cursor()

# save to sqlite3 db
cur.execute("SELECT * FROM data")
rows = cur.fetchall()
# row indices:
# 1: index
# 2: time
# 3: pm25
# 4: pm10
# 5: lps_temp
# 6: lps_pressure
# 7: dht_temp
# 8: dht_humidity
con.close()
'''
t_list = []
for row in rows:
    t1 = int(row[1][5:10].replace("-", ""))
    t_list.append(t1)
print(dict.fromkeys(t_list))
input()
'''
# initialisiert dict, das alle Minuten mit Anzahl der Spikes halten wird 
time_and_spikes = {}
# xticks: ticks auf x-achse, die angezeigt werden
xticks = []
for i in range(24):
    # only use 7 - 23 o'clock (7:00 - 22:59), but logs are in utc so 5 - 21
    if (i >= 5 and i <= 20):
        xticks.append(datetime(2022, 1, 1, i))
        for j in range(60):
            # :02d : 7 -> 07; 33 -> 33
            #time_and_spikes[int("{}{:02d}".format(i, j))] = 0
            time_and_spikes[datetime(2022, 1, 1, i, j)] = 0
# weil 21, 22, 23uhr noch fehlt:
xticks.append(datetime(2022, 1, 1, 21))
xticks.append(datetime(2022, 1, 1, 22))
xticks.append(datetime(2022, 1, 1, 23))
# remove 5 & 6 o'clock
xticks.pop(0)
xticks.pop(0)

'''
Wie es funktioniert:
benutzt modifizierte und verbesserte pm_25_avg functionen wie im prod, die avg_10 lists [] werden zurückgesetzt, 
wenn der Zeitunterschied zwischen zwei Messungen >3min ist. Sonst schlägt die "pm25 >= (2 * pm25_avg)"
an und es wird für die Minute im time_and_spikes dict +1, am Ende wird ein Diagramm erstellt.
'''

# init lists & stuff
pm25_avg_10 = []
pm10_avg_10 = []
lamp_is_on = 0
sds011_low_twice_in_row = 0


def calc_pm25_avg(pm25):
    # pm25 calc average over last 10
    pm25_avg = 0

    if len(pm25_avg_10) == 10:
        pm25_avg_10.pop(0)
    pm25_avg_10.append(pm25)

    for i in pm25_avg_10:
        pm25_avg += i
    pm25_avg /= len(pm25_avg_10)

    return pm25_avg

def calc_pm10_avg(pm10):
    # pm10 average calc over last 10
    pm10_avg = 0

    if len(pm10_avg_10) == 10:
        pm10_avg_10.pop(0)
    pm10_avg_10.append(pm10)

    for i in pm10_avg_10:
        pm10_avg += i
    pm10_avg /= len(pm10_avg_10)

    return pm10_avg
    
# returns True_if_spike, values_still_high both True if a spike was registered. Second one to avoid multiple measurments for one spike 
def check_if_spike(pm25, pm10, still_high):
    pm25_avg = calc_pm25_avg(pm25)
    pm10_avg = calc_pm10_avg(pm10)
    # if already measured but still high
    if (still_high and (pm25 >= (2 * pm25_avg))):
        pm25_avg_10.pop()
        pm10_avg_10.pop()
        return False, True
    # if low again
    elif (still_high):
        return False, False
    # first high measurment
    elif (pm25 >= (2 * pm25_avg)):
        pm25_avg_10.pop()
        pm10_avg_10.pop()
        return True, True
    else:
        return False, False

# remove days where more than 20min are missing
#   checks if difference between two measurements is >3min and then stars counting. If day has >20min missing it will discard that day
def remove_incomplete_days(rows):
    temp_rows = []
    cleaned_up_rows = []
    current_monthday = 101
    hourminute = datetime(2022, 1, 1, 5, 0)
    extra_time = 0

    for row in rows:
        # used to check if new day
        last_monthday = current_monthday
        current_monthday = int(row[1][5:10].replace("-", ""))
        # used to check time differences
        last_hourminute = hourminute
        hour = int(row[1][11:13])
        minute = int(row[1][14:16])
        hourminute = datetime(2022, 1, 1, hour, minute)

        # check if new day
        if (current_monthday > last_monthday):
            print(current_monthday)
            # check time diff from last measurement yesterday
            if ((datetime(2022, 1, 1, 21, 0) - last_hourminute).total_seconds() > 120):
                print("last measurement: {}s at {}".format((datetime(2022, 1, 1, 21, 0) - last_hourminute).total_seconds(), hourminute))
                extra_time += (datetime(2022, 1, 1, 21, 0) - last_hourminute).total_seconds()

            # check if less than 20min missing, if so add rows from temp to cleaned_up
            # also check if more than 
            if (extra_time < (20 * 60)):
                for row in temp_rows:
                    cleaned_up_rows.append(row)
            else:
                print("too much extra time sir: {}s".format(extra_time))
            temp_rows = []
            extra_time = 0

            # check if time missing from first measurement
            diff_start_of_day = (hourminute - datetime(2022, 1, 1, 5, 0)).total_seconds()
            if (diff_start_of_day >= 120):
                print("first measurement: {}s at {}".format(diff_start_of_day, hourminute))
                extra_time += diff_start_of_day

        # add row to temp
        temp_rows.append(row)  

        # check if difference between measurements >3min
        #   if a new day this will be negative, thus extra time wont be added twice
        if ((hourminute - last_hourminute).total_seconds() > 180):
            print("in middle: {}s at {}".format((hourminute - last_hourminute).total_seconds(), hourminute))
            extra_time += (hourminute - last_hourminute).total_seconds()
        
    return cleaned_up_rows


# main
if __name__ == "__main__":
    print("### starting ###")
    repeatedly_high = False
    hourminute = datetime(2022, 1, 1, 1, 1)
    current_monthday = 101
    # counting days and spkies per day
    days = 0
    spikes = 0
    spikes_per_day = 0
    rows = remove_incomplete_days(rows)
    for row in rows:
        pm25 = row[3]
        pm10 = row[4]
        # turns 03.03. into 303, used to check if new day
        last_monthday = current_monthday
        current_monthday = int(row[1][5:10].replace("-", ""))
        # turns 17:50 into "1750", used to compare exact time of measurement. Values in UTC so time 5-21 o'clock
        last_hourminute = hourminute
        hour = int(row[1][11:13])
        minute = int(row[1][14:16])
        hourminute = datetime(2022, 1, 1, hour, minute)
        # if new day
        if (current_monthday > last_monthday):
            #print(current_monthday, last_monthday)
            days += 1
            pm25_avg_10 = []
            pm10_avg_10 = []
        # skip if measurement out of normal hours, there was a bug in the beginning i believe
        if (hourminute < datetime(2022, 1, 1, 5, 0) or hourminute > datetime(2022, 1, 1, 20, 59)):
            continue
        # reset lists if there has been a pause of more than 4min from last measurement or if new day
        if ((hourminute - last_hourminute).total_seconds() > 180):
            #print((hourminute - last_hourminute).total_seconds())
            pm25_avg_10 = []
            pm10_avg_10 = []
        is_spike, repeatedly_high = check_if_spike(pm25, pm10, repeatedly_high)
        if is_spike:
            time_and_spikes[datetime(2022, 1, 1, hour, minute)] += 1
            spikes += 1

    
    # add 5 values into one, means 5 minutes bars
    list_x = []
    list_y = []
    temp_x = list(time_and_spikes.keys())[0] + timedelta(hours=2)
    temp_y = 0
    for i in range(len(time_and_spikes)):
        if (i == 0):
            continue
        if (i % 5 == 0):
            list_x.append(temp_x)
            list_y.append(temp_y)
            temp_x = list(time_and_spikes.keys())[i] + timedelta(hours=2)
            temp_y = 0
        else:
            temp_y += int(list(time_and_spikes.values())[i])
    
    spikes_per_day = spikes / days
    
    # create plot diagramm
    fig, ax = plt.subplots()  # Create a figure containing a single axes.
    fig.autofmt_xdate()
    ax.bar(list_x, list_y, width=0.003)  # Plot some data on the axes.
    xfmt = mdates.DateFormatter('%H:%M')
    ax.xaxis.set_major_formatter(xfmt)
    plt.title("AQI messdaten Auswertung, Tage: {}  Spikes/Tag: {}".format(days, spikes_per_day))
    plt.subplots_adjust(left=0.07, right=0.95, top=0.9, bottom=0.1)
    plt.xticks(xticks)
    plt.show()
    print("done")

