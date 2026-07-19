import { AlertTriangle, LoaderCircle, X } from "lucide-react";
import { useEffect, useRef } from "react";

import type { Repository } from "../repositories.types";

type DeleteRepositoryModalProps = {
  repository: Repository;
  isOpen: boolean;
  isDeleting: boolean;
  errorMessage?: string | null;
  onCancel: () => void;
  onConfirm: () => void;
};

export function DeleteRepositoryModal({
  repository,
  isOpen,
  isDeleting,
  errorMessage,
  onCancel,
  onConfirm,
}: DeleteRepositoryModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;

    if (!dialog) {
      return;
    }

    if (isOpen && !dialog.open) {
      dialog.showModal();
    }

    if (!isOpen && dialog.open) {
      dialog.close();
    }
  }, [isOpen]);

  function handleCancel() {
    if (isDeleting) {
      return;
    }

    onCancel();
  }

  return (
    <dialog
      ref={dialogRef}
      className="delete-modal"
      aria-labelledby="delete-modal-title"
      aria-describedby="delete-modal-description"
      onCancel={(event) => {
        event.preventDefault();
        handleCancel();
      }}
      onClose={() => {
        if (isOpen && !isDeleting) {
          onCancel();
        }
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) {
          handleCancel();
        }
      }}
    >
      <div className="delete-modal__panel">
        <div className="delete-modal__header">
          <span className="delete-modal__icon" aria-hidden="true">
            <AlertTriangle size={22} />
          </span>

          <button
            className="delete-modal__close"
            type="button"
            aria-label="Close delete confirmation"
            disabled={isDeleting}
            onClick={handleCancel}
          >
            <X size={19} aria-hidden="true" />
          </button>
        </div>

        <div className="delete-modal__content">
          <h2 id="delete-modal-title">Delete repository?</h2>

          <p id="delete-modal-description">
            This will remove{" "}
            <strong>
              {repository.owner}/{repository.name}
            </strong>{" "}
            from Trace.
          </p>

          <p className="delete-modal__warning">This action cannot be undone.</p>

          {errorMessage ? (
            <p className="delete-modal__error" role="alert">
              {errorMessage}
            </p>
          ) : null}
        </div>

        <div className="delete-modal__actions">
          <button
            className="delete-modal__cancel"
            type="button"
            disabled={isDeleting}
            onClick={handleCancel}
          >
            Cancel
          </button>

          <button
            className="delete-modal__confirm"
            type="button"
            disabled={isDeleting}
            onClick={onConfirm}
          >
            {isDeleting ? (
              <>
                <LoaderCircle
                  className="delete-modal__spinner"
                  size={17}
                  aria-hidden="true"
                />
                Deleting
              </>
            ) : (
              "Delete repository"
            )}
          </button>
        </div>
      </div>
    </dialog>
  );
}
