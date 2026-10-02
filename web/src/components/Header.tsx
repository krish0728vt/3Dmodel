import { Download, FolderOpen, Wrench } from "lucide-react";

import { modeBadge, type WorkspaceMode } from "./uiState";

type HeaderProps = {
  backendOnline: boolean;
  hasProject: boolean;
  title: string;
  revision: number | null;
  mode: WorkspaceMode;
  onOpenProjects: () => void;
  onOpenExport: () => void;
  onOpenTools: () => void;
};

/**
 * Application header: identity, what is open, and three entry points.
 *
 * Deliberately sparse. History moved to the left rail footer, the detail-level
 * preference moved into Tools, and the refresh and info icons are gone -- none
 * were used constantly, and together they made the bar read as a control strip
 * rather than a title bar.
 */
export function Header({
  backendOnline,
  hasProject,
  title,
  revision,
  mode,
  onOpenProjects,
  onOpenExport,
  onOpenTools
}: HeaderProps) {
  const badge = modeBadge(mode);

  return (
    <header className="app-header">
      <div className="app-header-brand">
        <img src="/shah-industries-logo.png" alt="SHAH INDUSTRIES" />
      </div>

      <div className="app-header-context">
        <span className="app-header-title">{title}</span>
        {badge ? (
          <span className="app-header-meta">
            {badge}
            {revision ? ` · REV ${revision}` : ""}
          </span>
        ) : null}
      </div>

      <div className="app-header-actions">
        <button type="button" className="action" onClick={onOpenProjects}>
          <FolderOpen size={15} />
          Open
        </button>
        <button
          type="button"
          className="action"
          onClick={onOpenExport}
          disabled={!hasProject}
          title={hasProject ? "Export this design" : "Open a project first"}
        >
          <Download size={15} />
          Export
        </button>
        <button type="button" className="action" onClick={onOpenTools} title="Tools and settings">
          <Wrench size={15} />
          Tools
        </button>

        <span
          className={backendOnline ? "conn conn-online" : "conn conn-offline"}
          role="status"
          title={backendOnline ? "Backend reachable" : "Backend offline"}
        >
          <span className="conn-dot" aria-hidden="true" />
          {backendOnline ? "Online" : "Offline"}
        </span>
      </div>
    </header>
  );
}
