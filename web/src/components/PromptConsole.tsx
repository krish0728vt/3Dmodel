import { Send } from "lucide-react";

type PromptConsoleProps = {
  prompt: string;
  disabled: boolean;
  selectedProjectId: string | null;
  log: string[];
  onPromptChange: (prompt: string) => void;
  onSubmit: () => void;
  onExample: (prompt: string) => void;
};

const examples = [
  "Create a 100 x 60 x 5 mm mounting plate.",
  "Create an enclosure for a 70 x 45 mm PCB.",
  "Create an 80 mm base with a center boss."
];

export function PromptConsole({
  prompt,
  disabled,
  selectedProjectId,
  log,
  onPromptChange,
  onSubmit,
  onExample
}: PromptConsoleProps) {
  return (
    <section className="prompt-console">
      <div className="console-header">
        <div>
          <div className="panel-title">SHAH Design Assistant</div>
          <small>{selectedProjectId ? "Editing current project" : "New project generation"}</small>
        </div>
        <div className="example-strip">
          {examples.map((example) => (
            <button type="button" key={example} onClick={() => onExample(example)}>
              {example}
            </button>
          ))}
        </div>
      </div>
      <div className="console-body">
        <textarea
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          placeholder={selectedProjectId ? "Make the boss 5 mm taller." : "What do you want to build?"}
        />
        <button type="button" className="send-button" onClick={onSubmit} disabled={disabled}>
          <Send size={18} />
          Run
        </button>
      </div>
      <div className="console-log">
        {log.map((line, index) => (
          <div key={`${line}-${index}`}>{line}</div>
        ))}
      </div>
    </section>
  );
}
