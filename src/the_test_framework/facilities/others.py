from typing import Protocol, Mapping, Any, Callable
import inspect


class HasRepr(Protocol):
    def __repr__(self) -> str: ...


def preview(obj: HasRepr, max_len: int = 79) -> str:
    """shortens a text"""
    text = repr(obj)
    if len(text) > max_len:
        text = text[:max_len - 4] + " ..."
    return text


def enforce_presence_of_class_attributes(cls,
                                         required: Mapping[str, type[Any]]):
    """Ensure required class attributes are defined with the correct types.

    This helper validates that each attribute name in ``attributes`` is
    defined directly on the class (not inherited) and that its value
    matches the expected type. If any attribute is missing or has an
    incorrect type, a ``TypeError`` is raised.

    Args:
       cls: The class object to check.
       required: A mapping of attribute names to their expected
           Python types.

    Raises:
       TypeError: If any required attribute is missing from the class
           or if an attribute has an unexpected type.
    """
    for attribute_name, attribute_type in required.items():
        if attribute_name not in cls.__dict__:
            raise TypeError(f"Missing class attribute `{attribute_name}` of "
                            f"type `{attribute_type}`!")
        if not isinstance(cls.__dict__[attribute_name], attribute_type):
            raise TypeError(f"Class attribute `{attribute_name}` must be "
                            f"of type `{attribute_type}` "
                            f"(got: {type(cls.__dict__[attribute_name])})!")


def origin_of_func(func: Callable) -> str:
    func_name = func.__name__
    file = inspect.getsourcefile(func)
    line_no = inspect.getsourcelines(func)[1]
    return f'{file}:{line_no} {func_name}():'
