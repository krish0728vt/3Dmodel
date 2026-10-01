export type HealthResponse = {
  status: "online";
  service: string;
  route_count: number;
};

export type VersionResponse = {
  app_version: string;
  schema_version: string;
  build: string | null;
  python_version: string;
  cad_engine: string;
  ai_configured: boolean;
};

export type ProjectSummary = {
  project_id: string;
  name: string;
  created_at: string;
  updated_at: string;
  current_revision: number;
  source_prompt: string | null;
  model_type: "template" | "operation_plan";
  status: "active" | "archived" | "failed";
  archived_at: string | null;
  last_opened_at: string | null;
  thumbnail_url: string | null;
  material: string | null;
};

export type RevisionSummary = {
  revision_id: string;
  project_id: string;
  revision_number: number;
  parent_revision_id: string | null;
  timestamp: string;
  user_instruction: string;
  model_type: "template" | "operation_plan";
  change_summary: string;
  step_output_path: string;
  generation_status: string;
  validation_status: string;
};

export type ProjectDetail = ProjectSummary & {
  current_revision_record: RevisionSummary | null;
  current_model: Record<string, unknown> | null;
};

export type DesignParameter = {
  parameter_id: string;
  name: string;
  value: number;
  unit: string;
  description: string | null;
  editable: boolean;
  source: string;
  role: "driving" | "derived";
};

export type ParametricRelationship = {
  relationship_id: string;
  relationship_type: string;
  description?: string | null;
  [key: string]: unknown;
};

export type ResolvedDesign = {
  parameters: DesignParameter[];
  relationships: ParametricRelationship[];
  resolved_parameters: Record<string, number>;
  derived_values: Record<string, number>;
  resolved_model: Record<string, unknown>;
  diagnostics: string[];
};

export type AssemblyTransform = {
  translation_x_mm: number;
  translation_y_mm: number;
  translation_z_mm: number;
  rotation_x_deg: number;
  rotation_y_deg: number;
  rotation_z_deg: number;
};

export type AssemblyComponent = {
  component_id: string;
  name: string;
  source_type: "project_revision" | "generated_file" | "capability_output" | "imported_file";
  project_id: string | null;
  project_revision: number | null;
  capability_output: Record<string, unknown> | null;
  external_step_path: string | null;
  external_stl_path: string | null;
  transform: AssemblyTransform;
  visible: boolean;
  grounded: boolean;
  metadata: Record<string, unknown>;
};

export type AssemblyRecord = {
  assembly_id: string;
  name: string;
  created_at: string;
  updated_at: string;
  current_revision: number;
  notes: string | null;
  status: "active" | "archived";
  archived_at: string | null;
  last_opened_at: string | null;
};

export type AssemblyRevision = {
  revision_id: string;
  assembly_id: string;
  revision_number: number;
  parent_revision_id: string | null;
  timestamp: string;
  user_instruction: string;
  change_summary: string;
  components: AssemblyComponent[];
  manifest_path: string | null;
};

export type AssemblyDetail = {
  assembly: AssemblyRecord;
  current_revision: AssemblyRevision | null;
};

export type AssemblyComponentPreview = {
  component_id: string;
  name: string;
  source_type: AssemblyComponent["source_type"];
  mesh_url: string | null;
  transform: AssemblyTransform;
  visible: boolean;
  grounded: boolean;
  bounding_box: PreviewBoundingBox | null;
};

export type AssemblyPreview = {
  assembly_id: string;
  revision: number;
  components: AssemblyComponentPreview[];
  bounding_box: PreviewBoundingBox | null;
};

