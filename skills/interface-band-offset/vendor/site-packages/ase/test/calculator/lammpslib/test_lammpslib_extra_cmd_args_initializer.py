import pytest

from ase import Atom, Atoms
from ase.build import bulk


@pytest.fixture()
def atoms_fcc_Ni_with_H_at_center():
    atoms = bulk('Ni', cubic=True)
    atoms += Atom('H', position=atoms.cell.diagonal() / 2)
    return atoms


@pytest.mark.calculator_lite()
@pytest.mark.calculator('lammpslib')
def test_lammpslib_simple_extra_cmd_args(
    factory,
    calc_params_NiH: dict,
    calc_params_extra_cmd_args: dict,
    atoms_fcc_Ni_with_H_at_center: Atoms,
):
    NiH = atoms_fcc_Ni_with_H_at_center

    # Add a bit of distortion to the cell
    NiH.set_cell(
        NiH.cell + [[0.1, 0.2, 0.4], [0.3, 0.2, 0.0], [0.1, 0.1, 0.1]],
        scale_atoms=True,
    )

    calc_params = calc_params_NiH.copy()
    calc_params.update(calc_params_extra_cmd_args)
    calc = factory.calc(**calc_params)
    NiH.calc = calc

    _ = NiH.get_potential_energy()

    # this should work only because extra_cmd_args defined nsteps=10
    calc.lmp.command('run ${nsteps}')


@pytest.mark.calculator_lite()
@pytest.mark.calculator('lammpslib')
def test_lammpslib_simple_initializer(
    factory,
    calc_params_NiH: dict,
    atoms_fcc_Ni_with_H_at_center: Atoms,
    capsys,
):
    with capsys.disabled():
        NiH = atoms_fcc_Ni_with_H_at_center

        calc_params = calc_params_NiH.copy()

        def _initializer(lmp):
            print('running initializer with lmp', lmp)
            assert lmp is not None

        calc_params['initializer'] = _initializer
        calc = factory.calc(**calc_params)
        NiH.calc = calc

    _ = NiH.get_potential_energy()

    assert 'running initializer' in str(capsys.readouterr())
