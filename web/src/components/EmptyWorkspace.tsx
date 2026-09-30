type EmptyWorkspaceProps = {
  onExample: (prompt: string) => void;
  onNewPart: () => void;
  onOpenProjects: () => void;
};

export function EmptyWorkspace({ onExample, onNewPart, onOpenProjects }: EmptyWorkspaceProps) {
  return (
    <section className="empty-workspace">
      <img src="/shah-industries-logo.png" alt="SHAH INDUSTRIES" />
      <p>AI-ASSISTED PARAMETRIC ENGINEERING</p>
      <div className="empty-actions">
        <button type="button" className="tool-button" onClick={onNewPart}>
          New Part
        </button>
        <button type="button" className="tool-button" onClick={onOpenProjects}>
          Open Projects
        </button>
      </div>
      <div className="empty-examples">
        <button type="button" onClick={() => onExample("Create a 100 x 60 x 5 mm mounting plate.")}>
          Mounting Plate
        </button>
        <button type="button" onClick={() => onExample("Create an enclosure for a 70 x 45 mm PCB.")}>
          PCB Enclosure
        </button>
        <button type="button" onClick={() => onExample("Create an 80 mm base with a center boss.")}>
          Center Boss Base
        </button>
      </div>
    </section>
  );
}
