"""
This module contains classes that implement hardware connections
that use the i2c bus.
"""
import sys, threading, asyncio

from mcp23017 import Bank as ExpanderBank
from i2cutils.bitpattern import Byte

from ..baseclasses import Responder, Sensor

class ExtenderSensorArray(Responder):
    """
    Holds up to eight Sensor objects, one for each pin of a
    mcp23017 GPIO Extender’s bank.

    The `on_change()` method must be called when the Expander’s
    input state changes, preferably by configuring the Expander’s
    interrupt mechanism and connecting its interrupt pin to the Pi’s
    GPIO. The on_change() method is *not* thread safe. You must wrap it
    in an `interruptsafe.InterruptHandler` instance for this to work.
    """
    def __init__(self, bank:ExpanderBank,
                 sensor_exids=[None, None, None, None,
                               None, None, None, None,]):
        """
        `sensor_exids` is a collection of eight values, either
        ints (the respective sensor’s exid) or None (pin is
        unconnected). 
        """
        self.bank = bank

        # Make sure the sensors list hast eight entries. 
        sensor_exids = list(sensor_exids)
        while len(sensor_exids) < 8:
            sensor_exids.append(None)
        sensor_exids = sensor_exids[:8]

        # Create the sensor objects. 
        self._sensors = tuple([Sensor(exid)
                               if exid is not None else None
                               for exid in sensor_exids])
        
        self.state:Byte|None = None
        """
        The last state read from the Expander’s bank or None on
        init.
        """
        
    @property
    def sensors(self) -> list:
        return [sensor for sensor in self._sensors if sensor is not None]
            
    def on_change(self):
        old = self.state
        new = self.bank.read()
        
        for pin, sensor in enumerate(self._sensors):
            if sensor is not None and (old is None or new[pin] != old[pin]):
                sensor.on_change(new[pin])
                
        self.state = new


