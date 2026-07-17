"use client";

import { useEffect, useState } from "react";

type MatchOption = {
  id: number;
  job_title: string;
  resume_title: string;
  score: number;
  created_at: string;
};

type Optimization = {
  id: number;
  match_id: number;
  job_id: number;
  resume_id: number;
  job_title: string;
  resume_title: string;
  original_content: string;
  proposed_content: string;
  suggestions: string[];
  warnings: string[];
  status: "draft" | "applied" | "rejected";
  created_at: string;
  updated_at: string;
};

const statusLabels: Record<Optimization["status"], string> = {
  draft: "草稿",
  applied: "已应用",
  rejected: "已拒绝",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function OptimizationPanel({ apiBase }: { apiBase: string }) {
  const [matches, setMatches] = useState<MatchOption[]>([]);
  const [optimizations, setOptimizations] = useState<Optimization[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState<number | "">("");
  const [current, setCurrent] = useState<Optimization | null>(null);
  const [proposedContent, setProposedContent] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("正在读取优化记录...");

  async function loadData() {
    const [matchesResponse, optimizationsResponse] = await Promise.all([
      fetch(`${apiBase}/api/matches`, { cache: "no-store" }),
      fetch(`${apiBase}/api/optimizations`, { cache: "no-store" }),
    ]);
    if (!matchesResponse.ok || !optimizationsResponse.ok) throw new Error("无法读取优化数据");
    const nextMatches = (await matchesResponse.json()) as MatchOption[];
    const nextOptimizations = (await optimizationsResponse.json()) as Optimization[];
    setMatches(nextMatches);
    setOptimizations(nextOptimizations);
    setSelectedMatchId((matchId) => matchId || nextMatches[0]?.id || "");
    if (nextOptimizations[0]) selectOptimization(nextOptimizations[0]);
    return { matches: nextMatches, optimizations: nextOptimizations };
  }

  useEffect(() => {
    loadData()
      .then(({ matches: nextMatches }) => setMessage(nextMatches.length ? `可基于 ${nextMatches.length} 条匹配记录生成草稿` : "请先完成一次 JD 匹配分析"))
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [apiBase]);

  function selectOptimization(optimization: Optimization) {
    setCurrent(optimization);
    setProposedContent(optimization.proposed_content);
    setConfirmed(false);
  }

  async function createDraft() {
    if (!selectedMatchId) return;
    setWorking(true);
    setMessage("正在生成优化草稿...");
    try {
      const response = await fetch(`${apiBase}/api/optimizations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ match_id: selectedMatchId }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "草稿生成失败");
      }
      const optimization = (await response.json()) as Optimization;
      setOptimizations((items) => [optimization, ...items]);
      selectOptimization(optimization);
      setMessage("优化草稿已生成，请核对并编辑");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "草稿生成失败");
    } finally {
      setWorking(false);
    }
  }

  async function saveDraft(silent = false): Promise<Optimization | null> {
    if (!current || current.status !== "draft") return current;
    const response = await fetch(`${apiBase}/api/optimizations/${current.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proposed_content: proposedContent }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail ?? "草稿保存失败");
    }
    const saved = (await response.json()) as Optimization;
    setCurrent(saved);
    setOptimizations((items) => items.map((item) => item.id === saved.id ? saved : item));
    if (!silent) setMessage("优化草稿已保存");
    return saved;
  }

  async function handleSave() {
    setWorking(true);
    try {
      await saveDraft();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "草稿保存失败");
    } finally {
      setWorking(false);
    }
  }

  async function applyDraft() {
    if (!current || !confirmed) return;
    setWorking(true);
    setMessage("正在应用到简历...");
    try {
      const saved = await saveDraft(true);
      if (!saved) return;
      const response = await fetch(`${apiBase}/api/optimizations/${saved.id}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed: true }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "应用失败");
      }
      const applied = (await response.json()) as Optimization;
      setCurrent(applied);
      setOptimizations((items) => items.map((item) => item.id === applied.id ? applied : item));
      setConfirmed(false);
      setMessage("优化内容已应用到原简历");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "应用失败，请稍后重试");
    } finally {
      setWorking(false);
    }
  }

  async function rejectDraft() {
    if (!current || current.status !== "draft") return;
    setWorking(true);
    try {
      const response = await fetch(`${apiBase}/api/optimizations/${current.id}/reject`, { method: "POST" });
      if (!response.ok) throw new Error("拒绝草稿失败");
      const rejected = (await response.json()) as Optimization;
      setCurrent(rejected);
      setOptimizations((items) => items.map((item) => item.id === rejected.id ? rejected : item));
      setMessage("优化草稿已拒绝，原简历未修改");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败");
    } finally {
      setWorking(false);
    }
  }

  async function deleteOptimization() {
    if (!current || !window.confirm("确定删除当前优化记录吗？")) return;
    setWorking(true);
    try {
      const response = await fetch(`${apiBase}/api/optimizations/${current.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败");
      const nextItems = optimizations.filter((item) => item.id !== current.id);
      setOptimizations(nextItems);
      if (nextItems[0]) selectOptimization(nextItems[0]);
      else {
        setCurrent(null);
        setProposedContent("");
      }
      setMessage("优化记录已删除");
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
          <h2 className="text-xl font-semibold">简历优化</h2>
          <p className="mt-1 text-sm text-muted">基于匹配结果生成可编辑草稿，只有确认真实性后才会覆盖简历正文。</p>
        </div>
        <span className="text-xs text-muted" aria-live="polite">{loading ? "加载中" : message}</span>
      </div>

      <div className="border-y border-slate-200 py-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="field-label flex-1">
            <span>选择匹配记录</span>
            <select value={selectedMatchId} onChange={(event) => setSelectedMatchId(event.target.value ? Number(event.target.value) : "")} disabled={loading || working}>
              <option value="">请选择匹配记录</option>
              {matches.map((match) => <option key={match.id} value={match.id}>{match.job_title} · {match.resume_title} · {match.score} 分</option>)}
            </select>
          </label>
          <button type="button" className="button-primary" disabled={loading || working || !selectedMatchId} onClick={() => void createDraft()}>生成优化草稿</button>
        </div>
      </div>

      {current ? (
        <div className="mt-6 grid gap-7 xl:grid-cols-[minmax(0,1fr)_280px]">
          <article>
            <div className="flex flex-col justify-between gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-start">
              <div><p className="text-sm text-muted">{current.job_title}</p><h3 className="mt-1 text-lg font-semibold">{current.resume_title}</h3></div>
              <span className={`optimization-status optimization-status-${current.status}`}>{statusLabels[current.status]}</span>
            </div>

            <div className="mt-6 grid gap-6 sm:grid-cols-2">
              <div>
                <h4 className="text-sm font-semibold">修改建议</h4>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">{current.suggestions.map((suggestion) => <li key={suggestion}>· {suggestion}</li>)}</ul>
              </div>
              <div>
                <h4 className="text-sm font-semibold">真实性提示</h4>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-rose-700">{current.warnings.map((warning) => <li key={warning}>· {warning}</li>)}</ul>
              </div>
            </div>

            <details className="mt-6 border-y border-slate-200 py-4">
              <summary className="cursor-pointer text-sm font-semibold">查看优化前原文</summary>
              <pre className="resume-preview mt-4">{current.original_content || "原简历正文为空"}</pre>
            </details>

            <label className="field-label mt-6">
              <span>优化建议稿</span>
              <textarea rows={22} maxLength={50000} value={proposedContent} disabled={current.status !== "draft" || working} onChange={(event) => setProposedContent(event.target.value)} />
              <small>建议稿可以继续手动修改；缺失技能不会被自动写入。</small>
            </label>

            {current.status === "draft" && (
              <label className="confirmation-row mt-5">
                <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
                <span>我已核对建议稿，确认内容真实，并同意覆盖当前简历正文。</span>
              </label>
            )}

            <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-slate-200 pt-5">
              <button type="button" className="button-secondary" disabled={working} onClick={() => void deleteOptimization()}>删除记录</button>
              {current.status === "draft" && <button type="button" className="button-secondary" disabled={working} onClick={() => void rejectDraft()}>拒绝草稿</button>}
              {current.status === "draft" && <button type="button" className="button-secondary" disabled={working} onClick={() => void handleSave()}>保存草稿</button>}
              {current.status === "draft" && <button type="button" className="button-primary" disabled={working || !confirmed} onClick={() => void applyDraft()}>确认并应用</button>}
            </div>
          </article>

          <aside className="border-l border-slate-200 pl-0 xl:pl-6">
            <h3 className="text-sm font-semibold">优化历史 ({optimizations.length})</h3>
            <div className="mt-3 divide-y divide-slate-200 border-y border-slate-200">
              {optimizations.map((optimization) => (
                <button key={optimization.id} type="button" className={`optimization-history-item ${current.id === optimization.id ? "optimization-history-active" : ""}`} onClick={() => selectOptimization(optimization)}>
                  <span className="flex items-center justify-between gap-2"><strong>{statusLabels[optimization.status]}</strong><span className="text-xs text-muted">{formatDate(optimization.updated_at)}</span></span>
                  <span className="mt-1 block truncate text-xs text-muted">{optimization.job_title}</span>
                  <span className="mt-1 block truncate text-xs text-muted">{optimization.resume_title}</span>
                </button>
              ))}
            </div>
          </aside>
        </div>
      ) : (
        <div className="empty-panel mt-8">先完成 JD 匹配分析，再选择一条匹配记录生成优化草稿。</div>
      )}
    </section>
  );
}
