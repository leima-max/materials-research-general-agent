from __future__ import annotations

from typing import Sequence
from warnings import warn

import numpy as np

from ase.constraints.constraint import FixConstraint, slice2enlist
from ase.geometry import (
    conditional_find_mic,
    get_angles,
    get_angles_derivatives,
    get_dihedrals,
    get_dihedrals_derivatives,
    get_distances_derivatives,
)


# TODO: Better interface might be to use dictionaries in place of very
# nested lists/tuples
class FixInternals(FixConstraint):
    """Constraint object for fixing multiple internal coordinates.

    Allows fixing bonds, angles, dihedrals as well as linear combinations
    of bonds (bondcombos).

    Please provide angular units in degrees using `angles_deg` and
    `dihedrals_deg`.
    Fixing planar angles is not supported at the moment.
    """

    def __init__(
        self,
        bonds=None,
        angles=None,
        dihedrals=None,
        angles_deg=None,
        dihedrals_deg=None,
        bondcombos=None,
        mic=False,
        epsilon=1.0e-7,
    ):
        """
        A constrained internal coordinate is defined as a nested list:
        '[value, [atom indices]]'. The constraint is initialized with a list of
        constrained internal coordinates, i.e. '[[value, [atom indices]], ...]'.
        If 'value' is None, the current value of the coordinate is constrained.

        Parameters
        ----------
        bonds: nested python list, optional
            List with targetvalue and atom indices defining the fixed bonds,
            i.e. [[targetvalue, [index0, index1]], ...]

        angles_deg: nested python list, optional
            List with targetvalue and atom indices defining the fixedangles,
            i.e. [[targetvalue, [index0, index1, index3]], ...]

        dihedrals_deg: nested python list, optional
            List with targetvalue and atom indices defining the fixed dihedrals,
            i.e. [[targetvalue, [index0, index1, index3]], ...]

        bondcombos: nested python list, optional
            List with targetvalue, atom indices and linear coefficient defining
            the fixed linear combination of bonds,
            i.e. [[targetvalue, [[index0, index1, coefficient_for_bond],
            [index1, index2, coefficient_for_bond]]], ...]

        mic: bool, optional, default: False
            Minimum image convention.

        epsilon: float, optional, default: 1e-7
            Convergence criterion.
        """
        warn_msg = 'Please specify {} in degrees using the {} argument.'
        if angles:
            warn(warn_msg.format('angles', 'angle_deg'), FutureWarning)
            angles = np.asarray(angles)
            angles[:, 0] = angles[:, 0] / np.pi * 180
            angles = angles.tolist()
        else:
            angles = angles_deg
        if dihedrals:
            warn(warn_msg.format('dihedrals', 'dihedrals_deg'), FutureWarning)
            dihedrals = np.asarray(dihedrals)
            dihedrals[:, 0] = dihedrals[:, 0] / np.pi * 180
            dihedrals = dihedrals.tolist()
        else:
            dihedrals = dihedrals_deg

        self.bonds = bonds or []
        self.angles = angles or []
        self.dihedrals = dihedrals or []
        self.bondcombos = bondcombos or []
        self.mic = mic
        self.epsilon = epsilon

        self.n = (
            len(self.bonds)
            + len(self.angles)
            + len(self.dihedrals)
            + len(self.bondcombos)
        )

        # Initialize these at run-time:
        self.constraints = []
        self.initialized = False

    def get_removed_dof(self, atoms):
        return self.n

    def initialize(self, atoms):
        if self.initialized:
            return
        masses = np.repeat(atoms.get_masses(), 3)
        cell = None
        pbc = None
        if self.mic:
            cell = atoms.cell
            pbc = atoms.pbc
        self.constraints = []
        for data, ConstrClass in [
            (self.bonds, self.FixBondLengthAlt),
            (self.angles, self.FixAngle),
            (self.dihedrals, self.FixDihedral),
            (self.bondcombos, self.FixBondCombo),
        ]:
            for datum in data:
                targetvalue = datum[0]
                if targetvalue is None:  # set to current value
                    targetvalue = ConstrClass.get_value(
                        atoms, datum[1], self.mic
                    )
                constr = ConstrClass(targetvalue, datum[1], masses, cell, pbc)
                self.constraints.append(constr)
        self.initialized = True

    @staticmethod
    def get_bondcombo(atoms, indices, mic=False):
        """Convenience function to return the value of the bondcombo coordinate
        (linear combination of bond lengths) for the given Atoms object 'atoms'.
        Example: Get the current value of the linear combination of two bond
        lengths defined as `bondcombo = [[0, 1, 1.0], [2, 3, -1.0]]`."""
        c = sum(df[2] * atoms.get_distance(*df[:2], mic=mic) for df in indices)
        return c

    def get_subconstraint(self, atoms, definition):
        """Get pointer to a specific subconstraint.
        Identification by its definition via indices (and coefficients)."""
        self.initialize(atoms)
        for subconstr in self.constraints:
            if isinstance(definition[0], Sequence):  # Combo constraint
                defin = [
                    d + [c] for d, c in zip(subconstr.indices, subconstr.coefs)
                ]
                if defin == definition:
                    return subconstr
            else:  # identify primitive constraints by their indices
                if subconstr.indices == [definition]:
                    return subconstr
        raise ValueError('Given `definition` not found on Atoms object.')

    def shuffle_definitions(self, shuffle_dic, internal_type):
        dfns = []  # definitions
        for dfn in internal_type:  # e.g. for bond in self.bonds
            append = True
            new_dfn = [dfn[0], list(dfn[1])]
            for old in dfn[1]:
                if old in shuffle_dic:
                    new_dfn[1][dfn[1].index(old)] = shuffle_dic[old]
                else:
                    append = False
                    break
            if append:
                dfns.append(new_dfn)
        return dfns

    def shuffle_combos(self, shuffle_dic, internal_type):
        dfns = []  # definitions
        for dfn in internal_type:  # i.e. for bondcombo in self.bondcombos
            append = True
            all_indices = [idx[0:-1] for idx in dfn[1]]
            new_dfn = [dfn[0], list(dfn[1])]
            for i, indices in enumerate(all_indices):
                for old in indices:
                    if old in shuffle_dic:
                        new_dfn[1][i][indices.index(old)] = shuffle_dic[old]
                    else:
                        append = False
                        break
                if not append:
                    break
            if append:
                dfns.append(new_dfn)
        return dfns

    def index_shuffle(self, atoms, ind):
        # See docstring of superclass
        self.initialize(atoms)
        shuffle_dic = dict(slice2enlist(ind, len(atoms)))
        shuffle_dic = {old: new for new, old in shuffle_dic.items()}
        self.bonds = self.shuffle_definitions(shuffle_dic, self.bonds)
        self.angles = self.shuffle_definitions(shuffle_dic, self.angles)
        self.dihedrals = self.shuffle_definitions(shuffle_dic, self.dihedrals)
        self.bondcombos = self.shuffle_combos(shuffle_dic, self.bondcombos)
        self.initialized = False
        self.initialize(atoms)
        if len(self.constraints) == 0:
            raise IndexError('Constraint not part of slice')

    def get_indices(self):
        cons = []
        for dfn in self.bonds + self.dihedrals + self.angles:
            cons.extend(dfn[1])
        for dfn in self.bondcombos:
            for partial_dfn in dfn[1]:
                cons.extend(partial_dfn[0:-1])  # last index is the coefficient
        return list(set(cons))

    def todict(self):
        return {
            'name': 'FixInternals',
            'kwargs': {
                'bonds': self.bonds,
                'angles_deg': self.angles,
                'dihedrals_deg': self.dihedrals,
                'bondcombos': self.bondcombos,
                'mic': self.mic,
                'epsilon': self.epsilon,
            },
        }

    def adjust_positions(self, atoms, newpos):
        self.initialize(atoms)
        for constraint in self.constraints:
            constraint.setup_jacobian(atoms.positions)
        for _ in range(50):
            maxerr = 0.0
            for constraint in self.constraints:
                constraint.adjust_positions(atoms.positions, newpos)
                maxerr = max(abs(constraint.sigma), maxerr)
            if maxerr < self.epsilon:
                return
        msg = 'FixInternals.adjust_positions did not converge.'
        if any(
            constr.targetvalue > 175.0 or constr.targetvalue < 5.0
            for constr in self.constraints
            if isinstance(constr, self.FixAngle)
        ):
            msg += (
                ' This may be caused by an almost planar angle.'
                ' Support for planar angles would require the'
                ' implementation of ghost, i.e. dummy, atoms.'
                ' See issue #868.'
            )
        raise ValueError(msg)

    def adjust_forces(self, atoms, forces):
        """Project out translations and rotations and all other constraints"""
        self.initialize(atoms)
        positions = atoms.positions
        N = len(forces)
        list2_constraints = list(np.zeros((6, N, 3)))
        tx, ty, tz, rx, ry, rz = list2_constraints

        list_constraints = [r.ravel() for r in list2_constraints]

        tx[:, 0] = 1.0
        ty[:, 1] = 1.0
        tz[:, 2] = 1.0
        ff = forces.ravel()

        # Calculate the center of mass
        center = positions.sum(axis=0) / N

        rx[:, 1] = -(positions[:, 2] - center[2])
        rx[:, 2] = positions[:, 1] - center[1]
        ry[:, 0] = positions[:, 2] - center[2]
        ry[:, 2] = -(positions[:, 0] - center[0])
        rz[:, 0] = -(positions[:, 1] - center[1])
        rz[:, 1] = positions[:, 0] - center[0]

        # Normalizing transl., rotat. constraints
        for r in list2_constraints:
            r /= np.linalg.norm(r.ravel())

        # Add all angle, etc. constraint vectors
        for constraint in self.constraints:
            constraint.setup_jacobian(positions)
            constraint.adjust_forces(positions, forces)
            list_constraints.insert(0, constraint.jacobian)
        # QR DECOMPOSITION - GRAM SCHMIDT

        list_constraints = [r.ravel() for r in list_constraints]
        aa = np.column_stack(list_constraints)
        (aa, _bb) = np.linalg.qr(aa)
        # Projection
        hh = []
        for i, constraint in enumerate(self.constraints):
            hh.append(aa[:, i] * np.vstack(aa[:, i]))

        txx = aa[:, self.n] * np.vstack(aa[:, self.n])
        tyy = aa[:, self.n + 1] * np.vstack(aa[:, self.n + 1])
        tzz = aa[:, self.n + 2] * np.vstack(aa[:, self.n + 2])
        rxx = aa[:, self.n + 3] * np.vstack(aa[:, self.n + 3])
        ryy = aa[:, self.n + 4] * np.vstack(aa[:, self.n + 4])
        rzz = aa[:, self.n + 5] * np.vstack(aa[:, self.n + 5])
        T = txx + tyy + tzz + rxx + ryy + rzz
        for vec in hh:
            T += vec
        ff = np.dot(T, np.vstack(ff))
        forces[:, :] -= np.dot(T, np.vstack(ff)).reshape(-1, 3)

    def __repr__(self):
        constraints = [repr(constr) for constr in self.constraints]
        return f'FixInternals(_copy_init={constraints}, epsilon={self.epsilon})'

    # Classes for internal use in FixInternals
    class FixInternalsBase:
        """Base class for subclasses of FixInternals."""

        def __init__(self, targetvalue, indices, masses, cell, pbc):
            self.targetvalue = targetvalue  # constant target value
            self.indices = [defin[0:-1] for defin in indices]  # indices, defs
            self.coefs = np.asarray([defin[-1] for defin in indices])
            self.masses = masses
            self.jacobian = []  # geometric Jacobian matrix, Wilson B-matrix
            self.sigma = 1.0  # difference between current and target value
            self.projected_force = None  # helps optimizers scan along constr.
            self.cell = cell
            self.pbc = pbc

        def finalize_jacobian(self, pos, n_internals, n, derivs):
            """Populate jacobian with derivatives for `n_internals` defined
            internals. n = 2 (bonds), 3 (angles), 4 (dihedrals)."""
            jacobian = np.zeros((n_internals, *pos.shape))
            for i, idx in enumerate(self.indices):
                for j in range(n):
                    jacobian[i, idx[j]] = derivs[i, j]
            jacobian = jacobian.reshape((n_internals, 3 * len(pos)))
            return self.coefs @ jacobian

        def finalize_positions(self, newpos):
            jacobian = self.jacobian / self.masses
            lamda = -self.sigma / (jacobian @ self.get_jacobian(newpos))
            dnewpos = lamda * jacobian
            newpos += dnewpos.reshape(newpos.shape)

        def adjust_forces(self, positions, forces):
            self.projected_forces = (
                self.jacobian @ forces.ravel()
            ) * self.jacobian
            self.jacobian /= np.linalg.norm(self.jacobian)

    class FixBondCombo(FixInternalsBase):
        """Constraint subobject for fixing linear combination of bond lengths
        within FixInternals.

        sum_i( coef_i * bond_length_i ) = constant
        """

        def get_jacobian(self, pos):
            bondvectors = [pos[k] - pos[h] for h, k in self.indices]
            derivs = get_distances_derivatives(
                bondvectors, cell=self.cell, pbc=self.pbc
            )
            return self.finalize_jacobian(pos, len(bondvectors), 2, derivs)

        def setup_jacobian(self, pos):
            self.jacobian = self.get_jacobian(pos)

        def adjust_positions(self, oldpos, newpos):
            bondvectors = [newpos[k] - newpos[h] for h, k in self.indices]
            (_,), (dists,) = conditional_find_mic(
                [bondvectors], cell=self.cell, pbc=self.pbc
            )
            value = self.coefs @ dists
            self.sigma = value - self.targetvalue
            self.finalize_positions(newpos)

        @staticmethod
        def get_value(atoms, indices, mic):
            return FixInternals.get_bondcombo(atoms, indices, mic)

        def __repr__(self):
            return (
                f'FixBondCombo({self.targetvalue}, {self.indices}, '
                '{self.coefs})'
            )

    class FixBondLengthAlt(FixBondCombo):
        """Constraint subobject for fixing bond length within FixInternals.
        Fix distance between atoms with indices a1, a2."""

        def __init__(self, targetvalue, indices, masses, cell, pbc):
            if targetvalue <= 0.0:
                raise ZeroDivisionError('Invalid targetvalue for fixed bond')
            indices = [list(indices) + [1.0]]  # bond definition with coef 1.
            super().__init__(targetvalue, indices, masses, cell=cell, pbc=pbc)

        @staticmethod
        def get_value(atoms, indices, mic):
            return atoms.get_distance(*indices, mic=mic)

        def __repr__(self):
            return f'FixBondLengthAlt({self.targetvalue}, {self.indices})'

    class FixAngle(FixInternalsBase):
        """Constraint subobject for fixing an angle within FixInternals.

        Convergence is potentially problematic for angles very close to
        0 or 180 degrees as there is a singularity in the Cartesian derivative.
        Fixing planar angles is therefore not supported at the moment.
        """

        def __init__(self, targetvalue, indices, masses, cell, pbc):
            """Fix atom movement to construct a constant angle."""
            if targetvalue <= 0.0 or targetvalue >= 180.0:
                raise ZeroDivisionError('Invalid targetvalue for fixed angle')
            indices = [list(indices) + [1.0]]  # angle definition with coef 1.
            super().__init__(targetvalue, indices, masses, cell=cell, pbc=pbc)

        def gather_vectors(self, pos):
            v0 = [pos[h] - pos[k] for h, k, l in self.indices]
            v1 = [pos[l] - pos[k] for h, k, l in self.indices]
            return v0, v1

        def get_jacobian(self, pos):
            v0, v1 = self.gather_vectors(pos)
            derivs = get_angles_derivatives(
                v0, v1, cell=self.cell, pbc=self.pbc
            )
            return self.finalize_jacobian(pos, len(v0), 3, derivs)

        def setup_jacobian(self, pos):
            self.jacobian = self.get_jacobian(pos)

        def adjust_positions(self, oldpos, newpos):
            v0, v1 = self.gather_vectors(newpos)
            value = get_angles(v0, v1, cell=self.cell, pbc=self.pbc)
            self.sigma = value - self.targetvalue
            self.finalize_positions(newpos)

        @staticmethod
        def get_value(atoms, indices, mic):
            return atoms.get_angle(*indices, mic=mic)

        def __repr__(self):
            return f'FixAngle({self.targetvalue}, {self.indices})'

    class FixDihedral(FixInternalsBase):
        """Constraint subobject for fixing a dihedral angle within FixInternals.

        A dihedral becomes undefined when at least one of the inner two angles
        becomes planar. Make sure to avoid this situation.
        """

        def __init__(self, targetvalue, indices, masses, cell, pbc):
            indices = [list(indices) + [1.0]]  # dihedral def. with coef 1.
            super().__init__(targetvalue, indices, masses, cell=cell, pbc=pbc)

        def gather_vectors(self, pos):
            v0 = [pos[k] - pos[h] for h, k, l, m in self.indices]
            v1 = [pos[l] - pos[k] for h, k, l, m in self.indices]
            v2 = [pos[m] - pos[l] for h, k, l, m in self.indices]
            return v0, v1, v2

        def get_jacobian(self, pos):
            v0, v1, v2 = self.gather_vectors(pos)
            derivs = get_dihedrals_derivatives(
                v0, v1, v2, cell=self.cell, pbc=self.pbc
            )
            return self.finalize_jacobian(pos, len(v0), 4, derivs)

        def setup_jacobian(self, pos):
            self.jacobian = self.get_jacobian(pos)

        def adjust_positions(self, oldpos, newpos):
            v0, v1, v2 = self.gather_vectors(newpos)
            value = get_dihedrals(v0, v1, v2, cell=self.cell, pbc=self.pbc)
            # apply minimum dihedral difference 'convention': (diff <= 180)
            self.sigma = (value - self.targetvalue + 180) % 360 - 180
            self.finalize_positions(newpos)

        @staticmethod
        def get_value(atoms, indices, mic):
            return atoms.get_dihedral(*indices, mic=mic)

        def __repr__(self):
            return f'FixDihedral({self.targetvalue}, {self.indices})'
