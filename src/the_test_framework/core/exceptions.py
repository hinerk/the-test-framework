class TestSystemException(Exception):
    """TestSystem base exception"""

class TestSystemIntrospectionError(TestSystemException):
    """issues occuring during initial introspection"""

class NoTestSystemInstanceFound(TestSystemException):
    """raised by TestSystem.get_active_instance() if no such thing was found"""

class TestSystemBaseFlowControlException(TestSystemException):
    """TestSystem base exception for "controlling" purposes"""

class QuitTestSystem(TestSystemBaseFlowControlException): ...

class FailedTest(TestSystemBaseFlowControlException): ...

class AbortTestSequence(TestSystemBaseFlowControlException):
    """raised by test_step to indicate the termination of the test sequence"""
