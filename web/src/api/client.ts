import type {
  AssemblyComponent,
  AssemblyDetail,
  AssemblyEngineeringSummary,
  AssemblyPreview,
  AssemblyRecord,
  CapabilityRecord,
  CapabilityAnalytics,
  DiscoverySource,
  EngineeringReport,
  ExportBatchResult,
  ExportFormat,
  EvaluationReport,
  FailureAnalytics,
  GenerateResponse,
  HealthResponse,
  LessonRecord,
  LearningStats,
  MaterialSpec,
  PatternRecord,
  RepairStrategyRecord,
  RevisionPreview,
  ProjectDetail,
  ProjectSummary,
  ResolvedDesign,
  RevisionSummary,
  VersionResponse
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  version: () => request<VersionResponse>("/api/version"),
  evaluationLatest: () => request<{ available: boolean; message?: string; report: EvaluationReport | null }>("/api/evaluation/latest"),
  evaluationCases: () => request<unknown[]>("/api/evaluation/cases"),
  evaluationRegressions: () => request<unknown[]>("/api/evaluation/regressions"),
  projects: (options?: { search?: string; status?: "active" | "archived" | "all"; sort?: "recently_updated" | "recently_opened" | "name" | "created" }) => {
    const params = new URLSearchParams();
    if (options?.search) params.set("search", options.search);
    if (options?.status) params.set("status", options.status);
    if (options?.sort) params.set("sort", options.sort);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<ProjectSummary[]>(`/api/projects${suffix}`);
  },
  project: (projectId: string) => request<ProjectDetail>(`/api/projects/${projectId}`),
  renameProject: (projectId: string, name: string) =>
    request<ProjectSummary>(`/api/projects/${projectId}/rename`, {
      method: "POST",
      body: JSON.stringify({ name })
    }),
  duplicateProject: (projectId: string, revision?: number) =>
    request<ProjectDetail>(`/api/projects/${projectId}/duplicate`, {
      method: "POST",
      body: JSON.stringify({ revision: revision ?? null })
    }),
  archiveProject: (projectId: string) => request<ProjectSummary>(`/api/projects/${projectId}/archive`, { method: "POST" }),
  unarchiveProject: (projectId: string) => request<ProjectSummary>(`/api/projects/${projectId}/unarchive`, { method: "POST" }),
  deleteProject: (projectId: string) =>
    request<{ project_id: string; deleted: boolean; revision_count: number; file_count: number }>(`/api/projects/${projectId}`, {
      method: "DELETE",
      body: JSON.stringify({ confirmation: "DELETE" })
    }),
  history: (projectId: string) => request<RevisionSummary[]>(`/api/projects/${projectId}/history`),
  resolvedDesign: (projectId: string) => request<ResolvedDesign>(`/api/projects/${projectId}/resolved-design`),
  updateParameter: (projectId: string, parameterId: string, value: number) =>
    request<{ revision: RevisionSummary; change_summary: string }>(`/api/projects/${projectId}/parameters/${parameterId}`, {
      method: "POST",
      body: JSON.stringify({ value, instruction: `Set ${parameterId} to ${value}` })
    }),
  assemblies: (options?: { search?: string; status?: "active" | "archived" | "all"; sort?: "recently_updated" | "recently_opened" | "name" | "created" }) => {
    const params = new URLSearchParams();
    if (options?.search) params.set("search", options.search);
    if (options?.status) params.set("status", options.status);
    if (options?.sort) params.set("sort", options.sort);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<AssemblyRecord[]>(`/api/assemblies${suffix}`);
  },
  assembly: (assemblyId: string) => request<AssemblyDetail>(`/api/assemblies/${assemblyId}`),
  renameAssembly: (assemblyId: string, name: string) =>
    request<AssemblyRecord>(`/api/assemblies/${assemblyId}/rename`, {
      method: "POST",
      body: JSON.stringify({ name })
    }),
  duplicateAssembly: (assemblyId: string) =>
    request<AssemblyDetail>(`/api/assemblies/${assemblyId}/duplicate`, {
      method: "POST",
      body: JSON.stringify({})
    }),
  archiveAssembly: (assemblyId: string) => request<AssemblyRecord>(`/api/assemblies/${assemblyId}/archive`, { method: "POST" }),
  unarchiveAssembly: (assemblyId: string) => request<AssemblyRecord>(`/api/assemblies/${assemblyId}/unarchive`, { method: "POST" }),
  deleteAssembly: (assemblyId: string) =>
    request<{ assembly_id: string; deleted: boolean; revision_count: number; file_count: number }>(`/api/assemblies/${assemblyId}`, {
      method: "DELETE",
      body: JSON.stringify({ confirmation: "DELETE" })
    }),
  createAssembly: (name: string, components: AssemblyComponent[] = [], notes?: string) =>
    request<AssemblyDetail>("/api/assemblies", {
      method: "POST",
      body: JSON.stringify({ name, notes: notes ?? null, components })
    }),
  addAssemblyComponent: (assemblyId: string, component: AssemblyComponent) =>
    request<{ revision: unknown; change_summary: string }>(`/api/assemblies/${assemblyId}/components`, {
      method: "POST",
      body: JSON.stringify(component)
    }),
  editAssembly: (assemblyId: string, edit: Record<string, unknown>, instruction = "Structured assembly edit") =>
    request<{ revision: unknown; change_summary: string }>(`/api/assemblies/${assemblyId}/edit`, {
      method: "POST",
      body: JSON.stringify({ instruction, edit })
    }),
  assemblyPreview: async (assemblyId: string) => normalizeAssemblyPreviewUrls(await request<AssemblyPreview>(`/api/assemblies/${assemblyId}/preview`)),
  assemblyEngineering: (assemblyId: string) => request<AssemblyEngineeringSummary>(`/api/assemblies/${assemblyId}/engineering`),
  createExport: (payload: {
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
  }) =>
    request<ExportBatchResult>("/api/exports", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  learningStats: () => request<LearningStats>("/api/learning/stats"),
  learningLessons: () => request<LessonRecord[]>("/api/learning/lessons"),
  learningPatterns: () => request<PatternRecord[]>("/api/learning/patterns"),
  repairStrategies: () => request<RepairStrategyRecord[]>("/api/learning/repair-strategies"),
  failureAnalytics: () => request<FailureAnalytics[]>("/api/learning/failures/analytics"),
  capabilityAnalytics: () => request<CapabilityAnalytics[]>("/api/learning/capabilities/analytics"),
  revalidateLesson: (lessonId: string) => request<LessonRecord>(`/api/learning/lessons/${lessonId}/revalidate`, { method: "POST" }),
  deprecateLesson: (lessonId: string) => request<LessonRecord>(`/api/learning/lessons/${lessonId}/deprecate`, { method: "POST" }),
  revalidatePattern: (patternId: string) => request<PatternRecord>(`/api/learning/patterns/${patternId}/revalidate`, { method: "POST" }),
  deprecatePattern: (patternId: string) => request<PatternRecord>(`/api/learning/patterns/${patternId}/deprecate`, { method: "POST" }),
  capabilities: () => request<CapabilityRecord[]>("/api/capabilities"),
  capabilitySources: () => request<DiscoverySource[]>("/api/capabilities/sources"),
  discoverCapabilities: (sourceId?: string) =>
    request<CapabilityRecord[]>("/api/capabilities/discover", {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId ?? null })
    }),
  testCapability: (capabilityId: string) =>
    request<CapabilityRecord>(`/api/capabilities/${capabilityId}/test`, { method: "POST" }),
  approveCapability: (capabilityId: string) =>
    request<CapabilityRecord>(`/api/capabilities/${capabilityId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by: "local_user", approval_notes: "Approved from local web workspace." })
    }),
  enableCapability: (capabilityId: string) =>
    request<CapabilityRecord>(`/api/capabilities/${capabilityId}/enable`, { method: "POST" }),
  disableCapability: (capabilityId: string) =>
    request<CapabilityRecord>(`/api/capabilities/${capabilityId}/disable`, { method: "POST" }),
  materials: () => request<MaterialSpec[]>("/api/materials"),
  engineering: (projectId: string, options: { revision?: number; material?: string; process?: string; displayUnits?: string }) => {
    const params = new URLSearchParams();
    if (options.revision) params.set("revision", String(options.revision));
    if (options.material) params.set("material", options.material);
    if (options.process) params.set("process", options.process);
    if (options.displayUnits) params.set("display_units", options.displayUnits);
    return request<EngineeringReport>(`/api/projects/${projectId}/engineering?${params.toString()}`);
  },
  preview: async (projectId: string, revision: number) => normalizePreviewUrls(await request<RevisionPreview>(`/api/projects/${projectId}/revisions/${revision}/preview`)),
  setMaterial: (projectId: string, materialId: string | null) =>
    request<{ project_id: string; material_id: string | null }>(`/api/projects/${projectId}/material`, {
      method: "POST",
      body: JSON.stringify({ material_id: materialId })
    }),
  generate: (prompt: string) =>
    request<GenerateResponse>("/api/generate", {
      method: "POST",
      body: JSON.stringify({ prompt, save_project: true })
    }),
  edit: (projectId: string, instruction: string, edit?: Record<string, unknown>) =>
    request<{ revision: RevisionSummary; change_summary: string }>(`/api/projects/${projectId}/edit`, {
      method: "POST",
      body: JSON.stringify(edit ? { instruction, edit } : { instruction })
    }),
  undo: (projectId: string) =>
    request<RevisionSummary>(`/api/projects/${projectId}/undo`, {
      method: "POST"
    }),
  restoreRevision: (projectId: string, revisionNumber: number) =>
    request<RevisionSummary>(`/api/projects/${projectId}/restore/${revisionNumber}`, {
      method: "POST"
    }),
  redo: (projectId: string) =>
    request<RevisionSummary>(`/api/projects/${projectId}/redo`, {
      method: "POST"
    })
};

export function stlUrl(projectId: string, revision?: number): string {
  const suffix = revision ? `?revision=${revision}` : "";
  return `${API_BASE}/api/projects/${projectId}/download/stl${suffix}`;
}

export function stepUrl(projectId: string, revision?: number): string {
  const suffix = revision ? `?revision=${revision}` : "";
  return `${API_BASE}/api/projects/${projectId}/download/step${suffix}`;
}

export function assemblyDownloadUrl(assemblyId: string): string {
  return `${API_BASE}/api/assemblies/${assemblyId}/download`;
}

export function exportDownloadUrl(exportId: string): string {
  return `${API_BASE}/api/exports/${exportId}/download`;
}

function normalizePreviewUrls(preview: RevisionPreview): RevisionPreview {
  return {
    ...preview,
    final_mesh_url: assetUrl(preview.final_mesh_url),
    objects: preview.objects.map((object) => ({
      ...object,
      mesh_url: object.mesh_url ? assetUrl(object.mesh_url) : null
    }))
  };
}

function normalizeAssemblyPreviewUrls(preview: AssemblyPreview): AssemblyPreview {
  return {
    ...preview,
    components: preview.components.map((component) => ({
      ...component,
      mesh_url: component.mesh_url ? assetUrl(component.mesh_url) : null
    }))
  };
}

function assetUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE}${path}`;
}
