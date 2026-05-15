# fmt: off

"""Modules for calculating thermochemical information from computational
outputs."""

import os
import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Literal
from warnings import catch_warnings, simplefilter, warn

import numpy as np
from scipy.integrate import trapezoid

from ase import Atoms, units

_GEOMETRY_OPTIONS = Literal['linear', 'nonlinear', 'monatomic']
_VIB_SELECTION_OPTIONS = Literal['exact', 'all', 'highest', 'abs_highest']
_FLOAT_OR_FLOATWITHDICT = float | tuple[float, dict[str, float]]
_FLOATWITHDICT = tuple[float, dict[str, float]]


def _sum_contributions(contrib_dicts: dict[str, float]) -> float:
    """Combine a Dict of floats to their sum.

    Ommits keys starting with an underscore.
    """
    return np.sum([value for key, value in contrib_dicts.items()
                   if not key.startswith('_')])


class AbstractMode(ABC):
    """Abstract base class for mode objects.

    Input:

    energy: float
            Initialize the mode with its energy in eV.
            Note: This energy refers to the vibrational energy of the mode.
            Get it e.g. from ase.vibrations.Vibrations.get_energies.
    """

    def __init__(self, energy: float) -> None:
        self.energy = energy

    @abstractmethod
    def get_internal_energy(
            self,
            temperature: float,
            contributions: bool) -> _FLOAT_OR_FLOATWITHDICT:
        raise NotImplementedError

    @abstractmethod
    def get_entropy(self, temperature: float,
                    contributions: bool) -> _FLOAT_OR_FLOATWITHDICT:
        raise NotImplementedError


class HarmonicMode(AbstractMode):
    """Class for a single harmonic mode."""

    def get_ZPE_correction(self) -> float:
        """Returns the zero-point vibrational energy correction in eV."""
        return 0.5 * self.energy

    def get_vib_energy_contribution(self, temperature: float) -> float:
        """Calculates the change in internal energy due to vibrations from
        0K to the specified temperature for a set of vibrations given in
        eV and a temperature given in Kelvin.
        Returns the energy change in eV."""
        kT = units.kB * temperature
        return self.energy / (np.exp(self.energy / kT) - 1.)

    def get_vib_entropy_contribution(self, temperature: float) -> float:
        """Calculates the entropy due to vibrations given in eV and a
        temperature given in Kelvin.  Returns the entropy in eV/K."""
        e = self.energy / units.kB / temperature
        S_v = e / (np.exp(e) - 1.) - np.log(1. - np.exp(-e))
        S_v *= units.kB
        return S_v

    def get_internal_energy(self,
                            temperature: float,
                            contributions: bool
                            ) -> _FLOAT_OR_FLOATWITHDICT:
        """Returns the internal energy in the harmonic approximation at a
        specified temperature (K)."""
        ret = {}
        ret['ZPE'] = self.get_ZPE_correction()
        ret['dU_v'] = self.get_vib_energy_contribution(temperature)
        ret_sum = _sum_contributions(ret)

        if contributions:
            return ret_sum, ret
        else:
            return ret_sum

    def get_entropy(self,
                    temperature: float,
                    contributions: bool) -> _FLOAT_OR_FLOATWITHDICT:
        """Returns the entropy in the harmonic approximation at a specified
        temperature (K).

        Parameters
        ----------
        temperature : float
            The temperature in Kelvin.
        contributions : bool
            If True, return the contributions to the entropy as a dict too.
            Here it will only contain the vibrational entropy.

        Returns
        -------
        float or Tuple[float, Dict[str, float]]
        """
        ret = {}
        ret['S_v'] = self.get_vib_entropy_contribution(temperature)
        if contributions:
            return ret['S_v'], ret
        else:
            return ret['S_v']


class RRHOMode(HarmonicMode):
    """Class for a single RRHO mode, including Grimme's scaling method
    based on :doi:`10.1002/chem.201200497` and :doi:`10.1039/D1SC00621E`.

    Inputs:

    mean_inertia : float
        The mean moment of inertia in amu*angstrom^2. Use
        `np.mean(ase.Atoms.get_moments_of_inertia())` to calculate.
    tau : float
        the vibrational energy threshold in :math:`cm^{-1}`, named
        :math:`\\tau` in :doi:`10.1039/D1SC00621E`.
        Values close or equal to 0 will result in the standard harmonic
        approximation. Defaults to :math:`35cm^{-1}`.
    treat_int_energy : bool
        Extend the msRRHO treatement to the internal thermal energy.
        If False, only the entropy contribution as in Grimmmes paper is
        modified according to the RRHO scheme. If True, the approach of
        Otlyotov and Minenkov :doi:`10.1002/jcc.27129` is used to modify
        the internal energy contribution.
    """

    def __init__(self, energy: float,
                 mean_inertia: float,
                 tau: float = 35.0,
                 treat_int_energy: bool = False) -> None:
        if np.iscomplex(energy):
            raise ValueError(
                "Imaginary frequencies are not allowed in RRHO mode.")
        super().__init__(energy)
        self._mean_inertia = mean_inertia
        self._tau = tau
        self._alpha = 4  # from paper 10.1002/chem.201200497
        self.treat_int_energy = treat_int_energy

    @property
    def frequency(self) -> float:
        return self.energy / units.invcm

    def _head_gordon_damp(self, freq: float) -> float:
        """Head-Gordon damping function.

        Equation 8 from :doi:`10.1002/chem.201200497`

        Parameters
        ----------
        freq : float
            The frequency in the same unit as tau.

        Returns
        -------
        float
        """
        return 1 / (1 + (self._tau / freq)**self._alpha)

    def _apply_head_gordon_damp(self, freq: float,
                                large_part: float,
                                small_part: float) -> float:
        """Apply the head-gordon damping scheme to two contributions.

        Equation 7 from :doi:`10.1002/chem.201200497`

        Returns the damped sum of the two contributions."""
        part_one = self._head_gordon_damp(freq) * large_part
        part_two = (1 - self._head_gordon_damp(freq)) * small_part
        return part_one + part_two

    def get_RRHO_entropy_r(self, temperature: float) -> float:
        """Calculates the rotation of a rigid rotor for low frequency modes.

        Equation numbering from :doi:`10.1002/chem.201200497`

        Returns the entropy contribution in eV/K."""
        kT = units._k * temperature
        R = units._k * units._Nav  # J / K / mol
        B_av = (self._mean_inertia /
                (units.kg * units.m**2))  # from amu/A^2 to kg m^2
        # note, some codes use B_av = 1e-44 as in 10.1002/chem.201200497
        # eq 4
        omega = units._c * self.frequency * 1e2   # s^-1
        mu = units._hplanck / (8 * np.pi**2 * omega)  # kg m^2
        # eq 5
        mu_prime = (mu * B_av) / (mu + B_av)  # kg m^2
        # eq 6
        x = np.sqrt(8 * np.pi**3 * mu_prime * kT / (units._hplanck)**2)
        # filter zeros out and set them to zero
        if x == 0.0:
            log_x = 0.0
        else:
            log_x = np.log(x)
        S_r = R * (0.5 + log_x)  # J/(Js)^2
        S_r *= units.J / units._Nav  # J/K/mol to eV/K
        return S_r

    def get_entropy(self,
                    temperature: float,
                    contributions: bool) -> _FLOAT_OR_FLOATWITHDICT:
        ret = {}
        ret['_S_vib_v'] = self.get_vib_entropy_contribution(temperature)
        ret['_S_vib_r'] = self.get_RRHO_entropy_r(temperature)
        ret['S_vib_damped'] = self._apply_head_gordon_damp(
            self.frequency, ret['_S_vib_v'], ret['_S_vib_r'])
        if contributions:
            return ret['S_vib_damped'], ret
        else:
            return ret['S_vib_damped']

    def get_rrho_internal_energy_v_contribution(
            self, temperature: float) -> float:
        """RRHO Vibrational Internal Energy Contribution from
        :doi:`10.1002/jcc.27129`.

        Returns the internal energy contribution in eV."""
        # equation numbering from :doi:`10.1002/jcc.27129`
        # eq 4
        # hv = self.energy
        theta = self.energy / units.kB
        E_v = 0.5 + 1 / (np.exp(theta / temperature) - 1)
        E_v *= self.energy  # = theta * units.kB
        return E_v

    @staticmethod
    def get_rrho_internal_energy_r_contribution(temperature: float) -> float:
        """Calculates the rotation of a rigid rotor contribution.

        Equation numbering from :doi:`10.1002/jcc.27129`

        Returns the internal energy contribution in eV."""
        # eq 5
        R = units._k * units._Nav
        E_r = R * temperature / 2
        E_r *= units.J / units._Nav
        return E_r

    def get_internal_energy(self,
                            temperature: float,
                            contributions: bool) -> _FLOAT_OR_FLOATWITHDICT:
        """Returns the internal energy in the msRRHO approximation at a
        specified temperature (K).

        If self.treat_int_energy is True, the approach of Otlyotov
        and Minenkov :doi:`10.1002/jcc.27129` is used. Otherwise, the approach
        of Grimme :doi:`10.1002/chem.201200497` is used.
        """
        if self.treat_int_energy:
            # Otlyotov and Minenkov approach with damping between vibrational
            # and rotational contributions to the internal energy
            # Note: The ZPE is not needed here, as the formula in the paper
            # uses the "bottom of the well" as reference. See
            # https://gaussian.com/wp-content/uploads/dl/thermo.pdf
            # for more formulas
            ret = {}
            ret['_dU_vib_v'] = self.get_rrho_internal_energy_v_contribution(
                temperature)
            ret['_dU_vib_r'] = self.get_rrho_internal_energy_r_contribution(
                temperature)
            ret['dU_vib_damped'] = self._apply_head_gordon_damp(
                self.frequency, ret['_dU_vib_v'], ret['_dU_vib_r'])
            if contributions:
                return ret['dU_vib_damped'], ret
            else:
                return ret['dU_vib_damped']
        else:
            # Grimme uses the Harmonic approach for the internal energy
            return super().get_internal_energy(temperature, contributions)


