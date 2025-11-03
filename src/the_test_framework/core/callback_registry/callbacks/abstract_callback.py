from abc import ABC, abstractmethod
from logging import getLogger
from typing import (
    Any,
    Callable,
    ClassVar,
)

from the_test_framework.facilities import enforce_presence_of_class_attributes
from .assimilation import (
    create_kwargs_translation_table,
    assimilate_function,
)


logger = getLogger(__name__)


class RegisteredCallback(ABC):
    """Base class for framework-native callback adapters.

    Subclasses define the native call signature in their __call__ method.
    A foreign function is registered once; its signature is introspected and
    integrated via a translation table so internal sites can invoke the wrapper
    with native kwarg names.
    """
    # a description of the callback
    description: ClassVar[str]

    # whether this callback must be registered
    mandatory: ClassVar[bool]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        enforce_presence_of_class_attributes(
            cls, {"description": str, "mandatory": bool})

    def __init__(self):
        self._registered = False
        self._integrated_func: Callable[..., Any] | None = None


    @abstractmethod
    def __call__(self, *args, **kwargs): ...

    def register(self, callback: Callable) -> None:
        """Register a single foreign function for this callback slot.

        Raises:
            RuntimeError: if a function is already registered.
            TypeError:    if the foreign function declares unsupported well-known args.
        """
        if self.registered:
            name = self.__class__.__name__
            raise RuntimeError(f"only one function can be registered as {name}")

        logger.debug(
            "Registering foreign function %s for native %s.__call__",
            getattr(callback, "__qualname__", callback),
            self.__class__.__name__,
        )

        table = create_kwargs_translation_table(self.__call__, callback)
        self._integrated_func = assimilate_function(callback, table)
        self._registered = True

        logger.info(
            "Registered %s for %s with translation %s",
            getattr(callback, "__qualname__", callback),
            self.__class__.__name__,
            table,
        )

    @property
    def registered(self) -> bool:
        """Whether a foreign function has been registered."""
        return self._registered

    def _invoke(self, **kwargs) -> Any:
        """Invoke the registered (integrated) function using native kwarg names.

        Returns:
            The foreign function's return value, or None if nothing is registered.
        """
        if self._integrated_func is None:
            logger.debug(
                "No function registered for %s; returning None.",
                self.__class__.__name__,
            )
            return None
        logger.debug(
            "Invoking %s with native kwargs: %s",
            self.__class__.__name__, kwargs
        )
        return self._integrated_func(**kwargs)