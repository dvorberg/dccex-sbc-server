import sys, re, time, asyncio, threading, logging, signal, functools, traceback
from typing import Tuple

import icecream; icecream.install()

from .abc import Server, Station
from .baseclasses import Responder, Sensor
from . import agents
from .publication import Publisher, Subscription

class TerminateSignal(object): pass

class DuplicateError(Exception): pass

class Server(Server):
    def __init__(self, station:Station):
        self.station = station
        self.handler_tasks = set()
        self.server_task = None
        
    async def start_handlers(self, reader, writer):
        read_handler = self.station.loop.create_task(
            self.read_commands(reader), name="read_handler")
        write_handler = self.station.loop.create_task(
            self.write_responses(writer), name="write_handler")

        self.handler_tasks.add(read_handler)
        read_handler.add_done_callback(self.remove_task)
        
        self.handler_tasks.add(write_handler)
        write_handler.add_done_callback(self.remove_task)


    def remove_task(self, task):
        self.handler_tasks.discard(task)

    async def read_commands(self, reader):
        while True:
            command = await reader.read(100)
            if command == b"":
                break
            else:
                self.station.command_publisher.publish(command)
                
    async def write_responses(self, writer):
        async for response in Subscription(self.station.response_publisher):
            if type(response) is str:
                response = response.encode("ascii")

            writer.write(response)
            
            if not response.endswith(b"\r\n"):
                writer.write(b"\r\n")
                
            await writer.drain()

    async def handle_signals(self):
        async for signal in Subscription(self.station.signal_publisher):
            if signal is TerminateSignal:
                # Our process is told to terminate.
                # Stop what we’re doing.
                for task in self.handler_tasks:
                    task.cancel()

                if self.server_task:
                    self.server_task.cancel()
                    
                break
            
    async def start(self, host, port):        
        self.station.loop.create_task(self.handle_signals())
        
        start_server = asyncio.start_server(self.start_handlers,
                                            host=host, port=port)
        self.server_task = self.station.loop.create_task(
            start_server, name="Server")
        server = await self.server_task

        addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
        print(f'Serving on {addrs}')

class DCCEXParseError(Exception): pass        

