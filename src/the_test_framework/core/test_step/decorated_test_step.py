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

from ..exceptions import (
    AbortTestSequence,
    NoTestSystemInstanceFound,
)
from ..test_system import TestSystem


P = ParamSpec("P")
R = TypeVar("R")
P_E = ParamSpec("P_E")
R_E = TypeVar("R_E")


logger = getLogger(__name__)


class _DataTypeWhichWontBeReturnedByAnyTestStep: ...


class DecoratedTestStep(Generic[P, R]):
    name: str

    def __init__(
            self,
            f: Callable[P, R],
            abort_on_error: bool,
            name: str,
    ):
        self._f = f
        self.name = name
        self.abort_on_error = abort_on_error

    def __repr__(self):
        return f"<TestStep {self.name!r}>"

    def _call_as_part_of_a_test_system(self,
                                       test_system: TestSystem,
                                       *args: P.args, **kwargs: P.kwargs) -> R:
        returned = _DataTypeWhichWontBeReturnedByAnyTestStep()
        while True:
            supervision = test_system.test_step_supervisor.supervise_test_step(self)
            try:
                logger.info(f"executing {self}")
                with supervision:
                    returned = self._f(*args, **kwargs)
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

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        try:
            test_system = TestSystem.get_active_instance()
        except NoTestSystemInstanceFound:
            logger.info(f"No instance of TestSystem found! Calling "
                        f"{self.name} outside of TestSystem scope!")
            return self._f(*args, **kwargs)
        else:
            return self._call_as_part_of_a_test_system(test_system, *args, **kwargs)


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
