import { MoreHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { assemblyDownloadUrl, exportDownloadUrl } from "../api/client";
import { emptyState, interferenceInfo } from "./uiState";
import { nextExpandedComponent } from "./workspaceLayout";
import type { DetailLevel, InspectorTab, TabDefinition } from "./workspaceLayout";
import type { AssemblyComponent, AssemblyComponentPreview, AssemblyDetail, AssemblyEngineeringSummary, AssemblyPreview, AssemblyRecord, CapabilityAnalytics, CapabilityRecord, DiscoverySource, EvaluationReport, ExportBatchResult, ExportFormat, FailureAnalytics, LearningStats, LessonRecord, PatternRecord, PreviewObject, ProjectDetail, RepairStrategyRecord, ResolvedDesign, RevisionPreview, SelectionState } from "../types/api";
import type { EngineeringReport, MaterialSpec } from "../types/api";
import { EngineeringPanel } from "./EngineeringPanel";
import { operationDetails, operationDisplayName, operationKind, templateDetails } from "../utils/modelFormatting";

type InspectorProps = {
  /** Tabs that apply to the current mode and detail level. */
  tabs: TabDefinition[];
  activeTab: InspectorTab | null;
  onTabChange: (tab: InspectorTab) => void;
  detailLevel: DetailLevel;
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
  tabs,
  activeTab,
  onTabChange,
  detailLevel,
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

  if (!project) {
    return (
      <aside className="inspector-panel" aria-label="Inspector">
        <div className="empty-inline">
          <strong>Nothing selected</strong>
          <small>Open a project or describe a part to begin.</small>
        </div>
      </aside>
    );
  }

  return (
    <aside className="inspector-panel" aria-label="Inspector">
      <div className="inspector-tabs" role="tablist" aria-label="Inspector sections">
        {tabs.map((tab) => (
          <button
            type="button"
            key={tab.id}
            role="tab"
            id={`inspector-tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`inspector-pane-${tab.id}`}
            className={activeTab === tab.id ? "inspector-tab active" : "inspector-tab"}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        className="inspector-body"
        role="tabpanel"
        id={`inspector-pane-${activeTab ?? "none"}`}
        aria-labelledby={activeTab ? `inspector-tab-${activeTab}` : undefined}
      >
        {activeTab === "properties" ? (
          <div className="inspector-stack">
            <section>
              <h3>{project.name}</h3>
              <dl>
                <div className="feature-row">
                  <dt>Type</dt>
                  <dd>{project.model_type}</dd>
                </div>
                <div className="feature-row">
                  <dt>Revision</dt>
                  <dd>{project.current_revision}</dd>
                </div>
                {detailLevel === "advanced" ? (
                  <div className="feature-row">
                    <dt>ID</dt>
                    <dd className="mono">{project.project_id}</dd>
                  </div>
                ) : null}
              </dl>
            </section>
            <SelectionInspector
              selectedOperation={selectedOperation}
              selectedPreview={selectedPreview}
              templateModel={operations.length === 0 ? project.current_model : null}
              onStructuredEdit={onStructuredEdit}
            />
          </div>
        ) : null}

        {activeTab === "engineering" ? (
          <div className="inspector-stack">
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
          </div>
        ) : null}

        {activeTab === "assembly" || activeTab === "component" ? (
          <div className="inspector-stack">
            <AssemblyPanel
              project={project}
              assemblies={assemblies}
              selectedAssembly={selectedAssembly}
              preview={assemblyPreview}
              engineering={assemblyEngineering}
              detailLevel={detailLevel}
              onCreateFromProject={onCreateAssemblyFromProject}
              onSelectAssembly={onSelectAssembly}
              onAddProjectToAssembly={onAddProjectToAssembly}
              onEditAssembly={onEditAssembly}
              onRenameAssembly={onRenameAssembly}
              onDuplicateAssembly={onDuplicateAssembly}
              onArchiveAssembly={onArchiveAssembly}
              onDeleteAssembly={onDeleteAssembly}
            />
          </div>
        ) : null}

        {activeTab === "parameters" ? (
          <div className="inspector-stack">
            <DesignIntentPanel
              resolvedDesign={resolvedDesign}
              onUpdateDesignParameter={onUpdateDesignParameter}
            />
            <section>
              <h3>Features</h3>
              {operations.length > 0 ? (
                <div className="feature-list">
                  {operations.map((operation) => (
                    <button
                      type="button"
                      className={
                        selection.selectedOperationId === String(operation.id)
                          ? "feature-item active"
                          : "feature-item"
                      }
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
        ) : null}
      </div>
    </aside>
  );
}

export function EvaluationPanel({ report }: { report: EvaluationReport | null }) {
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
        <div className="empty-inline">
          <strong>{emptyState("evaluation").message}</strong>
          <small>{emptyState("evaluation").action}</small>
        </div>
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
  detailLevel: DetailLevel;
  onCreateFromProject: () => void;
  onSelectAssembly: (assemblyId: string) => void;
  onAddProjectToAssembly: (assemblyId: string) => void;
  onEditAssembly: (assemblyId: string, edit: Record<string, unknown>, instruction: string) => void;
  onRenameAssembly: (assemblyId: string) => void;
  onDuplicateAssembly: (assemblyId: string) => void;
  onArchiveAssembly: (assemblyId: string) => void;
  onDeleteAssembly: (assemblyId: string) => void;
};

export function AssemblyPanel({
  project,
  assemblies,
  selectedAssembly,
  preview,
  engineering,
  detailLevel,
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
  // One expanded component at a time; a fully expanded list was the single
  // biggest source of vertical clutter in the inspector.
  const [expandedComponentId, setExpandedComponentId] = useState<string | null>(null);


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
          <section className="section">
            <h4 className="section-label">Overview</h4>
            <dl className="stat-rows">
              <div className="stat-row">
                <dt>Revision</dt>
                <dd>{current.revision_number}</dd>
              </div>
              <div className="stat-row">
                <dt>Parts</dt>
                <dd>{current.components.length}</dd>
              </div>
              <div className="stat-row">
                <dt>Mass</dt>
                <dd>
                  {engineering?.known_mass_g
                    ? `${engineering.known_mass_g.toFixed(1)} g`
                    : "Unknown"}
                </dd>
              </div>
              <div className="stat-row">
                <dt>Issues</dt>
                <dd>{engineering?.interferences.length ?? 0}</dd>
              </div>
            </dl>
          </section>

          <section className="section">
            <div className="section-head">
              <h4 className="section-label">Components</h4>
              <AssemblyActionsMenu
                assemblyId={selectedAssembly.assembly.assembly_id}
                archived={selectedAssembly.assembly.status === "archived"}
                onRename={onRenameAssembly}
                onDuplicate={onDuplicateAssembly}
                onArchive={onArchiveAssembly}
                onDelete={onDeleteAssembly}
              />
            </div>
            <div className="component-rows">
              {current.components.map((component) => {
                const expanded = expandedComponentId === component.component_id;
                return (
                  <div className="component-entry" key={component.component_id}>
                    <button
                      type="button"
                      className={expanded ? "component-summary open" : "component-summary"}
                      aria-expanded={expanded}
                      onClick={() =>
                        setExpandedComponentId(
                          nextExpandedComponent(expandedComponentId, component.component_id)
                        )
                      }
                    >
                      <span className="component-name">{component.name}</span>
                      <span className="component-state">
                        {component.visible ? "Visible" : "Hidden"} ·{" "}
                        {component.grounded ? "Grounded" : "Free"}
                      </span>
                    </button>

                    {expanded ? (
                      <ComponentEditor
                        component={component}
                        componentPreview={preview?.components.find(
                          (item) => item.component_id === component.component_id
                        )}
                        detailLevel={detailLevel}
                        onApplyTransform={(transform, label) =>
                          onEditAssembly(
                            selectedAssemblyId,
                            {
                              edit_type: "set_transform",
                              component_id: component.component_id,
                              transform
                            },
                            label
                          )
                        }
                        onToggleVisibility={() =>
                          onEditAssembly(
                            selectedAssemblyId,
                            {
                              edit_type: "set_visibility",
                              component_id: component.component_id,
                              visible: !component.visible
                            },
                            `${component.visible ? "Hide" : "Show"} ${component.name}`
                          )
                        }
                        onToggleGrounded={() =>
                          onEditAssembly(
                            selectedAssemblyId,
                            {
                              edit_type: "set_grounded",
                              component_id: component.component_id,
                              grounded: !component.grounded
                            },
                            `${component.grounded ? "Release" : "Ground"} ${component.name}`
                          )
                        }
                      />
                    ) : null}
                  </div>
                );
              })}
            </div>
          </section>

          {engineering?.interferences.length ? (
            <div className="interference-list">
              {engineering.interferences.map((item) => {
                const info = interferenceInfo(item.status, item.method);
                return (
                  <div
                    className={`interference-row tone-${info.tone}`}
                    key={`${item.first_component_id}-${item.second_component_id}`}
                  >
                    <strong>{info.label}</strong>
                    <span>
                      {item.first_component_id} / {item.second_component_id}
                    </span>
                    <small>{info.explanation}</small>
                  </div>
                );
              })}
            </div>
          ) : engineering ? (
            <div className="interference-row tone-success">
              <strong>{interferenceInfo("NO_OVERLAP").label}</strong>
              <small>{interferenceInfo("NO_OVERLAP").explanation}</small>
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

export function ExportPanel({ project, selectedAssembly, exportResult, onExport }: ExportPanelProps) {
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

export function DesignIntentPanel({ resolvedDesign, onUpdateDesignParameter }: DesignIntentPanelProps) {
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

export function LearningDashboard({
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

export function CapabilityManager({
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

export function SelectionInspector({ selectedOperation, selectedPreview, templateModel, onStructuredEdit }: SelectionInspectorProps) {
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

type ComponentEditorProps = {
  component: AssemblyComponent;
  componentPreview: AssemblyComponentPreview | undefined;
  detailLevel: DetailLevel;
  onApplyTransform: (transform: Record<string, number>, label: string) => void;
  onToggleVisibility: () => void;
  onToggleGrounded: () => void;
};

/**
 * One assembly component.
 *
 * The previous card exposed source, XYZ, rotation, bounding box and eight tiny
 * nudge buttons at once. This shows the name, two toggles, and editable
 * position and rotation fields with an explicit Apply; bounding box and source
 * move behind the advanced detail level.
 */
function ComponentEditor({
  component,
  componentPreview,
  detailLevel,
  onApplyTransform,
  onToggleVisibility,
  onToggleGrounded
}: ComponentEditorProps) {
  const transform = component.transform;
  const [draft, setDraft] = useState({
    x: transform.translation_x_mm,
    y: transform.translation_y_mm,
    z: transform.translation_z_mm,
    rx: transform.rotation_x_deg,
    ry: transform.rotation_y_deg,
    rz: transform.rotation_z_deg
  });

  // Re-sync when the stored transform changes, so a revision switch or an undo
  // does not leave stale numbers in the fields.
  useEffect(() => {
    setDraft({
      x: transform.translation_x_mm,
      y: transform.translation_y_mm,
      z: transform.translation_z_mm,
      rx: transform.rotation_x_deg,
      ry: transform.rotation_y_deg,
      rz: transform.rotation_z_deg
    });
  }, [
    transform.translation_x_mm,
    transform.translation_y_mm,
    transform.translation_z_mm,
    transform.rotation_x_deg,
    transform.rotation_y_deg,
    transform.rotation_z_deg
  ]);

  const dirty =
    draft.x !== transform.translation_x_mm ||
    draft.y !== transform.translation_y_mm ||
    draft.z !== transform.translation_z_mm ||
    draft.rx !== transform.rotation_x_deg ||
    draft.ry !== transform.rotation_y_deg ||
    draft.rz !== transform.rotation_z_deg;

  function apply() {
    onApplyTransform(
      {
        translation_x_mm: draft.x,
        translation_y_mm: draft.y,
        translation_z_mm: draft.z,
        rotation_x_deg: draft.rx,
        rotation_y_deg: draft.ry,
        rotation_z_deg: draft.rz
      },
      `Set ${component.name} transform`
    );
  }

  function field(
    key: keyof typeof draft,
    label: string,
    unit: string
  ) {
    return (
      <label className="transform-field" key={key}>
        <span>{label}</span>
        <input
          type="number"
          step="0.5"
          value={draft[key]}
          aria-label={`${component.name} ${label} ${unit}`}
          onChange={(event) =>
            setDraft((current) => ({ ...current, [key]: Number(event.target.value) }))
          }
        />
      </label>
    );
  }

  return (
    <div className="assembly-component">
      <div className="component-head">
        <strong>{component.name}</strong>
        <div className="component-toggles">
          <button
            type="button"
            className={component.visible ? "toggle on" : "toggle"}
            aria-pressed={component.visible}
            onClick={onToggleVisibility}
            title={component.visible ? "Hide this component" : "Show this component"}
          >
            {component.visible ? "Visible" : "Hidden"}
          </button>
          <button
            type="button"
            className={component.grounded ? "toggle on" : "toggle"}
            aria-pressed={component.grounded}
            onClick={onToggleGrounded}
            title={component.grounded ? "Release this component" : "Ground this component"}
          >
            {component.grounded ? "Grounded" : "Free"}
          </button>
        </div>
      </div>

      <div className="transform-group">
        <div className="transform-label">Position (mm)</div>
        <div className="transform-row">
          {field("x", "X", "mm")}
          {field("y", "Y", "mm")}
          {field("z", "Z", "mm")}
        </div>
      </div>

      <div className="transform-group">
        <div className="transform-label">Rotation (deg)</div>
        <div className="transform-row">
          {field("rx", "X", "degrees")}
          {field("ry", "Y", "degrees")}
          {field("rz", "Z", "degrees")}
        </div>
      </div>

      <button
        type="button"
        className="primary-action"
        onClick={apply}
        disabled={!dirty}
        title={dirty ? "Apply this transform" : "No changes to apply"}
      >
        Apply changes
      </button>

      {detailLevel === "advanced" ? (
        <details className="component-advanced">
          <summary>Advanced</summary>
          <dl>
            <DetailRow label="Component ID" value={component.component_id} />
            <DetailRow label="Source" value={component.source_type} />
            <DetailRow
              label="Bounding box"
              value={
                componentPreview?.bounding_box
                  ? `${formatNumber(componentPreview.bounding_box.xlen)} x ${formatNumber(componentPreview.bounding_box.ylen)} x ${formatNumber(componentPreview.bounding_box.zlen)} mm`
                  : "unavailable"
              }
            />
          </dl>
        </details>
      ) : null}
    </div>
  );
}

type AssemblyActionsMenuProps = {
  assemblyId: string;
  archived: boolean;
  onRename: (assemblyId: string) => void;
  onDuplicate: (assemblyId: string) => void;
  onArchive: (assemblyId: string) => void;
  onDelete: (assemblyId: string) => void;
};

/**
 * Assembly actions behind one control.
 *
 * Rename, Duplicate, Manifest, Archive and Delete used to sit as five buttons
 * in the inspector, giving a destructive action the same visual weight as a
 * rename.
 */
function AssemblyActionsMenu({
  assemblyId,
  archived,
  onRename,
  onDuplicate,
  onArchive,
  onDelete
}: AssemblyActionsMenuProps) {
  const [open, setOpen] = useState(false);

  function run(action: (id: string) => void) {
    setOpen(false);
    action(assemblyId);
  }

  return (
    <div className="actions-menu">
      <button
        type="button"
        className="icon-only"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Assembly actions"
        title="Assembly actions"
        onClick={() => setOpen((value) => !value)}
      >
        <MoreHorizontal size={15} />
      </button>
      {open ? (
        <>
          <div className="menu-dismiss" onClick={() => setOpen(false)} />
          <div className="float-menu actions-menu-list" role="menu">
            <button type="button" className="menu-item" role="menuitem" onClick={() => run(onRename)}>
              Rename
            </button>
            <button type="button" className="menu-item" role="menuitem" onClick={() => run(onDuplicate)}>
              Duplicate
            </button>
            <a className="menu-item" role="menuitem" href={assemblyDownloadUrl(assemblyId)} onClick={() => setOpen(false)}>
              Manifest
            </a>
            <button type="button" className="menu-item" role="menuitem" onClick={() => run(onArchive)}>
              {archived ? "Unarchive" : "Archive"}
            </button>
            <button
              type="button"
              className="menu-item destructive"
              role="menuitem"
              onClick={() => run(onDelete)}
            >
              Delete
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
