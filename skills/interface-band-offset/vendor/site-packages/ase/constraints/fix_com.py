from ase.constraints.constraint import FixConstraint, IndexedConstraint


class FixCom(FixConstraint):
    """Constraint class for fixing the center of mass."""

    index = slice(None)  # all atoms

    def get_removed_dof(self, atoms):
        return 3

    def adjust_positions(self, atoms, new):
        masses = atoms.get_masses()[self.index]
        old_cm = atoms.get_center_of_mass(indices=self.index)
        new_cm = masses @ new[self.index] / masses.sum()
        diff = old_cm - new_cm
        new += diff

    def adjust_momenta(self, atoms, momenta):
        """Adjust momenta so that the center-of-mass velocity is zero."""
        masses = atoms.get_masses()[self.index]
        velocity_com = momenta[self.index].sum(axis=0) / masses.sum()
        momenta[self.index] -= masses[:, None] * velocity_com

    def adjust_forces(self, atoms, forces):
        # Eqs. (3) and (7) in https://doi.org/10.1021/jp9722824
        masses = atoms.get_masses()[self.index]
        lmd = masses @ forces[self.index] / sum(masses**2)
        forces[self.index] -= masses[:, None] * lmd

    def todict(self):
        return {'name': 'FixCom', 'kwargs': {}}


class FixSubsetCom(FixCom, IndexedConstraint):
    """Constraint class for fixing the center of mass of a subset of atoms."""

    def __init__(self, indices):
        super().__init__(indices=indices)

    def todict(self):
        return {
            'name': self.__class__.__name__,
            'kwargs': {'indices': self.index.tolist()},
        }
