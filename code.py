import time
import board
#import microcontroller
#from digitalio import DigitalInOut, Direction, Pull
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix
from adafruit_datetime import datetime, date, timedelta
import adafruit_requests
#from adafruit_ticks import ticks_ms, ticks_add, ticks_diff
from adafruit_pm25.i2c import PM25_I2C
import adafruit_ahtx0
#from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font
import terminalio
import displayio
from digitalio import DigitalInOut, Direction, Pull

DEBUG=True
TIME_FETCH_INTERVAL = 20
ENV_REFRESH_INTERVAL = 1

#init button
btn = DigitalInOut(board.BUTTON_UP )
btn.direction = Direction.INPUT
btn.pull = Pull.UP
#setup graphics
matrix = Matrix()
display = matrix.display
# Set the location
# text_area.x = 0
# text_area.y = 4
font = terminalio.FONT
font_down = bitmap_font.load_font("/fonts/MartianMono_Condensed-Regular-6px.bdf")
font_down = bitmap_font.load_font("/fonts/RobotoMono-Regular-5pt.bdf")
font = bitmap_font.load_font("/fonts/RobotoMono-Regular-7pt.bdf")
color = 0x0000BF
# Show it
group = displayio.Group()


# init temp
sensor = adafruit_ahtx0.AHTx0(board.I2C())

# setup air quality sensor
i2c = board.STEMMA_I2C()

reset_pin = None

pm25 = PM25_I2C(i2c, reset_pin)
aqdata = pm25.read()


# initilize network object
network = Network(status_neopixel=board.NEOPIXEL, debug=True)

# a dict of three locations and their ISO time zone to be displayed
locations = {
    "DEL": "Asia/Kolkata",
    "JER": "Asia/Jerusalem",
    "NYC": "America/New_York",
    }
labels = {
    "DEL": label.Label(font, text="JER 12:55", color=color),
    "JER": label.Label(font, text="DEL 12:55", color=color),
    "NYC": label.Label(font, text="NYC 12:55", color=color),
 }

labels['DEL'].x = 0
labels['DEL'].y = 3
labels['JER'].x = 0
labels['JER'].y = 3+7+1
labels['NYC'].x = 0
labels['NYC'].y = 3+14+2

AQILabel = label.Label(font=font_down, text=" "*20, color=0xdddddd)
AQILabel.x=0
AQILabel.y=27

#setup satus
status = displayio.Bitmap(2,2,3)
status_palette = displayio.Palette(3)
status_palette[0] = 0x00ff00
status_palette[1] = 0xff0000
status_palette[2] = 0xfffb00
status_tile = displayio.TileGrid(status, pixel_shader=status_palette)
def set_status(status, color):
    status[0,0] = color
    status[1,0] = color
    status[0,1] = color
    status[1,1] = color

set_status(status,0)
status_g = displayio.Group()
#status_g.append(status_tile)
status_tile.x=62
status_tile.hidden = False




group.append(labels["DEL"])
group.append(labels["JER"])
group.append(labels["NYC"])
group.append(status_tile)
group.append(AQILabel)

display.root_group = group


def get_color(hour_in):
    """ Return color based on hour"""
    # translate to int. If there is a leading zero, then remove it before translating to decimal
    if hour_in[0]=="0":
        hour = int(hour_in[1])
    else:
        hour = int(hour_in)
    if hour in range(6,8):
        return 0x3a2edf #blue
    elif hour in range(8,17):
        return 0x00E000 # green
    elif hour in range(18,23):
        return 0x3a2edf #blue
    else:
        return 0xf54263 # redish pinkish
def updateScreen(now, labels):
    """
    Update the matrix screen with time
    """
    for location, ts in now.items():
        hours,minutes,seconds=now[location].isoformat().split('T')[1].split('.')[0].replace("0","O").split(':')
        color = get_color(hours.replace("O","0"))
        # blink the status
        status_tile.hidden = not status_tile.hidden
        # change hours leading 0 to blank
        if hours[0] == "O":
            hours = f" {hours[1]}"
        # change label only if there is something to change
        if labels[location].text!=f"{location} {hours}:{minutes}":
            labels[location].text=f"{location} {hours}:{minutes}"
            labels[location].color = color