class BaseThermoChem(ABC):
    """Abstract base class containing common methods used in thermochemistry
    calculations."""

    def __init__(self,
                 vib_energies: Sequence[float] | None = None,
                 atoms: Atoms | None = None,
                 modes: Sequence[AbstractMode] | None = None,
                 spin: float | None = None) -> None:
        if vib_energies is None and modes is None:
            raise ValueError("Either vib_energies or modes must be provided.")
        elif modes:
            self.modes = modes
        # in the monoatomic case, the vib_energies can be an empty list
        else:
            self._vib_energies = vib_energies
        self.referencepressure = 1.0e5  # Pa
        if atoms:
            # check that atoms has no periodic boundary conditions
            # moments of inertia are wrong otherwise.
            if atoms.pbc.any():
                raise ValueError("Atoms object should not have periodic "
                                 "boundary conditions for BaseThermoChem.")
            self.atoms = atoms
        self.spin = spin

    @classmethod
    def from_transition_state(cls, vib_energies: Sequence[complex],
                              *args, **kwargs) -> "BaseThermoChem":
        """Create a new instance for a transition state.

        This will work just as the standard constructor, but will remove
        one imaginary frequency from the given vib_energies first.
        If there is more than one imaginary frequency, an error will be raised.

        Returns
        -------
        BaseThermoChem instance
        """

        if sum(np.iscomplex(vib_energies)):
            # supress user warning
            with catch_warnings():
                simplefilter("ignore")
                vib_e, n_imag = _clean_vib_energies(vib_energies, True)
            if n_imag != 1:
                raise ValueError("Not exactly one imaginary frequency found.")
        else:
            raise ValueError("No imaginary frequencies found in vib_energies.")

        thermo = cls(vib_e, *args, **kwargs)

        return thermo

    @staticmethod
    def combine_contributions(
            contrib_dicts: Sequence[dict[str, float]]) -> dict[str, float]:
        """Combine the contributions from multiple modes."""
        ret: dict[str, float] = {}
        for contrib_dict in contrib_dicts:
            for key, value in contrib_dict.items():
                if key in ret:
                    ret[key] += value
                else:
                    ret[key] = value
        return ret

    def print_contributions(
            self, contributions: dict[str, float], verbose: bool) -> None:
        """Print the contributions."""
        if verbose:
            fmt = "{:<15s}{:13.3f} eV"
            for key, value in contributions.items():
                # subvalues start with _
                if key.startswith('_'):
                    key.replace('_', '... ')
                self._vprint(fmt.format(key, value))

    @abstractmethod
    def get_internal_energy(self, temperature: float, verbose: bool) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_entropy(self, temperature: float,
                    pressure: float = units.bar,
                    verbose: bool = True) -> float:
        raise NotImplementedError

    @property
    def vib_energies(self) -> np.ndarray:
        """Get the vibrational energies in eV.

        For backwards compatibility, this will return the modes' energies if
        they are available. Otherwise, it will return the stored vib_energies.
        """
        # build from modes if available
        if hasattr(self, 'modes'):
            return np.array([mode.energy for mode in self.modes])
        elif hasattr(self, '_vib_energies'):
            return np.array(self._vib_energies)
        else:
            raise AttributeError("No vibrational energies available.")

    @vib_energies.setter
    def vib_energies(self, value: Sequence[float]) -> None:
        """For backwards compatibility, raise a deprecation warning."""
        warn(
            "The vib_energies attribute is deprecated and will be removed in a"
            "future release. Please use the modes attribute instead."
            "Setting this outside the constructor will not update the modes",
            DeprecationWarning)
        self._vib_energies = value

    def get_ZPE_correction(self) -> float:
        """Returns the zero-point vibrational energy correction in eV."""
        return 0.5 * np.sum(self.vib_energies)

    @staticmethod
    def get_ideal_translational_energy(temperature: float) -> float:
        """Returns the translational heat capacity times T in eV.

        Parameters
        ----------
        temperature : float
            The temperature in Kelvin.

        Returns
        -------
        float
        """
        return 3. / 2. * units.kB * \
            temperature  # translational heat capacity (3-d gas)

    @staticmethod
    def get_ideal_rotational_energy(geometry: _GEOMETRY_OPTIONS,
                                    temperature: float) -> float:
        """Returns the rotational heat capacity times T in eV.

        Parameters
        ----------
        geometry : str
            The geometry of the molecule. Options are 'nonlinear',
            'linear', and 'monatomic'.
        temperature : float
            The temperature in Kelvin.

        Returns
        -------
        float
        """
        if geometry == 'nonlinear':  # rotational heat capacity
            Cv_r = 3. / 2. * units.kB
        elif geometry == 'linear':
            Cv_r = units.kB
        elif geometry == 'monatomic':
            Cv_r = 0.
        else:
            raise ValueError('Invalid geometry: %s' % geometry)
        return Cv_r * temperature

    def get_ideal_trans_entropy(
            self,
            atoms: Atoms,
            temperature: float) -> float:
        """Returns the translational entropy in eV/K.

        Parameters
        ----------
        atoms : ase.Atoms
            The atoms object.
        temperature : float
            The temperature in Kelvin.

        Returns
        -------
        float
        """
        # Translational entropy (term inside the log is in SI units).
        mass = sum(atoms.get_masses()) * units._amu  # kg/molecule
        S_t = (2 * np.pi * mass * units._k *
               temperature / units._hplanck**2)**(3.0 / 2)
        S_t *= units._k * temperature / self.referencepressure
        S_t = units.kB * (np.log(S_t) + 5.0 / 2.0)
        return S_t

    def get_vib_energy_contribution(self, temperature: float) -> float:
        """Calculates the change in internal energy due to vibrations from
        0K to the specified temperature for a set of vibrations given in
        eV and a temperature given in Kelvin.
        Returns the energy change in eV."""
        # Leftover for HinderedThermo class, delete once that is converted
        # to use modes
        kT = units.kB * temperature
        dU = 0.

        for energy in self.vib_energies:
            dU += energy / (np.exp(energy / kT) - 1.)
        return dU

    def get_vib_entropy_contribution(self,
                                     temperature: float,
                                     return_list: bool = False
                                     ) -> float | Sequence[float]:
        """Calculates the entropy due to vibrations for a set of vibrations
        given in eV and a temperature given in Kelvin.  Returns the entropy
        in eV/K."""
        kT = units.kB * temperature
        S_v = 0.
        energies = np.array(self.vib_energies)
        energies /= kT  # eV/ eV/K*K
        S_v = energies / (np.exp(energies) - 1.) - \
            np.log(1. - np.exp(-energies))
        S_v *= units.kB
        if return_list:
            return S_v
        else:
            return np.sum(S_v)

    def _vprint(self, text):
        """Print output if verbose flag True."""
        if self.verbose:
            sys.stdout.write(text + os.linesep)

    def get_ideal_entropy(
            self,
            temperature: float,
            translation: bool = False,
            vibration: bool = False,
            rotation: bool = False,
            geometry: _GEOMETRY_OPTIONS | None = None,
            electronic: bool = False,
            pressure: float | None = None,
            symmetrynumber: int | None = None) -> _FLOATWITHDICT:
        """Returns the entropy, in eV/K and a dict of the contributions.

        Parameters
        ----------
        temperature : float
            The temperature in Kelvin.
        translation : bool
            Include translational entropy.
        vibration : bool
            Include vibrational entropy.
        rotation : bool
            Include rotational entropy.
        geometry : str
            The geometry of the molecule. Options are 'nonlinear',
            'linear', and 'monatomic'.
        electronic : bool
            Include electronic entropy.
        pressure : float
            The pressure in Pa. Only needed for the translational entropy.
        symmetrynumber : int
            The symmetry number of the molecule. Only needed for linear and
            nonlinear molecules.

        Returns
        -------
        Tuple of one float and one dict
        The float is the total entropy in eV/K.
        The dict contains the contributions to the entropy.
        """

        if (geometry in ['linear', 'nonlinear']) and (symmetrynumber is None):
            raise ValueError(
                'Symmetry number required for linear and nonlinear molecules.')

        if not hasattr(self, 'atoms'):
            raise ValueError(
                'Atoms object required for ideal entropy calculation.')

        if electronic and (self.spin is None):
            raise ValueError(
                'Spin value required for electronic entropy calculation.')

        S: float = 0.0
        ret = {}

        if translation:
            S_t = self.get_ideal_trans_entropy(self.atoms, temperature)
            ret['S_t'] = S_t
            S += S_t
            if pressure:
                # Pressure correction to translational entropy.
                S_p = - units.kB * np.log(pressure / self.referencepressure)
                S += S_p
                ret['S_p'] = S_p

        if rotation:
            # Rotational entropy (term inside the log is in SI units).
            if geometry == 'monatomic':
                S_r = 0.0
            elif geometry == 'nonlinear':
                inertias = (self.atoms.get_moments_of_inertia() * units._amu /
                            1e10**2)  # kg m^2
                S_r = np.sqrt(np.pi * np.prod(inertias)) / symmetrynumber
                S_r *= (8.0 * np.pi**2 * units._k * temperature /
                        units._hplanck**2)**(3.0 / 2.0)
                S_r = units.kB * (np.log(S_r) + 3.0 / 2.0)
            elif geometry == 'linear':
                inertias = (self.atoms.get_moments_of_inertia() * units._amu /
                            (10.0**10)**2)  # kg m^2
                inertia = max(inertias)  # should be two identical and one zero
                S_r = (8 * np.pi**2 * inertia * units._k * temperature /
                       symmetrynumber / units._hplanck**2)
                S_r = units.kB * (np.log(S_r) + 1.)
            else:
                raise RuntimeError(f"Invalid geometry: {geometry}")
            S += S_r
            ret['S_r'] = S_r

        # Electronic entropy.
        if electronic:
            assert self.spin is not None  # for mypy, error is raised above
            S_e = units.kB * np.log(2 * self.spin + 1)
            S += S_e
            ret['S_e'] = S_e

        # Vibrational entropy
        if vibration:
            S_v = self.get_vib_entropy_contribution(temperature,
                                                    return_list=False)
            assert isinstance(S_v, float)  # make mypy happy
            S += S_v
            ret['S_v'] = S_v

        return S, ret


