import enum

from contextlib import ExitStack
from typing import (
    Callable,
    Generator,
)

from the_test_framework.core.arg_flags import (
    get_flagged_argument,
    get_argument_by_type,
    IsSystemSetupData,
    IsUUTSetupData,
    IsTestSequenceData,
)
from the_test_framework.core.dtypes import TestResultInfo


class WellKnownArgument(enum.Enum):
    """Enumerates the framework's 'semantic' parameters.

    These are the only arguments the native (framework-internal) call sites know
    how to supply. A foreign function 'requests' one of these by either having
    a matching type annotation or an Annotated[...] flag the framework understands.
    """
    exit_stack = enum.auto()
    system_setup_data = enum.auto()
    uut_setup_data = enum.auto()
    test_sequence_data = enum.auto()
    test_result = enum.auto()


def well_known_arguments(
        func: Callable
) -> Generator[tuple[WellKnownArgument, str], None, None]:
    """Get WellKnownArguments and corresponding names from `func`s signature.

    A function 'declares' a well-known argument if:
    - its signature contains a parameter whose annotation matches a known type
      (e.g., ExitStack or TestResultInfo), OR
    - it uses Annotated[..., <KnownFlag>] on that parameter
      (e.g., IsSystemSetupData).

    :param func: the function about to be inspected.
    :raises RuntimeError: if more than one argument in `func`'s signature
    matches the same WellKnownArgument. Like, when two arguments are typed as
    ExitStack or are annotated with the same ArgumentFlag
    (e.g. Annotated[..., IsSystemSetupData]).
    :return: yields (WellKnownArgument, name of the argument)
    """
    exit_stack_arg_name = get_argument_by_type(func, ExitStack)
    if exit_stack_arg_name is not None:
        yield WellKnownArgument.exit_stack, exit_stack_arg_name

    system_setup_arg_name = get_flagged_argument(func, IsSystemSetupData)
    if system_setup_arg_name is not None:
        yield WellKnownArgument.system_setup_data, system_setup_arg_name

    uut_setup_arg_name = get_flagged_argument(func, IsUUTSetupData)
    if uut_setup_arg_name is not None:
        yield WellKnownArgument.uut_setup_data, uut_setup_arg_name

    test_sequence_arg_name = get_flagged_argument(func, IsTestSequenceData)
    if test_sequence_arg_name is not None:
        yield WellKnownArgument.test_sequence_data, test_sequence_arg_name

    test_result_arg_name = get_argument_by_type(func, TestResultInfo)
    if test_result_arg_name is not None:
        yield WellKnownArgument.test_result, test_result_arg_name
