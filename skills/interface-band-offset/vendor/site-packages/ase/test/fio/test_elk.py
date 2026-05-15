# fmt: off
import io
import re

import numpy as np
import pytest

from ase import Atoms
from ase.build import bulk
from ase.io import write
from ase.io.elk import parse_elk_eigval, read_elk
from ase.units import Bohr, Hartree


def test_elk_in():
    atoms = bulk('Si')
    buf = io.StringIO()
    write(buf, atoms, format='elk-in', parameters={'mockparameter': 17})
    text = buf.getvalue()
    print(text)
    assert 'avec' in text
    assert re.search(r'mockparameter\s+17\n', text, re.M)


elk_in_param_types_out = """tasks
  0
  10

ngridk
  8 8 8

nempty
  8

bfieldc
  0.0 0.0 -0.01

spinpol
  .true.

dft+u
  2  1
  1  2  0.183  0.034911967

mommtfix
  1  1  0.0 0.0 0.0
  1  2  0.0  0.0  0.0

sppath
  '/path/to/species/'

avec
  5.48020576492709 0.00000000000000 0.00000000000000
  0.00000000000000 5.48020576492709 0.00000000000000
  0.00000000000000 0.00000000000000 5.48020576492709

atoms
  2
  'Fe.in' : spfname
  1
  0.00000000000000 0.00000000000000 0.00000000000000 0.0 0.0 0.00000000000000
  'Al.in' : spfname
  1
  0.50000000000000 0.50000000000000 0.50000000000000 0.0 0.0 0.00000000000000
"""


def test_elk_in_param_types():
    """test the elk-in writer with all valid parameter types"""
    params = {'tasks': [[0], [10]], 'ngridk': (8, 8, 8), 'nempty': 8,
              'bfieldc': np.array((0.0, 0.0, -0.01)), 'spinpol': True,
              'sppath': '/path/to/species',
              'dft+u': ((2, 1), (1, 2, 0.183, 0.034911967)),
              'mommtfix': ((1, 1, np.array((0.0, 0.0, 0.0))),
                           (1, 2, 0.0, 0.0, 0.0))}
    atoms = Atoms('FeAl', positions=[[0, 0, 0], [1.45] * 3], cell=[2.9] * 3)
    buf = io.StringIO()
    write(buf, atoms, format='elk-in', parameters=params)
    assert buf.getvalue() == elk_in_param_types_out


mock_elk_eigval_out = """
2 : nkpt
3 : nstsv

1   0.0 0.0 0.0 : k-point, vkl
(state, eigenvalue and occupancy below)
1 -1.0 2.0
2 -0.5 1.5
3  1.0 0.0


2   0.0 0.1 0.2 : k-point, vkl
(state, <blah blah>)
1 1.0 1.9
2 1.1 1.8
3 1.2 1.7
"""


def test_parse_eigval():
    fd = io.StringIO(mock_elk_eigval_out)
    dct = dict(parse_elk_eigval(fd))
    eig = dct['eigenvalues'] / Hartree
    occ = dct['occupations']
    kpts = dct['ibz_kpoints']
    assert len(eig) == 1
    assert len(occ) == 1
    assert pytest.approx(eig[0]) == [[-1.0, -0.5, 1.0], [1.0, 1.1, 1.2]]
    assert pytest.approx(occ[0]) == [[2.0, 1.5, 0.0], [1.9, 1.8, 1.7]]
    assert pytest.approx(kpts) == [[0., 0., 0.], [0.0, 0.1, 0.2]]


elk_geometry_out = """
scale
 1.0

scale1
 1.0

scale2
 1.0

scale3
 1.0

avec
   1.0 0.1 0.2
   0.3 2.0 0.4
   0.5 0.6 3.0

atoms
   1                                    : nspecies
'Si.in'                                 : spfname
   2                                    : natoms; atpos, bfcmt below
    0.1 0.2 0.3    0.0 0.0 0.0
    0.4 0.5 0.6    0.0 0.0 0.0
"""


def test_read_elk():
    atoms = read_elk(io.StringIO(elk_geometry_out))
    assert str(atoms.symbols) == 'Si2'
    assert all(atoms.pbc)
    assert atoms.cell / Bohr == pytest.approx(np.array([
        [1.0, 0.1, 0.2],
        [0.3, 2.0, 0.4],
        [0.5, 0.6, 3.0],
    ]))
    assert atoms.get_scaled_positions() == pytest.approx(np.array([
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
    ]))
