from abc import ABC


class ArgumentFlag(ABC):
    """flags a function's argument to indicate it expects certain data

    ArgumentFlag goes beyond what is expressible with type annotations.
    Consider the implementations of ArgumentFlag below for further explanation.
    """


class IsUUTSetupData(ArgumentFlag):
    """Flags an argument which expects the data returned by the UUT setup Callback

    >>> from the_test_framework.core import TestSystem
    >>> from typing import Annotated
    >>> @TestSystem().test_sequence
    ... def test_sequence(
    ...         serial_no: Annotated[int, IsUUTSetupData]
    ... ):
    ...     ...
    """


class IsSystemSetupData(ArgumentFlag):
    """Flags an argument which expects the data returned by the system setup Callback

    >>> from the_test_framework.core import TestSystem
    >>> from typing import Annotated
    >>> @TestSystem().uut_setup
    ... def uut_setup(
    ...         settings: Annotated[dict, IsSystemSetupData]
    ... ):
    ...     ...
    """


class IsTestSequenceData(ArgumentFlag):
    """Flags an argument which expects the data returned by from the test sequence Callback

    >>> from the_test_framework.core import TestSystem
    >>> from typing import Annotated
    >>> @TestSystem().uut_result_handler
    ... def uut_result_handler(
    ...         test_sequence_data: Annotated[dict, IsTestSequenceData]
    ... ):
    ...     ...
    """
