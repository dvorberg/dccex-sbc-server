from typing import Tuple

from .abc import Agent, Responder
from .baseclasses import Hardware

class Agent(Agent, Responder):
    def __init__(self, hardware:Hardware, state_map=Tuple|None):
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
    
class Accessory(Agent):
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
                 state_map=Tuple|None):
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
        
    @property
    def state_response(self) -> bytes:
        response = f"<* {cls} {self.address} set to {self.hardware.state} *>"
        return response.decode("ascii", "replace")
        
class Turnout(Agent):
    """
    An object of this class is listed as a turnout in the virtual command
    station. It is not neccessarily a turnout in the real world, but can
    also be, for example, a semaphone or another servo driven accessory.
    """
    def __init__(self, turnout_id:int, hardware:Hardware,
                 address_spec:Tuple|None=None,
                 state_map=Tuple|None):
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
        return b"<H %i %i>" % ( self.turnout_id, self.state, )

    @property
    def setup_response(self) -> bytes:
        if self.address_spec:
            return b"<H %i %s>" % (self.turnout_id, self.address_spec)

class Signal(object):
    pass
