"use client";

import { useEffect, useState } from "react";

type JobOption = {
  id: number;
  title: string;
  company_name: string;
  city: string;
};

type ResumeOption = {
  id: number;
  title: string;
  target_role: string;
  version: number;
};

type MatchAnalysis = {
  id: number;
  job_id: number;
  resume_id: number;
  job_title: string;
  resume_title: string;
  score: number;
  matched_keywords: string[];
  missing_keywords: string[];
  reasons: string[];
  recommendations: string[];
  created_at: string;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function MatchPanel({ apiBase }: { apiBase: string }) {
  const [jobs, setJobs] = useState<JobOption[]>([]);
  const [resumes, setResumes] = useState<ResumeOption[]>([]);
  const [analyses, setAnalyses] = useState<MatchAnalysis[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | "">("");
  const [selectedResumeId, setSelectedResumeId] = useState<number | "">("");
  const [current, setCurrent] = useState<MatchAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("正在读取岗位和简历...");

  async function loadData() {
    const [jobsResponse, resumesResponse, matchesResponse] = await Promise.all([
      fetch(`${apiBase}/api/jobs`, { cache: "no-store" }),
      fetch(`${apiBase}/api/resumes`, { cache: "no-store" }),
      fetch(`${apiBase}/api/matches`, { cache: "no-store" }),
    ]);
    if (!jobsResponse.ok || !resumesResponse.ok || !matchesResponse.ok) throw new Error("无法读取匹配数据");

    const nextJobs = (await jobsResponse.json()) as JobOption[];
    const nextResumes = (await resumesResponse.json()) as ResumeOption[];
    const nextAnalyses = (await matchesResponse.json()) as MatchAnalysis[];
    setJobs(nextJobs);
    setResumes(nextResumes);
    setAnalyses(nextAnalyses);
    setSelectedJobId((currentJobId) => currentJobId || nextJobs[0]?.id || "");
    setSelectedResumeId((currentResumeId) => currentResumeId || nextResumes.find((resume) => resume.id)?.id || "");
    if (!current && nextAnalyses[0]) setCurrent(nextAnalyses[0]);
    return { jobs: nextJobs, resumes: nextResumes, analyses: nextAnalyses };
  }

  useEffect(() => {
    loadData()
      .then(({ jobs: nextJobs, resumes: nextResumes, analyses: nextAnalyses }) => {
        if (!nextJobs.length || !nextResumes.length) {
          setMessage("请先在职位搜索和简历管理中准备数据");
        } else {
          setMessage(`可分析 ${nextJobs.length} 个岗位和 ${nextResumes.length} 份简历`);
        }
        if (!nextAnalyses.length) setCurrent(null);
      })
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [apiBase]);

  async function runAnalysis() {
    if (!selectedJobId || !selectedResumeId) return;
    setRunning(true);
    setMessage("正在分析 JD 与简历...");
    try {
      const response = await fetch(`${apiBase}/api/matches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: selectedJobId, resume_id: selectedResumeId }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "匹配分析失败");
      }
      const result = (await response.json()) as MatchAnalysis;
      setCurrent(result);
      setAnalyses((items) => [result, ...items]);
      setMessage("分析完成，结果已保存");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "匹配分析失败，请稍后重试");
    } finally {
      setRunning(false);
    }
  }

  async function deleteAnalysis(id: number) {
    try {
      const response = await fetch(`${apiBase}/api/matches/${id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败");
      const nextAnalyses = analyses.filter((analysis) => analysis.id !== id);
      setAnalyses(nextAnalyses);
      setCurrent((analysis) => (analysis?.id === id ? nextAnalyses[0] ?? null : analysis));
      setMessage("分析记录已删除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    }
  }

  return (
    <section>
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-xl font-semibold">JD 匹配分析</h2>
          <p className="mt-1 text-sm text-muted">基于 JD 关键词和简历已有内容给出可解释的匹配结果，不把缺失经历当成已具备。</p>
        </div>
        <span className="text-xs text-muted" aria-live="polite">{loading ? "加载中" : message}</span>
      </div>

      <div className="border-y border-slate-200 py-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="field-label">
            <span>选择职位</span>
            <select value={selectedJobId} onChange={(event) => setSelectedJobId(event.target.value ? Number(event.target.value) : "")} disabled={loading || running}>
              <option value="">请选择职位</option>
              {jobs.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company_name || "未填写公司"}</option>)}
            </select>
          </label>
          <label className="field-label">
            <span>选择简历</span>
            <select value={selectedResumeId} onChange={(event) => setSelectedResumeId(event.target.value ? Number(event.target.value) : "")} disabled={loading || running}>
              <option value="">请选择简历</option>
              {resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.title} · v{resume.version}</option>)}
            </select>
          </label>
        </div>
        <div className="mt-4 flex justify-end">
          <button type="button" className="button-primary" disabled={loading || running || !selectedJobId || !selectedResumeId} onClick={() => void runAnalysis()}>{running ? "分析中..." : "开始匹配"}</button>
        </div>
      </div>

      {current ? (
        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
          <article>
            <div className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-center">
              <div>
                <p className="text-sm text-muted">{current.job_title}</p>
                <h3 className="mt-1 text-lg font-semibold">匹配结果 · {current.resume_title}</h3>
              </div>
              <div className="score-display"><strong>{current.score}</strong><span>/ 100</span></div>
            </div>

            <div className="mt-5">
              <div className="flex items-center justify-between text-xs text-muted"><span>匹配度</span><span>{current.score}%</span></div>
              <div className="score-track mt-2"><span style={{ width: `${current.score}%` }} /></div>
            </div>

            <div className="mt-7 grid gap-6 sm:grid-cols-2">
              <div>
                <h4 className="text-sm font-semibold">已覆盖能力 ({current.matched_keywords.length})</h4>
                <div className="mt-3 flex flex-wrap gap-2">
                  {current.matched_keywords.length ? current.matched_keywords.map((keyword) => <span key={keyword} className="keyword-match">{keyword}</span>) : <span className="text-sm text-muted">暂未识别到命中关键词</span>}
                </div>
              </div>
              <div>
                <h4 className="text-sm font-semibold">待核对缺口 ({current.missing_keywords.length})</h4>
                <div className="mt-3 flex flex-wrap gap-2">
                  {current.missing_keywords.length ? current.missing_keywords.map((keyword) => <span key={keyword} className="keyword-missing">{keyword}</span>) : <span className="text-sm text-muted">没有识别到明显缺口</span>}
                </div>
              </div>
            </div>

            <div className="mt-7 border-t border-slate-200 pt-6">
              <h4 className="text-sm font-semibold">判断依据</h4>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">{current.reasons.map((reason) => <li key={reason}>· {reason}</li>)}</ul>
            </div>

            <div className="mt-6 border-t border-slate-200 pt-6">
              <h4 className="text-sm font-semibold">优化建议</h4>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">{current.recommendations.map((recommendation) => <li key={recommendation}>· {recommendation}</li>)}</ul>
            </div>
          </article>

          <aside className="border-l border-slate-200 pl-0 xl:pl-6">
            <h3 className="text-sm font-semibold">分析历史 ({analyses.length})</h3>
            <div className="mt-3 divide-y divide-slate-200 border-y border-slate-200">
              {analyses.map((analysis) => (
                <div key={analysis.id} role="button" tabIndex={0} className={`match-history-item ${current.id === analysis.id ? "match-history-active" : ""}`} onClick={() => setCurrent(analysis)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setCurrent(analysis); }}>
                  <span className="flex items-center justify-between gap-2"><strong>{analysis.score} 分</strong><span className="text-xs text-muted">{formatDate(analysis.created_at)}</span></span>
                  <span className="mt-1 block truncate text-xs text-muted">{analysis.job_title}</span>
                  <span className="mt-1 block truncate text-xs text-muted">{analysis.resume_title}</span>
                  <button type="button" className="mt-2 text-xs text-muted hover:text-rose-700" onClick={(event) => { event.stopPropagation(); void deleteAnalysis(analysis.id); }}>删除记录</button>
                </div>
              ))}
            </div>
          </aside>
        </div>
      ) : (
        <div className="empty-panel mt-8">选择一条职位和一份简历后开始匹配。分析结果会显示关键词覆盖、缺口与可执行建议。</div>
      )}
    </section>
  );
}
