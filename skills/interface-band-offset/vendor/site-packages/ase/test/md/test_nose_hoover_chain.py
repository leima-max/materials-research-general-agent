# fmt: off
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

import ase.build
import ase.units
from ase import Atoms
from ase.md.nose_hoover_chain import (
    MTKNPT,
    IsotropicMTKBarostat,
    IsotropicMTKNPT,
    MaskedMTKNPT,
    MTKBarostat,
    NoseHooverChainNVT,
    NoseHooverChainThermostat,
)
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary


@pytest.fixture
def hcp_Cu() -> Atoms:
    atoms = ase.build.bulk(
        "Cu", crystalstructure='hcp', a=2.53, c=4.11
    ).repeat(2)
    return atoms


@pytest.mark.parametrize("tchain", [1, 3])
@pytest.mark.parametrize("tloop", [1, 3])
def test_thermostat_round_trip(hcp_Cu: Atoms, tchain: int, tloop: int):
    atoms = hcp_Cu.copy()

    timestep = 1.0 * ase.units.fs
    thermostat = NoseHooverChainThermostat(
        num_atoms_global=len(atoms),
        masses=atoms.get_masses()[:, None],
        temperature_K=1000,
        tdamp=100 * timestep,
        tchain=tchain,
        tloop=tloop,
    )

    rng = np.random.default_rng(0)
    p = rng.standard_normal(size=(len(atoms), 3))

    # Forward `n` steps and backward `n` steps with`, which should go back to
    # the initial state.
    n = 1000
    p_start = p.copy()
    eta_start = thermostat._eta.copy()
    p_eta_start = thermostat._p_eta.copy()

    for _ in range(n):
        p = thermostat.integrate_nhc(p, timestep)
    assert not np.allclose(p, p_start, atol=1e-6)
    assert not np.allclose(thermostat._eta, eta_start, atol=1e-6)
    assert not np.allclose(thermostat._p_eta, p_eta_start, atol=1e-6)

    for _ in range(n):
        p = thermostat.integrate_nhc(p, -timestep)
    assert np.allclose(p, p_start, atol=1e-6)

    # These values are apparently very machine-dependent:
    assert np.allclose(thermostat._eta, eta_start, atol=1e-5)
    assert np.allclose(thermostat._p_eta, p_eta_start, atol=1e-4)


@pytest.mark.parametrize("tchain", [1, 3])
@pytest.mark.parametrize("tloop", [1, 3])
def test_thermostat_truncation_error(hcp_Cu: Atoms, tchain: int, tloop: int):
    """Compare thermostat integration with delta by n steps and delta/2 by 2n
    steps. The difference between the two results should decrease with delta
    until reaching rounding error.
    """
    atoms = hcp_Cu.copy()

    delta0 = 1e-1
    n = 100
    m = 10

    list_p_diff = []
    list_eta_diff = []
    list_p_eta_diff = []
    for i in range(m):
        delta = delta0 * (2 ** -i)
        thermostat = NoseHooverChainThermostat(
            num_atoms_global=len(atoms),
            masses=atoms.get_masses()[:, None],
            temperature_K=1000,
            tdamp=100 * delta0,
            tchain=tchain,
            tloop=tloop,
        )

        rng = np.random.default_rng(0)
        p = rng.standard_normal(size=(len(atoms), 3))
        thermostat._eta = rng.standard_normal(size=(tchain, ))
        thermostat._p_eta = rng.standard_normal(size=(tchain, ))

        thermostat1 = deepcopy(thermostat)
        p1 = p.copy()
        for _ in range(n):
            p1 = thermostat1.integrate_nhc(p1, delta)

        thermostat2 = deepcopy(thermostat)
        p2 = p.copy()
        for _ in range(2 * n):
            p2 = thermostat2.integrate_nhc(p2, delta / 2)

        # O(delta^3) truncation error
        list_p_diff.append(np.linalg.norm(p1 - p2))
        list_eta_diff.append(
            np.linalg.norm(thermostat1._eta - thermostat2._eta)
        )
        list_p_eta_diff.append(
            np.linalg.norm(thermostat1._p_eta - thermostat2._p_eta)
        )

    print(np.array(list_p_diff))
    print(np.array(list_eta_diff))
    print(np.array(list_p_eta_diff))

    # Check that the differences decrease with delta until reaching rounding
    # error.
    eps = 1e-12
    for i in range(1, m):
        assert (
            (list_p_diff[i] < eps)
            or (list_p_diff[i] < list_p_diff[i - 1])
        )
        assert (
            (list_eta_diff[i] < eps)
            or (list_eta_diff[i] < list_eta_diff[i - 1])
        )
        assert (
            (list_p_eta_diff[i] < eps)
            or (list_p_eta_diff[i] < list_p_eta_diff[i - 1])
        )


