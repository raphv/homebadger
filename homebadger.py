import uasyncio
import json
import badger2040w
import gc
from pimoroni_i2c import PimoroniI2C
from breakout_bme68x import BreakoutBME68X

import HOMEBADGER_CONFIG

ALL_SENSORS = HOMEBADGER_CONFIG.LOCAL_SENSORS + HOMEBADGER_CONFIG.HA_SENSORS
SENSOR_COUNT = len(ALL_SENSORS)

HTML_START = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Home Badger</title></head><body><h1>Home Badger</h1><h2>Status:</h2><table border="1">'
HTML_END = '</table><p>Machine-readable version at <a href="/json">/json</a></p></body></html>'

per_page = 3
current_pos = 0
changed = False
autoscroll = False
STARTED_AT = badger2040w.time.time()

statistics = {
    'requests_sent_to_ha': 0,
    'errors_in_requests_sent_to_ha': 0,
    'requests_received': 0,
    'errors_in_requests_received': 0,
    'screen_refreshes': 0,
    'uptime_seconds': 0,
    'local_sensor_count': len(HOMEBADGER_CONFIG.LOCAL_SENSORS),
    'ha_sensor_count': len(HOMEBADGER_CONFIG.HA_SENSORS),
    'total_sensor_count': SENSOR_COUNT,
}

def identity(x):
    return x

def make_response(content_type, content, status='200 OK'):
    return '\r\n'.join([
        'HTTP/1.0 %s'%status,
        'Connection: close',
        'Content-Type: %s'%content_type,
        '', '',
        content
    ]).encode()

def build_html_result():
    return '\n'.join([
        HTML_START,
        '<tr><th colspan="3">Sensor values</th></tr>',
        '<tr><th>Display name</th><th>Display value</th><th>Precise value</th></tr>',
    ] + [
        '<tr><th>%s</th><td>%s</td><td>%s</td></tr>'%(
            s['title'].replace('\n',' '),
            s.get('display_func',identity)(s['state']),
            s['state']
        ) for s in HOMEBADGER_CONFIG.LOCAL_SENSORS
    ] + [ '<tr><th colspan="3">Homebadger statistics</th></tr>' ] + [
        '<tr><th>%s</th><td colspan="2">%d</td>'%(k.replace('_',' '),v)
        for k,v in statistics.items()
    ] + [ HTML_END ])

async def server_callback(reader, writer):
    try:
        request = await reader.read(1024)
        request = request.decode()
        if request[:3] == 'GET':
            method, path, protocol = request.split('\r\n')[0].split(' ')
            print('Received request for %s'%path)
            statistics['requests_received'] += 1
            #response = None
            if path == '/':
                response = make_response(
                    'text/html',
                    build_html_result()
                )
            elif path == '/json':
                response = make_response(
                    'application/json',
                    json.dumps({
                        'sensors': dict(
                            (s['json_key'], s['state']) for s in HOMEBADGER_CONFIG.LOCAL_SENSORS
                        ),
                        'homebadger_statistics': statistics
                    })
                )
            else:
                response = make_response(
                    'text/plain',
                    'Not found.',
                    '404 Not Found'
                )
            writer.write(response)
            await writer.drain()
    except Exception as e:
        statistics['errors_in_requests_received'] += 1
        print("Error",e)
    finally:
        writer.close()
        reader.close()
        await writer.wait_closed()
        await reader.wait_closed()
        
async def get_ha_sensor_state(sensor_data):
    try:
        statistics['requests_sent_to_ha'] += 1
        reader, writer = await uasyncio.open_connection(
            HOMEBADGER_CONFIG.HA_HOSTNAME,
            HOMEBADGER_CONFIG.HA_PORT
        )
        url = '/api/states/%s'%(sensor_data['id'])
        headlines = [
            'GET %s HTTP/1.0'%url,
            'Authorization: Bearer %s'%HOMEBADGER_CONFIG.HA_TOKEN,
            '', ''
        ]
        writer.write("\r\n".join(headlines).encode())
        await writer.drain()
        resp = await reader.read()
        json_data = resp.decode().split('\r\n')[-1]
        state = json.loads(json_data)['state']
        sensor_data['state'] = state
        print('Updated ', sensor_data['id'], state)
        sensor_data['updated'] = badger2040w.time.ticks_ms()
    except Exception as e:
        statistics['errors_in_requests_sent_to_ha'] += 1
        print("Error", e)
    finally:
        reader.close()
        writer.close()
        await reader.wait_closed()
        await writer.wait_closed()

