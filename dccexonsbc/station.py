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
            print("Got command through network", repr(command))
            if command == b"":
                break
            else:
                self.station.command_publisher.publish(command)
                
    async def write_responses(self, writer):
        async for response in Subscription(self.station.response_publisher):
            print("Got response through the queue", repr(response))
            
            if type(response) is str:
                response = response.encode("ascii")

            writer.write(response)
            
            if not response.endswith(b"\r\n"):
                writer.write(b"\r\n")
                
            await writer.drain()

    async def handle_signals(self):
        ic("handle_signals()")
        async for signal in Subscription(self.station.signal_publisher):
            ic(signal)
                
            if signal is TerminateSignal:
                # Our process is told to terminate.
                # Stop what we’re doing.
                for task in self.handler_tasks:
                    task.cancel()

                if self.server_task:
                    self.server_task.cancel()

                print("break")
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

    command_re = re.compile(br"<([QS])([\s\d]*)>")
    whitespace_re = re.compile(br"\s+")
    def parse_command(self, command:bytes) -> None|str|Tuple[str,Tuple]:
        """
        Parse out subset of DCC++ commands into a single letter (string)
        and a tuple or 0 or more integer parameters. 
        """
        print("parse_command()", repr(command))
        match = self.command_re.match(command)
        
        if match is None:
            return None
        else:
            letter, params = match.groups()
            letter = letter.decode()

            if params:
                params = tuple(
                    [int(a) for a in self.whitespace_re.split(params.strip())])
                return letter, params,
            else:
                return letter
        return None
    
    async def handle_commands(self):
        # Shorthand:
        respond = self.response_publisher.publish
        
        async for command in Subscription(self.command_publisher):
            print("Handling command", repr(command),
                  repr(self.parse_command(command)))
            
            match self.parse_command(command):
                case "S":
                    # Request technical sensor info.
                    for sensor in self.sensors.values():
                        respond(sensor.setup_response)
                case "Q":
                    # Request list of sensor states.
                    for sensor in self.sensors.values():
                        respond(sensor.state_response)
                case "S", (id,):
                    # Delete a sensor. We respond by indicating an error.
                    # We can’t delete sensonrs.
                    respond(b"<X>")
                case "S", (id, vpin, pullup):
                    # Setup a sensor. We don’t do anything, but respond as
                    # if the operation had been successfull.
                    respond(b"<O>")
                case None:
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
        assert isinstance(sensor, agents.Accessory), TypeError
        if accessory.address in self.accessories:
            raise DuplicateError(f"Accessory with address "
                                 f"{accessory.address}"
                                 f"already registered.")
        else:
            self.accessories[accessory.address] = accessory
            accessory.response_publisher = self.response_publisher
        
    def register_turnout_agent(self, turnout:agents.Turnout):
        assert isinstance(turnout, agents.Turnout), TypeError(
            "This is registering Turnout Agents, not turnout hardware.")
        if turnout.turnout_id in self.turnouts:
            raise DuplicateError(f"Turnout (agent!) with id "
                                 f"{turnout.turnout_id}"
                                 f"already registered.")
        else:
            self.turnouts[turnout.turnout_id] = turnout
            turnout.response_publisher = self.response_publisher

    def register_signal_agent(self, signal:agents.Signal):
        pass

if __name__ == "__main__":
    import argparse, warnings, pathlib

    from .utils import hardware_setup_functions

    parser = argparse.ArgumentParser()
    parser.add_argument("-H", "--host",
                        help="IP address or host name to "
                        "open bind to. Defaults to any available.")
    parser.add_argument("-p", "--port", type=int, default=2560,
                        help="TCP port to listen to. Defaults to 2560.")
    parser.add_argument("modules", nargs="+",
                        help="Python module that defines "
                        "the hardware_setup(station) function we use to "
                        "setup the hardware this virtual command station "
                        "will interact with.")

    args = parser.parse_args()

    station = Station(host=args.host, port=args.port)
    
    try:
        for hardware_setup in hardware_setup_functions(args.modules):
            hardware_setup(station)
    except:
        station.abort()
        raise
    else:
        station.run()
    
