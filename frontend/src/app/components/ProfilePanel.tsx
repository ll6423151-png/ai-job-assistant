"use client";

import { Plus, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

type JobKeyword = { id: number; keyword: string; is_active: boolean };

type Profile = {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  current_city: string;
  preferred_cities: string[];
  target_roles: string[];
  salary_min: number | null;
  salary_max: number | null;
  degree: string;
  experience_level: string;
  company_sizes: string[];
  portfolio_url: string;
  summary: string;
  updated_at: string;
};

type ProfileForm = Omit<Profile, "id" | "updated_at" | "preferred_cities" | "target_roles" | "company_sizes"> & {
  preferred_cities: string;
  target_roles: string;
  company_sizes: string[];
};

const emptyForm: ProfileForm = {
  full_name: "",
  email: "",
  phone: "",
  current_city: "",
  preferred_cities: "",
  target_roles: "",
  salary_min: null,
  salary_max: null,
  degree: "",
  experience_level: "",
  company_sizes: [],
  portfolio_url: "",
  summary: "",
};

const companySizeOptions = ["初创公司", "中小企业", "中大型企业", "上市公司"];

function listToText(values: string[]) {
  return values.join(", ");
}

function textToList(value: string) {
  return [...new Set(value.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean))];
}

function formFromProfile(profile: Profile): ProfileForm {
  return {
    ...profile,
    preferred_cities: listToText(profile.preferred_cities),
    target_roles: listToText(profile.target_roles),
  };
}

