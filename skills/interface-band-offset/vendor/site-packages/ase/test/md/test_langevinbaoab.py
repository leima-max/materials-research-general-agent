import numpy as np
import pytest
import scipy

import ase.io
from ase.atoms import Atoms
from ase.calculators.morse import MorsePotential
from ase.md.langevinbaoab import LangevinBAOAB
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase.neighborlist import neighbor_list
from ase.units import GPa as u_GPa
from ase.units import fs as u_fs

timestep = 2.5 * u_fs
a0 = 4.0
n_steps = 10


@pytest.fixture
def calc():
    # sort of matches real Al
    return MorsePotential(
        r0=2.04 * np.sqrt(2), epsilon=0.07, neighbor_list=neighbor_list
    )


@pytest.fixture
def atoms():
    atoms = Atoms(
        'Al' * 4,
        cell=[a0] * 3,
        scaled_positions=[
            [0, 0, 0],
            [0.5, 0.5, 0],
            [0.5, 0, 0.5],
            [0, 0.5, 0.5],
        ],
        pbc=[True] * 3,
    )
    atoms.cell[2] += atoms.cell[0]
    atoms *= 3
    return atoms


####################################################################################################
# NVT - atoms move, fixed cell


def test_LangevinBAOAB_NVT(tmp_path, atoms, calc):
    atoms.calc = calc
    rng = np.random.default_rng(seed=5)
    dyn = LangevinBAOAB(
        atoms,
        timestep=timestep,
        temperature_K=300,
        T_tau=50 * timestep,
        rng=rng,
        trajectory=str(tmp_path / 'test.traj'),
    )
    dyn.run(n_steps)

    traj = ase.io.read(tmp_path / 'test.traj', ':')

    # atoms moved, fixed cell
    assert np.any(traj[0].positions != traj[-1].positions), "atoms didn't move"
    assert np.all(traj[0].cell == traj[-1].cell), 'cell not fixed'


####################################################################################################
# NPT - atoms move, cell changes volume but not shape


def test_LangevinBAOAB_NPT(tmp_path, atoms, calc):
    atoms.calc = calc
    rng = np.random.default_rng(seed=5)
    # expect warning about using heuristics for T_tau and/or P_tau
    warnings = [
        r'Got `externalstress` but missing `P_tau`, got `T_tau`,',
        r'Using heuristic P_mass',
    ]
    with pytest.warns(UserWarning, match='|'.join(warnings)):
        dyn = LangevinBAOAB(
            atoms,
            timestep=timestep,
            temperature_K=300,
            T_tau=50 * timestep,
            externalstress=-1.0 * u_GPa,
            hydrostatic=True,
            rng=rng,
            trajectory=str(tmp_path / 'test.traj'),
        )

    dyn.run(n_steps)

    traj = ase.io.read(tmp_path / 'test.traj', ':')

    # atoms moved
    assert np.any(
        traj[0].get_scaled_positions() != traj[-1].get_scaled_positions()
    ), "atoms didn't move"

    # fixed shape, variable vol
    ratio = traj[-1].cell[0, 0] / traj[0].cell[0, 0]
    print('ratio', ratio)
    print('initial cell')
    print(traj[0].cell)
    print('final cell')
    print(traj[-1].cell)
    assert np.abs(ratio - 1.0) > 1e-6, "cell size didn't change"
    assert np.all(np.abs(traj[0].cell * ratio - traj[-1].cell) < 1e-6), (
        'cell shape changed'
    )


####################################################################################################
# NsT - atoms move, cell changes volume and shape


def test_LangevinBAOAB_NsT(tmp_path, atoms, calc):
    atoms.calc = calc
    rng = np.random.default_rng(seed=7)
    externalstress_GPa = -1.0  # -np.asarray([0.2, 0.4, 0.6, 0.1, 0.0, 0.0])
    # expect warning about using heuristics for T_tau and/or P_tau
    warnings = [
        r'Got `externalstress` but missing `P_tau`, got `T_tau`,',
        r'Using heuristic P_mass',
    ]
    with pytest.warns(UserWarning, match='|'.join(warnings)):
        dyn = LangevinBAOAB(
            atoms,
            timestep=timestep,
            temperature_K=300,
            T_tau=50 * timestep,
            externalstress=externalstress_GPa * u_GPa,
            rng=rng,
            trajectory=str(tmp_path / 'test.traj'),
        )

    dyn.run(n_steps)

    traj = ase.io.read(tmp_path / 'test.traj', ':')

    # atoms and cell changed
    assert np.any(
        traj[0].get_scaled_positions() != traj[-1].get_scaled_positions()
    ), "atoms didn't move"
    assert np.all(np.abs(traj[0].cell - traj[-1].cell) > 1e-6), (
        "cell shape didn't change"
    )

    # make sure there was no rotation
    # ai @ F = af
    F = np.linalg.inv(traj[0].cell) @ traj[-1].cell
    u, p = scipy.linalg.polar(F)
    assert np.allclose(u, np.eye(3), atol=0.01)


