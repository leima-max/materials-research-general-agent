"""Tests for RDFs."""

import numpy as np
import pytest

from ase import Atoms
from ase.build.bulk import bulk
from ase.build.molecule import molecule
from ase.calculators.emt import EMT
from ase.cluster import Icosahedron
from ase.geometry.rdf import (
    CellTooSmall,
    VolumeNotDefined,
    get_rdf,
    get_volume_estimate,
)
from ase.lattice.compounds import L1_2
from ase.optimize.fire import FIRE


@pytest.fixture()
def atoms_h2():
    return molecule('H2')


def test_rdf_providing_volume_argument(atoms_h2):
    volume_estimate = get_volume_estimate(atoms_h2)
    rdf, dists = get_rdf(atoms_h2, 2.0, 5, volume=volume_estimate)

    rdf_ref = (0.0, 2.91718861, 0.0, 0.0, 0.0)
    dists_ref = (0.2, 0.6, 1.0, 1.4, 1.8)
    assert rdf == pytest.approx(rdf_ref)
    assert dists == pytest.approx(dists_ref)


def test_rdf_volume_not_defined_exception(atoms_h2):
    with pytest.raises(VolumeNotDefined):
        get_rdf(atoms_h2, 2.0, 5)


def test_rdf_cell_too_small_exception():
    with pytest.raises(CellTooSmall):
        get_rdf(bulk('Ag'), 2.0, 5)


def test_rdf_compute():
    eps = 1e-5

    atoms = Icosahedron('Cu', 3)
    atoms.center(vacuum=0.0)
    atoms.numbers[[0, 13, 15, 16, 18, 19, 21, 22, 24, 25, 27, 28, 30]] = 79
    atoms.calc = EMT()
    with FIRE(atoms, logfile=None) as opt:
        opt.run(fmax=0.05)

    rmax = 8.0
    nbins = 5
    rdf, dists = get_rdf(atoms, rmax, nbins)
    calc_dists = np.arange(rmax / (2 * nbins), rmax, rmax / nbins)
    assert all(abs(dists - calc_dists) < eps)
    reference_rdf1 = [0.0, 0.84408157, 0.398689, 0.23748934, 0.15398546]
    assert all(abs(rdf - reference_rdf1) < eps)


def test_bulk() -> None:
    """Test RDFs for crystalline sytems."""
    eps = 1e-5
    atoms = L1_2(['Au', 'Cu'], size=(3, 3, 3), latticeconstant=2 * np.sqrt(2))
    rdf = get_rdf(atoms, 4.2, 5)[0]
    reference_rdf2 = [0.0, 0.0, 1.43905094, 0.36948605, 1.34468694]
    assert all(abs(rdf - reference_rdf2) < eps)


def test_neighborlist_vs_distance_matrix():
    eps = 1e-5
    elements = (18, 18)
    atoms = bulk('Ar', 'fcc', cubic=True).repeat(2)

    dm = atoms.get_all_distances(mic=True)
    rdf_dm, dists_dm = get_rdf(atoms, 4.0, 5, distance_matrix=dm)
    rdf_nl, dists_nl = get_rdf(atoms, 4.0, 5)

    rdf_dm_e, dists_dm_e = get_rdf(
        atoms, 4.0, 5, distance_matrix=dm, elements=elements
    )
    rdf_nl_e, dists_nl_e = get_rdf(atoms, 4.0, 5, elements=elements)

    assert all(abs(rdf_dm - rdf_nl) < eps)
    assert all(abs(dists_dm - dists_nl) < eps)

    assert all(abs(rdf_dm_e - rdf_nl_e) < eps)
    assert all(abs(dists_dm_e - dists_nl_e) < eps)


def test_partial_rdfs() -> None:
    """Test if partial RDFs satisfy the required conditions."""
    rng = np.random.default_rng(42)

    atoms: Atoms = bulk('Cu', 'fcc', cubic=True) * 4  # 256 atoms

    # replace 1/4 by Au randomly
    indices = rng.choice(len(atoms), size=len(atoms) // 4, replace=False)
    atoms.symbols[indices] = 'Au'

    # concentrations of Cu and Au
    concs = {}
    for c in [29, 79]:
        concs[c] = np.count_nonzero(atoms.numbers == c) / len(atoms)

    atoms.rattle(0.1, rng=rng)

    rmax = 6.0
    nbins = 100

    rdf_total = get_rdf(atoms, rmax, nbins)[0]

    rdfs_partial = {}
    rdf_weighted_average = np.zeros_like(rdf_total)
    for c0, c1 in ((29, 29), (29, 79), (79, 29), (79, 79)):
        rdf_partial = get_rdf(atoms, rmax, nbins, elements=[c0, c1])[0]
        rdfs_partial[(c0, c1)] = rdf_partial
        rdf_weighted_average += concs[c0] * concs[c1] * rdf_partial

    np.testing.assert_allclose(rdfs_partial[(29, 79)], rdfs_partial[(79, 29)])
    np.testing.assert_allclose(rdf_total, rdf_weighted_average)


def test_elements() -> None:
    """Test if chemical symbols can be specified for `elements`."""
    atoms = L1_2(['Au', 'Cu'], size=(3, 3, 3), latticeconstant=2 * np.sqrt(2))
    rmax = 4.2
    nbins = 100
    rdf0 = get_rdf(atoms, rmax=rmax, nbins=nbins, elements=[79, 29])[0]
    rdf1 = get_rdf(atoms, rmax=rmax, nbins=nbins, elements=['Au', 'Cu'])[0]
    np.testing.assert_array_equal(rdf0, rdf1)