export function ProfilePanel({ apiBase }: { apiBase: string }) {
  const [form, setForm] = useState<ProfileForm>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("正在读取资料...");
  const [hasProfile, setHasProfile] = useState(false);
  const [jobKeywords, setJobKeywords] = useState<JobKeyword[]>([]);
  const [newKeyword, setNewKeyword] = useState("");

  useEffect(() => {
    async function loadProfile() {
      try {
        const response = await fetch(`${apiBase}/api/user-profile`, { cache: "no-store" });
        if (!response.ok) throw new Error("无法读取资料");
        const profile = (await response.json()) as Profile | null;
        if (profile) {
          setForm(formFromProfile(profile));
          setHasProfile(true);
          setMessage("资料已加载");
        } else {
          setMessage("还没有资料，填写后保存");
        }
      } catch {
        setMessage("无法连接后端，请确认 API 已启动");
      } finally {
        setLoading(false);
      }
    }

    void loadProfile();
  }, [apiBase]);

  useEffect(() => {
    fetch(`${apiBase}/api/job-keywords`, { cache: "no-store" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((items: JobKeyword[]) => setJobKeywords(items))
      .catch(() => setMessage("岗位屏蔽关键词读取失败"));
  }, [apiBase]);

  async function addJobKeyword() {
    const keyword = newKeyword.trim();
    if (!keyword) return;
    setSaving(true);
    try {
      const response = await fetch(`${apiBase}/api/job-keywords`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ keyword, is_active: true }) });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail ?? "保存失败");
      setJobKeywords((items) => [body as JobKeyword, ...items]);
      setNewKeyword("");
      setMessage(`已屏蔽岗位关键词：${keyword}`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "保存失败"); }
    finally { setSaving(false); }
  }

  async function deleteJobKeyword(item: JobKeyword) {
    setSaving(true);
    try {
      const response = await fetch(`${apiBase}/api/job-keywords/${item.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败");
      setJobKeywords((items) => items.filter((keyword) => keyword.id !== item.id));
      setMessage(`已取消屏蔽：${item.keyword}`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "删除失败"); }
    finally { setSaving(false); }
  }

  function updateField<K extends keyof ProfileForm>(field: K, value: ProfileForm[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function toggleCompanySize(size: string) {
    const next = form.company_sizes.includes(size)
      ? form.company_sizes.filter((item) => item !== size)
      : [...form.company_sizes, size];
    updateField("company_sizes", next);
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("正在保存...");

    const payload = {
      ...form,
      preferred_cities: textToList(form.preferred_cities),
      target_roles: textToList(form.target_roles),
    };

    try {
      const response = await fetch(`${apiBase}/api/user-profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "保存失败");
      }
      const saved = (await response.json()) as Profile;
      setForm(formFromProfile(saved));
      setHasProfile(true);
      setMessage("已保存，后续模块会使用这些偏好");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  async function resetProfile() {
    if (!hasProfile) {
      setForm(emptyForm);
      setMessage("已清空未保存内容");
      return;
    }

    setSaving(true);
    setMessage("正在删除资料...");
    try {
      const response = await fetch(`${apiBase}/api/user-profile`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败");
      setForm(emptyForm);
      setHasProfile(false);
      setMessage("资料已删除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">基本资料与求职偏好</h2>
          <p className="mt-1 text-sm text-muted">带 * 的字段建议优先填写。</p>
        </div>
        <span className="text-right text-xs text-muted" aria-live="polite">
          {loading ? "加载中" : message}
        </span>
      </div>

      <form onSubmit={saveProfile} className="space-y-7">
        <fieldset disabled={loading || saving} className="space-y-7">
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="field-label">
              <span>姓名 *</span>
              <input required maxLength={80} value={form.full_name} onChange={(event) => updateField("full_name", event.target.value)} placeholder="请填写姓名" />
            </label>
            <label className="field-label">
              <span>当前城市</span>
              <input value={form.current_city} onChange={(event) => updateField("current_city", event.target.value)} placeholder="请填写当前城市" />
            </label>
            <label className="field-label">
              <span>邮箱 *</span>
              <input required type="email" value={form.email} onChange={(event) => updateField("email", event.target.value)} placeholder="name@example.com" />
            </label>
            <label className="field-label">
              <span>手机号</span>
              <input value={form.phone} onChange={(event) => updateField("phone", event.target.value)} placeholder="用于招聘方联系" />
            </label>
          </div>

          <div className="border-t border-slate-200 pt-7">
            <h3 className="mb-4 text-base font-semibold">求职方向</h3>
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="field-label">
                <span>目标岗位 *</span>
                <input required value={form.target_roles} onChange={(event) => updateField("target_roles", event.target.value)} placeholder="请填写目标岗位" />
                <small>多个岗位用逗号分隔</small>
              </label>
              <label className="field-label">
                <span>意向城市</span>
                <input value={form.preferred_cities} onChange={(event) => updateField("preferred_cities", event.target.value)} placeholder="请填写意向城市" />
                <small>多个城市用逗号分隔</small>
              </label>
              <label className="field-label">
                <span>学历</span>
                <select value={form.degree} onChange={(event) => updateField("degree", event.target.value)}>
                  <option value="">未填写</option>
                  <option>本科</option>
                  <option>大专</option>
                  <option>硕士</option>
                  <option>博士</option>
                  <option>其他</option>
                </select>
              </label>
              <label className="field-label">
                <span>经验阶段</span>
                <select value={form.experience_level} onChange={(event) => updateField("experience_level", event.target.value)}>
                  <option value="">未填写</option>
                  <option>应届生/实习生</option>
                  <option>1年以内</option>
                  <option>1-3年</option>
                  <option>3年以上</option>
                </select>
              </label>
            </div>
          </div>

          <div className="border-t border-slate-200 pt-7">
            <h3 className="mb-4 text-base font-semibold">筛选偏好</h3>
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="field-label">
                <span>最低月薪（元）</span>
                <input type="number" min={0} value={form.salary_min ?? ""} onChange={(event) => updateField("salary_min", event.target.value ? Number(event.target.value) : null)} placeholder="不设下限可留空" />
              </label>
              <label className="field-label">
                <span>最高月薪（元）</span>
                <input type="number" min={0} value={form.salary_max ?? ""} onChange={(event) => updateField("salary_max", event.target.value ? Number(event.target.value) : null)} placeholder="不设上限可留空" />
              </label>
            </div>
            <div className="mt-5">
              <span className="field-label">公司规模偏好</span>
              <div className="mt-3 flex flex-wrap gap-2">
                {companySizeOptions.map((size) => (
                  <label key={size} className="checkbox-option">
                    <input type="checkbox" checked={form.company_sizes.includes(size)} onChange={() => toggleCompanySize(size)} />
                    <span>{size}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="mt-5 border-t border-slate-200 pt-5">
              <label className="field-label"><span>岗位屏蔽关键词</span><div className="flex gap-2"><input value={newKeyword} onChange={(event) => setNewKeyword(event.target.value)} maxLength={50} placeholder="例如：主播" /><button type="button" className="button-secondary icon-text-button shrink-0" disabled={saving || !newKeyword.trim()} onClick={() => void addJobKeyword()}><Plus size={15} />添加</button></div><small>岗位标题或 JD 命中后，不会进入自动投递候选。</small></label>
              <div className="mt-3 flex flex-wrap gap-2">{jobKeywords.map((item) => <span key={item.id} className="job-keyword-chip">{item.keyword}<button type="button" title={`取消屏蔽 ${item.keyword}`} aria-label={`取消屏蔽 ${item.keyword}`} disabled={saving} onClick={() => void deleteJobKeyword(item)}><X size={14} /></button></span>)}{!jobKeywords.length && <span className="text-xs text-muted">暂未设置屏蔽词</span>}</div>
            </div>
          </div>

          <div className="border-t border-slate-200 pt-7">
            <h3 className="mb-4 text-base font-semibold">补充信息</h3>
            <div className="space-y-5">
              <label className="field-label">
                <span>作品集链接</span>
                <input type="url" value={form.portfolio_url} onChange={(event) => updateField("portfolio_url", event.target.value)} placeholder="https://..." />
              </label>
              <label className="field-label">
                <span>个人简介</span>
                <textarea rows={4} maxLength={500} value={form.summary} onChange={(event) => updateField("summary", event.target.value)} placeholder="可填写内容方向、工具技能或希望突出的经历。" />
              </label>
            </div>
          </div>
        </fieldset>

        <div className="flex flex-col-reverse gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:justify-end">
          <button type="button" className="button-secondary" disabled={loading || saving} onClick={() => void resetProfile()}>清空资料</button>
          <button type="submit" className="button-primary" disabled={loading || saving}>{saving ? "处理中..." : "保存资料"}</button>
        </div>
      </form>
    </section>
  );
}