@pytest.mark.parametrize("pchain", [1, 3])
@pytest.mark.parametrize("ploop", [1, 3])
def test_isotropic_barostat(asap3, hcp_Cu: Atoms, pchain: int, ploop: int):
    atoms = hcp_Cu.copy()
    atoms.calc = asap3.EMT()

    timestep = 1.0 * ase.units.fs
    barostat = IsotropicMTKBarostat(
        num_atoms_global=len(atoms),
        temperature_K=1000,
        pdamp=1000 * timestep,
        pchain=pchain,
        ploop=ploop,
    )

    rng = np.random.default_rng(0)
    p_eps = float(rng.standard_normal())

    # Forward `n` steps and backward `n` steps with`, which should go back to
    # the initial state.
    n = 1000
    p_eps_start = p_eps
    xi_start = barostat._xi.copy()
    p_xi_start = barostat._p_xi.copy()
    for _ in range(n):
        p_eps = barostat.integrate_nhc_baro(p_eps, timestep)
    assert not np.allclose(p_eps, p_eps_start, atol=1e-6)
    assert not np.allclose(barostat._xi, xi_start, atol=1e-6)
    assert not np.allclose(barostat._p_xi, p_xi_start, atol=1e-6)

    for _ in range(n):
        p_eps = barostat.integrate_nhc_baro(p_eps, -timestep)
    assert np.allclose(p_eps, p_eps_start, atol=1e-6)
    assert np.allclose(barostat._xi, xi_start, atol=1e-6)
    assert np.allclose(barostat._p_xi, p_xi_start, atol=1e-6)


@pytest.mark.parametrize("pchain", [1, 3])
@pytest.mark.parametrize("ploop", [1, 3])
@pytest.mark.parametrize("mask",
    [
        pytest.param(None, id="aniso"),
        pytest.param((True, False, False), id='uniaxial'),
        pytest.param((True, True, False), id='biaxial'),
        pytest.param((True, True, True), id='iso'),
    ]
)
def test_anisotropic_barostat(
    asap3,
    hcp_Cu: Atoms,
    pchain: int,
    ploop: int,
    mask: tuple[bool, bool, bool] | None,
):
    atoms = hcp_Cu.copy()
    atoms.calc = asap3.EMT()

    timestep = 1.0 * ase.units.fs
    barostat = MTKBarostat(
        num_atoms_global=len(atoms),
        temperature_K=1000,
        pdamp=1000 * timestep,
        pchain=pchain,
        ploop=ploop,
        mask=mask,
    )

    rng = np.random.default_rng(0)
    p_g = rng.standard_normal((3, 3))
    p_g = 0.5 * (p_g + p_g.T)

    n = 1000
    p_g_start = p_g.copy()
    xi_start = barostat._xi.copy()
    p_xi_start = barostat._p_xi.copy()

    for _ in range(n):
        p_g = barostat.integrate_nhc_baro(p_g, timestep)
    # extended variables should be updated by n * timestep
    assert not np.allclose(p_g, p_g_start, atol=1e-6)
    assert not np.allclose(barostat._xi, xi_start, atol=1e-6)
    assert not np.allclose(barostat._p_xi, p_xi_start, atol=1e-6)

    for _ in range(n):
        p_g = barostat.integrate_nhc_baro(p_g, -timestep)
    # Now, the extended variables should be back to the initial state
    assert np.allclose(p_g, p_g_start, atol=1e-6)
    assert np.allclose(barostat._xi, xi_start, atol=1e-6)
    assert np.allclose(barostat._p_xi, p_xi_start, atol=1e-6)


@pytest.mark.parametrize("tchain", [1, 3])
def test_nose_hoover_chain_nvt(asap3, tchain: int):
    atoms = ase.build.bulk("Cu").repeat((2, 2, 2))
    atoms.calc = asap3.EMT()

    temperature_K = 300
    rng = np.random.default_rng(0)
    MaxwellBoltzmannDistribution(
        atoms,
        temperature_K=temperature_K, force_temp=True, rng=rng
    )
    Stationary(atoms)

    timestep = 1.0 * ase.units.fs
    md = NoseHooverChainNVT(
        atoms,
        timestep=timestep,
        temperature_K=temperature_K,
        tdamp=100 * timestep,
        tchain=tchain,
    )
    conserved_energy1 = md.get_conserved_energy()
    md.run(100)
    conserved_energy2 = md.get_conserved_energy()
    assert np.allclose(np.sum(atoms.get_momenta(), axis=0), 0.0)
    assert np.isclose(conserved_energy1, conserved_energy2, atol=1e-3)


