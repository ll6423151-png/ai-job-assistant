"use client";

import { FileUp } from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type Resume = {
  id: number;
  title: string;
  target_role: string;
  version: number;
  status: "draft" | "ready";
  content: string;
  notes: string;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
};

type ResumeForm = Omit<Resume, "id" | "created_at" | "updated_at">;

const emptyResume: ResumeForm = {
  title: "",
  target_role: "",
  version: 1,
  status: "draft",
  content: "",
  notes: "",
  is_primary: false,
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function ResumePanel({ apiBase }: { apiBase: string }) {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<ResumeForm>(emptyResume);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("正在读取简历...");

  async function loadResumes(selectId?: number | null) {
    const response = await fetch(`${apiBase}/api/resumes`, { cache: "no-store" });
    if (!response.ok) throw new Error("无法读取简历列表");
    const nextResumes = (await response.json()) as Resume[];
    setResumes(nextResumes);
    const nextId = selectId ?? nextResumes[0]?.id ?? null;
    const selected = nextResumes.find((item) => item.id === nextId);
    setSelectedId(selected?.id ?? null);
    setForm(selected ? resumeToForm(selected) : emptyResume);
  }

  useEffect(() => {
    loadResumes()
      .then(() => setMessage("简历列表已加载"))
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [apiBase]);

  function resumeToForm(resume: Resume): ResumeForm {
    return {
      title: resume.title,
      target_role: resume.target_role,
      version: resume.version,
      status: resume.status,
      content: resume.content,
      notes: resume.notes,
      is_primary: resume.is_primary,
    };
  }

  function updateField<K extends keyof ResumeForm>(field: K, value: ResumeForm[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function selectResume(resume: Resume) {
    setSelectedId(resume.id);
    setForm(resumeToForm(resume));
    setMessage("已切换版本");
  }

  function startNew() {
    setSelectedId(null);
    setForm(emptyResume);
    setMessage("正在创建新版本");
  }

  async function saveResume(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("正在保存...");
    const method = selectedId ? "PUT" : "POST";
    const endpoint = selectedId ? `${apiBase}/api/resumes/${selectedId}` : `${apiBase}/api/resumes`;

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
      const saved = (await response.json()) as Resume;
      await loadResumes(saved.id);
      setMessage("简历版本已保存");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  async function deleteResume() {
    if (!selectedId || !window.confirm("确定删除当前简历版本吗？")) return;
    setSaving(true);
    setMessage("正在删除...");
    try {
      const response = await fetch(`${apiBase}/api/resumes/${selectedId}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败");
      await loadResumes(null);
      setMessage("简历版本已删除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  async function uploadResume(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage(`正在上传并解析 ${file.name}...`);
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(`${apiBase}/api/resume-uploads`, { method: "POST", body });
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(error?.detail ?? "上传或解析失败");
      }
      const result = (await response.json()) as { resume_id: number; extracted_characters: number };
      await loadResumes(result.resume_id);
      setMessage(`${file.name} 上传成功，已解析 ${result.extracted_characters} 个字符；请检查内容后再设为可投递`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传或解析失败，请稍后重试");
    } finally {
      setUploading(false);
      input.value = "";
    }
  }

  return (
    <section>
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-xl font-semibold">简历版本</h2>
          <p className="mt-1 text-sm text-muted">每条记录代表一个可独立编辑的简历版本，后续可用于 JD 匹配。</p>
        </div>
        <span className="text-xs text-muted" aria-live="polite">{loading ? "加载中" : message}</span>
      </div>

      <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="border-y border-slate-200 xl:border-y-0 xl:border-r xl:pr-6">
          <div className="flex items-center justify-between gap-3 pb-3">
            <h3 className="text-sm font-semibold">已保存版本 ({resumes.length})</h3>
            <button type="button" className="button-secondary compact-button" onClick={startNew} disabled={saving || uploading}>新建</button>
          </div>
          <div className="divide-y divide-slate-200">
            {resumes.map((resume) => (
              <button key={resume.id} type="button" onClick={() => selectResume(resume)} className={`resume-list-item ${selectedId === resume.id ? "resume-list-item-active" : ""}`}>
                <span className="flex items-center justify-between gap-2">
                  <strong>{resume.title}</strong>
                  {resume.is_primary && <span className="status-done">主版本</span>}
                </span>
                <span className="mt-1 block text-xs text-muted">{resume.target_role || "未设置目标岗位"} · v{resume.version}</span>
                <span className="mt-1 block text-xs text-muted">更新于 {formatDate(resume.updated_at)}</span>
              </button>
            ))}
            {!resumes.length && <p className="py-6 text-sm leading-6 text-muted">还没有简历版本。点击“新建”开始整理第一份简历。</p>}
          </div>
        </aside>

        <form onSubmit={saveResume} className="space-y-6">
          <section className="border-y border-slate-200 py-5" aria-labelledby="resume-upload-heading">
            <div className="flex items-center gap-2"><FileUp size={17} className="text-brand" /><h3 id="resume-upload-heading" className="text-sm font-semibold">上传并解析简历</h3></div>
            <p className="mt-2 text-xs leading-5 text-muted">支持 PDF、DOCX、TXT、Markdown。上传成功后会创建一个草稿版本并自动选中，不会覆盖现有简历。</p>
            <label className={`upload-drop mt-4 ${uploading || loading || saving ? "upload-drop-disabled" : ""}`}>
              <input type="file" accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown" disabled={uploading || loading || saving} onChange={uploadResume} />
              <FileUp size={20} />
              <span>{uploading ? "正在上传并解析..." : "点击选择简历文件"}</span>
            </label>
            <p className="mt-3 text-xs leading-5 text-muted">单个文件大小受服务器配置限制。扫描图片型 PDF 需要先转为可复制文字；解析后请核对正文再设为“可投递”。</p>
          </section>

          <fieldset disabled={loading || saving || uploading} className="space-y-6">
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="field-label">
                <span>简历名称 *</span>
                <input required maxLength={120} value={form.title} onChange={(event) => updateField("title", event.target.value)} placeholder="例如：短视频运营实习生简历" />
              </label>
              <label className="field-label">
                <span>目标岗位</span>
                <input maxLength={120} value={form.target_role} onChange={(event) => updateField("target_role", event.target.value)} placeholder="例如：短视频运营 / 直播运营" />
              </label>
              <label className="field-label">
                <span>版本号</span>
                <input type="number" min={1} max={100} value={form.version} onChange={(event) => updateField("version", Number(event.target.value))} />
              </label>
              <label className="field-label">
                <span>状态</span>
                <select value={form.status} onChange={(event) => updateField("status", event.target.value as ResumeForm["status"])}>
                  <option value="draft">草稿</option>
                  <option value="ready">可投递</option>
                </select>
              </label>
            </div>

            <label className="checkbox-option w-fit">
              <input type="checkbox" checked={form.is_primary} onChange={(event) => updateField("is_primary", event.target.checked)} />
              <span>设为主版本</span>
            </label>

            <label className="field-label">
              <span>简历内容</span>
              <textarea rows={18} maxLength={50000} value={form.content} onChange={(event) => updateField("content", event.target.value)} placeholder="粘贴或输入简历正文，后续 JD 匹配模块会读取这里的内容。" />
            </label>

            <label className="field-label">
              <span>版本备注</span>
              <textarea rows={3} maxLength={2000} value={form.notes} onChange={(event) => updateField("notes", event.target.value)} placeholder="例如：针对重庆短视频运营实习岗位调整" />
            </label>
          </fieldset>

          <div className="flex flex-col-reverse gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:justify-end">
            <button type="button" className="button-secondary" disabled={!selectedId || loading || saving || uploading} onClick={() => void deleteResume()}>删除版本</button>
            <button type="submit" className="button-primary" disabled={loading || saving || uploading}>{saving ? "处理中..." : "保存版本"}</button>
          </div>
        </form>
      </div>
    </section>
  );
}
