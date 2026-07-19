import { Hero } from "../components/home/Hero";
import { HomeFeatures } from "../components/home/HomeFeatures";
import { Footer } from "../components/layout/Footer";
import { Header } from "../components/layout/Header";
import { RepositorySection } from "../features/repositories/components/RepositorySection";

export function HomePage() {
  return (
    <div className="app-shell">
      <Header />

      <main>
        <Hero />
        <HomeFeatures />
        <RepositorySection />
      </main>

      <Footer />
    </div>
  );
}
