"""
(Abstract) base classes.

These unify some aspects of the interface I want these classes to
have. Generally, these classes know how to publish themselves in a
DCC-EX context, i.e. know how to formulate responses describing their
current state.
"""

import threading
from typing import Any

from .abc import Responder, Publisher, Subscription

class Responder(Responder):
    """
    A hardware item that knows to represent its current state as
    DCC-EX response and needs access to the response publisher.
    """
    response_publisher:Publisher = None
    """
    The `response_publisher` is set by the server on adding a responder
    to the hardware list. 
    """
    
    def publish(self, response:bytes):
        self.response_publisher.publish(response)

class Hardware(object):
    states:tuple
    
    def set(self, state:Any):
        raise NotImplementedError()

    def reset(self):
        self.set(self.states[0])
    
    @property
    def state(self):
        raise NotImplementedError()

    @state.setter
    def state(self, state:Any):
        self.set(state)
    
class Turnout(Hardware):
    """
    A turnout or point. 
    """
    closed_state:int = 0
    """
    Default state, the turnout is set for the train to go straight.
    """
    
    thrown_state:int = 1
    """
    Thrown state, the train will turn left or right.
    """
    
    states = (closed_state, thrown_state,)

    @property
    def thrown(self) -> bool:
        """
        Represent whether the turnout is in thrown state.  There
        is no setter for `thrown`. Throwing and closing may take its
        time and we don’t want to block processing.
        """
        return (self.state == self.thrown_state)
    
    def throw(self):
        """
        Set the turnout in the thrown state.
        """
        self.set(self.thrown_state)

    def close(self):
        """
        Set the turnout in the default state.
        """
        self.set(self.reset_state)

    @property
    def state(self) -> int:
        """
        Return the turnout’s state as an integer. There is not
        setter for the state, because when setting it (moving aroung
        mechanical parts) a asyncio.sleep() timeout may be
        introduced. (Of course the operation of setting must be
        non-blocking!)
        """
        raise NotImplementedError()
        

class Signal(Hardware, Responder):
    """
    This is a base class for signals and semaphores. 
    """
    
    green = "green"
    open = "green"

    red = "red"
    stop = "red"
    
    states = (red, green,)
    """
    A regular signal has a red and a green state. 
    """

    @property
    def signaling_stop(self) -> bool:
        """
        Is the signal currently signaling “stop?"
        There is no setter. 
        """
        return (self.state == self.red)
        
    def greenlight(self):
        """
        Signal "go."
        """
        self.set(self.green)

    def reset(self):
        """
        Signal "stop."
        """
        self.set(self.red)


class ThreeStateSignal(Signal):
    """
    Some signals/semaphores have three states for stop, go, and
    "go slowly."
    """
    amber = "amber"
    slow = "amber"

    states = (Signal.red, Signal.green, amber,)

    def slowlight(self):
        """
        Signal amber
        """
        raise NotImplementedError()
    
    signaling_slow:bool = True

    
class Sensor(Hardware, Responder):
    """
    A sensor detecting if a vehicle is occupying a section of track. 
    """    
    def __init__(self, exid:int):
        """
        `exid`: Identify this accessory in DCC commands and responses.  
        """
        self.exid = exid
    
    active:bool|None = None
    """
    The current state of the sensor. On initialization this is
    None.
    """

    def on_change(self, active:bool) -> None:
        """
        Callback function informing the Sensor object of a
        state change. No check is being performed if the
        state is actually changed, a DCC-EX response will
        always be published. 
        """
        self.active = active
        self.publish(self.state_response)

    @property
    def state_response(self) -> bytes:
        """
        Represent the current state as a DCC-EX response. 
        """
        if self.active:
            letter = b"Q"
        else:
            letter = b"q"

        return b"<%s %i>" % ( letter, self.exid, )

    @property
    def setup_response(self) -> bytes:
        """
        Represent a sensor setup as a DCC-EX response.
        Since we’re not configured as a vpin on an
        Arduino, we say “0” here. 
        """
        return f"<Q {self.exid} 0 0>"
    
    def __repr__(self):
        try:
            active = self.active
        except:
            active = "?"

        cls = self.__class__.__name__
        return f"<{cls} {self.exid} state={active}>"

type SetPulse = Callable[[float|None], None]
"""
Called by a Servo class to set a servo’s pulse in fractions of a
second; “fractions” meaning the unit is 1sec and float < 1. Passing
None as argument will turn the servo off in its current position (to
minimize jitter). Always returns None.
"""

class Servo(object):
    """
    Baseclass for servos. The particular servo classes implement
    pulse_for() to convert an angle to the specific pulse length
    that will move the servo to that angle.
    """
    def __init__(self, set_pulse:SetPulse, stop_timeout=0.2):
        self._set_pulse = set_pulse
        self.stop_timeout = stop_timeout
        
        self._timeout = None
        
    def pulse_for(self, angle:float) -> float:
        raise NotImplementedError()

    def set_angle(self, angle:float) -> None:
        self.set_pulse(self.pulse_for(angle))

    def stop(self) -> None:
        self._set_pulse(None)

    def set_pulse(self, pulse_ms:float) -> None:
        self._set_pulse(pulse_ms)
        
        if self._timeout:
            self._timeout.cancel()
            
        self._timeout = threading.Timer(self.stop_timeout, self.stop)
        self._timeout.start()
    
    
class Pin(object):
    """
    GPIO Pin for output.
    """
    def __init__(self, initial:bool):
        self._state = initial
    
    def set(self, state:bool) -> None:
        raise NotImplementedError()

    def get(self) -> bool:
        return self._state

    def turn_on(self):
        self.set(True)

    def turn_off(self):
        self.set(False)

    @property
    def on(self) -> bool:
        return self._state

    @on.setter
    def on(self, state):
        self.set(state)

    @property
    def off(self) -> bool:
        return (not self._state)

    @on.setter
    def off(self, state:bool):
        self.set(not state)
        
        

        
