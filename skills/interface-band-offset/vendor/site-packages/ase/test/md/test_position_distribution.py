"""Tests for the position distribution."""

import numpy as np
from scipy.integrate import simpson
from scipy.stats import gaussian_kde

from ase import Atoms, units
from ase.calculators.morse import MorsePotential
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution

# Morse potential parameters of O2 in the ground state
# D. D. Konowalow and J. O. Hirschfelder, Phys. Fluids 4, 637 (1961).
# https://doi.org/10.1063/1.1706374
epsilon = 5.211
r0 = 1.207
rho0 = 2.78


def run(temperature_K: float) -> np.ndarray:
    # Create O2 molecule
    atoms = Atoms('O2', positions=[[0, 0, -0.5 * r0], [0, 0, +0.5 * r0]])

    # Morse potential
    atoms.calc = MorsePotential(epsilon=epsilon, rho0=rho0, r0=r0)

    rng = np.random.default_rng(42)

    # Initialize velocities
    MaxwellBoltzmannDistribution(atoms, temperature_K=temperature_K, rng=rng)

    steps = 1000
    distances = np.full(steps + 1, np.nan)
    with Langevin(
        atoms,
        timestep=1.0 * units.fs,
        temperature_K=temperature_K,
        friction=0.01 / units.fs,
        fixcm=False,
        rng=rng,
    ) as dyn:
        for i, _ in enumerate(dyn.irun(steps)):
            distances[i] = atoms.get_distance(0, 1)

    return distances


def calc_potential(d: np.ndarray) -> np.ndarray:
    """Calculate a Morse potential."""
    expf = np.exp(rho0 * (1.0 - d / r0))
    return epsilon * expf * (expf - 2.0)


def test_position_distribution():
    """Test if the position distribution of the NVT emsemble is reproduced."""
    temperature_K = 300.0

    grid = np.linspace(0.0, 2.0, 201)
    potential = calc_potential(grid)

    pdf_ref = np.exp(-potential / (units.kB * temperature_K))
    pdf_ref *= grid**2  # angular contribution in 3D
    pdf_ref /= simpson(pdf_ref, grid)  # normalization

    distances = run(temperature_K=temperature_K)
    pdf = gaussian_kde(distances)(grid)

    # replace zero with a tiny value
    eps = np.finfo(float).eps
    pdf = np.where(pdf == 0.0, eps, pdf)
    pdf_ref = np.where(pdf_ref == 0.0, eps, pdf_ref)

    # KL divergence
    kl_div = simpson(pdf * np.log(pdf / pdf_ref), grid)
    print(kl_div)
    assert kl_div < 0.05
