from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from parametrics.models import DesignParameter, ParametricRelationship


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
    parameters: list[DesignParameter] = Field(default_factory=list)
    relationships: list[ParametricRelationship] = Field(default_factory=list)


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
    parameters: list[DesignParameter] = Field(default_factory=list)
    relationships: list[ParametricRelationship] = Field(default_factory=list)


SupportedPartSpec: TypeAlias = Annotated[
    MountingPlateSpec
    | BoxSpec
    | CylinderSpec
    | SpacerSpec
    | LBracketSpec
    | ElectronicsEnclosureSpec,
    Field(discriminator="part_type"),
]


Point3D: TypeAlias = tuple[float, float, float]
Point2D: TypeAlias = tuple[float, float]
Plane: TypeAlias = Literal["XY", "XZ", "YZ"]
Axis: TypeAlias = Literal["x", "y", "z"]
Direction: TypeAlias = Literal["positive", "negative"]
ExtentType: TypeAlias = Literal["blind", "through_all"]
FaceSelector: TypeAlias = Literal[
    "top_face",
    "bottom_face",
    "front_face",
    "back_face",
    "left_face",
    "right_face",
    "all_faces",
]
EdgeSelector: TypeAlias = Literal[
    "all_edges",
    "vertical_edges",
    "horizontal_edges",
    "top_edges",
    "bottom_edges",
    "outer_edges",
]


class SelectionSpec(BaseModel):
    """Typed allowlisted geometry selection for future semantic targeting."""

    model_config = ConfigDict(extra="forbid")

    selection_type: Literal["face", "edge"]
    target_id: str
    selector: FaceSelector | EdgeSelector
    index: int | None = None


class LineEntity(BaseModel):
    """Straight sketch segment."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["line"] = "line"
    start: Point2D
    end: Point2D


class PolylineEntity(BaseModel):
    """Polyline sketch path or profile."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["polyline"] = "polyline"
    points: list[Point2D]
    closed: bool = False


class RectangleEntity(BaseModel):
    """Rectangular sketch profile."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["rectangle"] = "rectangle"
    width_mm: float
    height_mm: float
    center: Point2D = (0, 0)


class CircleEntity(BaseModel):
    """Circular sketch profile."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["circle"] = "circle"
    center: Point2D = (0, 0)
    diameter_mm: float


class ArcEntity(BaseModel):
    """Three-point arc sketch path."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["arc"] = "arc"
    start: Point2D
    mid: Point2D
    end: Point2D


class PolygonEntity(BaseModel):
    """Regular polygon sketch profile."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["polygon"] = "polygon"
    center: Point2D = (0, 0)
    radius_mm: float
    sides: int
    rotation_deg: float = 0


class SlotEntity(BaseModel):
    """Capsule/slot sketch profile."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["slot"] = "slot"
    center: Point2D = (0, 0)
    length_mm: float
    width_mm: float
    rotation_deg: float = 0


SketchEntity: TypeAlias = Annotated[
    LineEntity
    | PolylineEntity
    | RectangleEntity
    | CircleEntity
    | ArcEntity
    | PolygonEntity
    | SlotEntity,
    Field(discriminator="entity_type"),
]


class SketchPlan(BaseModel):
    """Structured sketch made of allowlisted 2D entities."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    plane: Plane = "XY"
    origin: Point3D = (0, 0, 0)
    entities: list[SketchEntity]
    closed: bool = True


class CreateBoxOperation(BaseModel):
    """Create a solid rectangular prism."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["create_box"] = "create_box"
    width_mm: float
    depth_mm: float
    height_mm: float
    center: Point3D = (0, 0, 0)


class CreateCylinderOperation(BaseModel):
    """Create a cylindrical solid."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["create_cylinder"] = "create_cylinder"
    diameter_mm: float
    height_mm: float
    center: Point3D = (0, 0, 0)
    axis: Axis = "z"


