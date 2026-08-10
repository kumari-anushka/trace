import axios from "axios";
import { ArrowLeft, ExternalLink, Search, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Footer } from "../components/layout/Footer";
import { Header } from "../components/layout/Header";
import { PageContainer } from "../components/layout/PageContainer";
import { AtlasNav } from "../features/atlas/components/AtlasNav";
import { useRepositoryQuery } from "../features/ask/hooks/useRepositoryQuery";
import { useRepository } from "../features/repositories/hooks/useRepositories";

const examples = [
  "How is ingestion organized?",
  "Why did the query architecture change?",
  "Who has relevant review context?",
];

export function AskPage() {
  const { repositoryId } = useParams();
  const repositoryQuery = useRepository(repositoryId);
  const query = useRepositoryQuery(repositoryId);
  const [question, setQuestion] = useState("");
  const repositoryNotFound =
    axios.isAxiosError(repositoryQuery.error) &&
    repositoryQuery.error.response?.status === 404;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = question.trim();
    if (value.length >= 3) query.mutate(value);
  }

  return (
    <div className="app-shell atlas-shell">
      <Header />
      <main className="atlas-page ask-page">
        <PageContainer>
          <Link
            className="atlas-back"
            to={repositoryId ? `/repositories/${repositoryId}` : "/"}
          >
            <ArrowLeft size={15} aria-hidden="true" /> Repository
          </Link>

          {repositoryQuery.isPending ? (
            <div className="atlas-state" aria-busy="true">
              <span /> <p>Loading repository…</p>
            </div>
          ) : repositoryQuery.isError ? (
            <div className="atlas-state" role="alert">
              <h1>
                {repositoryNotFound
                  ? "Repository not found"
                  : "Ask unavailable"}
              </h1>
              <p>
                {repositoryNotFound
                  ? "This repository may have been deleted."
                  : "Trace could not load this repository."}
              </p>
            </div>
          ) : repositoryQuery.data && repositoryId ? (
            <div className="atlas-content">
              <header className="atlas-hero">
                <div>
                  <p>
                    {repositoryQuery.data.owner}/{repositoryQuery.data.name}
                  </p>
                  <h1>Ask Atlas</h1>
                  <span>
                    Answers are limited to evidence in the latest snapshot.
                  </span>
                </div>
              </header>
              <AtlasNav repositoryId={repositoryId} />

              <section className="ask-compose" aria-labelledby="ask-title">
                <div>
                  <p>Repository question</p>
                  <h2 id="ask-title">What do you need to understand?</h2>
                </div>
                <form onSubmit={submit}>
                  <label htmlFor="atlas-question" className="sr-only">
                    Ask a question about this repository
                  </label>
                  <textarea
                    id="atlas-question"
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="Ask about architecture, history, decisions, code, or contributors…"
                    maxLength={2000}
                    rows={3}
                  />
                  <button
                    type="submit"
                    disabled={question.trim().length < 3 || query.isPending}
                  >
                    <Search size={16} aria-hidden="true" />
                    {query.isPending ? "Searching…" : "Ask"}
                  </button>
                </form>
                {!query.data ? (
                  <div className="ask-examples" aria-label="Example questions">
                    {examples.map((example) => (
                      <button
                        key={example}
                        type="button"
                        onClick={() => setQuestion(example)}
                      >
                        {example}
                      </button>
                    ))}
                  </div>
                ) : null}
              </section>

              {query.isError ? (
                <p className="ask-error" role="alert">
                  Trace could not answer that question. Check the snapshot and
                  try again.
                </p>
              ) : null}

              {query.data ? (
                <div className="ask-result" aria-live="polite">
                  <section className="ask-answer">
                    <header>
                      <span>
                        <ShieldCheck size={17} aria-hidden="true" />
                        {query.data.grounded
                          ? "Sources checked"
                          : "Insufficient evidence"}
                      </span>
                    </header>
                    <h2>Answer</h2>
                    {query.data.claims.length ? (
                      query.data.claims.map((claim, index) => (
                        <p key={`${claim.text}-${index}`}>
                          {claim.text}{" "}
                          {claim.citation_ids.map((citationId) => {
                            const citationIndex =
                              query.data.citations.findIndex(
                                (item) => item.id === citationId,
                              );
                            return citationIndex >= 0 ? (
                              <a
                                key={citationId}
                                href={`#citation-${citationIndex + 1}`}
                              >
                                [{citationIndex + 1}]
                              </a>
                            ) : null;
                          })}
                        </p>
                      ))
                    ) : (
                      <p>{query.data.answer}</p>
                    )}
                    {query.data.limitations.length ? (
                      <details>
                        <summary>
                          Limitations ({query.data.limitations.length})
                        </summary>
                        <ul>
                          {query.data.limitations.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </details>
                    ) : null}
                  </section>

                  <aside className="ask-sources" aria-label="Answer sources">
                    <h2>Sources</h2>
                    {query.data.citations.length ? (
                      query.data.citations.map((citation, index) => (
                        <article key={citation.id} id={`citation-${index + 1}`}>
                          <span>
                            [{index + 1}]{" "}
                            {citation.source_type.replaceAll("_", " ")}
                          </span>
                          <h3>{citation.title}</h3>
                          <p>{citation.excerpt}</p>
                          {citation.source_url ? (
                            <a
                              href={citation.source_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open source{" "}
                              <ExternalLink size={13} aria-hidden="true" />
                            </a>
                          ) : null}
                        </article>
                      ))
                    ) : (
                      <p>No source met the citation threshold.</p>
                    )}
                  </aside>
                </div>
              ) : null}
            </div>
          ) : null}
        </PageContainer>
      </main>
      <Footer />
    </div>
  );
}
