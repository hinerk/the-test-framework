class QuitTestSystem(Exception): ...

class FailedTest(Exception): ...

class SkippedTest(Exception): ...

class AbortTestSequence(Exception):
    """raised by test_step to indicate the termination of the test sequence"""

class NoTestSystemInstanceFound(Exception):
    """raised by get_active_instance() to indicate that no test system instance was found"""