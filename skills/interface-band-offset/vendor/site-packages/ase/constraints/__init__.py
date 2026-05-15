"""Constraints"""

from copy import deepcopy
from typing import Any

from ase.constraints.constraint import (
    FixConstraint,
    constrained_indices,
)
from ase.constraints.external_force import ExternalForce
from ase.constraints.fix_atoms import FixAtoms
from ase.constraints.fix_bond_lengths import FixBondLength, FixBondLengths
from ase.constraints.fix_cartesian import FixCartesian
from ase.constraints.fix_com import FixCom, FixSubsetCom
from ase.constraints.fix_internals import FixInternals
from ase.constraints.fix_linear_triatomic import FixLinearTriatomic
from ase.constraints.fix_parametric_relations import (
    FixCartesianParametricRelations,
    FixParametricRelations,
    FixScaledParametricRelations,
)
from ase.constraints.fix_scaled import FixScaled
from ase.constraints.fix_symmetry import FixSymmetry
from ase.constraints.fixed_line import FixedLine
from ase.constraints.fixed_mode import FixedMode
from ase.constraints.fixed_plane import FixedPlane
from ase.constraints.hookean import Hookean
from ase.constraints.mirror_force import MirrorForce
from ase.constraints.mirror_torque import MirrorTorque

__all__ = [
    'FixCartesian',
    'FixBondLength',
    'FixedMode',
    'FixAtoms',
    'FixScaled',
    'FixCom',
    'FixSubsetCom',
    'FixedPlane',
    'FixConstraint',
    'FixedLine',
    'FixBondLengths',
    'FixLinearTriatomic',
    'FixInternals',
    'Hookean',
    'ExternalForce',
    'MirrorForce',
    'MirrorTorque',
    'FixParametricRelations',
    'FixScaledParametricRelations',
    'FixCartesianParametricRelations',
    'FixSymmetry',
    'constrained_indices',
]


def dict2constraint(dct: dict[str, Any]) -> FixConstraint:
    """Convert dictionary to ASE `FixConstraint` object."""
    if dct['name'] not in __all__:
        raise ValueError
    # address backward-compatibility breaking between ASE 3.22.0 and 3.23.0
    # https://gitlab.com/ase/ase/-/merge_requests/3786
    if dct['name'] in {'FixedLine', 'FixedPlane'} and 'a' in dct['kwargs']:
        dct = deepcopy(dct)
        dct['kwargs']['indices'] = dct['kwargs'].pop('a')
    return globals()[dct['name']](**dct['kwargs'])
