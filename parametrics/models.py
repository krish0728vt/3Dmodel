from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class DesignParameter(BaseModel):
    """Named design intent parameter."""

    model_config = ConfigDict(extra="forbid")

    parameter_id: str
    name: str
    value: float
    unit: str = "mm"
    description: str | None = None
    editable: bool = True
    source: Literal["user", "parser", "template", "relationship", "capability", "manual"] = "user"
    role: Literal["driving", "derived"] = "driving"


class LiteralExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression_type: Literal["literal"] = "literal"
    value: float


class ParameterReferenceExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression_type: Literal["parameter_ref"] = "parameter_ref"
    parameter_id: str


class BinaryExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression_type: Literal["add", "subtract", "multiply", "divide", "min", "max"]
    left: "Expression"
    right: "Expression"


Expression = Annotated[
    LiteralExpression | ParameterReferenceExpression | BinaryExpression,
    Field(discriminator="expression_type"),
]


class FixedRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    relationship_type: Literal["fixed"] = "fixed"
    target: str
    value: float | Expression
    description: str | None = None
    provenance: Literal["explicit", "inferred", "manual"] = "explicit"


class DependentDimensionRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    relationship_type: Literal["dependent_dimension"] = "dependent_dimension"
    target_parameter: str
    expression: Expression
    description: str | None = None
    provenance: Literal["explicit", "inferred", "manual"] = "explicit"


class EdgeOffsetRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    relationship_type: Literal["edge_offset"] = "edge_offset"
    target: str
    reference_object: str
    reference_edge: Literal["left", "right", "top", "bottom", "front", "back"]
    offset_mm: float | Expression
    axis: Literal["x", "y", "z"]
    description: str | None = None
    provenance: Literal["explicit", "inferred", "manual"] = "explicit"


class CenteredRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    relationship_type: Literal["centered"] = "centered"
    target_id: str
    reference_id: str
    axes: Literal["x", "y", "z", "xy", "xyz"] = "xy"
    description: str | None = None
    provenance: Literal["explicit", "inferred", "manual"] = "explicit"


class AlignedRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    relationship_type: Literal["aligned"] = "aligned"
    target_id: str
    reference_id: str
    axes: list[Literal["x", "y", "z"]]
    description: str | None = None
    provenance: Literal["explicit", "inferred", "manual"] = "explicit"


class SymmetricRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    relationship_type: Literal["symmetric"] = "symmetric"
    target_ids: tuple[str, str]
    reference_object: str
    axis: Literal["x", "y", "z"]
    description: str | None = None
    provenance: Literal["explicit", "inferred", "manual"] = "explicit"


class EqualSpacingRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    relationship_type: Literal["equal_spacing"] = "equal_spacing"
    target_ids: list[str]
    axis: Literal["x", "y", "z"]
    start: float | Expression
    end: float | Expression
    description: str | None = None
    provenance: Literal["explicit", "inferred", "manual"] = "explicit"


class RelativePositionRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    relationship_type: Literal["relative_position"] = "relative_position"
    target_id: str
    reference_id: str
    axis: Literal["x", "y", "z"]
    offset_mm: float | Expression
    description: str | None = None
    provenance: Literal["explicit", "inferred", "manual"] = "explicit"


ParametricRelationship = Annotated[
    FixedRelationship
    | DependentDimensionRelationship
    | EdgeOffsetRelationship
    | CenteredRelationship
    | AlignedRelationship
    | SymmetricRelationship
    | EqualSpacingRelationship
    | RelativePositionRelationship,
    Field(discriminator="relationship_type"),
]
