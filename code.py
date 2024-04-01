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
import rgbmatrix
import framebufferio

DEBUG=True
TIME_FETCH_INTERVAL = 20
ENV_REFRESH_INTERVAL = 1

# setup display
bit_depth = 2
base_width = 64
base_height = 32
chain_across = 1
tile_down = 2
serpentine = True

width = base_width * chain_across
height = base_height * tile_down

addr_pins = [board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC, board.MTX_ADDRD]
rgb_pins = [
    board.MTX_R1,
    board.MTX_G1,
    board.MTX_B1,
    board.MTX_R2,
    board.MTX_G2,
    board.MTX_B2,
]
clock_pin = board.MTX_CLK
latch_pin = board.MTX_LAT
oe_pin = board.MTX_OE

displayio.release_displays()
matrix = rgbmatrix.RGBMatrix(
                width=width,
                height=height,
                bit_depth=bit_depth,
                rgb_pins=rgb_pins,
                addr_pins=addr_pins,
                clock_pin=clock_pin,
                latch_pin=latch_pin,
                output_enable_pin=oe_pin,
                tile=tile_down, serpentine=serpentine,
            )
display = framebufferio.FramebufferDisplay(matrix)

#init button
btn = DigitalInOut(board.BUTTON_UP )
btn.direction = Direction.INPUT
btn.pull = Pull.UP
#setup graphics
#matrix = Matrix()
#display = matrix.display
font_down = bitmap_font.load_font("/fonts/RobotoMono-Regular-5pt.bdf")
font = bitmap_font.load_font("/fonts/RobotoMono-Regular-7pt.bdf")
color = 0x0000BF
# Creat a group to hold all screen elements
group = displayio.Group()

# init temp
sensor = adafruit_ahtx0.AHTx0(board.I2C())

# init air quality sensor
i2c = board.STEMMA_I2C()
reset_pin = None
pm25 = PM25_I2C(i2c, reset_pin)
aqdata = pm25.read()


# initilize network object
network = Network(status_neopixel=board.NEOPIXEL, debug=True)

# a dict of three locations and their ISO time zone to be displayed
locations = {
    "SNG": "Asia/Singapore",
    "DEL": "Asia/Kolkata",
    "JER": "Asia/Jerusalem",
    "UTC": "UTC",
    "NYC": "America/New_York",
    "SJC": "America/Los_Angeles",
    }
# labels to hold the clock text
labels = {
    "SNG": label.Label(font, text="SNG 12:55", color=color),
    "DEL": label.Label(font, text="JER 12:55", color=color),
    "JER": label.Label(font, text="DEL 12:55", color=color),
    "UTC": label.Label(font, text="UTC 12:55", color=color),
    "NYC": label.Label(font, text="NYC 12:55", color=color),
    "SJC": label.Label(font, text="SJC 12:55", color=color),
 }

#set the position on the screen
labels['SNG'].x = 0
labels['SNG'].y = 3
labels['DEL'].x = 0
labels['DEL'].y = 3+9
labels['JER'].x = 0 
labels['JER'].y = 3+9+9
labels['UTC'].x = 0
labels['UTC'].y = 3+9+9+9
labels['NYC'].x = 0
labels['NYC'].y = 3+9+9+9+9
labels['SJC'].x = 0
labels['SJC'].y = 3+9+9+9+9+9

#create the enviormental label
AQILabel = label.Label(font=font_down, text=" "*20, color=0xdddddd)
AQILabel.x=0
AQILabel.y=27+32

#setup satus block
status = displayio.Bitmap(2,2,3)
status_palette = displayio.Palette(4)
status_palette[0] = 0x00ff00
status_palette[1] = 0xff0000
status_palette[2] = 0xfffb00
status_palette[3] = 0x000000
status_tile = displayio.TileGrid(status, pixel_shader=status_palette)
status_color = 0 # set the default color
def set_status(status, color, seconds):
    """ function to set the status label,
    colors base on status_pallete:
    0-Green
    1-Red
    2-Yellow
    the seconds will determin how many LED to display
    """
    status[0,0] = color
    if seconds > 14:
        status[1,0] = color
    else:
        status[1,0] = 3 # black
    if seconds > 29:
        status[0,1] = color
    else:
        status[0,1] = 3 # black
    if seconds > 44:
        status[1,1] = color
    else:
        status[1,1] = 3 #black
