"use client";

import { AlertTriangle, ClipboardCopy, ExternalLink, LogIn, PlayCircle, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import {
  runAutoApply,
  candidateActionLabel,
  HARD_MINIMUM_SALARY,
  resolveSalaryFloor,
  selectBatchPreparationCandidates,
  type AutoApplyCandidate,
  type AutoApplyPlan,
  type TaskStatus,
  type ZhaopinSearchImport,
} from "../lib/applicationAutomation";
import { openRecruitmentPlatformInNativeApp } from "../lib/nativeApps";

type Platform = { key: "zhaopin"; name: string; description: string; login_url: string; capabilities: string[]; browser_bridge_available: boolean; daily_submission_limit: number; cooldown_seconds: number };
type Job = { id: number; title: string; company_name: string; city: string; source_url: string; source_platform: string; salary_min: number | null };
type Resume = { id: number; title: string };
type Greeting = { id: number; job_id: number; resume_id: number; status: "draft" | "approved"; content: string };
type UserProfile = { salary_min: number | null };
type BlacklistRule = { company_name: string; match_type: "exact" | "contains"; is_active: boolean };
type Task = {
  id: number; platform_key: Platform["key"]; job_id: number; resume_id: number; greeting_id: number | null;
  application_record_id: number | null; status: TaskStatus; job_title_snapshot: string; company_snapshot: string;
  job_url_snapshot: string; resume_title_snapshot: string; greeting_snapshot: string; confirmation_token: string;
  preview: Record<string, unknown>; external_result: Record<string, unknown>; confirmed_by_user: boolean;
  error_message: string; created_at: string; updated_at: string;
};
type LoginState = { status: "logged_in" | "logged_out" | "unknown" | "bridge_unavailable"; message: string; evidence: string[] };
type JobEntry = { title: string; company_name: string; city: string; salary_min: string; source_url: string };
type CommunicationResult = { requested?: boolean; status?: string; sent?: boolean; reason?: string };

const statusLabels: Record<TaskStatus, string> = {
  draft: "待准备", awaiting_login: "待登录", awaiting_confirmation: "可确认投递", submitting: "提交中",
  submitted: "已验证投递", verification_required: "需人工核验", failed: "失败", cancelled: "已取消",
};
const DEFAULT_GREETING = "您好，我已投递简历，对这个岗位很感兴趣，期待与您进一步沟通，谢谢！";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "请求失败");
  }
  return response.json() as Promise<T>;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function SubmissionAutomationPanel({ apiBase }: { apiBase: string }) {
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [greetings, setGreetings] = useState<Greeting[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState<Platform["key"]>("zhaopin");
  const [jobEntryMode, setJobEntryMode] = useState<"existing" | "new">("existing");
  const [newJob, setNewJob] = useState<JobEntry>({ title: "", company_name: "", city: "", salary_min: "", source_url: "" });
  const [jobId, setJobId] = useState("");
  const [resumeId, setResumeId] = useState("");
  const [greetingId, setGreetingId] = useState("");
  const [greetingContent, setGreetingContent] = useState(DEFAULT_GREETING);
  const [current, setCurrent] = useState<Task | null>(null);
  const [loginStates, setLoginStates] = useState<Partial<Record<Platform["key"], LoginState>>>({});
  const [confirmed, setConfirmed] = useState(false);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("正在读取投递执行数据...");
  const [salaryFloor, setSalaryFloor] = useState(HARD_MINIMUM_SALARY);
  const [blacklist, setBlacklist] = useState<BlacklistRule[]>([]);
  const [autoPlan, setAutoPlan] = useState<AutoApplyPlan | null>(null);
  const [searchImport, setSearchImport] = useState<ZhaopinSearchImport | null>(null);
  const [preparingTaskId, setPreparingTaskId] = useState<number | null>(null);
  const [preparingAll, setPreparingAll] = useState(false);

  async function fetchLoginState(platformKey: Platform["key"]) {
    return readJson<LoginState>(await fetch(
      `${apiBase}/api/application-automation/platforms/${platformKey}/login-status`,
      { cache: "no-store" },
    ));
  }

  async function loadData(selectTaskId?: number) {
    const [platformData, jobData, resumeData, taskData, profileData, blacklistData, greetingData] = await Promise.all([
      readJson<Platform[]>(await fetch(`${apiBase}/api/application-automation/platforms`, { cache: "no-store" })),
      readJson<Job[]>(await fetch(`${apiBase}/api/jobs?include_blacklisted=true`, { cache: "no-store" })),
      readJson<Resume[]>(await fetch(`${apiBase}/api/resumes`, { cache: "no-store" })),
      readJson<Task[]>(await fetch(`${apiBase}/api/application-automation/tasks`, { cache: "no-store" })),
      readJson<UserProfile | null>(await fetch(`${apiBase}/api/user-profile`, { cache: "no-store" })),
      readJson<BlacklistRule[]>(await fetch(`${apiBase}/api/blacklist`, { cache: "no-store" })),
      readJson<Greeting[]>(await fetch(`${apiBase}/api/greetings`, { cache: "no-store" })),
    ]);
    setPlatforms(platformData); setJobs(jobData); setResumes(resumeData); setTasks(taskData); setGreetings(greetingData);
    setSalaryFloor(resolveSalaryFloor(profileData));
    setBlacklist(blacklistData);
    const loginEntries = await Promise.all(platformData.map(async (platform) => {
      try {
        return [platform.key, await fetchLoginState(platform.key)] as const;
      } catch (error) {
        return [platform.key, {
          status: "bridge_unavailable" as const,
          message: error instanceof Error ? error.message : "智联连接检查失败",
          evidence: [],
        }] as const;
      }
    }));
    setLoginStates(Object.fromEntries(loginEntries));
    setResumeId((value) => value || String(resumeData[0]?.id ?? ""));
    if (selectTaskId) setCurrent(taskData.find((task) => task.id === selectTaskId) ?? null);
    setMessage("投递执行数据已更新");
  }

  useEffect(() => { loadData().catch((error: unknown) => setMessage(error instanceof Error ? error.message : "加载失败")); }, [apiBase]);

  async function openLogin(platformKey: Platform["key"]) {
    const nativeMessage = openRecruitmentPlatformInNativeApp(platformKey);
    if (nativeMessage) {
      setMessage(nativeMessage);
      return;
    }
    setWorking(true); setMessage("正在打开平台登录页...");
    try {
      const result = await readJson<LoginState>(await fetch(`${apiBase}/api/application-automation/platforms/${platformKey}/open-login`, { method: "POST" }));
      setLoginStates((states) => ({ ...states, [platformKey]: result })); setMessage(result.message);
    } catch (error) { setMessage(error instanceof Error ? error.message : "无法打开登录页"); } finally { setWorking(false); }
  }

  async function checkLogin(platformKey: Platform["key"]) {
    setWorking(true);
    try {
      const result = await fetchLoginState(platformKey);
      setLoginStates((states) => ({ ...states, [platformKey]: result })); setMessage(result.message);
    } catch (error) { setMessage(error instanceof Error ? error.message : "登录检查失败"); } finally { setWorking(false); }
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setWorking(true); setMessage("正在创建投递任务...");
    try {
      const task = await readJson<Task>(await fetch(`${apiBase}/api/application-automation/tasks`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          platform_key: selectedPlatform,
          job_id: Number(jobId),
          resume_id: Number(resumeId),
          greeting_id: greetingId ? Number(greetingId) : null,
          greeting_content: greetingId ? null : greetingContent.trim() || null,
        }),
      }));
      setCurrent(task); setConfirmed(false); await loadData(task.id); setMessage("任务已创建，请准备页面预览");
    } catch (error) { setMessage(error instanceof Error ? error.message : "创建任务失败"); } finally { setWorking(false); }
  }

  async function saveNewJob() {
    const salary = Number(newJob.salary_min);
    if (!newJob.title.trim() || !newJob.company_name.trim() || !newJob.source_url.trim() || !Number.isFinite(salary)) {
      setMessage("请填写岗位名称、公司、最低月薪和智联招聘链接");
      return;
    }
    setWorking(true);
    setMessage("正在保存真实岗位...");
    try {
      const job = await readJson<Job>(await fetch(`${apiBase}/api/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newJob.title.trim(),
          company_name: newJob.company_name.trim(),
          city: newJob.city.trim(),
          salary_min: salary,
          salary_max: null,
          degree_required: "",
          experience_required: "",
          company_size: "",
          description: "",
          source_platform: "智联招聘",
          source_url: newJob.source_url.trim(),
          status: "open",
        }),
      }));
      await loadData();
      setJobId(String(job.id));
      setGreetingId("");
      setJobEntryMode("existing");
      setMessage("真实岗位已保存并选中");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存岗位失败");
    } finally {
      setWorking(false);
    }
  }

  async function startAutoApplyPlan() {
    setWorking(true);
    setMessage("正在搜索智联官网、导入 JD 并匹配岗位...");
    try {
      const result = await runAutoApply(apiBase, {
        page_limit: 3,
        import_limit: 20,
        greeting_content: greetingContent.trim() || null,
      });
      const { search: imported, plan } = result;
      setSearchImport(imported);
      setAutoPlan(plan);
      const firstTaskId = plan.candidates.find((candidate) => candidate.eligible && candidate.task_id)?.task_id;
      await loadData(firstTaskId ?? undefined);
      setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "智联搜索和待投递清单生成失败");
    } finally {
      setWorking(false);
    }
  }

  async function cancelPlannedTask(candidate: AutoApplyCandidate) {
    if (!candidate.task_id || candidate.task_status === "cancelled") return;
    setWorking(true);
    setMessage(`正在排除：${candidate.title}`);
    try {
      const task = await readJson<Task>(await fetch(`${apiBase}/api/application-automation/tasks/${candidate.task_id}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "用户在即将投递列表中勾选不投递" }),
      }));
      setAutoPlan((plan) => plan ? {
        ...plan,
        candidates: plan.candidates.map((item) => item.task_id === task.id ? { ...item, task_status: task.status } : item),
      } : plan);
      if (current?.id === task.id) setCurrent(task);
      await loadData(task.id);
      setMessage("该岗位已从本轮投递中排除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "排除岗位失败");
    } finally {
      setWorking(false);
    }
  }

  async function prepareTaskById(taskId: number) {
    setPreparingTaskId(taskId); setWorking(true); setMessage("正在打开岗位页面并生成投递预览...");
    try {
      const task = await readJson<Task>(await fetch(`${apiBase}/api/application-automation/tasks/${taskId}/prepare`, { method: "POST" }));
      setCurrent(task); setConfirmed(false); await loadData(task.id);
      setAutoPlan((plan) => plan ? {
        ...plan,
        candidates: plan.candidates.map((item) => item.task_id === task.id ? { ...item, task_status: task.status } : item),
      } : plan);
      setMessage(task.status === "awaiting_confirmation" ? "预览已生成，请逐项核对" : task.error_message || "任务状态已更新");
    } catch (error) { setMessage(error instanceof Error ? error.message : "准备任务失败"); } finally { setPreparingTaskId(null); setWorking(false); }
  }

  async function prepareTask() {
    if (!current) return;
    await prepareTaskById(current.id);
  }

  async function preparePlannedTasks() {
    if (!autoPlan) return;
    const candidates = selectBatchPreparationCandidates(autoPlan.candidates, 5);
    if (!candidates.length) {
      setMessage("当前没有可批量准备的岗位");
      return;
    }
    setPreparingAll(true); setWorking(true);
    setMessage(`正在准备前 ${candidates.length} 个岗位预览，不会执行最终投递...`);
    let preparedCount = 0;
    let failedCount = 0;
    let firstTask: Task | null = null;
    const statusByTask = new Map<number, TaskStatus>();
    try {
      for (const candidate of candidates) {
        try {
          const task = await readJson<Task>(await fetch(`${apiBase}/api/application-automation/tasks/${candidate.task_id}/prepare`, { method: "POST" }));
          statusByTask.set(task.id, task.status);
          if (task.status === "awaiting_confirmation") preparedCount += 1;
          else failedCount += 1;
          firstTask ??= task;
        } catch {
          failedCount += 1;
          if (candidate.task_id) statusByTask.set(candidate.task_id, "failed");
        }
      }
      setAutoPlan((plan) => plan ? {
        ...plan,
        candidates: plan.candidates.map((candidate) => candidate.task_id && statusByTask.has(candidate.task_id)
          ? { ...candidate, task_status: statusByTask.get(candidate.task_id) ?? candidate.task_status }
          : candidate),
      } : plan);
      if (firstTask) {
        setCurrent(firstTask);
        setConfirmed(false);
        await loadData(firstTask.id);
      } else {
        await loadData();
      }
      setMessage(`已准备 ${preparedCount} 个岗位预览，${failedCount} 个需要人工处理；最终投递仍需逐条确认`);
    } finally {
      setPreparingAll(false); setWorking(false);
    }
  }

  function openCandidateAction(candidate: AutoApplyCandidate) {
    if (!candidate.task_id) return;
    if (candidate.task_status === "awaiting_confirmation") {
      const task = tasks.find((item) => item.id === candidate.task_id);
      if (task) {
        setCurrent(task);
        setConfirmed(false);
        setMessage("已打开该岗位确认区，请核对后确认投递");
        return;
      }
    }
    void prepareTaskById(candidate.task_id);
  }

  async function submitTask() {
    if (!current || !confirmed) return; setWorking(true); setMessage("正在执行本次外部投递，请勿重复点击...");
    try {
      const task = await readJson<Task>(await fetch(`${apiBase}/api/application-automation/tasks/${current.id}/submit`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed: true, confirmation_token: current.confirmation_token }),
      }));
      setCurrent(task); setConfirmed(false); await loadData(task.id);
      const communication = (task.external_result.communication ?? {}) as CommunicationResult;
      if (task.status === "submitted" && communication.status === "sent") setMessage("投递成功，沟通内容已发送给 HR");
      else if (task.status === "submitted" && communication.status === "manual_required") setMessage(communication.reason || "投递成功，沟通内容需要在智联 APP 手动发送");
      else setMessage(task.status === "submitted" ? "平台已显示投递成功" : task.error_message || "投递操作已完成");
    } catch (error) { setMessage(error instanceof Error ? error.message : "投递执行失败"); } finally { setWorking(false); }
  }

  async function copyGreeting(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setMessage("沟通内容已复制");
    } catch {
      setMessage("浏览器未允许复制，请手动选择沟通内容");
    }
  }

  const selectedPlatformInfo = platforms.find((platform) => platform.key === selectedPlatform);
  const isBlacklisted = (companyName: string) => blacklist.some((rule) => {
    if (!rule.is_active) return false;
    const company = companyName.trim().toLocaleLowerCase();
    const blocked = rule.company_name.trim().toLocaleLowerCase();
    return rule.match_type === "contains" ? company.includes(blocked) : company === blocked;
  });
  const validJobs = jobs.filter((job) => {
    try {
      const host = new URL(job.source_url).hostname;
      const platformMatches = host === "zhaopin.com" || host.endsWith(".zhaopin.com");
      return platformMatches && !isBlacklisted(job.company_name) && job.salary_min !== null && job.salary_min >= salaryFloor;
    }
    catch { return false; }
  });
  const approvedGreetings = greetings.filter((greeting) =>
    greeting.status === "approved"
    && (!jobId || greeting.job_id === Number(jobId))
    && (!resumeId || greeting.resume_id === Number(resumeId))
  );

  return <section>
    <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><h2 className="text-xl font-semibold">投递执行</h2><p className="mt-1 text-sm text-muted">当前仅连接智联招聘，读取已登录页面并在逐条确认后点击投递入口。</p></div><span className="text-xs text-muted" aria-live="polite">{message}</span></div>
    <div className="automation-risk-banner"><AlertTriangle size={18} /><span>平台可能检测浏览器自动化。登录、验证码和最终投递确认均由你控制，请勿进行高频批量操作。</span></div>
    <div className="mt-6 grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
      <aside><h3 className="text-sm font-semibold">平台连接</h3><div className="mt-3 divide-y divide-slate-200 border-y border-slate-200">
        {platforms.map((platform) => { const login = loginStates[platform.key]; return <div key={platform.key} className={`automation-platform ${selectedPlatform === platform.key ? "automation-platform-active" : ""}`}>
          <button type="button" onClick={() => setSelectedPlatform(platform.key)}><strong>{platform.name}</strong><span>{platform.description}</span></button>
          <div className="mt-3 flex flex-wrap gap-2"><button type="button" className="button-secondary compact-button icon-text-button" disabled={working} onClick={() => void openLogin(platform.key)}><LogIn size={14} />打开登录</button><button type="button" className="button-secondary compact-button icon-text-button" disabled={working} onClick={() => void checkLogin(platform.key)}><RefreshCw size={14} />检查状态</button></div>
          <small className={`automation-login automation-login-${login?.status ?? "unknown"}`}>{login?.message ?? (platform.browser_bridge_available ? "等待登录检查" : "浏览器桥接未连接")}</small>
        </div>; })}
      </div></aside>
      <div className="min-w-0">
        <section className="mb-6 border-y border-slate-200 py-5">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div>
              <h3 className="text-base font-semibold">自动查找匹配岗位</h3>
              <p className="mt-1 text-sm text-muted">按用户中心搜索智联官网、读取必要 JD，并用可投递主简历生成逐条确认清单。</p>
            </div>
            <button type="button" className="button-primary icon-text-button" disabled={working} onClick={() => void startAutoApplyPlan()}><PlayCircle size={16} />搜索并生成清单</button>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,260px)_minmax(0,1fr)]">
            <label className="field-label"><span>已审核沟通内容</span><select value={greetingId} onChange={(event) => { const value = event.target.value; setGreetingId(value); const selected = greetings.find((item) => item.id === Number(value)); if (selected) setGreetingContent(selected.content); }}><option value="">自定义内容</option>{approvedGreetings.map((greeting) => <option key={greeting.id} value={greeting.id}>已定稿 #{greeting.id}</option>)}</select></label>
            <label className="field-label"><span>投递后发送给 HR</span><textarea rows={3} value={greetingContent} onChange={(event) => { setGreetingId(""); setGreetingContent(event.target.value); }} maxLength={1000} /><small>随每条任务保存；投递成功后尝试发送。智联 PC 无输入框时可直接复制到 APP。</small></label>
          </div>
          {autoPlan && <div className="mt-5">
            {searchImport && <p className="mb-3 text-xs text-muted">官网扫描 {searchImport.scanned_count} 个，符合 {searchImport.eligible_count} 个，新建 {searchImport.created_count} 个，更新 {searchImport.updated_count} 个，自动拉黑 {searchImport.auto_blacklisted_count} 家。</p>}
            <div className="automation-summary"><div><span>使用简历</span><strong>{autoPlan.resume_title}</strong></div><div><span>符合条件</span><strong>{autoPlan.eligible_count} 个岗位</strong></div><div><span>本次新建</span><strong>{autoPlan.queued_count} 个待投递任务</strong></div></div>
            <div className="mt-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><h4 className="text-sm font-semibold">即将投递</h4><span className="text-xs text-muted">官网筛除 {searchImport ? Math.max(0, searchImport.scanned_count - searchImport.eligible_count) : 0} 个；本地跳过 {autoPlan.skipped_count} 个</span></div><button type="button" className="button-secondary compact-button icon-text-button" disabled={working || !autoPlan.eligible_count} onClick={() => void preparePlannedTasks()}><RefreshCw size={14} />批量准备预览（最多 5 条）</button></div>
            <div className="mt-2 divide-y divide-slate-200 border-y border-slate-200">
              {autoPlan.candidates.filter((candidate) => candidate.eligible).map((candidate) => {
                const cancelled = candidate.task_status === "cancelled";
                return <article key={candidate.job_id} className="py-4">
                  <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                    <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><strong className="text-sm">{candidate.title}</strong><span className={`automation-task-status automation-task-status-${candidate.task_status ?? "draft"}`}>{candidate.task_status ? statusLabels[candidate.task_status] : "待准备"} · 规则 {candidate.score} 分</span></div><p className="mt-1 text-xs text-muted">{candidate.company_name || "公司未填写"} · {candidate.city || "城市未填写"} · {candidate.salary_min ?? "薪资未知"}{candidate.salary_max ? `-${candidate.salary_max}` : ""} 元/月</p><p className="mt-2 text-xs leading-5 text-muted">{candidate.reasons.join("；") || "已通过硬性规则检查"}</p></div>
                    <div className="flex shrink-0 flex-wrap items-center gap-2"><label className="confirmation-row compact-button"><input type="checkbox" checked={cancelled} disabled={working || cancelled} onChange={() => void cancelPlannedTask(candidate)} /><span>{cancelled ? "已排除" : "不投递"}</span></label><button type="button" className="button-primary compact-button icon-text-button" disabled={preparingAll || preparingTaskId === candidate.task_id || cancelled || !candidate.task_id} onClick={() => openCandidateAction(candidate)}><Send size={14} />{preparingTaskId === candidate.task_id ? "正在准备" : candidateActionLabel(candidate.task_status)}</button></div>
                  </div>
                </article>;
              })}
              {!autoPlan.eligible_count && <div className="py-6 text-sm text-muted">当前已导入岗位中没有同时满足用户信息、薪资和 JD 条件的岗位。</div>}
            </div>
          </div>}
        </section>
        <form onSubmit={createTask} className="space-y-5">
          <div className="automation-summary"><div><span>当前平台</span><strong>{selectedPlatformInfo?.name ?? "加载中"}</strong></div><div><span>最低月薪</span><strong>{salaryFloor} 元</strong></div><div><span>提交保护</span><strong>{selectedPlatformInfo ? `${selectedPlatformInfo.daily_submission_limit} 次/日 · 间隔 ${selectedPlatformInfo.cooldown_seconds} 秒` : "加载中"}</strong></div></div>
          <div className="border-y border-slate-200 py-4"><div className="flex flex-wrap items-center justify-between gap-3"><span className="text-sm font-semibold">岗位来源</span><div className="flex gap-2"><button type="button" className={jobEntryMode === "existing" ? "button-primary compact-button" : "button-secondary compact-button"} onClick={() => setJobEntryMode("existing")}>选择已保存岗位</button><button type="button" className={jobEntryMode === "new" ? "button-primary compact-button" : "button-secondary compact-button"} onClick={() => setJobEntryMode("new")}>录入真实岗位</button></div></div>{jobEntryMode === "existing" ? <label className="field-label mt-4"><span>真实岗位链接 *</span><select required value={jobId} onChange={(event) => { setJobId(event.target.value); setGreetingId(""); }}><option value="">请选择已保存岗位</option>{validJobs.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company_name || "公司未填写"} · {job.salary_min}元起</option>)}</select><small>{validJobs.length ? `仅显示智联链接、非黑名单且月薪下限不低于 ${salaryFloor} 元的岗位。` : `当前没有满足智联链接、黑名单和最低月薪 ${salaryFloor} 元要求的岗位。`}</small></label> : <div className="mt-4 grid gap-4 sm:grid-cols-2"><label className="field-label"><span>岗位名称 *</span><input value={newJob.title} onChange={(event) => setNewJob((current) => ({ ...current, title: event.target.value }))} placeholder="例如：线下直播运营助理" /></label><label className="field-label"><span>公司名称 *</span><input value={newJob.company_name} onChange={(event) => setNewJob((current) => ({ ...current, company_name: event.target.value }))} placeholder="例如：重庆星创无限文化传媒有限公司" /></label><label className="field-label"><span>城市</span><input value={newJob.city} onChange={(event) => setNewJob((current) => ({ ...current, city: event.target.value }))} placeholder="例如：重庆两江新区" /></label><label className="field-label"><span>最低月薪 *</span><input type="number" min={HARD_MINIMUM_SALARY} value={newJob.salary_min} onChange={(event) => setNewJob((current) => ({ ...current, salary_min: event.target.value }))} placeholder={`${salaryFloor}`} /></label><label className="field-label sm:col-span-2"><span>智联招聘真实岗位链接 *</span><input type="url" value={newJob.source_url} onChange={(event) => setNewJob((current) => ({ ...current, source_url: event.target.value }))} placeholder="https://www.zhaopin.com/jobdetail/..." /><small>保存后会自动选中，随后才能创建投递任务。</small></label><div className="flex justify-end sm:col-span-2"><button type="button" className="button-secondary" disabled={working} onClick={() => void saveNewJob()}>保存并选中岗位</button></div></div>}</div>
          <div className="grid gap-4 sm:grid-cols-2"><label className="field-label"><span>投递简历 *</span><select required value={resumeId} onChange={(event) => { setResumeId(event.target.value); setGreetingId(""); }}><option value="">请选择简历</option>{resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.title}</option>)}</select><small>智联弹出简历选择框时按名称选择；若官网直接投递，将使用智联默认简历。</small></label><div className="field-label"><span>沟通内容状态</span><div className="min-h-[43px] border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-normal text-muted">{greetingContent.trim() ? "已加入任务，投递成功后发送" : "未设置"}</div></div></div>
          <div className="flex justify-end border-t border-slate-200 pt-4"><button type="submit" className="button-primary" disabled={working || !jobId || !resumeId}>创建投递任务</button></div>
        </form>
        <div className="mt-7 grid gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
          <div className="border-y border-slate-200 lg:border-y-0 lg:border-r lg:pr-5"><h3 className="pb-3 text-sm font-semibold">任务记录 ({tasks.length})</h3><div className="divide-y divide-slate-200">{tasks.map((task) => <button key={task.id} type="button" className={`automation-task-row ${current?.id === task.id ? "automation-task-row-active" : ""}`} onClick={() => { setCurrent(task); setConfirmed(false); }}><span><strong>{task.job_title_snapshot}</strong><small>{task.company_snapshot || "公司未填写"}</small></span><em className={`automation-task-status automation-task-status-${task.status}`}>{statusLabels[task.status]}</em></button>)}{!tasks.length && <p className="py-6 text-sm text-muted">还没有投递任务。</p>}</div></div>
          {current ? <article><div className="flex flex-col justify-between gap-3 border-b border-slate-200 pb-4 sm:flex-row"><div><span className="text-xs text-muted">任务 #{current.id} · {formatDate(current.updated_at)}</span><h3 className="mt-1 text-base font-semibold">{current.job_title_snapshot}</h3><p className="mt-1 text-xs text-muted">{current.company_snapshot || "公司未填写"} · {current.resume_title_snapshot}</p></div><span className={`automation-task-status automation-task-status-${current.status}`}>{statusLabels[current.status]}</span></div>
            <a className="mt-4 inline-flex items-center gap-1 text-sm text-brand" href={current.job_url_snapshot} target="_blank" rel="noreferrer"><ExternalLink size={14} />查看岗位原页</a>
            {current.error_message && <div className={`check-result ${current.status === "submitted" ? "check-result-warning" : "check-result-blocked"} mt-4`}>{current.error_message}</div>}
            {Object.keys(current.preview).length > 0 && <dl className="automation-preview mt-4"><div><dt>页面标题</dt><dd>{String(current.preview.page_title ?? "未读取")}</dd></div><div><dt>登录状态</dt><dd>{String(current.preview.login_status ?? "unknown")}</dd></div><div><dt>投递入口</dt><dd>{Array.isArray(current.preview.apply_controls) ? current.preview.apply_controls.map((item) => String((item as { text?: string }).text ?? "")).join(" / ") : "未找到"}</dd></div><div><dt>沟通内容快照</dt><dd>{current.greeting_snapshot || "未关联"}</dd></div></dl>}
            {current.greeting_snapshot && <div className="mt-4 border-y border-slate-200 py-4"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-sm">投递后沟通</strong><button type="button" className="button-secondary compact-button icon-text-button" onClick={() => void copyGreeting(current.greeting_snapshot)}><ClipboardCopy size={14} />复制内容</button></div><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted">{current.greeting_snapshot}</p>{(() => { const communication = (current.external_result.communication ?? {}) as CommunicationResult; if (!communication.status || communication.status === "not_requested") return null; const labels: Record<string, string> = { sent: "已发送给 HR", manual_required: "需在智联 APP 手动发送", verification_required: "发送结果待核验", awaiting_application_verification: "等待投递成功核验" }; return <p className={`mt-2 text-xs ${communication.status === "sent" ? "text-emerald-700" : "text-amber-700"}`}>{labels[communication.status] ?? communication.status}{communication.reason ? `：${communication.reason}` : ""}</p>; })()}</div>}
            {["draft", "awaiting_login", "failed"].includes(current.status) && <div className="mt-5 flex justify-end"><button type="button" className="button-primary icon-text-button" disabled={working} onClick={() => void prepareTask()}><RefreshCw size={15} />准备并预览</button></div>}
            {current.status === "awaiting_confirmation" && <div className="mt-5 border-t border-slate-200 pt-5"><label className="confirmation-row"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>我已核对平台、公司、岗位、简历和沟通内容，确认执行这一条外部投递。</span></label><div className="mt-3 flex justify-end"><button type="button" className="button-primary icon-text-button" disabled={!confirmed || working} onClick={() => void submitTask()}><Send size={15} />确认并投递</button></div></div>}
            {current.status === "submitted" && <div className="check-result check-result-clear mt-5"><ShieldCheck size={18} /><strong>平台页面已显示成功标识</strong></div>}
            {current.status === "verification_required" && <div className="check-result check-result-blocked mt-5"><AlertTriangle size={18} /><strong>已执行点击，但平台未返回明确成功标识，请打开原页核验。</strong></div>}
          </article> : <div className="empty-panel">选择任务查看预览和执行状态。</div>}
        </div>
      </div>
    </div>
  </section>;
}
