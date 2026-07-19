import axios from "axios";
import { ArrowRight, LoaderCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { useCreateRepository } from "../hooks/useRepositories";
import { repositoryUrlSchema } from "../repositories.schema";

function getApiErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return "Could not add repository. Try again.";
  }

  const detail = error.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (error.response?.status === 409) {
    return "Repository already exists.";
  }

  if (error.response?.status === 422) {
    return "GitHub repository URL is invalid.";
  }

  if (!error.response) {
    return "Could not reach Trace API.";
  }

  return "Could not add repository. Try again.";
}

function scrollToRepositories() {
  document.getElementById("repositories")?.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

export function RepositoryForm() {
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const createRepositoryMutation = useCreateRepository();

  const apiError = createRepositoryMutation.isError
    ? getApiErrorMessage(createRepositoryMutation.error)
    : null;

  const error = validationError ?? apiError;

  function validateRepositoryUrl(value: string): string | null {
    const result = repositoryUrlSchema.safeParse(value);

    if (result.success) {
      return null;
    }

    return result.error.issues[0]?.message ?? "Invalid repository URL.";
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationMessage = validateRepositoryUrl(repositoryUrl);

    if (validationMessage) {
      setValidationError(validationMessage);
      toast.error(validationMessage);
      return;
    }

    setValidationError(null);

    createRepositoryMutation.mutate(
      {
        github_url: repositoryUrl.trim(),
      },
      {
        onSuccess: (repository) => {
          setRepositoryUrl("");

          toast.success("Repository added", {
            description: `${repository.owner}/${repository.name} is ready in your workspace.`,
          });

          window.setTimeout(scrollToRepositories, 150);
        },

        onError: (mutationError) => {
          toast.error("Could not add repository", {
            description: getApiErrorMessage(mutationError),
          });
        },
      },
    );
  }

  return (
    <form className="repository-form" noValidate onSubmit={handleSubmit}>
      <div className="repository-form__field">
        <label className="sr-only" htmlFor="repository-url">
          Public GitHub repository URL
        </label>

        <input
          id="repository-url"
          className="repository-form__input"
          type="text"
          inputMode="url"
          value={repositoryUrl}
          placeholder="https://github.com/owner/repository"
          aria-describedby={error ? "repository-url-error" : undefined}
          aria-invalid={Boolean(error)}
          autoComplete="url"
          spellCheck={false}
          disabled={createRepositoryMutation.isPending}
          onChange={(event) => {
            setRepositoryUrl(event.target.value);

            if (validationError) {
              setValidationError(null);
            }

            if (createRepositoryMutation.isError) {
              createRepositoryMutation.reset();
            }
          }}
          onBlur={(event) => {
            const message = validateRepositoryUrl(event.target.value);

            setValidationError(message);
          }}
        />

        {error ? (
          <p
            className="repository-form__error"
            id="repository-url-error"
            role="alert"
          >
            {error}
          </p>
        ) : null}
      </div>

      <button
        className="repository-form__button"
        type="submit"
        disabled={createRepositoryMutation.isPending}
      >
        {createRepositoryMutation.isPending ? (
          <>
            <LoaderCircle
              className="repository-form__spinner"
              size={18}
              aria-hidden="true"
            />
            Adding repository
          </>
        ) : (
          <>
            Generate Atlas
            <ArrowRight size={18} aria-hidden="true" />
          </>
        )}
      </button>
    </form>
  );
}
