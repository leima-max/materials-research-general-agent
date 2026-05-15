import numpy as np

from ase.constraints.constraint import FixConstraint
from ase.geometry import find_mic, wrap_positions


class FixLinearTriatomic(FixConstraint):
    """Holonomic constraints for rigid linear triatomic molecules."""

    def __init__(self, triples):
        """Apply RATTLE-type bond constraints between outer atoms n and m
        and linear vectorial constraints to the position of central
        atoms o to fix the geometry of linear triatomic molecules of the
        type:

        n--o--m

        Parameters:

        triples: list
            Indices of the atoms forming the linear molecules to constrain
            as triples. Sequence should be (n, o, m) or (m, o, n).

        When using these constraints in molecular dynamics or structure
        optimizations, atomic forces need to be redistributed within a
        triple. The function redistribute_forces_optimization implements
        the redistribution of forces for structure optimization, while
        the function redistribute_forces_md implements the redistribution
        for molecular dynamics.

        References:

        Ciccotti et al. Molecular Physics 47 (1982)
        :doi:`10.1080/00268978200100942`
        """
        self.triples = np.asarray(triples)
        if self.triples.shape[1] != 3:
            raise ValueError('"triples" has wrong size')
        self.bondlengths = None

    def get_removed_dof(self, atoms):
        return 4 * len(self.triples)

    @property
    def n_ind(self):
        return self.triples[:, 0]

    @property
    def m_ind(self):
        return self.triples[:, 2]

    @property
    def o_ind(self):
        return self.triples[:, 1]

    def initialize(self, atoms):
        masses = atoms.get_masses()
        self.mass_n, self.mass_m, self.mass_o = self.get_slices(masses)

        self.bondlengths = self.initialize_bond_lengths(atoms)
        self.bondlengths_nm = self.bondlengths.sum(axis=1)

        C1 = self.bondlengths[:, ::-1] / self.bondlengths_nm[:, None]
        C2 = (
            C1[:, 0] ** 2 * self.mass_o * self.mass_m
            + C1[:, 1] ** 2 * self.mass_n * self.mass_o
            + self.mass_n * self.mass_m
        )
        C2 = C1 / C2[:, None]
        C3 = self.mass_n * C1[:, 1] - self.mass_m * C1[:, 0]
        C3 = C2 * self.mass_o[:, None] * C3[:, None]
        C3[:, 1] *= -1
        C3 = (C3 + 1) / np.vstack((self.mass_n, self.mass_m)).T
        C4 = C1[:, 0] ** 2 + C1[:, 1] ** 2 + 1
        C4 = C1 / C4[:, None]

        self.C1 = C1
        self.C2 = C2
        self.C3 = C3
        self.C4 = C4

    def adjust_positions(self, atoms, new):
        old = atoms.positions
        new_n, new_m, new_o = self.get_slices(new)

        if self.bondlengths is None:
            self.initialize(atoms)

        r0 = old[self.n_ind] - old[self.m_ind]
        d0, _ = find_mic(r0, atoms.cell, atoms.pbc)
        d1 = new_n - new_m - r0 + d0
        a = np.einsum('ij,ij->i', d0, d0)
        b = np.einsum('ij,ij->i', d1, d0)
        c = np.einsum('ij,ij->i', d1, d1) - self.bondlengths_nm**2
        g = (b - (b**2 - a * c) ** 0.5) / (a * self.C3.sum(axis=1))
        g = g[:, None] * self.C3
        new_n -= g[:, 0, None] * d0
        new_m += g[:, 1, None] * d0
        if np.allclose(d0, r0):
            new_o = self.C1[:, 0, None] * new_n + self.C1[:, 1, None] * new_m
        else:
            v1, _ = find_mic(new_n, atoms.cell, atoms.pbc)
            v2, _ = find_mic(new_m, atoms.cell, atoms.pbc)
            rb = self.C1[:, 0, None] * v1 + self.C1[:, 1, None] * v2
            new_o = wrap_positions(rb, atoms.cell, atoms.pbc)

        self.set_slices(new_n, new_m, new_o, new)

    def adjust_momenta(self, atoms, p):
        old = atoms.positions
        p_n, p_m, p_o = self.get_slices(p)

        if self.bondlengths is None:
            self.initialize(atoms)

        mass_nn = self.mass_n[:, None]
        mass_mm = self.mass_m[:, None]
        mass_oo = self.mass_o[:, None]

        d = old[self.n_ind] - old[self.m_ind]
        d, _ = find_mic(d, atoms.cell, atoms.pbc)
        dv = p_n / mass_nn - p_m / mass_mm
        k = np.einsum('ij,ij->i', dv, d) / self.bondlengths_nm**2
        k = self.C3 / (self.C3.sum(axis=1)[:, None]) * k[:, None]
        p_n -= k[:, 0, None] * mass_nn * d
        p_m += k[:, 1, None] * mass_mm * d
        p_o = mass_oo * (
            self.C1[:, 0, None] * p_n / mass_nn
            + self.C1[:, 1, None] * p_m / mass_mm
        )

        self.set_slices(p_n, p_m, p_o, p)

    def adjust_forces(self, atoms, forces):
        if self.bondlengths is None:
            self.initialize(atoms)

        A = self.C4 * np.diff(self.C1)
        A[:, 0] *= -1
        A -= 1
        B = np.diff(self.C4) / (A.sum(axis=1))[:, None]
        A /= (A.sum(axis=1))[:, None]

        self.constraint_forces = -forces
        old = atoms.positions

        fr_n, fr_m, fr_o = self.redistribute_forces_optimization(forces)

        d = old[self.n_ind] - old[self.m_ind]
        d, _ = find_mic(d, atoms.cell, atoms.pbc)
        df = fr_n - fr_m
        k = -np.einsum('ij,ij->i', df, d) / self.bondlengths_nm**2
        forces[self.n_ind] = fr_n + k[:, None] * d * A[:, 0, None]
        forces[self.m_ind] = fr_m - k[:, None] * d * A[:, 1, None]
        forces[self.o_ind] = fr_o + k[:, None] * d * B

        self.constraint_forces += forces

    def redistribute_forces_optimization(self, forces):
        """Redistribute forces within a triple when performing structure
        optimizations.

        The redistributed forces needs to be further adjusted using the
        appropriate Lagrange multipliers as implemented in adjust_forces."""
        forces_n, forces_m, forces_o = self.get_slices(forces)
        C1_1 = self.C1[:, 0, None]
        C1_2 = self.C1[:, 1, None]
        C4_1 = self.C4[:, 0, None]
        C4_2 = self.C4[:, 1, None]

        fr_n = (1 - C4_1 * C1_1) * forces_n - C4_1 * (
            C1_2 * forces_m - forces_o
        )
        fr_m = (1 - C4_2 * C1_2) * forces_m - C4_2 * (
            C1_1 * forces_n - forces_o
        )
        fr_o = (
            (1 - 1 / (C1_1**2 + C1_2**2 + 1)) * forces_o
            + C4_1 * forces_n
            + C4_2 * forces_m
        )

        return fr_n, fr_m, fr_o

    def redistribute_forces_md(self, atoms, forces, rand=False):
        """Redistribute forces within a triple when performing molecular
        dynamics.

        When rand=True, use the equations for random force terms, as
        used e.g. by Langevin dynamics, otherwise apply the standard
        equations for deterministic forces (see Ciccotti et al. Molecular
        Physics 47 (1982))."""
        if self.bondlengths is None:
            self.initialize(atoms)
        forces_n, forces_m, forces_o = self.get_slices(forces)
        C1_1 = self.C1[:, 0, None]
        C1_2 = self.C1[:, 1, None]
        C2_1 = self.C2[:, 0, None]
        C2_2 = self.C2[:, 1, None]
        mass_nn = self.mass_n[:, None]
        mass_mm = self.mass_m[:, None]
        mass_oo = self.mass_o[:, None]
        if rand:
            mr1 = (mass_mm / mass_nn) ** 0.5
            mr2 = (mass_oo / mass_nn) ** 0.5
            mr3 = (mass_nn / mass_mm) ** 0.5
            mr4 = (mass_oo / mass_mm) ** 0.5
        else:
            mr1 = 1.0
            mr2 = 1.0
            mr3 = 1.0
            mr4 = 1.0

        fr_n = (1 - C1_1 * C2_1 * mass_oo * mass_mm) * forces_n - C2_1 * (
            C1_2 * mr1 * mass_oo * mass_nn * forces_m
            - mr2 * mass_mm * mass_nn * forces_o
        )

        fr_m = (1 - C1_2 * C2_2 * mass_oo * mass_nn) * forces_m - C2_2 * (
            C1_1 * mr3 * mass_oo * mass_mm * forces_n
            - mr4 * mass_mm * mass_nn * forces_o
        )

        self.set_slices(fr_n, fr_m, 0.0, forces)

    def get_slices(self, a):
        a_n = a[self.n_ind]
        a_m = a[self.m_ind]
        a_o = a[self.o_ind]

        return a_n, a_m, a_o

    def set_slices(self, a_n, a_m, a_o, a):
        a[self.n_ind] = a_n
        a[self.m_ind] = a_m
        a[self.o_ind] = a_o

    def initialize_bond_lengths(self, atoms):
        bondlengths = np.zeros((len(self.triples), 2))

        for i in range(len(self.triples)):
            bondlengths[i, 0] = atoms.get_distance(
                self.n_ind[i], self.o_ind[i], mic=True
            )
            bondlengths[i, 1] = atoms.get_distance(
                self.o_ind[i], self.m_ind[i], mic=True
            )

        return bondlengths

    def get_indices(self):
        return np.unique(self.triples.ravel())

    def todict(self):
        return {
            'name': 'FixLinearTriatomic',
            'kwargs': {'triples': self.triples.tolist()},
        }

    def index_shuffle(self, atoms, ind):
        """Shuffle the indices of the three atoms in this constraint"""
        map = np.zeros(len(atoms), int)
        map[ind] = 1
        n = map.sum()
        map[:] = -1
        map[ind] = range(n)
        triples = map[self.triples]
        self.triples = triples[(triples != -1).all(1)]
        if len(self.triples) == 0:
            raise IndexError('Constraint not part of slice')