class HarmonicThermo(BaseThermoChem):
    """Class for calculating thermodynamic properties in the approximation
    that all degrees of freedom are treated harmonically. Often used for
    adsorbates.

    Note: This class does not include the translational and rotational
    contributions to the entropy by default. Use the get_ideal_entropy method
    for that and add them manually.

    Inputs:

    vib_energies : list
        a list of the harmonic energies of the adsorbate (e.g., from
        ase.vibrations.Vibrations.get_energies). The number of
        energies should match the number of degrees of freedom of the
        adsorbate; i.e., 3*n, where n is the number of atoms. Note that
        this class does not check that the user has supplied the correct
        number of energies. Units of energies are eV. Note, that if 'modes'
        are given, these energies are not used.
    potentialenergy : float
        the potential energy in eV (e.g., from atoms.get_potential_energy)
        (if potentialenergy is unspecified, then the methods of this
        class can be interpreted as the energy corrections)
    ignore_imag_modes : bool
        If 'True', any imaginary frequencies will be removed in the
        calculation of the thermochemical properties.
        If 'False' (default), an error will be raised if any imaginary
        frequencies are present.
    modes : list of AbstractMode
        A list of mode objects. If not provided, :class:`HarmonicMode` objects
        will be created from the vib_energies. This is useful if you want to
        replace individual modes with non-harmonic modes.
    """

    def __init__(self, vib_energies: Sequence[complex],
                 potentialenergy: float = 0.,
                 ignore_imag_modes: bool = False,
                 modes: Sequence[AbstractMode] | None = None) -> None:

        # Check for imaginary frequencies.
        vib_energies, n_imag = _clean_vib_energies(
            vib_energies, ignore_imag_modes)
        if modes is None:
            modes = [HarmonicMode(energy) for energy in vib_energies]
        super().__init__(modes=modes)

        self.n_imag = n_imag

        self.potentialenergy = potentialenergy

    def get_internal_energy(self, temperature: float,
                            verbose: bool = True) -> float:
        """Returns the internal energy, in eV, in the harmonic approximation
        at a specified temperature (K)."""

        self.verbose = verbose
        vprint = self._vprint
        fmt = '%-15s%13.3f eV'
        vprint('Internal energy components at T = %.2f K:' % temperature)
        vprint('=' * 31)

        vprint(fmt % ('E_pot', self.potentialenergy))

        U, contribs = zip(*[mode.get_internal_energy(
            temperature, contributions=True) for mode in self.modes])
        U = np.sum(U)
        U += self.potentialenergy

        self.print_contributions(self.combine_contributions(contribs), verbose)
        vprint('-' * 31)
        vprint(fmt % ('U', U))
        vprint('=' * 31)

        return U

    def get_entropy(self, temperature: float,
                    pressure: float = units.bar,
                    verbose: bool = True) -> float:
        """Returns the entropy, in eV/K at a specified temperature (K).

        Note: This does not include the translational and rotational
        contributions to the entropy. Use the get_ideal_entropy method
        for that.

        Parameters
        ----------
        temperature : float
            The temperature in Kelvin.
        pressure : float
            Not used, but kept for compatibility with other classes.
        verbose : bool
            If True, print the contributions to the entropy.

        Returns
        -------
        float
        """

        self.verbose = verbose
        vprint = self._vprint
        fmt = '%-15s%13.7f eV/K%13.3f eV'
        vprint('Entropy components at T = %.2f K:' % temperature)
        vprint('=' * 49)
        vprint('%15s%13s     %13s' % ('', 'S', 'T*S'))

        S, contribs = zip(*[mode.get_entropy(
            temperature, contributions=True) for mode in self.modes])
        S = np.sum(S)

        self.print_contributions(self.combine_contributions(contribs), verbose)
        vprint('-' * 49)
        vprint(fmt % ('S', S, S * temperature))
        vprint('=' * 49)

        return S

    def get_helmholtz_energy(self, temperature: float,
                             verbose: bool = True) -> float:
        """Returns the Helmholtz free energy, in eV, in the harmonic
        approximation at a specified temperature (K)."""

        self.verbose = True
        vprint = self._vprint

        U = self.get_internal_energy(temperature, verbose=verbose)
        vprint('')
        S = self.get_entropy(temperature, verbose=verbose)
        F = U - temperature * S

        vprint('')
        vprint('Free energy components at T = %.2f K:' % temperature)
        vprint('=' * 23)
        fmt = '%5s%15.3f eV'
        vprint(fmt % ('U', U))
        vprint(fmt % ('-T*S', -temperature * S))
        vprint('-' * 23)
        vprint(fmt % ('F', F))
        vprint('=' * 23)
        return F


