import time
import board
import microcontroller
from digitalio import DigitalInOut, Direction, Pull
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix
from adafruit_datetime import datetime, date, timedelta
import adafruit_requests

DEBUG=True
TIME_FETCH_INTERVAL = 60

network = Network(status_neopixel=board.NEOPIXEL, debug=True)
locations = {
    #"home": "America/Los_Angeles", 
    "India": "Asia/Kolkata",
    "Jerusalem": "Asia/Jerusalem",
    "New York": "America/New_York",
    }

def get_time():
    """ get local time information from from the net and return list of (location, time)"""
    times = {}
    for location, tz in locations.items():
        res = network.fetch("http://worldtimeapi.org/api/timezone/"+tz)
        #times[location] = datetime.fromtimestamp(res.json()['unixtime']-res.json()['raw_offset'])+timedelta(seconds=1)
        if res:
            times[location] = datetime.fromisoformat(res.json()['datetime'])+timedelta(seconds=1)
        else:
            print("Error", res.status_code, res.text)
    return times

def get_local_time():
    res = network.fetch("http://worldtimeapi.org/api/timezone/America/Los_Angeles")
    return datetime.fromtimestamp(res.json()['unixtime'])

# isoformat().split('T')[1].split('.')[0]
now = get_time()
second_counter = 0
for location, ts in now.items():
    if DEBUG: print(location, now[location].isoformat().split('T')[1].split('.')[0])
last = time.monotonic()
while True:
    try:
        if time.monotonic() - last >= 1:
            last+=1
            for location, ts in now.items():
                now[location] += timedelta(seconds = 1)
                if DEBUG: print(location, now[location].isoformat().split('T')[1].split('.')[0])
            second_counter += 1 
            if second_counter >= TIME_FETCH_INTERVAL * 60:
                last = time.monotonic()
                now = get_time()
                second_counter = 0
        
        time.sleep(0.2)
    except RuntimeError as e:
        print("Error", e)
        continue
    except adafruit_requests.OutOfRetries as e:
        print("Error retrieveing data", e)
        continue
