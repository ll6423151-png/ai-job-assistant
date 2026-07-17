"use client";

import { FormEvent, useEffect, useState } from "react";

type ApplicationStatus = "prepared" | "submitted" | "screening" | "interview" | "offer" | "rejected" | "withdrawn";

type JobOption = { id: number; title: string; company_name: string };
type ResumeOption = { id: number; title: string; version: number };
type GreetingOption = { id: number; job_id: number; resume_id: number; job_title: string; status: "draft" | "approved" };
type StatusEvent = { status: ApplicationStatus; timestamp: string; note: string };

type ApplicationRecord = {
  id: number;
  job_id: number;
  resume_id: number;
  greeting_id: number | null;
  job_title: string;
  company_name: string;
  resume_title: string;
  channel: string;
  status: ApplicationStatus;
  confirmed_by_user: boolean;
  applied_at: string | null;
  next_follow_up_at: string | null;
  notes: string;
  status_history: StatusEvent[];
  created_at: string;
  updated_at: string;
};

const statusLabels: Record<ApplicationStatus, string> = {
  prepared: "待确认",
  submitted: "已投递",
  screening: "筛选中",
  interview: "面试",
  offer: "Offer",
  rejected: "未通过",
  withdrawn: "已撤回",
};

const nextStatuses: Record<ApplicationStatus, ApplicationStatus[]> = {
  prepared: ["withdrawn"],
  submitted: ["screening", "interview", "offer", "rejected", "withdrawn"],
  screening: ["interview", "offer", "rejected", "withdrawn"],
  interview: ["offer", "rejected", "withdrawn"],
  offer: [],
  rejected: [],
  withdrawn: [],
};

