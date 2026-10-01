import { KeyRound, Send } from "lucide-react";
import { useRef, useState } from "react";

import { EXAMPLE_PROMPTS } from "./EmptyWorkspace";
import type { PresentedError } from "./errorPresentation";
import { promptStateInfo, type PromptState } from "./promptState";
import { promptGate, promptKeyAction } from "./workspaceLayout";

type Clarification = {
  question: string;
  options: string[];
};

type PromptBarProps = {
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
  onSetupHelp: () => void;
};

/**
 * The persistent command bar.
 *
 * Pinned to the bottom of the workspace shell and never inside a scrolling
 * panel, so the primary interaction is always one click away. Previously this
 * lived in a 340x208 px cell in the bottom-right corner, below the fold.
 */
export function PromptBar({
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
  onChooseClarification,
  onSetupHelp
}: PromptBarProps) {
  const [showExamples, setShowExamples] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const info = promptStateInfo(state);
  const gate = promptGate({
    aiConfigured,
    backendOnline,
    busy: info.busy,
    text: prompt
  });

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    const action = promptKeyAction(event);
    if (action === "submit") {
      event.preventDefault();
      if (gate.sendEnabled) {
        onSubmit();
      }
      return;
    }
    // "newline" and "ignore" both fall through to the browser's default.
  }

  return (
    <section className="prompt-bar" aria-label="Design assistant">
      {error ? <ErrorNotice error={error} onDismiss={onDismissError} onRetry={onSubmit} /> : null}

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

      {!aiConfigured ? (
        <div className="prompt-unconfigured" role="status">
          <KeyRound size={14} aria-hidden="true" />
          <div>
            <strong>AI ASSISTANT NOT CONFIGURED</strong>
            <span>
              Configure OPENAI_API_KEY to enable natural-language design. Manual CAD
              features remain available.
            </span>
          </div>
          <button type="button" className="tool-button compact" onClick={onSetupHelp}>
            Setup help
          </button>
        </div>
      ) : null}

      {showExamples ? (
        <ul className="prompt-examples" aria-label="Example prompts">
          {EXAMPLE_PROMPTS.map((example) => (
            <li key={example}>
              <button
                type="button"
                onClick={() => {
                  onPromptChange(example);
                  setShowExamples(false);
                  textareaRef.current?.focus();
                }}
              >
                {example}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="prompt-row">
        <div className="prompt-state" title={info.hint}>
          <span className={`status-dot tone-${info.tone}`} aria-hidden="true" />
          <strong>{info.label}</strong>
        </div>

        <label className="visually-hidden" htmlFor="design-prompt">
          Describe what you want to build
        </label>
        <textarea
          id="design-prompt"
          ref={textareaRef}
          className="prompt-input"
          rows={1}
          value={prompt}
          disabled={!gate.inputEnabled}
          onChange={(event) => onPromptChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            selectedProjectId
              ? "Describe a change, for example: make the boss 5 mm taller..."
              : "Describe what you want to build..."
          }
        />

        <button
          type="button"
          className="tool-button compact"
          onClick={() => setShowExamples((visible) => !visible)}
          aria-expanded={showExamples}
          title="Example prompts"
        >
          Examples
        </button>

        <button
          type="button"
          className="send-button"
          onClick={onSubmit}
          disabled={!gate.sendEnabled}
          title={gate.reason ?? "Send the request (Enter)"}
        >
          <Send size={16} />
          {info.busy ? "Working" : "Send"}
        </button>
      </div>

      {gate.reason && aiConfigured ? (
        <p className="prompt-reason">{gate.reason}</p>
      ) : null}
    </section>
  );
}

function ErrorNotice({
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
