"""
MonkeyPatching tools

- The Patcher class allow to patch a single instance or a whole class
- unpatched() is an helper which works kind of like super()
- monkey is a context manager which unpatches the class/instance on exit
- decorator allow to patch a class
"""

import inspect
import types
from functools import wraps


class Patcher:
    """ Monkey Patcher. Applies a Monkey Class on a single instance or a whole class """

    def __init__(
        self, patched_object, monkey_class, patch_now=True, unpatch_on_delete=True
    ):

        self.class_patch = inspect.isclass(patched_object)
        self.patched_object = patched_object
        self.monkey_class = monkey_class
        self.unpatch_on_delete = unpatch_on_delete

        self.originals = {}
        if patch_now:
            self.patch()

    def __del__(self):
        if self.unpatch_on_delete:
            self.unpatch()

    def patch(self):
        for method_name, method in inspect.getmembers(
            self.monkey_class, predicate=inspect.isfunction
        ):
            original_method = getattr(self.patched_object, method_name, None)
            self.originals[method_name] = original_method

            if not self.class_patch:
                method = types.MethodType(method, self.patched_object)
            setattr(self.patched_object, method_name, method)
        setattr(self.patched_object, "_originals", self.originals)

    def unpatch(self):
        for method_name, method in self.originals.items():
            if method is None:
                delattr(self.patched_object, method_name)
            else:
                setattr(self.patched_object, method_name, method)


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
            if attrname in self.patched_instance._originals:
                func = self.patched_instance._originals[attrname]
                # Patched instance
                if inspect.ismethod(func):
                    return func
                # Patched class
                else:
                    return types.MethodType(
                        self.patched_instance._originals[attrname],
                        self.patched_instance,
                    )
            return getattr(self.patched_instance, attrname)

    return Wrapper(self)


class monkey:
    """ Monkey patch context manager """

    def __init__(self, patched_object, monkey_cls):
        self.patcher = Patcher(patched_object, monkey_cls)

    def __enter__(self):
        """ Return the Patcher object to allow manual patch / unpatch"""
        return self.patcher

    def __exit__(self, exception_type, value, traceback):
        """ Do nothing, object will be unpatched on self.patch deletion"""
        pass


def decorator(patched_cls, monkey_cls):
    """ Monkey patch decorator factory """

    def inner_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with monkey(patched_cls, monkey_cls):
                return func(*args, **kwargs)

        return wrapper

    return inner_decorator
