import type { AssemblyDetail, ExportBatchResult, ExportFormat, ProjectDetail } from "../types/api";
import { Drawer } from "./Drawer";
import { ExportPanel } from "./Inspector";

type ExportDrawerProps = {
  project: ProjectDetail;
  selectedAssembly: AssemblyDetail | null;
  exportResult: ExportBatchResult | null;
  onExport: (payload: {
    source_type: "project_revision" | "assembly_revision";
    source_id: string;
    revision: number;
    formats: ExportFormat[];
    options: {
      stl_quality: "draft" | "standard" | "high";
      package: boolean;
      include_manifest: boolean;
      component_mode?: "local" | "assembly_positioned";
    };
  }) => void;
  onClose: () => void;
};

/**
 * Export, behind one header action.
 *
 * The header used to carry permanent STEP and STL buttons while the inspector
 * also held the full export interface. Both are consolidated here.
 */
export function ExportDrawer({
  project,
  selectedAssembly,
  exportResult,
  onExport,
  onClose
}: ExportDrawerProps) {
  return (
    <Drawer title="Export" side="right" onClose={onClose}>
      <ExportPanel
        project={project}
        selectedAssembly={selectedAssembly}
        exportResult={exportResult}
        onExport={onExport}
      />
    </Drawer>
  );
}
