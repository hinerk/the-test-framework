import inspect

from logging import getLogger
from typing import (
    Any,
    Annotated,
    Callable,
    Generator,
    get_args,
)
from the_test_framework.facilities import origin_of_func

from .argument_flag import ArgumentFlag, IsUUTSetupData


logger = getLogger(__name__)


def _parameter_with_certain_flag(
        func: Callable,
        annotated_with: type[ArgumentFlag]
) -> Generator[str, None, None]:
    for param_name, param in inspect.signature(func).parameters.items():
        if annotated_with in get_args(param.annotation):
            yield param_name


def get_flagged_argument(
        func: Callable,
        flag: type[ArgumentFlag]
) -> str | None:
    """get the name of a flagged function argument
    >>> def func(serial_no: Annotated[int, IsUUTSetupData]): ...
    >>> get_flagged_argument(func, IsUUTSetupData)
    'serial_no'
    """
    matching_args = list(_parameter_with_certain_flag(func, flag))
    if (total_matching_args := len(matching_args)) == 1:
        return matching_args[0]
    elif total_matching_args == 0:
        logger.warning(f"{origin_of_func(func)} none of this function's "
                       f"arguments is flagged as {flag}!")
        return None
    else:
        raise RuntimeError(f"{origin_of_func(func)} flags more than one "
                           f"argument as {flag}!")


def _get_argument_by_type(
        func: Callable,
        dtype: Any
) -> Generator[str, None, None]:
    for param_name, param in inspect.signature(func).parameters.items():
        if param.annotation is dtype:
            yield param_name
        if (param.annotation is Annotated
                and dtype in get_args(param.annotation)):
            yield param_name


def get_argument_by_type(
        func: Callable,
        dtype: Any
) -> str | None:
    """get the name of a function argument by its annotated type

    >>> def func(argument: float): ...
    >>> get_argument_by_type(func, float)
    'argument'
    """
    matching_args = list(_get_argument_by_type(func, dtype))
    if (total_matching_args := len(matching_args)) == 1:
        return matching_args[0]
    elif total_matching_args == 0:
        logger.warning(f"{origin_of_func(func)} none of this function's "
                       f"parameter has a type annotation which implies, that "
                       f"it would accept a {dtype!r} object!")
        return None
    else:
        raise RuntimeError(f"{origin_of_func(func)} has more than one "
                           f"parameter typed as {dtype!r}!")
