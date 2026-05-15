#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = SCRIPT_DIR.parent
BOOTSTRAP_SCRIPT = SOURCE_ROOT / "scripts" / "bootstrap_band_engineering_skills.py"
SKILLS = {
    "band_align_plot": "band-align-plot",
    "band_diagram_calc": "band-diagram-calc",
    "interface_band_offset": "interface-band-offset",
}
EXPECTED_FILES = [
    "skills/band-align-plot/SKILL.md",
    "skills/band-align-plot/references/input-schema.md",
    "skills/band-align-plot/scripts/build_config.py",
    "skills/band-align-plot/scripts/render_band_align.py",
    "skills/band-align-plot/scripts/install_bapt.py",
    "skills/band-diagram-calc/SKILL.md",
    "skills/band-diagram-calc/references/input-schema.md",
    "skills/band-diagram-calc/assets/presets/materials.json",
    "skills/band-diagram-calc/scripts/install_eq_band_diagram.py",
    "skills/band-diagram-calc/scripts/solve_band_diagram.py",
    "skills/interface-band-offset/SKILL.md",
    "skills/interface-band-offset/references/input-schema.md",
    "skills/interface-band-offset/references/bulk-slab-interface-template.json",
    "skills/interface-band-offset/references/example-slab-based-minimal.json",
    "skills/interface-band-offset/references/example-explicit-interface-minimal.json",
    "skills/interface-band-offset/references/example-slab-plus-explicit-minimal.json",
    "skills/interface-band-offset/references/minimal-examples.md",
    "skills/interface-band-offset/scripts/install_intermat.py",
    "skills/interface-band-offset/scripts/run_band_offset_analysis.py",
]


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=False)



