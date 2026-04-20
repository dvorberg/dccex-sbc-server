import mcp23017, pca9685

from dccexonsbc.station import Station
from dccexonsbc.hardware.i2c import ExtenderSensorArray
from dccexonsbc.baseclasses import Sensor
from dccexonsbc.utils import SBC, GPIO

def hardware_setup(station:Station, remote=None):
    sbc = SBC("badenpi" if remote else None)
    gpio = GPIO(sbc)

    # Set up the MCP23017 “GPIO Expander”
    expander = mcp23017.Expander(sbc, 1, 0x22)
    expander.bank_a.iodir_is_input = True
    expander.bank_a.internal_pull_up_is_active = False
    expander.bank_a.input_polarity_is_reversed = False
    expander.bank_a.interrupt_on_change = True
    expander.bank_a.interrupt_polarity = True

    # Sensors 101…108
    sensors = ExtenderSensorArray(expander.bank_a,
                                  [ a+101 for a in range(8) ])
    station.register_sensors(sensors)
    
    gpio.register_pin_callback_threadsafe(
        20, station.loop, sensors.on_change,
        sbc.FALLING_EDGE, sbc.SET_PULL_UP)
    
    # Sensor 109 sits on the (inverted) GPIO pin #16 of the Raspberry Pi.
    sensor9 = Sensor(109)
    def on_sensor9_interrupt(chip, gpio, level, timestamp):
        sensor9.on_change(bool(level))
        
    gpio.register_pin_callback_threadsafe(
        16, station.loop, on_sensor9_interrupt,
        sbc.BOTH_EDGES, sbc.SET_PULL_DOWN,
        bouncetime_msec=1)
    station.register_sensor(sensor9)

    
                                          

    

