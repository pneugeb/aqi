#!/usr/bin/python -u
# coding=utf-8

import json, os

JSON_FILE = "shelly_active_times.json"

# i can't get clear to work in plink, disabled it in prod
clearConsole = lambda: os.system('cls' if os.name in ('nt', 'dos') else 'clear')
#clearConsole = lambda: print("c'ls")

def get_hour():
    try:
        hour = int(input("hour: "))
    except Exception as e:
        print(e)
        return get_hour()
    if (hour < 0 or hour > 23):
        print("only values 0-23 pls")
        return get_hour()
    return hour

def get_minutes():
    try:
        minutes = int(input("minutes: "))
    except Exception as e:
        print(e)
        return get_minutes()
    if (minutes < 0 or minutes > 59):
        print("only values 0-59 pls")
        print("try again:")
        return get_minutes()
    elif (minutes < 10):
        return "0{}".format(minutes)
    return minutes

def get_time():
    time = "{}:{}".format(get_hour(), get_minutes())
    return time
 
def check_p_or_t():
    print("\nwhich do you want to edit?")
    lamp = input("[p] or [t]?\n> ")
    if (lamp in ["p", "P"]):
        return "p"
    elif (lamp in ["t", "T"]):
        return "t"
    else:
        return check_p_or_t()

if __name__ == "__main__":
    # load old data
    try:
        with open(JSON_FILE) as json_data:
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
    
    clearConsole()
    print("Current settings:\np_start: {}\np_end: {}\nt_start: {}\nt_end: {}\n".format(p_start, p_end, t_start, t_end))

    
    # which shelly u want to edit?
    which_one = check_p_or_t()

    if (which_one == "p"):
        clearConsole()
        print("\nshelly_p active hours")
        print("\nstart time: ")
        p_start = get_time()
        print("\nend time: ")
        p_end = get_time()
    else:
        clearConsole()
        print("\nshelly_t active hours")
        print("\nstart time: ")
        t_start = get_time()
        print("\nend time: ")
        t_end = get_time()
    

    data = {"p_start": p_start, "p_end": p_end, "t_start": t_start, "t_end": t_end}

    with open(JSON_FILE, "w") as outfile:
        json.dump(data, outfile)
        clearConsole()
        #print("Result:")
        #print(data)

    print("\nCurrent settings:\np_start: {}\np_end: {}\nt_start: {}\nt_end: {}\n".format(p_start, p_end, t_start, t_end))
    input("press enter to finish...")
