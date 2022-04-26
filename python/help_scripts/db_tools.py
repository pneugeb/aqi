#!/usr/bin/python -u
# coding=utf-8

import sqlite3

# Initialize sqlite3 db
con = sqlite3.connect("aqi.db")
cur = con.cursor()

# save to sqlite3 db
cur.execute("SELECT * FROM data LIMIT 10")
rows = cur.fetchall()
for row in rows:
    print(row)
print("done")
con.close()
