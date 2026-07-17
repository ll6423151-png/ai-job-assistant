"use client";

import { ChevronLeft, ChevronRight, ExternalLink, RefreshCw, Search, Star, Trash2, Undo2 } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { clampJobPage, jobPageCount, paginateJobs } from "../lib/jobPagination";
import { executeJobClear, JobClearScope, previewJobClear, restoreClearedJobs } from "../lib/jobBulkClear";
import { countNewJobIds, prioritizeZhaopinCandidates } from "../lib/zhaopinSearch";
import { openZhaopinSearchInNativeApp } from "../lib/nativeApps";

type Job = {
  id: number;
  title: string;
  company_name: string;
  city: string;
  salary_min: number | null;
  salary_max: number | null;
  degree_required: string;
  experience_required: string;
  company_size: string;
  description: string;
  source_platform: string;
  source_url: string;
  status: "open" | "closed";
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
};

type JobForm = Omit<Job, "id" | "created_at" | "updated_at">;

type JobFilters = {
  keyword: string;
  city: string;
  salary_min: string;
  salary_max: string;
  degree: string;
  experience: string;
  company_size: string;
  favorite_only: string;
};

type ZhaopinSearchCandidate = {
  title: string; company_name: string; city: string; salary_text: string; source_url: string;
  eligible: boolean; score: number; reasons: string[]; blockers: string[]; job_id: number | null;
  description_loaded: boolean; auto_blacklisted: boolean; import_action: "created" | "updated" | null;
};

type ZhaopinSearchResult = {
  query: string; search_url: string; scanned_count: number; eligible_count: number;
  created_count: number; updated_count: number; auto_blacklisted_count: number; history_skipped_count: number;
  search_signature: string; candidates: ZhaopinSearchCandidate[]; message: string;
};

const emptyJob: JobForm = {
  title: "",
  company_name: "",
  city: "",
  salary_min: null,
  salary_max: null,
  degree_required: "不限",
  experience_required: "不限",
  company_size: "不限",
  description: "",
  source_platform: "手动录入",
  source_url: "",
  status: "open",
  is_favorite: false,
};

const emptyFilters: JobFilters = {
  keyword: "",
  city: "",
  salary_min: "",
  salary_max: "",
  degree: "",
  experience: "",
  company_size: "",
  favorite_only: "",
};

function jobToForm(job: Job): JobForm {
  const { id: _id, created_at: _createdAt, updated_at: _updatedAt, ...form } = job;
  return form;
}

function formatSalary(min: number | null, max: number | null) {
  if (min === null && max === null) return "薪资面议";
  if (min !== null && max !== null) return `${min}-${max} 元/月`;
  return min !== null ? `${min} 元/月起` : `最高 ${max} 元/月`;
}

function isImportedJob(job: Job) {
  return job.source_platform === "智联招聘" || job.source_url.includes("zhaopin.com/");
}

