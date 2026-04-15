import atexit, functools
import lgpio as sbc

import mcp23017, pca9685

from dccexonsbc.station import Station
from dccexonsbc.hardware.i2c import ExtenderSensorArray, ServoDriver
from dccexonsbc.accessories.withservos import (ServoTurnout,
                                               ThreeStateServoSemaphore)
from dccexonsbc.accessories.compound import Threeway
from dccexonsbc import agents

def hardware_setup(station:Station):
    loop = station.loop
    sbc.exceptions = True

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
    
    handle = sbc.gpiochip_open(0)

    #on_interrupt = InterruptHandler(loop, sensors.on_change)
    def on_interrupt(*args, **kw):
        loop.call_soon_threadsafe(sensors.on_change)

    # This needs to be debounced.
    interrupt_pin = 23
    result = sbc.gpio_claim_alert(handle,
                                  interrupt_pin,
                                  sbc.FALLING_EDGE,
                                  sbc.SET_PULL_UP)
    callback = sbc.callback(handle, interrupt_pin,
                            sbc.FALLING_EDGE,
                            on_interrupt)

    station.register_sensors(sensors)

    def cleanup_gpio():
        callback.cancel()
        sbc.gpio_free(handle, interrupt_pin)
        sbc.gpiochip_close(handle)
    atexit.register(cleanup_gpio)

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
    
    signal_agent = agents.Accessory(1, signal)
    station.register_accessory_agent(signal_agent)
    
    signal_agent = agents.Signal(1, signal)
    station.register_agent(signal_agent)
