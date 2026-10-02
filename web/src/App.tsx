import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import {
  FolderOpen,
  History,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  X
} from "lucide-react";

import { api, stepUrl, stlUrl } from "./api/client";
import { DesignRail } from "./components/DesignRail";
import { EmptyWorkspace } from "./components/EmptyWorkspace";
import { Header } from "./components/Header";
import { Inspector } from "./components/Inspector";
import { PromptBar } from "./components/PromptBar";
import { ProjectsDrawer } from "./components/ProjectsDrawer";
import { HistoryDrawer } from "./components/HistoryDrawer";
import { ExportDrawer } from "./components/ExportDrawer";
import { ToolsDrawer } from "./components/ToolsDrawer";
import {
  DEFAULT_DETAIL_LEVEL,
  resolveInspectorTab,
  toggleDrawer,
  type DetailLevel,
  type DrawerName,
  type InspectorTab
} from "./components/workspaceLayout";
import { inspectorTabs } from "./components/workspaceLayout";
import { inferCategory, presentError, type PresentedError } from "./components/errorPresentation";
import type { PromptState } from "./components/promptState";
import { isTextEntryTarget, viewShortcutFor, shortcutGroups, type ViewShortcut } from "./components/shortcuts";
import { loadingLabel, workspaceMode } from "./components/uiState";

