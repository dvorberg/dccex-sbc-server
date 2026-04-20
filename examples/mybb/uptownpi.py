import time

import mcp23017, pca9685

from dccexonsbc.station import Station
from dccexonsbc.hardware.i2c import ExtenderSensorArray, ServoDriver
from dccexonsbc.accessories.withservos import (
    ServoTurnout, ServoSemaphore, ThreeStateServoSemaphore)
from dccexonsbc.accessories.compound import Cross
from dccexonsbc.baseclasses import Sensor
from dccexonsbc import agents
from dccexonsbc.utils import SBC, GPIO

def hardware_setup(station:Station, remote=None):
    sbc = SBC("uptownpi" if remote else None)
    gpio = GPIO(sbc)

    # Set up the MCP23017 “GPIO Expander”
    expander = mcp23017.Expander(sbc, 1, 0x21)
    expander.bank_a.iodir_is_input = True
    expander.bank_a.internal_pull_up_is_active = True
    expander.bank_a.input_polarity_is_reversed = True
    expander.bank_a.interrupt_on_change = True
    expander.bank_a.interrupt_polarity = False

    # Sensors 201…207
    sensors = ExtenderSensorArray(expander.bank_a,
                                  [ a+201 for a in range(7) ])
    station.register_sensors(sensors)
    
    gpio.register_pin_callback_threadsafe(
        23, station.loop, sensors.on_change,
        sbc.FALLING_EDGE, sbc.SET_PULL_UP)


    expander.bank_b.iodir_is_input = True
    expander.bank_b.internal_pull_up_is_active = True
    expander.bank_b.input_polarity_is_reversed = True
    expander.bank_b.interrupt_on_change = True
    expander.bank_b.interrupt_polarity = False

    # Sensors 201…207
    sensors = ExtenderSensorArray(expander.bank_b,
                                  [ a+601 for a in range(4) ])
    station.register_sensors(sensors)
    
    gpio.register_pin_callback_threadsafe(
        24, station.loop, sensors.on_change,
        sbc.FALLING_EDGE, sbc.SET_PULL_UP)
    
    
    # Turnouts
    
    # Servos
    controller = pca9685.Controller(sbc, 1, 0x40)

    # At this time, by downtown module has no capacitators attached
    # to the servos, which creates random behavious. Better set them
    # one by one.
    driver = ServoDriver(controller, max_active_channels=1)

    station.register_turnout_agent(
        agents.Turnout(201, ServoTurnout(driver.get_servo(3), (85, 70))))
    time.sleep(.5)

    station.register_turnout_agent(
        agents.Turnout(202, ServoTurnout(driver.get_servo(4), (100, 130))))
    time.sleep(.5)
    
    station.register_turnout_agent(
        agents.Turnout(203, ServoTurnout(driver.get_servo(5), (115, 92))))
    time.sleep(.5)
    
    
    a = ServoTurnout(driver.get_servo(6), (55, 88))
    time.sleep(.5)
    b = ServoTurnout(driver.get_servo(7), (100, 70))
    time.sleep(.5)
    cross = Cross(a, b)
    cross_wrapper = agents.Cross(204, 205, cross)
    
    station.register_turnout_agent(cross_wrapper.a_agent)
    station.register_turnout_agent(cross_wrapper.b_agent)
    
    # Semaphores

    # Ausfahrtsignale
    station.register_accessory_agent(agents.Accessory(
        211, ServoSemaphore(driver.get_servo(0), (77, 97,))))
    time.sleep(.5)
    station.register_accessory_agent(agents.Accessory(
        212, ServoSemaphore(driver.get_servo(1), (83, 100,))))
    time.sleep(.5)
    station.register_accessory_agent(agents.Accessory(
        213, ServoSemaphore(driver.get_servo(2), (75, 100,))))


    
    

    
    
                                          

    

