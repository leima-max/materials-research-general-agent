#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import scipy.integrate as integrate
from numpy import ones, vstack
from numpy.linalg import lstsq
from scipy.interpolate import CubicSpline
from scipy.signal import find_peaks

os.environ.setdefault("MPLBACKEND", "Agg")

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LOCAL_VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"
ALLOWED_MODES = {"quick_estimate", "slab_based", "explicit_interface"}
ALLOWED_CALCULATOR_METHODS = {
    "ewald",
    "alignn_ff",
    "emt",
    "matgl",
    "eam_ase",
    "vasp",
    "tb3",
    "qe",
    "lammps",
    "gpaw",
}
ASE_BASED_CALCULATORS = {"alignn_ff", "emt", "matgl", "eam_ase", "gpaw"}
STEP_SIZE = 10


def _load_backend():
    backend_source = "path"
    if LOCAL_VENDOR_DIR.exists() and str(LOCAL_VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(LOCAL_VENDOR_DIR))
        backend_source = "local_vendor"
    try:
        from jarvis.analysis.interface.zur import get_hetero_type
        from jarvis.core.atoms import Atoms
        from jarvis.core.kpoints import Kpoints3D
        from jarvis.io.vasp.inputs import Incar
        from jarvis.io.vasp.outputs import Locpot, Outcar, Vasprun
        from intermat.generate import InterfaceCombi
        from intermat.run_intermat import main as run_intermat_main
        return (
            get_hetero_type,
            Atoms,
            Kpoints3D,
            Incar,
            Locpot,
            Outcar,
            Vasprun,
            InterfaceCombi,
            run_intermat_main,
            backend_source,
        )
    except Exception as exc:
        raise RuntimeError(
            "intermat backend is not available. Run scripts/install_intermat.py first."
        ) from exc


(
    get_hetero_type,
    Atoms,
    Kpoints3D,
    Incar,
    Locpot,
    Outcar,
    Vasprun,
    InterfaceCombi,
    run_intermat_main,
    BACKEND_SOURCE,
) = _load_backend()


