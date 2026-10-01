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

/**
 * First run.
 *
 * One question, three ways to start, and the example prompts. The real prompt
 * input is the persistent bar at the bottom of the workspace, so this screen
 * points at it rather than duplicating it.
 */
export function EmptyWorkspace({
  onExample,
  onNewPart,
  onNewAssembly,
  onOpenProjects,
  hasProjects,
  aiConfigured
}: EmptyWorkspaceProps) {
  return (
    <section className="first-run" aria-label="Getting started">
      <img className="first-run-logo" src="/shah-industries-logo.png" alt="SHAH INDUSTRIES" />
      <h1 className="first-run-question">What do you want to build?</h1>
      <p className="first-run-hint">
        {aiConfigured
          ? "Describe a part in the bar below, or start from one of these."
          : "Natural-language prompts need an API key. Start from a manual part or open an existing project."}
      </p>

      <div className="first-run-actions">
        <button type="button" className="tool-button primary" onClick={onNewPart}>
          New part
        </button>
        <button type="button" className="tool-button" onClick={onNewAssembly}>
          New assembly
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

      <div className="first-run-examples">
        <h2>Example prompts</h2>
        <ul>
          {EXAMPLE_PROMPTS.map((example) => (
            <li key={example}>
              <button
                type="button"
                onClick={() => onExample(example)}
                disabled={!aiConfigured}
                title={
                  aiConfigured
                    ? "Use this prompt"
                    : "Needs OPENAI_API_KEY; see the notice in the prompt bar"
                }
              >
                {example}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
