"""
MonkeyPatching tools

- The Patcher class allow to patch a single instance or a whole class
- unpatched() is an helper which works kind of like super()
- monkey is a context manager which unpatches the class/instance on exit
- decorator allow to patch a class
"""

import inspect
import types
import contextlib
from functools import wraps


PRIVATE_KEY_PREFIX = "monkey"
MONKEY_DICT_NAME = "_originals"


class MissingValue:
    pass


def patch(patched_object, monkey_class, repatch=False):

    if hasattr(patched_object, MONKEY_DICT_NAME):
        if not repatch:
            return
    else:
        setattr(patched_object, MONKEY_DICT_NAME, {})

    original_dict = getattr(patched_object, MONKEY_DICT_NAME)
    class_patch = inspect.isclass(patched_object)

    for method_name, method in inspect.getmembers(
        monkey_class, predicate=inspect.isfunction
    ):
        original_method = getattr(patched_object, method_name, MissingValue)

        if method_name.startswith("__"):
            key_name = PRIVATE_KEY_PREFIX + method_name
        else:
            key_name = method_name

        original_dict.setdefault(key_name, original_method)

        if not class_patch:
            method = types.MethodType(method, patched_object)
        setattr(patched_object, method_name, method)

    for method_name, method in inspect.getmembers(
        monkey_class, predicate=inspect.isfunction
    ):
        original_method = getattr(patched_object, method_name, MissingValue)

        if method_name.startswith("__"):
            key_name = PRIVATE_KEY_PREFIX + method_name
        else:
            key_name = method_name

        original_dict.setdefault(key_name, original_method)

        if not class_patch:
            method = types.MethodType(method, patched_object)
        setattr(patched_object, method_name, method)


def unpatch(obj):
    original_dict = getattr(obj, MONKEY_DICT_NAME, None)
    if original_dict is None:
        return

    for method_name, method in original_dict.items():
        if method_name.startswith(PRIVATE_KEY_PREFIX + "__"):
            method_name = method_name[: len(PRIVATE_KEY_PREFIX)]
        if method is MissingValue:
            delattr(obj, method_name)
        else:
            setattr(obj, method_name, method)

    delattr(obj, MONKEY_DICT_NAME)


def unpatched():
    """ Helper function to call original methods in Monkey Class definition.
    Acts kind of like like super() with child/parent classes"""
    frame = inspect.stack()[1][0]
    arginfo = inspect.getargvalues(frame)
    self = arginfo.locals[arginfo.args[0]]

    class Wrapper:
        def __init__(self, patched_instance):
            self.patched_instance = patched_instance

        def __getattr__(self, attrname):
            original_dict = getattr(self.patched_instance, MONKEY_DICT_NAME, {})
            if attrname in original_dict:
                func = original_dict[attrname]
                # Patched instance
                if inspect.ismethod(func):
                    return func
                # Patched class
                else:
                    return types.MethodType(
                        original_dict[attrname], self.patched_instance,
                    )
            return getattr(self.patched_instance, attrname)

    return Wrapper(self)


@contextlib.contextmanager
def monkey(patched_object, monkey_cls):
    """Changes working directory and returns to previous on exit."""
    patch(patched_object, monkey_cls)
    try:
        yield
    finally:
        unpatch(patched_object)


def decorator(patched_cls, monkey_cls):
    """ Monkey patch decorator factory """

    def inner_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with monkey(patched_cls, monkey_cls):
                return func(*args, **kwargs)

        return wrapper

    return inner_decorator


class Patcher:
    """ Monkey Patcher. Applies a Monkey Class on a single instance or a whole class """

    def __init__(
        self, patched_object, monkey_class, patch_now=True, unpatch_on_delete=True
    ):
        self.class_patch = inspect.isclass(patched_object)
        self.patched_object = patched_object
        self.monkey_class = monkey_class
        self.unpatch_on_delete = unpatch_on_delete
        if patch_now:
            self.patch()

    def __del__(self):
        if self.unpatch_on_delete:
            self.unpatch()

    def patch(self):
        patch(self.patched_object, self.monkey_class)

    def unpatch(self):
        unpatch(self.patched_object)
