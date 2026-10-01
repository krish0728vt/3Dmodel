import { Download, RefreshCw } from "lucide-react";

import { SystemInfo } from "./SystemInfo";

type HeaderProps = {
  backendOnline: boolean;
  selectedProjectId: string | null;
  title: string;
  revision: number | null;
  status: string | null;
  onRefresh: () => void;
  stepHref: string | null;
  stlHref: string | null;
};

export function Header({ backendOnline, selectedProjectId, title, revision, status, onRefresh, stepHref, stlHref }: HeaderProps) {
  return (
    <header className="workspace-header">
      <div className="brand-lockup">
        <img src="/shah-industries-logo.png" alt="SHAH INDUSTRIES" />
        <div className="brand-meta">
          <div className="brand-subtitle">AI-Assisted Parametric Engineering</div>
          <div className="header-context">
            <span>{title}</span>
            <small>{revision ? `REV ${revision}` : "No revision"}{status ? ` / ${status.toUpperCase()}` : ""}</small>
          </div>
        </div>
      </div>
      <div className="header-actions">
        <div className={backendOnline ? "status status-online" : "status status-offline"}>
          {backendOnline ? "BACKEND ONLINE" : "BACKEND OFFLINE"}
        </div>
        <button type="button" className="icon-button" onClick={onRefresh} title="Refresh workspace">
          <RefreshCw size={18} />
        </button>
        <SystemInfo backendOnline={backendOnline} />
        <a className={selectedProjectId ? "tool-button" : "tool-button disabled"} href={stepHref ?? undefined}>
          <Download size={16} />
          STEP
        </a>
        <a className={selectedProjectId ? "tool-button" : "tool-button disabled"} href={stlHref ?? undefined}>
          <Download size={16} />
          STL
        </a>
      </div>
    </header>
  );
}
