import { Info, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { VersionResponse } from "../types/api";

/** Rows rendered by the About panel. Pure so it can be tested directly. */
export type SystemInfoRow = {
  label: string;
  value: string;
};

/**
 * Build the About rows from backend state.
 *
 * Deliberately derives everything from the version payload and the online flag
 * so no environment value is ever read on the client.
 */
export function systemInfoRows(
  version: VersionResponse | null,
  backendOnline: boolean,
  frontendBuild: string
): SystemInfoRow[] {
  const rows: SystemInfoRow[] = [
    { label: "Version", value: version?.app_version ?? "unknown" },
    { label: "Build", value: version?.build ?? "not available" },
    { label: "Backend", value: backendOnline ? "ONLINE" : "OFFLINE" },
    { label: "API", value: version ? `v${version.app_version}` : "unreachable" },
    { label: "CAD engine", value: version?.cad_engine ?? "unknown" },
    { label: "Schema", value: version?.schema_version ?? "unknown" },
    { label: "Python", value: version?.python_version ?? "unknown" },
    { label: "Frontend build", value: frontendBuild },
    {
      label: "AI parsing",
      value: aiStatusLabel(version)
    }
  ];
  return rows;
}

/** AI availability, phrased the same way the launcher reports it. */
export function aiStatusLabel(version: VersionResponse | null): string {
  if (version === null) {
    return "unknown";
  }
  return version.ai_configured ? "CONFIGURED" : "AI NOT CONFIGURED";
}

type SystemInfoProps = {
  backendOnline: boolean;
};

export function SystemInfo({ backendOnline }: SystemInfoProps) {
  const [open, setOpen] = useState(false);
  const [version, setVersion] = useState<VersionResponse | null>(null);

  useEffect(() => {
    if (!open || !backendOnline) {
      return;
    }
    let cancelled = false;
    api
      .version()
      .then((payload) => {
        if (!cancelled) {
          setVersion(payload);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setVersion(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, backendOnline]);

  const rows = systemInfoRows(version, backendOnline, import.meta.env.MODE ?? "unknown");

  return (
    <>
      <button
        type="button"
        className="icon-button"
        onClick={() => setOpen((value) => !value)}
        title="System information"
        aria-label="System information"
      >
        <Info size={18} />
      </button>
      {open ? (
        <div className="system-info-panel" role="dialog" aria-label="System information">
          <div className="system-info-header">
            <span>SYSTEM</span>
            <button
              type="button"
              className="icon-button"
              onClick={() => setOpen(false)}
              aria-label="Close system information"
            >
              <X size={14} />
            </button>
          </div>
          <dl className="system-info-rows">
            {rows.map((row) => (
              <div key={row.label} className="system-info-row">
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
          {version !== null && !version.ai_configured ? (
            <p className="system-info-note">
              Manual CAD, projects, assemblies, exports, and evaluation work without an API key.
            </p>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

/**
 * System information as a plain panel, for the Tools drawer.
 *
 * Shares `systemInfoRows` with the header popup so the two can never disagree,
 * and like the popup it reports only whether AI is configured, never a key.
 */
export function SystemPanel({ backendOnline }: { backendOnline: boolean }) {
  const [version, setVersion] = useState<VersionResponse | null>(null);

  useEffect(() => {
    if (!backendOnline) {
      return;
    }
    let cancelled = false;
    api
      .version()
      .then((payload) => {
        if (!cancelled) {
          setVersion(payload);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setVersion(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [backendOnline]);

  const rows = systemInfoRows(version, backendOnline, import.meta.env.MODE ?? "unknown");

  return (
    <section>
      <h3>System</h3>
      <dl className="system-info-rows">
        {rows.map((row) => (
          <div key={row.label} className="system-info-row">
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      {version !== null && !version.ai_configured ? (
        <p className="system-info-note">
          Manual CAD, projects, assemblies, exports, and evaluation work without an API key.
        </p>
      ) : null}
    </section>
  );
}
