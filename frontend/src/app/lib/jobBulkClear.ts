export type JobClearScope =
  | { delete_all_imported: true }
  | { job_ids: number[] };

export type JobClearResult = {
  matched_count: number;
  cleared_count: number;
  cleared_job_ids: number[];
  preview: boolean;
  message: string;
};

type FetchLike = typeof fetch;

async function requestJobClear(
  apiBase: string,
  scope: JobClearScope,
  preview: boolean,
  fetchImpl: FetchLike = fetch,
): Promise<JobClearResult> {
  const response = await fetchImpl(`${apiBase}/api/jobs/bulk-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...scope, preview }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail ?? "清除岗位失败");
  return body as JobClearResult;
}

export function previewJobClear(
  apiBase: string,
  scope: JobClearScope,
  fetchImpl?: FetchLike,
) {
  return requestJobClear(apiBase, scope, true, fetchImpl);
}

export function executeJobClear(
  apiBase: string,
  scope: JobClearScope,
  fetchImpl?: FetchLike,
) {
  return requestJobClear(apiBase, scope, false, fetchImpl);
}

export async function restoreClearedJobs(
  apiBase: string,
  jobIds: number[],
  fetchImpl: FetchLike = fetch,
) {
  const response = await fetchImpl(`${apiBase}/api/jobs/bulk-restore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail ?? "恢复岗位失败");
  return body as {
    restored_count: number;
    restored_job_ids: number[];
    message: string;
  };
}
