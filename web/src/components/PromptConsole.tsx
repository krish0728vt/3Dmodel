import { Send } from "lucide-react";
import { useState } from "react";

import { EXAMPLE_PROMPTS } from "./EmptyWorkspace";
import type { PresentedError } from "./errorPresentation";
import { promptStateInfo, type PromptState } from "./promptState";

type Clarification = {
  question: string;
  options: string[];
};

type PromptConsoleProps = {
  prompt: string;
  state: PromptState;
  aiConfigured: boolean;
  backendOnline: boolean;
  selectedProjectId: string | null;
  error: PresentedError | null;
  clarification: Clarification | null;
  onPromptChange: (prompt: string) => void;
  onSubmit: () => void;
  onDismissError: () => void;
  onChooseClarification: (option: string) => void;
};

export function PromptConsole({
  prompt,
  state,
  aiConfigured,
  backendOnline,
  selectedProjectId,
  error,
  clarification,
  onPromptChange,
  onSubmit,
  onDismissError,
  onChooseClarification
}: PromptConsoleProps) {
  const [showExamples, setShowExamples] = useState(false);
  const info = promptStateInfo(state);
  const disabled = info.busy || !backendOnline;

  return (
    <section className="prompt-console" aria-label="Design prompt">
      <div className="console-header">
        <div className="console-identity">
          <div className="panel-title">SHAH Design Assistant</div>
          <div className="prompt-status">
            <span className={`status-dot tone-${info.tone}`} aria-hidden="true" />
            <strong>{info.label}</strong>
            <small>{info.hint}</small>
          </div>
        </div>
        <button
          type="button"
          className="tool-button compact"
          onClick={() => setShowExamples((visible) => !visible)}
          aria-expanded={showExamples}
        >
          Examples
        </button>
      </div>

      {showExamples ? (
        <ul className="example-strip" aria-label="Example prompts">
          {EXAMPLE_PROMPTS.map((example) => (
            <li key={example}>
              <button
                type="button"
                onClick={() => {
                  onPromptChange(example);
                  setShowExamples(false);
                }}
              >
                {example}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {aiConfigured ? null : (
        <div className="notice notice-warning" role="status">
          <strong>AI ASSISTANT NOT CONFIGURED</strong>
          <p>
            Manual CAD and deterministic tools remain available. Configure
            OPENAI_API_KEY in .env to enable natural-language design.
          </p>
        </div>
      )}

      {clarification ? (
        <div className="notice notice-attention" role="status">
          <strong>NEEDS CLARIFICATION</strong>
          <p>{clarification.question}</p>
          <div className="clarification-options">
            {clarification.options.map((option, index) => (
              <button
                type="button"
                key={option}
                className="tool-button compact"
                onClick={() => onChooseClarification(option)}
              >
                {index + 1}. {option}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {error ? <ErrorPanel error={error} onDismiss={onDismissError} onRetry={onSubmit} /> : null}

      <div className="console-body">
        <label className="visually-hidden" htmlFor="design-prompt">
          Design prompt
        </label>
        <textarea
          id="design-prompt"
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          placeholder={
            selectedProjectId
              ? "Describe a change, for example: make the boss 5 mm taller."
              : "Describe what you want to build..."
          }
        />
        <button
          type="button"
          className="send-button"
          onClick={onSubmit}
          disabled={disabled || prompt.trim().length === 0}
          title={backendOnline ? "Run the prompt" : "Backend is offline"}
        >
          <Send size={18} />
          {info.busy ? "Working" : "Run"}
        </button>
      </div>
    </section>
  );
}

function ErrorPanel({
  error,
  onDismiss,
  onRetry
}: {
  error: PresentedError;
  onDismiss: () => void;
  onRetry: () => void;
}) {
  const [showDetails, setShowDetails] = useState(false);
  const hasDetails = error.category !== null || error.technical !== null;

  return (
    <div className="notice notice-error" role="alert">
      <strong>{error.title}</strong>
      <p>{error.explanation}</p>
      {error.suggestion ? <p className="notice-suggestion">{error.suggestion}</p> : null}
      <div className="notice-actions">
        <button type="button" className="tool-button compact" onClick={onRetry}>
          Retry
        </button>
        <button type="button" className="tool-button compact" onClick={onDismiss}>
          Dismiss
        </button>
        {hasDetails ? (
          <button
            type="button"
            className="tool-button compact"
            onClick={() => setShowDetails((visible) => !visible)}
            aria-expanded={showDetails}
          >
            {showDetails ? "Hide details" : "Show details"}
          </button>
        ) : null}
      </div>
      {showDetails && hasDetails ? (
        <dl className="notice-details">
          {error.category ? (
            <div className="feature-row">
              <dt>Failure category</dt>
              <dd>{error.category}</dd>
            </div>
          ) : null}
          {error.technical ? (
            <div className="feature-row">
              <dt>Backend message</dt>
              <dd>{error.technical}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
    </div>
  );
}
