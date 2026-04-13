import atexit, functools
import lgpio as sbc

from mcp23017 import Expander, Bank as ExpanderBank

from dccexonsbc.station import Station
from dccexonsbc.hardware.i2c import ExtenderSensorArray

def hardware_setup(station:Station):
    loop = station.loop
    sbc.exceptions = True

    # Set up the MCP23017 “GPIO Expander”
    expander = Expander(sbc, 1, 0x20)
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
    
    