class QuasiHarmonicThermo(HarmonicThermo):
    """Subclass of :class:`HarmonicThermo`, including the quasi-harmonic
    approximation of Cramer, Truhlar and coworkers :doi:`10.1021/jp205508z`.

    Note: This class not include the translational and rotational
    contributions to the entropy by default. Use the get_ideal_entropy method
    for that and add them manually.

    Inputs:

    vib_energies : list
        a list of the energies of the vibrations (e.g., from
        ase.vibrations.Vibrations.get_energies). The number of
        energies should match the number of degrees of freedom of the
        adsorbate; i.e., 3*n, where n is the number of atoms. Note that
        this class does not check that the user has supplied the correct
        number of energies. Units of energies are eV.
    potentialenergy : float
        the potential energy in eV (e.g., from atoms.get_potential_energy)
        (if potentialenergy is unspecified, then the methods of this
        class can be interpreted as the energy corrections)
    ignore_imag_modes : bool
        If 'True', any imaginary frequencies will be removed in the
        calculation of the thermochemical properties.
        If 'False' (default), an error will be raised if any imaginary
        frequencies are present.
    modes : list of AbstractMode
        A list of mode objects. If not provided, :class:`HarmonicMode` objects
        will be created from the raised vib_energies. This is useful if you want
        to replace individual modes with non-harmonic modes.
    raise_to : float
        The value to which all frequencies smaller than this value will be
        raised. Unit is eV. Defaults to :math:`100cm^{-1} = 0.012398 eV`.

    """

    @staticmethod
    def _raise(input: Sequence[float], raise_to: float) -> Sequence[float]:
        return [raise_to if x < raise_to else x for x in input]

    def __init__(self, vib_energies: Sequence[complex],
                 potentialenergy: float = 0.,
                 ignore_imag_modes: bool = False,
                 modes: Sequence[AbstractMode] | None = None,
                 raise_to: float = 100 * units.invcm) -> None:

        # Check for imaginary frequencies.
        vib_energies, _ = _clean_vib_energies(
            vib_energies, ignore_imag_modes)
        # raise the low frequencies to a certain value
        vib_energies = self._raise(vib_energies, raise_to)
        if modes is None:
            modes = [HarmonicMode(energy) for energy in vib_energies]
        super().__init__(vib_energies,
                         potentialenergy=potentialenergy,
                         ignore_imag_modes=ignore_imag_modes,
                         modes=modes)


class MSRRHOThermo(QuasiHarmonicThermo):
    """Subclass of :class:`QuasiHarmonicThermo`,
    including Grimme's scaling method based on
    :doi:`10.1002/chem.201200497` and :doi:`10.1039/D1SC00621E`.

    Note: This class not include the translational and rotational
    contributions to the entropy by default. Use the get_ideal_entropy method
    for that and add them manually.

    We enforce treating imaginary modes as Grimme suggests (converting
    them to real by multiplying them with :math:`-i`). So make sure to check
    your input energies.

    Inputs:

    vib_energies : list
        a list of the energies of the vibrations (e.g., from
        ase.vibrations.Vibrations.get_energies). The number of
        energies should match the number of degrees of freedom of the
        atoms object; i.e., 3*n, where n is the number of atoms. Note that
        this class does not check that the user has supplied the correct
        number of energies. Units of energies are eV. Note, that if 'modes'
        are given, these energies are not used.
    atoms: an ASE atoms object
        used to calculate rotational moments of inertia and molecular mass.
        Should not contain periodic boundary conditions.
    tau : float
        the vibrational energy threshold in :math:`cm^{-1}`, namcomplexed
        :math:`\\tau` in :doi:`10.1039/D1SC00621E`.
        Values close or equal to 0 will result in the standard harmonic
        approximation. Defaults to :math:`35cm^{-1}`.
    nu_scal : float
        Linear scaling factor for the vibrational frequencies. Named
        :math:`\\nu_{scal}` in :doi:`10.1039/D1SC00621E`.
        Defaults to 1.0, check the `Truhlar group database
        <https://comp.chem.umn.edu/freqscale/index.html>`_
        for values corresponding to your level of theory.
        Note that for `\\nu_{scal}=1.0` this method is equivalent to
        the quasi-RRHO method in :doi:`10.1002/chem.201200497`.
    treat_int_energy : bool
        Extend the msRRHO treatement to the internal energy. If False, only
        the entropy contribution as in Grimmmes paper is considered.
        If true, the approach of Otlyotov and Minenkov
        :doi:`10.1002/jcc.27129` is used.
    modes : list of AbstractMode
        A list of mode objects. If not provided, :class:`RRHOMode` objects will
        be created from the raised vib_energies. This is useful if you want to
        replace individual modes with non-harmonic modes.

    """

    def __init__(self, vib_energies: Sequence[complex], atoms: Atoms,
                 potentialenergy: float = 0.,
                 tau: float = 35., nu_scal: float = 1.0,
                 treat_int_energy: bool = False,
                 modes: Sequence[AbstractMode] | None = None) -> None:

        # check that atoms has no periodic boundary conditions
        # moments of inertia are wrong otherwise.
        if atoms.pbc.any():
            raise ValueError("Atoms object should not have periodic "
                             "boundary conditions for MSRRHOThermo.")
        inertia = np.mean(atoms.get_moments_of_inertia())
        self.atoms = atoms

        # clean the energies by converting imaginary to real
        # i.e. multiply with -i
        vib_e: Sequence[float]  # make mypy happy
        vib_e = [np.imag(v) if np.iscomplex(v)
                        else np.real(v) for v in vib_energies]

        self.nu_scal = nu_scal
        # scale the frequencies (i.e. energies) before passing them on
        vib_e_scaled = [float(v) for v in np.multiply(vib_e, nu_scal)]

        if modes is None:
            modes = [RRHOMode(energy, inertia,
                              tau=tau,
                              treat_int_energy=treat_int_energy
                              ) for energy in vib_e_scaled]

        super().__init__(vib_e_scaled,
                         potentialenergy=potentialenergy,
                         ignore_imag_modes=False,
                         modes=modes,
                         raise_to=0.0)
        self.treat_int_energy = treat_int_energy


