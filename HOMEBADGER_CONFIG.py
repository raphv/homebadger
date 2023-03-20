#Home Badger Home Assistant Configuration

HA_HOSTNAME = '192.168.0.0'
HA_PORT = 8123
HA_TOKEN = "" #Check the Home Assistant docs to generate a token: https://www.home-assistant.io/docs/authentication/
LOCAL_SENSORS = [
    {
        "title": "BME688\nTemp. (C)",
        "json_key": "bme688_temperature",
        "display_func": lambda t: "%.1f"%t,
    },
    {
        "title": "BME688\nPressure\n(hPa)",
        "json_key": "bme688_pressure",
        "display_func": lambda t: "%.f"%(t/100),
    },
    {
        "title": "BME688\nHumidity",
        "json_key": "bme688_humidity",
        "display_func": lambda t: "%.f%%"%t,
    },
    {
        "title": "BME688 Gas\nResistance\n(kOhm)",
        "json_key": "bme688_gas_resistance",
        "display_func": lambda t: "%.f"%(t/1000),
    },
]
HA_SENSORS = [
    {
        "title": "Outdoors\nTemp. (C)",
        "id": "sensor.temperature_outdoor",
        "display_func": lambda t: "%.1f"%float(t),
    },
    {
        "title": "Outdoors\nHumidity",
        "id": "sensor.humidity_indoor",
        "display_func": lambda t: "%.f%%"%float(t),
    },
    {
        "title": "Master\nBedroom\nTemp. (C)",
        "id": "sensor.temperature_indoor",
        "display_func": lambda t: "%.1f"%float(t),
    },
    {
        "title": "Indoors\nHumidity",
        "id": "sensor.humidity_indoor",
        "display_func": lambda t: "%.f%%"%float(t),
    },
    {
        "title": "Indoors\nCO2\n(ppm)",
        "id": "sensor.mh_z14a_carbon_dioxide",
        "display_func": lambda t: "%.f"%float(t),
    },
    {
        "title": "Indoors\nPM <10um\n(ug/m3)",
        "id": "sensor.sds011_particulate_matter_10",
    },
    {
        "title": "Indoors\nPM <2.5um\n(ug/m3)",
        "id": "sensor.sds011_particulate_matter_2_5",
    },
]
SERVER_PORT = 80
