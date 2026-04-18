"""
This module contains classes that implement hardware connections
that use the i2c bus.
"""
import sys, threading, asyncio
import icecream; icecream.install()

import mcp23017, pca9685

from i2cutils.bitpattern import Byte

from ..baseclasses import Responder, Sensor, Servo
from .servos import SG90

class ExtenderSensorArray(object):
    """
    Holds up to eight Sensor objects, one for each pin of a
    mcp23017 GPIO Extender’s bank.

    The `on_change()` method must be called when the Expander’s
    input state changes, preferably by configuring the Expander’s
    interrupt mechanism and connecting its interrupt pin to the Pi’s
    GPIO. The on_change() method is *not* thread safe. You must wrap it
    in an `interruptsafe.InterruptHandler` instance for this to work.
    """
    def __init__(self, bank:mcp23017.Bank,
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

        self.on_change()
        
    @property
    def sensors(self) -> list:
        return [sensor for sensor in self._sensors if sensor is not None]

    def __iter__(self):
        return iter(self.sensors)
    
    def on_change(self, *args):
        old = self.state
        new = self.bank.read()
        
        for pin, sensor in enumerate(self._sensors):
            if sensor is not None and (old is None or new[pin] != old[pin]):
                sensor.on_change(new[pin])
                
        self.state = new

        
class ServoChannel(object):
    def __init__(self, output:pca9685.Output, update_rate:float):
        self.output = output
        self.update_rate = update_rate

        # Initialize the channel. 
        self.output.pwm_on = 0
        self.output.pwm_off = 0

    def set_pulse(self, pulse:float|None):
        if pulse is None:
            self.output.pwm_off = 0
        else:
            self.output.pwm_off = int(pulse * self.update_rate * 4096)
            
            
class ServoDriver(object):
    def __init__(self, controller:pca9685.Controller,
                 update_rate_mhz:float=50,
                 default_servo_class:type[Servo]=SG90,
                 default_stop_timeout:float=0.2):
        self.controller = controller
        
        controller.set_update_rate(update_rate_mhz)
        self.update_rate = update_rate_mhz
        
        self._servos = {}
        """
        Mape integer channel numbers to Servo objects.
        """

        self.default_servo_class = default_servo_class
        self.default_stop_timeout = default_stop_timeout
        
    def get_servo(self, channel_no:int,
                  servo_class:type[Servo]=None,
                  stop_timeout:float=None) -> Servo:
        if not channel_no in self._servos:
            if servo_class is None:
                servo_class = self.default_servo_class

            if stop_timeout is None:
                stop_timeout = self.default_stop_timeout
                
            self._servos[channel_no] = servo_class(
                ServoChannel(self.controller[channel_no],
                             self.update_rate).set_pulse,
                stop_timeout)
            
        return self._servos[channel_no]

    def __get_item__(self, idx:int):
        return self.make_servo(idx)

