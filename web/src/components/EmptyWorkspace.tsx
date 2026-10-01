type EmptyWorkspaceProps = {
  onExample: (prompt: string) => void;
  onNewPart: () => void;
  onNewAssembly: () => void;
  onOpenProjects: () => void;
  hasProjects: boolean;
  aiConfigured: boolean;
};

/** Example prompts offered on first run. Full sentences, not labels, so the
 *  shape of a useful request is obvious before the user types anything. */
export const EXAMPLE_PROMPTS = [
  "Create a 100 x 60 x 5 mm mounting plate with four holes 8 mm from the corners.",
  "Create an open-top enclosure for a 70 x 45 mm PCB.",
  "Create a 30 mm diameter spacer with an 8 mm center hole."
] as const;

export function EmptyWorkspace({
  onExample,
  onNewPart,
  onNewAssembly,
  onOpenProjects,
  hasProjects,
  aiConfigured
}: EmptyWorkspaceProps) {
  return (
    <section className="empty-workspace" aria-label="Getting started">
      <img src="/shah-industries-logo.png" alt="SHAH INDUSTRIES" />
      <p className="empty-tagline">AI-ASSISTED PARAMETRIC ENGINEERING</p>

      <div className="empty-block">
        <h2 className="empty-heading">Start with</h2>
        <div className="empty-actions">
          <button type="button" className="tool-button primary" onClick={onNewPart}>
            Create a part
          </button>
          <button type="button" className="tool-button" onClick={onNewAssembly}>
            Create an assembly
          </button>
          <button
            type="button"
            className={hasProjects ? "tool-button" : "tool-button disabled"}
            onClick={onOpenProjects}
            disabled={!hasProjects}
            title={hasProjects ? "Browse saved projects" : "No saved projects yet"}
          >
            Open project
          </button>
        </div>
      </div>

      <div className="empty-block">
        <h2 className="empty-heading">
          {aiConfigured ? "Example prompts" : "Example prompts (need an API key)"}
        </h2>
        <ul className="empty-examples">
          {EXAMPLE_PROMPTS.map((example) => (
            <li key={example}>
              <button type="button" onClick={() => onExample(example)}>
                {example}
              </button>
            </li>
          ))}
        </ul>
        {aiConfigured ? null : (
          <p className="empty-note">
            These use natural-language parsing. Without an API key, build parts from the
            manual and operation-plan tools instead.
          </p>
        )}
      </div>
    </section>
  );
}
