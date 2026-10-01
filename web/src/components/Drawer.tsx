import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

type DrawerSide = "left" | "right" | "bottom";

type DrawerProps = {
  title: string;
  side: DrawerSide;
  onClose: () => void;
  children: ReactNode;
  /** Optional actions rendered in the drawer header. */
  actions?: ReactNode;
};

/**
 * Overlay panel for secondary workspace content.
 *
 * Drawers overlay rather than take a grid track, so opening one never shrinks
 * the viewer. Escape closes, focus moves in on open and returns on close.
 */
export function Drawer({ title, side, onClose, children, actions }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    // Move focus into the drawer so keyboard users land inside it.
    panelRef.current?.focus();
    return () => {
      previouslyFocused.current?.focus?.();
    };
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [onClose]);

  return (
    <div className="drawer-scrim" onClick={onClose}>
      <div
        className={`drawer drawer-${side}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={panelRef}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="drawer-header">
          <h2>{title}</h2>
          <div className="drawer-actions">
            {actions}
            <button
              type="button"
              className="icon-button"
              onClick={onClose}
              aria-label={`Close ${title}`}
            >
              <X size={16} />
            </button>
          </div>
        </header>
        <div className="drawer-body">{children}</div>
      </div>
    </div>
  );
}
