# aqi
Measure AQI with a Raspberry pi zero 2, Nova SDS011, DHT22 and LPS25 sensor.

The measurments are available via a self hosted website and get saved in a sqlite3 database.

The system uses Shelly RGBW light bulbs that turn on red when a high pm2.5 or pm10 concentration is detected

install:
https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi

logs:
/var/www/html/logs
to be able to be accessed by web server


# to-do:
[] read lps25 and dht while sds011 gets ready for speedup
[] improve wifi connection stability
[] db_analysis: analyse daily patters eg if smoke at 8 also at 10
[]db_analysis: only use days that have 100% data, results will be spoofed if some hours missing
[] maybe dont turn on while building list, so that if first measurment is atypically low it wont stay on forever
[] why it keep stopping