export type AssemblyEngineeringSummary = {
  assembly_id: string;
  revision: number;
  component_count: number;
  component_summaries: Array<{
    component_id: string;
    name: string;
    bounding_box: PreviewBoundingBox | null;
    mass_g: number | null;
    center_of_mass: [number, number, number] | null;
    material_id: string | null;
  }>;
  bounding_box: PreviewBoundingBox | null;
  known_mass_g: number;
  unknown_mass_components: string[];
  center_of_mass: [number, number, number] | null;
  center_of_mass_status: "available" | "partial" | "unavailable";
  interferences: Array<{
    first_component_id: string;
    second_component_id: string;
    status: "NO_OVERLAP" | "POSSIBLE_OVERLAP" | "CONFIRMED_INTERFERENCE";
    method: string;
  }>;
};

export type ExportFormat = "step" | "stl" | "dxf" | "glb" | "obj" | "manifest" | "zip";

export type ExportResult = {
  export_id: string | null;
  format: ExportFormat;
  path: string;
  filename: string;
  size_bytes: number;
  checksum_sha256: string;
  created_at: string;
  warnings: string[];
  metadata: Record<string, unknown>;
};

export type ExportBatchResult = {
  request: {
    source_type: "project_revision" | "assembly_revision" | "capability_output";
    source_id: string;
    revision: number | null;
    formats: ExportFormat[];
    options: {
      stl_quality: "draft" | "standard" | "high";
      package: boolean;
      include_manifest: boolean;
      component_mode: "local" | "assembly_positioned";
    };
  };
  source_name: string;
  revision: number;
  revision_id: string | null;
  output_dir: string;
  results: ExportResult[];
  warnings: string[];
};

export type GenerateResponse = {
  project: ProjectSummary | null;
  revision: RevisionSummary | null;
  spec: Record<string, unknown>;
  step_url: string | null;
  stl_url: string | null;
  message: string;
};

export type LearningStats = {
  failures: number;
  resolved: number;
  unresolved: number;
  lessons: number;
  patterns: number;
  repairs: number;
  repair_strategies: number;
  repair_success_rate: number;
  lessons_by_status: Record<string, number>;
  patterns_by_status: Record<string, number>;
  average_lesson_confidence: number;
};

export type LessonRecord = {
  lesson_id: string;
  title: string;
  description: string;
  problem_signature: string;
  applicable_part_types: string[];
  applicable_operation_types: string[];
  status: string;
  evidence_count: number;
  success_count: number;
  failure_count: number;
  confidence_score: number;
  contradiction_count: number;
  last_verified_at: string | null;
  source_type: string;
};

export type PatternRecord = {
  pattern_id: string;
  name: string;
  description: string;
  applicable_operation_types: string[];
  operation_signature: string | null;
  usage_count: number;
  success_count: number;
  failure_count: number;
  confidence_score: number;
  status: string;
  last_verified_at: string | null;
};

export type FailureAnalytics = {
  signature: string;
  error_category: string;
  count: number;
};

export type RepairStrategyRecord = {
  strategy_signature: string;
  problem_signature: string;
  strategy: string;
  attempts: number;
  successes: number;
  failures: number;
  confidence_score: number;
  status: string;
  last_used_at: string | null;
};

export type CapabilityAnalytics = {
  capability_id: string;
  name: string;
  version: string;
  enabled: boolean;
  trust_level: string;
  invocation_count: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
};

export type CapabilityRecord = {
  capability_id: string;
  name: string;
  version: string;
  description: string;
  provider_type: string;
  source: string;
  trust_level: string;
  enabled: boolean;
  validation_status: string;
  supported_operations: string[];
  required_dependencies: string[];
  last_tested_at: string | null;
  approved_at: string | null;
  risk_notes: string | null;
  input_schema: Record<string, unknown>;
  output_type: string;
  metrics: {
    invocation_count: number;
    success_count: number;
    failure_count: number;
    last_success_at: string | null;
    last_failure_at: string | null;
  };
};

export type DiscoverySource = {
  source_id: string;
  name: string;
  source_type: string;
  location: string;
  enabled: boolean;
  trusted: boolean;
  notes: string | null;
};

export type MaterialSpec = {
  material_id: string;
  display_name: string;
  category: string;
  density_g_cm3: number;
  notes: string | null;
};

