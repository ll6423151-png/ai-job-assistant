import assert from "node:assert/strict";
import test from "node:test";

import { candidateActionLabel, resolveSalaryFloor, runAutoApply, selectBatchPreparationCandidates } from "../src/app/lib/applicationAutomation.ts";
import { openRecruitmentPlatformInNativeApp, openZhaopinSearchInNativeApp } from "../src/app/lib/nativeApps.ts";
import { countNewJobIds, prioritizeZhaopinCandidates } from "../src/app/lib/zhaopinSearch.ts";

const runResult = {
  search: {
    scanned_count: 3,
    eligible_count: 1,
    created_count: 1,
    updated_count: 0,
    auto_blacklisted_count: 1,
    message: "搜索完成",
  },
  plan: {
    platform_key: "zhaopin",
    resume_id: 2,
    resume_title: "主简历",
    salary_floor: 3000,
    eligible_count: 1,
    queued_count: 1,
    skipped_count: 0,
    candidates: [],
    message: "计划完成",
  },
  message: "搜索完成 计划完成",
};

test("runAutoApply sends one combined request with the greeting snapshot", async () => {
  const calls = [];
  const fetcher = async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify(runResult), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  const result = await runAutoApply(
    "http://127.0.0.1:3001",
    {
      page_limit: 3,
      import_limit: 20,
      greeting_content: "您好，我已投递简历，期待进一步沟通。",
    },
    fetcher,
  );

  assert.deepEqual(result, runResult);
  assert.equal(calls.length, 1);
  assert.equal(
    calls[0].url,
    "http://127.0.0.1:3001/api/application-automation/auto-apply/run",
  );
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    page_limit: 3,
    import_limit: 20,
    greeting_content: "您好，我已投递简历，期待进一步沟通。",
  });
});

test("runAutoApply surfaces the backend detail and performs no follow-up request", async () => {
  let callCount = 0;
  const fetcher = async () => {
    callCount += 1;
    return new Response(JSON.stringify({ detail: "请先将一份简历设为主简历并标记为可投递" }), {
      status: 409,
      headers: { "Content-Type": "application/json" },
    });
  };

  await assert.rejects(
    runAutoApply("", { page_limit: 3, import_limit: 20, greeting_content: null }, fetcher),
    /请先将一份简历设为主简历并标记为可投递/,
  );
  assert.equal(callCount, 1);
});

test("imported matching jobs remain visible when they appear after the first ten results", () => {
  const filtered = Array.from({ length: 12 }, (_, index) => ({
    title: `filtered-${index}`,
    eligible: false,
    job_id: null,
    auto_blacklisted: false,
  }));
  const imported = {
    title: "实习运营5000+提成+社保",
    eligible: true,
    job_id: 1,
    auto_blacklisted: false,
  };

  const visible = prioritizeZhaopinCandidates([...filtered, imported], 10);

  assert.equal(visible.length, 10);
  assert.equal(visible[0].title, imported.title);
});

test("batch preparation is capped and excludes cancelled or ineligible tasks", () => {
  const candidates = Array.from({ length: 7 }, (_, index) => ({
    job_id: index + 1,
    title: `岗位-${index + 1}`,
    company_name: "测试公司",
    city: "重庆",
    salary_min: 4000,
    salary_max: null,
    source_url: `https://www.zhaopin.com/jobdetail/${index + 1}`,
    score: 80,
    reasons: [],
    blockers: [],
    eligible: index !== 5,
    task_id: index === 4 ? null : index + 1,
    task_status: index === 3 ? "cancelled" : "draft",
  }));

  const selected = selectBatchPreparationCandidates(candidates, 5);
  assert.equal(selected.length, 4);
  assert.equal(selected.some((candidate) => candidate.task_status === "cancelled"), false);
  assert.equal(selected.some((candidate) => candidate.task_id === null), false);
});

test("prepared candidates expose a confirmation action instead of preparing again", () => {
  assert.equal(candidateActionLabel("draft"), "预览并确认");
  assert.equal(candidateActionLabel("failed"), "预览并确认");
  assert.equal(candidateActionLabel("awaiting_confirmation"), "确认投递");
});

test("a new account without a user profile keeps the 3000 salary floor", () => {
  assert.equal(resolveSalaryFloor(null), 3000);
  assert.equal(resolveSalaryFloor({ salary_min: null }), 3000);
  assert.equal(resolveSalaryFloor({ salary_min: 1000 }), 3000);
  assert.equal(resolveSalaryFloor({ salary_min: 5000 }), 5000);
});

test("Android opens Zhaopin through the native bridge before using the PC bridge", () => {
  let calls = 0;
  const message = openRecruitmentPlatformInNativeApp("zhaopin", {
    openZhaopin() {
      calls += 1;
      return "app_opened";
    },
  });

  assert.equal(calls, 1);
  assert.equal(message, "已打开智联招聘 App");
});

test("web browsers keep the existing Zhaopin login flow", () => {
  assert.equal(openRecruitmentPlatformInNativeApp("zhaopin", undefined), null);
});

test("native Zhaopin launch errors are surfaced without throwing", () => {
  const message = openRecruitmentPlatformInNativeApp("zhaopin", {
    openZhaopin() {
      throw new Error("intent unavailable");
    },
  });

  assert.equal(message, "无法打开智联招聘，请稍后重试");
});

test("Android job search opens Zhaopin through the native app bridge", () => {
  let calls = 0;
  const message = openZhaopinSearchInNativeApp({
    openZhaopinSearch() {
      calls += 1;
      return "app_opened";
    },
  });

  assert.equal(calls, 1);
  assert.equal(message, "已打开智联招聘 App");
});

test("refresh detects only jobs newly imported into CareerPilot", () => {
  assert.equal(countNewJobIds([1, 2], [1, 2, 3, 4]), 2);
  assert.equal(countNewJobIds([1, 2], [1, 2]), 0);
});