class HinderedThermo(BaseThermoChem):
    """Class for calculating thermodynamic properties in the hindered
    translator and hindered rotor model where all but three degrees of
    freedom are treated as harmonic vibrations, two are treated as
    hindered translations, and one is treated as a hindered rotation.

    Inputs:

    vib_energies : list
        a list of all the vibrational energies of the adsorbate (e.g., from
        ase.vibrations.Vibrations.get_energies). If atoms is not provided,
        then the number of energies must match the number of degrees of freedom
        of the adsorbate; i.e., 3*n, where n is the number of atoms. Note
        that this class does not check that the user has supplied the
        correct number of energies.
        Units of energies are eV.
    trans_barrier_energy : float
        the translational energy barrier in eV. This is the barrier for an
        adsorbate to diffuse on the surface.
    rot_barrier_energy : float
        the rotational energy barrier in eV. This is the barrier for an
        adsorbate to rotate about an axis perpendicular to the surface.
    sitedensity : float
        density of surface sites in cm^-2
    rotationalminima : integer
        the number of equivalent minima for an adsorbate's full rotation.
        For example, 6 for an adsorbate on an fcc(111) top site
    potentialenergy : float
        the potential energy in eV (e.g., from atoms.get_potential_energy)
        (if potentialenergy is unspecified, then the methods of this class
        can be interpreted as the energy corrections)
    mass : float
        the mass of the adsorbate in amu (if mass is unspecified, then it will
        be calculated from the atoms class)
    inertia : float
        the reduced moment of inertia of the adsorbate in amu*Ang^-2
        (if inertia is unspecified, then it will be calculated from the
        atoms class)
    atoms : an ASE atoms object
        used to calculate rotational moments of inertia and molecular mass
    symmetrynumber : integer
        symmetry number of the adsorbate. This is the number of symmetric arms
        of the adsorbate and depends upon how it is bound to the surface.
        For example, propane bound through its end carbon has a symmetry
        number of 1 but propane bound through its middle carbon has a symmetry
        number of 2. (if symmetrynumber is unspecified, then the default is 1)
    ignore_imag_modes : bool
        If 'True', any imaginary frequencies present after the 3N-3 cut will
        be removed in the calculation of the thermochemical properties.
        If 'False' (default), an error will be raised if imaginary frequencies
        are present after the 3N-3 cut.
    """

    def __init__(self, vib_energies, trans_barrier_energy, rot_barrier_energy,
                 sitedensity, rotationalminima, potentialenergy=0.,
                 mass=None, inertia=None, atoms=None, symmetrynumber=1,
                 ignore_imag_modes: bool = False) -> None:

        self.trans_barrier_energy = trans_barrier_energy * units._e
        self.rot_barrier_energy = rot_barrier_energy * units._e
        self.area = 1. / sitedensity / 100.0**2
        self.rotationalminima = rotationalminima
        self.potentialenergy = potentialenergy
        self.atoms = atoms
        self.symmetry = symmetrynumber

        # Sort the vibrations
        vib_energies = list(vib_energies)
        vib_energies.sort(key=np.abs)

        # Keep only the relevant vibrational energies (3N-3)
        if atoms:
            vib_energies = vib_energies[-(3 * len(atoms) - 3):]
        else:
            vib_energies = vib_energies[-(len(vib_energies) - 3):]

        # Check for imaginary frequencies.
        vib_energies, n_imag = _clean_vib_energies(
            vib_energies, ignore_imag_modes)
        super().__init__(vib_energies=vib_energies)
        self.n_imag = n_imag

        if (mass or atoms) and (inertia or atoms):
            if mass:
                self.mass = mass * units._amu
            elif atoms:
                self.mass = np.sum(atoms.get_masses()) * units._amu
            if inertia:
                self.inertia = inertia * units._amu / units.m**2
            elif atoms:
                # This is tricky because the moments of inertia
                # only work for non-periodic systems.
                # Check it here and raise an error if periodic
                if atoms.get_pbc().any():
                    raise RuntimeError('Atoms object with periodic '
                                       'boundary conditions cannot be '
                                       'used to calculate moments of '
                                       'inertia. Please provide '
                                       'a non-periodic Atoms object.')
                self.inertia = (atoms.get_moments_of_inertia()[2] *
                                units._amu / units.m**2)
        else:
            raise RuntimeError('Either mass and inertia of the '
                               'adsorbate must be specified or '
                               'atoms must be specified.')

        # Calculate hindered translational and rotational frequencies
        self.freq_t = np.sqrt(self.trans_barrier_energy /
                              (2 * self.mass * self.area))
        self.freq_r = 1. / (2 * np.pi) * np.sqrt(self.rotationalminima**2 *
                                                 self.rot_barrier_energy /
                                                 (2 * self.inertia))

    def get_internal_energy(self, temperature, verbose=True):
        """Returns the internal energy (including the zero point energy),
        in eV, in the hindered translator and hindered rotor model at a
        specified temperature (K)."""

        from scipy.special import iv

        self.verbose = verbose
        vprint = self._vprint
        fmt = '%-15s%13.3f eV'
        vprint('Internal energy components at T = %.2f K:' % temperature)
        vprint('=' * 31)

        U = 0.

        vprint(fmt % ('E_pot', self.potentialenergy))
        U += self.potentialenergy

        # Translational Energy
        T_t = units._k * temperature / (units._hplanck * self.freq_t)
        R_t = self.trans_barrier_energy / (units._hplanck * self.freq_t)
        dU_t = 2 * (-1. / 2 - 1. / T_t / (2 + 16 * R_t) + R_t / 2 / T_t -
                    R_t / 2 / T_t *
                    iv(1, R_t / 2 / T_t) / iv(0, R_t / 2 / T_t) +
                    1. / T_t / (np.exp(1. / T_t) - 1))
        dU_t *= units.kB * temperature
        vprint(fmt % ('E_trans', dU_t))
        U += dU_t

        # Rotational Energy
        T_r = units._k * temperature / (units._hplanck * self.freq_r)
        R_r = self.rot_barrier_energy / (units._hplanck * self.freq_r)
        dU_r = (-1. / 2 - 1. / T_r / (2 + 16 * R_r) + R_r / 2 / T_r -
                R_r / 2 / T_r *
                iv(1, R_r / 2 / T_r) / iv(0, R_r / 2 / T_r) +
                1. / T_r / (np.exp(1. / T_r) - 1))
        dU_r *= units.kB * temperature
        vprint(fmt % ('E_rot', dU_r))
        U += dU_r

        # Vibrational Energy
        dU_v = self.get_vib_energy_contribution(temperature)
        vprint(fmt % ('E_vib', dU_v))
        U += dU_v

        # Zero Point Energy
        dU_zpe = self.get_zero_point_energy()
        vprint(fmt % ('E_ZPE', dU_zpe))
        U += dU_zpe

        vprint('-' * 31)
        vprint(fmt % ('U', U))
        vprint('=' * 31)
        return U

    def get_zero_point_energy(self, verbose=True):
        """Returns the zero point energy, in eV, in the hindered
        translator and hindered rotor model"""

        zpe_t = 2 * (1. / 2 * self.freq_t * units._hplanck / units._e)
        zpe_r = 1. / 2 * self.freq_r * units._hplanck / units._e
        zpe_v = self.get_ZPE_correction()
        zpe = zpe_t + zpe_r + zpe_v
        return zpe

    def get_entropy(self, temperature,
                    pressure=units.bar,
                    verbose=True):
        """Returns the entropy, in eV/K, in the hindered translator
        and hindered rotor model at a specified temperature (K)."""

        from scipy.special import iv

        self.verbose = verbose
        vrpint = self._vprint
        fmt = '%-15s%13.7f eV/K%13.3f eV'
        vrpint('Entropy components at T = %.2f K:' % temperature)
        vrpint('=' * 49)
        vrpint('%15s%13s     %13s' % ('', 'S', 'T*S'))

        S = 0.

        # Translational Entropy
        T_t = units._k * temperature / (units._hplanck * self.freq_t)
        R_t = self.trans_barrier_energy / (units._hplanck * self.freq_t)
        S_t = 2 * (-1. / 2 + 1. / 2 * np.log(np.pi * R_t / T_t) -
                   R_t / 2 / T_t *
                   iv(1, R_t / 2 / T_t) / iv(0, R_t / 2 / T_t) +
                   np.log(iv(0, R_t / 2 / T_t)) +
                   1. / T_t / (np.exp(1. / T_t) - 1) -
                   np.log(1 - np.exp(-1. / T_t)))
        S_t *= units.kB
        vrpint(fmt % ('S_trans', S_t, S_t * temperature))
        S += S_t

        # Rotational Entropy
        T_r = units._k * temperature / (units._hplanck * self.freq_r)
        R_r = self.rot_barrier_energy / (units._hplanck * self.freq_r)
        S_r = (-1. / 2 + 1. / 2 * np.log(np.pi * R_r / T_r) -
               np.log(self.symmetry) -
               R_r / 2 / T_r * iv(1, R_r / 2 / T_r) / iv(0, R_r / 2 / T_r) +
               np.log(iv(0, R_r / 2 / T_r)) +
               1. / T_r / (np.exp(1. / T_r) - 1) -
               np.log(1 - np.exp(-1. / T_r)))
        S_r *= units.kB
        vrpint(fmt % ('S_rot', S_r, S_r * temperature))
        S += S_r

        # Vibrational Entropy
        S_v = self.get_vib_entropy_contribution(temperature)
        vrpint(fmt % ('S_vib', S_v, S_v * temperature))
        S += S_v

        # Concentration Related Entropy
        N_over_A = np.exp(1. / 3) * (10.0**5 /
                                     (units._k * temperature))**(2. / 3)
        S_c = 1 - np.log(N_over_A) - np.log(self.area)
        S_c *= units.kB
        vrpint(fmt % ('S_con', S_c, S_c * temperature))
        S += S_c

        vrpint('-' * 49)
        vrpint(fmt % ('S', S, S * temperature))
        vrpint('=' * 49)
        return S

    def get_helmholtz_energy(self, temperature, verbose=True):
        """Returns the Helmholtz free energy, in eV, in the hindered
        translator and hindered rotor model at a specified temperature
        (K)."""

        self.verbose = True
        vprint = self._vprint

        U = self.get_internal_energy(temperature, verbose=verbose)
        vprint('')
        S = self.get_entropy(temperature, verbose=verbose)
        F = U - temperature * S

        vprint('')
        vprint('Free energy components at T = %.2f K:' % temperature)
        vprint('=' * 23)
        fmt = '%5s%15.3f eV'
        vprint(fmt % ('U', U))
        vprint(fmt % ('-T*S', -temperature * S))
        vprint('-' * 23)
        vprint(fmt % ('F', F))
        vprint('=' * 23)
        return F


