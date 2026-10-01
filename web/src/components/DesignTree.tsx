import type { DesignParameter, ParametricRelationship, PreviewObject, ProjectDetail } from "../types/api";
import { operationDisplayName, operationKind, templateDetails } from "../utils/modelFormatting";
import { emptyState } from "./uiState";
import type { DetailLevel } from "./workspaceLayout";

type DesignTreeProps = {
  selectedProject: ProjectDetail | null;
  selectedOperationId: string | null;
  previewObjects: PreviewObject[];
  onSelectOperation: (operationId: string) => void;
  detailLevel: DetailLevel;
};

/**
 * The design tree for the open part.
 *
 * The project browser used to live here, permanently consuming the left
 * column while editing. It moved to a drawer; this panel now shows only the
 * structure of the part in front of you.
 */
export function DesignTree({
  selectedProject,
  selectedOperationId,
  previewObjects,
  onSelectOperation,
  detailLevel
}: DesignTreeProps) {
  const model = selectedProject?.current_model;
  const operations = Array.isArray(model?.operations) ? (model.operations as Record<string, unknown>[]) : [];
  const parameters = Array.isArray(model?.parameters) ? (model.parameters as DesignParameter[]) : [];
  const relationships = Array.isArray(model?.relationships) ? (model.relationships as ParametricRelationship[]) : [];
  const templateObject = operations.length === 0
    ? previewObjects.find((object) => object.operation_id === "model")
    : null;

  if (!selectedProject) {
    const info = emptyState("projects");
    return (
      <div className="tree-body">
        <div className="empty-inline">
          <strong>{info.message}</strong>
          <small>{info.action}</small>
        </div>
      </div>
    );
  }

  const advanced = detailLevel === "advanced";

  return (
    <div className="tree-body">
      {/* Parameters and relationships are design-intent detail; the simple
          level keeps the tree to the feature list. */}
      {advanced && parameters.length > 0 ? (
        <>
          <div className="tree-group-label">Parameters</div>
          {parameters.map((parameter) => (
            <div className="tree-item" key={parameter.parameter_id}>
              <span>{parameter.name}</span>
              <small>
                {parameter.role.toUpperCase()} · {formatNumber(parameter.value)} {parameter.unit}
              </small>
            </div>
          ))}
        </>
      ) : null}

      {advanced && relationships.length > 0 ? (
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

      {model && operations.length === 0 ? (
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
      ) : null}

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
  );
}

function formatNumber(value: number): string {
  return Number.isInteger(value)
    ? String(value)
    : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}
