import { useParams } from "react-router-dom";

export function RepositoryPage() {
  const { repositoryId } = useParams();

  return <main>Repository: {repositoryId}</main>;
}
