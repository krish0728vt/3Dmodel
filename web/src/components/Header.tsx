import { Download, RefreshCw } from "lucide-react";

import { SystemInfo } from "./SystemInfo";
import { modeBadge, type WorkspaceMode } from "./uiState";

type HeaderProps = {
  backendOnline: boolean;
  selectedProjectId: string | null;
  title: string;
  revision: number | null;
  status: string | null;
  mode: WorkspaceMode;
  onRefresh: () => void;
  stepHref: string | null;
  stlHref: string | null;
};

export function Header({
  backendOnline,
  selectedProjectId,
  title,
  revision,
  status,
  mode,
  onRefresh,
  stepHref,
  stlHref
}: HeaderProps) {
  const badge = modeBadge(mode);
  return (
    <header className="workspace-header">
      <div className="brand-lockup">
        <img src="/shah-industries-logo.png" alt="SHAH INDUSTRIES" />
        <div className="brand-meta">
          <div className="brand-subtitle">AI-Assisted Parametric Engineering</div>
          <div className="header-context">
            {badge ? (
              <span className={`mode-badge mode-${mode}`} aria-label={`${badge} mode`}>
                {badge}
              </span>
            ) : null}
            <span>{title}</span>
            <small>
              {revision ? `REV ${revision}` : "No revision"}
              {status ? ` / ${status.toUpperCase()}` : ""}
            </small>
          </div>
        </div>
      </div>
      <div className="header-actions">
        <div
          className={backendOnline ? "status status-online" : "status status-offline"}
          role="status"
        >
          {backendOnline ? "BACKEND ONLINE" : "BACKEND OFFLINE"}
        </div>
        <button
          type="button"
          className="icon-button"
          onClick={onRefresh}
          title="Refresh workspace"
          aria-label="Refresh workspace"
        >
          <RefreshCw size={18} />
        </button>
        <SystemInfo backendOnline={backendOnline} />
        <a
          className={selectedProjectId ? "tool-button" : "tool-button disabled"}
          href={stepHref ?? undefined}
          aria-disabled={selectedProjectId ? undefined : true}
          title={selectedProjectId ? "Download STEP" : "Open a project to export"}
        >
          <Download size={16} />
          STEP
        </a>
        <a
          className={selectedProjectId ? "tool-button" : "tool-button disabled"}
          href={stlHref ?? undefined}
          aria-disabled={selectedProjectId ? undefined : true}
          title={selectedProjectId ? "Download STL" : "Open a project to export"}
        >
          <Download size={16} />
          STL
        </a>
      </div>
    </header>
  );
}
