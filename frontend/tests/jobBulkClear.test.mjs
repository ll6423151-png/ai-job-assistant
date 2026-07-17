import assert from "node:assert/strict";
import test from "node:test";

import { executeJobClear, previewJobClear, restoreClearedJobs } from "../src/app/lib/jobBulkClear.ts";

test("bulk clear previews the exact backend scope before execution", async () => {
  const requests = [];
  const fetchImpl = async (_url, init) => {
    const payload = JSON.parse(init.body);
    requests.push(payload);
    return {
      ok: true,
      json: async () => payload.preview
        ? { matched_count: 13, cleared_count: 0, preview: true, message: "preview" }
        : { matched_count: 13, cleared_count: 13, cleared_job_ids: [1, 2], preview: false, message: "cleared" },
    };
  };

  const preview = await previewJobClear("", { delete_all_imported: true }, fetchImpl);
  assert.equal(preview.matched_count, 13);
  const result = await executeJobClear("", { delete_all_imported: true }, fetchImpl);
  assert.equal(result.cleared_count, 13);
  assert.deepEqual(requests, [
    { delete_all_imported: true, preview: true },
    { delete_all_imported: true, preview: false },
  ]);
});

test("cleared jobs can be restored through the tenant-scoped restore endpoint", async () => {
  const requests = [];
  const fetchImpl = async (url, init) => {
    requests.push({ url, payload: JSON.parse(init.body) });
    return {
      ok: true,
      json: async () => ({ restored_count: 2, restored_job_ids: [4, 8], message: "restored" }),
    };
  };

  const result = await restoreClearedJobs("", [4, 8], fetchImpl);
  assert.equal(result.restored_count, 2);
  assert.deepEqual(requests, [
    { url: "/api/jobs/bulk-restore", payload: { job_ids: [4, 8] } },
  ]);
});

test("selected clear keeps the selected ids in preview and execution", async () => {
  const requests = [];
  const fetchImpl = async (_url, init) => {
    const payload = JSON.parse(init.body);
    requests.push(payload);
    return {
      ok: true,
      json: async () => ({ matched_count: 2, cleared_count: payload.preview ? 0 : 2, preview: payload.preview, message: "ok" }),
    };
  };

  await previewJobClear("", { job_ids: [4, 8] }, fetchImpl);
  await executeJobClear("", { job_ids: [4, 8] }, fetchImpl);
  assert.deepEqual(requests, [
    { job_ids: [4, 8], preview: true },
    { job_ids: [4, 8], preview: false },
  ]);
});
