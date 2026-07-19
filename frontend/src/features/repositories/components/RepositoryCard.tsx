import { ArrowUpRight, CalendarDays, FolderGit2, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { useDeleteRepository } from "../hooks/useRepositories";
import type { Repository } from "../repositories.types";
import { DeleteRepositoryModal } from "./DeleteRepositoryModal";

type RepositoryCardProps = {
  repository: Repository;
};

export function RepositoryCard({ repository }: RepositoryCardProps) {
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const deleteRepositoryMutation = useDeleteRepository();

  const createdAt = new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(repository.created_at));

  function handleDelete() {
    deleteRepositoryMutation.mutate(repository.id, {
      onSuccess: () => {
        setIsDeleteModalOpen(false);

        toast.success("Repository deleted", {
          description: `${repository.owner}/${repository.name} was removed from Trace.`,
        });
      },

      onError: () => {
        toast.error("Could not delete repository");
      },
    });
  }

  return (
    <>
      <article className="repository-card">
        <div className="repository-card__top">
          <span className="repository-card__icon" aria-hidden="true">
            <FolderGit2 size={20} />
          </span>

          <button
            className="repository-card__delete"
            type="button"
            aria-label={`Delete ${repository.owner}/${repository.name}`}
            onClick={() => {
              deleteRepositoryMutation.reset();
              setIsDeleteModalOpen(true);
            }}
          >
            <Trash2 size={17} aria-hidden="true" />
          </button>
        </div>

        <Link
          className="repository-card__link"
          to={`/repositories/${repository.id}`}
        >
          <div>
            <p className="repository-card__owner">{repository.owner}</p>
            <h3 className="repository-card__name">{repository.name}</h3>
          </div>

          <div className="repository-card__footer">
            <span className="repository-card__meta">
              <CalendarDays size={14} aria-hidden="true" />
              Added {createdAt}
            </span>

            <ArrowUpRight
              className="repository-card__arrow"
              size={18}
              aria-hidden="true"
            />
          </div>
        </Link>
      </article>

      <DeleteRepositoryModal
        repository={repository}
        isOpen={isDeleteModalOpen}
        isDeleting={deleteRepositoryMutation.isPending}
        errorMessage={
          deleteRepositoryMutation.isError
            ? "Trace could not delete this repository. Try again."
            : null
        }
        onCancel={() => {
          deleteRepositoryMutation.reset();
          setIsDeleteModalOpen(false);
        }}
        onConfirm={handleDelete}
      />
    </>
  );
}
