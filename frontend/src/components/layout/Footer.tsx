import { Link } from "react-router-dom";

import { PageContainer } from "./PageContainer";

export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="footer">
      <PageContainer>
        <div className="footer__content">
          <Link className="footer__brand" to="/">
            <span className="footer__mark" aria-hidden="true">
              T
            </span>

            <span>Trace</span>
          </Link>

          <p className="footer__copyright">
            © {currentYear} Kumari Anushka. All rights reserved.
          </p>
        </div>
      </PageContainer>
    </footer>
  );
}