// Three.js and the STL loader are the bulk of the bundle and are only
// needed once a project is open, so the viewer loads on demand.
const CadViewer = lazy(() =>
  import("./viewer/CadViewer").then((module) => ({ default: module.CadViewer }))
);
import type { AssemblyDetail, AssemblyEngineeringSummary, AssemblyPreview, AssemblyRecord, CapabilityAnalytics, CapabilityRecord, DiscoverySource, EngineeringReport, EvaluationReport, ExportBatchResult, ExportFormat, FailureAnalytics, LearningStats, LessonRecord, MaterialSpec, PatternRecord, PreviewObject, ProjectDetail, ProjectSummary, RepairStrategyRecord, ResolvedDesign, RevisionPreview, RevisionSummary, SelectionState } from "./types/api";

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
  const [promptState, setPromptState] = useState<PromptState>("ready");
  const [promptError, setPromptError] = useState<PresentedError | null>(null);
  const [clarification, setClarification] = useState<{ question: string; options: string[] } | null>(null);
  const [aiConfigured, setAiConfigured] = useState(true);
  const [viewCommand, setViewCommand] = useState<{ action: ViewShortcut; nonce: number } | null>(null);
  // Monotonic token for project/assembly loads. Switching targets quickly can
  // land a slower earlier response after a newer one; each async step checks it
  // is still the active request before writing state.
  const loadTokenRef = useRef(0);
  const [detailLevel, setDetailLevel] = useState<DetailLevel>(DEFAULT_DETAIL_LEVEL);
  const [openDrawer, setOpenDrawer] = useState<DrawerName | null>(null);
  const [toolsTab, setToolsTab] = useState<"evaluation" | "learning" | "capabilities" | "system">("evaluation");
  const [requestedTab, setRequestedTab] = useState<InspectorTab | null>(null);
  const [treeCollapsed, setTreeCollapsed] = useState(false);
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);
  const [renameDialog, setRenameDialog] = useState<{
    title: string;
    label: string;
    initial: string;
    onSubmit: (value: string) => void;
  } | null>(null);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialog | null>(null);

  const selectedProjectId = selectedProject?.project_id ?? null;
  const currentRevision = selectedProject?.current_revision_record?.revision_number ?? null;
  const previewUrl = selectedProjectId ? stlUrl(selectedProjectId, currentRevision ?? undefined) : null;
  const stepHref = selectedProjectId ? stepUrl(selectedProjectId, currentRevision ?? undefined) : null;
  const stlHref = selectedProjectId ? stlUrl(selectedProjectId, currentRevision ?? undefined) : null;

  const title = useMemo(() => selectedProject?.name ?? "New Workspace", [selectedProject]);
  const mode = workspaceMode(selectedProject !== null, selectedAssembly !== null);
  const tabs = inspectorTabs(mode, detailLevel);
  const activeTab = resolveInspectorTab(requestedTab, mode, detailLevel);
  const canUndo = (currentRevision ?? 0) > 1;
  const canRedo = revisions.some((item) => item.revision_number > (currentRevision ?? 0));

  useEffect(() => {
    refreshWorkspace();
  }, []);

  // Poll health so the workspace recovers on its own when the backend comes
  // back, instead of showing OFFLINE until the user reloads. Cheap by design:
  // /api/health does no geometry work. A full refresh runs only on the
  // transition back to online, so a healthy session is not re-fetching.
  useEffect(() => {
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        await api.health();
        if (cancelled) {
          return;
        }
        setBackendOnline((wasOnline) => {
          if (!wasOnline) {
            refreshWorkspace(selectedProjectId);
          }
          return true;
        });
      } catch {
        if (!cancelled) {
          setBackendOnline(false);
        }
      }
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [selectedProjectId]);

  // Report AI availability from the backend rather than guessing in the client.
  // The endpoint returns a boolean only; the key itself is never sent.
  useEffect(() => {
    let cancelled = false;
    api
      .version()
      .then((payload) => {
        if (!cancelled) {
          setAiConfigured(payload.ai_configured);
        }
      })
      .catch(() => {
        // Backend unreachable; the offline banner already covers this.
      });
    return () => {
      cancelled = true;
    };
  }, [backendOnline]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      refreshWorkspace(selectedProjectId);
    }, 180);
    return () => window.clearTimeout(timeoutId);
  }, [projectSearch, projectStatusFilter, projectSort]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping = isTextEntryTarget(target);
      if (event.key === "Escape") {
        setShowShortcuts(false);
        setOpenDrawer(null);
        setConfirmDialog(null);
        setRenameDialog(null);
        setPromptError(null);
        setClarification(null);
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
        return;
      }
      // Bare-key view shortcuts, suppressed while typing so a prompt
      // containing "1" or "f" is never hijacked.
      if (!isTyping && !event.ctrlKey && !event.metaKey && !event.altKey) {
        const action = viewShortcutFor(event.key);
        if (action) {
          event.preventDefault();
          setViewCommand({ action, nonce: Date.now() });
        }
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
    const token = ++loadTokenRef.current;
    const [detail, history, resolved] = await Promise.all([
      api.project(projectId),
      api.history(projectId),
      api.resolvedDesign(projectId).catch(() => null)
    ]);
    // A newer load started while these were in flight.
    if (token !== loadTokenRef.current) {
      return;
    }
    setSelectedProject(detail);
    setRevisions(history);
    setResolvedDesign(resolved);
    const revision = detail.current_revision_record?.revision_number ?? undefined;
    await Promise.all([
      loadEngineering(projectId, revision, materialId, process, displayUnits, token),
      revision ? loadPreview(projectId, revision, preferredSelectionId, token) : Promise.resolve()
    ]);
  }

  async function loadAssembly(assemblyId: string) {
    const token = ++loadTokenRef.current;
    try {
      const [detail, preview, engineering] = await Promise.all([
        api.assembly(assemblyId),
        api.assemblyPreview(assemblyId),
        api.assemblyEngineering(assemblyId)
      ]);
      if (token !== loadTokenRef.current) {
        return;
      }
      setSelectedAssembly(detail);
      setAssemblyPreview(preview);
      setAssemblyEngineering(engineering);
    } catch (error) {
      if (token !== loadTokenRef.current) {
        return;
      }
      setSelectedAssembly(null);
      setAssemblyPreview(null);
      setAssemblyEngineering(null);
      setLog((lines) => [`Assembly unavailable: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function loadPreview(
    projectId: string,
    revision: number,
    preferredSelectionId: string | null,
    token = loadTokenRef.current
  ) {
    try {
      const nextPreview = await api.preview(projectId, revision);
      if (token !== loadTokenRef.current) {
        return;
      }
      setPreviewModel(nextPreview);
      const remapped = preferredSelectionId ? nextPreview.objects.find((object) => object.operation_id === preferredSelectionId) : null;
      if (remapped) {
        setSelection(selectionFromPreviewObject(remapped, "viewer"));
      } else {
        setSelection(emptySelection());
      }
    } catch (error) {
      if (token !== loadTokenRef.current) {
        return;
      }
      setPreviewModel(null);
      setSelection(emptySelection());
      setLog((lines) => [`Preview metadata unavailable: ${messageFrom(error)}`, ...lines].slice(0, 6));
    }
  }

  async function loadEngineering(
    projectId: string,
    revision?: number,
    nextMaterial = materialId,
    nextProcess = process,
    nextUnits = displayUnits,
    token = loadTokenRef.current
  ) {
    const report = await api.engineering(projectId, {
      revision,
      material: nextMaterial || undefined,
      process: nextProcess,
      displayUnits: nextUnits
    });
    if (token !== loadTokenRef.current) {
      return;
    }
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

  /** In-app replacement for window.prompt, so renames match the rest of the
   *  dialog styling instead of using a browser chrome popup. */
  function askForName(title: string, label: string, initial: string): Promise<string | null> {
    return new Promise((resolve) => {
      setRenameDialog({
        title,
        label,
        initial,
        onSubmit: (value) => {
          setRenameDialog(null);
          resolve(value.trim() ? value.trim() : null);
        }
      });
    });
  }

  async function runPrompt() {
    if (!prompt.trim()) {
      return;
    }
    setBusy(true);
    setPromptError(null);
    setClarification(null);
    // The backend reports stages, not percentages, so the console walks named
    // states rather than inventing a progress bar.
    setPromptState("interpreting");
    try {
      setPromptState("validating");
      if (selectedProjectId) {
        setPromptState("generating");
        const response = await api.edit(selectedProjectId, prompt.trim());
        setLog((lines) => [`REV ${response.revision.revision_number}: ${response.change_summary}`, ...lines].slice(0, 6));
        await refreshWorkspace(selectedProjectId);
      } else {
        setPromptState("generating");
        const response = await api.generate(prompt.trim());
        const projectId = response.project?.project_id ?? null;
        setLog((lines) => [response.message, ...lines].slice(0, 6));
        await refreshWorkspace(projectId);
      }
      setPromptState("revision_created");
      setPrompt("");
    } catch (error) {
      const message = messageFrom(error);
      const parsed = parseClarification(message);
      if (parsed) {
        setClarification(parsed);
        setPromptState("needs_clarification");
      } else {
        setPromptError(presentError(inferCategory(message), message));
        setPromptState("failed");
      }
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
    const name = await askForName("Rename project", "Project name", project?.name ?? "");
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
    const name = await askForName("Rename assembly", "Assembly name", assembly?.name ?? "");
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

  async function restoreRevision(revisionNumber: number) {
    if (!selectedProjectId) {
      return;
    }
    try {
      const revision = await api.restoreRevision(selectedProjectId, revisionNumber);
      setLog((lines) => [`Restored REV ${revision.revision_number}`, ...lines].slice(0, 6));
      await refreshWorkspace(selectedProjectId);
    } catch (error) {
      setLog((lines) => [`Restore failed: ${messageFrom(error)}`, ...lines].slice(0, 6));
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
    <div className="app-shell">
      <Header
        backendOnline={backendOnline}
        hasProject={selectedProject !== null}
        title={title}
        revision={currentRevision}
        mode={mode}
        onOpenProjects={() => setOpenDrawer((current) => toggleDrawer(current, "projects"))}
        onOpenExport={() => setOpenDrawer((current) => toggleDrawer(current, "export"))}
        onOpenTools={() => setOpenDrawer((current) => toggleDrawer(current, "tools"))}
      />

      <main className={`workspace-main${treeCollapsed ? " tree-collapsed" : ""}${inspectorCollapsed ? " inspector-collapsed" : ""}`}>
        <DesignRail
          selectedProject={selectedProject}
          selectedOperationId={selection.selectedOperationId}
          previewObjects={previewModel?.objects ?? []}
          onSelectOperation={(operationId) => selectOperation(operationId, "design_tree")}
          onCollapse={() => setTreeCollapsed(true)}
          onOpenProjects={() => setOpenDrawer("projects")}
          onOpenHistory={() => setOpenDrawer("history")}
          hasProject={selectedProject !== null}
          detailLevel={detailLevel}
        />

        {treeCollapsed ? (
          <div className="rail-strip rail-strip-left">
            <button
              type="button"
              className="icon-only"
              onClick={() => setTreeCollapsed(false)}
              title="Show the design tree"
              aria-label="Show design tree"
            >
              <PanelLeftOpen size={16} />
            </button>
            <button
              type="button"
              className="icon-only"
              onClick={() => setOpenDrawer("projects")}
              title="Projects"
              aria-label="Projects"
            >
              <FolderOpen size={15} />
            </button>
            <button
              type="button"
              className="icon-only"
              onClick={() => setOpenDrawer("history")}
              disabled={selectedProject === null}
              title="Revision history"
              aria-label="Revision history"
            >
              <History size={15} />
            </button>
          </div>
        ) : null}

        <section className="stage">
          {selectedProject ? (
            <Suspense fallback={<div className="viewer-loading">{loadingLabel("model")}</div>}>
              <CadViewer
                stlUrl={previewUrl}
                preview={previewModel}
                selection={selection}
                displayUnits={displayUnits}
                onSelectOperation={selectOperation}
                viewCommand={viewCommand}
              />
            </Suspense>
          ) : (
            <EmptyWorkspace
              onExample={setPrompt}
              onNewPart={() => focusPrompt()}
              onNewAssembly={() => createAssemblyFromSelectedProject()}
              onOpenProjects={() => setOpenDrawer("projects")}
              hasProjects={projects.length > 0}
              aiConfigured={aiConfigured}
            />
          )}
        </section>

        {inspectorCollapsed ? (
          <div className="rail-strip rail-strip-right">
            <button
              type="button"
              className="icon-only"
              onClick={() => setInspectorCollapsed(false)}
              title="Show the inspector"
              aria-label="Show inspector"
            >
              <PanelRightOpen size={16} />
            </button>
          </div>
        ) : null}

        <div className="rail rail-right">
          <div className="rail-head">
            <span className="panel-label">Inspector</span>
            <button
              type="button"
              className="icon-only"
              onClick={() => setInspectorCollapsed(true)}
              title="Collapse the inspector"
              aria-label="Collapse inspector"
            >
              <PanelRightClose size={15} />
            </button>
          </div>
          <Inspector
            tabs={tabs}
            activeTab={activeTab}
            onTabChange={setRequestedTab}
            detailLevel={detailLevel}
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
        </div>
      </main>

      <PromptBar
        prompt={prompt}
        state={promptState}
        aiConfigured={aiConfigured}
        backendOnline={backendOnline}
        selectedProjectId={selectedProjectId}
        error={promptError}
        clarification={clarification}
        onPromptChange={setPrompt}
        onSubmit={runPrompt}
        onDismissError={() => {
          setPromptError(null);
          setPromptState("ready");
        }}
        onChooseClarification={(option) => {
          setPrompt(option);
          setClarification(null);
          setPromptState("ready");
          focusPrompt();
        }}
        onSetupHelp={() => {
          setToolsTab("system");
          setOpenDrawer("tools");
        }}
      />

      <div className="toast-stack" aria-live="polite">
        {log.slice(0, 2).map((line) => (
          <div key={line}>{line}</div>
        ))}
      </div>

      {openDrawer === "projects" ? (
        <ProjectsDrawer
          projects={projects}
          selectedProject={selectedProject}
          search={projectSearch}
          statusFilter={projectStatusFilter}
          sort={projectSort}
          onSearchChange={setProjectSearch}
          onStatusFilterChange={setProjectStatusFilter}
          onSortChange={setProjectSort}
          onSelectProject={(projectId) => loadProject(projectId)}
          onRenameProject={renameProject}
          onDuplicateProject={duplicateProject}
          onArchiveProject={toggleArchiveProject}
          onDeleteProject={confirmDeleteProject}
          onClose={() => setOpenDrawer(null)}
        />
      ) : null}

      {openDrawer === "history" && selectedProject ? (
        <HistoryDrawer
          revisions={revisions}
          currentRevision={currentRevision}
          canUndo={canUndo}
          canRedo={canRedo}
          onUndo={undo}
          onRedo={redo}
          onRestore={restoreRevision}
          onClose={() => setOpenDrawer(null)}
        />
      ) : null}

      {openDrawer === "export" && selectedProject ? (
        <ExportDrawer
          project={selectedProject}
          selectedAssembly={selectedAssembly}
          exportResult={exportResult}
          onExport={runExport}
          onClose={() => setOpenDrawer(null)}
        />
      ) : null}

      {openDrawer === "tools" ? (
        <ToolsDrawer
          detailLevel={detailLevel}
          onDetailLevelChange={setDetailLevel}
          tab={toolsTab}
          onTabChange={setToolsTab}
          backendOnline={backendOnline}
          evaluationReport={evaluationReport}
          learningStats={learningStats}
          lessons={lessons}
          patterns={patterns}
          repairStrategies={repairStrategies}
          failureAnalytics={failureAnalytics}
          capabilityAnalytics={capabilityAnalytics}
          capabilities={capabilities}
          capabilitySources={capabilitySources}
          onDiscoverCapabilities={(sourceId) => runCapabilityAction(() => api.discoverCapabilities(sourceId))}
          onTestCapability={(capabilityId) => runCapabilityAction(() => api.testCapability(capabilityId))}
          onApproveCapability={(capabilityId) => runCapabilityAction(() => api.approveCapability(capabilityId))}
          onEnableCapability={(capabilityId) => runCapabilityAction(() => api.enableCapability(capabilityId))}
          onDisableCapability={(capabilityId) => runCapabilityAction(() => api.disableCapability(capabilityId))}
          onRevalidateLesson={(lessonId) => runLearningAction(() => api.revalidateLesson(lessonId))}
          onDeprecateLesson={(lessonId) => runLearningAction(() => api.deprecateLesson(lessonId))}
          onRevalidatePattern={(patternId) => runLearningAction(() => api.revalidatePattern(patternId))}
          onDeprecatePattern={(patternId) => runLearningAction(() => api.deprecatePattern(patternId))}
          onClose={() => setOpenDrawer(null)}
        />
      ) : null}

      {showShortcuts ? (
        <div className="modal-scrim" onClick={() => setShowShortcuts(false)}>
          <div
            className="shortcut-modal"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Keyboard shortcuts"
          >
            <div className="section-heading-row">
              <h3>Keyboard shortcuts</h3>
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowShortcuts(false)}
                aria-label="Close shortcuts"
                autoFocus
              >
                <X size={14} />
              </button>
            </div>
            {shortcutGroups().map((group) => (
              <div key={group.group} className="shortcut-group">
                <h4>{group.group}</h4>
                <dl>
                  {group.items.map((shortcut) => (
                    <Detail key={shortcut.keys} label={shortcut.keys} value={shortcut.description} />
                  ))}
                </dl>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {renameDialog ? (
        <RenameDialog
          title={renameDialog.title}
          label={renameDialog.label}
          initial={renameDialog.initial}
          onCancel={() => setRenameDialog(null)}
          onSubmit={renameDialog.onSubmit}
        />
      ) : null}

      {confirmDialog ? (
        <div className="modal-scrim">
          <div className="confirm-modal" role="dialog" aria-modal="true" aria-label={confirmDialog.title}>
            <h3>{confirmDialog.title}</h3>
            <p>{confirmDialog.message}</p>
            <div className="modal-actions">
              <button type="button" className="tool-button" onClick={() => setConfirmDialog(null)} autoFocus>
                Cancel
              </button>
              <button type="button" className="tool-button danger" onClick={confirmDialog.onConfirm}>
                {confirmDialog.confirmLabel}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function focusPrompt() {
  document.querySelector<HTMLTextAreaElement>(".console-body textarea")?.focus();
}

/** Recognizes the backend's ambiguity response so it can be shown as a
 *  question with choices rather than as a generic error. */
function parseClarification(message: string): { question: string; options: string[] } | null {
  const lowered = message.toLowerCase();
  if (!lowered.includes("ambiguous") && !lowered.includes("which one")) {
    return null;
  }
  // Candidate identifiers are quoted or comma-listed by the parser.
  const quoted = [...message.matchAll(/'([A-Za-z0-9_]+)'/g)].map((match) => match[1]);
  const options = [...new Set(quoted)];
  if (options.length < 2) {
    return null;
  }
  return {
    question: message.replace(/\s+/g, " ").trim(),
    options
  };
}

function RenameDialog({
  title,
  label,
  initial,
  onCancel,
  onSubmit
}: {
  title: string;
  label: string;
  initial: string;
  onCancel: () => void;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState(initial);
  return (
    <div className="modal-scrim">
      <div className="confirm-modal" role="dialog" aria-modal="true" aria-label={title}>
        <h3>{title}</h3>
        <label className="dialog-field">
          <span>{label}</span>
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                onSubmit(value);
              }
            }}
            autoFocus
          />
        </label>
        <div className="modal-actions">
          <button type="button" className="tool-button" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="tool-button primary"
            onClick={() => onSubmit(value)}
            disabled={value.trim().length === 0}
          >
            Save
          </button>
        </div>
      </div>
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
