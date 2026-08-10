import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const repositoryId = "11111111-1111-4111-8111-111111111111";
const versionId = "22222222-2222-4222-8222-222222222222";

const repository = {
  id: repositoryId,
  github_id: 1,
  github_url: "https://github.com/example/trace",
  owner: "example",
  name: "trace",
  default_branch: "main",
  description: "Evidence-backed repository intelligence",
  language: "Python",
  stars_count: 10,
  forks_count: 2,
  open_issues_count: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

async function assertAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

async function assertNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

test("home exposes the primary action without accessibility violations", async ({
  page,
}) => {
  await page.route("**/api/repositories", async (route) => {
    await route.fulfill({ json: { repositories: [] } });
  });

  await page.goto("/");

  await expect(
    page.getByRole("heading", {
      name: "Understand any GitHub repository in minutes.",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate Atlas" }),
  ).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await assertAccessible(page);
});

test("Atlas overview stays focused on required snapshot facts", async ({
  page,
}) => {
  await page.route(`**/api/repositories/${repositoryId}`, async (route) => {
    await route.fulfill({ json: repository });
  });
  await page.route("**/api/repository-versions?**", async (route) => {
    await route.fulfill({
      json: [
        {
          id: versionId,
          repository_id: repositoryId,
          commit_sha: "a".repeat(40),
          branch: "main",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
  });
  await page.route(
    "**/api/repositories/*/versions/*/graph**",
    async (route) => {
      await route.fulfill({
        json: {
          repository_id: repositoryId,
          repository_version_id: versionId,
          node_count: 1,
          edge_count: 0,
          metric_count: 0,
          nodes_truncated: false,
          edges_truncated: false,
          metrics_truncated: false,
          nodes: [
            {
              id: "33333333-3333-4333-8333-333333333333",
              repository_id: repositoryId,
              repository_version_id: versionId,
              entity_type: "architecture_summary",
              canonical_key: "architecture-summary",
              name: "Repository architecture",
              description: "A bounded repository architecture summary.",
              knowledge_kind: "derived",
              confidence: 0.9,
              provenance: { component: "test" },
              metadata: { file_count: 24, entry_points: [], limitations: [] },
              ontology_version: "1.0",
            },
          ],
          edges: [],
          metrics: [],
        },
      });
    },
  );

  await page.goto(`/repositories/${repositoryId}/overview`);

  await expect(
    page.getByRole("heading", { name: "Software Atlas" }),
  ).toBeVisible();
  const facts = page.getByLabel("Atlas facts");
  await expect(facts.getByText("Source files", { exact: true })).toBeVisible();
  await expect(
    facts.getByText("Likely entry points", { exact: true }),
  ).toBeVisible();
  await expect(
    facts.getByText("Confirmed subsystems", { exact: true }),
  ).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await assertAccessible(page);
});

test("Ask returns only verified claims, cited sources, and limitations", async ({
  page,
}) => {
  await page.route(`**/api/repositories/${repositoryId}`, async (route) => {
    await route.fulfill({ json: repository });
  });
  await page.route(
    `**/api/repositories/${repositoryId}/query`,
    async (route) => {
      await route.fulfill({
        json: {
          repository_id: repositoryId,
          repository_version_id: versionId,
          question: "How is ingestion organized?",
          answer: "Ingestion runs as a bounded worker pipeline.",
          claims: [
            {
              text: "Ingestion runs as a bounded worker pipeline.",
              citation_ids: ["doc:worker"],
            },
          ],
          citations: [
            {
              id: "doc:worker",
              title: "Worker stages",
              source_type: "repository_documentation",
              source_url:
                "https://github.com/example/trace/blob/main/docs/ingestion.md",
              excerpt: "The worker advances through bounded, persisted stages.",
              retrieval_modes: ["metadata", "vector"],
            },
          ],
          limitations: ["The answer is limited to the selected snapshot."],
          retrieval_modes: ["metadata", "vector", "graph"],
          grounded: true,
        },
      });
    },
  );

  await page.goto(`/repositories/${repositoryId}/ask`);
  await page
    .getByRole("textbox", { name: "Ask a question about this repository" })
    .fill("How is ingestion organized?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(page.getByText("Sources checked")).toBeVisible();
  await expect(
    page.getByText("Ingestion runs as a bounded worker pipeline."),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Worker stages" }),
  ).toBeVisible();
  await expect(page.getByText("Limitations (1)")).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await assertAccessible(page);
});