def load_payload(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_payload(payload: dict) -> dict:
    inputs = payload.setdefault("inputs", {})
    bundle = inputs.get("directory_bundle")
    if not isinstance(bundle, dict):
        return payload

    defaults = bundle.get("defaults", {}) if isinstance(bundle.get("defaults"), dict) else {}
    material_file_defaults = {
        "bulk_outcar_name": defaults.get("bulk_outcar_name", "OUTCAR"),
        "slab_locpot_name": defaults.get("slab_locpot_name", "LOCPOT"),
        "slab_outcar_name": defaults.get("slab_outcar_name", "OUTCAR"),
        "slab_vasprun_name": defaults.get("slab_vasprun_name", "vasprun.xml"),
    }
    interface_file_defaults = {
        "interface_locpot_name": defaults.get("interface_locpot_name", "LOCPOT"),
        "interface_outcar_name": defaults.get("interface_outcar_name", "OUTCAR"),
        "interface_vasprun_name": defaults.get("interface_vasprun_name", "vasprun.xml"),
    }

    for material_key in ("material_a", "material_b"):
        material = inputs.setdefault(material_key, {})
        material_bundle = bundle.get(material_key, {}) if isinstance(bundle.get(material_key), dict) else {}
        _apply_material_directory_bundle(material, material_bundle, material_file_defaults)

    interface_outputs = inputs.setdefault("interface_outputs", {})
    interface_bundle = bundle.get("interface", {}) if isinstance(bundle.get("interface"), dict) else {}
    _apply_interface_directory_bundle(interface_outputs, interface_bundle, interface_file_defaults)
    return payload


def _resolve_named_file(base_dir: str | Path, filename: str) -> str:
    return str((Path(base_dir) / filename).resolve())


def _apply_material_directory_bundle(material: dict, bundle: dict, defaults: dict) -> None:
    bulk_dir = bundle.get("bulk_dir")
    if bulk_dir and not material.get("bulk_outcar_path"):
        material["bulk_outcar_path"] = _resolve_named_file(
            bulk_dir, bundle.get("bulk_outcar_name", defaults["bulk_outcar_name"])
        )

    slab_dir = bundle.get("slab_dir")
    if slab_dir:
        material.setdefault("slab_output_dir", str(Path(slab_dir).resolve()))
        if not material.get("locpot_path"):
            material["locpot_path"] = _resolve_named_file(
                slab_dir, bundle.get("slab_locpot_name", defaults["slab_locpot_name"])
            )
        if not material.get("outcar_path"):
            material["outcar_path"] = _resolve_named_file(
                slab_dir, bundle.get("slab_outcar_name", defaults["slab_outcar_name"])
            )
        if not material.get("vasprun_path"):
            material["vasprun_path"] = _resolve_named_file(
                slab_dir, bundle.get("slab_vasprun_name", defaults["slab_vasprun_name"])
            )

    if bundle.get("vacuum_axis") and not material.get("vacuum_axis"):
        material["vacuum_axis"] = bundle["vacuum_axis"]


def _apply_interface_directory_bundle(interface_outputs: dict, bundle: dict, defaults: dict) -> None:
    output_dir = bundle.get("output_dir") or bundle.get("interface_dir")
    if output_dir:
        interface_outputs.setdefault("output_dir", str(Path(output_dir).resolve()))
        if not interface_outputs.get("locpot_path"):
            interface_outputs["locpot_path"] = _resolve_named_file(
                output_dir,
                bundle.get("interface_locpot_name", defaults["interface_locpot_name"]),
            )
        if not interface_outputs.get("outcar_path"):
            interface_outputs["outcar_path"] = _resolve_named_file(
                output_dir,
                bundle.get("interface_outcar_name", defaults["interface_outcar_name"]),
            )
        if not interface_outputs.get("vasprun_path"):
            interface_outputs["vasprun_path"] = _resolve_named_file(
                output_dir,
                bundle.get("interface_vasprun_name", defaults["interface_vasprun_name"]),
            )

    for key in ("vacuum_axis", "left_index", "peak_width", "polar"):
        if key in bundle and key not in interface_outputs:
            interface_outputs[key] = bundle[key]


def _deep_update(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_update(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _maybe_float(value: Any) -> Any:
    if value is None or value == "":
        return None
    return float(value)


def _get_calculator_settings(payload: dict) -> dict[str, Any] | None:
    inputs = payload.get("inputs", {})
    options = payload.get("options", {})
    raw = inputs.get("calculator") or options.get("calculator")
    compare = options.get("compare_methods")

    if raw is None and compare:
        if isinstance(compare, str):
            compare = [compare]
        if isinstance(compare, list) and compare:
            raw = {"method": compare[0], "requested_compare_methods": compare}

    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("inputs.calculator must be an object when provided")

    settings = dict(raw)
    method = settings.get("method") or settings.get("calculator_method") or ""
    method = str(method).strip()
    if not method:
        raise ValueError("inputs.calculator.method is required when calculator settings are provided")
    if method not in ALLOWED_CALCULATOR_METHODS:
        raise ValueError(
            f"Unsupported calculator method '{method}'. Allowed: {', '.join(sorted(ALLOWED_CALCULATOR_METHODS))}"
        )
    settings["method"] = method

    if "requested_compare_methods" not in settings and compare:
        if isinstance(compare, str):
            compare = [compare]
        if isinstance(compare, list):
            settings["requested_compare_methods"] = compare
    return settings


def _module_available(module_name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module_name) is not None


def _command_available(command: str) -> bool:
    return shutil.which(command) is not None


def _sanitize_for_json(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(k): _sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, (list, tuple, set)):
        return [_sanitize_for_json(v) for v in data]
    if isinstance(data, Path):
        return str(data)
    if isinstance(data, np.ndarray):
        return data.tolist()
    if isinstance(data, (np.floating, np.integer)):
        return data.item()
    if isinstance(data, np.bool_):
        return bool(data)
    return data


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-._") or "item"


@contextlib.contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _collect_created_paths(before: set[Path], after_root: Path) -> list[Path]:
    return sorted(path for path in after_root.iterdir() if path not in before)


def _preflight_calculator_settings(settings: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    method = settings["method"]
    ok = True
    checks: list[dict[str, Any]] = []
    hints: list[str] = []

    def add_check(name: str, passed: bool, detail: str) -> None:
        nonlocal ok
        checks.append({"name": name, "ok": passed, "detail": detail})
        if not passed:
            ok = False

    if method in ASE_BASED_CALCULATORS:
        has_ase = _module_available("ase")
        add_check("python_module:ase", has_ase, "ASE is required for ase-based intermat calculators.")
        if not has_ase:
            hints.append("Run scripts/install_intermat.py --extras ase before using ase-based calculator methods.")

    if method == "alignn_ff":
        has_alignn = _module_available("alignn")
        add_check("python_module:alignn", has_alignn, "ALIGNN-FF requires the alignn Python package.")
        if not has_alignn:
            hints.append("Run scripts/install_intermat.py --extras alignn to enable alignn_ff.")
    elif method == "matgl":
        has_matgl = _module_available("matgl")
        add_check("python_module:matgl", has_matgl, "matgl calculator requires the matgl Python package.")
        if not has_matgl:
            hints.append("Run scripts/install_intermat.py --extras matgl to enable matgl.")
    elif method == "gpaw":
        has_gpaw = _module_available("gpaw")
        add_check("python_module:gpaw", has_gpaw, "GPAW calculator requires the gpaw Python package.")
        if not has_gpaw:
            hints.append("Install gpaw into the workspace-local vendor environment before using the gpaw method.")
    elif method == "tb3":
        add_check("command:julia", _command_available("julia"), "tb3 route shells out to Julia.")
        if not _command_available("julia"):
            hints.append("Install Julia and the required ThreeBodyTB environment before using tb3.")
    elif method == "vasp":
        sub_job = _as_bool(config.get("sub_job"), False)
        vasp_cmd = str(config.get("vasp_params", {}).get("vasp_cmd") or "mpirun vasp_std")
        if not sub_job:
            command_head = vasp_cmd.split()[0]
            add_check(
                f"command:{command_head}",
                _command_available(command_head),
                f"vasp route expects local command '{command_head}' when sub_job is false.",
            )
        else:
            checks.append({
                "name": "scheduler_submission",
                "ok": True,
                "detail": "sub_job=true: local executable presence is not enforced during preflight.",
            })
    elif method == "qe":
        sub_job = _as_bool(config.get("sub_job"), False)
        qe_cmd = str(config.get("qe_params", {}).get("qe_cmd") or "pw.x")
        if not sub_job:
            command_head = qe_cmd.split()[0]
            add_check(
                f"command:{command_head}",
                _command_available(command_head),
                f"qe route expects local command '{command_head}' when sub_job is false.",
            )
        else:
            checks.append({
                "name": "scheduler_submission",
                "ok": True,
                "detail": "sub_job=true: local executable presence is not enforced during preflight.",
            })
    elif method == "lammps":
        lammps_cmd = str(config.get("lammps_params", {}).get("lammps_cmd") or "lmp_serial")
        command_head = lammps_cmd.split("<", 1)[0].strip().split()[0]
        add_check(
            f"command:{command_head}",
            _command_available(command_head),
            f"lammps route expects local command '{command_head}'.",
        )

    if method in {"ewald", "emt", "alignn_ff", "matgl", "eam_ase", "gpaw"} and not _as_bool(config.get("do_surfaces"), True):
        hints.append("do_surfaces=false makes upstream intermat return placeholder wads (-9999), so adhesion energy ranking will not be meaningful.")

    return {
        "method": method,
        "ok": ok,
        "checks": checks,
        "hints": hints,
    }



def validate_payload(payload: dict) -> None:
    mode = payload.get("mode")
    if mode not in ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(ALLOWED_MODES))}")

    inputs = payload.get("inputs", {})
    a = inputs.get("material_a", {})
    b = inputs.get("material_b", {})
    calculator = _get_calculator_settings(payload)
    if not a.get("name") or not b.get("name"):
        raise ValueError("inputs.material_a.name and inputs.material_b.name are required")

    if mode == "quick_estimate" and not _has_reference_route(payload):
        raise ValueError(
            "quick_estimate requires reference_values.ip+ea for both materials, or reference_values.band_offsets"
        )

    if mode == "slab_based":
        slab_vasp_closure = bool(calculator and calculator.get("method") == "vasp")
        if not (
            _has_reference_route(payload)
            or (_has_slab_output_route(a) and _has_slab_output_route(b))
            or slab_vasp_closure
        ):
            raise ValueError(
                "slab_based requires either reference_values, slab outputs for both materials "
                "(slab_output_dir or explicit locpot/outcar/vasprun paths), or calculator.method='vasp' with structure routes."
            )

    if mode == "explicit_interface":
        if not (_has_structure_route(a) and _has_structure_route(b)) and not _has_interface_output_route(payload):
            raise ValueError(
                "explicit_interface requires either material structure routes (jid or structure_source for both sides), "
                "or inputs.interface_outputs with an interface LOCPOT path."
            )

    if calculator:
        if mode not in {"explicit_interface", "slab_based"}:
            raise ValueError("intermat calculator routes are only supported with mode='explicit_interface' or mode='slab_based'")
        if mode == "slab_based" and calculator.get("method") != "vasp":
            raise ValueError("slab_based calculator closure currently supports only method='vasp'")
        if not (_has_structure_route(a) and _has_structure_route(b)) and not (_has_slab_output_route(a) and _has_slab_output_route(b)):
            raise ValueError(
                "inputs.calculator requires structure routes (jid or structure_source for both materials) for preparation, or finished slab outputs for collection."
            )



def _has_structure_route(material: dict) -> bool:
    return bool(material.get("jid") or material.get("structure_source"))



def _has_reference_route(payload: dict) -> bool:
    refs = payload.get("inputs", {}).get("reference_values", {})
    a = payload.get("inputs", {}).get("material_a", {}).get("name")
    b = payload.get("inputs", {}).get("material_b", {}).get("name")
    ip_refs = refs.get("ip", {})
    ea_refs = refs.get("ea", {})
    bo_refs = refs.get("band_offsets", {})
    return bool((a in ip_refs and b in ip_refs and a in ea_refs and b in ea_refs) or bo_refs)



def _has_slab_output_route(material: dict) -> bool:
    if material.get("slab_output_dir"):
        return True
    return bool(material.get("locpot_path") and material.get("outcar_path") and material.get("vasprun_path"))



def _has_interface_output_route(payload: dict) -> bool:
    iface = payload.get("inputs", {}).get("interface_outputs", {})
    if iface.get("output_dir"):
        return True
    return bool(iface.get("locpot_path"))



def _parse_surface(surface: Any, default: str = "0_0_1") -> str:
    if surface is None:
        return default
    if isinstance(surface, (list, tuple)) and len(surface) == 3:
        return "_".join(str(int(x)) for x in surface)
    text = str(surface).strip()
    nums = re.findall(r"-?\d+", text)
    if len(nums) == 3:
        return "_".join(nums)
    return default



def _band_edges_from_ip_ea(ip: float, ea: float) -> tuple[float, float]:
    vbm = -float(ip)
    cbm = -float(ea)
    return vbm, cbm



def _quick_reference_analysis(payload: dict) -> dict:
    inputs = payload.get("inputs", {})
    refs = inputs.get("reference_values", {})
    a = inputs["material_a"]["name"]
    b = inputs["material_b"]["name"]
    ip_refs = refs.get("ip", {})
    ea_refs = refs.get("ea", {})
    bo_refs = refs.get("band_offsets", {})

    if a in ip_refs and b in ip_refs and a in ea_refs and b in ea_refs:
        ip_a = float(ip_refs[a])
        ip_b = float(ip_refs[b])
        ea_a = float(ea_refs[a])
        ea_b = float(ea_refs[b])
        vbm_a, cbm_a = _band_edges_from_ip_ea(ip_a, ea_a)
        vbm_b, cbm_b = _band_edges_from_ip_ea(ip_b, ea_b)
        hetero_type, stack = get_hetero_type(
            A={"scf_vbm": vbm_a, "scf_cbm": cbm_a, "avg_max": 0},
            B={"scf_vbm": vbm_b, "scf_cbm": cbm_b, "avg_max": 0},
        )
        return {
            "mode": "reference_ip_ea",
            "ip": {a: ip_a, b: ip_b},
            "ea": {a: ea_a, b: ea_b},
            "band_edges_wrt_vacuum_ev": {
                a: {"vbm": vbm_a, "cbm": cbm_a},
                b: {"vbm": vbm_b, "cbm": cbm_b},
            },
            "band_offsets": {
                "delta_vbm_b_minus_a_ev": round(vbm_b - vbm_a, 6),
                "delta_cbm_b_minus_a_ev": round(cbm_b - cbm_a, 6),
            },
            "heterojunction_type": hetero_type,
            "stack_hint": stack,
            "sources": refs.get("sources", []),
        }

    if bo_refs:
        return {
            "mode": "reference_band_offsets",
            "band_offsets": bo_refs,
            "sources": refs.get("sources", []),
        }

    raise ValueError(
        "quick_estimate/slab_based requires reference_values.ip+ea for both materials, or reference_values.band_offsets"
    )


def _load_material_atoms(material: dict, dataset: str = "dft_3d") -> Atoms:
    if material.get("structure_source"):
        return Atoms.from_poscar(material["structure_source"])
    if material.get("jid"):
        try:
            from jarvis.db.figshare import get_jid_data
        except Exception as exc:
            raise RuntimeError("JARVIS dataset loader is unavailable for jid-based structure fetches.") from exc
        data = get_jid_data(jid=material["jid"], dataset=dataset)
        return Atoms.from_dict(data["atoms"])
    raise ValueError(f"Material {material.get('name')} needs jid or structure_source")


def _build_interface_generator(payload: dict, config: dict) -> InterfaceCombi:
    inputs = payload.get("inputs", {})
    ctx = inputs.get("calculation_context", {})
    film = _load_material_atoms(inputs["material_a"], dataset=config.get("dataset", "dft_3d"))
    subs = _load_material_atoms(inputs["material_b"], dataset=config.get("dataset", "dft_3d"))
    film_index = [int(x) for x in config["film_index"].split("_")]
    subs_index = [int(x) for x in config["substrate_index"].split("_")]
    kp_length = int(config.get("kp_length", 30))
    return InterfaceCombi(
        film_mats=[film],
        subs_mats=[subs],
        film_indices=[film_index],
        subs_indices=[subs_index],
        disp_intvl=float(config.get("disp_intvl", 0.0)),
        film_thicknesses=[float(config.get("film_thickness", 16))],
        subs_thicknesses=[float(config.get("substrate_thickness", 16))],
        seperations=[float(config.get("seperation", 2.5))],
        rotate_xz=_as_bool(config.get("rotate_xz"), False),
        vacuum_interface=float(config.get("vacuum_interface", 2.0)),
        max_area=float(config.get("max_area", 300.0)),
        ltol=float(config.get("ltol", 0.08)),
        atol=float(config.get("atol", 1.0)),
        from_conventional_structure_film=_as_bool(config.get("from_conventional_structure_film"), True),
        from_conventional_structure_subs=_as_bool(config.get("from_conventional_structure_subs"), True),
        film_ids=[_slug(inputs["material_a"].get("name", "film"))],
        subs_ids=[_slug(inputs["material_b"].get("name", "substrate"))],
        film_kplengths=[kp_length],
        subs_kplengths=[kp_length],
        dataset=[] if ctx.get("disable_dataset_lookup") else [None],
    )



def _intermat_config_from_payload(payload: dict) -> dict:
    inputs = payload.get("inputs", {})
    matching = inputs.get("matching", {})
    ctx = inputs.get("calculation_context", {})
    calculator = _get_calculator_settings(payload) or {}
    a = inputs["material_a"]
    b = inputs["material_b"]

    cfg: dict[str, Any] = {
        "film_index": _parse_surface(a.get("surface"), default="0_0_1"),
        "substrate_index": _parse_surface(b.get("surface"), default="0_0_1"),
        "film_thickness": float(ctx.get("film_thickness_ang", ctx.get("slab_thickness_ang", 16))),
        "substrate_thickness": float(ctx.get("substrate_thickness_ang", ctx.get("slab_thickness_ang", 16))),
        "seperation": float(ctx.get("separation_ang", 2.5)),
        "vacuum_interface": float(ctx.get("vacuum_thickness_ang", 2.0)),
        "disp_intvl": float(ctx.get("disp_intvl", 0.0)),
        "calculator_method": calculator.get("method", ""),
        "rotate_xz": _as_bool(ctx.get("rotate_xz"), False),
        "verbose": _as_bool(ctx.get("verbose"), False),
        "plot_wads": _as_bool(calculator.get("plot_wads"), False),
        "do_surfaces": _as_bool(calculator.get("do_surfaces"), True),
        "sub_job": _as_bool(calculator.get("sub_job"), False),
        "queue": calculator.get("queue", ctx.get("queue", "rack1,rack2")),
        "walltime": calculator.get("walltime", ctx.get("walltime", "30-00:00:00")),
        "extra_lines": calculator.get("extra_lines", ctx.get("extra_lines", "")),
        "copy_files": calculator.get("copy_files", ctx.get("copy_files", [])),
        "dataset": ctx.get("dataset", "dft_3d"),
    }
    if "max_lattice_mismatch_percent" in matching:
        cfg["ltol"] = float(matching["max_lattice_mismatch_percent"]) / 100.0
    if "max_area" in matching:
        cfg["max_area"] = float(matching["max_area"])
    if "angle_tolerance_deg" in matching:
        cfg["atol"] = float(matching["angle_tolerance_deg"])
    if "from_conventional_structure_film" in ctx:
        cfg["from_conventional_structure_film"] = _as_bool(ctx.get("from_conventional_structure_film"), True)
    if "from_conventional_structure_subs" in ctx:
        cfg["from_conventional_structure_subs"] = _as_bool(ctx.get("from_conventional_structure_subs"), True)
    if calculator.get("kp_length") is not None:
        cfg["kp_length"] = int(calculator["kp_length"])
    if calculator.get("potential"):
        cfg["potential"] = str(calculator["potential"])

    vasp_cfg = calculator.get("vasp") if isinstance(calculator.get("vasp"), dict) else {}
    if vasp_cfg:
        cfg["vasp_params"] = _deep_update(
            {"vasp_cmd": vasp_cfg.get("vasp_cmd", "mpirun vasp_std"), "inc": {}},
            {k: v for k, v in vasp_cfg.items() if k != "vasp_cmd"},
        )
        if "inc" not in cfg["vasp_params"]:
            cfg["vasp_params"]["inc"] = {}

    qe_cfg = calculator.get("qe") if isinstance(calculator.get("qe"), dict) else {}
    if qe_cfg:
        cfg["qe_params"] = _deep_update(
            {"qe_cmd": qe_cfg.get("qe_cmd", "pw.x"), "qe_params": {}},
            {k: v for k, v in qe_cfg.items() if k != "qe_cmd"},
        )
        if "qe_params" not in cfg["qe_params"]:
            cfg["qe_params"]["qe_params"] = {}

    lammps_cfg = calculator.get("lammps") if isinstance(calculator.get("lammps"), dict) else {}
    if lammps_cfg:
        cfg["lammps_params"] = dict(lammps_cfg)

    gpaw_cfg = calculator.get("gpaw") if isinstance(calculator.get("gpaw"), dict) else {}
    if gpaw_cfg:
        cfg["gpaw_params"] = dict(gpaw_cfg)

    if calculator.get("tb3_lines"):
        cfg["tb3_lines"] = list(calculator["tb3_lines"])

    if a.get("jid"):
        cfg["film_jid"] = a["jid"]
    elif a.get("structure_source"):
        cfg["film_file_path"] = a["structure_source"]
    else:
        raise ValueError("material_a needs jid or structure_source for explicit_interface generation")

    if b.get("jid"):
        cfg["substrate_jid"] = b["jid"]
    elif b.get("structure_source"):
        cfg["substrate_file_path"] = b["structure_source"]
    else:
        raise ValueError("material_b needs jid or structure_source for explicit_interface generation")

    return cfg



def _write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_sanitize_for_json(data), indent=2, ensure_ascii=False), encoding="utf-8")
    return path



