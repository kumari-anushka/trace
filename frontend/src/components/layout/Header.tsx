import { FaGithub } from "react-icons/fa";
import { Link } from "react-router-dom";

import { PageContainer } from "./PageContainer";

export function Header() {
  return (
    <header className="site-header">
      <PageContainer className="site-header__inner">
        <Link className="brand" to="/" aria-label="Trace home">
          <span className="brand__mark" aria-hidden="true">
            T
          </span>

          <span className="brand__name">Trace</span>
        </Link>

        <a
          className="header-link"
          href="https://github.com/kumari-anushka/trace"
          target="_blank"
          rel="noreferrer"
        >
          <FaGithub size={18} aria-hidden="true" />
          <span>GitHub</span>
        </a>
      </PageContainer>
    </header>
  );
}
