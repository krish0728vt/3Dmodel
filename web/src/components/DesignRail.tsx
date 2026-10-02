import { Box, Circle, FolderOpen, History, PanelLeftClose, Ruler, Scissors, Square } from "lucide-react";

import type { DesignParameter, ParametricRelationship, PreviewObject, ProjectDetail } from "../types/api";
import { operationDisplayName, operationKind } from "../utils/modelFormatting";
import type { DetailLevel } from "./workspaceLayout";

type DesignRailProps = {
  selectedProject: ProjectDetail | null;
  selectedOperationId: string | null;
  previewObjects: PreviewObject[];
  onSelectOperation: (operationId: string) => void;
  onCollapse: () => void;
  onOpenProjects: () => void;
  onOpenHistory: () => void;
  hasProject: boolean;
  detailLevel: DetailLevel;
};

/** A small glyph per feature family, so rows scan without needing a border. */
function featureIcon(kind: string) {
  const lowered = kind.toLowerCase();
  if (lowered.includes("hole") || lowered.includes("pocket") || lowered.includes("cut")) {
    return <Scissors size={13} />;
  }
  if (lowered.includes("cylinder") || lowered.includes("boss") || lowered.includes("circle")) {
    return <Circle size={13} />;
  }
  if (lowered.includes("sketch") || lowered.includes("rectangle")) {
    return <Square size={13} />;
  }
  if (lowered.includes("fillet") || lowered.includes("chamfer") || lowered.includes("pattern")) {
    return <Ruler size={13} />;
  }
  return <Box size={13} />;
}

/**
 * Left rail: the structure of the open part, plus secondary navigation.
 *
 * Projects and History sit in the footer rather than the header, so they stop
 * competing with Open and Export. Feature rows carry no border of their own --
 * selection is a background tint and an accent edge, which removes the
 * card-within-card look the review flagged.
 */
export function DesignRail({
  selectedProject,
  selectedOperationId,
  previewObjects,
  onSelectOperation,
  onCollapse,
  onOpenProjects,
  onOpenHistory,
  hasProject,
  detailLevel
}: DesignRailProps) {
  const model = selectedProject?.current_model;
  const operations = Array.isArray(model?.operations)
    ? (model.operations as Record<string, unknown>[])
    : [];
  const parameters = Array.isArray(model?.parameters)
    ? (model.parameters as DesignParameter[])
    : [];
  const relationships = Array.isArray(model?.relationships)
    ? (model.relationships as ParametricRelationship[])
    : [];
  const templateObject =
    operations.length === 0
      ? previewObjects.find((object) => object.operation_id === "model")
      : null;
  const advanced = detailLevel === "advanced";

  return (
    <aside className="rail rail-left" aria-label="Design tree">
      <div className="rail-head">
        <span className="panel-label">Design Tree</span>
        <button
          type="button"
          className="icon-only"
          onClick={onCollapse}
          title="Collapse the design tree"
          aria-label="Collapse design tree"
        >
          <PanelLeftClose size={15} />
        </button>
      </div>

      <div className="rail-scroll">
        {!selectedProject ? (
          <p className="rail-empty">No model open.</p>
        ) : (
          <>
            <section className="rail-section">
              <h3 className="section-label">Features</h3>
              <div className="feature-rows">
                {operations.length === 0 && model ? (
                  <button
                    type="button"
                    className={selectedOperationId === "model" ? "feature-row selected" : "feature-row"}
                    onClick={() => onSelectOperation("model")}
                  >
                    <span className="feature-glyph">{featureIcon(String(model.part_type ?? ""))}</span>
                    <span className="feature-text">
                      <span className="feature-name">
                        {templateObject?.label ?? String(model.part_type ?? "Part")}
                      </span>
                      <span className="feature-kind">
                        {String(model.part_type ?? "template").replace(/_/g, " ")}
                      </span>
                    </span>
                  </button>
                ) : null}

                {operations.map((operation) => {
                  const id = String(operation.id);
                  const kind = operationKind(operation);
                  return (
                    <button
                      type="button"
                      key={id}
                      className={selectedOperationId === id ? "feature-row selected" : "feature-row"}
                      onClick={() => onSelectOperation(id)}
                    >
                      <span className="feature-glyph">{featureIcon(kind)}</span>
                      <span className="feature-text">
                        <span className="feature-name">{operationDisplayName(operation)}</span>
                        <span className="feature-kind">{kind}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>

            {/* Design-intent detail is an Advanced concern; Simple mode keeps
                the rail to the feature list. */}
            {advanced && parameters.length > 0 ? (
              <section className="rail-section">
                <h3 className="section-label">Parameters</h3>
                <dl className="stat-rows">
                  {parameters.map((parameter) => (
                    <div className="stat-row" key={parameter.parameter_id}>
                      <dt>{parameter.name}</dt>
                      <dd>
                        {formatNumber(parameter.value)} {parameter.unit}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : null}

            {advanced && relationships.length > 0 ? (
              <section className="rail-section">
                <h3 className="section-label">Relationships</h3>
                <dl className="stat-rows">
                  {relationships.slice(0, 8).map((relationship) => (
                    <div className="stat-row" key={relationship.relationship_id}>
                      <dt>{relationship.relationship_id.replace(/_/g, " ")}</dt>
                      <dd>{relationship.relationship_type.replace(/_/g, " ")}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : null}
          </>
        )}
      </div>

      <footer className="rail-foot">
        <button type="button" className="rail-nav" onClick={onOpenProjects}>
          <FolderOpen size={14} />
          Projects
        </button>
        <button
          type="button"
          className="rail-nav"
          onClick={onOpenHistory}
          disabled={!hasProject}
          title={hasProject ? "Revision history" : "Open a project first"}
        >
          <History size={14} />
          History
        </button>
      </footer>
    </aside>
  );
}

function formatNumber(value: number): string {
  return Number.isInteger(value)
    ? String(value)
    : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}