def test_LangevinBAOAB_NsH(tmp_path, atoms, calc):
    atoms.calc = calc
    rng = np.random.default_rng(seed=7)

    # log barostat quantities in atoms object so conservation of enthalpy can
    # be checked
    def log_barostat():
        atoms.info['p_eps'] = dyn.p_eps
        atoms.info['barostat_mass'] = dyn.barostat_mass

    externalstress_GPa = 0.0
    MaxwellBoltzmannDistribution(atoms, temperature_K=300, rng=rng)
    # expect warning about using heuristics for T_tau and/or P_tau
    warnings = [
        r'Got `externalstress` but missing `P_tau` and `T_tau`,',
        r'Using heuristic P_mass',
    ]
    with pytest.warns(UserWarning, match='|'.join(warnings)):
        dyn = LangevinBAOAB(
            atoms,
            timestep=timestep,
            externalstress=externalstress_GPa * u_GPa,
            rng=rng,
            trajectory=str(tmp_path / 'test.traj'),
        )
    dyn.attach(log_barostat)
    dyn.run(n_steps * 3)
    traj = ase.io.read(tmp_path / 'test.traj', ':')

    E = np.asarray(
        [
            atoms.get_potential_energy() + atoms.get_kinetic_energy()
            for atoms in traj
        ]
    )

    P = -externalstress_GPa * u_GPa
    V = np.asarray([atoms.get_volume() for atoms in traj])

    d_p_eps = [np.asarray(atoms.info.get('p_eps', 0.0)) for atoms in traj]
    d_p_eps = [
        p_eps.reshape((int(np.sqrt(p_eps.size)), int(np.sqrt(p_eps.size))))
        for p_eps in d_p_eps
    ]
    barostat_mass = traj[-1].info['barostat_mass']
    KE_cell = np.asarray(
        [np.trace(p_eps @ p_eps.T) / (barostat_mass * 2) for p_eps in d_p_eps]
    )

    H = E + P * V + KE_cell

    assert np.max(E) - np.min(E) > 3.0 * (np.max(H) - np.min(H)), (
        'enthalpy is not conserved much better than energy'
    )

    # atoms and cell changed
    assert np.any(
        traj[0].get_scaled_positions() != traj[-1].get_scaled_positions()
    ), "atoms didn't move"
    assert np.all(np.abs(traj[0].cell - traj[-1].cell) > 1e-6), (
        "cell shape didn't change"
    )


def test_LangevinBAOAB_seed(tmp_path, atoms, calc):
    atoms.calc = calc
    # expect warning about using heuristics for T_tau and/or P_tau
    warnings = [
        r'No rng provided, generated one with',
        r'Got `externalstress` but missing `P_tau`, got `T_tau`,',
        'Using heuristic P_mass',
    ]
    with pytest.warns(UserWarning, match='|'.join(warnings)):
        _ = LangevinBAOAB(
            atoms,
            timestep=timestep,
            temperature_K=300,
            T_tau=50 * timestep,
            externalstress=-1.0 * u_GPa,
            hydrostatic=True,
            trajectory=str(tmp_path / 'test.traj'),
        )


def test_LangevinBAOAB_default_rng(atoms, calc):
    """Test LangevinBAOAB can be initialised with rng=None"""
    atoms.calc = calc

    with pytest.warns(
        UserWarning, match='No rng provided, generated one with seed'
    ):
        dyn = LangevinBAOAB(
            atoms,
            timestep=timestep,
            temperature_K=300,
            T_tau=50 * timestep,
            rng=None,
        )

    dyn.run(n_steps)
