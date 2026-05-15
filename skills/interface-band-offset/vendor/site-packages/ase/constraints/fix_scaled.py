from __future__ import annotations

import numpy as np

from ase import Atoms
from ase.constraints.constraint import IndexedConstraint


class FixScaled(IndexedConstraint):
    """Fix atoms in the directions of the unit vectors.

    Parameters
    ----------
    a : Sequence[int]
        Indices of atoms to be fixed.
    mask : tuple[bool, bool, bool], default: (True, True, True)
        Cell directions to be fixed. (False: unfixed, True: fixed)
    """

    def __init__(self, a, mask=(True, True, True), cell=None):
        # XXX The unused cell keyword is there for compatibility
        # with old trajectory files.
        super().__init__(indices=a)
        self.mask = np.asarray(mask, bool)

    def get_removed_dof(self, atoms: Atoms):
        return self.mask.sum() * len(self.index)

    def adjust_positions(self, atoms: Atoms, new):
        cell = atoms.cell
        scaled_old = cell.scaled_positions(atoms.positions[self.index])
        scaled_new = cell.scaled_positions(new[self.index])
        scaled_new[:, self.mask] = scaled_old[:, self.mask]
        new[self.index] = cell.cartesian_positions(scaled_new)

    def adjust_forces(self, atoms: Atoms, forces):
        # Forces are covariant to the coordinate transformation,
        # use the inverse transformations
        cell = atoms.cell
        scaled_forces = cell.cartesian_positions(forces[self.index])
        scaled_forces *= -(self.mask - 1)
        forces[self.index] = cell.scaled_positions(scaled_forces)

    def todict(self):
        return {
            'name': 'FixScaled',
            'kwargs': {'a': self.index.tolist(), 'mask': self.mask.tolist()},
        }

    def __repr__(self):
        name = type(self).__name__
        return f'{name}(indices={self.index.tolist()}, {self.mask.tolist()})'