function formatDate(value: string | null) {
  if (!value) return "未设置";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function toLocalInput(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export function ApplicationPanel({ apiBase }: { apiBase: string }) {
  const [jobs, setJobs] = useState<JobOption[]>([]);
  const [resumes, setResumes] = useState<ResumeOption[]>([]);
  const [greetings, setGreetings] = useState<GreetingOption[]>([]);
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | "">("");
  const [selectedResumeId, setSelectedResumeId] = useState<number | "">("");
  const [selectedGreetingId, setSelectedGreetingId] = useState<number | "">("");
  const [channel, setChannel] = useState("手动记录");
  const [notes, setNotes] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "">("");
  const [current, setCurrent] = useState<ApplicationRecord | null>(null);
  const [detailChannel, setDetailChannel] = useState("");
  const [detailNotes, setDetailNotes] = useState("");
  const [detailFollowUp, setDetailFollowUp] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [nextStatus, setNextStatus] = useState<ApplicationStatus | "">("");
  const [statusNote, setStatusNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("正在读取投递记录...");

  async function loadApplications(filter = statusFilter) {
    const params = new URLSearchParams();
    if (filter) params.set("application_status", filter);
    const response = await fetch(`${apiBase}/api/applications${params.toString() ? `?${params}` : ""}`, { cache: "no-store" });
    if (!response.ok) throw new Error("无法读取投递记录");
    const records = (await response.json()) as ApplicationRecord[];
    setApplications(records);
    return records;
  }

  useEffect(() => {
    Promise.all([
      fetch(`${apiBase}/api/jobs`, { cache: "no-store" }),
      fetch(`${apiBase}/api/resumes`, { cache: "no-store" }),
      fetch(`${apiBase}/api/greetings`, { cache: "no-store" }),
      fetch(`${apiBase}/api/applications`, { cache: "no-store" }),
    ]).then(async ([jobsResponse, resumesResponse, greetingsResponse, applicationsResponse]) => {
      if (![jobsResponse, resumesResponse, greetingsResponse, applicationsResponse].every((response) => response.ok)) throw new Error("无法读取投递数据");
      const nextJobs = (await jobsResponse.json()) as JobOption[];
      const nextResumes = (await resumesResponse.json()) as ResumeOption[];
      const nextGreetings = (await greetingsResponse.json()) as GreetingOption[];
      const nextApplications = (await applicationsResponse.json()) as ApplicationRecord[];
      setJobs(nextJobs);
      setResumes(nextResumes);
      setGreetings(nextGreetings.filter((greeting) => greeting.status === "approved"));
      setApplications(nextApplications);
      setSelectedJobId(nextJobs[0]?.id ?? "");
      setSelectedResumeId(nextResumes[0]?.id ?? "");
      if (nextApplications[0]) selectApplication(nextApplications[0]);
      setMessage(nextJobs.length && nextResumes.length ? "可以创建待确认投递记录" : "请先准备职位和简历");
    }).catch((error: unknown) => setMessage(error instanceof Error ? error.message : "加载失败")).finally(() => setLoading(false));
  }, [apiBase]);

  const availableGreetings = greetings.filter((greeting) => greeting.job_id === selectedJobId && greeting.resume_id === selectedResumeId);

  function selectApplication(record: ApplicationRecord) {
    setCurrent(record);
    setDetailChannel(record.channel);
    setDetailNotes(record.notes);
    setDetailFollowUp(toLocalInput(record.next_follow_up_at));
    setConfirmed(false);
    setNextStatus(nextStatuses[record.status][0] ?? "");
    setStatusNote("");
  }

  async function createApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedJobId || !selectedResumeId) return;
    setWorking(true);
    setMessage("正在创建待确认记录...");
    try {
      const response = await fetch(`${apiBase}/api/applications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: selectedJobId, resume_id: selectedResumeId, greeting_id: selectedGreetingId || null, channel, notes, next_follow_up_at: followUp ? new Date(followUp).toISOString() : null }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "创建失败");
      }
      const record = (await response.json()) as ApplicationRecord;
      const records = await loadApplications();
      if (records.some((item) => item.id === record.id)) selectApplication(record);
      setMessage("待确认记录已创建，尚未标记为已投递");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建失败");
    } finally {
      setWorking(false);
    }
  }

  async function saveDetails() {
    if (!current) return;
    setWorking(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${current.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: detailChannel, notes: detailNotes, next_follow_up_at: detailFollowUp ? new Date(detailFollowUp).toISOString() : null }),
      });
      if (!response.ok) throw new Error("保存失败");
      const saved = (await response.json()) as ApplicationRecord;
      setApplications((items) => items.map((item) => item.id === saved.id ? saved : item));
      selectApplication(saved);
      setMessage("投递详情已保存");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setWorking(false);
    }
  }

  async function confirmSubmitted() {
    if (!current || !confirmed) return;
    setWorking(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${current.id}/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmed: true }) });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "确认失败");
      }
      const updated = (await response.json()) as ApplicationRecord;
      setApplications((items) => items.map((item) => item.id === updated.id ? updated : item));
      selectApplication(updated);
      setMessage("已记录为用户确认投递；未执行外部平台操作");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认失败");
    } finally {
      setWorking(false);
    }
  }

  async function advanceStatus() {
    if (!current || !nextStatus) return;
    setWorking(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${current.id}/status`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: nextStatus, note: statusNote }) });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "状态更新失败");
      }
      const updated = (await response.json()) as ApplicationRecord;
      setApplications((items) => items.map((item) => item.id === updated.id ? updated : item));
      selectApplication(updated);
      setMessage(`状态已更新为：${statusLabels[updated.status]}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "状态更新失败");
    } finally {
      setWorking(false);
    }
  }

  async function deleteApplication() {
    if (!current || !window.confirm("确定删除当前投递记录吗？")) return;
    setWorking(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${current.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败");
      const records = await loadApplications();
      if (records[0]) selectApplication(records[0]); else setCurrent(null);
      setMessage("投递记录已删除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    } finally {
      setWorking(false);
    }
  }

  async function filterApplications(value: ApplicationStatus | "") {
    setStatusFilter(value);
    setLoading(true);
    try {
      const records = await loadApplications(value);
      if (records[0]) selectApplication(records[0]); else setCurrent(null);
      setMessage(`当前显示 ${records.length} 条记录`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "筛选失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><h2 className="text-xl font-semibold">投递记录</h2><p className="mt-1 text-sm text-muted">记录确认、进度与结果；所有操作只修改本地记录。</p></div><span className="text-xs text-muted" aria-live="polite">{loading ? "加载中" : message}</span></div>

      <form onSubmit={createApplication} className="border-y border-slate-200 py-5">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <label className="field-label"><span>职位</span><select value={selectedJobId} onChange={(event) => { setSelectedJobId(event.target.value ? Number(event.target.value) : ""); setSelectedGreetingId(""); }} disabled={loading || working}><option value="">请选择职位</option>{jobs.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company_name}</option>)}</select></label>
          <label className="field-label"><span>简历</span><select value={selectedResumeId} onChange={(event) => { setSelectedResumeId(event.target.value ? Number(event.target.value) : ""); setSelectedGreetingId(""); }} disabled={loading || working}><option value="">请选择简历</option>{resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.title} · v{resume.version}</option>)}</select></label>
          <label className="field-label"><span>已定稿沟通内容</span><select value={selectedGreetingId} onChange={(event) => setSelectedGreetingId(event.target.value ? Number(event.target.value) : "")} disabled={loading || working}><option value="">不关联</option>{availableGreetings.map((greeting) => <option key={greeting.id} value={greeting.id}>沟通记录 #{greeting.id}</option>)}</select></label>
          <label className="field-label"><span>渠道</span><input value={channel} onChange={(event) => setChannel(event.target.value)} placeholder="智联招聘、官网、邮件" /></label>
          <label className="field-label sm:col-span-2"><span>下次跟进时间</span><input type="datetime-local" value={followUp} onChange={(event) => setFollowUp(event.target.value)} /></label>
          <label className="field-label sm:col-span-2"><span>备注</span><input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="例如：等待用户手动投递" /></label>
        </div>
        <div className="mt-4 flex justify-end"><button type="submit" className="button-primary" disabled={loading || working || !selectedJobId || !selectedResumeId}>创建待确认记录</button></div>
      </form>

      <div className="mt-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><h3 className="text-base font-semibold">记录列表 ({applications.length})</h3><select className="application-filter" value={statusFilter} onChange={(event) => void filterApplications(event.target.value as ApplicationStatus | "")}><option value="">全部状态</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>

      <div className="mt-4 grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="divide-y divide-slate-200 border-y border-slate-200 xl:border-r xl:pr-5">
          {applications.map((record) => <button key={record.id} type="button" className={`application-list-item ${current?.id === record.id ? "application-list-active" : ""}`} onClick={() => selectApplication(record)}><span className="flex items-center justify-between gap-2"><strong>{record.job_title}</strong><span className={`application-status application-status-${record.status}`}>{statusLabels[record.status]}</span></span><span className="mt-1 block text-xs text-muted">{record.company_name || "公司未填写"}</span><span className="mt-1 block text-xs text-muted">更新于 {formatDate(record.updated_at)}</span></button>)}
          {!applications.length && <p className="py-8 text-center text-sm text-muted">暂无符合条件的投递记录</p>}
        </aside>

        {current ? <article>
          <div className="flex flex-col justify-between gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-start"><div><p className="text-sm text-muted">{current.company_name || "公司未填写"}</p><h3 className="mt-1 text-lg font-semibold">{current.job_title}</h3><p className="mt-1 text-xs text-muted">简历：{current.resume_title} · 投递时间：{formatDate(current.applied_at)}</p></div><span className={`application-status application-status-${current.status}`}>{statusLabels[current.status]}</span></div>

          <div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="field-label"><span>渠道</span><input value={detailChannel} onChange={(event) => setDetailChannel(event.target.value)} /></label><label className="field-label"><span>下次跟进</span><input type="datetime-local" value={detailFollowUp} onChange={(event) => setDetailFollowUp(event.target.value)} /></label></div>
          <label className="field-label mt-4"><span>备注</span><textarea rows={4} value={detailNotes} onChange={(event) => setDetailNotes(event.target.value)} /></label>
          <div className="mt-4 flex justify-end"><button type="button" className="button-secondary" disabled={working} onClick={() => void saveDetails()}>保存详情</button></div>

          {current.status === "prepared" && <div className="mt-6 border-t border-slate-200 pt-5"><label className="confirmation-row"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>我确认已经自行完成该岗位投递，仅将本地记录更新为“已投递”。</span></label><div className="mt-3 flex justify-end"><button type="button" className="button-primary" disabled={!confirmed || working} onClick={() => void confirmSubmitted()}>确认已投递</button></div><p className="mt-2 text-right text-xs text-muted">此操作不会访问或操作招聘平台。</p></div>}

          {nextStatuses[current.status].length > 0 && current.status !== "prepared" && <div className="mt-6 border-t border-slate-200 pt-5"><h4 className="text-sm font-semibold">更新进度</h4><div className="mt-3 grid gap-3 sm:grid-cols-[180px_minmax(0,1fr)_auto]"><select className="application-filter" value={nextStatus} onChange={(event) => setNextStatus(event.target.value as ApplicationStatus)}>{nextStatuses[current.status].map((value) => <option key={value} value={value}>{statusLabels[value]}</option>)}</select><input className="application-note" value={statusNote} onChange={(event) => setStatusNote(event.target.value)} placeholder="状态说明（可选）" /><button type="button" className="button-primary" disabled={!nextStatus || working} onClick={() => void advanceStatus()}>更新</button></div></div>}

          <div className="mt-6 border-t border-slate-200 pt-5"><h4 className="text-sm font-semibold">状态时间线</h4><ol className="application-timeline mt-4">{current.status_history.map((event, index) => <li key={`${event.timestamp}-${index}`}><span /><div><strong>{statusLabels[event.status]}</strong><p>{formatDate(event.timestamp)}{event.note ? ` · ${event.note}` : ""}</p></div></li>)}</ol></div>

          <div className="mt-5 flex justify-end border-t border-slate-200 pt-5"><button type="button" className="button-secondary" disabled={working} onClick={() => void deleteApplication()}>删除记录</button></div>
        </article> : <div className="empty-panel">选择一条投递记录查看详情和状态时间线。</div>}
      </div>
    </section>
  );
}
