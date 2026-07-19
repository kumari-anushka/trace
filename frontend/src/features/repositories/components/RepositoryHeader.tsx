import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

export function RepositoryHeader() {
  const { repositoryId } = useParams();

  return (
    <>
      <Link className="repository-back" to="/">
        <ArrowLeft size={16} />
        Back
      </Link>

      <div className="repository-hero">
        <p className="repository-id">Repository #{repositoryId}</p>

        <h1>Software Atlas</h1>

        <p>Atlas generation begins here in Week 2.</p>
      </div>
    </>
  );
}
