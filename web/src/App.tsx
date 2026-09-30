import { useEffect, useMemo, useState } from "react";

import { api, stepUrl, stlUrl } from "./api/client";
import { DesignTree } from "./components/DesignTree";
import { EmptyWorkspace } from "./components/EmptyWorkspace";
import { Header } from "./components/Header";
import { Inspector } from "./components/Inspector";
import { PromptConsole } from "./components/PromptConsole";
import { RevisionHistory } from "./components/RevisionHistory";
import type { AssemblyDetail, AssemblyEngineeringSummary, AssemblyPreview, AssemblyRecord, CapabilityAnalytics, CapabilityRecord, DiscoverySource, EngineeringReport, EvaluationReport, ExportBatchResult, ExportFormat, FailureAnalytics, LearningStats, LessonRecord, MaterialSpec, PatternRecord, PreviewObject, ProjectDetail, ProjectSummary, RepairStrategyRecord, ResolvedDesign, RevisionPreview, RevisionSummary, SelectionState } from "./types/api";
import { CadViewer } from "./viewer/CadViewer";

type ProjectStatusFilter = "active" | "archived" | "all";
type ProjectSort = "recently_updated" | "recently_opened" | "name" | "created";
type ConfirmDialog = {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
};

export default function App() {
  const [backendOnline, setBackendOnline] = useState(false);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectSearch, setProjectSearch] = useState("");
  const [projectStatusFilter, setProjectStatusFilter] = useState<ProjectStatusFilter>("active");
  const [projectSort, setProjectSort] = useState<ProjectSort>("recently_updated");
  const [selectedProject, setSelectedProject] = useState<ProjectDetail | null>(null);
  const [revisions, setRevisions] = useState<RevisionSummary[]>([]);
  const [learningStats, setLearningStats] = useState<LearningStats | null>(null);
  const [lessons, setLessons] = useState<LessonRecord[]>([]);
  const [patterns, setPatterns] = useState<PatternRecord[]>([]);
  const [repairStrategies, setRepairStrategies] = useState<RepairStrategyRecord[]>([]);
  const [failureAnalytics, setFailureAnalytics] = useState<FailureAnalytics[]>([]);
  const [capabilityAnalytics, setCapabilityAnalytics] = useState<CapabilityAnalytics[]>([]);
  const [capabilities, setCapabilities] = useState<CapabilityRecord[]>([]);
  const [capabilitySources, setCapabilitySources] = useState<DiscoverySource[]>([]);
  const [materials, setMaterials] = useState<MaterialSpec[]>([]);
  const [engineeringReport, setEngineeringReport] = useState<EngineeringReport | null>(null);
  const [resolvedDesign, setResolvedDesign] = useState<ResolvedDesign | null>(null);
  const [assemblies, setAssemblies] = useState<AssemblyRecord[]>([]);
  const [selectedAssembly, setSelectedAssembly] = useState<AssemblyDetail | null>(null);
  const [assemblyPreview, setAssemblyPreview] = useState<AssemblyPreview | null>(null);
  const [assemblyEngineering, setAssemblyEngineering] = useState<AssemblyEngineeringSummary | null>(null);
  const [exportResult, setExportResult] = useState<ExportBatchResult | null>(null);
  const [evaluationReport, setEvaluationReport] = useState<EvaluationReport | null>(null);
  const [previewModel, setPreviewModel] = useState<RevisionPreview | null>(null);
  const [selection, setSelection] = useState<SelectionState>({
    selectedOperationId: null,
    selectedLabel: null,
    selectedObjectType: null,
    selectedMeshId: null,
    source: null
  });
  const [materialId, setMaterialId] = useState("");
  const [process, setProcess] = useState("unknown");
  const [displayUnits, setDisplayUnits] = useState<"mm" | "in">("mm");
  const [prompt, setPrompt] = useState("");
  const [log, setLog] = useState<string[]>(["Workspace ready."]);
  const [busy, setBusy] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialog | null>(null);

  const selectedProjectId = selectedProject?.project_id ?? null;
  const currentRevision = selectedProject?.current_revision_record?.revision_number ?? null;
  const previewUrl = selectedProjectId ? stlUrl(selectedProjectId, currentRevision ?? undefined) : null;
  const stepHref = selectedProjectId ? stepUrl(selectedProjectId, currentRevision ?? undefined) : null;
  const stlHref = selectedProjectId ? stlUrl(selectedProjectId, currentRevision ?? undefined) : null;

  const title = useMemo(() => selectedProject?.name ?? "New Workspace", [selectedProject]);

  useEffect(() => {
    refreshWorkspace();
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      refreshWorkspace(selectedProjectId);
    }, 180);
    return () => window.clearTimeout(timeoutId);
  }, [projectSearch, projectStatusFilter, projectSort]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.tagName === "SELECT";
      if (event.key === "Escape") {
        setShowShortcuts(false);
        setConfirmDialog(null);
        setSelection(emptySelection());
        return;
      }
      if (event.key === "?" && !isTyping) {
        event.preventDefault();
        setShowShortcuts((visible) => !visible);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.querySelector<HTMLTextAreaElement>(".console-body textarea")?.focus();
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !event.shiftKey && !isTyping) {
        event.preventDefault();
        undo();
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && event.shiftKey && !isTyping) {
        event.preventDefault();
        redo();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedProjectId]);

  async function refreshWorkspace(projectId = selectedProjectId, preferredSelectionId = selection.selectedOperationId) {
    try {
      await api.health();
      setBackendOnline(true);
      const [projectList, assemblyList, stats, lessonList, patternList, repairStrategyList, failureList, capabilityMetricList, capabilityList, sourceList, materialList, evaluation] = await Promise.all([
        api.projects({ search: projectSearch, status: projectStatusFilter, sort: projectSort }),
        api.assemblies(),
        api.learningStats(),
        api.learningLessons(),
        api.learningPatterns(),
        api.repairStrategies(),
        api.failureAnalytics(),
        api.capabilityAnalytics(),
        api.capabilities(),
        api.capabilitySources(),
        api.materials(),
        api.evaluationLatest().catch(() => ({ available: false, report: null }))
      ]);
      setProjects(projectList);
      setAssemblies(assemblyList);
      setLearningStats(stats);
      setLessons(lessonList);
      setPatterns(patternList);
      setRepairStrategies(repairStrategyList);
      setFailureAnalytics(failureList);
      setCapabilityAnalytics(capabilityMetricList);
      setCapabilities(capabilityList);
      setCapabilitySources(sourceList);
      setMaterials(materialList);
      setEvaluationReport(evaluation.report);
      const nextProjectId = projectList.some((project) => project.project_id === projectId) ? projectId : projectList[0]?.project_id ?? null;
      if (nextProjectId) {
        await loadProject(nextProjectId, preferredSelectionId);
      } else {
        setSelectedProject(null);
        setRevisions([]);
        setPreviewModel(null);
        setResolvedDesign(null);
        setEngineeringReport(null);
      }
      const nextAssemblyId = selectedAssembly?.assembly.assembly_id ?? assemblyList[0]?.assembly_id ?? null;
      if (nextAssemblyId) {
        await loadAssembly(nextAssemblyId);
      } else {
        setSelectedAssembly(null);
        setAssemblyPreview(null);
        setAssemblyEngineering(null);
      }
    } catch (error) {
      setBackendOnline(false);
      setLog((lines) => [`Backend unavailable: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function loadProject(projectId: string, preferredSelectionId = selection.selectedOperationId) {
    const [detail, history, resolved] = await Promise.all([
      api.project(projectId),
      api.history(projectId),
      api.resolvedDesign(projectId).catch(() => null)
    ]);
    setSelectedProject(detail);
    setRevisions(history);
    setResolvedDesign(resolved);
    const revision = detail.current_revision_record?.revision_number ?? undefined;
    await Promise.all([
      loadEngineering(projectId, revision),
      revision ? loadPreview(projectId, revision, preferredSelectionId) : Promise.resolve()
    ]);
  }

  async function loadAssembly(assemblyId: string) {
    try {
      const [detail, preview, engineering] = await Promise.all([
        api.assembly(assemblyId),
        api.assemblyPreview(assemblyId),
        api.assemblyEngineering(assemblyId)
      ]);
      setSelectedAssembly(detail);
      setAssemblyPreview(preview);
      setAssemblyEngineering(engineering);
    } catch (error) {
      setSelectedAssembly(null);
      setAssemblyPreview(null);
      setAssemblyEngineering(null);
      setLog((lines) => [`Assembly unavailable: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function loadPreview(projectId: string, revision: number, preferredSelectionId: string | null) {
    try {
      const nextPreview = await api.preview(projectId, revision);
      setPreviewModel(nextPreview);
      const remapped = preferredSelectionId ? nextPreview.objects.find((object) => object.operation_id === preferredSelectionId) : null;
      if (remapped) {
        setSelection(selectionFromPreviewObject(remapped, "viewer"));
      } else {
        setSelection(emptySelection());
      }
    } catch (error) {
      setPreviewModel(null);
      setSelection(emptySelection());
      setLog((lines) => [`Preview metadata unavailable: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function loadEngineering(projectId: string, revision?: number, nextMaterial = materialId, nextProcess = process, nextUnits = displayUnits) {
    const report = await api.engineering(projectId, {
      revision,
      material: nextMaterial || undefined,
      process: nextProcess,
      displayUnits: nextUnits
    });
    setEngineeringReport(report);
  }

  async function changeMaterial(nextMaterialId: string) {
    setMaterialId(nextMaterialId);
    if (selectedProjectId) {
      await api.setMaterial(selectedProjectId, nextMaterialId || null);
      await loadEngineering(selectedProjectId, currentRevision ?? undefined, nextMaterialId, process, displayUnits);
    }
  }

  async function changeProcess(nextProcess: string) {
    setProcess(nextProcess);
    if (selectedProjectId) {
      await loadEngineering(selectedProjectId, currentRevision ?? undefined, materialId, nextProcess, displayUnits);
    }
  }

  async function changeDisplayUnits(nextUnits: "mm" | "in") {
    setDisplayUnits(nextUnits);
    if (selectedProjectId) {
      await loadEngineering(selectedProjectId, currentRevision ?? undefined, materialId, process, nextUnits);
    }
  }

  async function runPrompt() {
    if (!prompt.trim()) {
      return;
    }
    setBusy(true);
    try {
      if (selectedProjectId) {
        const response = await api.edit(selectedProjectId, prompt.trim());
        setLog((lines) => [`REV ${response.revision.revision_number}: ${response.change_summary}`, ...lines].slice(0, 6));
        await refreshWorkspace(selectedProjectId);
      } else {
        const response = await api.generate(prompt.trim());
        const projectId = response.project?.project_id ?? null;
        setLog((lines) => [response.message, ...lines].slice(0, 6));
        await refreshWorkspace(projectId);
      }
      setPrompt("");
    } catch (error) {
      setLog((lines) => [`Request failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    } finally {
      setBusy(false);
    }
  }

  async function undo() {
    if (!selectedProjectId) {
      return;
    }
    try {
      const revision = await api.undo(selectedProjectId);
      setLog((lines) => [`Undo to REV ${revision.revision_number}`, ...lines].slice(0, 6));
      await refreshWorkspace(selectedProjectId);
    } catch (error) {
      setLog((lines) => [`Undo failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function renameProject(projectId: string) {
    const project = projects.find((item) => item.project_id === projectId) ?? selectedProject;
    const name = window.prompt("Rename project", project?.name ?? "");
    if (!name?.trim()) {
      return;
    }
    try {
      await api.renameProject(projectId, name.trim());
      setLog((lines) => [`Renamed project to ${name.trim()}.`, ...lines].slice(0, 6));
      await refreshWorkspace(projectId);
    } catch (error) {
      setLog((lines) => [`Rename failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function duplicateProject(projectId: string) {
    try {
      const detail = await api.duplicateProject(projectId);
      setLog((lines) => [`Duplicated project: ${detail.name}.`, ...lines].slice(0, 6));
      await refreshWorkspace(detail.project_id);
    } catch (error) {
      setLog((lines) => [`Duplicate failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function toggleArchiveProject(projectId: string) {
    const project = projects.find((item) => item.project_id === projectId) ?? selectedProject;
    try {
      if (project?.status === "archived") {
        await api.unarchiveProject(projectId);
        setLog((lines) => [`Unarchived ${project.name}.`, ...lines].slice(0, 6));
      } else {
        await api.archiveProject(projectId);
        setLog((lines) => [`Archived ${project?.name ?? projectId}.`, ...lines].slice(0, 6));
      }
      await refreshWorkspace(projectId);
    } catch (error) {
      setLog((lines) => [`Archive action failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  function confirmDeleteProject(projectId: string) {
    const project = projects.find((item) => item.project_id === projectId) ?? selectedProject;
    setConfirmDialog({
      title: "Delete Project",
      message: `Delete ${project?.name ?? projectId} and its generated local files? This cannot be undone.`,
      confirmLabel: "Delete",
      onConfirm: () => {
        deleteProject(projectId);
      }
    });
  }

  async function deleteProject(projectId: string) {
    setConfirmDialog(null);
    try {
      await api.deleteProject(projectId);
      setLog((lines) => [`Deleted project ${projectId}.`, ...lines].slice(0, 6));
      await refreshWorkspace(null);
    } catch (error) {
      setLog((lines) => [`Delete failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function renameAssembly(assemblyId: string) {
    const assembly = assemblies.find((item) => item.assembly_id === assemblyId) ?? selectedAssembly?.assembly;
    const name = window.prompt("Rename assembly", assembly?.name ?? "");
    if (!name?.trim()) {
      return;
    }
    try {
      await api.renameAssembly(assemblyId, name.trim());
      setLog((lines) => [`Renamed assembly to ${name.trim()}.`, ...lines].slice(0, 6));
      await refreshAssemblies(assemblyId);
    } catch (error) {
      setLog((lines) => [`Assembly rename failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function duplicateAssembly(assemblyId: string) {
    try {
      const detail = await api.duplicateAssembly(assemblyId);
      setLog((lines) => [`Duplicated assembly: ${detail.assembly.name}.`, ...lines].slice(0, 6));
      await refreshAssemblies(detail.assembly.assembly_id);
    } catch (error) {
      setLog((lines) => [`Assembly duplicate failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function toggleArchiveAssembly(assemblyId: string) {
    const assembly = assemblies.find((item) => item.assembly_id === assemblyId) ?? selectedAssembly?.assembly;
    try {
      if (assembly?.status === "archived") {
        await api.unarchiveAssembly(assemblyId);
        setLog((lines) => [`Unarchived ${assembly.name}.`, ...lines].slice(0, 6));
      } else {
        await api.archiveAssembly(assemblyId);
        setLog((lines) => [`Archived ${assembly?.name ?? assemblyId}.`, ...lines].slice(0, 6));
      }
      await refreshAssemblies(assemblyId);
    } catch (error) {
      setLog((lines) => [`Assembly archive action failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  function confirmDeleteAssembly(assemblyId: string) {
    const assembly = assemblies.find((item) => item.assembly_id === assemblyId) ?? selectedAssembly?.assembly;
    setConfirmDialog({
      title: "Delete Assembly",
      message: `Delete ${assembly?.name ?? assemblyId} and its generated local files? This cannot be undone.`,
      confirmLabel: "Delete",
      onConfirm: () => {
        deleteAssembly(assemblyId);
      }
    });
  }

  async function deleteAssembly(assemblyId: string) {
    setConfirmDialog(null);
    try {
      await api.deleteAssembly(assemblyId);
      setLog((lines) => [`Deleted assembly ${assemblyId}.`, ...lines].slice(0, 6));
      await refreshAssemblies(null);
    } catch (error) {
      setLog((lines) => [`Assembly delete failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function redo() {
    if (!selectedProjectId) {
      return;
    }
    try {
      const revision = await api.redo(selectedProjectId);
      setLog((lines) => [`Redo to REV ${revision.revision_number}`, ...lines].slice(0, 6));
      await refreshWorkspace(selectedProjectId);
    } catch (error) {
      setLog((lines) => [`Redo failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  function selectOperation(operationId: string, source: SelectionState["source"]) {
    const previewObject = previewModel?.objects.find((object) => object.operation_id === operationId);
    if (previewObject) {
      setSelection(selectionFromPreviewObject(previewObject, source));
      return;
    }
    setSelection({
      selectedOperationId: operationId,
      selectedLabel: operationId,
      selectedObjectType: null,
      selectedMeshId: null,
      source
    });
  }

  async function submitStructuredEdit(instruction: string, edit: Record<string, unknown>) {
    if (!selectedProjectId) {
      return;
    }
    setBusy(true);
    const keepSelection = selection.selectedOperationId;
    try {
      const response = await api.edit(selectedProjectId, instruction, edit);
      setLog((lines) => [`REV ${response.revision.revision_number}: ${response.change_summary}`, ...lines].slice(0, 6));
      await refreshWorkspace(selectedProjectId, keepSelection);
    } catch (error) {
      setLog((lines) => [`Edit failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    } finally {
      setBusy(false);
    }
  }

  async function updateDesignParameter(parameterId: string, value: number) {
    if (!selectedProjectId) {
      return;
    }
    setBusy(true);
    try {
      const response = await api.updateParameter(selectedProjectId, parameterId, value);
      setLog((lines) => [`REV ${response.revision.revision_number}: ${response.change_summary}`, ...lines].slice(0, 6));
      await refreshWorkspace(selectedProjectId, selection.selectedOperationId);
    } catch (error) {
      setLog((lines) => [`Parameter edit failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    } finally {
      setBusy(false);
    }
  }

  async function createAssemblyFromSelectedProject() {
    if (!selectedProject || !currentRevision) {
      return;
    }
    setBusy(true);
    try {
      const detail = await api.createAssembly(`${selectedProject.name} Assembly`, [
        {
          component_id: componentIdFromProject(selectedProject.project_id),
          name: selectedProject.name,
          source_type: "project_revision",
          project_id: selectedProject.project_id,
          project_revision: currentRevision,
          capability_output: null,
          external_step_path: null,
          external_stl_path: null,
          transform: zeroTransform(),
          visible: true,
          grounded: true,
          metadata: {}
        }
      ]);
      setLog((lines) => [`Assembly created: ${detail.assembly.name}`, ...lines].slice(0, 6));
      await refreshWorkspace(selectedProject.project_id);
      await loadAssembly(detail.assembly.assembly_id);
    } catch (error) {
      setLog((lines) => [`Assembly create failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    } finally {
      setBusy(false);
    }
  }

  async function addSelectedProjectToAssembly(assemblyId: string) {
    if (!selectedProject || !currentRevision) {
      return;
    }
    setBusy(true);
    try {
      const existingCount = selectedAssembly?.current_revision?.components.length ?? 0;
      await api.addAssemblyComponent(assemblyId, {
        component_id: `${componentIdFromProject(selectedProject.project_id)}_${existingCount + 1}`,
        name: selectedProject.name,
        source_type: "project_revision",
        project_id: selectedProject.project_id,
        project_revision: currentRevision,
        capability_output: null,
        external_step_path: null,
        external_stl_path: null,
        transform: {
          ...zeroTransform(),
          translation_x_mm: existingCount * 15
        },
        visible: true,
        grounded: false,
        metadata: {}
      });
      setLog((lines) => [`Added ${selectedProject.name} to assembly.`, ...lines].slice(0, 6));
      await refreshAssemblies(assemblyId);
    } catch (error) {
      setLog((lines) => [`Assembly component add failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    } finally {
      setBusy(false);
    }
  }

  async function editAssembly(assemblyId: string, edit: Record<string, unknown>, instruction: string) {
    setBusy(true);
    try {
      const response = await api.editAssembly(assemblyId, edit, instruction);
      setLog((lines) => [`Assembly: ${response.change_summary}`, ...lines].slice(0, 6));
      await refreshAssemblies(assemblyId);
    } catch (error) {
      setLog((lines) => [`Assembly edit failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    } finally {
      setBusy(false);
    }
  }

  async function refreshAssemblies(assemblyId?: string | null) {
    const list = await api.assemblies();
    setAssemblies(list);
    const nextId = assemblyId ?? selectedAssembly?.assembly.assembly_id ?? list[0]?.assembly_id ?? null;
    if (nextId) {
      await loadAssembly(nextId);
    }
  }

  async function runExport(payload: {
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
  }) {
    setBusy(true);
    try {
      const result = await api.createExport(payload);
      setExportResult(result);
      setLog((lines) => [`Exported ${result.results.length} files for REV ${result.revision}.`, ...lines].slice(0, 6));
    } catch (error) {
      setLog((lines) => [`Export failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    } finally {
      setBusy(false);
    }
  }

  async function runCapabilityAction(action: () => Promise<CapabilityRecord | CapabilityRecord[]>) {
    try {
      const result = await action();
      const count = Array.isArray(result) ? result.length : 1;
      setLog((lines) => [`Capability action completed (${count}).`, ...lines].slice(0, 6));
      const [capabilityList, sourceList] = await Promise.all([api.capabilities(), api.capabilitySources()]);
      setCapabilities(capabilityList);
      setCapabilitySources(sourceList);
    } catch (error) {
      setLog((lines) => [`Capability action failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function refreshLearning() {
    const [stats, lessonList, patternList, repairStrategyList, failureList, capabilityMetricList] = await Promise.all([
      api.learningStats(),
      api.learningLessons(),
      api.learningPatterns(),
      api.repairStrategies(),
      api.failureAnalytics(),
      api.capabilityAnalytics()
    ]);
    setLearningStats(stats);
    setLessons(lessonList);
    setPatterns(patternList);
    setRepairStrategies(repairStrategyList);
    setFailureAnalytics(failureList);
    setCapabilityAnalytics(capabilityMetricList);
  }

  async function runLearningAction(action: () => Promise<LessonRecord | PatternRecord>) {
    try {
      await action();
      await refreshLearning();
      setLog((lines) => ["Learning evidence updated.", ...lines].slice(0, 6));
    } catch (error) {
      setLog((lines) => [`Learning action failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  return (
    <div className="workspace">
      <Header
        backendOnline={backendOnline}
        selectedProjectId={selectedProjectId}
        title={title}
        revision={currentRevision}
        status={selectedProject?.status ?? null}
        onRefresh={() => refreshWorkspace()}
        stepHref={stepHref}
        stlHref={stlHref}
      />
      <div className="toast-stack" aria-live="polite">
        {log.slice(0, 2).map((line) => (
          <div key={line}>{line}</div>
        ))}
      </div>
      <main className="workspace-grid">
        <DesignTree
          projects={projects}
          selectedProject={selectedProject}
          selectedOperationId={selection.selectedOperationId}
          previewObjects={previewModel?.objects ?? []}
          onSelectProject={(projectId) => loadProject(projectId)}
          onSelectOperation={(operationId) => selectOperation(operationId, "design_tree")}
          onRenameProject={renameProject}
          onDuplicateProject={duplicateProject}
          onArchiveProject={toggleArchiveProject}
          onDeleteProject={confirmDeleteProject}
          search={projectSearch}
          statusFilter={projectStatusFilter}
          sort={projectSort}
          onSearchChange={setProjectSearch}
          onStatusFilterChange={setProjectStatusFilter}
          onSortChange={setProjectSort}
        />
        <section className="center-stage">
          <div className="stage-title">
            <span>{title}</span>
            <small>{currentRevision ? `REV ${currentRevision}` : "No active revision"}</small>
          </div>
          {selectedProject ? (
            <CadViewer
              stlUrl={previewUrl}
              preview={previewModel}
              selection={selection}
              displayUnits={displayUnits}
              onSelectOperation={selectOperation}
            />
          ) : (
            <EmptyWorkspace
              onExample={setPrompt}
              onNewPart={() => document.querySelector<HTMLTextAreaElement>(".console-body textarea")?.focus()}
              onOpenProjects={() => setProjectStatusFilter("all")}
            />
          )}
        </section>
        <Inspector
          project={selectedProject}
          preview={previewModel}
          selection={selection}
          assemblies={assemblies}
          selectedAssembly={selectedAssembly}
          assemblyPreview={assemblyPreview}
          assemblyEngineering={assemblyEngineering}
          exportResult={exportResult}
          evaluationReport={evaluationReport}
          learningStats={learningStats}
          resolvedDesign={resolvedDesign}
          lessons={lessons}
          patterns={patterns}
          repairStrategies={repairStrategies}
          failureAnalytics={failureAnalytics}
          capabilityAnalytics={capabilityAnalytics}
          capabilities={capabilities}
          capabilitySources={capabilitySources}
          engineeringReport={engineeringReport}
          materials={materials}
          materialId={materialId}
          process={process}
          displayUnits={displayUnits}
          onMaterialChange={changeMaterial}
          onProcessChange={changeProcess}
          onDisplayUnitsChange={changeDisplayUnits}
          onSelectOperation={(operationId) => selectOperation(operationId, "inspector")}
          onStructuredEdit={submitStructuredEdit}
          onUpdateDesignParameter={updateDesignParameter}
          onCreateAssemblyFromProject={createAssemblyFromSelectedProject}
          onSelectAssembly={loadAssembly}
          onAddProjectToAssembly={addSelectedProjectToAssembly}
          onEditAssembly={editAssembly}
          onRenameAssembly={renameAssembly}
          onDuplicateAssembly={duplicateAssembly}
          onArchiveAssembly={toggleArchiveAssembly}
          onDeleteAssembly={confirmDeleteAssembly}
          onExport={runExport}
          onDiscoverCapabilities={(sourceId) => runCapabilityAction(() => api.discoverCapabilities(sourceId))}
          onTestCapability={(capabilityId) => runCapabilityAction(() => api.testCapability(capabilityId))}
          onApproveCapability={(capabilityId) => runCapabilityAction(() => api.approveCapability(capabilityId))}
          onEnableCapability={(capabilityId) => runCapabilityAction(() => api.enableCapability(capabilityId))}
          onDisableCapability={(capabilityId) => runCapabilityAction(() => api.disableCapability(capabilityId))}
          onRevalidateLesson={(lessonId) => runLearningAction(() => api.revalidateLesson(lessonId))}
          onDeprecateLesson={(lessonId) => runLearningAction(() => api.deprecateLesson(lessonId))}
          onRevalidatePattern={(patternId) => runLearningAction(() => api.revalidatePattern(patternId))}
          onDeprecatePattern={(patternId) => runLearningAction(() => api.deprecatePattern(patternId))}
        />
        <RevisionHistory
          revisions={revisions}
          currentRevision={currentRevision}
          onUndo={undo}
          onRedo={redo}
        />
        <PromptConsole
          prompt={prompt}
          disabled={busy || !backendOnline}
          selectedProjectId={selectedProjectId}
          log={log}
          onPromptChange={setPrompt}
          onSubmit={runPrompt}
          onExample={setPrompt}
        />
      </main>
      {showShortcuts ? (
        <div className="modal-scrim" onClick={() => setShowShortcuts(false)}>
          <div className="shortcut-modal" onClick={(event) => event.stopPropagation()}>
            <div className="section-heading-row">
              <h3>Shortcuts</h3>
              <button type="button" className="icon-button" onClick={() => setShowShortcuts(false)}>x</button>
            </div>
            <dl>
              <Detail label="Ctrl+K" value="Focus design prompt" />
              <Detail label="Ctrl+Z" value="Undo revision" />
              <Detail label="Ctrl+Shift+Z" value="Redo revision" />
              <Detail label="Esc" value="Clear selection or close overlays" />
              <Detail label="?" value="Show shortcuts" />
            </dl>
          </div>
        </div>
      ) : null}
      {confirmDialog ? (
        <div className="modal-scrim">
          <div className="confirm-modal">
            <h3>{confirmDialog.title}</h3>
            <p>{confirmDialog.message}</p>
            <div className="modal-actions">
              <button type="button" className="tool-button" onClick={() => setConfirmDialog(null)}>Cancel</button>
              <button type="button" className="tool-button danger" onClick={confirmDialog.onConfirm}>{confirmDialog.confirmLabel}</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function emptySelection(): SelectionState {
  return {
    selectedOperationId: null,
    selectedLabel: null,
    selectedObjectType: null,
    selectedMeshId: null,
    source: null
  };
}

function selectionFromPreviewObject(object: PreviewObject, source: SelectionState["source"]): SelectionState {
  return {
    selectedOperationId: object.operation_id,
    selectedLabel: object.label,
    selectedObjectType: object.object_type,
    selectedMeshId: object.mesh_url,
    source
  };
}

function zeroTransform() {
  return {
    translation_x_mm: 0,
    translation_y_mm: 0,
    translation_z_mm: 0,
    rotation_x_deg: 0,
    rotation_y_deg: 0,
    rotation_z_deg: 0
  };
}

function componentIdFromProject(projectId: string): string {
  return `component_${projectId.replace(/[^a-zA-Z0-9_]/g, "_")}`;
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="feature-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
