import type { EngineeringReport, MaterialSpec } from "../types/api";

type EngineeringPanelProps = {
  report: EngineeringReport | null;
  materials: MaterialSpec[];
  materialId: string;
  process: string;
  displayUnits: "mm" | "in";
  onMaterialChange: (materialId: string) => void;
  onProcessChange: (process: string) => void;
  onDisplayUnitsChange: (unit: "mm" | "in") => void;
};

export function EngineeringPanel({
  report,
  materials,
  materialId,
  process,
  displayUnits,
  onMaterialChange,
  onProcessChange,
  onDisplayUnitsChange
}: EngineeringPanelProps) {
  return (
    <section className="engineering-panel">
      <h3>Engineering</h3>
      <div className="engineering-controls">
        <label>
          Material
          <select value={materialId} onChange={(event) => onMaterialChange(event.target.value)}>
            <option value="">None</option>
            {materials.map((material) => (
              <option value={material.material_id} key={material.material_id}>
                {material.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Process
          <select value={process} onChange={(event) => onProcessChange(event.target.value)}>
            <option value="unknown">Unspecified</option>
            <option value="3d_printing">3D Printing</option>
            <option value="cnc_machining">CNC Machining</option>
          </select>
        </label>
        <div className="segmented">
          <button className={displayUnits === "mm" ? "active" : ""} type="button" onClick={() => onDisplayUnitsChange("mm")}>
            mm
          </button>
          <button className={displayUnits === "in" ? "active" : ""} type="button" onClick={() => onDisplayUnitsChange("in")}>
            in
          </button>
        </div>
      </div>
      {report ? (
        <>
          <dl>
            <div className="feature-row">
              <dt>X</dt>
              <dd>{format(report.display_metrics.x)} {report.display_metrics.length_unit}</dd>
            </div>
            <div className="feature-row">
              <dt>Y</dt>
              <dd>{format(report.display_metrics.y)} {report.display_metrics.length_unit}</dd>
            </div>
            <div className="feature-row">
              <dt>Z</dt>
              <dd>{format(report.display_metrics.z)} {report.display_metrics.length_unit}</dd>
            </div>
            <div className="feature-row">
              <dt>Volume</dt>
              <dd>{format(report.geometry_metrics.volume_mm3)} mm3</dd>
            </div>
            <div className="feature-row">
              <dt>Area</dt>
              <dd>{format(report.geometry_metrics.surface_area_mm2)} mm2</dd>
            </div>
            <div className="feature-row">
              <dt>Mass</dt>
              <dd>{report.mass_estimate ? `${format(report.mass_estimate.mass_g)} g` : "No material"}</dd>
            </div>
            <div className="feature-row">
              <dt>Density</dt>
              <dd>{report.material ? `${report.material.density_g_cm3} g/cm3` : "No material"}</dd>
            </div>
          </dl>
          <div className="warning-list">
            {report.warnings.map((warning) => (
              <div className={`warning ${warning.severity.toLowerCase()}`} key={warning.warning_id}>
                <strong>{warning.severity}: {warning.title}</strong>
                <span>{warning.message}</span>
                {warning.recommendation ? <small>{warning.recommendation}</small> : null}
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="muted">Engineering metrics load when a project revision is active.</div>
      )}
    </section>
  );
}

function format(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}
