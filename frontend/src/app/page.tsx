"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AnalyticsPanel } from "./components/AnalyticsPanel";
import { ApplicationPanel } from "./components/ApplicationPanel";
import { BlacklistPanel } from "./components/BlacklistPanel";
import { GreetingPanel } from "./components/GreetingPanel";
import { JobSearchPanel } from "./components/JobSearchPanel";
import { InterviewPanel } from "./components/InterviewPanel";
import { MatchPanel } from "./components/MatchPanel";
import { OptimizationPanel } from "./components/OptimizationPanel";
import { PlatformAdapterPanel } from "./components/PlatformAdapterPanel";
import { ProfilePanel } from "./components/ProfilePanel";
import { ResumePanel } from "./components/ResumePanel";
import { SubmissionAutomationPanel } from "./components/SubmissionAutomationPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import type { AuthUser } from "./lib/auth";

const API_BASE = "";
type Tab = "interviews" | "delivery" | "platforms" | "analytics" | "applications" | "greeting" | "optimize" | "match" | "blacklist" | "jobs" | "resumes" | "profile" | "settings";

const tabs: [Tab, string][] = [
  ["interviews", "AI 模拟面试"], ["delivery", "投递执行"], ["platforms", "平台适配器"],
  ["analytics", "数据统计"], ["applications", "投递记录"], ["greeting", "沟通内容"],
  ["optimize", "简历优化"], ["match", "JD 匹配"], ["blacklist", "公司黑名单"],
  ["jobs", "职位搜索"], ["resumes", "简历管理"], ["profile", "用户中心"], ["settings", "系统设置"],
];

export default function Home() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("interviews");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authFailed, setAuthFailed] = useState(false);

  useEffect(() => {
    const originalFetch = window.fetch.bind(window);
    const guardedFetch: typeof window.fetch = async (input, init) => {
      const response = await originalFetch(input, init);
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (response.status === 401 && url.includes("/api/") && !url.includes("/api/auth/")) {
        router.replace("/login");
      }
      return response;
    };
    window.fetch = guardedFetch;
    return () => {
      if (window.fetch === guardedFetch) window.fetch = originalFetch;
    };
  }, [router]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8_000);
    fetch("/api/auth/me", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("unauthorized");
        const currentUser = await response.json() as AuthUser;
        if (active) setUser(currentUser);
      })
      .catch(() => {
        if (!active) return;
        setAuthFailed(true);
        window.location.replace("/login");
      })
      .finally(() => window.clearTimeout(timeout));
    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [router]);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  if (!user) return <main className="auth-loading">{authFailed
    ? <div className="flex flex-col items-center gap-4"><span>登录状态已失效</span><a className="button-primary" href="/login">前往登录</a></div>
    : <span>正在验证登录状态...</span>}
  </main>;

  const panels: Record<Tab, React.ReactNode> = {
    interviews: <InterviewPanel apiBase={API_BASE} />, delivery: <SubmissionAutomationPanel apiBase={API_BASE} />,
    platforms: <PlatformAdapterPanel apiBase={API_BASE} />, analytics: <AnalyticsPanel apiBase={API_BASE} />,
    applications: <ApplicationPanel apiBase={API_BASE} />, greeting: <GreetingPanel apiBase={API_BASE} />,
    optimize: <OptimizationPanel apiBase={API_BASE} />, match: <MatchPanel apiBase={API_BASE} />,
    blacklist: <BlacklistPanel apiBase={API_BASE} />, jobs: <JobSearchPanel apiBase={API_BASE} />,
    resumes: <ResumePanel apiBase={API_BASE} />, profile: <ProfilePanel apiBase={API_BASE} />, settings: <SettingsPanel />,
  };
  const title = tabs.find(([key]) => key === activeTab)?.[1];

  return <main className="app-shell min-h-screen px-5 py-6 text-ink sm:px-8 sm:py-8"><div className="mx-auto max-w-7xl">
    <header className="flex flex-col justify-between gap-5 border-b border-slate-200 pb-6 sm:flex-row sm:items-end">
      <div><p className="mb-2 text-sm font-semibold text-brand">CAREERPILOT AI / WORKSPACE</p><h1 className="text-3xl font-semibold tracking-normal sm:text-4xl">{title}</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted">{activeTab === "interviews" ? "基于简历与目标职位开展连续追问、实时语音作答和证据化复盘。" : "在统一工作台中管理求职资料、岗位分析与投递流程。"}</p></div>
      <div className="account-summary"><div><strong>{user.username}</strong><span>{user.email}</span></div><button type="button" title="退出登录" onClick={logout}><LogOut size={17} /></button></div>
    </header>
    <nav className="app-tabs flex gap-1 overflow-x-auto border-b border-slate-200 pt-5" aria-label="模块切换">{tabs.map(([key, label]) => <button key={key} type="button" className={`tab-button ${activeTab === key ? "tab-button-active" : ""}`} onClick={() => setActiveTab(key)}>{label}</button>)}</nav>
    <div className="app-content grid gap-8 py-8 lg:grid-cols-[minmax(0,1fr)_240px]"><div className="min-w-0">{panels[activeTab]}</div><aside className="app-status border-l border-slate-200 pl-0 lg:pl-7"><h2 className="text-base font-semibold">项目状态</h2><div className="mt-4 border-y border-slate-200 py-4"><strong className="text-2xl text-emerald-700">13 / 13</strong><p className="mt-1 text-sm text-muted">工作台入口已接入</p></div><div className="mt-5 space-y-3 text-xs leading-5 text-muted"><p>当前账号的数据与其他用户严格隔离。</p><p>外部投递仅支持逐条预览和确认。</p><p>平台登录和验证码由用户手动完成。</p><p>当前仅接入智联招聘。</p></div></aside></div>
  </div></main>;
}
