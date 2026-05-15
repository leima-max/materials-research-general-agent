#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LOCAL_VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"
PRESET_PATH = SKILL_DIR / "assets" / "presets" / "materials.json"
ALLOWED_MODES = {"full_profile", "built_in_only", "compare_structures"}


def _load_backend():
    backend_source = "path"
    if LOCAL_VENDOR_DIR.exists() and str(LOCAL_VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(LOCAL_VENDOR_DIR))
        backend_source = "local_vendor"

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import eq_band_diagram as eq
        return np, plt, eq, backend_source
    except Exception as exc:
        raise RuntimeError(
            "eq_band_diagram backend is not available. Run scripts/install_eq_band_diagram.py first."
        ) from exc


np, plt, eq, BACKEND_SOURCE = _load_backend()


def load_payload(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_presets() -> dict:
    if not PRESET_PATH.exists():
        return {}
    return json.loads(PRESET_PATH.read_text(encoding="utf-8"))


def validate_payload(payload: dict) -> None:
    mode = payload.get("mode")
    if mode not in ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(ALLOWED_MODES))}")

    if mode == "compare_structures":
        structures = payload.get("inputs", {}).get("structures", [])
        if not structures:
            raise ValueError("compare_structures requires inputs.structures")
        for structure in structures:
            _validate_structure(structure, compare_mode=True)
    else:
        _validate_structure(payload.get("inputs", {}), compare_mode=False)



def _validate_structure(inputs: dict, compare_mode: bool) -> None:
    layers = inputs.get("layers", [])
    if not layers:
        raise ValueError("inputs.layers is required and must be non-empty")

    for layer in layers:
        for key in ["name", "thickness_nm", "doping_type", "doping_cm3"]:
            if key not in layer:
                raise ValueError(f"layer {layer.get('name', '<unknown>')} missing required field: {key}")
        if layer["doping_type"] not in {"n", "p", "intrinsic"}:
            raise ValueError(f"layer {layer['name']} has invalid doping_type {layer['doping_type']}")
        if "material_key" not in layer:
            for key in ["ea", "eg", "epsilon_r", "nc_cm3", "nv_cm3"]:
                if key not in layer:
                    raise ValueError(
                        f"layer {layer['name']} needs either material_key or explicit field {key}"
                    )



def _temperature_from_inputs(inputs: dict) -> float:
    return float(inputs.get("temperature_k", 300.0))



def _set_backend_temperature(temperature_k: float) -> None:
    eq.kT_in_eV = 8.617333262145e-5 * temperature_k



def _resolve_material_spec(layer: dict, presets: dict) -> dict:
    if "material_key" in layer:
        key = layer["material_key"]
        if key not in presets:
            raise ValueError(f"Unknown material_key '{key}' for layer {layer['name']}")
        spec = dict(presets[key])
        for override_key in ["ea", "eg", "epsilon_r", "nc_cm3", "nv_cm3"]:
            if override_key in layer:
                spec[override_key] = layer[override_key]
        spec.setdefault("name", layer["name"])
        return spec

    return {
        "name": layer["name"],
        "ea": layer["ea"],
        "eg": layer["eg"],
        "epsilon_r": layer["epsilon_r"],
        "nc_cm3": layer["nc_cm3"],
        "nv_cm3": layer["nv_cm3"],
    }



def _build_backend_layer(layer: dict, presets: dict):
    spec = _resolve_material_spec(layer, presets)
    material = eq.Material(
        NC=float(spec["nc_cm3"]),
        NV=float(spec["nv_cm3"]),
        EG=float(spec["eg"]),
        chi=float(spec["ea"]),
        eps=float(spec["epsilon_r"]),
        name=str(spec.get("name", layer["name"])),
    )
    doping_type = layer["doping_type"]
    backend_type = "n" if doping_type == "intrinsic" else doping_type
    backend_doping = 0.0 if doping_type == "intrinsic" else float(layer["doping_cm3"])
    backend_layer = eq.Layer(
        matl=material,
        n_or_p=backend_type,
        doping=backend_doping,
        thickness=float(layer["thickness_nm"]),
    )
    backend_layer.skill_layer_name = layer["name"]
    return backend_layer



def _layer_name_series(layers_backend: list[Any], points: Any) -> list[str]:
    names = []
    for pt in points:
        info = eq.where_am_I(layers_backend, float(pt))
        current_layer = info["current_layer"]
        names.append(getattr(current_layer, "skill_layer_name", current_layer.matl.name))
    return names



