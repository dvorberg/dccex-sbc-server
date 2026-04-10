import sys, asyncio, threading
import icecream; icecream.install()

class InterruptHandler(object):
    """
    Wrap a method that interacts with asynchronous code in such a way
    that it can be used as an interrupt callback. All arguments and
    return values will be discarded.

    The method here is the --best-- only way I found to make asyncio
    work with interrupts. Being interrupted upsets the event loop.  It
    seems, it was not designed to be used in such a way. There is a
    way, however, to interact with the event loop from a foreign
    thread.  So that’s what I do. I create a thread and call
    `loop.call_soon_threadsafe()` from it and it works like a charm!
    """
    def __init__(self, loop, method):
        self.loop = loop
        self.method = method

    def __call__(self, *args, **kw):
        def call():
            self.loop.call_soon_threadsafe(self.method)

        thread = threading.Thread(target=call)
        thread.start()
        
