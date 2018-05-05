from enum import Enum


class Behaviors (Enum):
    FSMMatch = "FSMMatch"
    FSMTests = "FSMTests"
    Slave = "Slave"


class Behavior:
    def __init__(self, robot):
        raise NotImplementedError("Behavior is an abstract class, you must inherit from it")

    def loop(self):
        raise NotImplementedError("This method must be overrided")
