import { Archive, Copy, Edit3, Trash2 } from "lucide-react";

import type { ProjectDetail, ProjectSummary } from "../types/api";
import { Drawer } from "./Drawer";
import { emptyState } from "./uiState";

type ProjectStatusFilter = "active" | "archived" | "all";
type ProjectSort = "recently_updated" | "recently_opened" | "name" | "created";

type ProjectsDrawerProps = {
  projects: ProjectSummary[];
  selectedProject: ProjectDetail | null;
  search: string;
  statusFilter: ProjectStatusFilter;
  sort: ProjectSort;
  onSearchChange: (value: string) => void;
  onStatusFilterChange: (value: ProjectStatusFilter) => void;
  onSortChange: (value: ProjectSort) => void;
  onSelectProject: (projectId: string) => void;
  onRenameProject: (projectId: string) => void;
  onDuplicateProject: (projectId: string) => void;
  onArchiveProject: (projectId: string) => void;
  onDeleteProject: (projectId: string) => void;
  onClose: () => void;
};

/**
 * The project browser, moved out of the CAD workspace.
 *
 * Project selection is an occasional action, so it no longer holds a permanent
 * left column while you are editing geometry.
 */
export function ProjectsDrawer({
  projects,
  selectedProject,
  search,
  statusFilter,
  sort,
  onSearchChange,
  onStatusFilterChange,
  onSortChange,
  onSelectProject,
  onRenameProject,
  onDuplicateProject,
  onArchiveProject,
  onDeleteProject,
  onClose
}: ProjectsDrawerProps) {
  const info = emptyState(search.trim() ? "search_results" : "projects");

  return (
    <Drawer title="Projects" side="left" onClose={onClose}>
      <div className="browser-controls">
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search projects"
          aria-label="Search projects"
          autoFocus
        />
        <div className="browser-control-row">
          <label className="visually-hidden" htmlFor="project-status">
            Status filter
          </label>
          <select
            id="project-status"
            value={statusFilter}
            onChange={(event) => onStatusFilterChange(event.target.value as ProjectStatusFilter)}
          >
            <option value="active">Active</option>
            <option value="archived">Archived</option>
            <option value="all">All</option>
          </select>
          <label className="visually-hidden" htmlFor="project-sort">
            Sort order
          </label>
          <select
            id="project-sort"
            value={sort}
            onChange={(event) => onSortChange(event.target.value as ProjectSort)}
          >
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
            <strong>{info.message}</strong>
            <small>{info.action}</small>
          </div>
        ) : null}
        {projects.map((project) => (
          <div
            key={project.project_id}
            className={
              selectedProject?.project_id === project.project_id
                ? "project-card active"
                : "project-card"
            }
          >
            <button
              type="button"
              className="project-card-main"
              onClick={() => {
                onSelectProject(project.project_id);
                onClose();
              }}
            >
              {project.thumbnail_url ? (
                <img src={project.thumbnail_url} alt="" />
              ) : (
                <span className="project-thumb-fallback" aria-hidden="true">
                  {project.name.slice(0, 2).toUpperCase()}
                </span>
              )}
              <span>
                <strong>{project.name}</strong>
                <small>
                  {project.model_type} · REV {project.current_revision} ·{" "}
                  {project.material ?? "no material"}
                </small>
              </span>
            </button>
            <div className="project-actions">
              <button
                type="button"
                title="Rename project"
                aria-label={`Rename ${project.name}`}
                onClick={() => onRenameProject(project.project_id)}
              >
                <Edit3 size={13} />
              </button>
              <button
                type="button"
                title="Duplicate project"
                aria-label={`Duplicate ${project.name}`}
                onClick={() => onDuplicateProject(project.project_id)}
              >
                <Copy size={13} />
              </button>
              <button
                type="button"
                title={project.status === "archived" ? "Unarchive project" : "Archive project"}
                aria-label={`${project.status === "archived" ? "Unarchive" : "Archive"} ${project.name}`}
                onClick={() => onArchiveProject(project.project_id)}
              >
                <Archive size={13} />
              </button>
              <button
                type="button"
                className="danger"
                title="Delete project"
                aria-label={`Delete ${project.name}`}
                onClick={() => onDeleteProject(project.project_id)}
              >
                <Trash2 size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </Drawer>
  );
}
