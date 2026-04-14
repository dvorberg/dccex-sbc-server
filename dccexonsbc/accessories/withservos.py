#!/usr/bin/env python

from ..baseclasses import Servo, Turnout, Signal, ThreeStateSignal

class ServoTurnout(Turnout):
    def __init__(self, servo:Servo, bounds:tuple[float, float]):
        # Bounds are 0 <= bound <= 180°,
        # first for regular position
        # second for thrown position.
        self.servo = servo
        self.bounds = ( servo.pulse_for(bounds[0]),
                        servo.pulse_for(bounds[1]), )

        # Force a servo update.
        self._state = None
        self._set(self.closed_state)

    @property
    def state(self):
        return self._state

    def _set(self, state:int):
        if state != self._state:
            self.servo.set_pulse(self.bounds[state])
            self._state = state
        
class ServoSemaphore(Signal):    
    def __init__(self, servo:Servo, bounds:tuple[float, float]):
        # Bounds are 0 <= bound <= 180°,
        # first for regular position
        # second for thrown position.
        self.servo = servo
        self.bounds = ( servo.pulse_for(bounds[0]),
                        servo.pulse_for(bounds[1]), )

        # Force a servo update.
        self._state = None
        self._set(self.red)

    @property
    def state(self):
        return self._state

    def _set(self, state:int):
        if state != self._state:
            idx = self.states.index(state)
            self.servo.set_pulse(self.bounds[idx])
            self._state = state
        

class ThreeStateServoSemaphore(ThreeStateSignal):
    def __init__(self,
                 main_servo, main_bounds:tuple[float, float],
                 speed_servo, speed_bounds:tuple[float, float]):
        self.main_signal = ServoSemaphore(main_servo, main_bounds)
        
        # Bounds are 0 <= bound <= 180°,
        # first for regular position
        # second for thrown position.
        self.speed_servo = speed_servo
        self.speed_bounds = ( speed_servo.pulse_for(speed_bounds[0]),
                              speed_servo.pulse_for(speed_bounds[1]), )

        # This is going to initialize the main servo and reset()
        # the signal to STOP.
        self._state = None
        self._set(self.states[0])

    @property
    def signaling_stop(self) -> bool:
        return (self._state == self.red)

    async def greenlight(self):
        if self._state != self.green:
            await self.main_signal.greenlight()
            self.speed_servo.set_pulse(self.speed_bounds[0])
            self._state = self.green

    async def slowlight(self):
        if self._state != self.amber:
            await self.main_signal.greenlight()
            self.speed_servo.set_pulse(self.speed_bounds[1])
            self._state = self.amber

    async def reset(self):
        if not self.signaling_stop:
            await self.main_signal.reset()
            self.speed_servo.set_pulse(self.speed_bounds[0]) 
            self._state = self.red
    
    async def set(self, state:str):
        assert state in self.states, ValueError
        
        if state == self.red:
            await self.reset()
        elif state == self.green:
            await self.greenlight()
        elif state == self.amber:
            await self.slowlight()
        
        
        
                 
        

    

