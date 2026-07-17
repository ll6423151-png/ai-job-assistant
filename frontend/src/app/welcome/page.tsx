import Link from "next/link";
import { ArrowRight, BriefcaseBusiness, CheckCircle2, ShieldCheck } from "lucide-react";

export default function WelcomePage() {
  return (
    <main className="welcome-page">
      <div className="welcome-shell">
        <header className="welcome-header"><div className="auth-brand"><BriefcaseBusiness size={20} /> CareerPilot AI</div><Link href="/login" className="button-secondary">登录</Link></header>
        <section className="welcome-content">
          <div>
            <p className="auth-kicker">AI 求职助手</p>
            <h1>从个人资料到岗位投递，在一个工作台完成。</h1>
            <p className="welcome-summary">登录后继续管理主简历、智联岗位搜索、匹配分析、沟通内容、投递记录和 AI 模拟面试。</p>
            <div className="welcome-actions"><Link href="/register" className="button-primary">创建 QQ 邮箱账号 <ArrowRight size={16} /></Link><Link href="/login" className="button-secondary">已有账号登录</Link></div>
          </div>
          <div className="welcome-capabilities">
            <div><CheckCircle2 size={17} /><span>已有功能与数据完整保留</span></div>
            <div><ShieldCheck size={17} /><span>每位用户的数据严格隔离</span></div>
            <div><BriefcaseBusiness size={17} /><span>招聘平台最终投递仍需用户确认</span></div>
          </div>
        </section>
      </div>
    </main>
  );
}
