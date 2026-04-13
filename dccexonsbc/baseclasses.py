"""
(Abstract) base classes.

These unify some aspects of the interface I want these classes to
have. Generally, these classes know how to publish themselves in a
DCC-EX context, i.e. know how to formulate responses describing their
current state.
"""

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
    
    async def set(self, state:Any):
        raise NotImplemented()

    @property
    def state(self):
        raise NotImplemented()

class ResponderWithState(Responder, Hardware):
    
    @property
    def state_response(self) -> bytes:
        """
        Represent our state as a DCC-EX response.
        """
        raise NotImplementedError()

    async def _set(self, state:Any):
        """
        Actually set the state, maybe by mechanically moving things.
        This function may introduce a timeout using asyncio.sleep(). 
        """
        raise NotImplementedError()
    
    async def set(self, state:Any):
        """
        Await _set() to do the actual work and then publish our
        state respone.
        """
        await self._set(state)
        self.publish(self.state_response)
        
class Turnout(ResponderWithState):
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
    
    states = {closed_state, thrown_state}

    @property
    def thrown(self) -> bool:
        """
        Represent whether the turnout is in thrown state.  There
        is no setter for `thrown`. Throwing and closing may take its
        time and we don’t want to block processing.
        """
        return (self.state == self.thrown_state)
    
    async def throw(self):
        """
        Set the turnout in the thrown state.
        """
        await self.set(self.thrown_state)

    async def close(self):
        """
        Set the turnout in the default state.
        """
        await self.set(self.reset_state)

    @property
    def state_response(self) -> bytes:
        """
        Represent our state as a DCC-EX response.
        """
        return b"<H %i %i>" % ( self.exid, self.state, )

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
        

class Signal(Responder):
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
        
    async def greenlight(self):
        """
        Signal "go."
        """
        await self.set(self.green)

    async def reset(self):
        """
        Signal "stop."
        """
        await self.set(self.red)


class ThreeStateSignal(Signal):
    """
    Some signals/semaphores have three states for stop, go, and
    "go slowly."
    """
    amber = "amber"
    slow = "amber"

    states = {Signal.red, Signal.green, amber}

    async def slowlight(self):
        """
        Signal 
        """
        raise NotImplementedError()
    
    signaling_slow:bool = True

    
class Sensor(Responder):
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


    
