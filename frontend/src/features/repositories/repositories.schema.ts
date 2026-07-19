import { z } from "zod";

function parseUrl(value: string): URL | null {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

export const repositoryUrlSchema = z
  .string()
  .trim()
  .min(1, "Enter a GitHub repository URL.")
  .refine((value) => parseUrl(value) !== null, "Enter a valid URL")
  .refine((value) => {
    const url = parseUrl(value);

    if (!url) {
      return false;
    }

    return url.protocol === "https:" || url.protocol === "http:";
  }, "URL must use http or https")
  .refine((value) => {
    const url = parseUrl(value);

    if (!url) {
      return false;
    }

    return url.hostname === "github.com" || url.hostname === "www.github.com";
  }, "Repository must be hosted on GitHub")
  .refine((value) => {
    const url = parseUrl(value);

    if (!url) {
      return false;
    }

    const segments = url.pathname.split("/").filter(Boolean);

    return segments.length === 2;
  }, "Use a repository URL like github.com/owner/repository");

export type RepositoryUrlInput = z.infer<typeof repositoryUrlSchema>;
