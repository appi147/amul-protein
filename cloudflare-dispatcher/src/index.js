const GITHUB_API_VERSION = "2022-11-28";

async function dispatchWorkflow(env) {
  if (!env.GITHUB_TOKEN) {
    throw new Error("GITHUB_TOKEN Worker secret is not configured");
  }

  const url = new URL(
    `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPOSITORY}` +
      `/actions/workflows/${env.GITHUB_WORKFLOW}/dispatches`,
  );

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "User-Agent": "amul-github-dispatcher",
      "X-GitHub-Api-Version": GITHUB_API_VERSION,
    },
    body: JSON.stringify({ ref: env.GITHUB_REF }),
  });

  // GitHub returns 204 No Content when it accepts a workflow_dispatch event.
  if (response.status !== 204) {
    throw new Error(
      `GitHub workflow dispatch failed (${response.status}): ${await response.text()}`,
    );
  }

  console.log(
    `Dispatched ${env.GITHUB_OWNER}/${env.GITHUB_REPOSITORY}` +
      ` workflow ${env.GITHUB_WORKFLOW} on ${env.GITHUB_REF}`,
  );
}

export default {
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(dispatchWorkflow(env));
  },

  async fetch() {
    return new Response("Amul GitHub Actions dispatcher is running.", { status: 200 });
  },
};
