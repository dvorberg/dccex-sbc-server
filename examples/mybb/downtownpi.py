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
    sbc = SBC("downtownpi" if remote else None)
    gpio = GPIO(sbc)

    # Set up the MCP23017 “GPIO Expander”
    expander = mcp23017.Expander(sbc, 1, 0x23)
    expander.bank_a.iodir_is_input = True
    expander.bank_a.internal_pull_up_is_active = False
    expander.bank_a.input_polarity_is_reversed = False
    expander.bank_a.interrupt_on_change = True
    expander.bank_a.interrupt_polarity = True

    # Sensors 301…30
    sensors = ExtenderSensorArray(expander.bank_a,
                                  [ a+301 for a in range(5) ])
    station.register_sensors(sensors)
    
    gpio.register_pin_callback_threadsafe(
        21, station.loop, sensors.on_change,
        sbc.FALLING_EDGE, sbc.SET_PULL_UP)
    
    # Turnouts
    
    # Servos
    controller = pca9685.Controller(sbc, 1, 0x43)

    # At this time, by downtown module has no capacitators attached
    # to the servos, which creates random behavious. Better set them
    # one by one.
    driver = ServoDriver(controller, max_active_channels=1)
    
    a = ServoTurnout(driver.get_servo(9), (150, 60))
    station.register_turnout_agent(agents.Turnout(301, a))
    time.sleep(.3)
    
    b = ServoTurnout(driver.get_servo(10), (125, 80))
    station.register_turnout_agent(agents.Turnout(302, b))
    time.sleep(.3)
    
    #cross = Cross(a, b)
    #cross_wrapper = agents.Cross(301, 302, cross)
    
    #station.register_turnout_agent(cross_wrapper.a_agent)
    #station.register_turnout_agent(cross_wrapper.b_agent)
    
    lower_turnout = ServoTurnout(driver.get_servo(11), (90, 120))
    time.sleep(.3)
    station.register_turnout_agent(agents.Turnout(303, lower_turnout))
    
    # Semaphores

    # Ausfahrtsignale
    station.register_accessory_agent(agents.Accessory(
        311, ServoSemaphore(driver.get_servo(2), (145, 132,))))
    time.sleep(.3)
    station.register_accessory_agent(agents.Accessory(
        312, ServoSemaphore(driver.get_servo(1), (153, 132,))))
    time.sleep(.3)
    station.register_accessory_agent(agents.Accessory(
        313, ServoSemaphore(driver.get_servo(0), (136, 152,))))
    time.sleep(.3)

    # Einfahrtsignale (dreiflüglich)
    station.register_accessory_agent(agents.Accessory(
        314, ThreeStateServoSemaphore(driver.get_servo(15), (92, 58, ),
                                      driver.get_servo(14), (110, 80,))))
    station.register_accessory_agent(agents.Accessory(
        315, ThreeStateServoSemaphore(driver.get_servo(12), (90, 120,),
                                      driver.get_servo(13), (88, 110,))))
    
    

    
    
                                          

    

