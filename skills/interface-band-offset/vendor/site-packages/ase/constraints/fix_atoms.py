from ase.constraints.constraint import IndexedConstraint, ints2string


class FixAtoms(IndexedConstraint):
    """Fix chosen atoms.

    Examples
    --------
    Fix all Copper atoms:

    >>> from ase.build import bulk

    >>> atoms = bulk('Cu', 'fcc', a=3.6)
    >>> mask = (atoms.symbols == 'Cu')
    >>> c = FixAtoms(mask=mask)
    >>> atoms.set_constraint(c)

    Fix all atoms with z-coordinate less than 1.0 Angstrom:

    >>> c = FixAtoms(mask=atoms.positions[:, 2] < 1.0)
    >>> atoms.set_constraint(c)
    """

    def get_removed_dof(self, atoms):
        return 3 * len(self.index)

    def adjust_positions(self, atoms, new):
        new[self.index] = atoms.positions[self.index]

    def adjust_forces(self, atoms, forces):
        forces[self.index] = 0.0

    def __repr__(self):
        clsname = type(self).__name__
        indices = ints2string(self.index)
        return f'{clsname}(indices={indices})'

    def todict(self):
        return {'name': 'FixAtoms', 'kwargs': {'indices': self.index.tolist()}}