def _parse_json_stdout(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    text = (proc.stdout or "").strip()
    if not text:
        raise ValueError("Command produced empty stdout; expected JSON output")
    return json.loads(text)



def _bootstrap(work_dir: Path, install_backends: bool) -> dict[str, Any]:
    command = [sys.executable, str(BOOTSTRAP_SCRIPT), "--base-dir", str(work_dir)]
    if install_backends:
        command.append("--install-backends")
    proc = _run(command, cwd=SOURCE_ROOT)
    data = _parse_json_stdout(proc)
    data["command"] = command
    data["returncode"] = proc.returncode
    if proc.stderr.strip():
        data["stderr"] = proc.stderr.strip()
    return data



def _copy_vendors(work_dir: Path) -> dict[str, Any]:
    copied = []
    missing = []
    for skill_dir_name in SKILLS.values():
        src = SOURCE_ROOT / "skills" / skill_dir_name / "vendor" / "site-packages"
        dst = work_dir / "skills" / skill_dir_name / "vendor" / "site-packages"
        if not src.exists():
            missing.append(skill_dir_name)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        copied.append({"skill": skill_dir_name, "source": str(src), "target": str(dst)})
    return {
        "mode": "copy",
        "copied": copied,
        "missing": missing,
    }



def _vendor_availability(work_dir: Path) -> dict[str, bool]:
    return {
        key: (work_dir / "skills" / skill_dir_name / "vendor" / "site-packages").exists()
        for key, skill_dir_name in SKILLS.items()
    }



def _compile_generated_scripts(work_dir: Path) -> dict[str, Any]:
    scripts = [
        work_dir / "skills" / "band-align-plot" / "scripts" / "build_config.py",
        work_dir / "skills" / "band-align-plot" / "scripts" / "render_band_align.py",
        work_dir / "skills" / "band-diagram-calc" / "scripts" / "install_eq_band_diagram.py",
        work_dir / "skills" / "band-diagram-calc" / "scripts" / "solve_band_diagram.py",
        work_dir / "skills" / "interface-band-offset" / "scripts" / "install_intermat.py",
        work_dir / "skills" / "interface-band-offset" / "scripts" / "run_band_offset_analysis.py",
    ]
    command = [sys.executable, "-m", "py_compile", *[str(p) for p in scripts]]
    proc = _run(command, cwd=work_dir)
    return {
        "status": "ok" if proc.returncode == 0 else "error",
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "checked_scripts": [str(p) for p in scripts],
    }



def _write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path



def _prepare_payloads(work_dir: Path) -> dict[str, Path]:
    payload_dir = work_dir / "smoke_inputs"

    band_align = {
        "task": "plot band alignment",
        "mode": "vacuum_alignment",
        "inputs": {
            "title": "smoke_alignment",
            "materials": [
                {"name": "Material_A_Smoke", "ip": 5.1, "ea": 4.0, "color": "#6a5acd"},
                {"name": "Material_B_Smoke", "ip": 5.8, "ea": 3.5, "color": "#2e8b57"},
            ]
        },
        "options": {"show_axis": True, "figure_width_inch": 6.0, "figure_height_inch": 4.0},
    }

    band_diagram = {
        "task": "solve band diagram",
        "mode": "built_in_only",
        "inputs": {
            "title": "smoke_pn_junction",
            "temperature_k": 300,
            "layers": [
                {
                    "name": "p_layer",
                    "thickness_nm": 120,
                    "doping_type": "p",
                    "doping_cm3": 1e17,
                    "ea": 4.0,
                    "eg": 1.4,
                    "epsilon_r": 11.0,
                    "nc_cm3": 2.5e18,
                    "nv_cm3": 1.8e19,
                },
                {
                    "name": "n_layer",
                    "thickness_nm": 120,
                    "doping_type": "n",
                    "doping_cm3": 8e16,
                    "ea": 4.2,
                    "eg": 1.6,
                    "epsilon_r": 9.5,
                    "nc_cm3": 2.2e18,
                    "nv_cm3": 1.6e19,
                },
            ],
        },
        "options": {"grid_points": 240, "figure_dpi": 120, "solver_tolerance": 1e-6, "max_iterations": 20000},
    }

    interface = {
        "task": "analyze interface band offset",
        "mode": "quick_estimate",
        "inputs": {
            "material_a": {"name": "Material_A_Smoke"},
            "material_b": {"name": "Material_B_Smoke"},
            "reference_values": {
                "ip": {"Material_A_Smoke": 5.1, "Material_B_Smoke": 5.8},
                "ea": {"Material_A_Smoke": 4.0, "Material_B_Smoke": 3.5},
                "sources": ["smoke test reference values"],
            },
        },
        "options": {"emit_downstream_parameters": True},
    }

    return {
        "band_align": _write_json(payload_dir / "band_align_input.json", band_align),
        "band_diagram": _write_json(payload_dir / "band_diagram_input.json", band_diagram),
        "interface": _write_json(payload_dir / "interface_input.json", interface),
    }



def _expect_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(str(path))



def _check_expected_files(work_dir: Path) -> dict[str, Any]:
    missing = []
    for rel in EXPECTED_FILES:
        if not (work_dir / rel).exists():
            missing.append(rel)
    return {
        "status": "ok" if not missing else "error",
        "missing": missing,
        "checked_count": len(EXPECTED_FILES),
    }



def _run_band_align_test(work_dir: Path, payload_path: Path, backend_ready: bool) -> dict[str, Any]:
    output_dir = work_dir / "smoke_outputs" / "band_align"
    script = work_dir / "skills" / "band-align-plot" / "scripts" / "render_band_align.py"
    command = [sys.executable, str(script), "--input", str(payload_path), "--output-dir", str(output_dir)]
    if not backend_ready:
        command.append("--dry-run")
    proc = _run(command, cwd=work_dir)
    data = _parse_json_stdout(proc)
    if backend_ready:
        if data.get("status") != "ok":
            raise RuntimeError(f"band-align-plot backend run failed: {data}")
        _expect_exists(output_dir / "smoke_alignment.pdf")
    else:
        if data.get("status") != "ok":
            raise RuntimeError(f"band-align-plot dry run failed: {data}")
    return {
        "command": command,
        "returncode": proc.returncode,
        "result": data,
    }



def _run_band_diagram_test(work_dir: Path, payload_path: Path, backend_ready: bool) -> dict[str, Any]:
    if not backend_ready:
        return {"status": "skipped", "reason": "eq_band_diagram backend not prepared"}
    output_dir = work_dir / "smoke_outputs" / "band_diagram"
    script = work_dir / "skills" / "band-diagram-calc" / "scripts" / "solve_band_diagram.py"
    command = [sys.executable, str(script), "--input", str(payload_path), "--output-dir", str(output_dir)]
    proc = _run(command, cwd=work_dir)
    data = _parse_json_stdout(proc)
    if data.get("status") != "ok":
        raise RuntimeError(f"band-diagram-calc run failed: {data}")
    _expect_exists(output_dir / "smoke_pn_junction_band_profile.png")
    _expect_exists(output_dir / "smoke_pn_junction_profile.csv")
    _expect_exists(output_dir / "smoke_pn_junction_field.csv")
    return {
        "command": command,
        "returncode": proc.returncode,
        "result": data,
    }



def _run_interface_test(work_dir: Path, payload_path: Path, backend_ready: bool) -> dict[str, Any]:
    if not backend_ready:
        return {"status": "skipped", "reason": "intermat backend not prepared"}
    output_dir = work_dir / "smoke_outputs" / "interface"
    script = work_dir / "skills" / "interface-band-offset" / "scripts" / "run_band_offset_analysis.py"
    command = [sys.executable, str(script), "--input", str(payload_path), "--output-dir", str(output_dir)]
    proc = _run(command, cwd=work_dir)
    data = _parse_json_stdout(proc)
    if data.get("status") != "ok":
        raise RuntimeError(f"interface-band-offset run failed: {data}")
    return {
        "command": command,
        "returncode": proc.returncode,
        "result": data,
    }



def _run_interface_slab_mock_test(work_dir: Path) -> dict[str, Any]:
    harness = work_dir / "smoke_inputs" / "interface_slab_mock_harness.py"
    output_dir = work_dir / "smoke_outputs" / "interface_slab_mock"
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = work_dir / "skills" / "interface-band-offset" / "scripts" / "run_band_offset_analysis.py"
    harness.write_text(
        f'''from __future__ import annotations\n\nimport importlib.util\nimport json\nimport tempfile\nfrom pathlib import Path\n\nMODULE_PATH = Path(r"{script_path}")\nspec = importlib.util.spec_from_file_location("run_band_offset_analysis_testmod", MODULE_PATH)\nmod = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(mod)\n\n\nclass FakeAtoms:\n    def __init__(self, n: int):\n        self.num_atoms = n\n        self.elements = ["X"] * n\n\n\nclass FakeComposition:\n    def __init__(self, formula: str):\n        self.reduced_formula = formula\n\n\nclass FakeStructure:\n    def __init__(self, formula: str, n: int):\n        self.composition = FakeComposition(formula)\n        self.num_atoms = n\n\n\nclass FakeOutcar:\n    def __init__(self, path: str):\n        if "mat_a" in path:\n            self.bandgap = [2.5, 1.5, -1.0]\n        else:\n            self.bandgap = [1.5, 0.8, -0.7]\n\n\nclass FakeVasprun:\n    def __init__(self, path: str):\n        if "mat_a" in path:\n            self.efermi = 0.2\n            self.all_structures = [FakeStructure("Material_A_Smoke", 24)]\n        else:\n            self.efermi = 0.1\n            self.all_structures = [FakeStructure("Material_B_Smoke", 32)]\n\n\nclass FakeLocpot:\n    def __init__(self, filename: str):\n        self.filename = filename\n\n    def vac_potential(self, direction="X", Ef=0, cbm=0, vbm=0, filename="avg.png", plot=True):\n        Path(filename).write_text(f"fake plot for {{self.filename}} axis={{direction}}", encoding="utf-8")\n        if "mat_a" in self.filename:\n            avg_max = 5.0\n            formula = "Material_A_Smoke"\n            atoms = FakeAtoms(24)\n        else:\n            avg_max = 4.8\n            formula = "Material_B_Smoke"\n            atoms = FakeAtoms(32)\n        mean_profile = [0.0, 0.1, 0.05, 0.08, 0.0]\n        return mean_profile, cbm, vbm, avg_max, Ef, formula, atoms\n\n\nmod.Outcar = FakeOutcar\nmod.Vasprun = FakeVasprun\nmod.Locpot = FakeLocpot\n\nwith tempfile.TemporaryDirectory() as tmp:\n    tmp_path = Path(tmp)\n    mat_a = tmp_path / "mat_a"\n    mat_b = tmp_path / "mat_b"\n    out_dir = Path(r"{output_dir}")\n    mat_a.mkdir()\n    mat_b.mkdir()\n    out_dir.mkdir(parents=True, exist_ok=True)\n    for folder in [mat_a, mat_b]:\n        for name in ["LOCPOT", "OUTCAR", "vasprun.xml"]:\n            (folder / name).write_text("stub", encoding="utf-8")\n\n    payload = {{\n        "task": "analyze interface band offset",\n        "mode": "slab_based",\n        "inputs": {{\n            "material_a": {{"name": "Material_A_Smoke", "slab_output_dir": str(mat_a)}},\n            "material_b": {{"name": "Material_B_Smoke", "slab_output_dir": str(mat_b)}},\n        }},\n        "options": {{}},\n    }}\n\n    mod.validate_payload(payload)\n    result = mod._slab_based_analysis(payload, out_dir)\n    print(json.dumps(result, indent=2, ensure_ascii=False))\n''',
        encoding="utf-8",
    )
    command = [sys.executable, str(harness)]
    proc = _run(command, cwd=work_dir)
    data = _parse_json_stdout(proc)
    if data.get("mode") != "surf_andersen_like_locpot":
        raise RuntimeError(f"interface-band-offset slab mock route failed: {data}")
    return {
        "command": command,
        "returncode": proc.returncode,
        "result": data,
    }



def _run_interface_explicit_mock_test(work_dir: Path) -> dict[str, Any]:
    harness = work_dir / "smoke_inputs" / "interface_explicit_mock_harness.py"
    output_dir = work_dir / "smoke_outputs" / "interface_explicit_mock"
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = work_dir / "skills" / "interface-band-offset" / "scripts" / "run_band_offset_analysis.py"
    harness.write_text(
        f'''from __future__ import annotations\n\nimport importlib.util\nimport json\nimport tempfile\nfrom pathlib import Path\n\nimport numpy as np\n\nMODULE_PATH = Path(r"{script_path}")\nspec = importlib.util.spec_from_file_location("run_band_offset_analysis_testmod", MODULE_PATH)\nmod = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(mod)\n\n\nclass FakeBulkOutcar:\n    def __init__(self, path: str):\n        if "bulk_a" in path:\n            self.bandgap = [2.0, 1.2, -0.8]\n        else:\n            self.bandgap = [1.8, 0.9, -0.6]\n\n\nclass FakeInterfaceAtoms:\n    def __init__(self):\n        self.lattice_mat = np.diag([40.0, 8.0, 8.0])\n        self.volume = float(np.linalg.det(self.lattice_mat))\n        self.num_atoms = 64\n        self.elements = ["X"] * 64\n\n\nmod.Outcar = FakeBulkOutcar\n\n\ndef fake_interface_locpot_profile(locpot_path, axis="X"):\n    x = np.linspace(0.0, 40.0, 800)\n    left = 0.6 * np.cos(2 * np.pi * x / 4.0)\n    right = 0.6 * np.cos(2 * np.pi * x / 4.0) + 0.7\n    profile = np.where(x < 20.0, left, right)\n    return x, profile, FakeInterfaceAtoms()\n\n\nmod._interface_locpot_profile = fake_interface_locpot_profile\n\nwith tempfile.TemporaryDirectory() as tmp:\n    tmp_path = Path(tmp)\n    interface_dir = tmp_path / "interface"\n    interface_dir.mkdir()\n    (interface_dir / "LOCPOT").write_text("stub", encoding="utf-8")\n    bulk_a_dir = tmp_path / "bulk_a"\n    bulk_b_dir = tmp_path / "bulk_b"\n    bulk_a_dir.mkdir()\n    bulk_b_dir.mkdir()\n    (bulk_a_dir / "OUTCAR").write_text("stub", encoding="utf-8")\n    (bulk_b_dir / "OUTCAR").write_text("stub", encoding="utf-8")\n\n    payload = {{\n        "task": "analyze interface band offset",\n        "mode": "explicit_interface",\n        "inputs": {{\n            "material_a": {{"name": "Material_A_Smoke"}},\n            "material_b": {{"name": "Material_B_Smoke"}},\n            "directory_bundle": {{\n                "material_a": {{"bulk_dir": str(bulk_a_dir)}},\n                "material_b": {{"bulk_dir": str(bulk_b_dir)}},\n                "interface": {{"output_dir": str(interface_dir), "peak_width": 5}}\n            }}\n        }},\n        "options": {{}}\n    }}\n\n    payload = mod.normalize_payload(payload)\n    mod.validate_payload(payload)\n    result = mod._explicit_interface_delta_v_analysis(payload, Path(r"{output_dir}"))\n    print(json.dumps({{"normalized_payload": payload, "analysis": result}}, indent=2, ensure_ascii=False))\n''',
        encoding="utf-8",
    )
    command = [sys.executable, str(harness)]
    proc = _run(command, cwd=work_dir)
    data = _parse_json_stdout(proc)
    result = data.get("analysis", {})
    if result.get("mode") != "explicit_interface_locpot_delta_v":
        raise RuntimeError(f"interface-band-offset explicit mock route failed: {data}")
    if "band_offsets" not in result:
        raise RuntimeError(f"explicit mock route did not produce band_offsets: {data}")
    normalized = data.get("normalized_payload", {}).get("inputs", {})
    if not normalized.get("material_a", {}).get("bulk_outcar_path"):
        raise RuntimeError(f"directory_bundle did not expand bulk_outcar_path for material_a: {data}")
    if not normalized.get("interface_outputs", {}).get("locpot_path"):
        raise RuntimeError(f"directory_bundle did not expand interface locpot_path: {data}")
    return {
        "command": command,
        "returncode": proc.returncode,
        "result": data,
    }



def main() -> None:
    parser = argparse.ArgumentParser(description="Unified smoke test for the three band-engineering skills.")
    parser.add_argument("--work-dir", default="tmp_band_engineering_smoke", help="Temporary workspace for bootstrap + smoke tests.")
    parser.add_argument(
        "--backend-mode",
        choices=["copy", "install", "skip"],
        default="copy",
        help="How to prepare local skill backends inside the temporary workspace.",
    )
    parser.add_argument("--keep-workdir", action="store_true", help="Keep an existing work directory instead of deleting it first.")
    args = parser.parse_args()

    work_dir = (SOURCE_ROOT / args.work_dir).resolve()
    if work_dir.exists() and not args.keep_workdir:
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "status": "ok",
        "source_root": str(SOURCE_ROOT),
        "work_dir": str(work_dir),
        "backend_mode": args.backend_mode,
        "steps": {},
    }

    try:
        summary["steps"]["bootstrap"] = _bootstrap(work_dir, install_backends=args.backend_mode == "install")
        summary["steps"]["expected_files"] = _check_expected_files(work_dir)
        if summary["steps"]["expected_files"]["status"] != "ok":
            raise RuntimeError(f"Missing expected files: {summary['steps']['expected_files']['missing']}")

        if args.backend_mode == "copy":
            summary["steps"]["backend_prepare"] = _copy_vendors(work_dir)
        elif args.backend_mode == "install":
            summary["steps"]["backend_prepare"] = {"mode": "install", "note": "Backends prepared during bootstrap --install-backends."}
        else:
            summary["steps"]["backend_prepare"] = {"mode": "skip", "note": "Backend preparation skipped by user request."}

        summary["steps"]["vendor_availability"] = _vendor_availability(work_dir)
        summary["steps"]["py_compile"] = _compile_generated_scripts(work_dir)
        if summary["steps"]["py_compile"]["status"] != "ok":
            raise RuntimeError("Generated scripts failed py_compile")

        payloads = _prepare_payloads(work_dir)
        summary["steps"]["payloads"] = {k: str(v) for k, v in payloads.items()}

        vendors = summary["steps"]["vendor_availability"]
        summary["steps"]["band_align_test"] = _run_band_align_test(work_dir, payloads["band_align"], backend_ready=vendors["band_align_plot"])
        summary["steps"]["band_diagram_test"] = _run_band_diagram_test(work_dir, payloads["band_diagram"], backend_ready=vendors["band_diagram_calc"])
        summary["steps"]["interface_test"] = _run_interface_test(work_dir, payloads["interface"], backend_ready=vendors["interface_band_offset"])
        summary["steps"]["interface_slab_mock_test"] = _run_interface_slab_mock_test(work_dir)
        summary["steps"]["interface_explicit_mock_test"] = _run_interface_explicit_mock_test(work_dir)

    except Exception as exc:
        summary["status"] = "error"
        summary["error"] = str(exc)

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()



