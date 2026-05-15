from __future__ import annotations

import numpy as np

from ase import Atoms
from ase.constraints.constraint import IndexedConstraint


class FixCartesian(IndexedConstraint):
    """Fix atoms in the directions of the cartesian coordinates.

    Parameters
    ----------
    a : Sequence[int]
        Indices of atoms to be fixed.
    mask : tuple[bool, bool, bool], default: (True, True, True)
        Cartesian directions to be fixed. (False: unfixed, True: fixed)
    """

    def __init__(self, a, mask=(True, True, True)):
        super().__init__(indices=a)
        self.mask = np.asarray(mask, bool)

    def get_removed_dof(self, atoms: Atoms):
        return self.mask.sum() * len(self.index)

    def adjust_positions(self, atoms: Atoms, new):
        new[self.index] = np.where(
            self.mask[None, :],
            atoms.positions[self.index],
            new[self.index],
        )

    def adjust_forces(self, atoms: Atoms, forces):
        forces[self.index] *= ~self.mask[None, :]

    def todict(self):
        return {
            'name': 'FixCartesian',
            'kwargs': {'a': self.index.tolist(), 'mask': self.mask.tolist()},
        }

    def __repr__(self):
        name = type(self).__name__
        return f'{name}(indices={self.index.tolist()}, {self.mask.tolist()})'
