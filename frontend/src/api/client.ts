const API_URL = import.meta.env.VITE_API_URL;

export async function getRepositories() {
  const response = await fetch(`${API_URL}/repositories`);

  if (!response.ok) {
    throw new Error("Failed to fetch repositories");
  }

  return response.json();
}
