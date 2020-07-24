from monkeypatch import Patcher, monkey, patch, unpatch, unpatched
import monkeypatch
import pytest


def simple_classes():
    class Foo:
        def __init__(self, stringvalue, boolvalue):
            self.stringvalue = stringvalue
            self.boolvalue = boolvalue

        def compute_string(self):
            return f"({self.stringvalue})"

        def compute_bool(self):
            return self.boolvalue

    class PatchedFoo:
        def compute_string(self):
            return unpatched().compute_string() + "_patched"

        def compute_bool(self):
            return not self.boolvalue

        def added_method(self):
            return

    return Foo, PatchedFoo


def test_patch_class_after_construction():

    Foo, PatchedFoo = simple_classes()
    f = Foo("val", True)

    assert f.compute_string() == "(val)"
    assert f.compute_bool()
    with pytest.raises(Exception):
        f.added_method()

    patch(Foo, PatchedFoo)

    assert f.compute_string() == "(val)_patched"
    assert not f.compute_bool()
    f.added_method()


def test_patch_class_before_construction():

    Foo, PatchedFoo = simple_classes()
    patch(Foo, PatchedFoo)

    f = Foo("val", True)

    assert f.compute_string() == "(val)_patched"
    assert not f.compute_bool()
    f.added_method()


def test_unpatch():

    Foo, PatchedFoo = simple_classes()
    f = Foo("val", True)

    patch(Foo, PatchedFoo)

    assert f.compute_string() == "(val)_patched"
    assert not f.compute_bool()
    f.added_method()

    unpatch(Foo)

    assert f.compute_string() == "(val)"
    assert f.compute_bool()
    with pytest.raises(Exception):
        f.added_method()


def test_multiple_call():

    Foo, PatchedFoo = simple_classes()
    f = Foo("val", True)

    patch(Foo, PatchedFoo)
    patch(Foo, PatchedFoo)
    patch(Foo, PatchedFoo)

    assert f.compute_string() == "(val)_patched"
    assert not f.compute_bool()
    f.added_method()

    unpatch(Foo)

    assert f.compute_string() == "(val)"
    assert f.compute_bool()
    with pytest.raises(Exception):
        f.added_method()

    unpatch(Foo)
    assert f.compute_string() == "(val)"
    assert f.compute_bool()
    with pytest.raises(Exception):
        f.added_method()


def test_force_repatch():

    Foo, PatchedFoo = simple_classes()

    class OtherPatch:
        def compute_string(self):
            return "second"

    f = Foo("val", True)

    patch(Foo, PatchedFoo)
    assert f.compute_string() == "(val)_patched"

    patch(Foo, OtherPatch)
    assert f.compute_string() == "(val)_patched"
    patch(Foo, OtherPatch, True)
    assert f.compute_string() == "second"

    unpatch(Foo)

    assert f.compute_string() == "(val)"


def test_patch_instance():

    Foo, PatchedFoo = simple_classes()
    f = Foo("val", True)
    f2 = Foo("val", True)

    patch(f, PatchedFoo)

    assert f.compute_string() == "(val)_patched"
    assert not f.compute_bool()
    f.added_method()

    assert f2.compute_string() == "(val)"
    assert f2.compute_bool()

    with pytest.raises(Exception):
        f2.added_method()

    unpatch(f)

    assert f.compute_string() == "(val)"
    assert f.compute_bool()

    with pytest.raises(Exception):
        f.added_method()


def test_context_manager():

    Foo, PatchedFoo = simple_classes()
    f = Foo("val", True)
    f2 = Foo("val", True)

    with monkey(Foo, PatchedFoo):
        assert f.compute_string() == "(val)_patched"
        assert not f.compute_bool()
        f.added_method()

    assert f.compute_string() == "(val)"
    assert f.compute_bool()
    with pytest.raises(Exception):
        f.added_method()

    with monkey(f2, PatchedFoo):
        assert f2.compute_string() == "(val)_patched"
        assert not f2.compute_bool()
        f2.added_method()

        assert f.compute_string() == "(val)"
        assert f.compute_bool()
        with pytest.raises(Exception):
            f.added_method()

    assert f2.compute_string() == "(val)"
    assert f2.compute_bool()
    with pytest.raises(Exception):
        f2.added_method()


def test_decorator():
    Foo, PatchedFoo = simple_classes()

    f = Foo("val", True)

    @monkeypatch.decorator(Foo, PatchedFoo)
    def check_foo(f):
        assert f.compute_string() == "(val)_patched"
        assert not f.compute_bool()
        f.added_method()

    check_foo(f)

    assert f.compute_string() == "(val)"
    assert f.compute_bool()
    with pytest.raises(Exception):
        f.added_method()


def test_patcher_delay_patch():
    Foo, PatchedFoo = simple_classes()
    f = Foo("Ok", True)

    patcher = Patcher(Foo, PatchedFoo, patch_now=False)

    assert f.compute_string() == "(Ok)"
    assert f.compute_bool()
    with pytest.raises(Exception):
        f.added_method()
    patcher.patch()

    assert f.compute_string() == "(Ok)_patched"
    assert not f.compute_bool()
    f.added_method()


def test_patcher_no_unpatch():
    Foo, PatchedFoo = simple_classes()
    f = Foo("Ko", True)

    def func1():
        Patcher(f, PatchedFoo)

    def func2():
        Patcher(f, PatchedFoo, unpatch_on_delete=False)

    func1()
    assert f.compute_string() == "(Ko)"
    assert f.compute_bool()
    with pytest.raises(Exception):
        f.added_method()

    func2()
    assert f.compute_string() == "(Ko)_patched"
    assert not f.compute_bool()
    f.added_method()

    monkeypatch.unpatch(f)
    assert f.compute_string() == "(Ko)"
    assert f.compute_bool()
    with pytest.raises(Exception):
        f.added_method()

