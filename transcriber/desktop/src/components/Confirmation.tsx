/*
 * Confirmation.tsx
 * Native HTML dialog for decisions that would interrupt work or discard a result.
 */
import { useEffect, useRef } from 'react';

// showModal supplies focus containment; cancellation always preserves current work.
export default function Confirmation({
  title,
  message,
  acceptLabel,
  onAccept,
  onCancel,
}: {
  title: string;
  message: string;
  acceptLabel: string;
  onAccept: () => void;
  onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    cancel.current?.focus();
    return () => element.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      aria-labelledby="confirmation-title"
      aria-describedby="confirmation-message"
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
    >
      <h2 id="confirmation-title">{title}</h2>
      <p id="confirmation-message">{message}</p>
      <div className="actions">
        <button ref={cancel} onClick={onCancel}>
          Cancel
        </button>
        <button className="danger" onClick={onAccept}>
          {acceptLabel}
        </button>
      </div>
    </dialog>
  );
}
