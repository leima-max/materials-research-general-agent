from __future__ import annotations

import numpy as np

from ase import Atoms


def slice2enlist(s, n):
    """Convert a slice object into a list of (new, old) tuples."""
    if isinstance(s, slice):
        return enumerate(range(*s.indices(n)))
    return enumerate(s)


def ints2string(x, threshold=None):
    """Convert ndarray of ints to string."""
    if threshold is None or len(x) <= threshold:
        return str(x.tolist())
    return str(x[:threshold].tolist())[:-1] + ', ...]'


def constrained_indices(atoms, only_include=None):
    """Returns a list of indices for the atoms that are constrained
    by a constraint that is applied.  By setting only_include to a
    specific type of constraint you can make it only look for that
    given constraint.
    """
    indices = []
    for constraint in atoms.constraints:
        if only_include is not None:
            if not isinstance(constraint, only_include):
                continue
        indices.extend(np.array(constraint.get_indices()))
    return np.array(np.unique(indices))


def _normalize(direction):
    if np.shape(direction) != (3,):
        raise ValueError('len(direction) is {len(direction)}. Has to be 3')

    direction = np.asarray(direction) / np.linalg.norm(direction)
    return direction


def _projection(vectors, direction):
    dotprods = vectors @ direction
    projection = direction[None, :] * dotprods[:, None]
    return projection


class FixConstraint:
    """Base class for classes that fix one or more atoms in some way."""

    def index_shuffle(self, atoms: Atoms, ind):
        """Change the indices.

        When the ordering of the atoms in the Atoms object changes,
        this method can be called to shuffle the indices of the
        constraints.

        ind -- List or tuple of indices.

        """
        raise NotImplementedError

    def repeat(self, m: int, n: int):
        """basic method to multiply by m, needs to know the length
        of the underlying atoms object for the assignment of
        multiplied constraints to work.
        """
        msg = (
            "Repeat is not compatible with your atoms' constraints."
            ' Use atoms.set_constraint() before calling repeat to '
            'remove your constraints.'
        )
        raise NotImplementedError(msg)

    def get_removed_dof(self, atoms: Atoms):
        """Get number of removed degrees of freedom due to constraint."""
        raise NotImplementedError

    def adjust_positions(self, atoms: Atoms, new):
        """Adjust positions."""

    def adjust_momenta(self, atoms: Atoms, momenta):
        """Adjust momenta."""
        # The default is in identical manner to forces.
        # TODO: The default is however not always reasonable.
        self.adjust_forces(atoms, momenta)

    def adjust_forces(self, atoms: Atoms, forces):
        """Adjust forces."""

    def copy(self):
        """Copy constraint."""
        # Import here to prevent circular imports
        from ase.constraints import dict2constraint

        return dict2constraint(self.todict().copy())

    def todict(self):
        """Convert constraint to dictionary."""


class IndexedConstraint(FixConstraint):
    def __init__(self, indices=None, mask=None):
        """Constrain chosen atoms.

        Parameters
        ----------
        indices : sequence of int
           Indices for those atoms that should be constrained.
        mask : sequence of bool
           One boolean per atom indicating if the atom should be
           constrained or not.
        """

        if mask is not None:
            if indices is not None:
                raise ValueError('Use only one of "indices" and "mask".')
            indices = mask
        indices = np.atleast_1d(indices)
        if np.ndim(indices) > 1:
            raise ValueError(
                'indices has wrong amount of dimensions. '
                f'Got {np.ndim(indices)}, expected ndim <= 1'
            )

        if indices.dtype == bool:
            indices = np.arange(len(indices))[indices]
        elif len(indices) == 0:
            indices = np.empty(0, dtype=int)
        elif not np.issubdtype(indices.dtype, np.integer):
            raise ValueError(
                'Indices must be integers or boolean mask, '
                f'not dtype={indices.dtype}'
            )

        if len(set(indices)) < len(indices):
            raise ValueError(
                'The indices array contains duplicates. '
                'Perhaps you want to specify a mask instead, but '
                'forgot the mask= keyword.'
            )

        self.index = indices

    def index_shuffle(self, atoms, ind):
        # See docstring of superclass
        index = []

        # Resolve negative indices:
        actual_indices = set(np.arange(len(atoms))[self.index])

        for new, old in slice2enlist(ind, len(atoms)):
            if old in actual_indices:
                index.append(new)
        if len(index) == 0:
            raise IndexError('All indices in FixAtoms not part of slice')
        self.index = np.asarray(index, int)
        # XXX make immutable

    def get_indices(self):
        return self.index.copy()

    def repeat(self, m, n):
        i0 = 0
        natoms = 0
        if isinstance(m, int):
            m = (m, m, m)
        index_new = []
        for _ in range(m[2]):
            for _ in range(m[1]):
                for _ in range(m[0]):
                    i1 = i0 + n
                    index_new += [i + natoms for i in self.index]
                    i0 = i1
                    natoms += n
        self.index = np.asarray(index_new, int)
        # XXX make immutable
        return self

    def delete_atoms(self, indices, natoms):
        """Removes atoms from the index array, if present.

        Required for removing atoms with existing constraint.
        """

        i = np.zeros(natoms, int) - 1
        new = np.delete(np.arange(natoms), indices)
        i[new] = np.arange(len(new))
        index = i[self.index]
        self.index = index[index >= 0]
        # XXX make immutable
        if len(self.index) == 0:
            return None
        return self