export function JobSearchPanel({ apiBase }: { apiBase: string }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [filters, setFilters] = useState<JobFilters>(emptyFilters);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<JobForm>(emptyJob);
  const [editorOpen, setEditorOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("正在读取岗位...");
  const [zhaopinResult, setZhaopinResult] = useState<ZhaopinSearchResult | null>(null);
  const [isAndroidApp, setIsAndroidApp] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedJobIds, setSelectedJobIds] = useState<Set<number>>(new Set());
  const [lastClearedJobIds, setLastClearedJobIds] = useState<number[]>([]);
  const knownJobIds = useRef<Set<number>>(new Set());
  const searchStartJobIds = useRef<Set<number> | null>(null);

  async function loadJobs(nextFilters: JobFilters, selectId?: number | null) {
    const params = new URLSearchParams();
    Object.entries(nextFilters).forEach(([key, value]) => {
      if (value.trim()) params.set(key, value.trim());
    });
    const query = params.toString();
    const response = await fetch(`${apiBase}/api/jobs${query ? `?${query}` : ""}`, { cache: "no-store" });
    if (!response.ok) throw new Error("无法读取岗位列表");
    const nextJobs = (await response.json()) as Job[];
    setJobs(nextJobs);
    const nextIds = new Set(nextJobs.map((job) => job.id));
    setSelectedJobIds((current) => new Set([...current].filter((id) => nextIds.has(id))));
    setCurrentPage((current) => clampJobPage(current, nextJobs.length));
    nextJobs.forEach((job) => knownJobIds.current.add(job.id));

    if (selectId !== undefined) {
      const selected = nextJobs.find((job) => job.id === selectId);
      setSelectedId(selected?.id ?? null);
      if (selected) setForm(jobToForm(selected));
    }
    return nextJobs;
  }

  useEffect(() => {
    setIsAndroidApp(Boolean(window.CareerPilotNativeApps?.openZhaopinSearch));
    loadJobs(emptyFilters)
      .then((items) => setMessage(`已加载 ${items.length} 个岗位`))
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [apiBase]);

  function updateFilter(field: keyof JobFilters, value: string) {
    setFilters((current) => ({ ...current, [field]: value }));
  }

  function updateField<K extends keyof JobForm>(field: K, value: JobForm[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function searchJobs(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setLoading(true);
    setMessage("正在筛选...");
    try {
      setCurrentPage(1);
      const items = await loadJobs(filters);
      setMessage(`找到 ${items.length} 个岗位`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "筛选失败");
    } finally {
      setLoading(false);
    }
  }

  async function resetFilters() {
    setFilters(emptyFilters);
    setCurrentPage(1);
    setLoading(true);
    try {
      const items = await loadJobs(emptyFilters);
      setMessage(`已显示全部 ${items.length} 个岗位`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function searchAndImportZhaopin() {
    if (isAndroidApp) {
      const nativeMessage = openZhaopinSearchInNativeApp();
      setMessage(nativeMessage ?? "正在打开智联招聘 App，请在 App 内完成搜索；搜索结果需手动导入");
      return;
    }
    searchStartJobIds.current = new Set(knownJobIds.current);
    setLoading(true);
    setMessage("正在通过电脑 Edge 搜索智联招聘并读取少量 JD...");
    try {
      const response = await fetch(`${apiBase}/api/application-automation/zhaopin/search-import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keyword: filters.keyword.trim() || null,
          city: filters.city.trim() || null,
          page_limit: isAndroidApp ? 1 : 3,
          import_limit: isAndroidApp ? 5 : 20,
        }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail ?? "智联官网搜索失败");
      const result = body as ZhaopinSearchResult;
      setZhaopinResult(result);
      setFilters(emptyFilters);
      setCurrentPage(1);
      await loadJobs(emptyFilters);
      setMessage(result.message);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "智联官网搜索失败";
      if (/浏览器|桥接|Edge|web-access|打开/.test(detail)) {
        window.open("https://www.zhaopin.com/", "_blank", "noopener,noreferrer");
        setMessage("电脑端桥接未连接，已打开智联官网；完成搜索后可复制真实岗位链接，在投递模块录入");
      } else {
        setMessage(detail);
      }
    } finally {
      setLoading(false);
    }
  }

  function openZhaopinApp() {
    const nativeMessage = openZhaopinSearchInNativeApp();
    setMessage(nativeMessage ?? "此入口仅在 Android App 内可用");
  }

  async function refreshImportedJobs() {
    setLoading(true);
    setMessage("正在刷新本软件岗位数据...");
    try {
      setCurrentPage(1);
      const baseline = searchStartJobIds.current ?? new Set(knownJobIds.current);
      const items = await loadJobs(emptyFilters);
      setFilters(emptyFilters);
      const added = countNewJobIds(baseline, items.map((job) => job.id));
      const zhaopinCount = items.filter((job) => {
        try {
          const host = new URL(job.source_url).hostname;
          return host === "zhaopin.com" || host.endsWith(".zhaopin.com");
        } catch {
          return false;
        }
      }).length;
      searchStartJobIds.current = new Set(items.map((job) => job.id));
      setMessage(added
        ? `刷新成功：本软件新增 ${added} 个岗位，当前共 ${zhaopinCount} 个智联岗位`
        : `刷新完成：没有发现新导入岗位，当前共 ${zhaopinCount} 个智联岗位；智联 App 搜索结果不会自动同步`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "刷新已导入岗位失败");
    } finally {
      setLoading(false);
    }
  }

  async function clearSearchExclusions() {
    if (!zhaopinResult || !window.confirm("清除当前搜索条件的历史跳过记录吗？下次相同条件会重新评估这些岗位。")) return;
    setLoading(true);
    setMessage("正在清除当前条件的历史跳过记录...");
    try {
      const response = await fetch(`${apiBase}/api/application-automation/zhaopin/search-exclusions/clear`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ search_signature: zhaopinResult.search_signature }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail ?? "清除历史跳过记录失败");
      setZhaopinResult((current) => current ? { ...current, history_skipped_count: 0 } : current);
      setMessage(body?.message ?? "已清除当前条件的历史跳过记录");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "清除历史跳过记录失败");
    } finally {
      setLoading(false);
    }
  }

  function toggleJobSelection(jobId: number) {
    setSelectedJobIds((current) => {
      const next = new Set(current);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  }

  async function clearJobs(deleteAllImported: boolean) {
    setSaving(true);
    setMessage("正在核对清除范围...");
    try {
      const scope: JobClearScope = deleteAllImported
        ? { delete_all_imported: true }
        : { job_ids: [...selectedJobIds] };
      const preview = await previewJobClear(apiBase, scope);
      if (!preview.matched_count) {
        setMessage("没有可清除的岗位");
        return;
      }
      const prompt = deleteAllImported
        ? `确定从列表清除当前账号的全部 ${preview.matched_count} 个智联导入岗位吗？手工录入岗位会保留。`
        : `确定从列表清除已勾选的 ${preview.matched_count} 个岗位吗？`;
      if (!window.confirm(`${prompt}\n岗位历史与投递快照会保留，也不会操作智联平台或拉黑公司。`)) {
        setMessage("已取消清除");
        return;
      }
      setMessage("正在从职位列表清除岗位...");
      const result = await executeJobClear(apiBase, scope);
      setLastClearedJobIds(result.cleared_job_ids);
      if (!deleteAllImported && selectedId && selectedJobIds.has(selectedId)) {
        setSelectedId(null);
        setEditorOpen(false);
        setForm(emptyJob);
      }
      if (deleteAllImported && selectedId && jobs.some((job) => job.id === selectedId && isImportedJob(job))) {
        setSelectedId(null);
        setEditorOpen(false);
        setForm(emptyJob);
      }
      setSelectedJobIds(new Set());
      const items = await loadJobs(filters);
      setCurrentPage((current) => clampJobPage(current, items.length));
      setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "清除岗位失败");
    } finally {
      setSaving(false);
    }
  }

  async function restoreLastClearedJobs() {
    if (!lastClearedJobIds.length) return;
    setSaving(true);
    setMessage("正在恢复岗位...");
    try {
      const result = await restoreClearedJobs(apiBase, lastClearedJobIds);
      setLastClearedJobIds([]);
      setCurrentPage(1);
      await loadJobs(filters);
      setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "恢复岗位失败");
    } finally {
      setSaving(false);
    }
  }

  function selectJob(job: Job) {
    setSelectedId(job.id);
    setForm(jobToForm(job));
    setEditorOpen(true);
    setMessage("已打开岗位详情");
  }

  function startNewJob() {
    setSelectedId(null);
    setForm(emptyJob);
    setEditorOpen(true);
    setMessage("正在录入新岗位");
  }

  async function saveJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("正在保存岗位...");
    const endpoint = selectedId ? `${apiBase}/api/jobs/${selectedId}` : `${apiBase}/api/jobs`;
    const method = selectedId ? "PUT" : "POST";

    try {
      const response = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "保存失败");
      }
      const saved = (await response.json()) as Job;
      const items = await loadJobs(filters, saved.id);
      if (saved.status === "closed" || !items.some((job) => job.id === saved.id)) {
        setEditorOpen(false);
        setSelectedId(null);
      }
      setMessage(saved.status === "closed" ? "岗位已关闭并从结果中移除" : "岗位已保存");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  async function deleteJob() {
    if (!selectedId || !window.confirm("确定删除当前岗位吗？")) return;
    setSaving(true);
    setMessage("正在删除岗位...");
    try {
      const response = await fetch(`${apiBase}/api/jobs/${selectedId}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败");
      await loadJobs(filters);
      setSelectedJobIds((current) => {
        const next = new Set(current);
        next.delete(selectedId);
        return next;
      });
      setSelectedId(null);
      setForm(emptyJob);
      setEditorOpen(false);
      setMessage("岗位已删除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  const totalPages = jobPageCount(jobs.length);
  const visiblePage = clampJobPage(currentPage, jobs.length);
  const visibleJobs = paginateJobs(jobs, visiblePage);

  async function toggleFavorite(job: Job) {
    setSaving(true);
    setMessage(job.is_favorite ? "正在取消收藏..." : "正在收藏岗位...");
    try {
      const response = await fetch(
        `${apiBase}/api/jobs/${job.id}/favorite?favorite=${!job.is_favorite}`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("收藏状态更新失败");
      const updated = (await response.json()) as Job;
      setJobs((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      if (selectedId === updated.id) setForm(jobToForm(updated));
      setMessage(updated.is_favorite ? "已收藏岗位" : "已取消收藏");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "收藏状态更新失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-xl font-semibold">职位搜索与筛选</h2>
          <p className="mt-1 text-sm text-muted">可按用户资料搜索智联官网并导入，也可筛选已经录入的岗位。</p>
        </div>
        <span className="text-xs text-muted" aria-live="polite">{loading ? "加载中" : message}</span>
      </div>

      <section className="border-y border-slate-200 py-5">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div><h3 className="text-base font-semibold">智联官网搜索</h3><p className="mt-1 text-sm text-muted">筛选框留空时自动使用用户中心的目标岗位、城市和最低薪资。</p></div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="button-secondary icon-text-button" disabled={loading} onClick={() => void refreshImportedJobs()}><RefreshCw size={16} className={loading ? "animate-spin" : ""} />刷新已导入岗位</button>
            {isAndroidApp && <button type="button" className="button-secondary icon-text-button" disabled={loading} onClick={openZhaopinApp}><ExternalLink size={16} />打开智联 App</button>}
            {!isAndroidApp && <button type="button" className="button-secondary icon-text-button" disabled={loading} onClick={() => window.open("https://www.zhaopin.com/", "_blank", "noopener,noreferrer")}><ExternalLink size={16} />打开智联官网</button>}
            <button type="button" className="button-primary icon-text-button" disabled={loading} onClick={() => void searchAndImportZhaopin()}>{loading ? <RefreshCw size={16} className="animate-spin" /> : <Search size={16} />}搜索并导入</button>
          </div>
        </div>
        {zhaopinResult && <div className="mt-4">
          <div className="automation-summary automation-summary-four"><div><span>搜索条件</span><strong>{zhaopinResult.query}</strong></div><div><span>扫描 / 符合</span><strong>{zhaopinResult.scanned_count} / {zhaopinResult.eligible_count}</strong></div><div><span>新导入 / 更新 / 拉黑</span><strong>{zhaopinResult.created_count} / {zhaopinResult.updated_count} / {zhaopinResult.auto_blacklisted_count}</strong></div><div><span>历史跳过</span><strong>{zhaopinResult.history_skipped_count}</strong></div></div>
          <div className="mt-3 flex flex-wrap justify-end gap-3"><button type="button" className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink" disabled={loading} onClick={() => void clearSearchExclusions()}><Trash2 size={13} />清除当前条件记录</button><a className="inline-flex items-center gap-1 text-xs text-brand" href={zhaopinResult.search_url} target="_blank" rel="noreferrer"><ExternalLink size={13} />查看本次智联搜索页</a></div>
          <div className="mt-2 divide-y divide-slate-200 border-y border-slate-200">
            {prioritizeZhaopinCandidates(zhaopinResult.candidates, 10).map((candidate) => <div key={candidate.source_url} className="flex flex-col justify-between gap-2 py-3 sm:flex-row sm:items-start"><div className="min-w-0"><strong className="text-sm text-ink">{candidate.title}</strong><p className="mt-1 text-xs text-muted">{candidate.company_name} · {candidate.city} · {candidate.salary_text}</p><p className="mt-1 text-xs leading-5 text-muted">{candidate.eligible ? candidate.reasons.join("；") : candidate.blockers.join("；")}</p></div><span className={`automation-task-status ${candidate.eligible ? "automation-task-status-submitted" : "automation-task-status-failed"}`}>{candidate.auto_blacklisted ? "已拉黑" : candidate.import_action === "created" ? "新导入" : candidate.import_action === "updated" ? "已存在并更新" : candidate.job_id ? "已导入" : candidate.eligible ? "符合" : "已过滤"}</span></div>)}
          </div>
        </div>}
      </section>

      <form onSubmit={searchJobs} className="border-y border-slate-200 py-5">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <label className="field-label sm:col-span-2">
            <span>岗位或公司</span>
            <input value={filters.keyword} onChange={(event) => updateFilter("keyword", event.target.value)} placeholder="短视频运营、直播运营或公司名" />
          </label>
          <label className="field-label">
            <span>城市</span>
            <input value={filters.city} onChange={(event) => updateFilter("city", event.target.value)} placeholder="例如：重庆" />
          </label>
          <label className="field-label">
            <span>学历</span>
            <select value={filters.degree} onChange={(event) => updateFilter("degree", event.target.value)}>
              <option value="">不限</option>
              <option>大专</option>
              <option>本科</option>
              <option>硕士</option>
            </select>
          </label>
          <label className="field-label">
            <span>最低月薪（元）</span>
            <input type="number" min={0} value={filters.salary_min} onChange={(event) => updateFilter("salary_min", event.target.value)} placeholder="例如：3000" />
          </label>
          <label className="field-label">
            <span>最高月薪（元）</span>
            <input type="number" min={0} value={filters.salary_max} onChange={(event) => updateFilter("salary_max", event.target.value)} placeholder="例如：8000" />
          </label>
          <label className="field-label">
            <span>经验</span>
            <select value={filters.experience} onChange={(event) => updateFilter("experience", event.target.value)}>
              <option value="">不限</option>
              <option>应届生/实习生</option>
              <option>1年以内</option>
              <option>1-3年</option>
              <option>3年以上</option>
            </select>
          </label>
          <label className="field-label">
            <span>公司规模</span>
            <select value={filters.company_size} onChange={(event) => updateFilter("company_size", event.target.value)}>
              <option value="">不限</option>
              <option>初创公司</option>
              <option>中小企业</option>
              <option>中大型企业</option>
              <option>上市公司</option>
            </select>
          </label>
          <label className="checkbox-option self-end">
            <input type="checkbox" checked={filters.favorite_only === "true"} onChange={(event) => updateFilter("favorite_only", event.target.checked ? "true" : "")} />
            <span>仅看收藏岗位</span>
          </label>
        </div>
        <div className="mt-4 flex flex-wrap justify-end gap-3">
          <button type="button" className="button-secondary" disabled={loading} onClick={() => void resetFilters()}>重置</button>
          <button type="submit" className="button-primary" disabled={loading}>筛选本地职位</button>
        </div>
      </form>

      <div className="mt-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div><h3 className="text-base font-semibold">搜索结果 ({jobs.length})</h3><p className="mt-1 text-xs text-muted">第 {visiblePage} / {totalPages} 页，每页 7 个；已勾选 {selectedJobIds.size} 个</p></div>
        <div className="flex flex-wrap gap-2">
          {lastClearedJobIds.length > 0 && <button type="button" className="button-secondary compact-button icon-text-button" onClick={() => void restoreLastClearedJobs()} disabled={saving}><Undo2 size={15} />撤销上次清除</button>}
          <button type="button" className="button-secondary compact-button icon-text-button" onClick={() => void clearJobs(false)} disabled={saving || selectedJobIds.size === 0}><Trash2 size={15} />清除已选</button>
          <button type="button" className="button-secondary compact-button icon-text-button danger-button" onClick={() => void clearJobs(true)} disabled={saving}><Trash2 size={15} />全部清除导入岗位</button>
          <button type="button" className="button-secondary compact-button" onClick={startNewJob} disabled={saving}>新增岗位</button>
        </div>
      </div>

      <div className={`mt-4 grid gap-6 ${editorOpen ? "xl:grid-cols-[minmax(0,1fr)_360px]" : ""}`}>
        <div>
        <div className="divide-y divide-slate-200 border-y border-slate-200">
          {visibleJobs.map((job) => (
            <div key={job.id} className={`job-result flex items-start gap-2 ${selectedId === job.id ? "job-result-active" : ""}`}>
              <label className="job-select-checkbox" title="选择这个岗位"><input type="checkbox" checked={selectedJobIds.has(job.id)} onChange={() => toggleJobSelection(job.id)} aria-label={`选择岗位：${job.title}`} /></label>
              <button type="button" className="min-w-0 flex-1 text-left" onClick={() => selectJob(job)}>
                <span className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
                  <span>
                    <strong>{job.title}</strong>
                    <span className="mt-1 block text-sm text-muted">{job.company_name || "公司名称未填写"} · {job.city || "城市未填写"}</span>
                  </span>
                  <span className="text-sm font-semibold text-emerald-700">{formatSalary(job.salary_min, job.salary_max)}</span>
                </span>
                <span className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                  <span>学历：{job.degree_required || "不限"}</span>
                  <span>经验：{job.experience_required || "不限"}</span>
                  <span>规模：{job.company_size || "不限"}</span>
                  <span>来源：{job.source_platform}</span>
                </span>
              </button>
              <button type="button" className="icon-button shrink-0" onClick={() => void toggleFavorite(job)} disabled={saving} aria-label={job.is_favorite ? "取消收藏" : "收藏岗位"} title={job.is_favorite ? "取消收藏" : "收藏岗位"}>
                <Star size={18} fill={job.is_favorite ? "currentColor" : "none"} className={job.is_favorite ? "text-amber-500" : "text-muted"} />
              </button>
            </div>
          ))}
          {!jobs.length && <div className="py-10 text-center text-sm leading-6 text-muted">没有符合条件的岗位。可调整筛选条件或新增一个岗位。</div>}
        </div>

        {jobs.length > 0 && <nav className="job-pagination" aria-label="职位结果分页"><button type="button" className="icon-button" title="上一页" aria-label="上一页" disabled={visiblePage <= 1} onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}><ChevronLeft size={17} /></button>{Array.from({ length: totalPages }, (_, index) => index + 1).map((page) => <button key={page} type="button" className={page === visiblePage ? "active" : ""} aria-current={page === visiblePage ? "page" : undefined} onClick={() => setCurrentPage(page)}>第 {page} 页</button>)}<button type="button" className="icon-button" title="下一页" aria-label="下一页" disabled={visiblePage >= totalPages} onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}><ChevronRight size={17} /></button></nav>}
        </div>

        {editorOpen && (
          <form onSubmit={saveJob} className="space-y-4 border-l border-slate-200 pl-0 xl:pl-6">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-base font-semibold">{selectedId ? "岗位详情" : "新增岗位"}</h3>
              <button type="button" className="text-sm text-muted hover:text-ink" onClick={() => setEditorOpen(false)}>关闭</button>
            </div>
            <fieldset disabled={saving} className="space-y-4">
              <label className="field-label">
                <span>岗位名称 *</span>
                <input required maxLength={160} value={form.title} onChange={(event) => updateField("title", event.target.value)} placeholder="例如：短视频运营实习生" />
              </label>
              <label className="field-label">
                <span>公司名称</span>
                <input value={form.company_name} onChange={(event) => updateField("company_name", event.target.value)} />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="field-label">
                  <span>城市</span>
                  <input value={form.city} onChange={(event) => updateField("city", event.target.value)} />
                </label>
                <label className="field-label">
                  <span>状态</span>
                  <select value={form.status} onChange={(event) => updateField("status", event.target.value as JobForm["status"])}>
                    <option value="open">招聘中</option>
                    <option value="closed">已关闭</option>
                  </select>
                </label>
                <label className="field-label">
                  <span>最低月薪</span>
                  <input type="number" min={0} value={form.salary_min ?? ""} onChange={(event) => updateField("salary_min", event.target.value ? Number(event.target.value) : null)} />
                </label>
                <label className="field-label">
                  <span>最高月薪</span>
                  <input type="number" min={0} value={form.salary_max ?? ""} onChange={(event) => updateField("salary_max", event.target.value ? Number(event.target.value) : null)} />
                </label>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="field-label">
                  <span>学历</span>
                  <select value={form.degree_required} onChange={(event) => updateField("degree_required", event.target.value)}>
                    <option>不限</option><option>大专</option><option>本科</option><option>硕士</option>
                  </select>
                </label>
                <label className="field-label">
                  <span>经验</span>
                  <select value={form.experience_required} onChange={(event) => updateField("experience_required", event.target.value)}>
                    <option>不限</option><option>应届生/实习生</option><option>1年以内</option><option>1-3年</option><option>3年以上</option>
                  </select>
                </label>
              </div>
              <label className="field-label">
                <span>公司规模</span>
                <select value={form.company_size} onChange={(event) => updateField("company_size", event.target.value)}>
                  <option>不限</option><option>初创公司</option><option>中小企业</option><option>中大型企业</option><option>上市公司</option>
                </select>
              </label>
              <label className="field-label">
                <span>职位描述（JD）</span>
                <textarea rows={9} value={form.description} onChange={(event) => updateField("description", event.target.value)} placeholder="粘贴岗位职责和任职要求" />
              </label>
              <label className="field-label">
                <span>来源平台</span>
                <input value={form.source_platform} onChange={(event) => updateField("source_platform", event.target.value)} placeholder="手动录入" />
              </label>
              <label className="field-label">
                <span>原始链接</span>
                <input type="url" value={form.source_url} onChange={(event) => updateField("source_url", event.target.value)} placeholder="https://..." />
              </label>
            </fieldset>
            <div className="flex flex-wrap justify-end gap-3 border-t border-slate-200 pt-4">
              <button type="button" className="button-secondary" disabled={!selectedId || saving} onClick={() => void deleteJob()}>删除</button>
              <button type="submit" className="button-primary" disabled={saving}>{saving ? "处理中..." : "保存岗位"}</button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}
