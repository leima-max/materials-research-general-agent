import numpy as np

from ase.constraints.constraint import FixConstraint, slice2enlist


class ExternalForce(FixConstraint):
    """Constraint object for pulling two atoms apart by an external force.

    You can combine this constraint for example with FixBondLength but make
    sure that *ExternalForce* comes first in the list if there are overlaps
    between atom1-2 and atom3-4:

    >>> from ase.build import bulk

    >>> atoms = bulk('Cu', 'fcc', a=3.6)
    >>> atom1, atom2, atom3, atom4 = atoms[:4]
    >>> fext = 1.0
    >>> con1 = ExternalForce(atom1, atom2, f_ext)
    >>> con2 = FixBondLength(atom3, atom4)
    >>> atoms.set_constraint([con1, con2])

    see ase/test/external_force.py"""

    def __init__(self, a1, a2, f_ext):
        self.indices = [a1, a2]
        self.external_force = f_ext

    def get_removed_dof(self, atoms):
        return 0

    def adjust_positions(self, atoms, new):
        pass

    def adjust_forces(self, atoms, forces):
        dist = np.subtract.reduce(atoms.positions[self.indices])
        force = self.external_force * dist / np.linalg.norm(dist)
        forces[self.indices] += (force, -force)

    def adjust_potential_energy(self, atoms):
        dist = np.subtract.reduce(atoms.positions[self.indices])
        return -np.linalg.norm(dist) * self.external_force

    def index_shuffle(self, atoms, ind):
        """Shuffle the indices of the two atoms in this constraint"""
        newa = [-1, -1]  # Signal error
        for new, old in slice2enlist(ind, len(atoms)):
            for i, a in enumerate(self.indices):
                if old == a:
                    newa[i] = new
        if newa[0] == -1 or newa[1] == -1:
            raise IndexError('Constraint not part of slice')
        self.indices = newa

    def __repr__(self):
        return 'ExternalForce(%d, %d, %f)' % (
            self.indices[0],
            self.indices[1],
            self.external_force,
        )

    def todict(self):
        return {
            'name': 'ExternalForce',
            'kwargs': {
                'a1': self.indices[0],
                'a2': self.indices[1],
                'f_ext': self.external_force,
            },
        }