class IdealGasThermo(BaseThermoChem):
    """Class for calculating thermodynamic properties of a molecule
    based on statistical mechanical treatments in the ideal gas
    approximation.

    Inputs for enthalpy calculations:

    vib_energies : list
        a list of the vibrational energies of the molecule (e.g., from
        ase.vibrations.Vibrations.get_energies). The number of expected
        vibrations is calculated by the geometry and the number of atoms.
        By default, the lowest energies are cut to enforce the expected
        length. By setting vib_selection, this behaviour can be changed.
        If either atoms and natoms is unspecified, the full list is used.
        Units are eV.
    geometry : 'monatomic', 'linear', or 'nonlinear'
        geometry of the molecule
    potentialenergy : float
        the potential energy in eV (e.g., from atoms.get_potential_energy)
        (if potentialenergy is unspecified, then the methods of this
        class can be interpreted as the energy corrections)
    natoms : integer
        the number of atoms, used along with 'geometry' to determine how
        many vibrations to use. (Not needed if an atoms object is supplied
        in 'atoms' or if the user desires the entire list of vibrations
        to be used.)
    vib_selection : 'exact', 'highest' (default), 'abs_highest', 'all'
        selection of input vibrational energies considered to be true
        vibrations (excluding translations and rotations) implied by the
        geometry and number of atoms. Only applied if number of atoms
        is provided, either with natoms or atoms.
        - 'exact': no selection; the number of input vibrational energies must
        be equal to the number of true vibrations
        - 'highest': select vibrational energies whose square is the highest
        , i.e. large real energies followed by small real energies, small
        imaginary energies and large imaginary energies. Will not catch
        unrealistically large imaginary frequencies, resulting from e.g.
        unrelaxed molecules. This is the default.
        - 'abs_highest': select vibrational energies whose absolute number are
        highest, real or imaginary. Will fail intentionally for
        unrealistically large imaginary frequencies, but also unintentionally
        for small real energies, corresponding e.g. to frustrated rotations
        in a larger molecule.
        - 'all': Use all input vibrational energies without checking the
        number of them.
    ignore_imag_modes : bool
        If 'True', any imaginary frequencies present after the 3N-3 cut will
        be removed in the calculation of the thermochemical properties.
        If 'False' (default), an error will be raised if imaginary frequencies
        are present after the 3N-3 cut.

    Extra inputs needed for entropy / free energy calculations:

    atoms : an ASE atoms object
        used to calculate rotational moments of inertia and molecular mass
    symmetrynumber : integer
        symmetry number of the molecule. See, for example, Table 10.1 and
        Appendix B of C. Cramer "Essentials of Computational Chemistry",
        2nd Ed.
    spin : float
        the total electronic spin. (0 for molecules in which all electrons
        are paired, 0.5 for a free radical with a single unpaired electron,
        1.0 for a triplet with two unpaired electrons, such as O_2.)

    """

    def __init__(self, vib_energies: Sequence[complex],
                 geometry: _GEOMETRY_OPTIONS,
                 potentialenergy: float = 0.,
                 atoms: Atoms | None = None,
                 symmetrynumber: int | None = None,
                 spin: float | None = None,
                 natoms: int | None = None,
                 vib_selection: _VIB_SELECTION_OPTIONS | None = 'highest',
                 ignore_imag_modes: bool = False,
                 modes: Sequence[AbstractMode] | None = None) -> None:
        self.potentialenergy = potentialenergy
        self.geometry = geometry
        self.sigma = symmetrynumber
        if natoms is None and atoms:
            natoms = len(atoms)

        # Preliminary sorting vibrations by square
        vib_energies = list(vib_energies)
        vib_energies.sort(key=lambda f: (f ** 2).real)

        if natoms and vib_selection != 'all':
            # Determine number of true vibrations from geometry
            if geometry == 'nonlinear':
                num_vibs = 3 * natoms - 6
            elif geometry == 'linear':
                num_vibs = 3 * natoms - 5
            elif geometry == 'monatomic':
                num_vibs = 0
            else:
                raise ValueError(f"Unsupported geometry: {geometry}")
            if num_vibs < 0:
                raise ValueError(
                    f"Number of atoms ({natoms}) too small for " +
                    f"geometry '{geometry}'."
                )

            if vib_selection == 'exact':
                # Demand the expected number of true vibrations
                if len(vib_energies) != num_vibs:
                    raise ValueError(
                        f"{num_vibs} vibrational energies expected, " +
                        f"{len(vib_energies)} received.\n" +
                        "To select true vibrational energies automatically," +
                        " set vib_selection."
                    )

            elif vib_selection in ('highest', 'abs_highest'):
                # Cut vibrations to get the expected number of true vibrations
                if num_vibs == 0:
                    vib_energies = []
                else:
                    if vib_selection == 'abs_highest':
                        vib_energies.sort(key=np.abs)
                    vib_energies = vib_energies[-num_vibs:]
                if len(vib_energies) != num_vibs:
                    raise ValueError(
                        f"Too few vibration modes ({len(vib_energies)}) " +
                        "after selection. {num_vibs} expected"
                    )
            else:
                raise ValueError(
                    f"(Unsupported vib_selection: {vib_selection})"
                )
        elif not natoms and not atoms and vib_selection != 'all':
            raise ValueError(
                "Either natoms or atoms must be specified to select " +
                "true vibrational energies. Else, set vib_selection to 'all'."
            )

        # Check for imaginary frequencies.
        vib_energies, n_imag = _clean_vib_energies(
            vib_energies, ignore_imag_modes)
        super().__init__(vib_energies=vib_energies,
                         atoms=atoms,
                         spin=spin)
        self.n_imag = n_imag

    def get_internal_energy(self, temperature: float,
                            verbose: bool = True) -> float:
        """Returns the internal energy, in eV, in the ideal gas approximation
        at a specified temperature (K)."""

        self.verbose = verbose
        vprint = self._vprint
        fmt = '%-15s%13.3f eV'
        vprint('Enthalpy components at T = %.2f K:' % temperature)
        vprint('=' * 31)

        U = 0.

        vprint(fmt % ('E_pot', self.potentialenergy))
        U += self.potentialenergy

        zpe = self.get_ZPE_correction()
        vprint(fmt % ('E_ZPE', zpe))
        U += zpe

        Cv_tT = self.get_ideal_translational_energy(temperature)
        vprint(fmt % ('Cv_trans (0->T)', Cv_tT))
        U += Cv_tT

        Cv_rT = self.get_ideal_rotational_energy(self.geometry, temperature)
        vprint(fmt % ('Cv_rot (0->T)', Cv_rT))
        U += Cv_rT

        dU_v = self.get_vib_energy_contribution(temperature)
        vprint(fmt % ('Cv_vib (0->T)', dU_v))
        U += dU_v

        vprint('-' * 31)
        vprint(fmt % ('U', U))
        vprint('=' * 31)
        return U

    def get_enthalpy(self, temperature: float,
                     verbose: bool = True) -> float:
        """Returns the enthalpy, in eV, in the ideal gas approximation
        at a specified temperature (K)."""

        self.verbose = verbose
        vprint = self._vprint
        fmt = '%-15s%13.3f eV'
        vprint('Enthalpy components at T = %.2f K:' % temperature)
        vprint('=' * 31)

        H = 0.
        H += self.get_internal_energy(temperature, verbose=verbose)

        Cp_corr = units.kB * temperature
        vprint(fmt % ('(C_v -> C_p)', Cp_corr))
        H += Cp_corr

        vprint('-' * 31)
        vprint(fmt % ('H', H))
        vprint('=' * 31)
        return H

    def get_entropy(self, temperature: float,
                    pressure: float = units.bar,
                    verbose: bool = True) -> float:
        """Returns the entropy, in eV/K, in the ideal gas approximation
        at a specified temperature (K) and pressure (Pa)."""

        if self.atoms is None or self.sigma is None or self.spin is None:
            raise RuntimeError('atoms, symmetrynumber, and spin must be '
                               'specified for entropy and free energy '
                               'calculations.')
        self.verbose = verbose
        vprint = self._vprint
        fmt = '%-15s%13.7f eV/K%13.3f eV'
        vprint(f'Entropy components at T = {temperature:.2f} K and'
               f' P = {pressure:.1f} Pa:')
        vprint('=' * 49)
        vprint('{"":15s}{"S":13s}     {"T*S:13s}')
        S, S_dict = self.get_ideal_entropy(temperature,
                                           translation=True,
                                           vibration=True,
                                           rotation=True,
                                           geometry=self.geometry,
                                           electronic=True,
                                           pressure=pressure,
                                           symmetrynumber=self.sigma)

        vprint(
            fmt %
            ('S_trans (1 bar)',
                S_dict['S_t'],
                S_dict['S_t'] *
                temperature))
        vprint(fmt % ('S_rot', S_dict['S_r'], S_dict['S_r'] * temperature))
        vprint(fmt % ('S_elec', S_dict['S_e'], S_dict['S_e'] * temperature))
        vprint(fmt % ('S_vib', S_dict['S_v'], S_dict['S_v'] * temperature))
        vprint(
            fmt %
            ('S (1 bar -> P)',
                S_dict['S_p'],
                S_dict['S_p'] * temperature))
        vprint('-' * 49)
        vprint(fmt % ('S', S, S * temperature))
        vprint('=' * 49)
        return S

    def get_gibbs_energy(self, temperature: float,
                         pressure: float,
                         verbose: bool = True) -> float:
        """Returns the Gibbs free energy, in eV, in the ideal gas
        approximation at a specified temperature (K) and pressure (Pa)."""

        self.verbose = verbose
        vprint = self._vprint

        H = self.get_enthalpy(temperature, verbose=verbose)
        vprint('')
        S = self.get_entropy(temperature, pressure=pressure, verbose=verbose)
        G = H - temperature * S

        vprint('')
        vprint('Free energy components at T = %.2f K and P = %.1f Pa:' %
               (temperature, pressure))
        vprint('=' * 23)
        fmt = '%5s%15.3f eV'
        vprint(fmt % ('H', H))
        vprint(fmt % ('-T*S', -temperature * S))
        vprint('-' * 23)
        vprint(fmt % ('G', G))
        vprint('=' * 23)
        return G


