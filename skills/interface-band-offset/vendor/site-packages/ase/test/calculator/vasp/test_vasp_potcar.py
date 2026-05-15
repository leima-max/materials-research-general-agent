# fmt: off
from pathlib import Path

import pytest

from ase.build import bulk, molecule
from ase.calculators.vasp import Vasp

parent = Path(__file__).parents[2]


@pytest.fixture()
def nacl():
    atoms = bulk("NaCl", crystalstructure="rocksalt", a=4.1, cubic=True)
    return atoms


@pytest.fixture()
def nh3():
    atoms = molecule("NH3", vacuum=10)
    return atoms


def _potcar_header():
    with open("POTCAR") as f:
        return [line.strip() for line in f.readlines()]


def get_suffixes(ppp_list):
    suffixes = []
    for p in ppp_list:
        name = Path(p).parent.name
        # since the H PPs with fractional valence
        # do not have an '_', we need to handle them
        element = name.split("_")[0] if "." not in name else "H"
        suffix = name[len(element):]
        suffixes.append(suffix)
    return suffixes


def test_potcar_setups(nacl, monkeypatch):
    monkeypatch.setenv("VASP_PP_PATH", str(parent / "testdata/vasp/fake_pseudos"
                                           ))
    setups = {
        "recommended": ["_pv", ""],
        "GW": ["_sv_GW", "_GW"],
        "custom": ["", "_h"],
    }
    calc = Vasp(setups="recommended")
    calc.write_input(nacl)
    assert get_suffixes(calc.ppp_list) == setups["recommended"]
    assert _potcar_header() == ["potpaw Na_pv", "potpaw Cl"]

    calc = Vasp(xc="PBE", setups={"Cl": "_h"})
    calc.write_input(nacl)
    assert get_suffixes(calc.ppp_list) == ['', '_h']
    assert _potcar_header() == ["potpaw_PBE Na", "potpaw_PBE Cl_h"]

    calc = Vasp(setups="GW")
    calc.write_input(nacl)
    assert get_suffixes(calc.ppp_list) == setups["GW"]
    assert _potcar_header() == ["potpaw Na_sv_GW", "potpaw Cl_GW"]

    calc = Vasp(setups={"base": "minimal", "Cl": "_h"})
    calc.write_input(nacl)
    assert get_suffixes(calc.ppp_list) == setups["custom"]
    assert _potcar_header() == ["potpaw Na", "potpaw Cl_h"]


@pytest.mark.parametrize(
    "vasp_kwargs, expected",
    [
        ({}, ["potpaw Na", "potpaw Cl"]),
        ({"xc": "PBE"}, ["potpaw_PBE Na", "potpaw_PBE Cl"]),
        ({"xc": "HSE06"}, ["potpaw_PBE Na", "potpaw_PBE Cl"]),
        ({"pp_version": "64"}, ["potpaw_LDA.64 Na", "potpaw_LDA.64 Cl"]),
        ({"xc": "PBE", "pp_version": "64"}, ["potpaw_PBE.64 Na",
                                             "potpaw_PBE.64 Cl"]),
        (
            {"xc": "PBE", "pp_version": "original"},
            ["potpaw_PBE.original Na", "potpaw_PBE.original Cl"],
        ),
        (
            {"xc": "PBE", "pp_version": "64", "setups": {"Na": "_sv_GW"}},
            ["potpaw_PBE.64 Na_sv_GW", "potpaw_PBE.64 Cl"],
        ),
    ],
)
def test_potcar_version(nacl, monkeypatch, vasp_kwargs, expected):
    monkeypatch.setenv("VASP_PP_PATH", str(parent / "testdata/vasp/fake_pseudos"
                                           ))

    calc = Vasp(**vasp_kwargs)
    calc.write_input(nacl)

    assert _potcar_header() == expected


@pytest.mark.parametrize(
    "vasp_kwargs, pp_version, expected",
    [
        ({}, "", ["potpaw Na", "potpaw Cl"]),
        ({"xc": "PBE"}, "", ["potpaw_PBE Na", "potpaw_PBE Cl"]),
        ({"xc": "HSE06"}, "", ["potpaw_PBE Na", "potpaw_PBE Cl"]),
        ({}, "64", ["potpaw_LDA.64 Na", "potpaw_LDA.64 Cl"]),
        ({"xc": "PBE"}, "64", ["potpaw_PBE.64 Na", "potpaw_PBE.64 Cl"]),
        (
            {"xc": "PBE"},
            "original",
            ["potpaw_PBE.original Na", "potpaw_PBE.original Cl"],
        ),
        (
            {"xc": "PBE", "setups": {"Na": "_sv_GW"}},
            "64",
            ["potpaw_PBE.64 Na_sv_GW", "potpaw_PBE.64 Cl"],
        ),
    ],
)
def test_potcar_version_env(nacl, monkeypatch, vasp_kwargs, pp_version,
                            expected):
    monkeypatch.setenv("VASP_PP_PATH", str(parent / "testdata/vasp/fake_pseudos"
                                           ))
    monkeypatch.setenv("VASP_PP_VERSION", pp_version)

    calc = Vasp(**vasp_kwargs)
    calc.write_input(nacl)

    assert _potcar_header() == expected


def test_bad_potcar_version(nacl, monkeypatch):
    monkeypatch.setenv("VASP_PP_PATH", str(parent / "testdata/vasp/fake_pseudos"
                                           ))

    with pytest.raises(RuntimeError, match="Looking for"):
        calc = Vasp(pp_version="bad")
        calc.initialize(nacl)


def test_bad_potcar_version_env(nacl, monkeypatch):
    monkeypatch.setenv("VASP_PP_PATH", str(parent / "testdata/vasp/fake_pseudos"
                                           ))
    monkeypatch.setenv("VASP_PP_VERSION", "bad")

    with pytest.raises(RuntimeError, match="Looking for"):
        calc = Vasp()
        calc.initialize(nacl)


def test_potcar_setups_fractional_valence(nh3, monkeypatch):
    monkeypatch.setenv("VASP_PP_PATH", str(parent / "testdata/vasp/fake_pseudos"
                                           ))
    setups = {"base": "recommended", 1: "H.5", 2: "H1.75", 3: "H.75"}
    calc = Vasp(setups=setups, xc="PBE")
    calc.write_input(nh3)
    assert get_suffixes(calc.ppp_list) == [".5", "1.75", ".75", ""]
    assert _potcar_header() == ["potpaw_PBE H.5", "potpaw_PBE H.1.75",
                                "potpaw_PBE H.75", "potpaw_PBE N"]