class CreateSketchRectangleOperation(BaseModel):
    """Create a rectangular sketch/profile."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["create_sketch_rectangle"] = "create_sketch_rectangle"
    width_mm: float
    height_mm: float
    plane: Plane = "XY"
    center: Point3D = (0, 0, 0)


class CreateSketchCircleOperation(BaseModel):
    """Create a circular sketch/profile."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["create_sketch_circle"] = "create_sketch_circle"
    diameter_mm: float
    plane: Plane = "XY"
    center: Point3D = (0, 0, 0)


class ExtrudeOperation(BaseModel):
    """Extrude a sketch/profile into a solid."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["extrude"] = "extrude"
    sketch_id: str
    distance_mm: float
    symmetric: bool = False
    direction: Direction = "positive"


class RevolveOperation(BaseModel):
    """Revolve a sketch/profile around a global axis."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["revolve"] = "revolve"
    sketch_id: str
    angle_deg: float = 360
    axis: Axis = "z"


class CutHoleOperation(BaseModel):
    """Cut a cylindrical hole in a target solid."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["cut_hole"] = "cut_hole"
    target_id: str
    diameter_mm: float
    position: Point2D = (0, 0)
    direction: Axis = "z"
    depth_mm: float | None = None


class CreateSketchOperation(BaseModel):
    """Create a structured sketch from typed entities."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["create_sketch"] = "create_sketch"
    sketch: SketchPlan


class CutExtrudeOperation(BaseModel):
    """Cut a closed sketch from a target solid."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["cut_extrude"] = "cut_extrude"
    target_id: str
    sketch_id: str
    distance_mm: float | None = None
    extent_type: ExtentType = "blind"
    direction: Direction = "negative"


class LoftOperation(BaseModel):
    """Loft between multiple structured sketch profiles."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["loft"] = "loft"
    sketch_ids: list[str]
    ruled: bool = False
    solid: bool = True


class SweepOperation(BaseModel):
    """Sweep a closed profile along a structured path sketch."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["sweep"] = "sweep"
    profile_sketch_id: str
    path_sketch_id: str
    make_solid: bool = True


class ShellOperation(BaseModel):
    """Shell a solid with an optional removed face selector."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["shell"] = "shell"
    target_id: str
    thickness_mm: float
    remove_face_selector: FaceSelector | None = None


class ThroughHoleOperation(BaseModel):
    """Cut a through hole from an allowlisted face selector."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["through_hole"] = "through_hole"
    target_id: str
    position: Point2D = (0, 0)
    hole_diameter_mm: float
    face_selector: FaceSelector = "top_face"


class BlindHoleOperation(BaseModel):
    """Cut a blind cylindrical hole from an allowlisted face selector."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["blind_hole"] = "blind_hole"
    target_id: str
    position: Point2D = (0, 0)
    hole_diameter_mm: float
    depth_mm: float
    face_selector: FaceSelector = "top_face"


class CounterboreHoleOperation(BaseModel):
    """Cut a counterbored hole from an allowlisted face selector."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["counterbore_hole"] = "counterbore_hole"
    target_id: str
    position: Point2D = (0, 0)
    hole_diameter_mm: float
    counterbore_diameter_mm: float
    counterbore_depth_mm: float
    face_selector: FaceSelector = "top_face"


class CountersinkHoleOperation(BaseModel):
    """Cut a countersunk hole from an allowlisted face selector."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["countersink_hole"] = "countersink_hole"
    target_id: str
    position: Point2D = (0, 0)
    hole_diameter_mm: float
    countersink_diameter_mm: float
    angle_deg: float = 90
    face_selector: FaceSelector = "top_face"


class BossOperation(BaseModel):
    """Union a cylindrical boss onto a target solid."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["boss"] = "boss"
    target_id: str
    position: Point2D = (0, 0)
    diameter_mm: float
    height_mm: float
    face_selector: FaceSelector = "top_face"


class RibOperation(BaseModel):
    """Union a simple rectangular reinforcing rib onto a target solid."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["rib"] = "rib"
    target_id: str
    start: Point2D
    end: Point2D
    thickness_mm: float
    height_mm: float
    face_selector: FaceSelector = "top_face"


