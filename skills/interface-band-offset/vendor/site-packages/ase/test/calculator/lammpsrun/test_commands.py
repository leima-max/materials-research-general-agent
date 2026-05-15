"""Tests for LAMMPS commands in the ASE LAMMPS calculator."""

import numpy as np
import pytest

from ase import Atoms
from ase.build import bulk


@pytest.mark.calculator_lite()
@pytest.mark.calculator('lammpsrun')
def test_velocity(factory) -> None:
    """Test if `velocity` is recognized by the ASE LAMMPS calculator."""
    atoms: Atoms = bulk('Pt') * 2
    params: dict[str, str | list[str]] = {}
    params['pair_style'] = 'eam'
    params['pair_coeff'] = ['1 1 Pt_u3.eam']
    params['velocity'] = 'all create 300.0 42'
    files = [f'{factory.factory.potentials_path}/Pt_u3.eam']
    with factory.calc(specorder=['Pt'], files=files, **params) as calc:
        atoms.calc = calc

        # As of ASE 3.26.0, we must once run a calculation to `set_atoms` work.
        atoms.get_potential_energy()

        calc.run(set_atoms=True)

        # If `velocity` is recognized, we should get non-zero velocities.
        assert np.all(calc.atoms.get_momenta() != 0.0)
