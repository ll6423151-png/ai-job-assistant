"use client";

import { useEffect, useState } from "react";

type JobOption = {
  id: number;
  title: string;
  company_name: string;
};

type ResumeOption = {
  id: number;
  title: string;
  version: number;
};

type Tone = "concise" | "professional" | "warm";

type Greeting = {
  id: number;
  job_id: number;
  resume_id: number;
  match_id: number | null;
  job_title: string;
  company_name: string;
  resume_title: string;
  tone: Tone;
  content: string;
  status: "draft" | "approved";
  created_at: string;
  updated_at: string;
};

const toneLabels: Record<Tone, string> = {
  concise: "简洁",
  professional: "专业",
  warm: "友好",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function GreetingPanel({ apiBase }: { apiBase: string }) {
  const [jobs, setJobs] = useState<JobOption[]>([]);
  const [resumes, setResumes] = useState<ResumeOption[]>([]);
  const [greetings, setGreetings] = useState<Greeting[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | "">("");
  const [selectedResumeId, setSelectedResumeId] = useState<number | "">("");
  const [tone, setTone] = useState<Tone>("professional");
  const [current, setCurrent] = useState<Greeting | null>(null);
  const [content, setContent] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("正在读取沟通草稿...");

  async function loadData() {
    const [jobsResponse, resumesResponse, greetingsResponse] = await Promise.all([
      fetch(`${apiBase}/api/jobs`, { cache: "no-store" }),
      fetch(`${apiBase}/api/resumes`, { cache: "no-store" }),
      fetch(`${apiBase}/api/greetings`, { cache: "no-store" }),
    ]);
    if (!jobsResponse.ok || !resumesResponse.ok || !greetingsResponse.ok) throw new Error("无法读取沟通数据");
    const nextJobs = (await jobsResponse.json()) as JobOption[];
    const nextResumes = (await resumesResponse.json()) as ResumeOption[];
    const nextGreetings = (await greetingsResponse.json()) as Greeting[];
    setJobs(nextJobs);
    setResumes(nextResumes);
    setGreetings(nextGreetings);
    setSelectedJobId((id) => id || nextJobs[0]?.id || "");
    setSelectedResumeId((id) => id || nextResumes[0]?.id || "");
    if (nextGreetings[0]) selectGreeting(nextGreetings[0]);
    return { jobs: nextJobs, resumes: nextResumes };
  }

  useEffect(() => {
    loadData()
      .then(({ jobs: nextJobs, resumes: nextResumes }) => setMessage(nextJobs.length && nextResumes.length ? "可生成沟通草稿" : "请先准备职位和简历"))
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [apiBase]);

  function selectGreeting(greeting: Greeting) {
    setCurrent(greeting);
    setContent(greeting.content);
    setTone(greeting.tone);
    setConfirmed(false);
  }

  async function generateGreeting() {
    if (!selectedJobId || !selectedResumeId) return;
    setWorking(true);
    setMessage("正在生成沟通草稿...");
    try {
      const response = await fetch(`${apiBase}/api/greetings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: selectedJobId, resume_id: selectedResumeId, tone }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "生成失败");
      }
      const greeting = (await response.json()) as Greeting;
      setGreetings((items) => [greeting, ...items]);
      selectGreeting(greeting);
      setMessage(greeting.match_id ? "草稿已生成，并使用最近一次匹配关键词" : "草稿已生成，当前职位与简历暂无匹配记录");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "生成失败，请稍后重试");
    } finally {
      setWorking(false);
    }
  }

  async function saveDraft(silent = false): Promise<Greeting | null> {
    if (!current || current.status !== "draft") return current;
    const response = await fetch(`${apiBase}/api/greetings/${current.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail ?? "保存失败");
    }
    const saved = (await response.json()) as Greeting;
    setCurrent(saved);
    setGreetings((items) => items.map((item) => item.id === saved.id ? saved : item));
    if (!silent) setMessage("沟通草稿已保存");
    return saved;
  }

  async function handleSave() {
    setWorking(true);
    try {
      await saveDraft();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setWorking(false);
    }
  }

  async function approveGreeting() {
    if (!current || !confirmed) return;
    setWorking(true);
    setMessage("正在确认定稿...");
    try {
      const saved = await saveDraft(true);
      if (!saved) return;
      const response = await fetch(`${apiBase}/api/greetings/${saved.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed: true }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "定稿失败");
      }
      const approved = (await response.json()) as Greeting;
      setCurrent(approved);
      setGreetings((items) => items.map((item) => item.id === approved.id ? approved : item));
      setConfirmed(false);
      setMessage("内容已定稿，但不会自动发送");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "定稿失败");
    } finally {
      setWorking(false);
    }
  }

  async function copyContent() {
    try {
      await navigator.clipboard.writeText(content);
      setMessage("沟通内容已复制");
    } catch {
      setMessage("复制失败，请检查浏览器剪贴板权限");
    }
  }

  async function deleteGreeting() {
    if (!current || !window.confirm("确定删除当前沟通记录吗？")) return;
    setWorking(true);
    try {
      const response = await fetch(`${apiBase}/api/greetings/${current.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败");
      const nextItems = greetings.filter((item) => item.id !== current.id);
      setGreetings(nextItems);
      if (nextItems[0]) selectGreeting(nextItems[0]);
      else {
        setCurrent(null);
        setContent("");
      }
      setMessage("沟通记录已删除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section>
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-xl font-semibold">求职沟通内容</h2>
          <p className="mt-1 text-sm text-muted">根据已有职位、简历和匹配证据生成草稿；定稿后仍需由你自行决定是否发送。</p>
        </div>
        <span className="text-xs text-muted" aria-live="polite">{loading ? "加载中" : message}</span>
      </div>

      <div className="border-y border-slate-200 py-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="field-label sm:col-span-1">
            <span>职位</span>
            <select value={selectedJobId} onChange={(event) => setSelectedJobId(event.target.value ? Number(event.target.value) : "")} disabled={loading || working}>
              <option value="">请选择职位</option>
              {jobs.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company_name || "未填写公司"}</option>)}
            </select>
          </label>
          <label className="field-label sm:col-span-1">
            <span>简历</span>
            <select value={selectedResumeId} onChange={(event) => setSelectedResumeId(event.target.value ? Number(event.target.value) : "")} disabled={loading || working}>
              <option value="">请选择简历</option>
              {resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.title} · v{resume.version}</option>)}
            </select>
          </label>
          <label className="field-label sm:col-span-1">
            <span>语气</span>
            <select value={tone} onChange={(event) => setTone(event.target.value as Tone)} disabled={loading || working}>
              <option value="concise">简洁</option>
              <option value="professional">专业</option>
              <option value="warm">友好</option>
            </select>
          </label>
        </div>
        <div className="mt-4 flex justify-end"><button type="button" className="button-primary" disabled={loading || working || !selectedJobId || !selectedResumeId} onClick={() => void generateGreeting()}>生成沟通草稿</button></div>
      </div>

      {current ? (
        <div className="mt-6 grid gap-7 xl:grid-cols-[minmax(0,1fr)_280px]">
          <article>
            <div className="flex flex-col justify-between gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-start">
              <div><p className="text-sm text-muted">{current.company_name || "公司名称未填写"}</p><h3 className="mt-1 text-lg font-semibold">{current.job_title}</h3><p className="mt-1 text-xs text-muted">语气：{toneLabels[current.tone]} · 简历：{current.resume_title}</p></div>
              <span className={`greeting-status greeting-status-${current.status}`}>{current.status === "draft" ? "草稿" : "已定稿"}</span>
            </div>

            <label className="field-label mt-6">
              <span>沟通内容</span>
              <textarea rows={10} maxLength={1000} value={content} disabled={current.status !== "draft" || working} onChange={(event) => setContent(event.target.value)} />
              <small>{content.length}/1000 字；请核对姓名、岗位和经历描述。</small>
            </label>

            {current.status === "draft" && (
              <label className="confirmation-row mt-5"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>我已核对内容真实准确，并将其确认为可使用版本。</span></label>
            )}

            <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-slate-200 pt-5">
              <button type="button" className="button-secondary" disabled={working} onClick={() => void deleteGreeting()}>删除记录</button>
              <button type="button" className="button-secondary" disabled={!content || working} onClick={() => void copyContent()}>复制内容</button>
              {current.status === "draft" && <button type="button" className="button-secondary" disabled={working || !content.trim()} onClick={() => void handleSave()}>保存草稿</button>}
              {current.status === "draft" && <button type="button" className="button-primary" disabled={working || !confirmed || !content.trim()} onClick={() => void approveGreeting()}>确认定稿</button>}
            </div>
            <p className="mt-3 text-right text-xs text-muted">定稿不会触发发送或投递。</p>
          </article>

          <aside className="border-l border-slate-200 pl-0 xl:pl-6">
            <h3 className="text-sm font-semibold">沟通历史 ({greetings.length})</h3>
            <div className="mt-3 divide-y divide-slate-200 border-y border-slate-200">
              {greetings.map((greeting) => (
                <button key={greeting.id} type="button" className={`greeting-history-item ${current.id === greeting.id ? "greeting-history-active" : ""}`} onClick={() => selectGreeting(greeting)}>
                  <span className="flex items-center justify-between gap-2"><strong>{greeting.status === "draft" ? "草稿" : "已定稿"}</strong><span className="text-xs text-muted">{formatDate(greeting.updated_at)}</span></span>
                  <span className="mt-1 block truncate text-xs text-muted">{greeting.job_title}</span>
                  <span className="mt-1 block truncate text-xs text-muted">{toneLabels[greeting.tone]}</span>
                </button>
              ))}
            </div>
          </aside>
        </div>
      ) : (
        <div className="empty-panel mt-8">选择职位、简历和语气后生成沟通草稿。系统不会自动发送。</div>
      )}
    </section>
  );
}
