"use client";

import { ArrowRight, BookOpen, Check, Copy, HelpCircle, Search, Settings } from "lucide-react";
import { useMemo, useState } from "react";

import helpData from "../data/help-center.json";

type Guide = {
  introduction: string;
  steps: string[];
  scenarios: string[];
  aiWorkflow: string;
  inputs: string[];
  outputs: string[];
  notices: string[];
  questions: string[];
};

type Chapter = {
  id: string;
  category: string;
  title: string;
  file: string;
  status: "available" | "partial" | "planned";
  summary: string;
  keywords: string[];
  sections?: { heading: string; items: string[] }[];
  guide?: Guide;
};

type Availability = {
  reason: string;
  availableNow: string[];
  unavailable: string[];
  requirements: string[];
};

const statusLabels = { available: "可用", partial: "部分可用", planned: "规划中" };
const guideSections: [keyof Guide, string][] = [
  ["introduction", "功能介绍"], ["steps", "一步步操作"], ["scenarios", "使用场景"],
  ["aiWorkflow", "AI 工作流"], ["inputs", "用户输入"], ["outputs", "输出结果"],
  ["notices", "注意事项"], ["questions", "常见问题"],
];

const moduleAvailability: Record<string, Availability> = {
  dashboard: {
    reason: "当前没有独立 Dashboard 页面，工作台状态侧栏和数据统计页共同承担概览能力。",
    availableNow: ["查看主要功能入口与项目状态", "在数据统计中查看投递漏斗、趋势和最近活动"],
    unavailable: ["统一首页总览", "跨模块待办和风险提醒的自动汇总"],
    requirements: ["新增独立 Dashboard 页面", "确定跨模块指标口径并补齐聚合接口与测试"],
  },
  resumes: {
    reason: "简历上传、解析、编辑、主简历和可投递状态已有页面与后端接口。",
    availableNow: ["上传并解析 PDF、DOCX、TXT 和 Markdown", "维护多份简历并设置主简历与可投递状态"],
    unavailable: ["扫描图片型 PDF 的 OCR", "从智联账号自动同步平台简历"],
    requirements: ["扫描件需先经过 OCR", "平台简历仍需用户手动导出或在智联 App 内维护"],
  },
  optimization: {
    reason: "优化草稿、差距提示、人工确认和保留旧版本的流程已经存在。",
    availableNow: ["根据 JD 生成优化建议", "人工核对后应用修改并保留版本"],
    unavailable: ["真实 OpenAI 服务质量验证", "自动补写用户未提供的经历或技能"],
    requirements: ["真实 OpenAI 调用需配置有效 API Key 并完成环境验证", "所有事实必须由用户确认"],
  },
  match: {
    reason: "JD 与简历的匹配评分、关键词覆盖、差距和建议已具备完整流程。",
    availableNow: ["选择职位和简历执行匹配", "查看可解释的分数、命中项和差距"],
    unavailable: ["把匹配分数当作录用概率", "在 JD 不完整时给出可靠结论"],
    requirements: ["使用真实且完整的 JD", "仍需通过薪资、黑名单等硬规则"],
  },
  communication: {
    reason: "沟通内容可以生成、编辑、审核定稿，并作为投递任务快照保存。",
    availableNow: ["按岗位和简历生成沟通草稿", "人工修改、定稿和复制内容"],
    unavailable: ["在智联 PC 页面没有真实输入框时自动发送", "未经用户审核自动外发"],
    requirements: ["平台缺少输入框时在智联 App 手动发送", "外发前必须由用户确认"],
  },
  interview: {
    reason: "文字面试、连续追问、报告、历史、录音上传和本地转写已实现。",
    availableNow: ["进行文字或实时语音模拟面试", "上传录音转写并生成评分报告"],
    unavailable: ["所有 Android 设备都稳定支持实时语音", "缺少麦克风权限时进行实时对话"],
    requirements: ["允许麦克风权限并使用支持语音能力的环境", "不可用时使用录音上传或文字回答"],
  },
  "career-planning": {
    reason: "尚未建立独立页面、数据模型、API、规划引擎和验证测试，因此不能作为可用功能开放。",
    availableNow: ["组合用户中心、代表性 JD、匹配结果和统计数据进行人工规划"],
    unavailable: ["个性化职业路线图", "阶段目标、技能计划和进度跟踪"],
    requirements: ["先明确规划规则和输出边界", "完成数据模型、接口、页面、隐私评审和测试"],
  },
  applications: {
    reason: "本地投递记录、状态流转、时间线、备注和统计联动已经可用。",
    availableNow: ["创建并维护投递记录", "更新状态并查看时间线和跟进信息"],
    unavailable: ["用本地确认代替智联官网实际提交", "无人确认的批量投递"],
    requirements: ["最终提交必须逐条确认", "只以平台明确成功标识记录真实投递成功"],
  },
  analytics: {
    reason: "统计页能够只读汇总本软件已经保存的匹配、投递和面试数据。",
    availableNow: ["查看投递漏斗、趋势、分布和最近活动", "根据本地记录进行阶段复盘"],
    unavailable: ["实时同步智联招聘全部数据", "小样本情况下给出稳定预测"],
    requirements: ["持续维护真实投递状态", "数据量不足时只把比例作为参考"],
  },
  "knowledge-base": {
    reason: "尚未实现资料摄取、向量存储、检索接口、权限控制和来源追踪，当前不能使用。",
    availableNow: ["使用现有简历、匹配、沟通和面试历史记录", "查阅固定帮助文档"],
    unavailable: ["上传资料后智能问答", "个人知识的语义检索和引用来源"],
    requirements: ["实现用户隔离的存储、删除和来源追踪", "完成检索质量、隐私与安全测试"],
  },
  settings: {
    reason: "基础设置说明和帮助中心可用，但敏感运维配置仍保留在服务端，尚无安全的管理界面。",
    availableNow: ["查看账号、连接与隐私说明", "搜索教程、FAQ 和生成脱敏反馈摘要"],
    unavailable: ["在线修改 SMTP、AI Provider 和域名配置", "独立系统健康检查页面和管理员控制台"],
    requirements: ["先完成管理员权限与秘密信息保护设计", "补齐只读健康接口、审计边界和测试"],
  },
  "help-feedback": {
    reason: "帮助目录、模块教程、完整流程、FAQ 搜索和本地反馈摘要均已实现。",
    availableNow: ["搜索并阅读 17 个帮助章节", "展开 FAQ 并复制脱敏诊断摘要"],
    unavailable: ["自动把反馈发送给维护人员"],
    requirements: ["当前需人工粘贴反馈摘要", "自动发送前需定义接收渠道和隐私策略"],
  },
};