async def display_loop():
    current_display = ''
    while True:
        indices_displayed = [x % SENSOR_COUNT for x in range(current_pos, current_pos + per_page)]
        sensors_displayed = [ALL_SENSORS[i] for i in indices_displayed]
        displayed_states = [
            sensor.get('display_func', identity)(sensor['state'])
            if 'state' in sensor
            else '??'
            for sensor in sensors_displayed
        ]
        if autoscroll: # only update at each scroll point
            to_be_displayed = '%d %d'%(per_page, current_pos)
        else: # update when anything visible has changed
            to_be_displayed = '%d %d %s'%(per_page, current_pos,' '.join(displayed_states))
        if to_be_displayed != current_display:
            current_display = to_be_displayed
            statistics['screen_refreshes'] += 1
            #Clearing the whole screen
            display.set_pen(15)
            display.clear()
            #Drawing Play/Pause button
            display.set_pen(15*(not autoscroll))
            display.rectangle(28,116,12,12)
            display.set_pen(15*autoscroll)
            display.triangle(30,118,30,126,38,122)
            display.rectangle(40,116,12,12)
            display.set_pen(15*(not autoscroll))
            display.rectangle(42,118,3,8)
            display.rectangle(47,118,3,8)
            display.set_pen(0)
            display.set_font('bitmap8')
            display.text('%d/PAGE'%per_page,130,120,scale=1)
            #Drawing the scrolling indicators
            sensor_rect_height = min(16, 128//SENSOR_COUNT)
            yoffset = (128 - sensor_rect_height * SENSOR_COUNT)//2
            for i in range(SENSOR_COUNT):
                display.set_pen(0)
                display.rectangle(284, yoffset + i*sensor_rect_height+1, 12, sensor_rect_height-2)
                if i not in indices_displayed:
                    display.set_pen(15)
                    display.rectangle(285, yoffset + i*sensor_rect_height+2, 10, sensor_rect_height-4)
            #Displaying sensors
            if per_page == 1:
                display.set_pen(0)
                title = sensors_displayed[0]['title'].replace('\n',' ')
                display.set_font('bitmap8')
                display.text(title, 0, 0,scale=3)
                display.set_font('sans')
                font_scale = 3.5
                value = displayed_states[0]
                while True:
                    display_width = display.measure_text(value, font_scale)
                    if display_width > 274:
                        font_scale -= .1
                    else:
                        x = (284 - display_width)//2
                        display.text(value, x, 75, scale=font_scale)
                        #Faux Bold
                        display.text(value, x+1, 75, scale=font_scale)
                        display.text(value, x, 76, scale=font_scale)
                        break
            else:
                column_width = 284//per_page
                for position, sensor in enumerate(sensors_displayed):
                    left = column_width * position
                    display.set_pen(0)
                    title_lines = sensor['title'].split('\n')
                    display.set_font('bitmap8')
                    for i, l in enumerate(title_lines):
                        w = display.measure_text(l, 2)
                        x = left + (column_width - w)//2
                        display.text(l, x, 18*i,scale=2)
                    display.set_font('sans')
                    font_scale = 2
                    value = displayed_states[position]
                    while True:
                        display_width = display.measure_text(value, font_scale)
                        if display_width > (column_width - 10):
                            font_scale -= .1
                        else:
                            x = left + (column_width - display_width)//2
                            #Faux Bold
                            display.text(value, x, 85, scale=font_scale)
                            display.text(value, x-1, 85, scale=font_scale)
                            display.text(value, x, 86, scale=font_scale)
                            break
            display.update()
            await uasyncio.sleep_ms(500) #avoid updating too often
        else:
            await uasyncio.sleep_ms(100)

async def blink_led():
    while True:
        display.led(128)
        await uasyncio.sleep_ms(500)
        display.led(0)
        statistics['uptime_seconds'] = badger2040w.time.time()-STARTED_AT
#        print(gc.mem_free())
        await uasyncio.sleep_ms(500)

async def ha_sensor_update_loop():
    while True:
        for sensor in HOMEBADGER_CONFIG.HA_SENSORS:
            freshness = badger2040w.time.ticks_diff(
                badger2040w.time.ticks_ms(),
                sensor.get('updated',0)
            )
            if (freshness > 30_000):
                await get_ha_sensor_state(sensor)
        await uasyncio.sleep_ms(500)

async def local_sensor_loop():
    while True:
        values = bme.read()
        for n in range(4):
            HOMEBADGER_CONFIG.LOCAL_SENSORS[n]['state'] = values[n]
        await uasyncio.sleep_ms(10_000)

async def button_loop():
    global current_pos, autoscroll, per_page
    while True:
        button_pressed = False
        if display.pressed(badger2040w.BUTTON_DOWN):
            button_pressed = True
            current_pos = (current_pos + 1)%SENSOR_COUNT
        if display.pressed(badger2040w.BUTTON_UP):
            button_pressed = True
            current_pos = (current_pos - 1)%SENSOR_COUNT
        if display.pressed(badger2040w.BUTTON_A):
            button_pressed = True
            autoscroll = not autoscroll
        if display.pressed(badger2040w.BUTTON_B):
            button_pressed = True
            per_page = 1 + (per_page % 3) 
        await uasyncio.sleep_ms(
            100 if button_pressed else 10
            )

async def autoscroll_loop():
    global current_pos
    while True:
        if autoscroll:
            current_pos = (current_pos + 1)%SENSOR_COUNT
            await uasyncio.sleep_ms(5_000)
        else:
            await uasyncio.sleep_ms(200)

async def main():
    await uasyncio.start_server(
        server_callback,
        '0.0.0.0',
        HOMEBADGER_CONFIG.SERVER_PORT
    )
    uasyncio.create_task(ha_sensor_update_loop())
    uasyncio.create_task(local_sensor_loop())
    uasyncio.create_task(display_loop())
    uasyncio.create_task(button_loop())
    uasyncio.create_task(autoscroll_loop())
    await uasyncio.create_task(blink_led())

display = badger2040w.Badger2040W()
display.set_update_speed(badger2040w.UPDATE_FAST)

i2c = PimoroniI2C(sda=4, scl=5)
bme = BreakoutBME68X(i2c, address=0x76)

display.connect()
display.set_pen(0)
display.clear()
display.set_pen(15)
display.set_font('bitmap6')
display.text('Loading',20,20,scale=4)
display.text('Sensor',20,50,scale=4)
display.text('Data...',20,80,scale=4)
display.update()

uasyncio.run(main())
    

