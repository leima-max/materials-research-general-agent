import numpy as np
import pytest

import ase.lattice as lattice


@pytest.mark.parametrize(
    'lat',
    [
        lattice.ORCI(2.1, 3.2, 4.3),
        lattice.CRECT(2.1, 80.0),
    ],
)
@pytest.mark.parametrize('noise', [0.0, 1e-6, 1e-4, 1e-2, 1e-1])
def test_match_to_lattice(lat: lattice.BravaisLattice, noise: float):
    rng = np.random.RandomState(42)

    ndim = lat.ndim
    cell = lat.tocell()
    eps = noise * rng.random((ndim, ndim))
    cell[:ndim, :ndim] += eps  # type: ignore[index]

    match = min(
        lattice.match_to_lattice(cell, lat.name), key=lambda match: match.error
    )

    tolerance = 2 * noise + 1e-12
    assert 0.01 * noise <= match.error < tolerance
    assert match.lat.name == lat.name
    assert lattice.celldiff(match.lat.tocell(), lat.tocell()) < tolerance