def _run_intermat_config(config: dict, workdir: Path) -> tuple[dict, list[str], list[Path]]:
    workdir.mkdir(parents=True, exist_ok=True)
    before = set(workdir.iterdir()) if workdir.exists() else set()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with _pushd(workdir), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = run_intermat_main(config)
    raw_lines = [line.strip() for line in (stdout.getvalue() + "\n" + stderr.getvalue()).splitlines() if line.strip()]
    keep_prefixes = (
        "Number of generated interface",
        "Quick interface generation",
        "config.calculator_method",
        "w_adhesion (J/m2)",
        "Time taken:",
        "Obtaining 3D dataset",
        "Loading completed.",
        "Reference:",
        "Other versions:",
    )
    logs = [line for line in raw_lines if line.startswith(keep_prefixes)]
    created_paths = _collect_created_paths(before, workdir)
    return _sanitize_for_json(result), logs, created_paths



def _resolve_slab_paths(material: dict) -> dict[str, Path]:
    slab_dir = material.get("slab_output_dir")
    if slab_dir:
        base = Path(slab_dir)
        locpot = Path(material.get("locpot_path", base / "LOCPOT"))
        outcar = Path(material.get("outcar_path", base / "OUTCAR"))
        vasprun = Path(material.get("vasprun_path", base / "vasprun.xml"))
    else:
        locpot = Path(material["locpot_path"])
        outcar = Path(material["outcar_path"])
        vasprun = Path(material["vasprun_path"])

    for key, path in {"LOCPOT": locpot, "OUTCAR": outcar, "vasprun.xml": vasprun}.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing {key} for material {material.get('name')}: {path}")

    return {"locpot": locpot, "outcar": outcar, "vasprun": vasprun}



def _slab_surface_reference(material: dict, output_dir: Path, role: str) -> dict:
    paths = _resolve_slab_paths(material)
    outcar = Outcar(str(paths["outcar"]))
    bandgap = outcar.bandgap
    if not isinstance(bandgap, (list, tuple)) or len(bandgap) < 3:
        raise ValueError(f"Could not read CBM/VBM from OUTCAR for material {material.get('name')}")

    cbm = float(bandgap[1])
    vbm = float(bandgap[2])
    vrun = Vasprun(str(paths["vasprun"]))
    efermi = float(vrun.efermi)
    axis = str(material.get("vacuum_axis") or material.get("axis") or "X")
    profile_plot = output_dir / f"{role}_slab_vacuum_profile.png"

    mean_profile, cbm_scf, vbm_scf, avg_max, _, formula, atoms = Locpot(
        filename=str(paths["locpot"])
    ).vac_potential(
        direction=axis,
        Ef=efermi,
        cbm=cbm,
        vbm=vbm,
        filename=str(profile_plot),
        plot=True,
    )

    cbm_vac = float(cbm_scf) - float(avg_max)
    vbm_vac = float(vbm_scf) - float(avg_max)
    work_function = float(avg_max)

    return {
        "material": material.get("name"),
        "role": role,
        "analysis_route": "surf_andersen_like_locpot",
        "vacuum_axis": axis,
        "formula": str(formula),
        "num_atoms": int(getattr(atoms, "num_atoms", len(getattr(atoms, "elements", [])))),
        "paths": {k: str(v) for k, v in paths.items()},
        "electronic_reference": {
            "efermi_ev": round(efermi, 6),
            "scf_cbm_ev": round(float(cbm_scf), 6),
            "scf_vbm_ev": round(float(vbm_scf), 6),
            "vacuum_minus_ef_ev": round(work_function, 6),
        },
        "band_edges_wrt_vacuum_ev": {
            "vbm": round(vbm_vac, 6),
            "cbm": round(cbm_vac, 6),
        },
        "derived_quantities": {
            "ip_ev": round(-vbm_vac, 6),
            "ea_ev": round(-cbm_vac, 6),
            "work_function_ev": round(work_function, 6),
            "band_gap_ev": round(float(cbm_scf) - float(vbm_scf), 6),
            "profile_points": int(len(mean_profile)),
        },
        "artifacts": [
            {"type": "figure", "path": str(profile_plot)},
        ],
        "hetero_input": {
            "scf_vbm": float(vbm_scf),
            "scf_cbm": float(cbm_scf),
            "avg_max": float(avg_max),
        },
    }



