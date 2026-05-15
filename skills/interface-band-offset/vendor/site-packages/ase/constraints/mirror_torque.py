import numpy as np

from ase.constraints.constraint import FixConstraint, slice2enlist


class MirrorTorque(FixConstraint):
    """Constraint object for mirroring the torque acting on a dihedral
    angle defined by four atoms.

    This class is designed to find a transition state with the help of a
    single optimization. It can be used if the transition state belongs to a
    cis-trans-isomerization with a change of dihedral angle. First the given
    dihedral angle will be fixed until all other degrees of freedom are
    optimized, then the torque acting on the dihedral angle will be mirrored
    to find the transition state. Transition states in
    dependence of the force can be obtained by stretching the molecule and
    fixing its total length with *FixBondLength* or by using *ExternalForce*
    during the optimization with *MirrorTorque*.

    This constraint can be used to find
    transition states of cis-trans-isomerization.

    a1    a4
    |      |
    a2 __ a3

    Parameters
    ----------
    a1: int
        First atom index.
    a2: int
        Second atom index.
    a3: int
        Third atom index.
    a4: int
        Fourth atom index.
    max_angle: float
        Upper limit of the dihedral angle interval where the transition state
        can be found.
    min_angle: float
        Lower limit of the dihedral angle interval where the transition state
        can be found.
    fmax: float
        Maximum force used for the optimization.

    Notes
    -----
    You can combine this constraint for example with FixBondLength but make
    sure that *MirrorTorque* comes first in the list if there are overlaps
    between atom1-4 and atom5-6:

    >>> from ase.build import bulk

    >>> atoms = bulk('Cu', 'fcc', a=3.6)
    >>> atom1, atom2, atom3, atom4, atom5, atom6 = atoms[:6]
    >>> con1 = MirrorTorque(atom1, atom2, atom3, atom4)
    >>> con2 = FixBondLength(atom5, atom6)
    >>> atoms.set_constraint([con1, con2])

    """

    def __init__(
        self, a1, a2, a3, a4, max_angle=2 * np.pi, min_angle=0.0, fmax=0.1
    ):
        self.indices = [a1, a2, a3, a4]
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.fmax = fmax

    def adjust_positions(self, atoms, new):
        pass

    def adjust_forces(self, atoms, forces):
        angle = atoms.get_dihedral(
            self.indices[0], self.indices[1], self.indices[2], self.indices[3]
        )
        angle *= np.pi / 180.0
        if (angle < self.min_angle) or (angle > self.max_angle):
            # Stop structure optimization
            forces[:] *= 0
            return
        p = atoms.positions[self.indices]
        f = forces[self.indices]

        f0 = (f[1] + f[2]) / 2.0
        ff = f - f0
        p0 = (p[2] + p[1]) / 2.0
        m0 = np.cross(p[1] - p0, ff[1]) / (p[1] - p0).dot(p[1] - p0)
        fff = ff - np.cross(m0, p - p0)
        d1 = np.cross(np.cross(p[1] - p0, p[0] - p[1]), p[1] - p0) / (
            p[1] - p0
        ).dot(p[1] - p0)
        d2 = np.cross(np.cross(p[2] - p0, p[3] - p[2]), p[2] - p0) / (
            p[2] - p0
        ).dot(p[2] - p0)
        omegap1 = (np.cross(d1, fff[0]) / d1.dot(d1)).dot(
            p[1] - p0
        ) / np.linalg.norm(p[1] - p0)
        omegap2 = (np.cross(d2, fff[3]) / d2.dot(d2)).dot(
            p[2] - p0
        ) / np.linalg.norm(p[2] - p0)
        omegap = omegap1 + omegap2
        con_saved = atoms.constraints
        try:
            con = [
                con for con in con_saved if not isinstance(con, MirrorTorque)
            ]
            atoms.set_constraint(con)
            forces_copy = atoms.get_forces()
        finally:
            atoms.set_constraint(con_saved)
        df1 = (
            -1
            / 2.0
            * omegap
            * np.cross(p[1] - p0, d1)
            / np.linalg.norm(p[1] - p0)
        )
        df2 = (
            -1
            / 2.0
            * omegap
            * np.cross(p[2] - p0, d2)
            / np.linalg.norm(p[2] - p0)
        )
        forces_copy[self.indices] += (
            df1,
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            df2,
        )
        # Check if forces would be converged if the dihedral angle with
        # mirrored torque would also be fixed
        if (forces_copy**2).sum(axis=1).max() < self.fmax**2:
            factor = 1.0
        else:
            factor = 0.0
        df1 = (
            -(1 + factor)
            / 2.0
            * omegap
            * np.cross(p[1] - p0, d1)
            / np.linalg.norm(p[1] - p0)
        )
        df2 = (
            -(1 + factor)
            / 2.0
            * omegap
            * np.cross(p[2] - p0, d2)
            / np.linalg.norm(p[2] - p0)
        )
        forces[self.indices] += (df1, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], df2)

    def index_shuffle(self, atoms, ind):
        # See docstring of superclass
        indices = []
        for new, old in slice2enlist(ind, len(atoms)):
            if old in self.indices:
                indices.append(new)
        if len(indices) == 0:
            raise IndexError('All indices in MirrorTorque not part of slice')
        self.indices = np.asarray(indices, int)

    def __repr__(self):
        return 'MirrorTorque(%d, %d, %d, %d, %f, %f, %f)' % (
            self.indices[0],
            self.indices[1],
            self.indices[2],
            self.indices[3],
            self.max_angle,
            self.min_angle,
            self.fmax,
        )

    def todict(self):
        return {
            'name': 'MirrorTorque',
            'kwargs': {
                'a1': self.indices[0],
                'a2': self.indices[1],
                'a3': self.indices[2],
                'a4': self.indices[3],
                'max_angle': self.max_angle,
                'min_angle': self.min_angle,
                'fmax': self.fmax,
            },
        }