class RectangularHolePatternOperation(BaseModel):
    """Cut a rectangular grid of through holes."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["rectangular_hole_pattern"] = "rectangular_hole_pattern"
    target_id: str
    hole_diameter_mm: float
    count_x: int
    count_y: int
    spacing_x_mm: float
    spacing_y_mm: float
    center: Point2D = (0, 0)
    face_selector: FaceSelector = "top_face"


class CircularHolePatternOperation(BaseModel):
    """Cut a circular/radial pattern of through holes."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["circular_hole_pattern"] = "circular_hole_pattern"
    target_id: str
    hole_diameter_mm: float
    count: int
    radius_mm: float
    center: Point2D = (0, 0)
    start_angle_deg: float = 0
    face_selector: FaceSelector = "top_face"


class BooleanUnionOperation(BaseModel):
    """Union two solid objects."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["boolean_union"] = "boolean_union"
    target_id: str
    tool_id: str


class BooleanCutOperation(BaseModel):
    """Cut one solid object from another."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["boolean_cut"] = "boolean_cut"
    target_id: str
    tool_id: str


class FilletOperation(BaseModel):
    """Apply a fillet using an allowlisted edge selector."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["fillet"] = "fillet"
    target_id: str
    radius_mm: float
    edge_selector: EdgeSelector = "all_edges"


class ChamferOperation(BaseModel):
    """Apply a chamfer using an allowlisted edge selector."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["chamfer"] = "chamfer"
    target_id: str
    distance_mm: float
    edge_selector: EdgeSelector = "all_edges"


class LinearPatternOperation(BaseModel):
    """Pattern a complete solid along a global axis direction."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["linear_pattern"] = "linear_pattern"
    target_id: str
    direction: Axis = "x"
    spacing_mm: float
    count: int


class CircularPatternOperation(BaseModel):
    """Pattern a complete solid around a global axis."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["circular_pattern"] = "circular_pattern"
    target_id: str
    axis: Axis = "z"
    count: int
    angle_deg: float = 360


class MirrorOperation(BaseModel):
    """Mirror a complete solid across a major plane and union it with the original."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["mirror"] = "mirror"
    target_id: str
    plane: Plane = "YZ"


class ExternalCapabilityOperation(BaseModel):
    """Invoke an approved/enabled external capability through the centralized gate."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None
    operation_type: Literal["external_capability"] = "external_capability"
    capability_id: str
    arguments: dict[str, Any]
    output_id: str | None = None


OperationSpec: TypeAlias = Annotated[
    CreateBoxOperation
    | CreateCylinderOperation
    | CreateSketchOperation
    | CreateSketchRectangleOperation
    | CreateSketchCircleOperation
    | ExtrudeOperation
    | RevolveOperation
    | CutHoleOperation
    | CutExtrudeOperation
    | LoftOperation
    | SweepOperation
    | ShellOperation
    | ThroughHoleOperation
    | BlindHoleOperation
    | CounterboreHoleOperation
    | CountersinkHoleOperation
    | BossOperation
    | RibOperation
    | RectangularHolePatternOperation
    | CircularHolePatternOperation
    | BooleanUnionOperation
    | BooleanCutOperation
    | FilletOperation
    | ChamferOperation
    | LinearPatternOperation
    | CircularPatternOperation
    | MirrorOperation
    | ExternalCapabilityOperation,
    Field(discriminator="operation_type"),
]


class OperationPlan(BaseModel):
    """Safe, structured operation-based CAD plan."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.2"
    project_name: str
    units: Literal["mm"] = "mm"
    parameters: list[DesignParameter] = Field(default_factory=list)
    relationships: list[ParametricRelationship] = Field(default_factory=list)
    operations: list[OperationSpec]
    final_object_id: str | None = None


SupportedDesignSpec: TypeAlias = SupportedPartSpec | OperationPlan


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
    spec: SupportedDesignSpec | None = Field(
        default=None,
        description="A complete supported CAD spec when status is success.",
    )
