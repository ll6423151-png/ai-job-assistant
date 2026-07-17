"use client";

import { FormEvent, useEffect, useState } from "react";

type BlacklistRule = {
  id: number;
  company_name: string;
  match_type: "exact" | "contains";
  reason: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type RuleForm = Omit<BlacklistRule, "id" | "created_at" | "updated_at">;

type CheckResult = {
  company_name: string;
  matched: boolean;
  reason: string | null;
  rule_id: number | null;
  match_type: "exact" | "contains" | null;
};

const emptyRule: RuleForm = {
  company_name: "",
  match_type: "exact",
  reason: "",
  is_active: true,
};

function ruleToForm(rule: BlacklistRule): RuleForm {
  const { id: _id, created_at: _createdAt, updated_at: _updatedAt, ...form } = rule;
  return form;
}

export function BlacklistPanel({ apiBase }: { apiBase: string }) {
  const [rules, setRules] = useState<BlacklistRule[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<RuleForm>(emptyRule);
  const [companyToCheck, setCompanyToCheck] = useState("");
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("正在读取黑名单...");

  async function loadRules(selectId?: number | null) {
    const response = await fetch(`${apiBase}/api/blacklist`, { cache: "no-store" });
    if (!response.ok) throw new Error("无法读取黑名单规则");
    const nextRules = (await response.json()) as BlacklistRule[];
    setRules(nextRules);
    if (selectId !== undefined) {
      const selected = nextRules.find((rule) => rule.id === selectId);
      setSelectedId(selected?.id ?? null);
      setForm(selected ? ruleToForm(selected) : emptyRule);
    }
    return nextRules;
  }

  useEffect(() => {
    loadRules()
      .then((items) => setMessage(`已加载 ${items.length} 条规则`))
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [apiBase]);

  function updateField<K extends keyof RuleForm>(field: K, value: RuleForm[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function selectRule(rule: BlacklistRule) {
    setSelectedId(rule.id);
    setForm(ruleToForm(rule));
    setEditorOpen(true);
    setMessage("已打开规则");
  }

  function startNew() {
    setSelectedId(null);
    setForm(emptyRule);
    setEditorOpen(true);
    setMessage("正在新增规则");
  }

  async function saveRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("正在保存规则...");
    const endpoint = selectedId ? `${apiBase}/api/blacklist/${selectedId}` : `${apiBase}/api/blacklist`;
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
      const saved = (await response.json()) as BlacklistRule;
      await loadRules(saved.id);
      setMessage("黑名单规则已保存");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  async function deleteRule() {
    if (!selectedId || !window.confirm("确定删除当前黑名单规则吗？")) return;
    setSaving(true);
    setMessage("正在删除规则...");
    try {
      const response = await fetch(`${apiBase}/api/blacklist/${selectedId}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败");
      await loadRules();
      setSelectedId(null);
      setForm(emptyRule);
      setEditorOpen(false);
      setMessage("黑名单规则已删除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  async function checkCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!companyToCheck.trim()) return;
    setMessage("正在检查公司名称...");
    try {
      const params = new URLSearchParams({ company_name: companyToCheck.trim() });
      const response = await fetch(`${apiBase}/api/blacklist/check?${params.toString()}`);
      if (!response.ok) throw new Error("检查失败");
      setCheckResult((await response.json()) as CheckResult);
      setMessage("检查完成");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "检查失败，请稍后重试");
    }
  }

  return (
    <section>
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-xl font-semibold">公司黑名单</h2>
          <p className="mt-1 text-sm text-muted">启用规则会自动过滤职位搜索结果，并保留明确的命中原因。</p>
        </div>
        <span className="text-xs text-muted" aria-live="polite">{loading ? "加载中" : message}</span>
      </div>

      <form onSubmit={checkCompany} className="border-y border-slate-200 py-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="field-label flex-1">
            <span>检查公司是否命中</span>
            <input value={companyToCheck} onChange={(event) => setCompanyToCheck(event.target.value)} placeholder="输入完整或部分公司名称" />
          </label>
          <button type="submit" className="button-primary" disabled={!companyToCheck.trim()}>检查</button>
        </div>
        {checkResult && (
          <div className={`mt-4 check-result ${checkResult.matched ? "check-result-blocked" : "check-result-clear"}`}>
            <strong>{checkResult.matched ? "已命中黑名单" : "未命中黑名单"}</strong>
            <span>{checkResult.matched ? `原因：${checkResult.reason || "未填写原因"}` : "该公司当前不会被过滤。"}</span>
          </div>
        )}
      </form>

      <div className="mt-6 flex items-center justify-between gap-4">
        <h3 className="text-base font-semibold">规则列表 ({rules.length})</h3>
        <button type="button" className="button-secondary compact-button" onClick={startNew} disabled={saving}>新增规则</button>
      </div>

      <div className={`mt-4 grid gap-6 ${editorOpen ? "xl:grid-cols-[minmax(0,1fr)_360px]" : ""}`}>
        <div className="divide-y divide-slate-200 border-y border-slate-200">
          {rules.map((rule) => (
            <button key={rule.id} type="button" className={`blacklist-item ${selectedId === rule.id ? "blacklist-item-active" : ""}`} onClick={() => selectRule(rule)}>
              <span className="flex items-center justify-between gap-3">
                <strong>{rule.company_name}</strong>
                <span className={rule.is_active ? "status-danger" : "status-next"}>{rule.is_active ? "已启用" : "已停用"}</span>
              </span>
              <span className="mt-2 block text-xs text-muted">匹配方式：{rule.match_type === "exact" ? "完整名称" : "名称包含"}</span>
              <span className="mt-1 block text-sm text-muted">{rule.reason || "未填写原因"}</span>
            </button>
          ))}
          {!rules.length && <div className="py-10 text-center text-sm leading-6 text-muted">还没有黑名单规则。新增规则后，职位搜索会自动应用。</div>}
        </div>

        {editorOpen && (
          <form onSubmit={saveRule} className="space-y-4 border-l border-slate-200 pl-0 xl:pl-6">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-base font-semibold">{selectedId ? "编辑规则" : "新增规则"}</h3>
              <button type="button" className="text-sm text-muted hover:text-ink" onClick={() => setEditorOpen(false)}>关闭</button>
            </div>
            <fieldset disabled={saving} className="space-y-4">
              <label className="field-label">
                <span>公司名称 *</span>
                <input required maxLength={160} value={form.company_name} onChange={(event) => updateField("company_name", event.target.value)} placeholder="例如：某某科技有限公司" />
              </label>
              <label className="field-label">
                <span>匹配方式</span>
                <select value={form.match_type} onChange={(event) => updateField("match_type", event.target.value as RuleForm["match_type"])}>
                  <option value="exact">完整名称匹配</option>
                  <option value="contains">名称包含匹配</option>
                </select>
                <small>包含匹配适合集团名、品牌名等多种写法。</small>
              </label>
              <label className="field-label">
                <span>加入原因</span>
                <textarea rows={5} maxLength={500} value={form.reason} onChange={(event) => updateField("reason", event.target.value)} placeholder="例如：已知不符合求职偏好" />
              </label>
              <label className="checkbox-option w-fit">
                <input type="checkbox" checked={form.is_active} onChange={(event) => updateField("is_active", event.target.checked)} />
                <span>启用这条规则</span>
              </label>
            </fieldset>
            <div className="flex flex-wrap justify-end gap-3 border-t border-slate-200 pt-4">
              <button type="button" className="button-secondary" disabled={!selectedId || saving} onClick={() => void deleteRule()}>删除</button>
              <button type="submit" className="button-primary" disabled={saving}>{saving ? "处理中..." : "保存规则"}</button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}
