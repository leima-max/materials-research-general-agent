import secrets
import warnings

import numpy as np
from scipy.linalg import expm

from ase import units
from ase.md.md import MolecularDynamics
from ase.stress import voigt_6_to_full_3x3_stress


class LangevinBAOAB(MolecularDynamics):
    """Time integrator using Langevin for positions and Langevin-Hoover
    for cell (fixed cell, fixed cell shape + variable volume, or fully
    variable cell) with BAOAB time propagation

    BAOAB algorithm from Leimkuhler and Matthews "Robust and efficient
    configurational molecular sampling via Langevin dynamics",
    J. Chem. Phys. 138 174102 (2013).
    https://doi.org/10.1063/1.4802990

    There is some evidence that other time integration schemes, e.g. BAOA,
    may be better (https://pubs.acs.org/doi/full/10.1021/acs.jctc.2c00585),
    and it may be straightforward to add these, but none are not currently
    supported .

    Langevin-Hoover from Quigley and Probert "Langevin dynamics in constant
    pressure extended systems", J. Chem. Phys 120 11432 (2004).
    https://doi.org/10.1063/1.1755657

    Parameters
    ----------
    atoms: Atoms
        Atoms object for dynamics.
    timestep: float
        Timestep (ASE native units) for time propagation.
    temperature_K: float, optional
        Constant temperature to apply, in K. Enables constant temperature
        dynamics with NVT or NPT, otherwise dynamics are NVE or NPH
        (depending on ``externalstress``).
    externalstress: float, ndarray(3), narray(6), narray((3, 3)), optional
        Constant stress to apply, in ASE native units. Enables variable cell
        dynamics with constant NPH or NPT (depending on ``temperature_K``).
        Note that stress is negative of pressure, so *negative* values lead to
        compression. Note also that barostat will keep mean stress **including
        kinetic (i.e. ideal gas) contribution** equal to this value.  Only
        scalars are allowed if ``hydrostatic`` is True.
    hydrostatic: bool, default False
        Allow only hydrostatic strain (i.e. preserve cell *shape* but allow
        overall scaling of volume).
    T_tau: float, optional
        Time constant for position degree of freedom Langevin. Defaults to 50 *
        ``timestep`` if not specified.
    P_tau: float, optional
        Time constant for variable cell dynamics (cell fluctuation period
        used to set P_mass heuristic for NPH, and both flucutation period and
        Langevin timescale for NPT). Defaults to 20 * ``T_tau`` if T_tau is
        provided, otherwise 1000 * ``timestep``.
    P_mass: float, optional
        Mass used for variable cell dynamics. Default is a heuristic value that
        aims for fluctuation period of ``P_tau / 4``.
    P_mass_factor: float, default 1.0
        Factor to multiply heuristic ``P_mass`` if no user ``P_mass`` value is
        explicitly provided
    disable_cell_langevin: bool, default False
        Turn off Langevin thermalization of cell DOF even if ``temperature_K``
        is not ``None``.  Variable cell will still be done if
        ``externalstress`` is not ``None``, in which case cell equilibration
        will rely on interaction between cell and position DOFs.
    rng: np.random.Generator or argument to np.random.default_rng, default None
        Random number generator for Langevin forces, or integer used as seed
        for new Generator.  If None, a random seed will be generated and
        reported for future reproducibility of run
    **kwargs: dict
        Additional ase.md.md.MolecularDynamics kwargs.
    """

    def __init__(
        self,
        atoms,
        timestep,
        *,
        temperature_K=None,
        externalstress=None,
        hydrostatic=False,
        T_tau=None,
        P_tau=None,
        P_mass=None,
        P_mass_factor=1.0,
        disable_cell_langevin=False,
        rng=None,
        **kwargs,
    ):
        super().__init__(atoms, timestep, **kwargs)

        self._set_externalstress_hydrostatic(externalstress, hydrostatic)
        self.disable_cell_langevin = disable_cell_langevin

        if temperature_K is not None:
            # run constant T, need rng and T_tau
            if rng is None:
                # procedure recommended in
                # https://blog.scientific-python.org/numpy/numpy-rng/#random-number-generation-with-numpy
                seed = secrets.randbits(128)
                self.rng = np.random.default_rng(seed)
                warnings.warn(
                    f'No rng provided, generated one with seed={seed} from '
                    'secrets.randbits',
                )
            elif not isinstance(rng, np.random.Generator):
                self.rng = np.random.default_rng(rng)
            else:
                # already a Generator
                self.rng = rng

            if T_tau is None:
                T_tau = 50.0 * self.dt
                warnings.warn(
                    'Got `temperature_K` but missing `T_tau`, '
                    f'defaulting to 50 * `timstep` = {T_tau}'
                )
        self.T_tau = T_tau
        if self.T_tau is not None and self.T_tau <= 0:
            raise ValueError(f'Invalid T_tau {self.T_tau} <= 0')

        # default contribution to effective gamma used in _BAOAB_OU that comes
        # from barostat from 2nd term in RHS of Quigley Eq. (5b)
        self.gamma_mod = 0.0

        if self.externalstress is not None:
            # set various quantities required for variable cell dynamics

            # pressure timescale
            self._set_P_tau(P_tau)
            if self.P_tau is not None and self.P_tau <= 0:
                raise ValueError(f'Invalid P_tau {self.P_tau} <= 0')

            # initial momentum of cell DOFs
            self.p_eps = 0.0

            # Hope that ASE Atoms.get_number_of_degrees_of_freedom() gives
            # correct value.  It's not, for example, completely obvious what
            # should be # done about the 3 overall translation DOFs, since
            # conventional # Langevin does not actually preserve those (i.e.
            # violates conservation of momentum). See, e.g.,
            #     https://doi.org/10.1063/5.0286750
            # for discussion of variants, e.g. DPD pairwise-force thermostat
            if len(self.atoms.constraints) != 0:
                warnings.warn(
                    'WARNING: LangevinBAOAB has not been '
                    'tested with constraints'
                )
            self.Ndof = self.atoms.get_number_of_degrees_of_freedom()

            self._set_barostat_mass(P_mass, P_mass_factor)

        # must call _after_ var cell quantities are set, because actual
        # parameters used in dynamics depend on temperature, so this function
        # needs to know P_tau, etc
        self.set_temperature(temperature_K, from_init=True)

        # initialize forces and stresses
        self._update_accel()
        if self.externalstress is not None:
            self._update_force_eps()

    def _set_externalstress_hydrostatic(self, externalstress, hydrostatic):
        """Set self.externalstress of correct shape and self.hydrostatic

        Parameters
        ----------
        externalstress: float or None
            external stress
        hydrostatic: bool
            hydrostatic (fixed shape, variable volume) variations
        """
        self.hydrostatic = hydrostatic

        if externalstress is None:
            self.externalstress = externalstress
            return None

        # promote to ndarray to simplify code below
        externalstress = np.asarray(externalstress)
        if externalstress.shape == ():
            externalstress = externalstress.reshape((-1))

        # reshape to scalar (iff hydrostatic) or 3x3 matrix (general var cell)
        if self.hydrostatic:
            # external stress must be scalar
            if externalstress.shape != (1,):
                raise ValueError(
                    'externalstress must be scalar when hydrostatic, '
                    f"got '{externalstress}' with shape "
                    f'{externalstress.shape}'
                )
            externalstress = externalstress[0]
        else:
            # external stress must end up as 3x3 matrix
            match externalstress.shape:
                case (1,):
                    externalstress = externalstress * np.identity(3)
                case (3,):
                    externalstress = np.diag(externalstress)
                case (6,):
                    externalstress = voigt_6_to_full_3x3_stress(externalstress)
                case (3, 3):
                    pass
                case '_':
                    raise ValueError(
                        'externalstress must be scalar, 3-vector (diagonal), '
                        '6-vector (Voigt), or 3x3 matrix, '
                        f'got "{externalstress}" with shape '
                        f'{externalstress.shape}'
                    )

        self.externalstress = externalstress

    def _set_P_tau(self, P_tau):
        """Set self.P_tau from value, or default based on self.T_tau or self.dt

        Parameters
        ----------
        P_tau: float or None
            time scale for pressure fluctuations
        """
        if P_tau is None:
            if self.T_tau is not None:
                P_tau = 20.0 * self.T_tau
                warnings.warn(
                    'Got `externalstress` but missing `P_tau`, got '
                    f'`T_tau`, defaulting to 20 * `T_tau` = {P_tau}'
                )
            else:
                P_tau = 1000.0 * self.dt
                warnings.warn(
                    'Got `externalstress` but missing `P_tau` and '
                    f'`T_tau`, defaulting to 1000 * `timestep` = {P_tau}'
                )
        self.P_tau = P_tau

    def _set_barostat_mass(self, P_mass, P_mass_factor):
        """Set self.barostat_mass based on P_mass and P_mass_factor, as well as
        variable cell timescale self.P_tau

        Parameters
        ----------
        P_mass: float or None
            barostat mass
        P_mass_factor: float, default 1.0
            factor to be applied relative to default value of heuristic
        """
        if P_mass is None:
            # set P_mass with heuristic
            #
            # originally tried expression from Quigley Eq. 17
            #    W = 3 N k_B T / (2 pi / tau)^2
            # empirically didn't work at all
            #
            # instead, using empirical value based on tests
            # of various P_mass, supercell sizes
            #
            # supercell of 4 atom Al FCC cell
            # VARY P_mass: looks like tau \prop sqrt(P_mass)
            # sc 3 P_mass 1000  T 300 period 34.01360544217687
            # sc 3 P_mass 10000 T 300 period 91.74311926605505
            # VARY sc: looks like tau \prop 1/sqrt(N^1/3)
            # sc 2 P_mass 10000.0 T 400 period 104.16666666666667 (32 atoms)
            # sc 3 P_mass 10000.0 T 400 period 92.5925925925926  (108 atoms)
            # sc 4 P_mass 10000.0 T 400 period 66.66666666666667 (256 atoms)
            # tau = C * sqrt(P_mass) / N**(1/6)
            # 66 fs for N = 4 * 4^3 = 256, P_mass = 10^4
            # 66 fs = C * 10000**0.5 / 256.0**(1.0/6.0)
            # C = 66 fs / (10000**0.5 / 256.0**(1.0/6.0))
            # C = 1.6630957858612323 fs
            # P_mass = ((tau / C) * N**(1/6)) ** 2
            #
            # note that constant here may be very system (bulk modulus?)
            # dependent
            if not self.P_tau > 0:
                raise ValueError('Heuristic used for P_mass requires P_tau > 0')
            C = 1.66 * units.fs
            barostat_mass = (
                ((self.P_tau / 4.0) / C) * (len(self.atoms) ** (1.0 / 6.0))
            ) ** 2
            warnings.warn(
                f'Using heuristic P_mass {barostat_mass} '
                f'from P_tau {self.P_tau}'
            )
            barostat_mass *= P_mass_factor
        else:
            barostat_mass = P_mass

        self.barostat_mass = barostat_mass

    def set_temperature(self, temperature_K, from_init=False):
        """Set the internal parameters that depend on temperature

        Parameters
        ----------
        temperature_K: float
            temperature in K
        """
        self.temperature_K = temperature_K

        # default to thermostats (for positions and cell DOFs) disabled
        self.gamma = 0.0
        self.barostat_gamma = 0.0

        if self.temperature_K is None:
            return

        ############################################################
        # position related quantities
        if self.T_tau is None or self.T_tau <= 0:
            raise RuntimeError(
                f'Got temperature {self.temperature_K}, but Langevin '
                f'time-scale T_tau {self.T_tau} is invalud'
            )
        self.gamma = 1.0 / self.T_tau
        # sigma from before Eq. 4 of Leimkuhler
        sigma = np.sqrt(2.0 * self.gamma * units.kB * self.temperature_K)
        # prefactor from after Eq. 6
        self.BAOAB_prefactor = (sigma / np.sqrt(2.0 * self.gamma)) * np.sqrt(
            1.0 - np.exp(-2.0 * self.gamma * self.dt)
        )
        # does not include sqrt(mass), since that is different for
        # each atom type

        ############################################################
        # cell related quantities
        if self.externalstress is not None and not self.disable_cell_langevin:
            self.barostat_gamma = 1.0 / self.P_tau
            sigma = np.sqrt(
                2.0 * self.barostat_gamma * units.kB * self.temperature_K
            )
            self._barostat_BAOAB_prefactor = (
                (sigma / np.sqrt(2.0 * self.barostat_gamma))
                * np.sqrt(1.0 - np.exp(-2.0 * self.barostat_gamma * self.dt))
                * np.sqrt(self.barostat_mass)
            )
            # _does_ include sqrt(mass) factor

    def _update_accel(self):
        """Update position-acceleration from current positions via forces"""
        self.accel = (self.atoms.get_forces().T / self.atoms.get_masses()).T

    def _update_force_eps(self):
        """Update cell force from current positions via stress"""
        volume = self.atoms.get_volume()
        if self.hydrostatic:
            KE = self.atoms.get_kinetic_energy()
            Tr_virial = -volume * np.trace(self.atoms.get_stress(voigt=False))
            X = 1.0 / (3.0 * volume) * (2.0 * KE + Tr_virial)

            # NB explicit dphi/dV term in Quigley Eq. 6 is old fashioned
            # explicit volume dependence for long range tails.  Stress/pressure
            # comes in via sum r . f, which is
            # Tr[virial] = - volume * Tr[stress]
            self.force_eps = (
                3.0 * volume * (X + self.externalstress)
                + (3.0 / self.Ndof) * 2.0 * KE
            )
        else:
            mom = self.atoms.get_momenta()
            kinetic_stress_contrib = (mom.T / self.atoms.get_masses()) @ mom
            virial = -volume * self.atoms.get_stress(voigt=False)
            X = (1.0 / volume) * (kinetic_stress_contrib + virial)

            self.force_eps = volume * (X + self.externalstress) + (
                1.0 / self.Ndof
            ) * np.trace(kinetic_stress_contrib) * np.identity(3)

    def _BAOAB_B(self):
        """Do a BAOAB B (velocity) half step"""
        dvel = 0.5 * self.dt * self.accel
        self.atoms.set_velocities(self.atoms.get_velocities() + dvel)

    def _barostat_BAOAB_B(self):
        """Do a barostat BAOAB B (cell momentum) half step"""
        self.p_eps += 0.5 * self.dt * self.force_eps

    def _BAOAB_A(self):
        """Do a BAOAB A (position) half step"""
        self.atoms.positions += 0.5 * self.dt * self.atoms.get_velocities()

    def _barostat_BAOAB_A(self):
        """Do a barostat BAOAB A (cell volume) half step"""
        if self.hydrostatic:
            volume = self.atoms.get_volume()
            new_volume = volume * np.exp(
                0.5 * self.dt * 3.0 * self.p_eps / self.barostat_mass
            )
            new_cell = self.atoms.cell * (new_volume / volume) ** (1.0 / 3.0)
        else:
            new_cell = (
                self.atoms.cell
                @ expm(0.5 * self.dt * self.p_eps / self.barostat_mass).T
            )

        self.atoms.set_cell(new_cell, True)

    def _BAOAB_OU(self, drag_gamma_mod=0.0):
        """Do a BAOAB Ornstein-Uhlenbeck position Langevin full step

        Parameters
        ----------
        drag_gamma_mod: float, default 0
            additional contribution to effective gamma used for drag on
            velocities, e.g. from Langevin-Hoover
        """
        if self.gamma == 0 and np.all(drag_gamma_mod == 0):
            return

        vel = self.atoms.get_velocities()

        if self.hydrostatic:
            vel *= np.exp(-(self.gamma + drag_gamma_mod) * self.dt)
        else:
            vel = (
                vel
                @ expm(
                    -(self.gamma * np.identity(3) + drag_gamma_mod) * self.dt
                ).T
            )

        if self.gamma != 0:
            # here we divide by sqrt(m), since Leimkuhler definition includes
            # sqrt(m) in numerator but that's for momentum, so for velocity we
            # divide by m, i.e. net 1/sqrt(m)
            vel_shape = self.atoms.positions.shape
            masses = self.atoms.get_masses()
            vel += (
                self.BAOAB_prefactor
                * (self.rng.normal(size=vel_shape).T / np.sqrt(masses)).T
            )

        self.atoms.set_velocities(vel)

    def _barostat_BAOAB_OU(self):
        """Do a barostat BAOAB Ornstein-Uhlenbeck cell volume Langevin full
        step"""
        if self.barostat_gamma == 0:
            # i.e. temperature_K is None or disable_cell_langevin
            return

        self.p_eps *= np.exp(-self.barostat_gamma * self.dt)

        if self.hydrostatic:
            self.p_eps += self._barostat_BAOAB_prefactor * self.rng.normal()
        else:
            random_force = self.rng.normal(size=(3, 3))
            # symmetrize to avoid rotation
            random_force += random_force.T
            random_force /= 2
            self.p_eps += self._barostat_BAOAB_prefactor * random_force

    def _barostat_BAOAB_OU_gamma_mod(self):
        """Compute contribution to drag effective gamma applied to atom
        velocities due to barostat velocity
        """
        if self.hydrostatic:
            return (1.0 + 3.0 / self.Ndof) * self.p_eps / self.barostat_mass
        else:
            return (
                self.p_eps + (1.0 / self.Ndof) * np.trace(self.p_eps)
            ) / self.barostat_mass

    def step(self):
        """Do a time step"""
        if self.externalstress is not None:
            self._barostat_BAOAB_B()
        self._BAOAB_B()  # half step vel

        if self.externalstress is not None:
            self._barostat_BAOAB_A()
        self._BAOAB_A()  # half step pos

        if self.externalstress is not None:
            self.gamma_mod = self._barostat_BAOAB_OU_gamma_mod()
        self._BAOAB_OU(self.gamma_mod)  # OU vel
        if self.externalstress is not None:
            self._barostat_BAOAB_OU()

        self._BAOAB_A()  # half step pos
        if self.externalstress is not None:
            self._barostat_BAOAB_A()

        self._update_accel()  # update accel from final pos
        if self.externalstress is not None:
            self._update_force_eps()  # update cell force

        self._BAOAB_B()  # half step vel
        if self.externalstress is not None:
            self._barostat_BAOAB_B()