def _charge_from_dopants_series(layers_backend: list[Any], points: Any) -> Any:
    charge = np.zeros(len(points))
    for i, pt in enumerate(points):
        layer = eq.where_am_I(layers_backend, float(pt))["current_layer"]
        if layer.n_or_p == "n":
            charge[i] = layer.doping
        elif layer.n_or_p == "p":
            charge[i] = -layer.doping
        else:
            raise ValueError("Unexpected doping polarity in backend layer")
    return charge



def _material_series(layers_backend: list[Any], points: Any):
    mats = []
    for pt in points:
        mats.append(eq.where_am_I(layers_backend, float(pt))["current_layer"].matl)
    return mats



def _compute_depletion_width(points: Any, net_charge: Any, layer_names: list[str]) -> dict:
    dx = float(points[1] - points[0]) if len(points) > 1 else 0.0
    max_abs_charge = float(np.max(np.abs(net_charge))) if len(net_charge) else 0.0
    threshold = max(max_abs_charge * 0.05, 1e10)
    depleted_mask = np.abs(net_charge) > threshold

    by_layer: dict[str, float] = {}
    for mask_value, layer_name in zip(depleted_mask, layer_names):
        if mask_value:
            by_layer[layer_name] = by_layer.get(layer_name, 0.0) + dx

    total = sum(by_layer.values())
    return {
        "method": "|net_charge| > max(5% of peak, 1e10 e/cm^3)",
        "total": round(total, 3),
        "by_layer": {k: round(v, 3) for k, v in by_layer.items()},
    }



def _write_profile_csv(output_dir: Path, stem: str, rows: list[list[Any]]) -> Path:
    path = output_dir / f"{stem}_profile.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "x_nm",
            "layer",
            "Evac_eV",
            "Ec_eV",
            "Ev_eV",
            "Ef_eV",
            "field_V_per_nm",
            "field_V_per_cm",
            "net_charge_e_per_cm3",
            "n_cm3",
            "p_cm3",
        ])
        writer.writerows(rows)
    return path



def _write_field_csv(output_dir: Path, stem: str, points: Any, field_v_per_nm: Any) -> Path:
    path = output_dir / f"{stem}_field.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["x_nm", "field_V_per_nm", "field_V_per_cm"])
        for x, field in zip(points, field_v_per_nm):
            writer.writerow([round(float(x), 6), round(float(field), 10), round(float(field) * 1e7, 3)])
    return path



def _plot_bands(output_dir: Path, stem: str, points: Any, ec: Any, ev: Any, ef: Any, title: str, dpi: int = 200) -> Path:
    fig = plt.figure(figsize=(8, 5), dpi=dpi)
    ax = fig.add_subplot(111)
    ax.plot(points, ec, label="Ec", color="black")
    ax.plot(points, ev, label="Ev", color="black")
    ax.plot(points, ef, label="Ef", color="red", linestyle="--")
    ax.set_xlabel("Position (nm)")
    ax.set_ylabel("Electron energy (eV)")
    ax.set_title(title)
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    path = output_dir / f"{stem}_band_profile.png"
    fig.savefig(path)
    plt.close(fig)
    return path



def _structure_stem(name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in name).strip("_")
    return safe or "structure"



