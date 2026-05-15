import numpy as np
import pytest

from ase.build import bulk
from ase.calculators.test import FreeElectrons
from ase.dft.kpoints import special_paths
from ase.lattice import RHL
from ase.spectrum.band_structure import BandStructure


@pytest.fixture()
def bs_cu():
    atoms = bulk('Cu')
    path = special_paths['fcc']
    atoms.calc = FreeElectrons(nvalence=1, kpts={'path': path, 'npoints': 200})
    atoms.get_potential_energy()
    return atoms.calc.band_structure()


@pytest.fixture()
def bs_spin(bs_cu):
    # Artificially add a second spin channel for testing
    return BandStructure(
        path=bs_cu.path,
        energies=np.array([bs_cu.energies[0], bs_cu.energies[0] + 1.0]),
        reference=bs_cu.reference,
    )


def test_bandstructure(bs_cu, testdir, plt):
    _coords, _labelcoords, labels = bs_cu.get_labels()
    print(labels)
    bs_cu.write('hmm.json')
    bs = BandStructure.read('hmm.json')
    _coords, _labelcoords, labels = bs.get_labels()
    print(labels)
    assert ''.join(labels) == 'GXWKGLUWLKUX'
    bs_cu.plot(emax=10, filename='bs.png')
    cols = np.linspace(-1.0, 1.0, bs_cu.energies.size)
    cols.shape = bs_cu.energies.shape
    bs_cu.plot(emax=10, point_colors=cols, filename='bs2.png')


def test_bandstructure_with_spin(bs_spin, testdir, plt):
    _coords, _labelcoords, labels = bs_spin.get_labels()
    print(labels)
    bs_spin.write('hmm_spin.json')
    bs = BandStructure.read('hmm_spin.json')
    _coords, _labelcoords, labels = bs.get_labels()
    print(labels)
    assert ''.join(labels) == 'GXWKGLUWLKUX'
    bs_spin.plot(emax=10, filename='bs_spin.png', spin=0, linestyle='dotted')
    bs_spin.plot(emax=10, filename='bs_spin2.png', spin=1, linestyle='solid')
    bs_spin.plot(emax=10, filename='bs_spin_all.png', colors='rb')


@pytest.fixture()
def bs():
    rhl = RHL(4.0, 65.0)
    path = rhl.bandpath()
    return path.free_electron_band_structure()


def test_print_bs(bs):
    print(bs)


def test_subtract_ref(bs):
    avg = np.mean(bs.energies)
    bs._reference = 5
    bs2 = bs.subtract_reference()
    avg2 = np.mean(bs2.energies)
    assert avg - 5 == pytest.approx(avg2)