# set initial status 
set_status(status,0,48)
status_g = displayio.Group()
status_tile.x=54
status_tile.y=1
status_tile.hidden = False

# create the graphics layout and apply it to the display
group.append(labels["SNG"])
group.append(labels["DEL"])
group.append(labels["JER"])
group.append(labels["UTC"])
group.append(labels["NYC"])
group.append(labels["SJC"])
group.append(status_tile)
group.append(AQILabel)
display.root_group = group


def get_color(hour_in):
    """ Return a color based on hour of the day to show different colors:
    Green - working hours
    Blue - non working hours
    Red/Pink - sleeping hours (11pm to 6am)
    """
    hour = int(hour_in)
    if hour in range(6,8):
        return 0x3a2edf #blue
    elif hour in range(8,18):
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
        # extract the time, converting 0 to O so the diisplay won't show somethign too similar to 8
        hours,minutes,seconds=now[location].isoformat().split('T')[1].split('.')[0].replace("0","O").split(':')
        # get the color based on daytime. the functions can't cope with O so translate back to 0
        color = get_color(hours.replace("O","0"))

        # blink the status
        status_tile.hidden = not status_tile.hidden
        if not status_tile.hidden:
            set_status(status, status_color, int(seconds.replace("O","0")))
        # change hours leading 0/O to blank
        if hours[0] == "O":
            hours = f" {hours[1]}"
        # change label only if there is something to change
        if labels[location].text!=f"{location} {hours}:{minutes}":
            labels[location].text=f"{location} {hours}:{minutes}"
        if labels[location].color != color:
            labels[location].color = color


def updatesensor(seconds): 
    """
    Update sensor data
    """
    try:
        aqdata = pm25.read()
        pm2 = int(aqdata["pm25 standard"])
    except RuntimeError:
        print("Unable to read from PM2.5 sensor, no new data..")
        status_color = 1
        set_status(status,status_color,seconds)
        pm2=0
    # update the display
    AQILabel.text = f"AQI:{pm2} T:{(sensor.temperature*9/5)+32:.0f} H:{sensor.relative_humidity:.0f}"
    if DEBUG: print(f"AQI: {pm2} temp: {sensor.temperature} Humidity {sensor.relative_humidity}")

def get_time(seconds):
    """ get local time information from from the net and return list of (location, time)"""
    set_status(status,2,seconds)
    times = {}
    for location, tz in locations.items():
        # use REST API to get the time at the time zone
        res = network.fetch("http://worldtimeapi.org/api/timezone/"+tz)
        if res:
            # get the returned timestamp ISO format and add a second
            times[location] = datetime.fromisoformat(res.json()['datetime'])
        else:
            print("Error", res.status_code, res.text)
    status_color = 0
    set_status(status,status_color,seconds)
    return times

# initial sensor update
updatesensor(45)
# `now` holds the local time for all locations
now = get_time(45)
# display the updated times
updateScreen(now, labels)

# second_counter coutns the numebr of seconds so every TIME_FETCH_INTERVAL*60 will trigget network update to time
second_counter = 0
env_count = 0 # same as the above , but ust for temp metrics

# loop
# last will hold the last read for time to manage how often we refresh the seconds
last = time.monotonic() # start the clock referebce
while True:
    # hide unhide display based on the up button
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
            
            # this section handles when to fetch the time from the internet
            second_counter += 1  # advance the overall seconds counter
            if second_counter >= TIME_FETCH_INTERVAL * 60:
                now = get_time(seconds) # refresh the time from the time server
                second_counter = 0 # reset the seconds counter so we can coutn again to TIME_FETCH_INTERVAL * 60
            
            # this section updates the env measurments
            env_count += 1
            if env_count >= ENV_REFRESH_INTERVAL * 60:
                updatesensor(seconds)
                env_count = 0

        # no need to busy loop, enough to check the time every 200 millis 
        time.sleep(0.2)
    except RuntimeError as e:
        print("Error", e)
        status_color = 1
        set_status(status,status_color,seconds)
        continue
    except adafruit_requests.OutOfRetries as e:
        # if netowrk isn't avail just try the next hour
        print("Error retrieveing data", e)
        status_color = 1
        set_status(status,status_color,seconds)
        continue
