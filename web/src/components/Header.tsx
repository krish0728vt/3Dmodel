import { Download, FolderOpen, History, RefreshCw, Wrench } from "lucide-react";

import { SystemInfo } from "./SystemInfo";
import { modeBadge, type WorkspaceMode } from "./uiState";
import type { DetailLevel } from "./workspaceLayout";

type HeaderProps = {
  backendOnline: boolean;
  hasProject: boolean;
  title: string;
  revision: number | null;
  mode: WorkspaceMode;
  detailLevel: DetailLevel;
  onDetailLevelChange: (level: DetailLevel) => void;
  onOpenProjects: () => void;
  onOpenHistory: () => void;
  onOpenExport: () => void;
  onOpenTools: () => void;
  onRefresh: () => void;
};

/**
 * Application header.
 *
 * Identity, context and a small set of entry points. Technical controls that
 * used to sit here (permanent STEP and STL download buttons) moved into the
 * Export drawer.
 */
export function Header({
  backendOnline,
  hasProject,
  title,
  revision,
  mode,
  detailLevel,
  onDetailLevelChange,
  onOpenProjects,
  onOpenHistory,
  onOpenExport,
  onOpenTools,
  onRefresh
}: HeaderProps) {
  const badge = modeBadge(mode);

  return (
    <header className="workspace-header">
      <div className="brand-lockup">
        <img src="/shah-industries-logo.png" alt="SHAH INDUSTRIES" />
        <div className="header-context">
          {badge ? (
            <span className={`mode-badge mode-${mode}`} aria-label={`${badge} mode`}>
              {badge}
            </span>
          ) : null}
          <span className="header-title">{title}</span>
          {revision ? <small>REV {revision}</small> : null}
        </div>
      </div>

      <div className="header-actions">
        <div
          className={backendOnline ? "status status-online" : "status status-offline"}
          role="status"
          title={backendOnline ? "Backend reachable" : "Backend offline"}
        >
          {backendOnline ? "ONLINE" : "OFFLINE"}
        </div>

        <div className="detail-toggle" role="group" aria-label="Detail level">
          {(["simple", "advanced"] as DetailLevel[]).map((level) => (
            <button
              type="button"
              key={level}
              className={detailLevel === level ? "chip active" : "chip"}
              aria-pressed={detailLevel === level}
              onClick={() => onDetailLevelChange(level)}
              title={
                level === "simple"
                  ? "Show the essentials"
                  : "Show parameters, relationships and internal detail"
              }
            >
              {level === "simple" ? "Simple" : "Advanced"}
            </button>
          ))}
        </div>

        <button type="button" className="tool-button compact" onClick={onOpenProjects}>
          <FolderOpen size={15} />
          Open
        </button>
        <button
          type="button"
          className={hasProject ? "tool-button compact" : "tool-button compact disabled"}
          onClick={onOpenHistory}
          disabled={!hasProject}
          title={hasProject ? "Revision history" : "Open a project first"}
        >
          <History size={15} />
          History
        </button>
        <button
          type="button"
          className={hasProject ? "tool-button compact" : "tool-button compact disabled"}
          onClick={onOpenExport}
          disabled={!hasProject}
          title={hasProject ? "Export this design" : "Open a project first"}
        >
          <Download size={15} />
          Export
        </button>
        <button
          type="button"
          className="tool-button compact"
          onClick={onOpenTools}
          title="Evaluation, Learning Core, capabilities and system information"
        >
          <Wrench size={15} />
          Tools
        </button>

        <button
          type="button"
          className="icon-button"
          onClick={onRefresh}
          title="Refresh workspace"
          aria-label="Refresh workspace"
        >
          <RefreshCw size={16} />
        </button>
        <SystemInfo backendOnline={backendOnline} />
      </div>
    </header>
  );
}
