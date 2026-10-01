import { Archive, Copy, Edit3, Trash2 } from "lucide-react";
import { emptyState } from "./uiState";

import type { DesignParameter, ParametricRelationship, PreviewObject, ProjectDetail, ProjectSummary } from "../types/api";
import { operationDisplayName, operationKind, templateDetails } from "../utils/modelFormatting";

type DesignTreeProps = {
  projects: ProjectSummary[];
  selectedProject: ProjectDetail | null;
  selectedOperationId: string | null;
  previewObjects: PreviewObject[];
  onSelectProject: (projectId: string) => void;
  onSelectOperation: (operationId: string) => void;
  onRenameProject: (projectId: string) => void;
  onDuplicateProject: (projectId: string) => void;
  onArchiveProject: (projectId: string) => void;
  onDeleteProject: (projectId: string) => void;
  search: string;
  statusFilter: "active" | "archived" | "all";
  sort: "recently_updated" | "recently_opened" | "name" | "created";
  onSearchChange: (value: string) => void;
  onStatusFilterChange: (value: "active" | "archived" | "all") => void;
  onSortChange: (value: "recently_updated" | "recently_opened" | "name" | "created") => void;
};

export function DesignTree({
  projects,
  selectedProject,
  selectedOperationId,
  previewObjects,
  onSelectProject,
  onSelectOperation,
  onRenameProject,
  onDuplicateProject,
  onArchiveProject,
  onDeleteProject,
  search,
  statusFilter,
  sort,
  onSearchChange,
  onStatusFilterChange,
  onSortChange
}: DesignTreeProps) {
  const model = selectedProject?.current_model;
  const operations = Array.isArray(model?.operations) ? (model.operations as Record<string, unknown>[]) : [];
  const parameters = Array.isArray(model?.parameters) ? (model.parameters as DesignParameter[]) : [];
  const relationships = Array.isArray(model?.relationships) ? (model.relationships as ParametricRelationship[]) : [];
  const templateObject = operations.length === 0 ? previewObjects.find((object) => object.operation_id === "model") : null;

  // A filtered-out list and a genuinely empty workspace need different advice.
  const emptyStateInfo = emptyState(search.trim() ? "search_results" : "projects");

  return (
    <aside className="panel tree-panel">
      <div className="panel-title">Design Tree</div>
      <div className="browser-controls">
        <input value={search} onChange={(event) => onSearchChange(event.target.value)} placeholder="Search projects" />
        <div className="browser-control-row">
          <select value={statusFilter} onChange={(event) => onStatusFilterChange(event.target.value as "active" | "archived" | "all")}>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
            <option value="all">All</option>
          </select>
          <select value={sort} onChange={(event) => onSortChange(event.target.value as "recently_updated" | "recently_opened" | "name" | "created")}>
            <option value="recently_updated">Updated</option>
            <option value="recently_opened">Recent</option>
            <option value="name">Name</option>
            <option value="created">Created</option>
          </select>
        </div>
      </div>
      <div className="project-list">
        {projects.length === 0 ? (
          <div className="empty-inline">
            <strong>{emptyStateInfo.message}</strong>
            <small>{emptyStateInfo.action}</small>
          </div>
        ) : null}
        {projects.map((project) => (
          <div key={project.project_id} className={selectedProject?.project_id === project.project_id ? "project-card active" : "project-card"}>
            <button type="button" className="project-card-main" onClick={() => onSelectProject(project.project_id)}>
              <img src={project.thumbnail_url ?? ""} alt="" />
              <span>
                <strong>{project.name}</strong>
                <small>{project.model_type} / REV {project.current_revision} / {project.material ?? "no material"}</small>
              </span>
            </button>
            <div className="project-actions">
              <button type="button" title="Rename project" onClick={() => onRenameProject(project.project_id)}><Edit3 size={13} /></button>
              <button type="button" title="Duplicate project" onClick={() => onDuplicateProject(project.project_id)}><Copy size={13} /></button>
              <button type="button" title={project.status === "archived" ? "Unarchive project" : "Archive project"} onClick={() => onArchiveProject(project.project_id)}><Archive size={13} /></button>
              <button type="button" title="Delete project" onClick={() => onDeleteProject(project.project_id)}><Trash2 size={13} /></button>
            </div>
          </div>
        ))}
      </div>
      <div className="tree-section">
        {parameters.length > 0 ? (
          <>
            <div className="tree-group-label">Parameters</div>
            {parameters.map((parameter) => (
              <div className="tree-item" key={parameter.parameter_id}>
                <span>{parameter.name}</span>
                <small>{parameter.role.toUpperCase()} · {formatNumber(parameter.value)} {parameter.unit}</small>
              </div>
            ))}
          </>
        ) : null}
        {relationships.length > 0 ? (
          <>
            <div className="tree-group-label">Relationships</div>
            {relationships.slice(0, 8).map((relationship) => (
              <div className="tree-item" key={relationship.relationship_id}>
                <span>{relationship.relationship_id.replace(/_/g, " ")}</span>
                <small>{relationship.relationship_type.toUpperCase()}</small>
              </div>
            ))}
          </>
        ) : null}
        {operations.length > 0 ? <div className="tree-group-label">Features</div> : null}
        {model && operations.length === 0 && (
          <>
            <button
              type="button"
              className={selectedOperationId === "model" ? "tree-item primary active" : "tree-item primary"}
              onClick={() => onSelectOperation("model")}
            >
              <span>{templateObject?.label ?? String(model.part_type ?? "Template Part")}</span>
              <small>{templateObject?.object_type ?? "final_solid"}</small>
            </button>
            {templateDetails(model).map(([key, value]) => (
                <div className="tree-item" key={key}>
                  {key}: {value}
                </div>
              ))}
          </>
        )}
        {operations.map((operation) => (
          <button
            type="button"
            className={selectedOperationId === String(operation.id) ? "tree-item active" : "tree-item"}
            key={String(operation.id)}
            onClick={() => onSelectOperation(String(operation.id))}
          >
            <span>{operationDisplayName(operation)}</span>
            <small>{operationKind(operation)}</small>
          </button>
        ))}
      </div>
    </aside>
  );
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}