def _slab_based_analysis(payload: dict, output_dir: Path) -> dict:
    inputs = payload.get("inputs", {})
    a = _slab_surface_reference(inputs["material_a"], output_dir, "material_a")
    b = _slab_surface_reference(inputs["material_b"], output_dir, "material_b")

    hetero_type, stack = get_hetero_type(A=a["hetero_input"], B=b["hetero_input"])
    vbm_a = a["band_edges_wrt_vacuum_ev"]["vbm"]
    cbm_a = a["band_edges_wrt_vacuum_ev"]["cbm"]
    vbm_b = b["band_edges_wrt_vacuum_ev"]["vbm"]
    cbm_b = b["band_edges_wrt_vacuum_ev"]["cbm"]

    return {
        "mode": "surf_andersen_like_locpot",
        "materials": {
            inputs["material_a"]["name"]: {k: v for k, v in a.items() if k != "hetero_input"},
            inputs["material_b"]["name"]: {k: v for k, v in b.items() if k != "hetero_input"},
        },
        "band_offsets": {
            "delta_vbm_b_minus_a_ev": round(vbm_b - vbm_a, 6),
            "delta_cbm_b_minus_a_ev": round(cbm_b - cbm_a, 6),
        },
        "heterojunction_type": hetero_type,
        "stack_hint": stack,
        "artifacts": [*a["artifacts"], *b["artifacts"]],
    }



def _resolve_interface_output_paths(payload: dict) -> dict[str, Path | None]:
    iface = payload.get("inputs", {}).get("interface_outputs", {})
    output_dir = iface.get("output_dir")
    if output_dir:
        base = Path(output_dir)
        locpot = Path(iface.get("locpot_path", base / "LOCPOT"))
        outcar = Path(iface["outcar_path"]) if iface.get("outcar_path") else (base / "OUTCAR")
        vasprun = Path(iface["vasprun_path"]) if iface.get("vasprun_path") else (base / "vasprun.xml")
    else:
        locpot = Path(iface["locpot_path"])
        outcar = Path(iface["outcar_path"]) if iface.get("outcar_path") else None
        vasprun = Path(iface["vasprun_path"]) if iface.get("vasprun_path") else None

    if not locpot.exists():
        raise FileNotFoundError(f"Missing interface LOCPOT: {locpot}")
    if outcar is not None and not outcar.exists():
        outcar = None
    if vasprun is not None and not vasprun.exists():
        vasprun = None

    return {"locpot": locpot, "outcar": outcar, "vasprun": vasprun}



def _interface_locpot_profile(locpot_path: Path, axis: str = "X") -> tuple[np.ndarray, np.ndarray, Any]:
    loc = Locpot(filename=str(locpot_path))
    atoms = loc.atoms
    cell = np.array(atoms.lattice_mat)
    latlens = np.linalg.norm(cell, axis=1)
    vol = float(atoms.volume)
    raw = np.array(loc.chg[0])
    if raw.ndim != 3:
        raise ValueError(f"Unexpected LOCPOT grid shape for {locpot_path}: {raw.shape}")

    grid = raw.flatten().reshape([raw.shape[2], raw.shape[0], raw.shape[1]])
    iaxis = {"X": 0, "Y": 1, "Z": 2}[axis.upper()]
    axes = tuple(i for i in range(3) if i != iaxis)
    mean = np.mean(grid, axes) * vol
    xvals = np.linspace(0.0, float(latlens[iaxis]), grid.shape[iaxis])
    return xvals, mean, atoms



def _get_m_c(x: Any, y: Any) -> tuple[float, float]:
    A = vstack([x, ones(len(x))]).T
    m, c = lstsq(A, y, rcond=None)[0]
    return float(m), float(c)



def _get_best_L(start_L: float, end_L: float, spline: CubicSpline, x_target: np.ndarray) -> float:
    best = float("inf")
    best_L = start_L
    step = (end_L - start_L) / (STEP_SIZE + 0.55)
    if step <= 0:
        return start_L
    for L_guess in np.arange(start_L, end_L + 1e-5, step):
        current = 0.0
        for xx in x_target:
            current += abs(float(spline(xx)) - float(spline(xx + L_guess)))
        if current < best:
            best = current
            best_L = float(L_guess)
    return best_L



def _best_L_recursive(start_L: float, end_L: float, spline: CubicSpline, x_target: np.ndarray) -> float:
    L_best = start_L
    L_range = end_L - start_L
    for _ in range(STEP_SIZE):
        L_best = _get_best_L(start_L, end_L, spline, x_target)
        L_range = L_range / STEP_SIZE
        start_L = L_best - L_range
        end_L = L_best + L_range
    return float(L_best)



def _do_average(L: float, x: np.ndarray, spline: CubicSpline) -> tuple[np.ndarray, np.ndarray]:
    avg = []
    xx = []
    for value in x:
        if value - L / 2.0 < x[0]:
            continue
        if value + L / 2.0 > x[-1]:
            continue
        xx.append(float(value))
        avg.append(integrate.quad(spline, value - L / 2.0, value + L / 2.0)[0] / L)
    return np.array(xx), np.array(avg)