@pytest.mark.parametrize("tchain", [1, 3])
@pytest.mark.parametrize("pchain", [1, 3])
def test_isotropic_mtk_npt(asap3, hcp_Cu: Atoms, tchain: int, pchain: int):
    atoms = hcp_Cu.copy()
    atoms.calc = asap3.EMT()

    temperature_K = 300
    rng = np.random.default_rng(0)
    MaxwellBoltzmannDistribution(
        atoms,
        temperature_K=temperature_K, force_temp=True, rng=rng
    )
    Stationary(atoms)

    timestep = 1.0 * ase.units.fs
    md = IsotropicMTKNPT(
        atoms,
        timestep=timestep,
        temperature_K=temperature_K,
        pressure_au=10.0 * ase.units.GPa,
        tdamp=100 * timestep,
        pdamp=1000 * timestep,
        tchain=tchain,
        pchain=pchain,
    )

    conserved_energy1 = md.get_conserved_energy()
    md.run(100)
    conserved_energy2 = md.get_conserved_energy()
    assert np.allclose(np.sum(atoms.get_momenta(), axis=0), 0.0)
    assert np.isclose(conserved_energy1, conserved_energy2, atol=1e-3)


@pytest.mark.parametrize("tchain", [1, 3])
@pytest.mark.parametrize("pchain", [1, 3])
def test_anisotropic_npt(asap3, hcp_Cu: Atoms, tchain: int, pchain: int):
    atoms = hcp_Cu.copy()
    atoms.calc = asap3.EMT()

    temperature_K = 300
    rng = np.random.default_rng(0)
    MaxwellBoltzmannDistribution(
        atoms,
        temperature_K=temperature_K, force_temp=True, rng=rng
    )
    Stationary(atoms)

    timestep = 1.0 * ase.units.fs
    md = MTKNPT(
        atoms,
        timestep=timestep,
        temperature_K=temperature_K,
        pressure_au=10.0 * ase.units.GPa,
        tdamp=100 * timestep,
        pdamp=1000 * timestep,
        tchain=tchain,
        pchain=pchain,
    )
    conserved_energy1 = md.get_conserved_energy()
    positions1 = atoms.get_positions().copy()
    md.run(100)
    conserved_energy2 = md.get_conserved_energy()
    assert np.allclose(np.sum(atoms.get_momenta(), axis=0), 0.0)
    assert np.isclose(conserved_energy1, conserved_energy2, atol=1e-3)
    assert not np.allclose(atoms.get_positions(), positions1, atol=1e-6)


@pytest.mark.parametrize("tchain", [1, 3])
@pytest.mark.parametrize("pchain", [1, 3])
@pytest.mark.parametrize("mask",
    [
        pytest.param((True, False, False), id='uniaxial-a'),
        pytest.param((False, False, True), id='uniaxial-c'),
        pytest.param((True, True, False), id='biaxial-a-b'),
        pytest.param((True, False, True), id='biaxial-a-c'),
        pytest.param((True, True, True), id='triaxial'),
    ]
)
def test_masked_npt(
    asap3,
    hcp_Cu: Atoms,
    tchain: int,
    pchain: int,
    mask: tuple[bool, bool, bool]
):
    atoms = hcp_Cu.copy()
    atoms.calc = asap3.EMT()

    temperature_K = 300
    rng = np.random.default_rng(0)
    MaxwellBoltzmannDistribution(
        atoms,
        temperature_K=temperature_K, force_temp=True, rng=rng
    )
    Stationary(atoms)

    timestep = 1.0 * ase.units.fs
    md = MaskedMTKNPT(
        atoms,
        timestep=timestep,
        temperature_K=temperature_K,
        pressure_au=10.0 * ase.units.GPa,
        mask=mask,
        tdamp=100 * timestep,
        pdamp=1000 * timestep,
        tchain=tchain,
        pchain=pchain,
    )
    conserved_energy1 = md.get_conserved_energy()
    positions1 = atoms.get_positions().copy()
    md.run(100)
    conserved_energy2 = md.get_conserved_energy()
    assert np.allclose(np.sum(atoms.get_momenta(), axis=0), 0.0)
    assert np.isclose(conserved_energy1, conserved_energy2, atol=1e-3)
    assert not np.allclose(atoms.get_positions(), positions1, atol=1e-6)