def _solve_one_structure(inputs: dict, output_dir: Path, name: str, options: dict, presets: dict) -> dict:
    temperature_k = _temperature_from_inputs(inputs)
    _set_backend_temperature(temperature_k)

    backend_layers = [_build_backend_layer(layer, presets) for layer in inputs["layers"]]
    grid_points = int(options.get("grid_points", 400))
    tol = float(options.get("solver_tolerance", 1e-6))
    max_iterations = float(options.get("max_iterations", 20000))
    bc = inputs.get("boundary_conditions", {})
    evac_start = bc.get("evac_start")
    evac_end = bc.get("evac_end")

    backend_stdout = io.StringIO()
    with contextlib.redirect_stdout(backend_stdout):
        calc = eq.calc_layer_stack(
            backend_layers,
            num_points=grid_points,
            tol=tol,
            max_iterations=max_iterations,
            Evac_start=evac_start,
            Evac_end=evac_end,
        )
    backend_messages = [line.strip() for line in backend_stdout.getvalue().splitlines() if line.strip()]

    points = calc["points"]
    evac = calc["Evac"]
    mats = _material_series(backend_layers, points)
    chi = np.array([m.chi for m in mats])
    eg = np.array([m.EG for m in mats])
    ni = np.array([m.ni for m in mats])
    evac_minus_ei = np.array([m.Evac_minus_Ei for m in mats])
    layer_names = _layer_name_series(backend_layers, points)
    charge_from_dopants = _charge_from_dopants_series(backend_layers, points)
    local = eq.local_charge(evac_minus_ei, ni, charge_from_dopants, evac)

    ec = evac - chi
    ev = ec - eg
    ef = np.zeros(len(points))
    field_v_per_nm = -np.gradient(evac, points)
    field_peak_v_per_cm = float(np.max(np.abs(field_v_per_nm))) * 1e7
    built_in_potential_v = abs(float(evac[-1] - evac[0]))
    depletion = _compute_depletion_width(points, local["net_charge"], layer_names)

    stem = _structure_stem(name)
    rows = []
    for i in range(len(points)):
        rows.append([
            round(float(points[i]), 6),
            layer_names[i],
            round(float(evac[i]), 10),
            round(float(ec[i]), 10),
            round(float(ev[i]), 10),
            round(float(ef[i]), 10),
            round(float(field_v_per_nm[i]), 10),
            round(float(field_v_per_nm[i]) * 1e7, 3),
            round(float(local["net_charge"][i]), 3),
            round(float(local["n"][i]), 3),
            round(float(local["p"][i]), 3),
        ])

    profile_csv = _write_profile_csv(output_dir, stem, rows)
    field_csv = _write_field_csv(output_dir, stem, points, field_v_per_nm)
    figure_path = _plot_bands(output_dir, stem, points, ec, ev, ef, title=name, dpi=int(options.get("figure_dpi", 200)))

    assumptions = []
    if abs(temperature_k - 300.0) > 1e-6:
        assumptions.append(
            f"Backend global kT was reset to match temperature_k={temperature_k:g} K for this run."
        )
    if any(layer["doping_type"] == "intrinsic" for layer in inputs["layers"]):
        assumptions.append("Intrinsic layers are passed to the backend as zero-doped 'n' layers.")

    return {
        "name": name,
        "assumptions": assumptions,
        "backend_messages": backend_messages,
        "results": {
            "built_in_potential_v": round(built_in_potential_v, 6),
            "depletion_width_nm": depletion,
            "electric_field_peak_v_per_cm": round(field_peak_v_per_cm, 3),
            "profiles": {
                "ec_ev_ef_csv": str(profile_csv),
                "field_csv": str(field_csv),
            },
        },
        "artifacts": [
            {"type": "figure", "path": str(figure_path)},
            {"type": "data", "path": str(profile_csv)},
            {"type": "data", "path": str(field_csv)},
        ],
    }



def main() -> None:
    parser = argparse.ArgumentParser(description="Solve equilibrium band diagrams via eq_band_diagram")
    parser.add_argument("--input", required=True, help="Path to band-diagram-calc JSON input")
    parser.add_argument("--output-dir", required=True, help="Directory for generated files")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        payload = load_payload(args.input)
        validate_payload(payload)
        options = payload.get("options", {})
        presets = load_presets()

        assumptions = [
            f"Backend source: {BACKEND_SOURCE}",
            "eq_band_diagram is an equilibrium 1D solver, not a non-equilibrium TCAD engine.",
        ]

        if payload["mode"] == "compare_structures":
            structures_out = []
            artifacts = []
            for structure in payload["inputs"]["structures"]:
                name = structure.get("name", "structure")
                solved = _solve_one_structure(structure, output_dir, name, options, presets)
                structures_out.append({
                    "name": solved["name"],
                    **solved["results"],
                })
                assumptions.extend(solved["assumptions"])
                for msg in solved.get("backend_messages", []):
                    assumptions.append(f"{name}: {msg}")
                artifacts.extend(solved["artifacts"])

            result = {
                "status": "ok",
                "summary": f"Solved {len(structures_out)} structures with eq_band_diagram.",
                "assumptions": assumptions,
                "results": {
                    "backend": "eq_band_diagram",
                    "backend_source": BACKEND_SOURCE,
                    "structures": structures_out,
                },
                "artifacts": artifacts,
            }
        else:
            name = payload.get("inputs", {}).get("title") or "band_diagram"
            solved = _solve_one_structure(payload["inputs"], output_dir, name, options, presets)
            assumptions.extend(solved["assumptions"])
            assumptions.extend(solved.get("backend_messages", []))
            result = {
                "status": "ok",
                "summary": "Solved the equilibrium band diagram through eq_band_diagram.",
                "assumptions": assumptions,
                "results": {
                    "backend": "eq_band_diagram",
                    "backend_source": BACKEND_SOURCE,
                    **solved["results"],
                },
                "artifacts": solved["artifacts"],
            }

    except Exception as exc:
        result = {
            "status": "error",
            "summary": "Failed to solve the band diagram.",
            "assumptions": [],
            "results": {},
            "artifacts": [],
            "error": str(exc),
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
