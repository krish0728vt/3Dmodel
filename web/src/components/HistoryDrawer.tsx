import { Redo2, Undo2 } from "lucide-react";

import type { RevisionSummary } from "../types/api";
import { Drawer } from "./Drawer";
import { emptyState } from "./uiState";

type HistoryDrawerProps = {
  revisions: RevisionSummary[];
  currentRevision: number | null;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onRestore: (revisionNumber: number) => void;
  onClose: () => void;
};

/**
 * Revision history, moved out of the permanent bottom strip.
 *
 * It previously held a full-width band of the workspace at all times. Undo and
 * redo stay reachable from the header and from Ctrl+Z / Ctrl+Shift+Z, so the
 * list itself only needs to appear when asked for.
 */
export function HistoryDrawer({
  revisions,
  currentRevision,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onRestore,
  onClose
}: HistoryDrawerProps) {
  const info = emptyState("revisions");

  return (
    <Drawer
      title="Revision History"
      side="bottom"
      onClose={onClose}
      actions={
        <>
          <button
            type="button"
            className="icon-button"
            onClick={onUndo}
            disabled={!canUndo}
            title="Undo (Ctrl+Z)"
            aria-label="Undo"
          >
            <Undo2 size={16} />
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={onRedo}
            disabled={!canRedo}
            title="Redo (Ctrl+Shift+Z)"
            aria-label="Redo"
          >
            <Redo2 size={16} />
          </button>
        </>
      }
    >
      {revisions.length === 0 ? (
        <div className="empty-inline">
          <strong>{info.message}</strong>
          <small>{info.action}</small>
        </div>
      ) : (
        <div className="revision-list">
          {revisions
            .slice()
            .reverse()
            .map((revision) => {
              const isCurrent = revision.revision_number === currentRevision;
              return (
                <div
                  className={isCurrent ? "revision-row active" : "revision-row"}
                  key={revision.revision_id}
                >
                  <strong>REV {revision.revision_number}</strong>
                  <span>{revision.change_summary}</span>
                  {isCurrent ? (
                    <small className="revision-current">CURRENT</small>
                  ) : (
                    <button
                      type="button"
                      className="tool-button compact"
                      onClick={() => onRestore(revision.revision_number)}
                      title={`Restore revision ${revision.revision_number}`}
                    >
                      Restore
                    </button>
                  )}
                </div>
              );
            })}
        </div>
      )}
    </Drawer>
  );
}
