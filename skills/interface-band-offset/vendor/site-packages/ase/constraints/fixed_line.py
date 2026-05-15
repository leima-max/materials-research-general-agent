from ase.constraints.constraint import (
    IndexedConstraint,
    _normalize,
    _projection,
)


class FixedLine(IndexedConstraint):
    """
    Constrain an atom index or a list of atom indices to move on a line only.

    The line is defined by its vector *direction*
    """

    def __init__(self, indices, direction):
        """Constrain chosen atoms.

        Parameters
        ----------
        indices : int or list of int
            Index or indices for atoms that should be constrained
        direction : list of 3 int
            Direction of the vector defining the line

        Examples
        --------
        Fix all Copper atoms to only move in the x-direction:

        >>> from ase.constraints import FixedLine
        >>> c = FixedLine(
        ...     indices=[atom.index for atom in atoms if atom.symbol == 'Cu'],
        ...     direction=[1, 0, 0],
        ... )
        >>> atoms.set_constraint(c)

        or constrain a single atom with the index 0 to move in the z-direction:

        >>> c = FixedLine(indices=0, direction=[0, 0, 1])
        >>> atoms.set_constraint(c)
        """
        super().__init__(indices)
        self.dir = _normalize(direction)

    def adjust_positions(self, atoms, newpositions):
        step = newpositions[self.index] - atoms.positions[self.index]
        projection = _projection(step, self.dir)
        newpositions[self.index] = atoms.positions[self.index] + projection

    def adjust_forces(self, atoms, forces):
        forces[self.index] = _projection(forces[self.index], self.dir)

    def get_removed_dof(self, atoms):
        return 2 * len(self.index)

    def __repr__(self):
        return f'FixedLine(indices={self.index}, {self.dir.tolist()})'

    def todict(self):
        return {
            'name': 'FixedLine',
            'kwargs': {
                'indices': self.index.tolist(),
                'direction': self.dir.tolist(),
            },
        }
