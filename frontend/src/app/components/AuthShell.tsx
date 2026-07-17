import Link from "next/link";
import { BriefcaseBusiness, ShieldCheck } from "lucide-react";

export function AuthShell({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <main className="auth-page">
      <div className="auth-layout">
        <section className="auth-context" aria-label="产品信息">
          <div className="auth-brand"><BriefcaseBusiness size={20} /> CareerPilot AI</div>
          <div>
            <p className="auth-kicker">AI 求职工作台</p>
            <h1>你的求职资料，始终只属于你的账号。</h1>
            <p>简历、职位、分析、黑名单与投递记录均按登录用户独立保存。</p>
          </div>
          <div className="auth-security-note"><ShieldCheck size={18} /><span>密码采用 Argon2 加密，登录会话可随时退出并撤销。</span></div>
        </section>
        <section className="auth-form-panel">
          <Link href="/welcome" className="auth-mobile-brand"><BriefcaseBusiness size={18} /> CareerPilot AI</Link>
          <div className="auth-heading"><h2>{title}</h2><p>{description}</p></div>
          {children}
        </section>
      </div>
    </main>
  );
}
