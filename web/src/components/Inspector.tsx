import { useEffect, useMemo, useState } from "react";

import { assemblyDownloadUrl, exportDownloadUrl } from "../api/client";
import type { AssemblyDetail, AssemblyEngineeringSummary, AssemblyPreview, AssemblyRecord, CapabilityAnalytics, CapabilityRecord, DiscoverySource, EvaluationReport, ExportBatchResult, ExportFormat, FailureAnalytics, LearningStats, LessonRecord, PatternRecord, PreviewObject, ProjectDetail, RepairStrategyRecord, ResolvedDesign, RevisionPreview, SelectionState } from "../types/api";
import type { EngineeringReport, MaterialSpec } from "../types/api";
import { EngineeringPanel } from "./EngineeringPanel";
import { operationDetails, operationDisplayName, operationKind, templateDetails } from "../utils/modelFormatting";

type InspectorProps = {
  project: ProjectDetail | null;
  preview: RevisionPreview | null;
  selection: SelectionState;
  assemblies: AssemblyRecord[];
  selectedAssembly: AssemblyDetail | null;
  assemblyPreview: AssemblyPreview | null;
  assemblyEngineering: AssemblyEngineeringSummary | null;
  exportResult: ExportBatchResult | null;
  evaluationReport: EvaluationReport | null;
  learningStats: LearningStats | null;
  resolvedDesign: ResolvedDesign | null;
  lessons: LessonRecord[];
  patterns: PatternRecord[];
  repairStrategies: RepairStrategyRecord[];
  failureAnalytics: FailureAnalytics[];
  capabilityAnalytics: CapabilityAnalytics[];
  capabilities: CapabilityRecord[];
  capabilitySources: DiscoverySource[];
  engineeringReport: EngineeringReport | null;
  materials: MaterialSpec[];
  materialId: string;
  process: string;
  displayUnits: "mm" | "in";
  onMaterialChange: (materialId: string) => void;
  onProcessChange: (process: string) => void;
  onDisplayUnitsChange: (unit: "mm" | "in") => void;
  onSelectOperation: (operationId: string) => void;
  onStructuredEdit: (instruction: string, edit: Record<string, unknown>) => void;
  onUpdateDesignParameter: (parameterId: string, value: number) => void;
  onCreateAssemblyFromProject: () => void;
  onSelectAssembly: (assemblyId: string) => void;
  onAddProjectToAssembly: (assemblyId: string) => void;
  onEditAssembly: (assemblyId: string, edit: Record<string, unknown>, instruction: string) => void;
  onRenameAssembly: (assemblyId: string) => void;
  onDuplicateAssembly: (assemblyId: string) => void;
  onArchiveAssembly: (assemblyId: string) => void;
  onDeleteAssembly: (assemblyId: string) => void;
  onExport: (payload: {
    source_type: "project_revision" | "assembly_revision";
    source_id: string;
    revision: number;
    formats: ExportFormat[];
    options: {
      stl_quality: "draft" | "standard" | "high";
      package: boolean;
      include_manifest: boolean;
      component_mode?: "local" | "assembly_positioned";
    };
  }) => void;
  onDiscoverCapabilities: (sourceId?: string) => void;
  onTestCapability: (capabilityId: string) => void;
  onApproveCapability: (capabilityId: string) => void;
  onEnableCapability: (capabilityId: string) => void;
  onDisableCapability: (capabilityId: string) => void;
  onRevalidateLesson: (lessonId: string) => void;
  onDeprecateLesson: (lessonId: string) => void;
  onRevalidatePattern: (patternId: string) => void;
  onDeprecatePattern: (patternId: string) => void;
};

