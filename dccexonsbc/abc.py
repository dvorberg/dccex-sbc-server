from typing import Tuple, Any

class Subscription(object):
    pass

class Publisher(object):
    """
    Publisher/subscriber message passing pattern. 
    """
    def publish(self, message:Any):
        """
        Publish a messsage to all subscribers. None will be ignored.
        """
        raise NotImplementedError()

    def discontinue(self):
        """
        Discontinue this publication. 
        """
        raise NotImplementedError()

    def make_subscription(self) -> Subscription:
        """
        Return a subscription to this publisher. 
        """
        raise NotImplementedError()

class Station(object):
    pass

class Server(object):
    pass

class HardwareItem(object):
    """
    Any piece hardware our DCC-EX server knows about like
    turnouts, signals, and signals. 
    """
    pass
    
class Responder(object):
    response_publisher:Publisher
    
    def publish(self, message:Any):
        raise NotImplementedError()

class Agent(object):
    responder:Responder = None
    """
    An agent may have a responder property (which may be self). On
    registering the station will set the responder’s `response_publisher`
    property. 
    """

    def set(self, *params):
        """
        Set the state of the associated hardware according to the
        command’s parameters. 
        """
        raise NotImplementedError()

    @property
    def setup_response(self):
        """
        For many types of agent there are corresponding commands, those
        to start and action or to request setup, often with the same
        opcode but different parameter list. This property lets the
        station reply to the request for setup information.
        """
        raise NotImplementedError()

