import inspect
import functools


from logging import getLogger
from typing import (
    Any,
    Callable,
    TypeAlias,
    Mapping,
)

from the_test_framework.facilities import origin_of_func
from the_test_framework.core.callback_registry.well_known_argument import well_known_arguments


logger = getLogger(__name__)


ForeignArgName: TypeAlias = str
NativeArgName: TypeAlias = str
NativeToForeign = dict[NativeArgName, ForeignArgName]


def create_kwargs_translation_table(
        native_func: Callable,
        foreign_func: Callable
) -> NativeToForeign:
    """Build a mapping of native kwarg name -> foreign kwarg name.

    The native (framework) call site provides certain well-known semantics
    under its own parameter names. The foreign function may use different
    parameter names for those semantics. This table rewires names at call time.

    :param native_func: the native function
    :param foreign_func: the foreign function
    :return: a mapping of native kwarg name -> foreign kwarg name
    :raises TypeError: if the foreign function requests a well-known argument
    that the native call site does not supply.
    """
    native_args = dict(well_known_arguments(native_func))  # {WK -> native_name}
    mapping: NativeToForeign = {}
    foreign_func_name = getattr(foreign_func, "__qualname__", foreign_func)
    native_func_name = native_func.__qualname__

    foreign_wk = list(well_known_arguments(foreign_func))
    if not foreign_wk:
        logger.debug("Foreign function %s declares no well-known args; "
                     "no translation needed.", foreign_func_name)

    logger.debug(f"Creating kwargs translation table for native function: "
                 f"`{origin_of_func(native_func)}` to foreign function: "
                 f"`{origin_of_func(foreign_func)}`")
    for wk_arg, foreign_arg_name in foreign_wk:
        if wk_arg not in native_args:
            raise TypeError(f"{foreign_func_name} declares `{wk_arg.name}`"
                            f" but native call {native_func_name} "
                            f"doesn’t supply it.")
        native_arg_name = native_args[wk_arg]
        mapping[native_arg_name] = foreign_arg_name
        logger.debug(f"kwargs translation for %s -> %s",
                     native_arg_name, foreign_arg_name)

    logger.debug("finalized kwargs translation table: %s", mapping)
    return mapping


def assimilate_function(
        foreign_func: Callable,
        kwarg_translate_table: Mapping[NativeArgName, ForeignArgName]
) -> Callable[..., Any]:
    """wrap `foreign_func` such that it accepts arguments via a native API.

    Example:
        >>> from typing import TypeVar
        >>> A = TypeVar("A")
        >>> B = TypeVar("B")
        >>> C = TypeVar("C")

        Native function API may look like:
        >>> def native_function(a: "A", b: "B", c: "C"): ...

        but foreign function looks like this:
        >>> def foreign_function(k1: "C", k2: "A", k3: "B"):
        ...     return {"k1": k1, "k2": k2, "k3": k3}

        and it is established that arguments shall be translated like:
        >>> translation = {
        ...     "a": "k2",  # native arg "a" shall be used for foreign arg "k2"
        ...     "b": "k3",  # native arg "b" shall be used for foreign arg "k3"
        ...     "c": "k1",  # ... you got the gist ...
        ... }

        then the foreign function can be assimilated like this:
        >>> assimilated_func = assimilate_function(foreign_function, translation)

        such that it will accept the native API
        >>> assimilated_func(a="a", b="b", c="c")
        {'k1': 'c', 'k2': 'a', 'k3': 'b'}

    Args:
        foreign_func (Callable): the function which shall be wrapped.
        kwarg_translate_table (Mapping[NativeArgName, ForeignArgName]):
        mapping from native arg name to foreign arg name.

    Returns:
        A callable that can be invoked with the native kwarg names.
    """
    ff_repr = origin_of_func(foreign_func)

    # *** SANITY CHECKS ***
    foreign_parameters = inspect.signature(foreign_func).parameters.values()

    if var_pos_args := [p.name for p in foreign_parameters
                        if p.kind is inspect.Parameter.VAR_POSITIONAL]:
        # VAR_POSITIONAL argument is one like `def func(*args): ...`
        # we cannot handle arbitrary arguments
        raise AssertionError(f"{ff_repr} specifies the variable positional "
                             f"argument {var_pos_args[0]!r}, which "
                             f"cannot be properly translated!")

    if var_keyword_args := [p.name for p in foreign_parameters
                          if p.kind is inspect.Parameter.VAR_KEYWORD]:
        # VAR_KEYWORD argument is one like `def func(**kwargs): ...`
        # we cannot handle arbitrary arguments
        raise AssertionError(f"{ff_repr} specifies a variable keyword "
                             f"argument {var_keyword_args[0]!r}, which cannot "
                             f"be properly translated!")

    if pos_only_args := [p.name for p in foreign_parameters
                         if p.kind is inspect.Parameter.POSITIONAL_ONLY]:
        pos_only_args = ", ".join([repr(p) for p in pos_only_args])
        raise AssertionError(f"{ff_repr} specifies positional only arguments "
                             f"({pos_only_args}), which cannot handled by "
                             f"the current implementation!")

    args_covered_by_native_api = set(kwarg_translate_table.values())
    args_without_default_value = {p.name for p in foreign_parameters
                            if p.default is inspect._empty}
    if orphaned_args := args_without_default_value - args_covered_by_native_api:
        raise AssertionError(f"{ff_repr} specified {", ".join(orphaned_args)} "
                             "arguments which aren't provided via the native "
                             "API!")

    @functools.wraps(foreign_func)
    def _assimilated_foreign_function(**kwargs):
        # pipe native kwarg names to the ones of foreign function
        foreign_kwargs: dict[str, Any] = {}
        for native_arg_name, foreign_arg_name in kwarg_translate_table.items():
            if native_arg_name not in kwargs:
                raise TypeError(f"Missing native kwarg `{native_arg_name}` "
                                f"when invoking {ff_repr} (required by "
                                f"translation table).")
            foreign_kwargs[foreign_arg_name] = kwargs[native_arg_name]
        logger.debug("Invoking foreign %s with kwargs: %s",
                     ff_repr, foreign_kwargs)
        return foreign_func(**foreign_kwargs)

    logger.debug("Integrated foreign function %s with translation table: %s",
                 ff_repr, kwarg_translate_table)
    return _assimilated_foreign_function