export function SettingsPanel() {
  const chapters = helpData.chapters as Chapter[];
  const [view, setView] = useState<"settings" | "help">("help");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("全部");
  const [selectedId, setSelectedId] = useState("home");
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [feedbackType, setFeedbackType] = useState("功能问题");
  const [feedback, setFeedback] = useState("");
  const [copied, setCopied] = useState(false);

  const normalizedQuery = query.trim().toLocaleLowerCase();
  const filteredChapters = useMemo(() => chapters.filter((chapter) => {
    const categoryMatches = category === "全部" || chapter.category === category;
    const text = `${chapter.title} ${chapter.summary} ${chapter.keywords.join(" ")}`.toLocaleLowerCase();
    return categoryMatches && (!normalizedQuery || text.includes(normalizedQuery));
  }), [category, chapters, normalizedQuery]);
  const filteredFaqs = useMemo(() => helpData.faqs
    .map(([question, answer], index) => ({ question, answer, index }))
    .filter((item) => !normalizedQuery || `${item.question} ${item.answer}`.toLocaleLowerCase().includes(normalizedQuery)), [normalizedQuery]);
  const selected = chapters.find((chapter) => chapter.id === selectedId) ?? chapters[0];
  const selectedAvailability = moduleAvailability[selected.id];
  const moduleChapters = chapters.filter((chapter) => chapter.category === "功能模块");
  const moduleCounts = moduleChapters.reduce((counts, chapter) => ({ ...counts, [chapter.status]: counts[chapter.status] + 1 }), { available: 0, partial: 0, planned: 0 });

  function openModuleDetails(chapterId: string) {
    setSelectedId(chapterId);
    setView("help");
    setQuery("");
    setCategory("全部");
  }

  async function copyFeedback() {
    const summary = [
      `问题类型：${feedbackType}`,
      `帮助中心版本：${helpData.version}`,
      `当前章节：${selected.title}`,
      `问题描述：${feedback.trim() || "未填写"}`,
      "安全检查：未包含密码、验证码、Cookie、API Key 或 SMTP 授权码。",
    ].join("\n");
    await navigator.clipboard.writeText(summary);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return <section>
    <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
      <div><h2 className="text-xl font-semibold">系统设置</h2><p className="mt-1 text-sm text-muted">账号安全、连接说明、帮助文档与问题反馈。</p></div>
      <span className="text-xs text-muted">帮助版本 {helpData.version}</span>
    </div>

    <div className="settings-segmented" role="tablist" aria-label="设置页面">
      <button type="button" className={view === "settings" ? "active" : ""} onClick={() => setView("settings")}><Settings size={16} />设置概览</button>
      <button type="button" className={view === "help" ? "active" : ""} onClick={() => setView("help")}><HelpCircle size={16} />帮助与反馈</button>
    </div>

    {view === "settings" ? <div className="mt-6 divide-y divide-slate-200 border-y border-slate-200">
      <section className="py-5"><h3 className="text-base font-semibold">账号与数据</h3><p className="mt-2 text-sm leading-6 text-muted">密码使用安全哈希，会话通过 HttpOnly Cookie，业务数据按账号隔离。个人求职资料请在“用户中心”维护。</p></section>
      <section className="py-5"><h3 className="text-base font-semibold">智联招聘连接</h3><p className="mt-2 text-sm leading-6 text-muted">手机搜索导入依赖本机后端、电脑 Edge 和 web-access。打开智联 App 不会自动同步岗位；最终投递必须逐条确认。</p></section>
      <section className="py-5"><h3 className="text-base font-semibold">隐私边界</h3><p className="mt-2 text-sm leading-6 text-muted">不要在备注或反馈中保存密码、验证码、Cookie、API Key、SMTP 授权码、身份证或银行卡信息。</p></section>
      <section className="py-5">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><h3 className="text-base font-semibold">功能可用性</h3><p className="mt-1 text-sm text-muted">状态来自当前代码、接口、测试和已知运行限制。</p></div><div className="availability-counts"><span className="help-status help-status-available">可用 {moduleCounts.available}</span><span className="help-status help-status-partial">部分可用 {moduleCounts.partial}</span><span className="help-status help-status-planned">规划中 {moduleCounts.planned}</span></div></div>
        <div className="mt-4 divide-y divide-slate-200 border-y border-slate-200">{moduleChapters.map((chapter) => <div key={chapter.id} className="settings-module-row"><div><div className="flex flex-wrap items-center gap-2"><strong>{chapter.title}</strong><span className={`help-status help-status-${chapter.status}`}>{statusLabels[chapter.status]}</span></div><p>{moduleAvailability[chapter.id]?.reason ?? chapter.summary}</p></div><button type="button" onClick={() => openModuleDetails(chapter.id)} aria-label={`查看${chapter.title}可用性说明`}>查看原因<ArrowRight size={15} /></button></div>)}</div>
      </section>
    </div> : <div className="mt-6">
      <div className="help-search-row">
        <label className="help-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索简历、面试、投递、Edge..." /></label>
        <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="帮助分类"><option>全部</option>{helpData.categories.map((item) => <option key={item}>{item}</option>)}</select>
      </div>

      <div className="mt-5 grid gap-7 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="help-directory">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3"><h3 className="text-sm font-semibold">目录</h3><span>{filteredChapters.length} 章</span></div>
          <div>{filteredChapters.map((chapter) => <button key={chapter.id} type="button" className={selected.id === chapter.id ? "active" : ""} onClick={() => setSelectedId(chapter.id)}><span><strong>{chapter.title}</strong><small>{chapter.summary}</small></span><em className={`help-status help-status-${chapter.status}`}>{statusLabels[chapter.status]}</em></button>)}</div>
          {!filteredChapters.length && <p className="py-6 text-sm text-muted">没有匹配章节，请更换关键词。</p>}
        </aside>

        <article className="help-article">
          <div className="border-b border-slate-200 pb-5"><div className="flex flex-wrap items-center gap-2"><BookOpen size={17} className="text-brand" /><span className="text-xs text-muted">{selected.category}</span><span className={`help-status help-status-${selected.status}`}>{statusLabels[selected.status]}</span></div><h3 className="mt-3 text-xl font-semibold">{selected.title}</h3><p className="mt-2 text-sm leading-6 text-muted">{selected.summary}</p><code className="mt-3 block text-xs text-muted">{selected.file}</code></div>
          {selectedAvailability && <section className={`availability-panel availability-panel-${selected.status}`} aria-label="功能可用性说明"><div className="availability-panel-title"><span className={`help-status help-status-${selected.status}`}>{statusLabels[selected.status]}</span><strong>{selected.status === "available" ? "为什么可以使用" : "为什么暂时不能完整使用"}</strong></div><p>{selectedAvailability.reason}</p><div className="availability-grid"><div><h4>现在能做什么</h4><ul>{selectedAvailability.availableNow.map((item) => <li key={item}>{item}</li>)}</ul></div><div><h4>{selected.status === "available" ? "当前限制" : "还缺少什么"}</h4><ul>{selectedAvailability.unavailable.map((item) => <li key={item}>{item}</li>)}</ul></div><div><h4>使用或启用条件</h4><ul>{selectedAvailability.requirements.map((item) => <li key={item}>{item}</li>)}</ul></div></div></section>}
          {selected.sections?.map((section) => <section key={section.heading} className="help-section"><h4>{section.heading}</h4><ul>{section.items.map((item) => <li key={item}>{item}</li>)}</ul></section>)}
          {selected.guide && guideSections.map(([key, label]) => {
            const value = selected.guide?.[key];
            return <section key={key} className="help-section"><h4>{label}</h4>{Array.isArray(value) ? <ol>{value.map((item) => <li key={item}>{item}</li>)}</ol> : <p>{value}</p>}</section>;
          })}
        </article>
      </div>

      <section className="mt-9 border-t border-slate-200 pt-7"><div className="flex items-end justify-between gap-4"><div><h3 className="text-base font-semibold">常见问题</h3><p className="mt-1 text-sm text-muted">当前显示 {filteredFaqs.length} / {helpData.faqs.length} 条</p></div></div><div className="mt-4 divide-y divide-slate-200 border-y border-slate-200">{filteredFaqs.map((item) => <div key={item.index} className="help-faq"><button type="button" onClick={() => setOpenFaq(openFaq === item.index ? null : item.index)}><span>{item.question}</span><strong>{openFaq === item.index ? "−" : "+"}</strong></button>{openFaq === item.index && <p>{item.answer}</p>}</div>)}</div></section>

      <section className="mt-9 border-t border-slate-200 pt-7"><h3 className="text-base font-semibold">反馈问题</h3><p className="mt-1 text-sm text-muted">生成本地诊断摘要，不会自动发送。提交前请移除个人信息和凭据。</p><div className="mt-4 grid gap-4 sm:grid-cols-[180px_minmax(0,1fr)]"><label className="field-label"><span>问题类型</span><select value={feedbackType} onChange={(event) => setFeedbackType(event.target.value)}><option>功能问题</option><option>使用建议</option><option>账号与登录</option><option>智联连接</option><option>数据与隐私</option></select></label><label className="field-label"><span>问题描述</span><textarea rows={4} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="请写复现步骤、预期结果和实际结果；不要粘贴密码或验证码。" /></label></div><div className="mt-4 flex justify-end"><button type="button" className="button-secondary icon-text-button" onClick={() => void copyFeedback()}>{copied ? <Check size={16} /> : <Copy size={16} />}{copied ? "已复制" : "复制诊断摘要"}</button></div></section>
    </div>}
  </section>;
}
