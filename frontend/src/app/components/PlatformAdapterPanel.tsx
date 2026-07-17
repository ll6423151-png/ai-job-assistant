"use client";

import { FormEvent, useEffect, useState } from "react";

type AdapterInfo = {
  key: string;
  name: string;
  description: string;
  capabilities: string[];
  supports_external_search: boolean;
  supports_application_submit: boolean;
};

type JobPayload = {
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
};

type Preview = { adapter: AdapterInfo; normalized_job: JobPayload; warnings: string[] };
type ImportResult = { adapter_key: string; job: JobPayload & { id: number }; message: string };

const emptyJob: JobPayload = { title: "", company_name: "", city: "", salary_min: null, salary_max: null, degree_required: "不限", experience_required: "不限", company_size: "不限", description: "", source_platform: "手动导入", source_url: "", status: "open" };

export function PlatformAdapterPanel({ apiBase }: { apiBase: string }) {
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [job, setJob] = useState<JobPayload>(emptyJob);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("正在读取适配器...");

  useEffect(() => {
    fetch(`${apiBase}/api/platform-adapters`, { cache: "no-store" })
      .then(async (response) => { if (!response.ok) throw new Error("无法读取适配器"); return response.json() as Promise<AdapterInfo[]>; })
      .then((items) => { setAdapters(items); setSelectedKey(items[0]?.key ?? ""); setMessage(`已注册 ${items.length} 个适配器`); })
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [apiBase]);

  function updateField<K extends keyof JobPayload>(field: K, value: JobPayload[K]) {
    setJob((current) => ({ ...current, [field]: value }));
    setPreview(null);
    setConfirmed(false);
    setResult(null);
  }

  async function previewImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedKey) return;
    setWorking(true);
    setMessage("正在规范化职位数据...");
    try {
      const response = await fetch(`${apiBase}/api/platform-adapters/${selectedKey}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job }) });
      if (!response.ok) { const detail = await response.json().catch(() => null); throw new Error(detail?.detail ?? "预览失败"); }
      const nextPreview = (await response.json()) as Preview;
      setPreview(nextPreview);
      setConfirmed(false);
      setMessage("预览已生成，请核对后确认导入");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "预览失败");
    } finally {
      setWorking(false);
    }
  }

  async function confirmImport() {
    if (!preview || !confirmed) return;
    setWorking(true);
    setMessage("正在导入本地职位库...");
    try {
      const response = await fetch(`${apiBase}/api/platform-adapters/${selectedKey}/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job: preview.normalized_job, confirmed: true }) });
      if (!response.ok) { const detail = await response.json().catch(() => null); throw new Error(detail?.detail ?? "导入失败"); }
      const imported = (await response.json()) as ImportResult;
      setResult(imported);
      setConfirmed(false);
      setMessage(`职位 #${imported.job.id} 已导入`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导入失败");
    } finally {
      setWorking(false);
    }
  }

  const selectedAdapter = adapters.find((adapter) => adapter.key === selectedKey);

  return <section>
    <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><h2 className="text-xl font-semibold">平台适配器</h2><p className="mt-1 text-sm text-muted">通过统一接口导入职位数据；当前不抓取招聘平台，也不执行投递。</p></div><span className="text-xs text-muted" aria-live="polite">{loading ? "加载中" : message}</span></div>

    <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
      <aside><h3 className="text-sm font-semibold">已注册适配器 ({adapters.length})</h3><div className="mt-3 divide-y divide-slate-200 border-y border-slate-200">{adapters.map((adapter) => <button key={adapter.key} type="button" className={`adapter-item ${selectedKey === adapter.key ? "adapter-item-active" : ""}`} onClick={() => { setSelectedKey(adapter.key); setPreview(null); setResult(null); }}><strong>{adapter.name}</strong><span>{adapter.description}</span><div><small>{adapter.supports_external_search ? "支持外部搜索" : "不支持外部搜索"}</small><small>{adapter.supports_application_submit ? "支持提交" : "不支持提交"}</small></div></button>)}</div></aside>

      <div>
        {selectedAdapter && <div className="adapter-summary"><div><span>适配器标识</span><strong>{selectedAdapter.key}</strong></div><div><span>能力</span><strong>{selectedAdapter.capabilities.join(" / ")}</strong></div><div><span>本页面边界</span><strong>仅预览和确认导入</strong></div></div>}

        <form onSubmit={previewImport} className="mt-6 space-y-5">
          <div className="grid gap-4 sm:grid-cols-2"><label className="field-label"><span>岗位名称 *</span><input required value={job.title} onChange={(event) => updateField("title", event.target.value)} /></label><label className="field-label"><span>公司名称</span><input value={job.company_name} onChange={(event) => updateField("company_name", event.target.value)} /></label><label className="field-label"><span>城市</span><input value={job.city} onChange={(event) => updateField("city", event.target.value)} /></label><label className="field-label"><span>原始链接</span><input type="url" value={job.source_url} onChange={(event) => updateField("source_url", event.target.value)} placeholder="https://..." /></label><label className="field-label"><span>最低月薪</span><input type="number" min={0} value={job.salary_min ?? ""} onChange={(event) => updateField("salary_min", event.target.value ? Number(event.target.value) : null)} /></label><label className="field-label"><span>最高月薪</span><input type="number" min={0} value={job.salary_max ?? ""} onChange={(event) => updateField("salary_max", event.target.value ? Number(event.target.value) : null)} /></label><label className="field-label"><span>学历</span><select value={job.degree_required} onChange={(event) => updateField("degree_required", event.target.value)}><option>不限</option><option>大专</option><option>本科</option><option>硕士</option></select></label><label className="field-label"><span>经验</span><select value={job.experience_required} onChange={(event) => updateField("experience_required", event.target.value)}><option>不限</option><option>应届生/实习生</option><option>1年以内</option><option>1-3年</option><option>3年以上</option></select></label><label className="field-label sm:col-span-2"><span>公司规模</span><select value={job.company_size} onChange={(event) => updateField("company_size", event.target.value)}><option>不限</option><option>初创公司</option><option>中小企业</option><option>中大型企业</option><option>上市公司</option></select></label></div>
          <label className="field-label"><span>职位描述（JD）</span><textarea rows={10} value={job.description} onChange={(event) => updateField("description", event.target.value)} /></label>
          <div className="flex justify-end"><button type="submit" className="button-primary" disabled={loading || working || !selectedKey}>生成导入预览</button></div>
        </form>

        {preview && <div className="mt-7 border-t border-slate-200 pt-6"><div className="flex items-center justify-between gap-3"><h3 className="text-base font-semibold">规范化预览</h3><span className="status-done">{preview.adapter.name}</span></div><dl className="adapter-preview mt-4"><div><dt>岗位</dt><dd>{preview.normalized_job.title}</dd></div><div><dt>公司</dt><dd>{preview.normalized_job.company_name || "未填写"}</dd></div><div><dt>城市</dt><dd>{preview.normalized_job.city || "未填写"}</dd></div><div><dt>来源</dt><dd>{preview.normalized_job.source_platform}</dd></div></dl>{preview.warnings.length > 0 && <ul className="mt-4 space-y-1 text-sm text-amber-700">{preview.warnings.map((warning) => <li key={warning}>· {warning}</li>)}</ul>}<label className="confirmation-row mt-5"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>我已核对职位数据，并确认将其导入本地职位库。</span></label><div className="mt-4 flex justify-end"><button type="button" className="button-primary" disabled={!confirmed || working} onClick={() => void confirmImport()}>确认导入</button></div></div>}

        {result && <div className="check-result check-result-clear mt-5"><strong>导入成功：职位 #{result.job.id}</strong><span>{result.message}</span></div>}
      </div>
    </div>
  </section>;
}
