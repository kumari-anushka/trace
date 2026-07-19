import { RepositoryForm } from "../../features/repositories/components/RepositoryForm";
import { PageContainer } from "../layout/PageContainer";

export function Hero() {
  return (
    <section className="hero" id="generate-atlas">
      <PageContainer>
        <div className="hero__content">
          <div className="hero__badge">
            <span aria-hidden="true" />
            AI Software Intelligence
          </div>

          <h1 className="hero__title">
            Understand any GitHub
            <br />
            repository in <span>minutes.</span>
          </h1>

          <p className="hero__description">
            Trace turns public GitHub repositories into evidence-backed software
            atlases that explain architecture, code organization, contributors,
            history, and design decisions.
          </p>

          <RepositoryForm />

          <p className="hero__note">
            Works on any public repository · Evidence-frst · ~10 minute
            walkthrough
          </p>
        </div>
      </PageContainer>
    </section>
  );
}
