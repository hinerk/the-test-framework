from logging import getLogger
from typing import (
    Callable,
    TypeVar,
    ParamSpec,
    Generic,
    Any,
    TypeGuard,
    overload,
    Literal
)

from ..dtypes import CustomTestResult
from ..exceptions import AbortTestSequence
from ..test_system import TestSystem


P = ParamSpec("P")
R = TypeVar("R")
P_E = ParamSpec("P_E")
R_E = TypeVar("R_E")


logger = getLogger(__name__)


def infer_return_value(returned: Any):
    if isinstance(returned, CustomTestResult):
        return returned.returned
    return returned


class _DataTypeWhichWontBeReturnedByAnyTestStep: ...


class DecoratedTestStep(Generic[P, R]):
    name: str
    ancestry: tuple[str, ...]
    root: bool

    def __init__(self, f: Callable[P, R], abort_on_error: bool, name: str, *ancestors: str):
        self._f = f
        self.name = name
        self.ancestry = ancestors
        self.abort_on_error = abort_on_error

    def __repr__(self):
        return f"<TestStep {self.name!r}>"

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        returned = _DataTypeWhichWontBeReturnedByAnyTestStep()
        test_system = TestSystem.get_active_instance()
        while True:
            supervision = test_system.test_step_supervisor.supervise_test_step(self)
            try:
                logger.info(f"executing {self}")
                with supervision:
                    returned = infer_return_value(self._f(*args, **kwargs))
                supervision.submit_return_value(returned)
                logger.debug(f"{self} completed")
            except Exception as e:
                logger.exception(f"{self} failed with exception!", exc_info=e)

            if test_system.repeat_test_step(self):
                continue

            result = supervision.metadata.test_result
            if not result:
                if self.abort_on_error:
                    raise AbortTestSequence(
                        f"Aborting test sequence since {self} failed! "
                        f"(result: {result!r}")

            if isinstance(returned, _DataTypeWhichWontBeReturnedByAnyTestStep):
                # calming pyright, which would otherwise claim, that returned
                # type is the union of its original type and None
                raise AssertionError("Hinerk obviously isn't as good at his "
                                     "job as he's claiming to be!")
            return returned

    @overload
    def sub_step(
            self, name: str, abort_on_error: Literal[False] = ...
    ) -> "Callable[[Callable[P_E, None]], DecoratedTestStep[P_E, None]]": ...

    @overload
    def sub_step(
            self, name: str, abort_on_error: Literal[True] = ...
    ) -> "Callable[[Callable[P_E, R_E]], DecoratedTestStep[P_E, R_E]]": ...

    def sub_step(
            self, name: str, abort_on_error: bool = True
    ) -> Callable[[Callable[P_E, R_E]], "DecoratedTestStep[P_E, R_E]"]:
        def decorator(f: Callable[P_E, R_E]) -> DecoratedTestStep[P_E, R_E]:
            return DecoratedTestStep(f, abort_on_error, name, *(*self.ancestry, self.name))
        return decorator


def is_decorated_test_step(obj: Any) -> TypeGuard[DecoratedTestStep[Any, Any]]:
    return isinstance(obj, DecoratedTestStep)


@overload
def test_step(
        name: str, abort_on_error: Literal[False]
) -> Callable[[Callable[P, None]], DecoratedTestStep[P, None]]: ...
@overload
def test_step(
        name: str, abort_on_error: Literal[True] = ...
) -> Callable[[Callable[P, R]], DecoratedTestStep[P, R]]: ...
def test_step(
        name: str, abort_on_error: bool = True
) -> Callable[[Callable[P, R]], DecoratedTestStep[P, R]]:
    """decorator for registering test-steps"""
    def decorator(f: Callable[P, R]) -> DecoratedTestStep[P, R]:
        return DecoratedTestStep(f, abort_on_error, name)
    return decorator
