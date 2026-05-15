import numpy as np

from ase.constraints.constraint import FixConstraint
from ase.geometry import find_mic


class FixBondLengths(FixConstraint):
    maxiter = 500

    def __init__(
        self, pairs, tolerance=1e-13, bondlengths=None, iterations=None
    ):
        """iterations:
        Ignored"""
        self.pairs = np.asarray(pairs)
        self.tolerance = tolerance
        self.bondlengths = bondlengths

    def get_removed_dof(self, atoms):
        return len(self.pairs)

    def adjust_positions(self, atoms, new):
        old = atoms.positions
        masses = atoms.get_masses()

        if self.bondlengths is None:
            self.bondlengths = self.initialize_bond_lengths(atoms)

        for i in range(self.maxiter):
            converged = True
            for j, ab in enumerate(self.pairs):
                a = ab[0]
                b = ab[1]
                cd = self.bondlengths[j]
                r0 = old[a] - old[b]
                d0, _ = find_mic(r0, atoms.cell, atoms.pbc)
                d1 = new[a] - new[b] - r0 + d0
                m = 1 / (1 / masses[a] + 1 / masses[b])
                x = 0.5 * (cd**2 - np.dot(d1, d1)) / np.dot(d0, d1)
                if abs(x) > self.tolerance:
                    new[a] += x * m / masses[a] * d0
                    new[b] -= x * m / masses[b] * d0
                    converged = False
            if converged:
                break
        else:
            raise RuntimeError('Did not converge')

    def adjust_momenta(self, atoms, p):
        old = atoms.positions
        masses = atoms.get_masses()

        if self.bondlengths is None:
            self.bondlengths = self.initialize_bond_lengths(atoms)

        for i in range(self.maxiter):
            converged = True
            for j, ab in enumerate(self.pairs):
                a = ab[0]
                b = ab[1]
                cd = self.bondlengths[j]
                d = old[a] - old[b]
                d, _ = find_mic(d, atoms.cell, atoms.pbc)
                dv = p[a] / masses[a] - p[b] / masses[b]
                m = 1 / (1 / masses[a] + 1 / masses[b])
                x = -np.dot(dv, d) / cd**2
                if abs(x) > self.tolerance:
                    p[a] += x * m * d
                    p[b] -= x * m * d
                    converged = False
            if converged:
                break
        else:
            raise RuntimeError('Did not converge')

    def adjust_forces(self, atoms, forces):
        self.constraint_forces = -forces
        self.adjust_momenta(atoms, forces)
        self.constraint_forces += forces

    def initialize_bond_lengths(self, atoms):
        bondlengths = np.zeros(len(self.pairs))

        for i, ab in enumerate(self.pairs):
            bondlengths[i] = atoms.get_distance(ab[0], ab[1], mic=True)

        return bondlengths

    def get_indices(self):
        return np.unique(self.pairs.ravel())

    def todict(self):
        return {
            'name': 'FixBondLengths',
            'kwargs': {
                'pairs': self.pairs.tolist(),
                'tolerance': self.tolerance,
            },
        }

    def index_shuffle(self, atoms, ind):
        """Shuffle the indices of the two atoms in this constraint"""
        map = np.zeros(len(atoms), int)
        map[ind] = 1
        n = map.sum()
        map[:] = -1
        map[ind] = range(n)
        pairs = map[self.pairs]
        self.pairs = pairs[(pairs != -1).all(1)]
        if len(self.pairs) == 0:
            raise IndexError('Constraint not part of slice')


def FixBondLength(a1, a2):
    """Fix distance between atoms with indices a1 and a2."""
    return FixBondLengths([(a1, a2)])
