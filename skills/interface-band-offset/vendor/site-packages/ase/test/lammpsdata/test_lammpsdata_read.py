"""Tests for `read_lammps_data`."""

from io import StringIO

import numpy as np

from ase.io.lammpsdata import read_lammps_data

from .comparison import compare_with_pytest_approx
from .parse_lammps_data_file import lammpsdata_file_extracted_sections

# Relative tolerance for comparing floats with pytest.approx
REL_TOL = 1e-2


def test_lammpsdata_read(lammpsdata_file_path):
    """Test if `Atoms` can be created properly with `read_lammps_data`.

    This checks if the cell, mass, positions, and velocities match the
    values that are parsed directly from the data file.

    NOTE: This test currently only works when using a lammps data file
    containing a single atomic species
    """
    atoms = read_lammps_data(
        lammpsdata_file_path,
        read_image_flags=False,
        units='metal',
    )

    expected_values = lammpsdata_file_extracted_sections(lammpsdata_file_path)

    # Check cell was read in correctly
    cell_read_in = atoms.get_cell()
    cell_expected = expected_values['cell']
    compare_with_pytest_approx(cell_read_in, cell_expected, REL_TOL)

    # Check masses were read in correctly
    masses_read_in = atoms.get_masses()
    masses_expected = [expected_values['mass']] * len(
        expected_values['positions']
    )
    compare_with_pytest_approx(masses_read_in, masses_expected, REL_TOL)

    # Check positions were read in correctly
    positions_read_in = atoms.get_positions()
    positions_expected = expected_values['positions']
    compare_with_pytest_approx(positions_read_in, positions_expected, REL_TOL)

    # Check velocities were read in correctly
    velocities_read_in = atoms.get_velocities()
    velocities_expected = expected_values['velocities']
    compare_with_pytest_approx(velocities_read_in, velocities_expected, REL_TOL)

    # TODO: Also check charges, travels, molecule id, bonds, and angles


BUF_GENERAL_TRICLINIC_BOX = r"""
(written by ASE)

1 atoms
1 atom types

 -1.0  2.0  3.0 avec
  1.0 -2.0  3.0 bvec
  1.0  2.0 -3.0 cvec
  0.0  0.0  0.0 abc origin

Masses

     1      63.545999983653154 # Cu

Atoms # atomic

1 1 0 0 0 0 0 0

Velocities

1 0 0 0
"""


def test_general_triclinic_box() -> None:
    """Test if a general triclinic box can be parsed."""
    atoms = read_lammps_data(StringIO(BUF_GENERAL_TRICLINIC_BOX))
    np.testing.assert_allclose(atoms.cell, [[-1, 2, 3], [1, -2, 3], [1, 2, -3]])


BUF_ATOM_TYPE_LABELS = r"""
(written by ASE)

1 atoms
1 atom types

0 1 xlo xhi
0 1 ylo yhi
0 1 zlo zhi

Atom Type Labels

1 Cu

Masses

1 63.54599998365315

Atoms # atomic

1 Cu 0 0 0 0 0 0

Velocities

1 0 0 0
"""


def test_atom_type_labels() -> None:
    """Test if a LAMMPS data file with Atom Type Labels can be parsed."""
    read_lammps_data(StringIO(BUF_ATOM_TYPE_LABELS))
