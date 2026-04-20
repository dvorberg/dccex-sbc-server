from typing import Tuple

from .abc import Agent
from .baseclasses import Hardware, Responder

class Agent(Agent, Responder):
    def __init__(self, hardware:Hardware, state_map:Tuple|None=None):
        """
        If a state map is provided, the hardware will be called
        through `set(state_map[i])` instead of `set(hardware.states[i])`.
        """
        self.hardware = hardware
        self.state_map = state_map

        if isinstance(hardware, Responder):
            self.responder = hardware

    async def set(self, activate:int):
        """
        This is the default case. Most DCC commands causing any hardware
        to move of change have a single intetger as id for the device
        and another integer as either an 0=off or 1=on state. 
        """
        if self.state_map:
            self.hardware.set(self.state_map[activate])
        else:
            self.hardware.set(self.hardware.states[activate])

        await self.publish_state()

    async def publish_state(self):
        response = self.state_response
        if response:
            self.publish(response)

    @property
    def state_response(self) -> bytes:
        raise NotImplementedError()

class SilentAgent(Agent):
    @property
    def state_response(self) -> bytes:
        cls = self.__class__.__name__
        response = f"<*sbc {cls} {self.address} set to {self.hardware.state} *>"
        return response.encode("ascii", "replace")           
    
class Accessory(SilentAgent):
    """
    The DCC Command Station can talk to DCC Accessory Controllers over the 
    track. The controller will then power and activate that accessory.
    There are two options how to address these:

        <a addr subaddr activate>

    and

        <a linear_addr activate>

    The addresses are a pair (tuple) of integers for the first case
    and a single integer in the latter case. `activate` is either:
    * 0 (off, deactivate, straigt or closed)
    * 1 (on, activate, turn or thrown)

    The `activate` parameter will map to the first and the second state
    of the Hardware, respectively.

    The accessory command <a …> does not create any response.
    There is no command to setup or list accessories.
    """
    def __init__(self, address:int|Tuple[int, int], hardware:Hardware,
                 state_map:Tuple|None=None):
        super().__init__(hardware, state_map)
        self.address = address
        self.responder = None

    async def set_aspect(self, aspect:int):
        """
        This corresponds to DCC-EX’ new <A address asect> command.
        The default impementation will set the `hardware` to the
        state numbered by the `aspect`.

        This does not create responses. 
        """        
        self.hardware.set(self.hardware.states[aspect])
        
class Turnout(Agent):
    """
    An object of this class is listed as a turnout in the virtual command
    station. It is not neccessarily a turnout in the real world, but can
    also be, for example, a semaphone or another servo driven accessory.
    """
    def __init__(self, turnout_id:int, hardware:Hardware,
                 address_spec:Tuple|None=None,
                 state_map:Tuple|None=None):
        """
        The `turnout_id` is the integer number by which this
        turnout is identified for commands. The `address_spec` allows
        to emulate the various ways in which a turnout may be setup in
        DCC EX. It has no application beyond providing setup
        information if requested by the client. If not set, the
        virtual station will not list this turnout when requested to
        do so by <JT …> or <J T …> commands. If set, it will turn the
        members of the tuple to byte strings and join them with
        spaces. (Use byte strings, not strings!) 

            turnout_id = 5, address_spec = ( b"DCC", 7, 12)
            <T 5 X>
            => <H 5 DCC 7 12>
        """
        super().__init__(hardware, state_map)
        self.turnout_id = turnout_id
        if address_spec:
            self.address_spec = b" ".join([bytes(a) for a in address_spec])
        else:
            self.address_spec = None

    @property
    def state_response(self) -> bytes:
        return b"<H %i %i>" % ( self.turnout_id, self.hardware.state, )

    @property
    def setup_response(self) -> bytes:
        if self.address_spec:
            return b"<H %i %s>" % (self.turnout_id, self.address_spec)

class Threeway(object):
    class Agent(Turnout):
        def __init__(self, wrapper, turnout_id, thrown_state):
            if thrown_state == wrapper.hardware.left:
                hardware = wrapper.hardware.left_turnout
            else:
                hardware = wrapper.hardware.right_turnout
               
            super().__init__(turnout_id, hardware)
            
            self.wrapper = wrapper
            self.thrown_state = thrown_state

        async def set(self, state:int):
            if state == 0:
                self.wrapper.hardware.set(0)
            else:
                self.wrapper.hardware.set(self.thrown_state)

            await self.wrapper.publish_states()

    def __init__(self, left_turnout_id:int, right_turnout_id:int,
                 hardware:Hardware):
        self.hardware = hardware
        self.left_agent = self.Agent(self, left_turnout_id, 1)
        self.right_agent = self.Agent(self, right_turnout_id, 2)

    async def publish_states(self):
        self.left_agent.publish(b"<H %i %i>" % (
            self.left_agent.turnout_id,
            self.hardware.left_turnout.state, ))
        self.right_agent.publish(b"<H %i %i>" % (
            self.right_agent.turnout_id,
            self.hardware.right_turnout.state, ))

class Cross(object):
    class Agent(Turnout):
        def __init__(self, wrapper, turnout_id, ab=0):
            hardware = [ wrapper.cross.a,
                         wrapper.cross.b][ab]
               
            super().__init__(turnout_id, hardware)
            
            self.wrapper = wrapper
            self.ab = ab

        async def set(self, state:int):
            cross = self.wrapper.cross
            
            if state == 0:
                cross.a.reset()
                cross.b.reset()
            else:
                if self.ab == 0:
                    cross.a.throw()
                    cross.b.reset()
                else:
                    cross.b.throw()
                    cross.a.reset()                    
                
            await self.wrapper.publish_states()

    def __init__(self, a_id:int, b_id:int, cross:Hardware):
        self.cross = cross
        self.a_agent = self.Agent(self, a_id, 0)
        self.b_agent = self.Agent(self, b_id, 1)

    async def publish_states(self):
        self.a_agent.publish(b"<H %i %i>" % (
            self.a_agent.turnout_id, self.cross.a.state, ))
        self.b_agent.publish(b"<H %i %i>" % (
            self.b_agent.turnout_id, self.cross.b.state, ))

        
class Signal(SilentAgent):
    state_map = { "AMBER": "amber",
                  "GREEN": "green",
                  "RED": "red", }
    
    def __init__(self, signal_id:int, hardware:Hardware,
                 state_map:dict|None=None):
        super().__init__(hardware, state_map)
        self.signal_id = signal_id

        if state_map is None:
            self.state_map = self.__class__.state_map
        else:
            self.state_map = state_map

    @property
    def address(self) -> int:
        return self.signal_id
            
    async def set(self, color:str):
        self.hardware.set(self.state_map[color])
        await self.publish_state()
            
