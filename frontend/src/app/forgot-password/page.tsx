"use client";

import Link from "next/link";
import { Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { AuthShell } from "../components/AuthShell";
import { readApiError, sendEmailCode } from "../lib/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState(""); const [code, setCode] = useState(""); const [password, setPassword] = useState(""); const [showPassword, setShowPassword] = useState(false);
  const [countdown, setCountdown] = useState(0); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [done, setDone] = useState(false);
  useEffect(() => { if (!countdown) return; const timer = window.setInterval(() => setCountdown((value) => Math.max(0, value - 1)), 1000); return () => window.clearInterval(timer); }, [countdown]);
  async function requestCode() { setError(""); try { await sendEmailCode(email, "reset_password"); setCountdown(60); } catch (caught) { setError(caught instanceof Error ? caught.message : "验证码发送失败"); } }
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(""); try { const response = await fetch("/api/auth/reset-password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, verification_code: code, new_password: password }) }); if (!response.ok) throw new Error(await readApiError(response)); setDone(true); } catch (caught) { setError(caught instanceof Error ? caught.message : "密码重置失败"); } finally { setBusy(false); } }
  return <AuthShell title="找回密码" description="验证码会发送到注册时使用的 QQ 邮箱。">{done ? <div className="auth-success"><h3>密码已重置</h3><p>旧登录会话已全部退出，请使用新密码重新登录。</p><Link href="/login" className="button-primary">返回登录</Link></div> : <form className="auth-form" onSubmit={submit}>
    <label className="field-label"><span>QQ 邮箱</span><div className="auth-input"><Mail size={17} /><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="123456789@qq.com" required /></div></label>
    <label className="field-label"><span>邮箱验证码</span><div className="auth-code-row"><input value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="6 位验证码" inputMode="numeric" required /><button type="button" className="button-secondary" disabled={countdown > 0 || !email} onClick={requestCode}>{countdown ? `${countdown} 秒` : "发送验证码"}</button></div></label>
    <label className="field-label"><span>新密码</span><div className="auth-input"><LockKeyhole size={17} /><input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required /><button type="button" title={showPassword ? "隐藏密码" : "显示密码"} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div><small>至少 8 位，同时包含字母和数字</small></label>
    {error && <p className="auth-error" role="alert">{error}</p>}<button className="button-primary auth-submit" disabled={busy}>{busy ? "正在重置..." : "重置密码"}</button>
  </form>}<p className="auth-switch"><Link href="/login">返回登录</Link></p></AuthShell>;
}