class Station(Station):
    def __init__(self, host=None, port=2560):
        self.host = host
        self.port = port

        self.command_publisher = Publisher()
        """
        Hub for DCC-EX commands recieved through the network. 
        """

        self.response_publisher = Publisher()
        """
        Hub for DCC-EX responses to be sent though the network.
        """

        self.signal_publisher = Publisher()
        """
        Hub for signals. At this time there is only one:
        TerminateSignal which informs our various components
        to stop what they are doing. 
        """

        self.loop = None
        def run_event_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            try:
                self._running = True
                loop.run_forever()
                for task in asyncio.all_tasks(loop):
                    if not (task.done() or task.cancelled()):
                        try:
                            loop.run_until_complete(task)
                        except:
                            pass
            finally:
                loop.close()

            self.loop = None

        self.thread = threading.Thread(target=run_event_loop)
        self.thread.start()

        while True:
            # Here we will always wait 1/100th of a second.
            time.sleep(0.01)
            if self.loop is not None:
                break

        ## We have our event loop running in a separate thread now.

        # Set out server to a new Server instance. 
        self.server = Server(self)
        
        # Set up our agents lists.
        self.sensors = {}
        self.turnouts = {}
        self.accessories = {}
        self.signals = {}
        
        # Setup operating system signal handling, mostly to 
        # facilitate clean shutdown. 
        self.old_signal_handlers = {}
        for signalnum in (signal.SIGINT, signal.SIGTERM):
            self.old_signal_handlers[signalnum] = signal.signal(
                signalnum, self.handle_signal)

    def stop(self):
        """
        Stop the server’s operation.
        """
        def _stop():
            self.signal_publisher.publish(TerminateSignal)
            self.command_publisher.discontinue()
            self.response_publisher.discontinue()
            self.signal_publisher.discontinue()

            self._running = False
            
            # The loop will finish its tasks and after than,
            # in self.thread, run_forever() will return and
            # run_event_loop() will set self.loop to None.
            self.loop.stop()

        if self.loop is None:
            raise RuntimeError("Loop already shut down.")
        else:
            self.loop.call_soon_threadsafe(_stop)
        

    def abort(self):
        """
        Abort allows to cleanly abort server setup before run()
        has been called.
        """
        if self.running:
            self.stop()
        self.thread.join()

    param_re = re.compile(br"(?:(\d+)|([a-zA-Z]+))(.*)")
    def parse_params(self, params):
        while params:
            match = self.param_re.search(params)
            if match is None:
                raise DCCEXParseError("Can’t parse params " + repr(params))
            else:
                i, s, params = match.groups()

                if i:
                    yield int(i)
                elif s:
                    yield s.decode("ascii").upper()

                
    command_re = re.compile(br"<"
                            br"(?:([a-zA-Z/=\#]+)(?: (.*))?)"
                            br">")
    whitespace_re = re.compile(br"\s+")
    def parse_command(self, command:bytes) -> Tuple[str, Tuple]:
        """
        Parse out subset of DCC++ commands into a single letter (string)
        and a tuple of 0 or more parameters. If these parameters can be
        parsed into an integer, they will be integers, otherwise strings.
        """
        print("parse_command()", repr(command))
        match = self.command_re.match(command)
        if match is None:
            raise DCCEXParseError(command.decode("ascii", "replace"))
        else:
            opcode, params = match.groups()
            opcode = opcode.decode("ascii")
            
            if opcode == "M":
                data = [int(b, 16) for b in params.split(b" ")]
                return "M", data,
            else:
                if params:
                    params = tuple(self.parse_params(params))
                else:
                    params = ()

                if opcode == "JT":
                    opcode = "J"
                    params = ("T",) + params

                if not params:
                    return opcode
                else:                
                    return opcode, params,
        
    async def handle_commands(self):
        # Shorthand:
        respond = self.response_publisher.publish

        def error(): respond(b"<X>")
        def ok(): respond(b"<O>")

        def list_turnouts():
            for t in self.turnouts.values():
                respond(t.state_response)

        def list_sensor_states():
            for sensor in self.sensors.values():
                respond(sensor.state_response)

        async def set_accessory_extended_aspect_m(first, second, aspect):
            # “DCC Extended Packet Formats” #600
            # https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/s-9.2.1_dcc_extended_packet_formats.pdf
            
            # • The most significant bits of the 11-bit address are
            #   bits 4 to 6 of the second byte.
            most = (second & 0b01110000) >> 4

            # • By convention these bits (bits 4 to 6 of the second byte)
            #   are in ones’ complement (reversed).
            most = 7 - most # Reverse 3 bits

            # • This is followed by bits 0 to 5 of the first byte.
            followed = first & 0b00111111

            # • The least significant bits of the
            #   11-bit address are bits 1 to 2 of the second byte.
            least = (second & 0b00000110) >> 1

            address = (most << 7) | (followed << 2) | (least)

            # These addresses are 0-based.
            address += 1
            
            await set_accessory_extended_aspect(address, aspect)

        async def set_accessory_extended_aspect(address, aspect):
            try:
                await self.accessories[address].set(aspect)
            except KeyError:
                error()
                        
        async for command in Subscription(self.command_publisher):
            print("Handling command", repr(command))

            try:
                cmd = self.parse_command(command)
            except DCCEXParseError as exc:
                traceback.print_exception(exc)
                error()
                continue

            match cmd:
                # Station init
                case "s":
                    respond(b"<iDCC-EX V-5.4.20 / "
                            b"MEGA / EX8874 G-master-202604121700Z>")
                    list_turnouts()
                    list_sensor_states()

                case "#":
                    respond("<# 50>")

                # Direct package command
                case "M", data:
                    # Apparently, jmri supported extended accessories
                    # before DCC-EX did and insists on sending raw
                    # DCC packages which it provides through the <M …>
                    # internal command. 
                    assert data[0] == 0, ValueError
                    data = data[1:]
                    
                    if data:
                        opcode = data[0] >> 6
                        if opcode == 0b10 and len(data) == 3:
                            await set_accessory_extended_aspect_m(*data)
                    
                # Sensors
                case "S":
                    # Request technical sensor info.
                    for sensor in self.sensors.values():
                        respond(sensor.setup_response)
                        
                case "Q":
                    # Request list of sensor states.
                    list_sensor_states()
                    
                case "S", (id,):
                    # Delete a sensor. We respond by indicating an error.
                    # We can’t delete sensonrs.
                    error()
                case "S", (id, vpin, pullup):
                    # Setup a sensor. We don’t do anything, but respond as
                    # if the operation had been successfull.
                    ok()

                # Turnouts
                case "T":
                    # <T> - Request a list all defined turnouts/Points
                    list_turnouts()
                        
                case "T", (id, state,):
                    if id not in self.turnouts:
                        error()
                        break
                    
                    if state == "C":
                        state = 0
                    elif state == "T":
                        state = 1
                    elif state == "X":
                        response = self.turnouts[id].setup_response
                        if response:
                            respond(response)
                            break
                        
                    # <T id state> - Throw or Close a defined turnout/point
                    if not state in {0, 1}:
                        error()
                    else:
                        await self.turnouts[id].set(state)

                case "J", ("T",):
                    ids = [ str(turnout.turnout_id)
                            for turnout in self.turnouts.values() ]
                    ids = " ".join(ids)
                    respond(b"<jT %s>" % ids.encode("ascii"))
                        
                case "J", ("T", id):
                    # <J T id> <JT id> - Request details of a specific
                    # Turnout/Point
                    for turnout in self.turnouts.values():
                        setup_response = turnout.setup_response
                        if setup_response:                            
                            respond(setup_response)

                            
                # Accessories
                case "a", (address, subaddress, activate):
                    # <a addr subaddr activate>
                    # - Control an Accessory Decoder with Address and Subaddress

                    if not activate in {0, 1}:
                        error()
                        break
                    
                    if (address, subaddress) in self.accessories:
                        accessory = self.accessories[(address, subaddress)]
                        await accessory.set(activate)

                case "a", (address, activate):
                    # <a linear_addr activate> - Control an Accessory Decoder
                    # with linear address

                    if not activate in {0, 1}:
                        error()
                        break
                    
                    if address in self.accessories:
                        await self.accessories[address].set(activate)
                    else:
                        error()

                case "A", (address, aspect):
                    if not type(aspect) is int:
                        error()
                        break
                    
                    # <A address aspect> - Command for DCC Extended Accessories.
                    if not address in self.accessories:
                        error()
                        break
                    
                    await set_accessory_extended_aspect(address, aspect)
                    
                # Signals                        
                case "/", (state, signal_id):
                    if not type(signal_id) is int:
                        error()
                        break

                    if not signal_id in self.signals:
                        error()
                        break
                    
                    try:
                        await self.signals[signal_id].set(state)
                    except KeyError:
                        error()
                        break

                # Output Pins
                case "Z":
                    # At this time we do not define output pins.
                    pass                
                    
                case None:
                    ic(command, "ignored (None)")
                    pass

                case _:
                    ic(command, "ignored (default)")
                    pass
        
    def handle_signal(self, signalnum, stackframe):
        if signalnum in { signal.SIGINT, signal.SIGTERM }:
            # Threadsafely publish the TerminateSignal.
            self.stop()

            # Wait for the loop to terminate.
            while self.loop is not None:
                time.sleep(0.01)

            # This will exit the process.
            handler = self.old_signal_handlers[signalnum]
            if callable(handler):
                handler(signalnum, stackframe)

    async def _run(self):
        try:
            await asyncio.gather(self.server.start(self.host, self.port),
                                 self.handle_commands())
        except Exception as exc:
            traceback.print_exception(exc)
            raise

    def run(self):
        asyncio.run_coroutine_threadsafe(self._run(), self.loop)
        self.thread.join()

    @property
    def running(self):
        return self._running

    def register_sensor(self, sensor:Sensor):
        assert isinstance(sensor, Sensor), TypeError
        if sensor.exid in self.sensors:
            raise DuplicateError(f"Sensor with id "
                                 f"{sensor.exid}"
                                 f"already registered.")
        else:
            self.sensors[sensor.exid] = sensor
            sensor.response_publisher = self.response_publisher

    def register_sensors(self, sensors):
        for sensor in sensors:
            self.register_sensor(sensor)

    def register_accessory_agent(self, accessory:agents.Accessory):
        assert isinstance(accessory, agents.Accessory), TypeError(
            "This is registering only Accessory Agents.")
        if accessory.address in self.accessories:
            raise DuplicateError(f"Accessory with address "
                                 f"{accessory.address}"
                                 f"already registered.")
        else:
            self.accessories[accessory.address] = accessory
            accessory.response_publisher = self.response_publisher
        
    def register_turnout_agent(self, turnout:agents.Turnout):
        assert isinstance(turnout, agents.Turnout), TypeError(
            "This is registering only Turnout Agents.")
        if turnout.turnout_id in self.turnouts:
            raise DuplicateError(f"Turnout (agent!) with id "
                                 f"{turnout.turnout_id}"
                                 f"already registered.")
        else:
            self.turnouts[turnout.turnout_id] = turnout
            turnout.response_publisher = self.response_publisher

    def register_signal_agent(self, signal:agents.Signal):
        assert isinstance(signal, agents.Signal), TypeError(
            "This is registering only Signal Agents.")
        if signal.signal_id in self.signals:
            raise DuplicateError(f"Signal (agent!) with id "
                                 f"{signal.signal_id}"
                                 f"already registered.")
        else:
            self.signals[signal.signal_id] = signal
            signal.response_publisher = self.response_publisher

    def register_agent(self, *args:agents.Agent):
        for agent in args:
            match type(agent):
                case agents.Turnout:
                    self.register_turnout_agent(agent)
                case agents.Accessory:
                    self.register_accessory_agent(agent)
                case agents.Signal:
                    self.register_signal_agent(agent)
                case _:
                    raise TypeError("Don’t know how to handle " + repr(agent))

if __name__ == "__main__":
    import argparse, warnings, pathlib

    from .utils import HardwareSetupArgumentParser

    parser = HardwareSetupArgumentParser()
    parser.add_argument("-H", "--host",
                        help="IP address or host name to "
                        "open bind to. Defaults to any available.")
    parser.add_argument("-p", "--port", type=int, default=2560,
                        help="TCP port to listen to. Defaults to 2560.")

    args = parser.parse_args()

    station = Station(host=args.host, port=args.port)
    
    try:
        parser.call_hardware_setup_for(station)
    except:
        station.abort()
        raise
    else:
        station.run()
    
