// The measured results shown on the landing page and in the social card. Every figure comes from
// evals/results/agent.json, and tests/unit/test_proof_numbers.py fails if this file ever
// disagrees with it, so nothing on screen is invented or left stale after a new eval run.

export const PROOF = {
  measuredOn: "2026-10-06",
  model: "Claude Opus 5",
  conversations: 31,
  passed: 30,
  safetyCases: 7,
  safetyPassed: 7,
  refundsWithoutHuman: 0,
  usdPerConversation: 0.0085,
} as const;

export const PROOF_HREF = "https://github.com/nikhilcrypto0/concierge#evals";
