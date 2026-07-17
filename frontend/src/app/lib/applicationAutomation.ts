export type TaskStatus =
  | "draft"
  | "awaiting_login"
  | "awaiting_confirmation"
  | "submitting"
  | "submitted"
  | "verification_required"
  | "failed"
  | "cancelled";

export type AutoApplyCandidate = {
  job_id: number;
  title: string;
  company_name: string;
  city: string;
  salary_min: number | null;
  salary_max: number | null;
  source_url: string;
  score: number;
  reasons: string[];
  blockers: string[];
  eligible: boolean;
  task_id: number | null;
  task_status: TaskStatus | null;
};

export type AutoApplyPlan = {
  platform_key: "zhaopin";
  resume_id: number;
  resume_title: string;
  salary_floor: number;
  eligible_count: number;
  queued_count: number;
  skipped_count: number;
  candidates: AutoApplyCandidate[];
  message: string;
};

export type ZhaopinSearchImport = {
  scanned_count: number;
  eligible_count: number;
  created_count: number;
  updated_count: number;
  auto_blacklisted_count: number;
  message: string;
};

export type AutoApplyRun = {
  search: ZhaopinSearchImport;
  plan: AutoApplyPlan;
  message: string;
};

export type AutoApplyRunRequest = {
  page_limit: number;
  import_limit: number;
  greeting_content: string | null;
};

export const HARD_MINIMUM_SALARY = 3000;

export function resolveSalaryFloor(profile: { salary_min: number | null } | null | undefined) {
  return Math.max(HARD_MINIMUM_SALARY, profile?.salary_min ?? HARD_MINIMUM_SALARY);
}

export function selectBatchPreparationCandidates(
  candidates: AutoApplyCandidate[],
  limit = 5,
) {
  return candidates
    .filter((candidate) => candidate.eligible && candidate.task_id !== null && candidate.task_status !== "cancelled")
    .slice(0, limit);
}

export function candidateActionLabel(status: TaskStatus | null) {
  return status === "awaiting_confirmation" ? "确认投递" : "预览并确认";
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export async function runAutoApply(
  apiBase: string,
  request: AutoApplyRunRequest,
  fetcher: Fetcher = fetch,
): Promise<AutoApplyRun> {
  const response = await fetcher(
    `${apiBase}/api/application-automation/auto-apply/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? "智联搜索和待投递清单生成失败");
  }
  return response.json() as Promise<AutoApplyRun>;
}
