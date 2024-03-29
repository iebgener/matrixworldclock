import time
import board
import microcontroller
from digitalio import DigitalInOut, Direction, Pull
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix
from adafruit_datetime import datetime, date, timedelta
import adafruit_requests

DEBUG=True
TIME_FETCH_INTERVAL = 20

# initilize network object
network = Network(status_neopixel=board.NEOPIXEL, debug=True)

# a dict of three locations and their ISO time zone to be displayed
locations = {
    "India": "Asia/Kolkata",
    "Jerusalem": "Asia/Jerusalem",
    "New York": "America/New_York",
    }


def get_time():
    """ get local time information from from the net and return list of (location, time)"""
    times = {}
    for location, tz in locations.items():
        res = network.fetch("http://worldtimeapi.org/api/timezone/"+tz)
        if res:
            # get the returned timestamp ISO format and add a second
            times[location] = datetime.fromisoformat(res.json()['datetime'])
        else:
            print("Error", res.status_code, res.text)
    return times

# `now` holds the local time for all locations
now = get_time()

# second_counter coutns the numebr of seconds so every TIME_FETCH_INTERVAL*60 will trigget network update to time
second_counter = 0

# pirint initial local times
for location, ts in now.items():
    if DEBUG: print(location, now[location].isoformat().split('T')[1].split('.')[0])

# loop
# last will hold the last read for time to manage how often we refresh the seconds
last = time.monotonic()
while True:
    try:
        # check if a second past to update the current time, and check if its time to fetch the time from the net 
        if time.monotonic() - last >= 1:
            last+=1
            # if seconds in in 10 to 50 range, adv the seconds by one and copy to all locations so they will be the same
            #otherwise just add 1 second to each (the reason is to allow rolling the minute/hours/days when closer to 60 or right after 01)
            seconds = now[list(now)[0]].second
            seconds+=1
            if seconds in range(10, 50):
                for location, ts in now.items():
                    now[location] = now[location].replace(second=seconds)
            else:
                for location, ts in now.items():
                    now[location] += timedelta(seconds = 1)
            for location, ts in now.items():
                if DEBUG: print(location, now[location].isoformat().split('T')[1].split('.')[0])
            
            # this section handles when to fetch the data from all sites
            second_counter += 1 
            if second_counter >= TIME_FETCH_INTERVAL * 60:
                last = time.monotonic()
                now = get_time()
                second_counter = 0
        # no need to busy loop, enough to check the time every 200 millis 
        time.sleep(0.2)
    except RuntimeError as e:
        print("Error", e)
        # todo - show a error signal on the  matric to show a problem
        continue
    except adafruit_requests.OutOfRetries as e:
        # if netowrk isn't avail just try the next hour
        # todo - set a n indicator to show that time is not in sync
        print("Error retrieveing data", e)
        continue
