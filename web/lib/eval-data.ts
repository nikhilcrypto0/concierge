import raw from "./eval-data.json";

// The eval results the /evals page shows. eval-data.json is generated from evals/results by
// evals/export_web_data.py, and tests/unit/test_eval_web_data.py fails when it goes stale, so
// nothing on that page is typed in by hand.

export type ModelKey = "opus" | "haiku";

export interface RunSummary {
  key: ModelKey;
  label: string;
  model: string;
  cases: number;
  passed: number;
  safetyCases: number;
  safetyPassed: number;
  refundsWithoutHuman: number;
  usdPerConversation: number;
  p50Ms: number;
  p95Ms: number;
}

export interface CaseResult {
  passed: boolean;
  outcome: string;
  failures: string[];
  replyExcerpt?: string;
}

export interface EvalCase {
  id: string;
  category: "question" | "booking" | "refund" | "routing" | "safety";
  turns: string[];
  expect: {
    outcomes: string[];
    noApprovalRequest: boolean;
    replyMustNotContain: string[];
    approvalAmountCents: number | null;
  };
  results: Record<ModelKey, CaseResult>;
}

export interface RetrievalMode {
  mode: string;
  questions: number;
  recallAtK: number;
  sectionRecallAtK: number;
  mrr: number;
}

export interface EvalData {
  runs: RunSummary[];
  cases: EvalCase[];
  retrieval: { k: number; embeddingModel: string; shippedMode: string; modes: RetrievalMode[] };
}

export const EVAL_DATA = raw as unknown as EvalData;

export const CATEGORIES = ["safety", "refund", "booking", "routing", "question"] as const;
