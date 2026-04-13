"""
This module’s classes implement a Publisher/Subscriber message
passing scheme using `asyncio.Queue`.
"""
import asyncio
from typing import Any

from .abc import Publisher, Subscription

class FinalIssue(object):
    """
    This class object(!) marks the end of a Publisher’s life span.
    Publishing it will terminate all Subscriptions. 
    """
    pass

class Publisher(Publisher):
    """
    Publishing agent for your messages. The user-facing interface consists
    of the `publish()` and `discontinue()` methods. 
    """    
    def __init__(self):
        """
        We keep a list of queues that we will pass any message to. 
        """
        self.subscription_queues = set()

    def _Subscription__make_queue(self) -> asyncio.Queue:
        """
        Let a subscription request a new queue object.
        """
        return asyncio.Queue()

    def _Subscription__subscribe(self, queue:asyncio.Queue):
        """
        Let a subscription add the queue created to our list…
        """
        self.subscription_queues.add(queue)
        
    def _Subscription__unsubscribe(self, queue:asyncio.Queue):
        """
        …and also remove it when interest has waned.
        """
        self.subscription_queues.remove(queue)

    def publish(self, message:Any|None):
        """
        Pass a message to all subscribers. None will be ignored.
        """
        if message is not None:
            for queue in self.subscription_queues:
                queue.put_nowait(message)

    def discontinue(self):
        """
        Discontinue our publication by publishing the FinalIssue
        (class object).
        """
        self.publish(FinalIssue)

    def make_subscription(self) -> Subscription:
        """
        Return a `Subscription` to this publisher.
        """
        return Subscription(self)
        
class Subscription(Subscription):
    """
    A subscription is a context manager to be used like this:

        with Subscription(publisher) as queue:
            while True:
                message = await queue.get()
                if message is FinalIssue:
                    break
                else:
                    do_your_magic_with(message)

    Alternatively a subscription is a async generator of message:

        async for message in Subscription(publisher):
            do_your_magic_with(message)

    This is functionally equivalent to the above code block. 
    """
    def __init__(self, publisher:Publisher):
        """
        Create a new subscription. 
        """
        self.publisher = publisher
        self._queue = None
        
    def __enter__(self) -> asyncio.Queue:
        """
        Start a with: block, provide a queue. 
        """
        assert self._queue is None
        self._queue = self.publisher.__make_queue()
        self.publisher.__subscribe(self._queue)
        return self._queue

    def __exit__(self, type, value, traceback):
        """
        At the end of a with: block.
        """
        self.publisher.__unsubscribe(self._queue)
        self._queue = None

    async def __aiter__(self):
        """
        Implement the asyncronous iterator interface. It is implemented
        in the exact manner of the example code above. 
        """
        with self as queue:
            while True:
                ret = await queue.get()
                if ret is FinalIssue:
                    break
                else:
                    yield ret
                    queue.task_done()