def _sample_region(x: np.ndarray, start_idx: int, end_idx: int) -> np.ndarray:
    if end_idx <= start_idx:
        raise ValueError("Invalid peak region while sampling plateau")
    width = end_idx - start_idx
    stride = max(1, width // 24)
    region = x[np.arange(start_idx, end_idx, stride, dtype=int)]
    if len(region) < 2:
        region = x[start_idx : end_idx + 1]
    if len(region) < 2:
        raise ValueError("Too few points in plateau region for explicit interface ΔV analysis")
    return region



def _mean_val(x_target: np.ndarray, XX: np.ndarray, AVG: np.ndarray) -> tuple[float, float, float]:
    idx = XX.searchsorted(x_target)
    idx = np.clip(idx, 0, len(AVG) - 1)
    new_mean = float(np.mean(AVG[idx]))
    m, c = _get_m_c(x=XX[idx], y=AVG[idx])
    return new_mean, m, c



def _resolve_bulk_band_edges(material: dict, refs: dict) -> dict | None:
    name = material["name"]
    inline = material.get("bulk_band_edges")
    if inline and "vbm" in inline and "cbm" in inline:
        return {
            "source": "material.bulk_band_edges",
            "vbm": float(inline["vbm"]),
            "cbm": float(inline["cbm"]),
        }

    ref_bulk = refs.get("bulk_band_edges", {})
    if name in ref_bulk and "vbm" in ref_bulk[name] and "cbm" in ref_bulk[name]:
        return {
            "source": "reference_values.bulk_band_edges",
            "vbm": float(ref_bulk[name]["vbm"]),
            "cbm": float(ref_bulk[name]["cbm"]),
        }

    bulk_outcar = material.get("bulk_outcar_path")
    if bulk_outcar:
        path = Path(bulk_outcar)
        if not path.exists():
            raise FileNotFoundError(f"Missing bulk OUTCAR for material {name}: {path}")
        bandgap = Outcar(str(path)).bandgap
        if not isinstance(bandgap, (list, tuple)) or len(bandgap) < 3:
            raise ValueError(f"Could not read CBM/VBM from bulk OUTCAR for material {name}")
        return {
            "source": "material.bulk_outcar_path",
            "vbm": float(bandgap[2]),
            "cbm": float(bandgap[1]),
            "path": str(path),
        }

    return None



def _explicit_interface_delta_v_analysis(payload: dict, output_dir: Path) -> dict:
    inputs = payload.get("inputs", {})
    iface_cfg = inputs.get("interface_outputs", {})
    paths = _resolve_interface_output_paths(payload)
    axis = str(iface_cfg.get("vacuum_axis") or iface_cfg.get("axis") or "X").upper()
    left_index = int(iface_cfg.get("left_index", -1))
    peak_width = int(iface_cfg.get("peak_width", 5))
    polar = bool(iface_cfg.get("polar", False))

    x, profile, atoms = _interface_locpot_profile(paths["locpot"], axis=axis)
    spline = CubicSpline(x, profile)
    max_peaks, _ = find_peaks(profile, prominence=1, width=peak_width)
    max_peaks = max_peaks[:-1]
    if len(max_peaks) < 4:
        raise ValueError(
            f"Explicit interface ΔV analysis found too few peaks ({len(max_peaks)}) in LOCPOT profile; "
            "provide a cleaner supercell or override left_index/peak_width."
        )

    auto_left = False
    if left_index == -1:
        auto_left = True
        if len(max_peaks) <= 8:
            left_index = 1
        elif len(max_peaks) <= 12:
            left_index = 2
        else:
            left_index = 3

    left_pair = (left_index, left_index + 1)
    right_pair = (len(max_peaks) - left_index - 2, len(max_peaks) - left_index - 1)
    if (
        left_pair[0] < 0
        or left_pair[1] >= len(max_peaks)
        or right_pair[0] < 0
        or right_pair[1] >= len(max_peaks)
        or left_pair[0] >= left_pair[1]
        or right_pair[0] >= right_pair[1]
    ):
        raise ValueError(
            f"Chosen plateau indices are out of range for detected peaks: left_index={left_index}, "
            f"left_pair={left_pair}, right_pair={right_pair}, peak_count={len(max_peaks)}"
        )

    x_target1 = _sample_region(x, int(max_peaks[left_pair[0]]), int(max_peaks[left_pair[1]]))
    x_target2 = _sample_region(x, int(max_peaks[right_pair[0]]), int(max_peaks[right_pair[1]]))

    L_guess_left = float(x_target1[-1] - x_target1[0])
    L_left = _best_L_recursive(1.0, max(1.5, L_guess_left * 1.5), spline, x_target1)
    XX_left, AVG_left = _do_average(L_left, x, spline)
    meanval1, m1, c1 = _mean_val(x_target1, XX_left, AVG_left)

    L_guess_right = float(x_target2[-1] - x_target2[0])
    L_right = _best_L_recursive(1.0, max(1.5, L_guess_right * 1.5), spline, x_target2)
    XX_right, AVG_right = _do_average(L_right, x, spline)
    meanval2, m2, c2 = _mean_val(x_target2, XX_right, AVG_right)

    delta_v = float(meanval2 - meanval1)
    if polar:
        mid_idx = int((len(XX_right) - 1) / 2)
        delta_v = float((np.array(XX_right) * m2 + c2)[mid_idx] - (np.array(XX_left) * m1 + c1)[mid_idx])

    plot_path = output_dir / "explicit_interface_delta_v_profile.png"
    fig = plt.figure(figsize=(8, 5), dpi=200)
    ax = fig.add_subplot(111)
    ax.plot(x, profile, c="black", label="LOCPOT mean profile")
    ax.plot(x[max_peaks], profile[max_peaks], "x", label="detected peaks")
    ax.plot(XX_left, AVG_left, c="tab:red", alpha=0.9, label="left averaged")
    ax.plot(XX_right, AVG_right, c="tab:green", alpha=0.9, label="right averaged")
    ax.plot(x_target1, spline(x_target1), c="cyan", linewidth=1.0)
    ax.plot(x_target2, spline(x_target2), c="cyan", linewidth=1.0)
    ax.axhline(meanval1, linestyle="--", c="tab:red", alpha=0.7)
    ax.axhline(meanval2, linestyle="--", c="tab:green", alpha=0.7)
    ax.set_xlabel(r"Distance ($\AA$)")
    ax.set_ylabel("Potential (eV)")
    ax.set_title(f"Interface ΔV = {delta_v:.3f} eV")
    ax.grid(alpha=0.2)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_path)
    plt.close(fig)

    result = {
        "mode": "explicit_interface_locpot_delta_v",
        "interface_outputs": {
            "locpot_path": str(paths["locpot"]),
            "outcar_path": str(paths["outcar"]) if paths["outcar"] else None,
            "vasprun_path": str(paths["vasprun"]) if paths["vasprun"] else None,
            "vacuum_axis": axis,
        },
        "potential_lineup": {
            "delta_v_ev": round(delta_v, 6),
            "left_plateau_ev": round(float(meanval1), 6),
            "right_plateau_ev": round(float(meanval2), 6),
            "left_period_ang": round(float(L_left), 6),
            "right_period_ang": round(float(L_right), 6),
            "peak_count": int(len(max_peaks)),
            "left_index": int(left_index),
            "left_pair": [int(left_pair[0]), int(left_pair[1])],
            "right_pair": [int(right_pair[0]), int(right_pair[1])],
            "left_index_auto": auto_left,
            "polar_mode": polar,
        },
        "interface_model": {
            "num_atoms": int(getattr(atoms, "num_atoms", len(getattr(atoms, "elements", [])))),
        },
        "artifacts": [
            {"type": "figure", "path": str(plot_path)},
        ],
    }

    refs = inputs.get("reference_values", {})
    bulk_a = _resolve_bulk_band_edges(inputs["material_a"], refs)
    bulk_b = _resolve_bulk_band_edges(inputs["material_b"], refs)
    if bulk_a and bulk_b:
        vbo = delta_v + (bulk_b["vbm"] - bulk_a["vbm"])
        cbo = delta_v + (bulk_b["cbm"] - bulk_a["cbm"])
        hetero_type, stack = get_hetero_type(
            A={"scf_vbm": bulk_a["vbm"], "scf_cbm": bulk_a["cbm"], "avg_max": 0},
            B={"scf_vbm": bulk_b["vbm"] + delta_v, "scf_cbm": bulk_b["cbm"] + delta_v, "avg_max": 0},
        )
        result["bulk_band_edges"] = {
            inputs["material_a"]["name"]: bulk_a,
            inputs["material_b"]["name"]: bulk_b,
        }
        result["band_offsets"] = {
            "delta_vbm_b_minus_a_ev": round(vbo, 6),
            "delta_cbm_b_minus_a_ev": round(cbo, 6),
        }
        result["heterojunction_type"] = hetero_type
        result["stack_hint"] = stack
    else:
        result["bulk_band_edges"] = {
            inputs["material_a"]["name"]: bulk_a,
            inputs["material_b"]["name"]: bulk_b,
        }

    return result



def _summarize_wads(wads: Any, do_surfaces: bool) -> dict[str, Any] | None:
    if wads in (None, ""):
        return None
    values = _sanitize_for_json(wads)
    if not isinstance(values, list):
        values = [values]
    numeric_values = []
    for value in values:
        try:
            numeric_values.append(float(value))
        except Exception:
            continue
    if not numeric_values:
        return {"raw": values}

    summary: dict[str, Any] = {
        "values_j_per_m2": [round(v, 6) for v in numeric_values],
        "count": len(numeric_values),
    }
    if do_surfaces:
        best_index = int(np.argmin(numeric_values))
        summary["best_index"] = best_index
        summary["best_wad_j_per_m2"] = round(numeric_values[best_index], 6)
        summary["min_wad_j_per_m2"] = round(min(numeric_values), 6)
        summary["max_wad_j_per_m2"] = round(max(numeric_values), 6)
    else:
        summary["note"] = "Upstream intermat leaves wads at placeholder values when do_surfaces=false."
    return summary



def _make_vasp_incar(incar_data: dict[str, Any]) -> Incar:
    return Incar(incar_data)


def _make_surface_kpoints(atoms: Atoms, kp_length: int, is_surface: bool) -> Any:
    kp = Kpoints3D().automatic_length_mesh(lattice_mat=atoms.lattice_mat, length=kp_length)
    kmesh = list(kp.kpts[0])
    if is_surface and len(kmesh) == 3:
        kmesh[2] = 1
    return Kpoints3D(kpoints=[kmesh])


def _discover_vasp_outputs(job_dir: Path) -> dict[str, Path | None]:
    candidates = [job_dir]
    nested = job_dir / job_dir.name
    if nested.exists():
        candidates.insert(0, nested)
    for candidate in candidates:
        outcar = candidate / "OUTCAR"
        vasprun = candidate / "vasprun.xml"
        locpot = candidate / "LOCPOT"
        contcar = candidate / "CONTCAR"
        if outcar.exists() or vasprun.exists() or locpot.exists():
            return {
                "job_dir": candidate,
                "outcar": outcar if outcar.exists() else None,
                "vasprun": vasprun if vasprun.exists() else None,
                "locpot": locpot if locpot.exists() else None,
                "contcar": contcar if contcar.exists() else None,
            }
    return {"job_dir": job_dir, "outcar": None, "vasprun": None, "locpot": None, "contcar": None}


def _vasp_job_status(job_dir: Path, require_locpot: bool = True) -> dict[str, Any]:
    paths = _discover_vasp_outputs(job_dir)
    converged = False
    energy = None
    try:
        if paths["outcar"] is not None:
            converged = bool(Outcar(str(paths["outcar"])).converged)
    except Exception:
        converged = False
    try:
        if converged and paths["vasprun"] is not None:
            energy = float(Vasprun(str(paths["vasprun"])).final_energy)
    except Exception:
        energy = None
    complete = converged and paths["vasprun"] is not None and (paths["locpot"] is not None or not require_locpot)
    return {
        "job_dir": str(paths["job_dir"]),
        "outcar_path": str(paths["outcar"]) if paths["outcar"] else None,
        "vasprun_path": str(paths["vasprun"]) if paths["vasprun"] else None,
        "locpot_path": str(paths["locpot"]) if paths["locpot"] else None,
        "contcar_path": str(paths["contcar"]) if paths["contcar"] else None,
        "converged": converged,
        "complete": bool(complete),
        "energy_ev": round(energy, 8) if energy is not None else None,
    }


