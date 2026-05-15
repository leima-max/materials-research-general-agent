#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Adapter helpers for converting band-align-plot JSON payloads into bapt config.

The generated config is written as JSON text to a .yaml file. JSON is valid YAML,
so bapt/yaml.safe_load can parse it without requiring PyYAML on the adapter side.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

ALLOWED_MODES = {"vacuum_alignment", "offset_alignment", "device_stack"}


def load_payload(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_payload(payload: dict) -> None:
    mode = payload.get("mode")
    if mode not in ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(ALLOWED_MODES))}")

    inputs = payload.get("inputs", {})
    materials = inputs.get("materials", [])
    if not materials:
        raise ValueError("inputs.materials is required and must be non-empty")

    names = [m.get("name") for m in materials]
    if any(not name for name in names):
        raise ValueError("each material must have a non-empty name")
    if len(names) != len(set(names)):
        raise ValueError("material names must be unique")

    if mode in {"vacuum_alignment", "device_stack"}:
        for material in materials:
            if "ip" not in material or "ea" not in material:
                raise ValueError(
                    f"{mode} requires ip and ea for material {material.get('name')}"
                )

    if mode == "offset_alignment":
        offsets = inputs.get("offsets", [])
        if len(materials) < 2:
            raise ValueError("offset_alignment requires at least two materials")
        if len(offsets) != len(materials) - 1:
            raise ValueError(
                "offset_alignment expects one adjacent offset entry per interface "
                f"({len(materials) - 1} required)"
            )
        for material in materials:
            if "eg" not in material:
                raise ValueError(
                    f"offset_alignment requires eg for material {material.get('name')}"
                )
        for idx, offset in enumerate(offsets):
            if offset.get("left") != materials[idx]["name"] or offset.get("right") != materials[idx + 1]["name"]:
                raise ValueError(
                    "offset entries must follow the same adjacent order as materials: "
                    f"expected {materials[idx]['name']} -> {materials[idx + 1]['name']} at index {idx}"
                )
            if "vbo" not in offset and "cbo" not in offset:
                raise ValueError("each offset entry must contain vbo or cbo")

    if mode == "device_stack":
        stack_order = inputs.get("stack_order", [])
        if not stack_order:
            raise ValueError("device_stack requires inputs.stack_order")
        if set(stack_order) != set(names):
            raise ValueError("stack_order must reference the same material names as inputs.materials")



def _ordered_materials(payload: dict) -> List[dict]:
    inputs = payload.get("inputs", {})
    materials = list(inputs.get("materials", []))
    if payload.get("mode") != "device_stack":
        return materials

    by_name = {material["name"]: material for material in materials}
    return [by_name[name] for name in inputs.get("stack_order", [])]



def _settings_from_options(payload: dict) -> dict:
    options = payload.get("options", {})
    settings = {}

    mapping = {
        "show_axis": "show_axis",
        "font": "font",
        "font_size": "label_size",
        "name_colour": "name_colour",
        "fade_cb": "fade_cb",
        "gradients": "gradients",
        "photocat": "photocat",
        "bar_width": "bar_width",
        "gap": "gap",
    }
    for src, dst in mapping.items():
        if src in options:
            settings[dst] = options[src]

    if "figure_height_inch" in options:
        settings["height"] = options["figure_height_inch"]
    if "figure_width_inch" in options:
        settings["width"] = options["figure_width_inch"]

    # bapt's show_ea flag means “display electron affinity value”; this is the
    # closest built-in analogue to “show values” for vacuum-alignment plots.
    if options.get("show_values") is True:
        settings["show_ea"] = True

    return settings



def _vacuum_compounds(payload: dict) -> List[dict]:
    compounds = []
    for material in _ordered_materials(payload):
        compound = {
            "name": material.get("label") or material["name"],
            "ip": float(material["ip"]),
            "ea": float(material["ea"]),
        }
        if "vb_colour" in material:
            compound["vb_colour"] = material["vb_colour"]
        if "cb_colour" in material:
            compound["cb_colour"] = material["cb_colour"]
        if "color" in material:
            compound.setdefault("vb_colour", material["color"])
            compound.setdefault("cb_colour", material["color"])
        if material.get("fade") is True:
            compound["fade"] = True
        compounds.append(compound)
    return compounds



def _offset_series(materials: List[dict], offsets: List[dict]) -> Tuple[str, List[float]]:
    kind = None
    absolute_values = [0.0]

    for idx, offset in enumerate(offsets):
        if "cbo" in offset and "vbo" in offset:
            raise ValueError(
                "Each offset entry must choose one basis only (vbo or cbo) in this first adapter version"
            )
        if kind is None:
            kind = "cbo" if "cbo" in offset else "vbo"
        current_kind = "cbo" if "cbo" in offset else "vbo"
        if current_kind != kind:
            raise ValueError("All offset entries must use the same basis (all cbo or all vbo)")

        delta = float(offset[current_kind])
        absolute_values.append(absolute_values[idx] + delta)

    if kind is None:
        raise ValueError("No valid offset basis detected")
    return kind, absolute_values



def _offset_compounds(payload: dict) -> List[dict]:
    materials = _ordered_materials(payload)
    offsets = payload.get("inputs", {}).get("offsets", [])
    kind, absolute_values = _offset_series(materials, offsets)

    compounds = []
    for material, absolute_value in zip(materials, absolute_values):
        compound = {
            "name": material.get("label") or material["name"],
            "band_gap": float(material["eg"]),
            kind: float(absolute_value),
        }
        if "vb_colour" in material:
            compound["vb_colour"] = material["vb_colour"]
        if "cb_colour" in material:
            compound["cb_colour"] = material["cb_colour"]
        if "color" in material:
            compound.setdefault("vb_colour", material["color"])
            compound.setdefault("cb_colour", material["color"])
        if material.get("fade") is True:
            compound["fade"] = True
        compounds.append(compound)
    return compounds



def infer_alignment_type(payload: dict) -> str:
    if payload.get("mode") == "offset_alignment":
        offsets = payload.get("inputs", {}).get("offsets", [])
        if offsets and all("vbo" in x for x in offsets):
            if any(float(x["vbo"]) > 0 for x in offsets):
                return "offset-based"
        if offsets and all("cbo" in x for x in offsets):
            return "offset-based"
        return "undetermined"

    materials = _ordered_materials(payload)
    if len(materials) >= 2:
        left = materials[0]
        right = materials[1]
        left_vb = float(left["ea"]) - float(left.get("eg", float(left["ip"]) - float(left["ea"])))
        right_vb = float(right["ea"]) - float(right.get("eg", float(right["ip"]) - float(right["ea"])))
        if float(left["ea"]) > float(right["ea"]) and left_vb < right_vb:
            return "Type-II-like"
    return "undetermined"



def payload_to_bapt_config(payload: dict) -> dict:
    validate_payload(payload)
    mode = payload["mode"]
    settings = _settings_from_options(payload)

    if mode in {"vacuum_alignment", "device_stack"}:
        compounds = _vacuum_compounds(payload)
    else:
        compounds = _offset_compounds(payload)

    return {
        "compounds": compounds,
        "settings": settings,
    }



def write_bapt_config(config: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
