import argparse, atexit, asyncio, functools
from typing import Callable, Coroutine

import importlib, pathlib
import importlib.machinery
import importlib.util

from .baseclasses import Pin

def load_module_from_file(filepath):
    """
    Load a python module from a .py path identified by `filepath`.
    """
    path = pathlib.Path(filepath)
    name = path.stem
    loader = importlib.machinery.SourceFileLoader( name, filepath)
    spec = importlib.util.spec_from_loader( name, loader )
    module = importlib.util.module_from_spec( spec )
    loader.exec_module( module )

    return module
            
class HardwareSetupArgumentParser(argparse.ArgumentParser):
    """
    Augment argparse.ArgumentParser with default arguments to
    feed useful parameters to hardware_setup() functions
    for debugging and other purposes. 
    """
    
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.add_argument("-S", "--set-value", action="append", default=[],
                          help="Use format name=value to pass string values "
                          "to the hardware_setup() function.")
        self.add_argument("-E", "--eval-value", action="append", default=[],
                          help="Use format name=expression to pass values "
                          "to the hardware_setup() function. "
                          "Expressions are evaluated in your "
                          "hardware_setup() module.")        
        self.add_argument("modules", nargs="+",
                          help="Python module that defines "
                          "the hardware_setup(station) function we use to "
                          "setup the hardware this virtual command station "
                          "will interact with.")


    def call_hardware_setup_for(self, station, **kw):
        """
        Load the module specified on the command line,
        augment `kw` with options from --set-value and --eval-value
        (which will overwrite kw) and call the hardware_setup() function
        from our module with `station` and `**kw`. 
        """
        args = self.parse_args()

        for module in args.modules:
            self._call_hardware_setup_in(module, station, args, **kw)
            
    def _call_hardware_setup_in(self, module, station, args, **kw):
        module = load_module_from_file(module)
        hardware_setup = getattr(module, "hardware_setup", None)
        
        if hardware_setup is None:
            warnings.warn(f"{modulename} does not contain a "
                          "hardware_setup() function.")
            return

        for s in args.set_value:
            if not "=" in s:
                self.error("Syntax for -S/--set-value values is name=value.")
            else:
                name, value = s.split("=", 1)
                kw[name] = value

        for s in args.eval_value:
            if not "=" in s:
                self.error("Syntax for -E/--eval-value values is name=value.")
            else:
                name, value = s.split("=", 1)
                kw[name] = eval(value, globals=module.__dict__)

        hardware_setup(station, **kw)
            
def SBC(remote=None):
    """
    If remote is None, return the lgpio module.  Otherwise, if
    remote is a host[:port] spec (with the port defaulting to 8889)
    return a rgpio connection augmented with const names that make
    it a drop-in replacement for lgpio. 
    """
    if remote is None:
        import lgpio
        return lgpio
    else:
        import rgpio

        if ":" in remote:
            host, port = remote.split(":", 1)
            port = int(port)
        else:
            host = remote
            port = 8889

        sbc = rgpio.sbc(host, port)

        for name in ("SET_ACTIVE_LOW", "SET_OPEN_DRAIN", "SET_OPEN_SOURCE",
                     "SET_PULL_UP", "SET_PULL_DOWN", "SET_PULL_NONE",
                     "RISING_EDGE", "FALLING_EDGE", "BOTH_EDGES"):
            setattr(sbc, name, getattr(rgpio, name))

        return sbc

class GPIOError(Exception): pass

class FunctionWrapper(object):
    def __init__(self, name, function):
        self.name = name
        self.function = function

    def __call__(self, *args, **kw):
        print("CALL!", self.name + "(", repr(args), repr(kw), ")")
        return self.function(*args, **kw)