class CrystalThermo(BaseThermoChem):
    """Class for calculating thermodynamic properties of a crystalline
    solid in the approximation that a lattice of N atoms behaves as a
    system of 3N independent harmonic oscillators.

    Inputs:

    phonon_DOS : list
        a list of the phonon density of states,
        where each value represents the phonon DOS at the vibrational energy
        value of the corresponding index in phonon_energies.

    phonon_energies : list
        a list of the range of vibrational energies (hbar*omega) over which
        the phonon density of states has been evaluated. This list should be
        the same length as phonon_DOS and integrating phonon_DOS over
        phonon_energies should yield approximately 3N, where N is the number
        of atoms per unit cell. If the first element of this list is
        zero-valued it will be deleted along with the first element of
        phonon_DOS. Units of vibrational energies are eV.

    potentialenergy : float
        the potential energy in eV (e.g., from atoms.get_potential_energy)
        (if potentialenergy is unspecified, then the methods of this
        class can be interpreted as the energy corrections)

    formula_units : int
        the number of formula units per unit cell. If unspecified, the
        thermodynamic quantities calculated will be listed on a
        per-unit-cell basis.
    """

    @classmethod
    def from_transition_state(cls, *args, **kwargs) -> "CrystalThermo":
        """
        Not yet implemented for CrystalThermo but needed to overwrite
        BaseThermoChem method.
        """
        raise NotImplementedError(
            "from_transition_state is not implemented for CrystalThermo."
        )

    def __init__(self, phonon_DOS, phonon_energies,
                 formula_units=None, potentialenergy=0.):
        self.phonon_energies = phonon_energies
        self.phonon_DOS = phonon_DOS

        if formula_units:
            self.formula_units = formula_units
            self.potentialenergy = potentialenergy / formula_units
        else:
            self.formula_units = 0
            self.potentialenergy = potentialenergy

    def get_internal_energy(self, temperature, verbose=True):
        """Returns the internal energy, in eV, of crystalline solid
        at a specified temperature (K)."""

        self.verbose = verbose
        vprint = self._vprint
        fmt = '%-15s%13.4f eV'
        if self.formula_units == 0:
            vprint('Internal energy components at '
                   'T = %.2f K,\non a per-unit-cell basis:' % temperature)
        else:
            vprint('Internal energy components at '
                   'T = %.2f K,\non a per-formula-unit basis:' % temperature)
        vprint('=' * 31)

        U = 0.

        omega_e = self.phonon_energies
        dos_e = self.phonon_DOS
        if omega_e[0] == 0.:
            omega_e = np.delete(omega_e, 0)
            dos_e = np.delete(dos_e, 0)

        vprint(fmt % ('E_pot', self.potentialenergy))
        U += self.potentialenergy

        zpe_list = omega_e / 2.
        if self.formula_units == 0:
            zpe = trapezoid(zpe_list * dos_e, omega_e)
        else:
            zpe = trapezoid(zpe_list * dos_e, omega_e) / self.formula_units
        vprint(fmt % ('E_ZPE', zpe))
        U += zpe

        B = 1. / (units.kB * temperature)
        E_vib = omega_e / (np.exp(omega_e * B) - 1.)
        if self.formula_units == 0:
            E_phonon = trapezoid(E_vib * dos_e, omega_e)
        else:
            E_phonon = trapezoid(E_vib * dos_e, omega_e) / self.formula_units
        vprint(fmt % ('E_phonon', E_phonon))
        U += E_phonon

        vprint('-' * 31)
        vprint(fmt % ('U', U))
        vprint('=' * 31)
        return U

    def get_entropy(self, temperature, verbose=True):
        """Returns the entropy, in eV/K, of crystalline solid
        at a specified temperature (K)."""

        self.verbose = verbose
        vprint = self._vprint
        fmt = '%-15s%13.7f eV/K%13.4f eV'
        if self.formula_units == 0:
            vprint('Entropy components at '
                   'T = %.2f K,\non a per-unit-cell basis:' % temperature)
        else:
            vprint('Entropy components at '
                   'T = %.2f K,\non a per-formula-unit basis:' % temperature)
        vprint('=' * 49)
        vprint('%15s%13s     %13s' % ('', 'S', 'T*S'))

        omega_e = self.phonon_energies
        dos_e = self.phonon_DOS
        if omega_e[0] == 0.:
            omega_e = np.delete(omega_e, 0)
            dos_e = np.delete(dos_e, 0)

        B = 1. / (units.kB * temperature)
        S_vib = (omega_e / (temperature * (np.exp(omega_e * B) - 1.)) -
                 units.kB * np.log(1. - np.exp(-omega_e * B)))
        if self.formula_units == 0:
            S = trapezoid(S_vib * dos_e, omega_e)
        else:
            S = trapezoid(S_vib * dos_e, omega_e) / self.formula_units

        vprint('-' * 49)
        vprint(fmt % ('S', S, S * temperature))
        vprint('=' * 49)
        return S

    def get_helmholtz_energy(self, temperature, verbose=True):
        """Returns the Helmholtz free energy, in eV, of crystalline solid
        at a specified temperature (K)."""

        self.verbose = True
        vprint = self._vprint

        U = self.get_internal_energy(temperature, verbose=verbose)
        vprint('')
        S = self.get_entropy(temperature, verbose=verbose)
        F = U - temperature * S

        vprint('')
        if self.formula_units == 0:
            vprint('Helmholtz free energy components at '
                   'T = %.2f K,\non a per-unit-cell basis:' % temperature)
        else:
            vprint('Helmholtz free energy components at '
                   'T = %.2f K,\non a per-formula-unit basis:' % temperature)
        vprint('=' * 23)
        fmt = '%5s%15.4f eV'
        vprint(fmt % ('U', U))
        vprint(fmt % ('-T*S', -temperature * S))
        vprint('-' * 23)
        vprint(fmt % ('F', F))
        vprint('=' * 23)
        return F


def _clean_vib_energies(vib_energies: Sequence[complex],
                        ignore_imag_modes: bool = False
                        ) -> tuple[Sequence[float], int]:
    """Checks and deal with the presence of imaginary vibrational modes

    Also removes +0.j from real vibrational energies.

    Inputs:

    vib_energies : list
        a list of the vibrational energies

    ignore_imag_modes : bool
        If 'True', any imaginary frequencies will be removed.
        If 'False' (default), an error will be raised if imaginary
        frequencies are present.

    Outputs:

    vib_energies : list
        a list of the real vibrational energies.

    n_imag : int
        the number of imaginary frequencies treated.
    """
    # raise to a value, accept int and float in contrast to documentation
    if ignore_imag_modes:
        n_vib_energies = len(vib_energies)
        vib_energies = [np.real(v) for v in vib_energies if np.real(v) > 0]
        n_imag = n_vib_energies - len(vib_energies)
        if n_imag > 0:
            warn(f"{n_imag} imag modes removed", UserWarning)
    else:
        if sum(np.iscomplex(vib_energies)):
            raise ValueError('Imaginary vibrational energies are present.')
        n_imag = 0
    ret = [np.real(v) for v in vib_energies]  # clear +0.j

    return ret, n_imag
