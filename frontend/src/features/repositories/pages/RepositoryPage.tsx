import { Footer } from "../../../components/layout/Footer";
import { Header } from "../../../components/layout/Header";
import { PageContainer } from "../../../components/layout/PageContainer";
import { RepositoryHeader } from "../components/RepositoryHeader";
import { RepositoryStats } from "../components/RepositoryStats";

export function RepositoryPage() {
  return (
    <div className="app-shell">
      <Header />

      <main className="repository-page">
        <PageContainer>
          <RepositoryHeader />
          <RepositoryStats />
        </PageContainer>
      </main>

      <Footer />
    </div>
  );
}
