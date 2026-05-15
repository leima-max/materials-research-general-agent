"""Tests for the `restart` file."""

from pathlib import Path

import pytest

from ase import Atoms
from ase.build import bulk
from ase.calculators.emt import EMT
from ase.optimize import BFGS, RestartError


@pytest.mark.optimize()
def test_path_restart(testdir) -> None:
    """Test if the `Path` object can be passed for `restart`."""
    atoms = bulk('Cu')
    atoms.calc = EMT()
    restart = Path('restart.json')
    with BFGS(atoms, trajectory='opt.traj', restart=restart) as dyn:
        dyn.run()
        assert dyn.todict()['restart'] == 'restart.json'


@pytest.mark.optimize()
def test_none_restart(testdir) -> None:
    """Test if `None` can be passed for `restart`."""
    atoms = bulk('Cu')
    atoms.calc = EMT()
    with BFGS(atoms, trajectory='opt.traj', restart=None) as dyn:
        dyn.run()
        assert dyn.todict()['restart'] is None


@pytest.mark.optimize()
def test_bad_restart(testdir):
    fname = 'tmp.dat'

    with open(fname, 'w') as fd:
        fd.write('hello world\n')

    with pytest.raises(RestartError, match='Could not decode'):
        BFGS(Atoms(), restart=fname)
