import atexit, functools

import mcp23017, pca9685

from dccexonsbc.station import Station
from dccexonsbc.hardware.i2c import ExtenderSensorArray, ServoDriver
from dccexonsbc.accessories.withservos import (ServoTurnout,
                                               ThreeStateServoSemaphore)
from dccexonsbc.accessories.compound import Threeway
from dccexonsbc import agents
from dccexonsbc.utils import SBC, GPIO

def hardware_setup(station:Station, remote=None):
    loop = station.loop

    sbc = SBC(remote)
    gpio = GPIO(sbc)

    # Set up the MCP23017 “GPIO Expander”
    expander = mcp23017.Expander(sbc, 1, 0x20)
    expander.bank_a.iodir_is_input = True
    expander.bank_a.internal_pull_up_is_active = False
    expander.bank_a.input_polarity_is_reversed = False
    expander.bank_a.interrupt_on_change = True
    expander.bank_a.interrupt_polarity = False

    # Wrap the expander’s bank A in a SensorArray object. 
    sensors = ExtenderSensorArray(expander.bank_a,
                                  [ 101, 102, 103, 104, 105 ])    

    gpio.register_pin_callback_threadsafe(
        23, loop, sensors.on_change, sbc.FALLING_EDGE, sbc.SET_PULL_UP)

    station.register_sensors(sensors)
    
    # Servos
    controller = pca9685.Controller(sbc, 1, 0x40)
    driver = ServoDriver(controller)
    
    # Single Turnout
    simple_turnout = ServoTurnout(driver.get_servo(15), (65, 90))
    station.register_turnout_agent(agents.Turnout(1, simple_turnout))

    # The Threeway    
    left = ServoTurnout(driver.get_servo(13), (50, 70))
    right = ServoTurnout(driver.get_servo(14), (65, 105))
    threeway = Threeway(left, right)
    agent = agents.Threeway(2, 3, threeway)
    station.register_turnout_agent(agent.left_agent)
    station.register_turnout_agent(agent.right_agent)


    # Semaphore
    # 10 75 90  oberer Flügel
    # 11 80 100 untere Flügel
    signal = ThreeStateServoSemaphore(driver.get_servo(10), (75,  90,),
                                      driver.get_servo(11), (80, 100))
    
    accessory_agent = agents.Accessory(1, signal)
    station.register_accessory_agent(accessory_agent)
