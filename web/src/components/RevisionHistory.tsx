import { Redo2, Undo2 } from "lucide-react";

import type { RevisionSummary } from "../types/api";

type RevisionHistoryProps = {
  revisions: RevisionSummary[];
  currentRevision: number | null;
  onUndo: () => void;
  onRedo: () => void;
};

export function RevisionHistory({ revisions, currentRevision, onUndo, onRedo }: RevisionHistoryProps) {
  return (
    <section className="revision-panel">
      <div className="panel-title">Revision History</div>
      <div className="revision-actions">
        <button type="button" className="icon-button" onClick={onUndo} title="Undo">
          <Undo2 size={16} />
        </button>
        <button type="button" className="icon-button" onClick={onRedo} title="Redo">
          <Redo2 size={16} />
        </button>
      </div>
      <div className="revision-list">
        {revisions
          .slice()
          .reverse()
          .map((revision) => (
            <div
              className={revision.revision_number === currentRevision ? "revision-row active" : "revision-row"}
              key={revision.revision_id}
            >
              <strong>REV {revision.revision_number}</strong>
              <span>{revision.change_summary}</span>
            </div>
          ))}
      </div>
    </section>
  );
}
