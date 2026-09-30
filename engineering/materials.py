from __future__ import annotations

from engineering.models import MaterialSpec


class UnknownMaterialError(ValueError):
    """Raised when a material ID is not registered."""


_MATERIALS: dict[str, MaterialSpec] = {
    "pla": MaterialSpec(material_id="pla", display_name="PLA", category="plastic", density_g_cm3=1.24),
    "petg": MaterialSpec(material_id="petg", display_name="PETG", category="plastic", density_g_cm3=1.27),
    "abs": MaterialSpec(material_id="abs", display_name="ABS", category="plastic", density_g_cm3=1.04),
    "nylon": MaterialSpec(material_id="nylon", display_name="Nylon", category="plastic", density_g_cm3=1.15),
    "tpu": MaterialSpec(material_id="tpu", display_name="TPU", category="plastic", density_g_cm3=1.21),
    "aluminum_6061": MaterialSpec(
        material_id="aluminum_6061",
        display_name="Aluminum 6061",
        category="metal",
        density_g_cm3=2.70,
    ),
    "aluminum_7075": MaterialSpec(
        material_id="aluminum_7075",
        display_name="Aluminum 7075",
        category="metal",
        density_g_cm3=2.81,
    ),
    "mild_steel": MaterialSpec(material_id="mild_steel", display_name="Mild Steel", category="metal", density_g_cm3=7.85),
    "stainless_steel_304": MaterialSpec(
        material_id="stainless_steel_304",
        display_name="Stainless Steel 304",
        category="metal",
        density_g_cm3=8.00,
    ),
    "generic_plastic": MaterialSpec(
        material_id="generic_plastic",
        display_name="Generic Plastic",
        category="plastic",
        density_g_cm3=1.10,
        notes="General estimate when exact plastic is unknown.",
    ),
    "generic_aluminum": MaterialSpec(
        material_id="generic_aluminum",
        display_name="Generic Aluminum",
        category="metal",
        density_g_cm3=2.70,
    ),
    "generic_steel": MaterialSpec(
        material_id="generic_steel",
        display_name="Generic Steel",
        category="metal",
        density_g_cm3=7.85,
    ),
}


def list_materials() -> list[MaterialSpec]:
    return sorted(_MATERIALS.values(), key=lambda material: material.display_name)


def get_material(material_id: str | None) -> MaterialSpec | None:
    if material_id is None or material_id == "":
        return None
    key = material_id.strip().lower()
    if key not in _MATERIALS:
        raise UnknownMaterialError(f"Unknown material: {material_id}")
    return _MATERIALS[key]
