import assert from "node:assert/strict";
import test from "node:test";

import { clampJobPage, jobPageCount, paginateJobs } from "../src/app/lib/jobPagination.ts";

test("job results use seven items per page", () => {
  const jobs = Array.from({ length: 15 }, (_, index) => ({ id: index + 1 }));

  assert.equal(jobPageCount(7), 1);
  assert.equal(jobPageCount(8), 2);
  assert.deepEqual(paginateJobs(jobs, 1).map((job) => job.id), [1, 2, 3, 4, 5, 6, 7]);
  assert.deepEqual(paginateJobs(jobs, 2).map((job) => job.id), [8, 9, 10, 11, 12, 13, 14]);
  assert.deepEqual(paginateJobs(jobs, 3).map((job) => job.id), [15]);
});

test("current page is clamped after filtering or deletion", () => {
  assert.equal(clampJobPage(3, 6), 1);
  assert.equal(clampJobPage(0, 15), 1);
  assert.equal(clampJobPage(2, 15), 2);
});