export type EngineeringWarning = {
  warning_id: string;
  severity: "INFO" | "WARNING" | "ERROR";
  category: string;
  title: string;
  message: string;
  related_operation_id: string | null;
  recommendation: string | null;
};

export type EngineeringReport = {
  project_id: string | null;
  revision_number: number | null;
  geometry_metrics: {
    volume_mm3: number;
    surface_area_mm2: number;
    size: { x_mm: number; y_mm: number; z_mm: number };
    center_of_mass: { x_mm: number; y_mm: number; z_mm: number };
    solid_count: number;
  };
  display_metrics: {
    length_unit: "mm" | "in";
    x: number;
    y: number;
    z: number;
  };
  material: MaterialSpec | null;
  mass_estimate: {
    material_id: string;
    density_g_cm3: number;
    volume_cm3: number;
    mass_g: number;
    mass_kg: number;
    estimate_basis: string;
  } | null;
  manufacturing_process: "unknown" | "3d_printing" | "cnc_machining";
  warnings: EngineeringWarning[];
  generated_at: string;
};

export type PreviewBoundingBox = {
  xmin: number;
  ymin: number;
  zmin: number;
  xmax: number;
  ymax: number;
  zmax: number;
  xlen: number;
  ylen: number;
  zlen: number;
};

export type SketchPreviewEntity = {
  entity_type: string;
  points: Array<[number, number, number]>;
};

export type PreviewObject = {
  operation_id: string;
  label: string;
  operation_type: string;
  object_type: "solid" | "sketch" | "subtractive_helper" | "helper" | "final_solid";
  mesh_url: string | null;
  bounding_box: PreviewBoundingBox | null;
  visible_by_default: boolean;
  selectable: boolean;
  source_operation: Record<string, unknown> | null;
  sketch_entities: SketchPreviewEntity[];
  notes: string | null;
};

export type RevisionPreview = {
  project_id: string;
  revision: number;
  preview_format: "semantic-stl-preview";
  units: "mm";
  final_mesh_url: string;
  objects: PreviewObject[];
  overall_bounding_box: PreviewBoundingBox | null;
  limitations: string[];
};

export type SelectionState = {
  selectedOperationId: string | null;
  selectedLabel: string | null;
  selectedObjectType: string | null;
  selectedMeshId: string | null;
  source: "viewer" | "design_tree" | "inspector" | null;
};

export type EvaluationStage = {
  name: string;
  success: boolean;
  skipped: boolean;
  duration_ms: number;
  message: string | null;
};

export type EvaluationResult = {
  case_id: string;
  name: string;
  category: string;
  difficulty: string;
  mode: string;
  duration_ms: number;
  failure_category: string | null;
  failure_message: string | null;
  metrics: Record<string, unknown>;
  stages: EvaluationStage[];
  overall_status: "pass" | "fail" | "unsupported" | "skipped";
};

export type EvaluationReport = {
  suite: string;
  milestone: string;
  generated_at: string;
  deterministic: boolean;
  live_ai: boolean;
  case_count: number;
  metrics: {
    total_cases: number;
    pass_count: number;
    fail_count: number;
    unsupported_count: number;
    skipped_count: number;
    parse_success_rate: number;
    schema_success_rate: number;
    cad_generation_success_rate: number;
    step_export_success_rate: number;
    stl_export_success_rate: number;
    repair_success_rate: number;
    parametric_preservation_rate: number;
    assembly_success_rate: number;
    capability_success_rate: number;
    category: Record<string, { total: number; pass: number; fail: number; unsupported: number; success_rate: number }>;
    difficulty: Record<string, { total: number; pass: number; fail: number; unsupported: number; success_rate: number }>;
    failure_distribution: Record<string, number>;
    total_duration_ms: number;
    average_duration_ms: number;
    slowest_cases: Array<Record<string, unknown>>;
  };
  regressions: Array<{
    case_id: string;
    previous_status: string | null;
    current_status: string;
    regression_type: string;
    message: string;
  }>;
  results: EvaluationResult[];
};