def _write_vasp_job_files(
    atoms: Atoms,
    job_dir: Path,
    jobname: str,
    incar_data: dict[str, Any],
    kp_length: int,
    vasp_cmd: str,
    extra_lines: str,
    copy_files: list[str],
    is_surface: bool,
) -> dict[str, Any]:
    job_dir.mkdir(parents=True, exist_ok=True)
    atoms.write_poscar(str(job_dir / "POSCAR"))
    _make_vasp_incar(incar_data).write_file(filename=str(job_dir / "INCAR"))
    _make_surface_kpoints(atoms=atoms, kp_length=kp_length, is_surface=is_surface).write_file(str(job_dir / "KPOINTS"))

    metadata = {
        "jobname": jobname,
        "vasp_cmd": vasp_cmd,
        "extra_lines": extra_lines,
        "copy_files": copy_files,
        "is_surface": is_surface,
    }
    metadata_path = _write_json(job_dir / "job_metadata.json", metadata)

    run_script = "#!/usr/bin/env bash\nset -e\n"
    if extra_lines:
        run_script += extra_lines.rstrip() + "\n"
    run_script += f"{vasp_cmd}\n"
    run_script_path = job_dir / "run_vasp.sh"
    run_script_path.write_text(run_script, encoding="utf-8")

    job_py = f'''#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import shutil
import subprocess
from pathlib import Path

from jarvis.io.vasp.inputs import Poscar, Potcar
from jarvis.io.vasp.outputs import Outcar

meta = json.loads(Path("job_metadata.json").read_text(encoding="utf-8"))
job_dir = Path.cwd()
outcar = job_dir / "OUTCAR"
if outcar.exists():
    try:
        if Outcar(str(outcar)).converged:
            print("OUTCAR already converged; skip rerun.")
            raise SystemExit(0)
    except Exception:
        pass

pos = Poscar.from_file("POSCAR")
elements = []
for element in pos.atoms.elements:
    if element not in elements:
        elements.append(element)

Potcar(elements=elements).write_file("POTCAR")
for item in meta.get("copy_files", []):
    if item and Path(item).exists():
        shutil.copy2(item, ".")

extra_lines = str(meta.get("extra_lines", ""))
vasp_cmd = str(meta.get("vasp_cmd", "mpirun vasp_std"))
if extra_lines.strip() and os.name != "nt" and shutil.which("bash"):
    cmd = "bash run_vasp.sh"
else:
    cmd = vasp_cmd
completed = subprocess.run(cmd, shell=True, check=False)
raise SystemExit(completed.returncode)
'''
    job_py_path = job_dir / "job.py"
    job_py_path.write_text(job_py, encoding="utf-8")

    return {
        "metadata_path": str(metadata_path),
        "run_script_path": str(run_script_path),
        "job_py_path": str(job_py_path),
        "poscar_path": str(job_dir / "POSCAR"),
        "incar_path": str(job_dir / "INCAR"),
        "kpoints_path": str(job_dir / "KPOINTS"),
    }


def _compute_vasp_wad(candidate: dict[str, Any]) -> float | None:
    film = candidate["film_job"]
    subs = candidate["substrate_job"]
    interface = candidate["interface_job"]
    if not (film["complete"] and subs["complete"] and interface["complete"]):
        return None
    film_en = float(film["energy_ev"])
    subs_en = float(subs["energy_ev"])
    interface_en = float(interface["energy_ev"])
    film_scale = float(candidate["film_slab_atoms"]) / float(candidate["film_surface_atoms"])
    subs_scale = float(candidate["substrate_slab_atoms"]) / float(candidate["substrate_surface_atoms"])
    m = np.array(candidate["interface_lattice_mat"])
    area = float(np.linalg.norm(np.cross(m[0], m[1])))
    return 16.0 * (interface_en - subs_scale * subs_en - film_scale * film_en) / area


def _build_vasp_analysis_payload(original_payload: dict, candidate: dict[str, Any]) -> dict:
    payload = json.loads(json.dumps(original_payload))
    inputs = payload.setdefault("inputs", {})
    material_a = inputs.setdefault("material_a", {})
    material_b = inputs.setdefault("material_b", {})
    material_a["locpot_path"] = candidate["film_job"]["locpot_path"]
    material_a["outcar_path"] = candidate["film_job"]["outcar_path"]
    material_a["vasprun_path"] = candidate["film_job"]["vasprun_path"]
    material_a["slab_output_dir"] = candidate["film_job"]["job_dir"]
    material_b["locpot_path"] = candidate["substrate_job"]["locpot_path"]
    material_b["outcar_path"] = candidate["substrate_job"]["outcar_path"]
    material_b["vasprun_path"] = candidate["substrate_job"]["vasprun_path"]
    material_b["slab_output_dir"] = candidate["substrate_job"]["job_dir"]
    iface = inputs.setdefault("interface_outputs", {})
    iface["locpot_path"] = candidate["interface_job"]["locpot_path"]
    iface["outcar_path"] = candidate["interface_job"]["outcar_path"]
    iface["vasprun_path"] = candidate["interface_job"]["vasprun_path"]
    iface["output_dir"] = candidate["interface_job"]["job_dir"]
    return payload


def _build_slab_analysis_payload(original_payload: dict, slab_jobs: dict[str, Any]) -> dict:
    payload = json.loads(json.dumps(original_payload))
    inputs = payload.setdefault("inputs", {})
    material_a = inputs.setdefault("material_a", {})
    material_b = inputs.setdefault("material_b", {})
    material_a["locpot_path"] = slab_jobs["material_a"]["locpot_path"]
    material_a["outcar_path"] = slab_jobs["material_a"]["outcar_path"]
    material_a["vasprun_path"] = slab_jobs["material_a"]["vasprun_path"]
    material_a["slab_output_dir"] = slab_jobs["material_a"]["job_dir"]
    material_b["locpot_path"] = slab_jobs["material_b"]["locpot_path"]
    material_b["outcar_path"] = slab_jobs["material_b"]["outcar_path"]
    material_b["vasprun_path"] = slab_jobs["material_b"]["vasprun_path"]
    material_b["slab_output_dir"] = slab_jobs["material_b"]["job_dir"]
    return payload


def _run_slab_vasp_closed_loop(payload: dict, output_dir: Path) -> dict:
    config = _intermat_config_from_payload(payload)
    calculator = _get_calculator_settings(payload) or {}
    vasp_cfg = calculator.get("vasp") if isinstance(calculator.get("vasp"), dict) else {}
    run_mode = str(vasp_cfg.get("run_mode") or calculator.get("run_mode") or "auto").strip().lower()
    if run_mode not in {"auto", "prepare_only", "collect_only"}:
        raise ValueError("For slab_based vasp closed-loop, run_mode must be one of: auto, prepare_only, collect_only")

    work_root = output_dir / "slab_vasp_closure"
    work_root.mkdir(parents=True, exist_ok=True)
    incar_data = dict(config.get("vasp_params", {}).get("inc", {}))
    vasp_cmd = str(config.get("vasp_params", {}).get("vasp_cmd") or "mpirun vasp_std")
    copy_files = [str(x) for x in config.get("copy_files", [])]
    kp_default = int(config.get("kp_length", 30))
    logs: list[str] = []
    artifacts: list[dict[str, str]] = []

    material_jobs = {
        "material_a": work_root / "material_a_surface",
        "material_b": work_root / "material_b_surface",
    }

    if _has_structure_route(payload["inputs"]["material_a"]) and _has_structure_route(payload["inputs"]["material_b"]):
        slab_config = dict(config)
        slab_config["disp_intvl"] = 0.0
        generated = _build_interface_generator(payload, slab_config).generate()
        if not generated:
            raise ValueError("Could not generate matched slab surfaces for slab-based vasp closure.")
        info = generated[0]
        if len(generated) > 1:
            logs.append("slab_based vasp closure ignored displacement scan and used the first matched surface candidate because surf_andersen-like analysis only needs the two surface slabs.")

        film_atoms = Atoms.from_dict(info["film_surf"])
        subs_atoms = Atoms.from_dict(info["subs_surf"])

        film_prep = _write_vasp_job_files(
            atoms=film_atoms,
            job_dir=material_jobs["material_a"],
            jobname="material_a_surface",
            incar_data=incar_data,
            kp_length=int(info.get("film_kplength", kp_default)),
            vasp_cmd=vasp_cmd,
            extra_lines=str(config.get("extra_lines", "")),
            copy_files=copy_files,
            is_surface=True,
        )
        subs_prep = _write_vasp_job_files(
            atoms=subs_atoms,
            job_dir=material_jobs["material_b"],
            jobname="material_b_surface",
            incar_data=incar_data,
            kp_length=int(info.get("subs_kplength", kp_default)),
            vasp_cmd=vasp_cmd,
            extra_lines=str(config.get("extra_lines", "")),
            copy_files=copy_files,
            is_surface=True,
        )
        for prep in (film_prep, subs_prep):
            artifacts.extend({"type": "vasp_input", "path": str(path)} for path in prep.values())
        context = {
            "surface_context": {
                "film_surface_name": info.get("film_surface_name"),
                "substrate_surface_name": info.get("subs_surface_name"),
                "film_surface_atoms": int(film_atoms.num_atoms),
                "substrate_surface_atoms": int(subs_atoms.num_atoms),
                "film_slab_atoms": int(Atoms.from_dict(info["film_sl"]).num_atoms),
                "substrate_slab_atoms": int(Atoms.from_dict(info["subs_sl"]).num_atoms),
            }
        }
    else:
        context = {
            "surface_context": {
                "film_surface_name": "material_a_surface",
                "substrate_surface_name": "material_b_surface",
            }
        }
        logs.append("slab_based vasp closure skipped surface preparation because no structure routes were provided; attempting collection-only from existing slab_vasp_closure folders.")

    slab_jobs = {
        "material_a": _vasp_job_status(material_jobs["material_a"], require_locpot=True),
        "material_b": _vasp_job_status(material_jobs["material_b"], require_locpot=True),
    }
    manifest_path = _write_json(work_root / "slab_vasp_closure_manifest.json", {"run_mode": run_mode, **context, "slab_jobs": slab_jobs})
    artifacts.append({"type": "manifest", "path": str(manifest_path)})

    results: dict[str, Any] = {
        "mode": "slab_vasp_closed_loop",
        "run_mode": run_mode,
        "run_root": str(work_root),
        "manifest_path": str(manifest_path),
        **context,
        "slab_jobs": slab_jobs,
    }

    both_complete = slab_jobs["material_a"]["complete"] and slab_jobs["material_b"]["complete"]
    if both_complete and run_mode != "prepare_only":
        analysis_payload = _build_slab_analysis_payload(payload, slab_jobs)
        slab_result = _slab_based_analysis(analysis_payload, output_dir)
        results["slab_analysis"] = {k: v for k, v in slab_result.items() if k != "artifacts"}
        artifacts.extend(slab_result["artifacts"])
        logs.append("Closed-loop slab VASP collection succeeded: slab vacuum alignment and surf_andersen-like band offsets were derived from prepared surface outputs.")
    elif both_complete and run_mode == "prepare_only":
        logs.append("Prepared slab VASP closed-loop inputs and detected completed outputs, but skipped automatic collection because run_mode=prepare_only.")
    else:
        logs.append("Prepared slab VASP closed-loop inputs. Re-run after both surface jobs finish to auto-collect slab alignment, IP/EA, and VBO/CBO.")

    return {"results": results, "artifacts": artifacts, "logs": logs}


