import { ArrowLeft } from "lucide-react";
import { FaGithub } from "react-icons/fa";
import { Link, useLocation } from "react-router-dom";

import { Header } from "../components/layout/Header";
import { PageContainer } from "../components/layout/PageContainer";

export function NotFoundPage() {
  const { pathname } = useLocation();

  return (
    <div className="app-shell not-found-shell">
      <Header />

      <main className="not-found-page">
        <div className="not-found-page__glow" aria-hidden="true" />

        <PageContainer className="not-found-page__container">
          <section className="not-found-page__content">
            <p className="not-found-page__eyebrow">
              <span aria-hidden="true" />
              Error 404 · Route unresolved
            </p>

            <h1>This page left no trace.</h1>
            <p className="not-found-page__description">
              The route you followed doesn’t exist, or it moved somewhere new.
              Let’s get you back to familiar ground.
            </p>

            <div className="not-found-page__actions">
              <Link className="not-found-page__primary" to="/">
                <ArrowLeft size={18} strokeWidth={2} aria-hidden="true" />
                Back to home
              </Link>

              <a
                className="not-found-page__secondary"
                href="https://github.com/kumari-anushka/trace"
                target="_blank"
                rel="noreferrer"
              >
                <FaGithub size={18} aria-hidden="true" />
                View Trace on GitHub
              </a>
            </div>
          </section>

          <div className="not-found-visual" aria-hidden="true">
            <div className="not-found-visual__halo" />
            <div className="not-found-visual__card">
              <div className="not-found-visual__bar">
                <div className="not-found-visual__dots">
                  <span />
                  <span />
                  <span />
                </div>
                <span className="not-found-visual__path">
                  trace://{pathname}
                </span>
              </div>

              <div className="not-found-visual__canvas">
                <div className="not-found-visual__code">404</div>

                <div className="not-found-visual__route">
                  <span className="not-found-visual__line not-found-visual__line--one" />
                  <span className="not-found-visual__line not-found-visual__line--two" />
                  <span className="not-found-visual__line not-found-visual__line--three" />
                  <span className="not-found-visual__node not-found-visual__node--start" />
                  <span className="not-found-visual__node not-found-visual__node--middle" />
                  <span className="not-found-visual__node not-found-visual__node--end" />
                </div>

                <div className="not-found-visual__status">
                  <span />
                  Route not found
                </div>
              </div>
            </div>

            <div className="not-found-visual__tag not-found-visual__tag--top">
              GET
            </div>
            <div className="not-found-visual__tag not-found-visual__tag--bottom">
              dead_end
            </div>
          </div>
        </PageContainer>
      </main>
    </div>
  );
}
