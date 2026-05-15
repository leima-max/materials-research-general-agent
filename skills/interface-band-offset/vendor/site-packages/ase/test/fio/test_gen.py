# fmt: off
"""Tests for GEN format"""
import numpy as np
import pytest

from ase import Atoms
from ase.io import write
from ase.io.gen import read_gen, write_gen


@pytest.mark.parametrize("fractional", [False, True])
@pytest.mark.parametrize("cell", [None, [[2.5, 0, 0], [2, 4, 0], [1, 2, 3]]])
@pytest.mark.parametrize("pbc", [False, [True, True, False], True])
@pytest.mark.parametrize("write_format", ["gen", "dftb"])
def test_gen(write_format: str, cell: list, pbc: bool, fractional: bool):
    """Test for `write_gen` and `read_gen`"""
    if fractional and cell is None:
        # fractional==True is invalid when cell is None.
        return

    positions = [[-0.1, 1.2, 0.3], [-0.1, 0.0, 0.2], [0.4, -0.9, 0.0]]
    atoms = Atoms(symbols="OCO", pbc=pbc, cell=cell, positions=positions)
    fname = "test.gen"
    write(fname, atoms, format=write_format, fractional=fractional)
    atoms_new = read_gen(fname)

    assert np.all(atoms_new.numbers == atoms.numbers)
    assert np.allclose(atoms_new.positions, atoms.positions)

    if atoms.pbc.any() or fractional:
        assert np.all(atoms_new.pbc)
        assert np.allclose(atoms_new.cell, atoms.cell)
    else:
        assert np.all(~atoms_new.pbc)
        assert np.allclose(atoms_new.cell, 0.0)


def test_gen_tags():
    """Test GEN format with tags for atomic species"""
    atoms = Atoms("H2", positions=[[0, 0, 0], [1, 0, 0]], tags=[1, 2])
    fname = "test_tags.gen"
    write_gen(fname, atoms, with_tags=True)

    atoms_new = read_gen(fname)
    np.testing.assert_equal(atoms_new.get_chemical_symbols(), ["H", "H"])
    np.testing.assert_equal(atoms_new.get_tags(), [1, 2])
    np.testing.assert_allclose(atoms_new.positions, atoms.positions)


def test_gen_tags_repeated():
    """Test GEN format with repeated tags (same element, same tag)"""
    atoms = Atoms("H4",
                  positions=[[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]],
                  tags=[1, 1, 2, 2])
    fname = "test_tags_repeated.gen"
    write_gen(fname, atoms, with_tags=True)

    atoms_new = read_gen(fname)
    np.testing.assert_equal(atoms_new.get_chemical_symbols(),
                            ["H", "H", "H", "H"])
    np.testing.assert_equal(atoms_new.get_tags(), [1, 1, 2, 2])
    np.testing.assert_allclose(atoms_new.positions, atoms.positions)


def test_gen_tags_multiple_elements():
    """Test GEN format with tags for multiple different elements"""
    atoms = Atoms("H2O2",
                  positions=[[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]],
                  tags=[1, 2, 1, 2])
    fname = "test_tags_multi_elem.gen"
    write_gen(fname, atoms, with_tags=True)

    atoms_new = read_gen(fname)
    np.testing.assert_equal(atoms_new.get_chemical_symbols(),
                            ["H", "H", "O", "O"])
    np.testing.assert_equal(atoms_new.get_tags(), [1, 2, 1, 2])
    np.testing.assert_allclose(atoms_new.positions, atoms.positions)


def test_gen_multiple():
    """Test multiple images (not supported by the format) that should fail"""
    atoms = Atoms("H2")

    with pytest.raises(ValueError):
        write("test.gen", [atoms, atoms])
