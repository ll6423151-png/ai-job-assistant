"use client";

import { useEffect, useState } from "react";

type BreakdownItem = { key: string; count: number; percentage: number };
type TrendPoint = { date: string; count: number };
type RecentApplication = { id: number; job_title: string; company_name: string; status: string; channel: string; updated_at: string };

type AnalyticsOverview = {
  generated_at: string;
  jobs_count: number;
  resumes_count: number;
  match_analyses_count: number;
  applications_total: number;
  submitted_count: number;
  active_count: number;
  response_count: number;
  interview_count: number;
  offer_count: number;
  rejected_count: number;
  due_follow_ups: number;
  response_rate: number;
  interview_rate: number;
  offer_rate: number;
  average_match_score: number;
  status_breakdown: BreakdownItem[];
  channel_breakdown: BreakdownItem[];
  score_distribution: BreakdownItem[];
  submission_trend: TrendPoint[];
  recent_applications: RecentApplication[];
};

const statusLabels: Record<string, string> = { prepared: "待确认", submitted: "已投递", screening: "筛选中", interview: "面试", offer: "Offer", rejected: "未通过", withdrawn: "已撤回" };
const scoreLabels: Record<string, string> = { high: "高匹配（80-100）", medium: "中匹配（60-79）", low: "待提升（0-59）" };

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(new Date(value));
}

export function AnalyticsPanel({ apiBase }: { apiBase: string }) {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("正在计算统计数据...");

  async function loadAnalytics() {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/analytics/overview`, { cache: "no-store" });
      if (!response.ok) throw new Error("无法读取统计数据");
      const overview = (await response.json()) as AnalyticsOverview;
      setData(overview);
      setMessage(`数据更新于 ${new Intl.DateTimeFormat("zh-CN", { timeStyle: "short" }).format(new Date(overview.generated_at))}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "统计加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadAnalytics(); }, [apiBase]);

  if (!data) return <section><div className="mb-5 flex items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">数据统计</h2><p className="mt-1 text-sm text-muted">汇总职位、匹配和投递进度。</p></div><span className="text-xs text-muted">{message}</span></div><div className="empty-panel">{loading ? "正在计算统计数据..." : "暂无可展示数据"}</div></section>;

  const maxTrend = Math.max(...data.submission_trend.map((point) => point.count), 1);
  const metrics = [
    ["已确认投递", data.submitted_count, `全部记录 ${data.applications_total}`],
    ["收到响应", data.response_count, `响应率 ${data.response_rate}%`],
    ["进入面试", data.interview_count, `面试率 ${data.interview_rate}%`],
    ["获得 Offer", data.offer_count, `Offer 率 ${data.offer_rate}%`],
    ["平均匹配分", data.average_match_score, `${data.match_analyses_count} 次分析`],
    ["待跟进", data.due_follow_ups, data.due_follow_ups ? "已有记录到期" : "暂无到期记录"],
  ];

  return <section>
    <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><h2 className="text-xl font-semibold">数据统计</h2><p className="mt-1 text-sm text-muted">实时汇总职位、简历、匹配分析和用户确认的投递记录。</p></div><div className="flex items-center gap-3"><span className="text-xs text-muted">{loading ? "刷新中" : message}</span><button type="button" className="button-secondary compact-button" disabled={loading} onClick={() => void loadAnalytics()}>刷新</button></div></div>

    <div className="analytics-metrics">
      {metrics.map(([label, value, detail]) => <article key={label as string} className="metric-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>)}
    </div>

    <div className="mt-7 grid gap-7 xl:grid-cols-2">
      <section className="analytics-section"><h3>投递状态分布</h3><div className="mt-4 space-y-3">{data.status_breakdown.map((item) => <div key={item.key} className="distribution-row"><div><span>{statusLabels[item.key]}</span><strong>{item.count}</strong></div><div className="distribution-track"><span style={{ width: `${item.percentage}%` }} /></div></div>)}</div></section>
      <section className="analytics-section"><h3>JD 匹配分布</h3><div className="mt-4 space-y-3">{data.score_distribution.map((item) => <div key={item.key} className="distribution-row"><div><span>{scoreLabels[item.key]}</span><strong>{item.count}</strong></div><div className={`distribution-track score-${item.key}`}><span style={{ width: `${item.percentage}%` }} /></div></div>)}</div><div className="mt-5 grid grid-cols-3 gap-3 border-t border-slate-200 pt-4 text-center"><div><strong className="block text-lg text-ink">{data.jobs_count}</strong><span className="text-xs text-muted">职位</span></div><div><strong className="block text-lg text-ink">{data.resumes_count}</strong><span className="text-xs text-muted">简历</span></div><div><strong className="block text-lg text-ink">{data.active_count}</strong><span className="text-xs text-muted">进行中</span></div></div></section>
    </div>

    <section className="analytics-section mt-7"><div className="flex items-center justify-between gap-3"><h3>近 14 天确认投递</h3><span className="text-xs text-muted">合计 {data.submission_trend.reduce((sum, point) => sum + point.count, 0)}</span></div><div className="trend-chart mt-5">{data.submission_trend.map((point) => <div key={point.date} className="trend-column"><div className="trend-value">{point.count || ""}</div><div className="trend-bar-wrap"><span style={{ height: point.count ? `${Math.max((point.count / maxTrend) * 100, 8)}%` : "0%" }} /></div><small>{formatDate(point.date)}</small></div>)}</div></section>

    <div className="mt-7 grid gap-7 xl:grid-cols-[320px_minmax(0,1fr)]">
      <section className="analytics-section"><h3>投递渠道</h3><div className="mt-4 space-y-3">{data.channel_breakdown.length ? data.channel_breakdown.map((item) => <div key={item.key} className="channel-row"><span>{item.key}</span><strong>{item.count}</strong><small>{item.percentage}%</small></div>) : <p className="text-sm text-muted">暂无渠道数据</p>}</div></section>
      <section className="analytics-section"><h3>最近更新的投递</h3><div className="mt-4 overflow-x-auto"><table className="analytics-table"><thead><tr><th>岗位</th><th>公司</th><th>渠道</th><th>状态</th><th>更新时间</th></tr></thead><tbody>{data.recent_applications.map((item) => <tr key={item.id}><td>{item.job_title}</td><td>{item.company_name || "-"}</td><td>{item.channel}</td><td><span className={`application-status application-status-${item.status}`}>{statusLabels[item.status]}</span></td><td>{formatDate(item.updated_at)}</td></tr>)}</tbody></table>{!data.recent_applications.length && <p className="py-6 text-center text-sm text-muted">暂无投递记录</p>}</div></section>
    </div>
  </section>;
}