class Wrapper(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped
        
    def __getattr__(self, name):
        print("__getattr__", name)        
        ret = getattr(self.wrapped, name)
        if name.startswith("gpio_") or name == "callback":
            return FunctionWrapper(name, ret)
        else:
            return ret
    
class GPIO(object):
    """
    Wrapper class for a SBC’s GPIO pins.

    Once you either made a pin writable or readable (by registering
    a callback with it), that’s what it is. You can’t change mode.
    I figure, you hooked up some electronics to that pin and we’re
    not going to change that in software.

    This class will take care of releasing all resources when the
    interpreter process terminates through Python’s `atexit` mechanism. 
    """

    def __init__(self, sbc, gpio_chip=0):
        self.sbc = sbc # Wrapper()
        self.gpio_chip = gpio_chip
        self._handle = self.sbc.gpiochip_open(gpio_chip)
        self._write_pins = set()
        self._read_pins = {}

        atexit.register(self.cleanup)

    def make_pin_writable(self, pin:int, initial:bool=False,
                          line_flags:int=0):
        """
        * `pin` is the number of the pin to be used in l/rgpio numbering
           which corresponds to “BCM” numbering on a Raspberry Pi, that is
           logical numbering, *not* the number of the pin in the header.
        * `initial` True for on, False for off, obviously.
        * Possible `line_flags` are: SET_ACTIVE_LOW, SET_OPEN_DRAIN,
          SET_OPEN_SOURCE, SET_PULL_UP, SET_PULL_DOWN, and SET_PULL_NONE.
        """
        if pin in self._read_pins:
            raise GPIOError("Can’t use a pin for reading and writing "
                            "at the same time.")
        gpio_claim_output(self._handle, pin, int(initial_level), line_flags)
        self._write_pins.add(pin)
        
        return Pin(self, pin, initial)

    def register_pin_callback(self, pin:int, callback:Callable,
                              event_flags:int, line_flags:int=0,
                              bouncetime_msec:float|None=None):
        """
        * `pin` is the number of the pin to be used in l/rgpio numbering
           which corresponds to “BCM” numbering on a Raspberry Pi, that is
           logical numbering, *not* the number of the pin in the header.
        * The `callback` will receive four parameters:
          `chip`, `gpio`, `level`, `timestamp`.
        * Possible `event_flags` are RISING_EDGE, FALLING_EDGE, and BOTH_EDGES,
          each available as properties of `sbc`.
        * Possible `line_flags` are: SET_ACTIVE_LOW, SET_OPEN_DRAIN,
          SET_OPEN_SOURCE, SET_PULL_UP, SET_PULL_DOWN, and SET_PULL_NONE.
        * If `bouncetime_msec` is set, l/rgpio’s debouncing mechanism will
          be used. 
        """
        if pin in self._write_pins:
            raise GPIOError("Can’t use a pin for reading and writing "
                            "at the same time.")
        if pin in self._read_pins:
            raise GPIOError("Can’t register multiple callbacks per pin.")

        # This gpio_free may seem redundant, but is required when changing
        # the line-flags of an already acquired input line
        try:
            self.sbc.gpio_free(self._handle, pin)
        except Exception:
            pass

        # RPi.setup() does this. It does seem redundant. 
        self.sbc.gpio_claim_input(self._handle, pin, line_flags)
        
        self.sbc.gpio_claim_alert(self._handle, pin, event_flags, line_flags)
        
        if bouncetime_msec:
            self.sbc.gpio_set_debounce_micros(
                self._handle, pin, int(bouncetime_msec*1000))
        
        self._read_pins[pin] = self.sbc.callback(
            self._handle, pin, func=callback)

        initial = self.sbc.gpio_read(self._handle, pin)
        callback(self.gpio_chip, pin, initial, 0)

    def _write__Pin(self, pin:int, level:int):
        self.sbc.gpio_write(self._handle, pin, level)

    def register_pin_callback_threadsafe(
            self, pin:int, loop, callback:Callable, 
            event_flags, line_flags=0,
            bouncetime_msec:float|None=None):
        """
        Like `register_pin_callback()` but uses `loop.call_soon_threadsafe`
        to run the callback on the event loop’s thread in a way that interacts
        will with your asyncio code.
        
        * `pin` is the number of the pin to be used in l/rgpio numbering
           which corresponds to “BCM” numbering on a Raspberry Pi, that is
           logical numbering, *not* the number of the pin in the header.
        * The `callback` will receive four parameters:
          `chip`, `gpio`, `level`, `timestamp`.
        * Possible `event_flags` are RISING_EDGE, FALLING_EDGE, and BOTH_EDGES,
          each available as properties of `sbc`.
        * Possible `line_flags` are: SET_ACTIVE_LOW, SET_OPEN_DRAIN,
          SET_OPEN_SOURCE, SET_PULL_UP, SET_PULL_DOWN, and SET_PULL_NONE.
        * If `bouncetime_msec` is set, l/rgpio’s debouncing mechanism will
          be used. 
        """
        def call(*args, **kw):
            loop.call_soon_threadsafe(functools.partial(callback, *args, **kw))

        self.register_pin_callback(pin, call,
                                   event_flags, line_flags,
                                   bouncetime_msec)

    # def register_pin_coroutine_threadsafe(
    #         self, pin:int, loop, coroutine:Coroutine,
    #         event_flags, line_flags=0):
    #     """
    #     Like `register_pin_callback()` but uses
    #     `asyncio.run_coroutine_threadsafe` to await `courouting` on
    #     the event loop in a way that interacts will with threads.
    #     """
        
    def cleanup(self):
        for pin, callback in self._read_pins.items():
            callback.cancel()
            self.sbc.gpio_free(self._handle, pin)

        for pin in self._write_pins:
            self.sbc.gpio_free(self._handle, pin)
            
        self.sbc.gpiochip_close(self._handle)

class Pin(Pin):
    def __init__(self, gpios:GPIO, pin:int, initial:bool):
        self.gpios = gpios
        self.pin = pin
        super().__init__(initial)

    def set(self, state:bool) -> None:
        self.gpios._write(self.pin, int(state))
        self._state = state

