import mcp23017, pca9685

from dccexonsbc.station import Station
from dccexonsbc.hardware.i2c import ExtenderSensorArray, ServoDriver
from dccexonsbc.accessories.withservos import (ServoTurnout,
                                               ThreeStateServoSemaphore)
from dccexonsbc.baseclasses import Sensor
from dccexonsbc import agents
from dccexonsbc.utils import SBC, GPIO

def hardware_setup(station:Station, remote=None):
    sbc = SBC("sawmillpi" if remote else None)
    gpio = GPIO(sbc)

    # Set up the MCP23017 “GPIO Expander”
    expander = mcp23017.Expander(sbc, 0, 0x20)
    expander.bank_a.iodir_is_input = True
    expander.bank_a.internal_pull_up_is_active = True
    expander.bank_a.input_polarity_is_reversed = True
    expander.bank_a.interrupt_on_change = True
    expander.bank_a.interrupt_polarity = False

    # Sensors 401…408
    sensors = ExtenderSensorArray(expander.bank_a,
                                  [ a+401 for a in range(8) ])
    station.register_sensors(sensors)
    
    gpio.register_pin_callback_threadsafe(
        24, station.loop, sensors.on_change,
        sbc.FALLING_EDGE, sbc.SET_PULL_UP)
    
    # Sensor 409 sits on the (inverted) GPIO pin #25 of the Raspberry Pi.
    sensor9 = Sensor(409)
    def on_sensor9_interrupt(chip, gpio, level, timestamp):
        sensor9.on_change(bool(level))
        
    gpio.register_pin_callback_threadsafe(
        23, station.loop, on_sensor9_interrupt,
        sbc.BOTH_EDGES, sbc.SET_PULL_UP | sbc.SET_ACTIVE_LOW,
        bouncetime_msec=1)
    station.register_sensor(sensor9)


    # Turnouts
    
    # Servos
    controller = pca9685.Controller(sbc, 0, 0x40)
    driver = ServoDriver(controller)
    
    sawmill_turnout = ServoTurnout(driver.get_servo(13), (70, 110))
    station.register_turnout_agent(agents.Turnout(401, sawmill_turnout))

    station_turnout = ServoTurnout(driver.get_servo(12), (85, 110))
    station.register_turnout_agent(agents.Turnout(402, station_turnout))
    
        
                                          

    

