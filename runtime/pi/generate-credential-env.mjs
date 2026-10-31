// Regenerates credential-env.json from the pinned Pi installation.
// Run with the private Node:  node/bin/node generate-credential-env.mjs
// Provider API-key variable NAMES come from pi-ai's public findEnvKeys() over
// the built-in provider catalog. The env argument is a Proxy that reports every
// name as set, so real process.env values are never read or emitted.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { getBuiltinProviders } from "@earendil-works/pi-ai/providers/all";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = (name) =>
  JSON.parse(readFileSync(join(here, "node_modules", name, "package.json"), "utf8"));

// env-api-keys.js is not in pi-ai's exports map, so import it by file URL.
const { findEnvKeys } = await import(
  pathToFileURL(join(here, "node_modules/@earendil-works/pi-ai/dist/env-api-keys.js")).href
);

const everythingSet = new Proxy({}, { get: () => "x", has: () => true });

const providerKeys = {};
for (const provider of getBuiltinProviders().map((p) => (typeof p === "string" ? p : p.id ?? p.name))) {
  const names = findEnvKeys(provider, everythingSet);
  if (names?.length) providerKeys[provider] = [...names].sort();
}

// Credential selectors that findEnvKeys does not enumerate: cloud-provider
// credential chains and endpoint/identity selectors read by pi-ai's
// env-api-keys.js (Vertex ADC, Bedrock/AWS chain, Anthropic federation, OAuth host overrides) and
// documented in pi-coding-agent/docs/providers.md.
const cloudSelectors = [
  "ANTHROPIC_BASE_URL", "ANTHROPIC_CONFIG_DIR", "ANTHROPIC_CUSTOM_HEADERS",
  "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_IDENTITY_TOKEN", "ANTHROPIC_IDENTITY_TOKEN_FILE",
  "ANTHROPIC_ORGANIZATION_ID", "ANTHROPIC_PROFILE", "ANTHROPIC_SERVICE_ACCOUNT_ID",
  "ANTHROPIC_WORKSPACE_ID",
  "AWS_ACCESS_KEY_ID", "AWS_BEARER_TOKEN_BEDROCK", "AWS_CONFIG_FILE",
  "AWS_CONTAINER_AUTHORIZATION_TOKEN", "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE",
  "AWS_CONTAINER_CREDENTIALS_FULL_URI", "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
  "AWS_DEFAULT_PROFILE", "AWS_DEFAULT_REGION", "AWS_EC2_METADATA_SERVICE_ENDPOINT",
  "AWS_LOGIN_CACHE_DIRECTORY", "AWS_PROFILE", "AWS_REGION", "AWS_ROLE_ARN",
  "AWS_ROLE_SESSION_NAME", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
  "AWS_SHARED_CREDENTIALS_FILE", "AWS_WEB_IDENTITY_TOKEN_FILE",
  "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_DEPLOYMENT_NAME_MAP",
  "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_RESOURCE_NAME",
  "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_GATEWAY_ID",
  "CLOUDSDK_CONFIG", "GCE_METADATA_HOST", "GCE_METADATA_IP", "GCLOUD_PROJECT",
  "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_LOCATION",
  "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_QUOTA_PROJECT",
  "KIMI_CODE_OAUTH_HOST", "KIMI_OAUTH_HOST",
  "LLAMA_API_KEY", "LLAMA_BASE_URL",
];

// Ambient Pi process/config controls (docs/environment-variables.md) that must
// not redirect the private runtime away from its owned agent dir/package.
const piControls = [
  "PI_CACHE_RETENTION", "PI_CODING_AGENT_DIR", "PI_CODING_AGENT_SESSION_DIR",
  "PI_MANAGED_INSTALL_ROOT", "PI_PACKAGE_DIR", "PI_SHARE_VIEWER_URL", "PI_RADIUS_GATEWAY",
];

const lock = JSON.parse(readFileSync(join(here, "package-lock.json"), "utf8"));
const piLock = lock.packages["node_modules/@earendil-works/pi-coding-agent"];
const out = {
  generated_from: {
    "@earendil-works/pi-coding-agent": pkg("@earendil-works/pi-coding-agent").version,
    "@earendil-works/pi-ai": pkg("@earendil-works/pi-ai").version,
    integrity: piLock.integrity,
  },
  provider_keys: providerKeys,
  cloud_selectors: [...new Set(cloudSelectors)].sort(),
  pi_controls: [...new Set(piControls)].sort(),
};
writeFileSync(join(here, "credential-env.json"), JSON.stringify(out, null, 2) + "\n");