def _run_vasp_closed_loop(payload: dict, output_dir: Path) -> dict:
    config = _intermat_config_from_payload(payload)
    calculator = _get_calculator_settings(payload) or {}
    vasp_cfg = calculator.get("vasp") if isinstance(calculator.get("vasp"), dict) else {}
    run_mode = str(vasp_cfg.get("run_mode") or calculator.get("run_mode") or "auto").strip().lower()
    if run_mode not in {"auto", "prepare_only", "collect_only"}:
        raise ValueError("For vasp closed-loop, run_mode must be one of: auto, prepare_only, collect_only")

    generator = _build_interface_generator(payload, config)
    generated = generator.generate()
    if not generated:
        raise ValueError("Interface generator did not produce any candidates for the vasp route.")

    work_root = output_dir / "vasp_closure"
    work_root.mkdir(parents=True, exist_ok=True)
    incar_data = dict(config.get("vasp_params", {}).get("inc", {}))
    vasp_cmd = str(config.get("vasp_params", {}).get("vasp_cmd") or "mpirun vasp_std")
    copy_files = [str(x) for x in config.get("copy_files", [])]
    kp_default = int(config.get("kp_length", 30))

    candidates: list[dict[str, Any]] = []
    artifacts: list[dict[str, str]] = []
    any_complete = False

    for idx, info in enumerate(generated):
        candidate_dir = work_root / f"candidate_{idx:03d}"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        film_atoms = Atoms.from_dict(info["film_surf"])
        subs_atoms = Atoms.from_dict(info["subs_surf"])
        interface_atoms = Atoms.from_dict(info["generated_interface"])
        film_job_dir = candidate_dir / "film_surface"
        subs_job_dir = candidate_dir / "substrate_surface"
        interface_job_dir = candidate_dir / "interface"

        film_prep = _write_vasp_job_files(
            atoms=film_atoms,
            job_dir=film_job_dir,
            jobname=f"film_surface_{idx:03d}",
            incar_data=incar_data,
            kp_length=int(info.get("film_kplength", kp_default)),
            vasp_cmd=vasp_cmd,
            extra_lines=str(config.get("extra_lines", "")),
            copy_files=copy_files,
            is_surface=True,
        )
        subs_prep = _write_vasp_job_files(
            atoms=subs_atoms,
            job_dir=subs_job_dir,
            jobname=f"substrate_surface_{idx:03d}",
            incar_data=incar_data,
            kp_length=int(info.get("subs_kplength", kp_default)),
            vasp_cmd=vasp_cmd,
            extra_lines=str(config.get("extra_lines", "")),
            copy_files=copy_files,
            is_surface=True,
        )
        interface_prep = _write_vasp_job_files(
            atoms=interface_atoms,
            job_dir=interface_job_dir,
            jobname=f"interface_{idx:03d}",
            incar_data=incar_data,
            kp_length=max(int(info.get("film_kplength", kp_default)), int(info.get("subs_kplength", kp_default))),
            vasp_cmd=vasp_cmd,
            extra_lines=str(config.get("extra_lines", "")),
            copy_files=copy_files,
            is_surface=False,
        )

        film_status = _vasp_job_status(film_job_dir, require_locpot=True)
        subs_status = _vasp_job_status(subs_job_dir, require_locpot=True)
        interface_status = _vasp_job_status(interface_job_dir, require_locpot=True)
        any_complete = any_complete or (film_status["complete"] and subs_status["complete"] and interface_status["complete"])

        candidate = {
            "candidate_index": idx,
            "candidate_dir": str(candidate_dir),
            "interface_name": info.get("interface_name"),
            "film_surface_name": info.get("film_surface_name"),
            "substrate_surface_name": info.get("subs_surface_name"),
            "film_surface_atoms": int(film_atoms.num_atoms),
            "substrate_surface_atoms": int(subs_atoms.num_atoms),
            "film_slab_atoms": int(Atoms.from_dict(info["film_sl"]).num_atoms),
            "substrate_slab_atoms": int(Atoms.from_dict(info["subs_sl"]).num_atoms),
            "interface_lattice_mat": _sanitize_for_json(interface_atoms.lattice_mat),
            "film_job": {**film_status, "prep": film_prep},
            "substrate_job": {**subs_status, "prep": subs_prep},
            "interface_job": {**interface_status, "prep": interface_prep},
        }
        wad = _compute_vasp_wad(candidate)
        if wad is not None:
            candidate["wad_j_per_m2"] = round(wad, 6)

        candidates.append(candidate)
        for prep in (film_prep, subs_prep, interface_prep):
            artifacts.extend({"type": "vasp_input", "path": str(path)} for path in prep.values())

    manifest_path = _write_json(work_root / "vasp_closure_manifest.json", {"candidates": candidates, "run_mode": run_mode})
    artifacts.append({"type": "manifest", "path": str(manifest_path)})

    results: dict[str, Any] = {
        "mode": "vasp_closed_loop",
        "run_mode": run_mode,
        "run_root": str(work_root),
        "candidates": candidates,
        "manifest_path": str(manifest_path),
    }
    logs: list[str] = []

    completed_candidates = [c for c in candidates if c.get("wad_j_per_m2") is not None]
    if completed_candidates and run_mode != "prepare_only":
        best = min(completed_candidates, key=lambda item: item["wad_j_per_m2"])
        analysis_payload = _build_vasp_analysis_payload(payload, best)
        slab_result = _slab_based_analysis(analysis_payload, output_dir)
        delta_v_result = _explicit_interface_delta_v_analysis(analysis_payload, output_dir)
        results["best_candidate"] = {
            "candidate_index": best["candidate_index"],
            "wad_j_per_m2": best["wad_j_per_m2"],
        }
        results["slab_analysis"] = {k: v for k, v in slab_result.items() if k != "artifacts"}
        results["explicit_interface_delta_v"] = {k: v for k, v in delta_v_result.items() if k != "artifacts"}
        artifacts.extend(slab_result["artifacts"])
        artifacts.extend(delta_v_result["artifacts"])
        logs.append("Closed-loop VASP collection succeeded: slab vacuum alignment and explicit-interface ΔV were derived from prepared candidate outputs.")
    elif any_complete and run_mode == "prepare_only":
        logs.append("Prepared VASP closed-loop inputs and detected some completed outputs, but skipped automatic collection because run_mode=prepare_only.")
    else:
        logs.append("Prepared VASP closed-loop inputs. Re-run after the surface/interface jobs finish to auto-collect slab alignment and explicit-interface ΔV.")

    return {"results": results, "artifacts": artifacts, "logs": logs}



def _explicit_interface_generation(payload: dict, output_dir: Path) -> dict:
    config = _intermat_config_from_payload(payload)
    calculator = _get_calculator_settings(payload)
    preflight = _preflight_calculator_settings(calculator, config) if calculator else None
    if preflight and not preflight["ok"]:
        reasons = "; ".join(check["name"] for check in preflight["checks"] if not check["ok"])
        raise RuntimeError(
            "Calculator preflight failed for method "
            + f"'{preflight['method']}': {reasons}. "
            + " ".join(preflight.get("hints", []))
        )

    run_dir_name = "intermat_generation"
    if calculator:
        run_dir_name = f"intermat_{calculator['method']}"
    run_dir = output_dir / run_dir_name
    intermat_result, logs, created_paths = _run_intermat_config(config, workdir=run_dir)

    structure_dict = intermat_result.get("systems")
    if not structure_dict:
        raise ValueError("intermat did not return generated interface structure data")

    atoms = Atoms.from_dict(structure_dict)
    poscar_path = output_dir / "generated_interface_POSCAR.vasp"
    atoms.write_poscar(str(poscar_path))

    config_path = _write_json(output_dir / "intermat_config.json", config)
    summary_path = _write_json(output_dir / "intermat_result_summary.json", intermat_result)

    generated_artifacts = [
        {"type": "calculator_run_path" if path.is_dir() else "calculator_run_file", "path": str(path)}
        for path in created_paths
    ]

    calculator_result = None
    if calculator:
        calculator_result = {
            "method": calculator["method"],
            "preflight": preflight,
            "do_surfaces": _as_bool(config.get("do_surfaces"), True),
            "sub_job": _as_bool(config.get("sub_job"), False),
            "run_directory": str(run_dir),
            "wads": _summarize_wads(intermat_result.get("wads"), _as_bool(config.get("do_surfaces"), True)),
        }

    interface_model = {
            "film_role": payload["inputs"]["material_a"]["name"],
            "substrate_role": payload["inputs"]["material_b"]["name"],
            "film_index": config["film_index"],
            "substrate_index": config["substrate_index"],
            "num_atoms": int(atoms.num_atoms),
            "time_taken_s": intermat_result.get("time_taken"),
    }
    if calculator_result and calculator_result.get("wads") and calculator_result["wads"].get("best_index") is not None:
        interface_model["best_interface_index"] = calculator_result["wads"]["best_index"]

    result = {
        "interface_model": interface_model,
        "intermat_summary": {
            "run_directory": str(run_dir),
            "logs": logs,
        },
        "artifacts": [
            {"type": "config", "path": str(config_path)},
            {"type": "report", "path": str(summary_path)},
            {"type": "structure", "path": str(poscar_path)},
            *generated_artifacts,
        ],
    }
    if calculator_result:
        result["calculator"] = calculator_result
    return result



