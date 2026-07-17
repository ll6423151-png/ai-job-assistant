"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { AuthShell } from "../components/AuthShell";
import { readApiError, sendEmailCode } from "../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"password" | "code">("password");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [countdown, setCountdown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!countdown) return;
    const timer = window.setInterval(() => setCountdown((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [countdown]);

  async function requestCode() {
    setError("");
    try {
      await sendEmailCode(identifier, "login");
      setCountdown(60);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "验证码发送失败");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    const endpoint = mode === "password" ? "/api/auth/login" : "/api/auth/code-login";
    const body = mode === "password" ? { identifier, password, remember_me: rememberMe } : { email: identifier, verification_code: code, remember_me: rememberMe };
    try {
      const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!response.ok) throw new Error(await readApiError(response));
      router.replace("/"); router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败");
    } finally { setBusy(false); }
  }

  return <AuthShell title="登录" description="使用 QQ 邮箱或本机管理员账号进入工作台。">
    <div className="auth-mode-tabs"><button type="button" className={mode === "password" ? "active" : ""} onClick={() => setMode("password")}>密码登录</button><button type="button" className={mode === "code" ? "active" : ""} onClick={() => setMode("code")}>验证码登录</button></div>
    <form className="auth-form" onSubmit={submit}>
      <label className="field-label"><span>{mode === "password" ? "QQ 邮箱或用户名" : "QQ 邮箱"}</span><div className="auth-input"><Mail size={17} /><input value={identifier} onChange={(event) => setIdentifier(event.target.value)} placeholder={mode === "password" ? "QQ 邮箱或 admin" : "例如 123456789@qq.com"} autoComplete="username" required /></div></label>
      {mode === "password" ? <label className="field-label"><span>密码</span><div className="auth-input"><LockKeyhole size={17} /><input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /><button type="button" title={showPassword ? "隐藏密码" : "显示密码"} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label> : <label className="field-label"><span>邮箱验证码</span><div className="auth-code-row"><input value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" placeholder="6 位验证码" required /><button type="button" className="button-secondary" disabled={countdown > 0 || !identifier} onClick={requestCode}>{countdown ? `${countdown} 秒` : "发送验证码"}</button></div></label>}
      <div className="auth-form-options"><label><input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} /> 保持登录</label><Link href="/forgot-password">忘记密码</Link></div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button className="button-primary auth-submit" disabled={busy}>{busy ? "正在登录..." : "登录"}</button>
    </form>
    <p className="auth-switch">还没有账号？<Link href="/register">注册 QQ 邮箱账号</Link></p>
  </AuthShell>;
}
