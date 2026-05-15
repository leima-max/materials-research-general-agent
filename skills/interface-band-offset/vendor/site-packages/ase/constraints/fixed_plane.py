from ase.constraints.constraint import (
    IndexedConstraint,
    _normalize,
    _projection,
)


class FixedPlane(IndexedConstraint):
    """
    Constraint object for fixing chosen atoms to only move in a plane.

    The plane is defined by its normal vector *direction*
    """

    def __init__(self, indices, direction):
        """Constrain chosen atoms.

        Parameters
        ----------
        indices : int or list of int
            Index or indices for atoms that should be constrained
        direction : list of 3 int
            Direction of the normal vector

        Examples
        --------
        Fix all Copper atoms to only move in the yz-plane:

        >>> from ase.build import bulk
        >>> from ase.constraints import FixedPlane

        >>> atoms = bulk('Cu', 'fcc', a=3.6)
        >>> c = FixedPlane(
        ...     indices=[atom.index for atom in atoms if atom.symbol == 'Cu'],
        ...     direction=[1, 0, 0],
        ... )
        >>> atoms.set_constraint(c)

        or constrain a single atom with the index 0 to move in the xy-plane:

        >>> c = FixedPlane(indices=0, direction=[0, 0, 1])
        >>> atoms.set_constraint(c)
        """
        super().__init__(indices=indices)
        self.dir = _normalize(direction)

    def adjust_positions(self, atoms, newpositions):
        step = newpositions[self.index] - atoms.positions[self.index]
        newpositions[self.index] -= _projection(step, self.dir)

    def adjust_forces(self, atoms, forces):
        forces[self.index] -= _projection(forces[self.index], self.dir)

    def get_removed_dof(self, atoms):
        return len(self.index)

    def todict(self):
        return {
            'name': 'FixedPlane',
            'kwargs': {
                'indices': self.index.tolist(),
                'direction': self.dir.tolist(),
            },
        }

    def __repr__(self):
        return f'FixedPlane(indices={self.index}, {self.dir.tolist()})'