def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze interface band offsets via intermat stack")
    parser.add_argument("--input", required=True, help="Path to interface-band-offset JSON input")
    parser.add_argument("--output-dir", required=True, help="Directory for generated files")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        payload = normalize_payload(load_payload(args.input))
        validate_payload(payload)

        assumptions = [
            f"Backend source: {BACKEND_SOURCE}",
            "The current intermat adapter supports validated light workflows before heavy external calculator flows.",
        ]
        if payload.get("inputs", {}).get("directory_bundle"):
            assumptions.append(
                "Resolved bulk/slab/interface directory bundle into explicit file paths before analysis."
            )
        artifacts: list[dict[str, str]] = []
        results: dict[str, Any] = {
            "backend": "intermat",
            "backend_source": BACKEND_SOURCE,
        }

        mode = payload["mode"]
        reference_result = None
        calculator_settings = _get_calculator_settings(payload)

        if mode == "quick_estimate":
            reference_result = _quick_reference_analysis(payload)
            results["reference_analysis"] = reference_result

        elif mode == "slab_based":
            if calculator_settings and calculator_settings.get("method") == "vasp":
                slab_closure = _run_slab_vasp_closed_loop(payload, output_dir)
                results["slab_generation"] = {
                    "run_root": slab_closure["results"]["run_root"],
                }
                results["slab_calculator"] = {
                    "method": "vasp",
                    "closure": slab_closure["results"],
                }
                assumptions.append(
                    "slab_based vasp route prepared matched surface-slab VASP jobs and will auto-collect surf_andersen-like vacuum alignment when completed outputs are present."
                )
                assumptions.extend(slab_closure.get("logs", []))
                artifacts.extend(slab_closure["artifacts"])
                if slab_closure["results"].get("slab_analysis"):
                    results["slab_analysis"] = slab_closure["results"]["slab_analysis"]
                    refs = results["slab_analysis"]["materials"]
                    a_name = payload["inputs"]["material_a"]["name"]
                    b_name = payload["inputs"]["material_b"]["name"]
                    results["recommended_downstream_parameters"] = {
                        "for_band_diagram_calc": {
                            "ea": {
                                a_name: refs[a_name]["derived_quantities"]["ea_ev"],
                                b_name: refs[b_name]["derived_quantities"]["ea_ev"],
                            },
                            "offset_basis": "slab_vasp_closed_loop_locpot",
                        }
                    }
            elif _has_slab_output_route(payload["inputs"]["material_a"]) and _has_slab_output_route(payload["inputs"]["material_b"]):
                slab_result = _slab_based_analysis(payload, output_dir)
                results["slab_analysis"] = {k: v for k, v in slab_result.items() if k != "artifacts"}
                artifacts.extend(slab_result["artifacts"])
                assumptions.append(
                    "slab_based path used surf_andersen-like vacuum alignment from LOCPOT/OUTCAR/vasprun.xml surface outputs."
                )
                refs = results["slab_analysis"]["materials"]
                a_name = payload["inputs"]["material_a"]["name"]
                b_name = payload["inputs"]["material_b"]["name"]
                results["recommended_downstream_parameters"] = {
                    "for_band_diagram_calc": {
                        "ea": {
                            a_name: refs[a_name]["derived_quantities"]["ea_ev"],
                            b_name: refs[b_name]["derived_quantities"]["ea_ev"],
                        },
                        "offset_basis": "surf_andersen_like_locpot",
                    }
                }
            else:
                reference_result = _quick_reference_analysis(payload)
                results["reference_analysis"] = reference_result
                assumptions.append(
                    "slab_based fell back to reference_values because slab outputs were not supplied for both materials."
                )

        elif mode == "explicit_interface":
            if _has_reference_route(payload):
                try:
                    reference_result = _quick_reference_analysis(payload)
                    results["reference_analysis"] = reference_result
                except Exception as ref_exc:
                    assumptions.append(f"Reference analysis skipped: {ref_exc}")

            if _has_interface_output_route(payload):
                delta_v_result = _explicit_interface_delta_v_analysis(payload, output_dir)
                results["explicit_interface_delta_v"] = {
                    k: v for k, v in delta_v_result.items() if k != "artifacts"
                }
                artifacts.extend(delta_v_result["artifacts"])
                assumptions.append(
                    "explicit_interface LOCPOT ΔV path used interface lineup from local LOCPOT and combined it with bulk VBM/CBM references when available."
                )
                band_offsets = results["explicit_interface_delta_v"].get("band_offsets")
                if band_offsets:
                    results["recommended_downstream_parameters"] = {
                        "for_band_diagram_calc": {
                            "band_offsets": band_offsets,
                            "offset_basis": "explicit_interface_locpot_delta_v",
                        }
                    }
                else:
                    assumptions.append(
                        "Explicit interface ΔV was computed, but bulk band-edge references were not sufficient to derive final VBO/CBO."
                    )

            if _has_structure_route(payload["inputs"]["material_a"]) and _has_structure_route(payload["inputs"]["material_b"]):
                if calculator_settings and calculator_settings.get("method") == "vasp":
                    explicit = _run_vasp_closed_loop(payload, output_dir)
                    results["explicit_interface_generation"] = {
                        "run_root": explicit["results"]["run_root"],
                        "candidate_count": len(explicit["results"].get("candidates", [])),
                    }
                    results["explicit_interface_calculator"] = {
                        "method": "vasp",
                        "closure": explicit["results"],
                    }
                    assumptions.append(
                        "explicit_interface vasp route prepared candidate-specific surface/interface VASP jobs and will auto-collect slab alignment plus explicit-interface ΔV when completed outputs are present."
                    )
                    assumptions.extend(explicit.get("logs", []))
                    artifacts.extend(explicit["artifacts"])
                    if explicit["results"].get("explicit_interface_delta_v"):
                        results["explicit_interface_delta_v"] = explicit["results"]["explicit_interface_delta_v"]
                    if explicit["results"].get("slab_analysis"):
                        results["slab_analysis"] = explicit["results"]["slab_analysis"]
                        a_name = payload["inputs"]["material_a"]["name"]
                        b_name = payload["inputs"]["material_b"]["name"]
                        refs = results["slab_analysis"]["materials"]
                        results["recommended_downstream_parameters"] = {
                            "for_band_diagram_calc": {
                                "ea": {
                                    a_name: refs[a_name]["derived_quantities"]["ea_ev"],
                                    b_name: refs[b_name]["derived_quantities"]["ea_ev"],
                                },
                                "offset_basis": "vasp_closed_loop_locpot",
                            }
                        }
                    if explicit["results"].get("explicit_interface_delta_v", {}).get("band_offsets"):
                        results["recommended_downstream_parameters"] = {
                            "for_band_diagram_calc": {
                                "band_offsets": explicit["results"]["explicit_interface_delta_v"]["band_offsets"],
                                "offset_basis": "vasp_closed_loop_explicit_interface_locpot_delta_v",
                            }
                        }
                else:
                    explicit = _explicit_interface_generation(payload, output_dir)
                    results["explicit_interface_generation"] = explicit["interface_model"]
                    if explicit.get("calculator"):
                        results["explicit_interface_calculator"] = explicit["calculator"]
                        assumptions.append(
                            f"explicit_interface calculator route executed through intermat.calculate_wad(method='{explicit['calculator']['method']}')."
                        )
                    assumptions.extend(explicit.get("intermat_summary", {}).get("logs", []))
                    artifacts.extend(explicit["artifacts"])

        if reference_result and reference_result.get("mode") == "reference_ip_ea" and "recommended_downstream_parameters" not in results:
            results["recommended_downstream_parameters"] = {
                "for_band_diagram_calc": {
                    "ea": reference_result["ea"],
                    "offset_basis": "reference_ip_ea_and_anderson_classification",
                }
            }

        result = {
            "status": "ok",
            "summary": "Completed interface-band-offset analysis through the intermat stack.",
            "assumptions": assumptions,
            "results": results,
            "artifacts": artifacts,
        }

    except Exception as exc:
        result = {
            "status": "error",
            "summary": "Failed to analyze interface-band-offset request.",
            "assumptions": [],
            "results": {},
            "artifacts": [],
            "error": str(exc),
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
