from machine import Pin, PWM, Timer, ADC, I2C, RTC, SPI, SoftSPI
import time
import ssd1306
from micropython import const
import math
import urequests as requests
import json
import ustruct
import re
import network
import usocket as socket
import uselect as select

# Functiuon for getting json data from API
def http_get(url):
    import socket
    _, _, host, path = url.split('/', 3)
    addr = socket.getaddrinfo(host, 80)[0][-1]
    s = socket.socket()
    s.connect(addr)
    s.send(bytes('GET /%s HTTP/1.0\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))
    data_str = ''
    while True:
        data = s.recv(100)
        if data:
            data_str = data_str + (str(data, 'utf8'))
        else:
            break
    s.close()
    return data_str

# Connecting to the network
def do_connect():
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network...')
        wlan.connect('Columbia University', '12345678')
        while not wlan.isconnected():
            pass
    
    print('Connected to WIFI\nIP Adress: ' +  str(wlan.ifconfig()[0]))
do_connect()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('', 80))
server.listen(5)

# get location information from ip-api
location_str = http_get('http://ip-api.com/json')
lat_pattern = re.compile(r'lat":-?[0-9\.]+')
lat_matches = lat_pattern.search(location_str)
lon_pattern = re.compile(r'lon":-?[0-9\.]+')
lon_matches = lon_pattern.search(location_str)
longtitude = lon_matches.group(0)[5:]
latitude = lat_matches.group(0)[5:]
#print(lat_matches.group(0)[5:])
#print(lon_matches.group(0)[5:])
# Get weather information from Open Weather
weather_str = http_get('https://api.openweathermap.org/data/2.5/weather?lat='+latitude+'&lon='+longtitude+'&appid=72bcd8b2ab328d03bf4fe17e9c4cdb1f')
description_pattern = re.compile(r'"description":"[A-Za-z ]+"')
description_matches = description_pattern.search(weather_str)
temp_pattern = re.compile(r'"temp":[0-9]+')
temp_matches = temp_pattern.search(weather_str)
# API key for weather 72bcd8b2ab328d03bf4fe17e9c4cdb1f
description = description_matches.group(0)[14:]
temprature = temp_matches.group(0)[7:]
temprature_int = int(temprature)
temprature_int = (temprature_int - 273.15) * 9 / 5 + 32

# Send a twitter when powered on 
url = "https://maker.ifttt.com/trigger/Tweet/json/with/key/jWYCGVNiq_l2jDPCXmGsi4V_rPrnMT0lpRQJImBctp-"
#url = "https://maker.ifttt.com/trigger/tweet/json/with/key/egvOxsZyL1SEcHQHeEBWgQEZTbf-zfn1UHEz47nw3kg"
json = {"The weather now is: ":description}
r = requests.post(url,json=json)
r.close()

############################################################################################################

# function converting from 2's complement bianry to decimal
def twosCom_binDec(bin, digit): 
    while len(bin)<digit :
            bin = '0'+bin
    if bin[0] == '0':
        return int(bin, 2)
    else:
        return -1 * (int(''.join('1' if x == '0' else '0' for x in bin), 2) + 1)

# convert raw data to decimal
def convert_data(reg):
    #data = spi.read(2, reg)
    
    data = bytearray(3)     # create a buffer
    spi.readinto(data, reg)
    data = data[0:2]
    
    data = int.from_bytes(data, "little", False)
    data_binary = str(bin(data))
    data_trim = data_binary.replace('0b', '')
    value = int(twosCom_binDec(data_trim, 16) / 256)
    return value

# Buttong A for seleting field: 1->Hour 2->Minutes 3->Second
chosen_field = 1
def buttonA_callback(pin):
    if check_valid(time.ticks_ms()):
        global chosen_field
        if chosen_field == 3:
            chosen_field = 0
        chosen_field += 1
        print('Field '+str(chosen_field)+' is chosen')

# Button B for adding 1 to the selected field
def buttonB_callback(pin):
    print('button b pressed')
    if check_valid(time.ticks_ms()):
        global chosen_field
        now = rtc.datetime()
        if chosen_field == 1:
            rtc.datetime((now[0], now[1], now[2], now[3], now[4]+1, now[5], now[6], now[7]))
            print('Hour + 1')
        elif chosen_field == 2:
            rtc.datetime((now[0], now[1], now[2], now[3], now[4], now[5]+1, now[6], now[7]))
            print('Minute + 1')
        elif chosen_field == 3:
            rtc.datetime((now[0], now[1], now[2], now[3], now[4], now[5], now[6]+1, now[7]))
            print('Second + 1')
            
# Button C for entering and exiting alarm setting mode
alarm_setting_mode = False
alarm_time = ()
real_time = ()
def buttonC_callback(pin):
    if check_valid(time.ticks_ms()):
        global alarm_setting_mode
        global real_time
        global alarm_time
        if(not alarm_setting_mode):
            real_time = rtc.datetime()
            alarm_setting_mode = True
            print('Alarm Setting Mode Entered')
        else:
            alarm_time = rtc.datetime()
            rtc.datetime((real_time[0], real_time[1], real_time[2], real_time[3], real_time[4], real_time[5], real_time[6], real_time[7]))
            alarm_setting_mode = False
            real_time = ()
            print('Alarm set to'+str(alarm_time[0:7]))
            print('Alarm Setting Mode Exited')
       
# Initializing OLED
LED_i2c = I2C(sda=Pin(4), scl=Pin(5), freq=400000)
display = ssd1306.SSD1306_I2C(128, 32, LED_i2c)
alarming = False
rtc = RTC()
buzzer = Pin(12, Pin.OUT)
# Initializing OLED buttons
Pin(0, Pin.IN).irq(trigger=Pin.IRQ_RISING, handler=buttonA_callback) #Button A
Pin(3, Pin.IN).irq(trigger=Pin.IRQ_RISING, handler=buttonB_callback) #Button B
Pin(2, Pin.IN).irq(trigger=Pin.IRQ_RISING, handler=buttonC_callback) #Button C

# Initializing adc for reading light sensor value
adc = ADC(0)
# Button deboucing
last_trigger_time = 0
def check_valid(last_trigger_time_param):
    global last_trigger_time
    if time.ticks_ms() > last_trigger_time + 300:
        last_trigger_time = time.ticks_ms()
        return True
    else:
        return False

# Initializing timer for alarming for exactly 3s
tim2 = Timer(1)
def stopalarm(timer):
    print('Alarm Stopped')
    global alarming
    alarming = False
    buzzer.value(0)

# Initialization of SPI
spi = SPI(1, baudrate = 1500000, polarity = 1, phase = 1)
cs = Pin(15, machine.Pin.OUT)
# turn on measure
cs.value(0)
spi.write(b'\x2d\x08') 
cs.value(1)
# data format
cs.value(0)
spi.write(b'\x31\x00') 
cs.value(1)
# data rate
cs.value(0)
spi.write(b'\x2c\x0c') 
cs.value(1)
# Calibrate: replace xfa with correct value
cs.value(0)
#spi.write(b'\x1f\x00') 
cs.value(1)

def update_realtime(timer):
    global real_time
    if len(real_time) == 8: # updating real_time while setting alarm
        real_time_list = list(real_time)
        real_time_list[6] += 1
        real_time = tuple(real_time_list)
        print('real time is now '+str(real_time))  
tim1 = Timer(0)
tim1.init(period=1000, mode=Timer.PERIODIC, callback=update_realtime)


command = ''
def Client_handler(conn): #Do this when there's a socket connection
    global command
    request = conn.recv(1024).decode("utf-8")
    print(request)
    command_pattern = re.compile(r'command":["a-z A-Z0-9\+]+')
    command_pattern_match = command_pattern.search(request)
    command = command_pattern_match.group(0)[10:-1]
    print(command_pattern_match.group(0)[10:-1])
    conn.close()


while True:
    r, w, err = select.select((server,), (), (), 1)
    if r:
        for readable in r:
            conn, addr = server.accept()
            try:
                Client_handler(conn)
            except OSError as e:
                pass
            
    cs.value(0)
    x = convert_data(0xf2)
    cs.value(1)
    cs.value(0)
    y = convert_data(0xf4)
    cs.value(1)
    cs.value(0)
    z = convert_data(0xf6)
    cs.value(1)
    #print('x: '+str(x) + ' y: '+str(y)+' z: ' + str(z))

    time_now = rtc.datetime()
    if time_now[0:7]==alarm_time[0:7]: #trigger alarm
        print('Alarm Started')
        alarming = True
        #buzzer.value(1)
        tim2.init(period=3000, mode=Timer.ONE_SHOT, callback=stopalarm)
    display.fill(0)
    if not alarming:
        if x > -10 and x < 10:
            x = 0
        if y > -10 and y < 10:
            y = 0
        if(command=="display time"):
            display.text(str(time_now[4])+ ":"+str(time_now[5])+ ":"+str(time_now[6]), int(x)+30, int(y))
        elif(command.find('display message')!=-1):
            display.text(command[16:], int(x)+30, int(y))
        else:
            display.text(str(time_now[0])+ "/"+str(time_now[1])+ "/"+str(time_now[2]),int(x)+30,int(y))
            display.text(str(time_now[4])+ ":"+str(time_now[5])+ ":"+str(time_now[6]), int(x)+30, int(y)+10)
            # longtitude and latitude
            display.text('lon:' + longtitude[:3],int(x),int(y)+20)
            display.text('lat:' + latitude[:3], int(x)+70, int(y)+20)
            # weather and temprature
            display.text(description,int(x),int(y)+30)
            display.text(str(temprature_int), int(x), int(y)+40)
            
        display.contrast((int)(255*(adc.read()/1024)))  # 0-255
        #print(command)
        if(command=="display off"):
            display.fill(0)
            display.show()
        else:
            display.show()

    else:
        display.fill(1)
        display.show()
