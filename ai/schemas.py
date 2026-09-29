from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class HoleSpec(BaseModel):
    """Location and diameter for a through hole in millimeters."""

    model_config = ConfigDict(extra="forbid")

    diameter_mm: float = Field(..., description="Hole diameter in millimeters.")
    x_mm: float = Field(..., description="Hole center X coordinate from plate center.")
    y_mm: float = Field(..., description="Hole center Y coordinate from plate center.")


class MountingPlateSpec(BaseModel):
    """Structured specification for a rectangular mounting plate."""

    model_config = ConfigDict(extra="forbid")

    part_type: Literal["mounting_plate"] = "mounting_plate"
    width_mm: float = Field(..., description="Overall plate width in millimeters.")
    height_mm: float = Field(..., description="Overall plate height in millimeters.")
    thickness_mm: float = Field(..., description="Plate thickness in millimeters.")
    corner_radius_mm: float = Field(0, description="Outside corner radius in millimeters.")
    holes: list[HoleSpec] = Field(default_factory=list)


class BoxSpec(BaseModel):
    """Structured specification for a solid rectangular box."""

    model_config = ConfigDict(extra="forbid")

    part_type: Literal["box"] = "box"
    width_mm: float = Field(..., description="Overall box width in millimeters.")
    depth_mm: float = Field(..., description="Overall box depth in millimeters.")
    height_mm: float = Field(..., description="Overall box height in millimeters.")
    corner_radius_mm: float = Field(0, description="Vertical edge radius in millimeters.")


class CylinderSpec(BaseModel):
    """Structured specification for a cylinder, optionally with a center hole."""

    model_config = ConfigDict(extra="forbid")

    part_type: Literal["cylinder"] = "cylinder"
    diameter_mm: float = Field(..., description="Outside cylinder diameter in millimeters.")
    height_mm: float = Field(..., description="Cylinder height in millimeters.")
    center_hole_diameter_mm: float | None = Field(
        default=None,
        description="Optional through hole diameter in millimeters.",
    )


class SpacerSpec(BaseModel):
    """Structured specification for a cylindrical spacer with a center through hole."""

    model_config = ConfigDict(extra="forbid")

    part_type: Literal["spacer"] = "spacer"
    outer_diameter_mm: float = Field(..., description="Spacer outside diameter in millimeters.")
    inner_diameter_mm: float = Field(..., description="Spacer inside diameter in millimeters.")
    height_mm: float = Field(..., description="Spacer height in millimeters.")


class LBracketSpec(BaseModel):
    """Structured specification for a simple 90-degree L bracket."""

    model_config = ConfigDict(extra="forbid")

    part_type: Literal["l_bracket"] = "l_bracket"
    width_mm: float = Field(..., description="Bracket width along X in millimeters.")
    height_mm: float = Field(..., description="Vertical leg height in millimeters.")
    leg_depth_mm: float = Field(..., description="Horizontal leg depth in millimeters.")
    thickness_mm: float = Field(..., description="Material thickness in millimeters.")
    corner_radius_mm: float = Field(0, description="Optional outside edge radius in millimeters.")
    holes: list[HoleSpec] = Field(
        default_factory=list,
        description="Reserved for future face-specific holes. Ignored by this milestone.",
    )


class MountingPostSpec(BaseModel):
    """Structured specification for an enclosure mounting post."""

    model_config = ConfigDict(extra="forbid")

    x_mm: float = Field(..., description="Post center X coordinate from enclosure center.")
    y_mm: float = Field(..., description="Post center Y coordinate from enclosure center.")
    outer_diameter_mm: float = Field(..., description="Post outside diameter in millimeters.")
    hole_diameter_mm: float = Field(..., description="Post center hole diameter in millimeters.")
    height_mm: float = Field(..., description="Post height above the enclosure floor.")


class ElectronicsEnclosureSpec(BaseModel):
    """Structured specification for a simple open-top electronics enclosure."""

    model_config = ConfigDict(extra="forbid")

    part_type: Literal["electronics_enclosure"] = "electronics_enclosure"
    internal_width_mm: float = Field(..., description="Internal cavity width in millimeters.")
    internal_depth_mm: float = Field(..., description="Internal cavity depth in millimeters.")
    internal_height_mm: float = Field(..., description="Internal cavity height in millimeters.")
    wall_thickness_mm: float = Field(..., description="Side wall thickness in millimeters.")
    bottom_thickness_mm: float = Field(..., description="Bottom thickness in millimeters.")
    corner_radius_mm: float = Field(0, description="Outer vertical corner radius in millimeters.")
    mounting_posts: list[MountingPostSpec] = Field(default_factory=list)


SupportedPartSpec: TypeAlias = Annotated[
    MountingPlateSpec
    | BoxSpec
    | CylinderSpec
    | SpacerSpec
    | LBracketSpec
    | ElectronicsEnclosureSpec,
    Field(discriminator="part_type"),
]


class PromptParseResponse(BaseModel):
    """Structured AI interpretation result for a natural-language CAD prompt."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "unsupported", "missing_information"] = Field(
        ...,
        description="Whether the prompt can be converted into a supported CAD spec.",
    )
    message: str = Field(
        ...,
        description="Brief explanation for the user. State missing fields or unsupported part type.",
    )
    spec: SupportedPartSpec | None = Field(
        default=None,
        description="A complete supported CAD spec when status is success.",
    )