export function Inspector({
  project,
  preview,
  selection,
  assemblies,
  selectedAssembly,
  assemblyPreview,
  assemblyEngineering,
  exportResult,
  evaluationReport,
  learningStats,
  resolvedDesign,
  lessons,
  patterns,
  repairStrategies,
  failureAnalytics,
  capabilityAnalytics,
  capabilities,
  capabilitySources,
  engineeringReport,
  materials,
  materialId,
  process,
  displayUnits,
  onMaterialChange,
  onProcessChange,
  onDisplayUnitsChange,
  onSelectOperation,
  onStructuredEdit,
  onUpdateDesignParameter,
  onCreateAssemblyFromProject,
  onSelectAssembly,
  onAddProjectToAssembly,
  onEditAssembly,
  onRenameAssembly,
  onDuplicateAssembly,
  onArchiveAssembly,
  onDeleteAssembly,
  onExport,
  onDiscoverCapabilities,
  onTestCapability,
  onApproveCapability,
  onEnableCapability,
  onDisableCapability,
  onRevalidateLesson,
  onDeprecateLesson,
  onRevalidatePattern,
  onDeprecatePattern
}: InspectorProps) {
  const model = project?.current_model;
  const operations = Array.isArray(model?.operations) ? (model.operations as Record<string, unknown>[]) : [];
  const selectedOperation = operations.find((operation) => String(operation.id) === selection.selectedOperationId) ?? null;
  const selectedPreview = preview?.objects.find((object) => object.operation_id === selection.selectedOperationId) ?? null;

  return (
    <aside className="panel inspector-panel">
      <div className="panel-title">Inspector</div>
      {project ? (
        <div className="inspector-stack">
          <section>
            <h3>{project.name}</h3>
            <dl>
              <dt>ID</dt>
              <dd>{project.project_id}</dd>
              <dt>Type</dt>
              <dd>{project.model_type}</dd>
              <dt>Revision</dt>
              <dd>{project.current_revision}</dd>
            </dl>
          </section>
          <SelectionInspector
            selectedOperation={selectedOperation}
            selectedPreview={selectedPreview}
            templateModel={operations.length === 0 ? project.current_model : null}
            onStructuredEdit={onStructuredEdit}
          />
          <DesignIntentPanel resolvedDesign={resolvedDesign} onUpdateDesignParameter={onUpdateDesignParameter} />
          <AssemblyPanel
            project={project}
            assemblies={assemblies}
            selectedAssembly={selectedAssembly}
            preview={assemblyPreview}
            engineering={assemblyEngineering}
            onCreateFromProject={onCreateAssemblyFromProject}
            onSelectAssembly={onSelectAssembly}
            onAddProjectToAssembly={onAddProjectToAssembly}
            onEditAssembly={onEditAssembly}
            onRenameAssembly={onRenameAssembly}
            onDuplicateAssembly={onDuplicateAssembly}
            onArchiveAssembly={onArchiveAssembly}
            onDeleteAssembly={onDeleteAssembly}
          />
          <ExportPanel project={project} selectedAssembly={selectedAssembly} exportResult={exportResult} onExport={onExport} />
          <section>
            <h3>Parameters</h3>
            {operations.length > 0 ? (
              <div className="feature-list">
                {operations.map((operation) => (
                  <button
                    type="button"
                    className={selection.selectedOperationId === String(operation.id) ? "feature-item active" : "feature-item"}
                    key={String(operation.id)}
                    onClick={() => onSelectOperation(String(operation.id))}
                  >
                    <div className="feature-heading">
                      <strong>{operationDisplayName(operation)}</strong>
                      <small>{operationKind(operation)}</small>
                    </div>
                    <dl>
                      {operationDetails(operation).map(([key, value]) => (
                        <div className="feature-row" key={key}>
                          <dt>{key}</dt>
                          <dd>{value}</dd>
                        </div>
                      ))}
                    </dl>
                  </button>
                ))}
              </div>
            ) : (
              <dl>
                {templateDetails(project.current_model ?? {}).map(([key, value]) => (
                  <div className="feature-row" key={key}>
                    <dt>{key}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>
        </div>
      ) : (
        <div className="muted">Select or generate a project.</div>
      )}
      <section className="system-section">
        <EngineeringPanel
          report={engineeringReport}
          materials={materials}
          materialId={materialId}
          process={process}
          displayUnits={displayUnits}
          onMaterialChange={onMaterialChange}
          onProcessChange={onProcessChange}
          onDisplayUnitsChange={onDisplayUnitsChange}
        />
      </section>
      <LearningDashboard
        stats={learningStats}
        lessons={lessons}
        patterns={patterns}
        repairStrategies={repairStrategies}
        failures={failureAnalytics}
        capabilityAnalytics={capabilityAnalytics}
        onRevalidateLesson={onRevalidateLesson}
        onDeprecateLesson={onDeprecateLesson}
        onRevalidatePattern={onRevalidatePattern}
        onDeprecatePattern={onDeprecatePattern}
      />
      <EvaluationPanel report={evaluationReport} />
      <CapabilityManager
        capabilities={capabilities}
        sources={capabilitySources}
        onDiscoverCapabilities={onDiscoverCapabilities}
        onTestCapability={onTestCapability}
        onApproveCapability={onApproveCapability}
        onEnableCapability={onEnableCapability}
        onDisableCapability={onDisableCapability}
      />
    </aside>
  );
}

function EvaluationPanel({ report }: { report: EvaluationReport | null }) {
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const failed = report?.results.filter((result) => result.overall_status === "fail") ?? [];
  const selected = report?.results.find((result) => result.case_id === selectedCaseId) ?? failed[0] ?? report?.results[0] ?? null;

  return (
    <section className="system-section evaluation-panel">
      <h3>Evaluation</h3>
      {report ? (
        <>
          <div className="learning-stat-grid">
            <Metric label="Cases" value={String(report.metrics.total_cases)} />
            <Metric label="Passed" value={String(report.metrics.pass_count)} />
            <Metric label="Failed" value={String(report.metrics.fail_count)} />
            <Metric label="Regressions" value={String(report.regressions.length)} />
          </div>
          <div className="status-strip">
            <span>Stages</span>
            <small>Parser: {report.metrics.parse_success_rate}%</small>
            <small>CAD: {report.metrics.cad_generation_success_rate}%</small>
            <small>STEP: {report.metrics.step_export_success_rate}%</small>
            <small>STL: {report.metrics.stl_export_success_rate}%</small>
          </div>
          <div className="learning-list">
            <strong>Categories</strong>
            {Object.entries(report.metrics.category).slice(0, 6).map(([category, data]) => (
              <div className="learning-item" key={category}>
                <span>{category}</span>
                <small>{data.pass}/{data.total} pass / {data.success_rate}%</small>
              </div>
            ))}
          </div>
          <div className="learning-list">
            <strong>{failed.length ? "Failed Cases" : "Case Detail"}</strong>
            {(failed.length ? failed : report.results.slice(0, 3)).map((result) => (
              <div className="learning-item" key={result.case_id}>
                <span>{result.name}</span>
                <small>{result.case_id} / {result.overall_status}</small>
                <div className="mini-actions">
                  <button type="button" onClick={() => setSelectedCaseId(result.case_id)}>Inspect</button>
                </div>
              </div>
            ))}
          </div>
          {selected ? (
            <div className="learning-detail">
              <strong>{selected.name}</strong>
              <dl>
                <DetailRow label="Status" value={selected.overall_status} />
                <DetailRow label="Category" value={selected.category} />
                <DetailRow label="Failure" value={selected.failure_category ?? "none"} />
              </dl>
              <div className="stage-list">
                {selected.stages.map((stage) => (
                  <small key={stage.name}>{stage.success ? "PASS" : "FAIL"} / {stage.name}{stage.message ? ` / ${stage.message}` : ""}</small>
                ))}
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <div className="muted">No evaluation report found. Run python app.py evaluate smoke.</div>
      )}
    </section>
  );
}

type LearningDashboardProps = {
  stats: LearningStats | null;
  lessons: LessonRecord[];
  patterns: PatternRecord[];
  repairStrategies: RepairStrategyRecord[];
  failures: FailureAnalytics[];
  capabilityAnalytics: CapabilityAnalytics[];
  onRevalidateLesson: (lessonId: string) => void;
  onDeprecateLesson: (lessonId: string) => void;
  onRevalidatePattern: (patternId: string) => void;
  onDeprecatePattern: (patternId: string) => void;
};

type DesignIntentPanelProps = {
  resolvedDesign: ResolvedDesign | null;
  onUpdateDesignParameter: (parameterId: string, value: number) => void;
};

type AssemblyPanelProps = {
  project: ProjectDetail;
  assemblies: AssemblyRecord[];
  selectedAssembly: AssemblyDetail | null;
  preview: AssemblyPreview | null;
  engineering: AssemblyEngineeringSummary | null;
  onCreateFromProject: () => void;
  onSelectAssembly: (assemblyId: string) => void;
  onAddProjectToAssembly: (assemblyId: string) => void;
  onEditAssembly: (assemblyId: string, edit: Record<string, unknown>, instruction: string) => void;
  onRenameAssembly: (assemblyId: string) => void;
  onDuplicateAssembly: (assemblyId: string) => void;
  onArchiveAssembly: (assemblyId: string) => void;
  onDeleteAssembly: (assemblyId: string) => void;
};

function AssemblyPanel({
  project,
  assemblies,
  selectedAssembly,
  preview,
  engineering,
  onCreateFromProject,
  onSelectAssembly,
  onAddProjectToAssembly,
  onEditAssembly,
  onRenameAssembly,
  onDuplicateAssembly,
  onArchiveAssembly,
  onDeleteAssembly
}: AssemblyPanelProps) {
  const current = selectedAssembly?.current_revision;
  const selectedAssemblyId = selectedAssembly?.assembly.assembly_id ?? "";

  function nudge(componentId: string, axis: "x" | "y" | "z", amount: number) {
    if (!selectedAssemblyId) {
      return;
    }
    onEditAssembly(
      selectedAssemblyId,
      {
        edit_type: "move_component",
        component_id: componentId,
        dx_mm: axis === "x" ? amount : 0,
        dy_mm: axis === "y" ? amount : 0,
        dz_mm: axis === "z" ? amount : 0
      },
      `Move ${componentId} ${amount} mm on ${axis.toUpperCase()}`
    );
  }

  function rotate(componentId: string, amount: number) {
    if (!selectedAssemblyId) {
      return;
    }
    onEditAssembly(
      selectedAssemblyId,
      {
        edit_type: "rotate_component",
        component_id: componentId,
        rz_deg: amount
      },
      `Rotate ${componentId} ${amount} degrees around Z`
    );
  }

  return (
    <section className="assembly-panel">
      <div className="section-heading-row">
        <h3>Assembly</h3>
        <button type="button" className="tool-button compact" onClick={onCreateFromProject}>
          New
        </button>
      </div>
      {assemblies.length > 0 ? (
        <div className="assembly-select-row">
          <select value={selectedAssemblyId} onChange={(event) => onSelectAssembly(event.target.value)}>
            {assemblies.map((assembly) => (
              <option value={assembly.assembly_id} key={assembly.assembly_id}>
                {assembly.name}
              </option>
            ))}
          </select>
          {selectedAssemblyId ? (
            <button type="button" className="tool-button compact" onClick={() => onAddProjectToAssembly(selectedAssemblyId)}>
              Add Current
            </button>
          ) : null}
        </div>
      ) : (
        <div className="muted">Create an assembly from {project.name}.</div>
      )}
      {selectedAssembly && current ? (
        <>
          <div className="assembly-summary">
            <Metric label="Revision" value={String(current.revision_number)} />
            <Metric label="Parts" value={String(current.components.length)} />
            <Metric label="Mass" value={engineering?.known_mass_g ? `${engineering.known_mass_g.toFixed(1)} g` : "unknown"} />
            <Metric label="Issues" value={String(engineering?.interferences.length ?? 0)} />
          </div>
          <div className="assembly-actions">
            <a className="tool-button compact" href={assemblyDownloadUrl(selectedAssembly.assembly.assembly_id)}>
              Manifest
            </a>
            <button type="button" className="tool-button compact" onClick={() => onRenameAssembly(selectedAssembly.assembly.assembly_id)}>
              Rename
            </button>
            <button type="button" className="tool-button compact" onClick={() => onDuplicateAssembly(selectedAssembly.assembly.assembly_id)}>
              Duplicate
            </button>
            <button type="button" className="tool-button compact" onClick={() => onArchiveAssembly(selectedAssembly.assembly.assembly_id)}>
              {selectedAssembly.assembly.status === "archived" ? "Unarchive" : "Archive"}
            </button>
            <button type="button" className="tool-button compact danger" onClick={() => onDeleteAssembly(selectedAssembly.assembly.assembly_id)}>
              Delete
            </button>
          </div>
          <div className="assembly-component-list">
            {current.components.map((component) => {
              const componentPreview = preview?.components.find((item) => item.component_id === component.component_id);
              return (
                <div className="assembly-component" key={component.component_id}>
                  <div className="feature-heading">
                    <strong>{component.name}</strong>
                    <small>{component.visible ? "VISIBLE" : "HIDDEN"} / {component.grounded ? "GROUNDED" : "FREE"}</small>
                  </div>
                  <dl>
                    <DetailRow label="Source" value={component.source_type} />
                    <DetailRow label="X/Y/Z" value={`${formatNumber(component.transform.translation_x_mm)}, ${formatNumber(component.transform.translation_y_mm)}, ${formatNumber(component.transform.translation_z_mm)}`} />
                    <DetailRow label="Rot Z" value={`${formatNumber(component.transform.rotation_z_deg)} deg`} />
                    <DetailRow label="BBox" value={componentPreview?.bounding_box ? `${formatNumber(componentPreview.bounding_box.xlen)} x ${formatNumber(componentPreview.bounding_box.ylen)} x ${formatNumber(componentPreview.bounding_box.zlen)} mm` : "unavailable"} />
                  </dl>
                  <div className="assembly-controls">
                    <button type="button" onClick={() => nudge(component.component_id, "x", -5)} title="Move X negative">X-</button>
                    <button type="button" onClick={() => nudge(component.component_id, "x", 5)} title="Move X positive">X+</button>
                    <button type="button" onClick={() => nudge(component.component_id, "y", -5)} title="Move Y negative">Y-</button>
                    <button type="button" onClick={() => nudge(component.component_id, "y", 5)} title="Move Y positive">Y+</button>
                    <button type="button" onClick={() => nudge(component.component_id, "z", 5)} title="Move Z positive">Z+</button>
                    <button type="button" onClick={() => rotate(component.component_id, 15)} title="Rotate around Z">RZ</button>
                    <button
                      type="button"
                      onClick={() => onEditAssembly(selectedAssemblyId, { edit_type: "set_visibility", component_id: component.component_id, visible: !component.visible }, `Toggle ${component.component_id} visibility`)}
                      title="Toggle visibility"
                    >
                      {component.visible ? "Hide" : "Show"}
                    </button>
                    <button
                      type="button"
                      onClick={() => onEditAssembly(selectedAssemblyId, { edit_type: "set_grounded", component_id: component.component_id, grounded: !component.grounded }, `Toggle ${component.component_id} grounded state`)}
                      title="Toggle grounded state"
                    >
                      {component.grounded ? "Free" : "Ground"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          {engineering?.interferences.length ? (
            <div className="assembly-warning">
              {engineering.interferences.map((item) => (
                <small key={`${item.first_component_id}-${item.second_component_id}`}>
                  {item.status}: {item.first_component_id} / {item.second_component_id}
                </small>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

type ExportPanelProps = {
  project: ProjectDetail;
  selectedAssembly: AssemblyDetail | null;
  exportResult: ExportBatchResult | null;
  onExport: InspectorProps["onExport"];
};

const ALL_EXPORT_FORMATS: ExportFormat[] = ["step", "stl", "dxf", "glb", "obj"];

function ExportPanel({ project, selectedAssembly, exportResult, onExport }: ExportPanelProps) {
  const [source, setSource] = useState<"project_revision" | "assembly_revision">("project_revision");
  const [formats, setFormats] = useState<ExportFormat[]>(["step", "stl"]);
  const [quality, setQuality] = useState<"draft" | "standard" | "high">("standard");
  const [makePackage, setMakePackage] = useState(false);
  const projectRevision = project.current_revision_record?.revision_number ?? project.current_revision;
  const assemblyRevision = selectedAssembly?.current_revision?.revision_number ?? null;
  const canUseAssembly = Boolean(selectedAssembly && assemblyRevision);
  const activeSource = source === "assembly_revision" && canUseAssembly ? "assembly_revision" : "project_revision";

  function toggle(format: ExportFormat) {
    setFormats((current) => (current.includes(format) ? current.filter((item) => item !== format) : [...current, format]));
  }

  function disabledReason(format: ExportFormat): string | null {
    if (format === "glb" || format === "obj") {
      return "Deferred until a reliable local exporter is available";
    }
    if (format === "dxf" && activeSource !== "project_revision") {
      return "DXF is limited to structured 2D project sketches";
    }
    return null;
  }

  function submit() {
    const selectedFormats = formats.filter((format) => !disabledReason(format));
    if (selectedFormats.length === 0) {
      return;
    }
    if (activeSource === "assembly_revision" && selectedAssembly && assemblyRevision) {
      onExport({
        source_type: "assembly_revision",
        source_id: selectedAssembly.assembly.assembly_id,
        revision: assemblyRevision,
        formats: selectedFormats,
        options: {
          stl_quality: quality,
          package: makePackage,
          include_manifest: true,
          component_mode: "assembly_positioned"
        }
      });
      return;
    }
    onExport({
      source_type: "project_revision",
      source_id: project.project_id,
      revision: projectRevision,
      formats: selectedFormats,
      options: {
        stl_quality: quality,
        package: makePackage,
        include_manifest: true
      }
    });
  }

  return (
    <section className="export-panel">
      <h3>Export</h3>
      <div className="export-source-row">
        <button type="button" className={activeSource === "project_revision" ? "source-chip active" : "source-chip"} onClick={() => setSource("project_revision")}>
          Project
        </button>
        <button type="button" className={activeSource === "assembly_revision" ? "source-chip active" : "source-chip"} disabled={!canUseAssembly} onClick={() => setSource("assembly_revision")}>
          Assembly
        </button>
      </div>
      <div className="export-format-grid">
        {ALL_EXPORT_FORMATS.map((format) => {
          const reason = disabledReason(format);
          return (
            <label className={reason ? "format-option disabled" : "format-option"} key={format} title={reason ?? format.toUpperCase()}>
              <input type="checkbox" checked={formats.includes(format)} disabled={Boolean(reason)} onChange={() => toggle(format)} />
              <span>{format.toUpperCase()}</span>
            </label>
          );
        })}
      </div>
      {formats.includes("stl") ? (
        <label className="export-quality">
          STL Quality
          <select value={quality} onChange={(event) => setQuality(event.target.value as "draft" | "standard" | "high")}>
            <option value="draft">Draft - small and fast</option>
            <option value="standard">Standard - balanced</option>
            <option value="high">High - finer mesh</option>
          </select>
        </label>
      ) : null}
      <label className="format-option">
        <input type="checkbox" checked={makePackage} onChange={(event) => setMakePackage(event.target.checked)} />
        <span>ZIP package</span>
      </label>
      <button type="button" className="tool-button" onClick={submit}>
        Export Revision
      </button>
      {exportResult ? (
        <div className="export-results">
          <strong>{exportResult.source_name} REV {exportResult.revision}</strong>
          {exportResult.results.map((result) => (
            <div className="export-result" key={`${result.format}-${result.filename}`}>
              <span>{result.format.toUpperCase()}</span>
              <small>{result.filename}</small>
              <small>{formatBytes(result.size_bytes)} / SHA256 {result.checksum_sha256.slice(0, 8)}...</small>
              {result.export_id ? (
                <a className="tool-button compact" href={exportDownloadUrl(result.export_id)}>
                  Download
                </a>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function DesignIntentPanel({ resolvedDesign, onUpdateDesignParameter }: DesignIntentPanelProps) {
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const parameters = resolvedDesign?.parameters ?? [];
  const relationships = resolvedDesign?.relationships ?? [];
  const derivedValues = resolvedDesign?.derived_values ?? {};

  useEffect(() => {
    setDraftValues(Object.fromEntries(parameters.map((parameter) => [parameter.parameter_id, String(parameter.value)])));
  }, [parameters]);

  if (parameters.length === 0 && relationships.length === 0) {
    return null;
  }

  function submit(parameterId: string) {
    const value = Number(draftValues[parameterId]);
    if (Number.isFinite(value)) {
      onUpdateDesignParameter(parameterId, value);
    }
  }

  return (
    <section className="design-intent-panel">
      <h3>Design Intent</h3>
      <div className="intent-list">
        <strong>Parameters</strong>
        {parameters.map((parameter) => (
          <div className="intent-row" key={parameter.parameter_id}>
            <div>
              <span>{parameter.name}</span>
              <small>{parameter.role.toUpperCase()} - {parameter.unit}</small>
            </div>
            {parameter.editable && parameter.role === "driving" ? (
              <div className="parameter-edit">
                <input
                  value={draftValues[parameter.parameter_id] ?? ""}
                  onChange={(event) => setDraftValues((current) => ({ ...current, [parameter.parameter_id]: event.target.value }))}
                />
                <button type="button" onClick={() => submit(parameter.parameter_id)}>Apply</button>
              </div>
            ) : (
              <strong>{formatNumber(parameter.value)}</strong>
            )}
          </div>
        ))}
      </div>
      <div className="intent-list">
        <strong>Relationships</strong>
        {relationships.slice(0, 8).map((relationship) => (
          <div className="relationship-badge" key={relationship.relationship_id}>
            <span>{relationship.relationship_type.replace(/_/g, " ").toUpperCase()}</span>
            <small>{relationship.relationship_id.replace(/_/g, " ")}</small>
          </div>
        ))}
      </div>
      {Object.keys(derivedValues).length > 0 ? (
        <div className="intent-list">
          <strong>Resolved Values</strong>
          {Object.entries(derivedValues).slice(0, 8).map(([path, value]) => (
            <div className="feature-row" key={path}>
              <dt>{path}</dt>
              <dd>{formatNumber(value)}</dd>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function LearningDashboard({
  stats,
  lessons,
  patterns,
  repairStrategies,
  failures,
  capabilityAnalytics,
  onRevalidateLesson,
  onDeprecateLesson,
  onRevalidatePattern,
  onDeprecatePattern
}: LearningDashboardProps) {
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null);
  const [selectedPatternId, setSelectedPatternId] = useState<string | null>(null);
  const selectedLesson = lessons.find((lesson) => lesson.lesson_id === selectedLessonId) ?? lessons[0] ?? null;
  const selectedPattern = patterns.find((pattern) => pattern.pattern_id === selectedPatternId) ?? patterns[0] ?? null;

  return (
    <section className="system-section learning-dashboard">
      <h3>Learning Core</h3>
      <div className="learning-stat-grid">
        <Metric label="Failures" value={String(stats?.failures ?? 0)} />
        <Metric label="Resolved" value={String(stats?.resolved ?? 0)} />
        <Metric label="Repair" value={`${stats?.repair_success_rate ?? 0}%`} />
        <Metric label="Strategies" value={String(stats?.repair_strategies ?? 0)} />
      </div>
      <StatusStrip title="Lessons" counts={stats?.lessons_by_status ?? {}} />
      <StatusStrip title="Patterns" counts={stats?.patterns_by_status ?? {}} />
      <div className="learning-list">
        <strong>Lessons</strong>
        {lessons.slice(0, 3).map((lesson) => (
          <div className="learning-item" key={lesson.lesson_id}>
            <span>{lesson.title}</span>
            <small>{lesson.status} · {formatConfidence(lesson.confidence_score)} · {lesson.success_count}S/{lesson.contradiction_count}C</small>
            <div className="mini-actions">
              <button type="button" onClick={() => setSelectedLessonId(lesson.lesson_id)}>Inspect</button>
              <button type="button" onClick={() => onRevalidateLesson(lesson.lesson_id)}>Revalidate</button>
              <button type="button" onClick={() => onDeprecateLesson(lesson.lesson_id)}>Deprecate</button>
            </div>
          </div>
        ))}
        {selectedLesson ? (
          <div className="learning-detail">
            <strong>{selectedLesson.title}</strong>
            <dl>
              <DetailRow label="Status" value={selectedLesson.status} />
              <DetailRow label="Confidence" value={formatConfidence(selectedLesson.confidence_score)} />
              <DetailRow label="Evidence" value={`${selectedLesson.evidence_count} events, ${selectedLesson.contradiction_count} contradictions`} />
              <DetailRow label="Problem" value={selectedLesson.problem_signature} />
              <DetailRow label="Ops" value={selectedLesson.applicable_operation_types.join(", ") || "none"} />
              <DetailRow label="Source" value={selectedLesson.source_type} />
              <DetailRow label="Verified" value={selectedLesson.last_verified_at ?? "not yet"} />
            </dl>
            <p className="muted">{selectedLesson.description}</p>
          </div>
        ) : null}
      </div>
      <div className="learning-list">
        <strong>Patterns</strong>
        {patterns.slice(0, 3).map((pattern) => (
          <div className="learning-item" key={pattern.pattern_id}>
            <span>{pattern.name}</span>
            <small>{pattern.status} · {formatConfidence(pattern.confidence_score)} · {pattern.operation_signature ?? pattern.applicable_operation_types.join("+")}</small>
            <div className="mini-actions">
              <button type="button" onClick={() => setSelectedPatternId(pattern.pattern_id)}>Inspect</button>
              <button type="button" onClick={() => onRevalidatePattern(pattern.pattern_id)}>Revalidate</button>
              <button type="button" onClick={() => onDeprecatePattern(pattern.pattern_id)}>Deprecate</button>
            </div>
          </div>
        ))}
        {selectedPattern ? (
          <div className="learning-detail">
            <strong>{selectedPattern.name}</strong>
            <dl>
              <DetailRow label="Status" value={selectedPattern.status} />
              <DetailRow label="Confidence" value={formatConfidence(selectedPattern.confidence_score)} />
              <DetailRow label="Usage" value={`${selectedPattern.usage_count} uses, ${selectedPattern.success_count}S/${selectedPattern.failure_count}F`} />
              <DetailRow label="Signature" value={selectedPattern.operation_signature ?? "none"} />
              <DetailRow label="Ops" value={selectedPattern.applicable_operation_types.join(", ") || "none"} />
              <DetailRow label="Verified" value={selectedPattern.last_verified_at ?? "not yet"} />
            </dl>
            <p className="muted">{selectedPattern.description}</p>
          </div>
        ) : null}
      </div>
      <div className="learning-list">
        <strong>Repair Strategies</strong>
        {repairStrategies.slice(0, 3).map((strategy) => (
          <div className="learning-item" key={strategy.strategy_signature}>
            <span>{strategy.strategy}</span>
            <small>{strategy.status} · {formatConfidence(strategy.confidence_score)} · {strategy.successes}S/{strategy.failures}F · {strategy.problem_signature}</small>
          </div>
        ))}
      </div>
      <div className="learning-list">
        <strong>Failure Analytics</strong>
        {failures.slice(0, 3).map((failure) => (
          <div className="learning-item" key={`${failure.signature}-${failure.error_category}`}>
            <span>{failure.signature}</span>
            <small>{failure.error_category} · {failure.count}</small>
          </div>
        ))}
      </div>
      <div className="learning-list">
        <strong>Capability Metrics</strong>
        {capabilityAnalytics.slice(0, 3).map((capability) => (
          <div className="learning-item" key={capability.capability_id}>
            <span>{capability.name}</span>
            <small>{capability.success_rate}% · {capability.success_count}S/{capability.failure_count}F</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="feature-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusStrip({ title, counts }: { title: string; counts: Record<string, number> }) {
  const keys = ["TRUSTED", "VALIDATED", "OBSERVED", "DEPRECATED"];
  return (
    <div className="status-strip">
      <span>{title}</span>
      {keys.map((key) => (
        <small key={key}>{key}: {counts[key] ?? 0}</small>
      ))}
    </div>
  );
}

function formatConfidence(value: number): string {
  return value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

type CapabilityManagerProps = {
  capabilities: CapabilityRecord[];
  sources: DiscoverySource[];
  onDiscoverCapabilities: (sourceId?: string) => void;
  onTestCapability: (capabilityId: string) => void;
  onApproveCapability: (capabilityId: string) => void;
  onEnableCapability: (capabilityId: string) => void;
  onDisableCapability: (capabilityId: string) => void;
};

function CapabilityManager({
  capabilities,
  sources,
  onDiscoverCapabilities,
  onTestCapability,
  onApproveCapability,
  onEnableCapability,
  onDisableCapability
}: CapabilityManagerProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = capabilities.find((capability) => capability.capability_id === selectedId) ?? capabilities[0] ?? null;

  return (
    <section className="system-section capability-manager">
      <div className="section-heading-row">
        <h3>Capabilities</h3>
        <button type="button" className="tool-button compact" onClick={() => onDiscoverCapabilities("local_adapters")}>
          Discover
        </button>
      </div>
      <div className="source-list">
        {sources.map((source) => (
          <button
            type="button"
            className="source-chip"
            key={source.source_id}
            onClick={() => onDiscoverCapabilities(source.source_id)}
            title={source.notes ?? source.location}
          >
            {source.name}
          </button>
        ))}
      </div>
      <div className="capability-list">
        {capabilities.map((capability) => (
          <button
            type="button"
            className={selected?.capability_id === capability.capability_id ? "capability active" : "capability"}
            key={capability.capability_id}
            onClick={() => setSelectedId(capability.capability_id)}
          >
            <span>{capability.name}</span>
            <small>{capability.trust_level} · {capability.enabled ? "ENABLED" : "DISABLED"}</small>
          </button>
        ))}
      </div>
      {selected ? (
        <div className="capability-detail">
          <dl>
            <div className="feature-row">
              <dt>ID</dt>
              <dd>{selected.capability_id}</dd>
            </div>
            <div className="feature-row">
              <dt>Provider</dt>
              <dd>{selected.provider_type}</dd>
            </div>
            <div className="feature-row">
              <dt>Version</dt>
              <dd>{selected.version}</dd>
            </div>
            <div className="feature-row">
              <dt>Status</dt>
              <dd>{selected.validation_status}</dd>
            </div>
            <div className="feature-row">
              <dt>Ops</dt>
              <dd>{selected.supported_operations.join(", ") || "none"}</dd>
            </div>
            <div className="feature-row">
              <dt>Uses</dt>
              <dd>{selected.metrics.invocation_count} calls, {selected.metrics.failure_count} failures</dd>
            </div>
          </dl>
          <p className="muted">{selected.risk_notes ?? selected.description}</p>
          <div className="capability-actions">
            <button type="button" className="tool-button compact" onClick={() => onTestCapability(selected.capability_id)}>
              Test
            </button>
            <button type="button" className="tool-button compact" onClick={() => onApproveCapability(selected.capability_id)}>
              Approve
            </button>
            <button type="button" className="tool-button compact" onClick={() => onEnableCapability(selected.capability_id)}>
              Enable
            </button>
            <button type="button" className="tool-button compact" onClick={() => onDisableCapability(selected.capability_id)}>
              Disable
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

type SelectionInspectorProps = {
  selectedOperation: Record<string, unknown> | null;
  selectedPreview: PreviewObject | null;
  templateModel: Record<string, unknown> | null | undefined;
  onStructuredEdit: (instruction: string, edit: Record<string, unknown>) => void;
};

function SelectionInspector({ selectedOperation, selectedPreview, templateModel, onStructuredEdit }: SelectionInspectorProps) {
  const selectedModel = selectedOperation ?? (selectedPreview?.operation_id === "model" ? templateModel ?? null : null);
  const editableFields = useMemo(() => numericFields(selectedModel), [selectedModel]);
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    setValues(Object.fromEntries(editableFields.map(([key, value]) => [key, String(value)])));
  }, [editableFields]);

  if (!selectedPreview && !selectedOperation) {
    return (
      <section className="selection-inspector">
        <h3>Selection</h3>
        <div className="muted">Select an operation in the tree or viewer.</div>
      </section>
    );
  }

  function submit() {
    if (!selectedModel || editableFields.length === 0) {
      return;
    }
    const changes = Object.fromEntries(
      editableFields
        .map(([key]) => [key, Number(values[key])])
        .filter(([, value]) => Number.isFinite(value))
    );
    if (selectedOperation) {
      onStructuredEdit(`Inspector edit: update ${String(selectedOperation.id)}`, {
        edit_type: "modify_operation",
        operation_id: String(selectedOperation.id),
        changes
      });
      return;
    }
    const [firstKey, firstValue] = Object.entries(changes)[0] ?? [];
    if (firstKey) {
      onStructuredEdit(`Inspector edit: update ${firstKey}`, {
        edit_type: "set_parameter",
        path: firstKey,
        value: firstValue
      });
    }
  }

  return (
    <section className="selection-inspector">
      <h3>Selection</h3>
      <dl>
        <div className="feature-row">
          <dt>ID</dt>
          <dd>{selectedPreview?.operation_id ?? String(selectedOperation?.id ?? "model")}</dd>
        </div>
        <div className="feature-row">
          <dt>Type</dt>
          <dd>{selectedPreview?.object_type ?? String(selectedOperation?.operation_type ?? "model")}</dd>
        </div>
        <div className="feature-row">
          <dt>Mapping</dt>
          <dd>{selectedPreview?.notes ?? "Semantic operation preview"}</dd>
        </div>
      </dl>
      {editableFields.length > 0 ? (
        <div className="inline-edit-grid">
          {editableFields.map(([key]) => (
            <label key={key}>
              {key}
              <input value={values[key] ?? ""} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))} />
            </label>
          ))}
          <button type="button" className="tool-button" onClick={submit}>
            Apply Structured Edit
          </button>
        </div>
      ) : (
        <div className="muted">No shallow numeric parameters available for direct inspector edit.</div>
      )}
    </section>
  );
}

function numericFields(model: Record<string, unknown> | null): Array<[string, number]> {
  if (!model) {
    return [];
  }
  return Object.entries(model)
    .filter(([key, value]) => !["id"].includes(key) && typeof value === "number")
    .map(([key, value]) => [key, value as number]);
}
