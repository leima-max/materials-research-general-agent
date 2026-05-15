import numpy as np

from ase.constraints.constraint import FixConstraint


class FixedMode(FixConstraint):
    """Constrain atoms to move along directions orthogonal to
    a given mode only. Initialize with a mode, such as one produced by
    ase.vibrations.Vibrations.get_mode()."""

    def __init__(self, mode):
        mode = np.asarray(mode)
        self.mode = (mode / np.sqrt((mode**2).sum())).reshape(-1)

    def get_removed_dof(self, atoms):
        return len(atoms)

    def adjust_positions(self, atoms, newpositions):
        newpositions = newpositions.ravel()
        oldpositions = atoms.positions.ravel()
        step = newpositions - oldpositions
        newpositions -= self.mode * np.dot(step, self.mode)

    def adjust_forces(self, atoms, forces):
        forces = forces.ravel()
        forces -= self.mode * np.dot(forces, self.mode)

    def index_shuffle(self, atoms, ind):
        eps = 1e-12
        mode = self.mode.reshape(-1, 3)
        excluded = np.ones(len(mode), dtype=bool)
        excluded[ind] = False
        if (abs(mode[excluded]) > eps).any():
            raise IndexError('All nonzero parts of mode not in slice')
        self.mode = mode[ind].ravel()

    def get_indices(self):
        # This function will never properly work because it works on all
        # atoms and it has no idea how to tell how many atoms it is
        # attached to.  If it is being used, surely the user knows
        # everything is being constrained.
        return []

    def todict(self):
        return {'name': 'FixedMode', 'kwargs': {'mode': self.mode.tolist()}}

    def __repr__(self):
        return f'FixedMode({self.mode.tolist()})'
