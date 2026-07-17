export const JOBS_PER_PAGE = 7;

export function jobPageCount(total: number, pageSize = JOBS_PER_PAGE) {
  return Math.max(1, Math.ceil(total / pageSize));
}

export function clampJobPage(page: number, total: number, pageSize = JOBS_PER_PAGE) {
  return Math.min(Math.max(1, page), jobPageCount(total, pageSize));
}

export function paginateJobs<T>(items: T[], page: number, pageSize = JOBS_PER_PAGE) {
  const current = clampJobPage(page, items.length, pageSize);
  const start = (current - 1) * pageSize;
  return items.slice(start, start + pageSize);
}
