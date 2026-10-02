import { AlertTriangle, Send } from "lucide-react";
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
 * One command bar.
 *
 * The previous version stacked four layers -- a full-width AI warning, a status
 * row, the textarea and an Examples button -- which made the most important
 * control the tallest and busiest region on screen. Everything optional is now
 * either a single thin line above the input or hidden until it applies.
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
  const gate = promptGate({ aiConfigured, backendOnline, busy: info.busy, text: prompt });

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (promptKeyAction(event) === "submit") {
      event.preventDefault();
      if (gate.sendEnabled) {
        onSubmit();
      }
    }
    // "newline" and "ignore" fall through to the browser default.
  }

  return (
    <section className="command-bar" aria-label="Design assistant">
      {/* Only one of these three ever shows, so the bar keeps a stable height
          in normal use. */}
      {error ? (
        <ErrorLine error={error} onDismiss={onDismissError} onRetry={onSubmit} />
      ) : clarification ? (
        <div className="command-line attention" role="status">
          <span className="command-line-text">{clarification.question}</span>
          <span className="command-line-actions">
            {clarification.options.map((option, index) => (
              <button
                type="button"
                key={option}
                className="link-action"
                onClick={() => onChooseClarification(option)}
              >
                {index + 1}. {option}
              </button>
            ))}
          </span>
        </div>
      ) : !aiConfigured ? (
        <div className="command-line warn" role="status">
          <AlertTriangle size={13} aria-hidden="true" />
          <span className="command-line-text">
            AI assistant unavailable &mdash; configure API key
          </span>
          <button type="button" className="link-action" onClick={onSetupHelp}>
            Setup
          </button>
        </div>
      ) : null}

      {showExamples ? (
        <div className="command-examples">
          {EXAMPLE_PROMPTS.map((example) => (
            <button
              type="button"
              key={example}
              onClick={() => {
                onPromptChange(example);
                setShowExamples(false);
                textareaRef.current?.focus();
              }}
            >
              {example}
            </button>
          ))}
        </div>
      ) : null}

      <div className="command-row">
        <span className="command-status" title={info.hint}>
          <span className={`status-dot tone-${info.tone}`} aria-hidden="true" />
          <span className="command-status-text">{statusWord(info.label)}</span>
        </span>

        <label className="visually-hidden" htmlFor="design-prompt">
          Describe what you want to build
        </label>
        <textarea
          id="design-prompt"
          ref={textareaRef}
          className="command-input"
          rows={1}
          value={prompt}
          disabled={!gate.inputEnabled}
          onChange={(event) => onPromptChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            selectedProjectId
              ? "Describe what you want to change..."
              : "Describe what you want to build..."
          }
        />

        <button
          type="button"
          className="link-action command-examples-toggle"
          onClick={() => setShowExamples((visible) => !visible)}
          aria-expanded={showExamples}
        >
          Examples
        </button>

        <button
          type="button"
          className="command-send"
          onClick={onSubmit}
          disabled={!gate.sendEnabled}
          title={gate.reason ?? "Send the request (Enter)"}
        >
          <Send size={15} />
          {info.busy ? "Working" : "Send"}
        </button>
      </div>
    </section>
  );
}

/** Sentence case for the status dot; the bar is not a place for shouting. */
function statusWord(label: string): string {
  const lowered = label.toLowerCase();
  return lowered.charAt(0).toUpperCase() + lowered.slice(1);
}

function ErrorLine({
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
    <div className="command-line error" role="alert">
      <AlertTriangle size={13} aria-hidden="true" />
      <span className="command-line-text">
        <strong>{error.title}</strong> {error.explanation}
        {error.suggestion ? ` ${error.suggestion}` : ""}
      </span>
      <span className="command-line-actions">
        <button type="button" className="link-action" onClick={onRetry}>
          Retry
        </button>
        {hasDetails ? (
          <button
            type="button"
            className="link-action"
            onClick={() => setShowDetails((visible) => !visible)}
            aria-expanded={showDetails}
          >
            {showDetails ? "Hide details" : "Details"}
          </button>
        ) : null}
        <button type="button" className="link-action" onClick={onDismiss}>
          Dismiss
        </button>
      </span>
      {showDetails && hasDetails ? (
        <dl className="command-details">
          {error.category ? (
            <div className="stat-row">
              <dt>Failure category</dt>
              <dd className="mono">{error.category}</dd>
            </div>
          ) : null}
          {error.technical ? (
            <div className="stat-row">
              <dt>Backend message</dt>
              <dd className="mono">{error.technical}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
    </div>
  );
}