def updatesensor(): 
    try:
        aqdata = pm25.read()
        pm2 = int(aqdata["pm25 standard"])
    except RuntimeError:
        print("Unable to read from PM2.5 sensor, no new data..")
        set_status(status,1)
        pm2=0
    AQILabel.text = f"AQI:{pm2} T:{sensor.temperature:.0f} H:{sensor.relative_humidity:.0f}"
    if DEBUG: print(f"AQI: {pm2} temp: {sensor.temperature} Humidity {sensor.relative_humidity}")

def get_time():
    """ get local time information from from the net and return list of (location, time)"""
    set_status(status,2)
    times = {}
    for location, tz in locations.items():
        res = network.fetch("http://worldtimeapi.org/api/timezone/"+tz)
        if res:
            # get the returned timestamp ISO format and add a second
            times[location] = datetime.fromisoformat(res.json()['datetime'])
        else:
            print("Error", res.status_code, res.text)
    set_status(status,0)
    return times

updatesensor()
# `now` holds the local time for all locations
now = get_time()

updateScreen(now, labels)
# second_counter coutns the numebr of seconds so every TIME_FETCH_INTERVAL*60 will trigget network update to time
second_counter = 0
env_count = 0 # same as the above , but ust for temp metrics

# pirint initial local times
for location, ts in now.items():
    if DEBUG: print(location, now[location].isoformat().split('T')[1].split('.')[0])

# loop
# last will hold the last read for time to manage how often we refresh the seconds
last = time.monotonic() # start the clock referebce
while True:
    # hide unhide display
    if btn.value == False:
        group.hidden = not group.hidden

    try:
        # check if a second past to update the current time, and check if its time to fetch the time from the net 
        if time.monotonic() - last >= 1:
            last+=1 # advance the clock referebce
            # check if 3am in NYC. If so, turn display off
            hours=now["NYC"].hour
            minutes=now["NYC"].minute
            if hours == 3 and minutes ==0:
                group.hidden = True
            if hours == 9 and minutes ==0:
                group.hidden = False
            # if seconds in in 10 to 50 range, adv the seconds by one and copy to all locations so they will be the same
            #otherwise just add 1 second to each (the reason is to allow rolling the minute/hours/days when closer to 60 or right after 01)
            seconds = now[list(now)[0]].second #extract the seconds from the first entry in `now`
            seconds+=1 # add a second
            if seconds in range(10, 50):
                for location, ts in now.items():
                    now[location] = now[location].replace(second=seconds)
            else:
                for location, ts in now.items():
                    now[location] += timedelta(seconds = 1)
            
            #update screen
            updateScreen(now, labels)
            # print debug info

            for location, ts in now.items():
                if DEBUG and ts.second == 0: print(location, now[location].isoformat().split('T')[1].split('.')[0])
            
            # this section handles when to fetch the data from all sites
            second_counter += 1  # advance the overall seconds counter
            if second_counter >= TIME_FETCH_INTERVAL * 60:
                # last = time.monotonic()
                now = get_time() # refresh the time from the time server
                second_counter = 0 # reset the seconds counter so we can coutn again to TIME_FETCH_INTERVAL * 60
            env_count += 1
            if env_count >= ENV_REFRESH_INTERVAL * 60:
            # co2 = scd4x.CO2
            # temp = c_to_f(scd4x.temperature)
            # humidity = scd4x.relative_humidity
                updatesensor()
                env_count = 0
        # no need to busy loop, enough to check the time every 200 millis 
        time.sleep(0.2)
    except RuntimeError as e:
        print("Error", e)
        set_status(status,1)
        # todo - show a error signal on the  matric to show a problem
        continue
    except adafruit_requests.OutOfRetries as e:
        # if netowrk isn't avail just try the next hour
        # todo - set a n indicator to show that time is not in sync
        print("Error retrieveing data", e)
        set_status(status,1)
        continue
