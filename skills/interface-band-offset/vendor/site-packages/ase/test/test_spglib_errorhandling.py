import pytest

from ase.utils import OldSpglibError, spglib_new_errorhandling

# Remove all this when we only support new-style spglib exceptions.


def test_none():
    def returns_none():
        return None

    with pytest.raises(OldSpglibError):
        spglib_new_errorhandling(returns_none)()


def test_raises():
    def raises():
        raise RuntimeError('boo')

    with pytest.raises(RuntimeError):
        spglib_new_errorhandling(raises)()
