"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { AuthShell } from "../components/AuthShell";
import { readApiError, sendEmailCode } from "../lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState(""); const [code, setCode] = useState(""); const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState(""); const [showPassword, setShowPassword] = useState(false);
  const [countdown, setCountdown] = useState(0); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  useEffect(() => { if (!countdown) return; const timer = window.setInterval(() => setCountdown((value) => Math.max(0, value - 1)), 1000); return () => window.clearInterval(timer); }, [countdown]);
  async function requestCode() { setError(""); try { await sendEmailCode(email, "register"); setCountdown(60); } catch (caught) { setError(caught instanceof Error ? caught.message : "验证码发送失败"); } }
  async function submit(event: FormEvent) { event.preventDefault(); if (password !== confirmPassword) { setError("两次输入的密码不一致"); return; } setBusy(true); setError(""); try { const response = await fetch("/api/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password, verification_code: code }) }); if (!response.ok) throw new Error(await readApiError(response)); router.replace("/"); router.refresh(); } catch (caught) { setError(caught instanceof Error ? caught.message : "注册失败"); } finally { setBusy(false); } }
  return <AuthShell title="创建账号" description="使用你的 QQ 邮箱接收验证码并创建独立工作区。"><form className="auth-form" onSubmit={submit}>
    <label className="field-label"><span>QQ 邮箱</span><div className="auth-input"><Mail size={17} /><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="123456789@qq.com" autoComplete="email" required /></div></label>
    <label className="field-label"><span>邮箱验证码</span><div className="auth-code-row"><input value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" placeholder="6 位验证码" required /><button type="button" className="button-secondary" disabled={countdown > 0 || !email} onClick={requestCode}>{countdown ? `${countdown} 秒` : "发送验证码"}</button></div></label>
    <label className="field-label"><span>密码</span><div className="auth-input"><LockKeyhole size={17} /><input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" minLength={8} required /><button type="button" title={showPassword ? "隐藏密码" : "显示密码"} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div><small>至少 8 位，同时包含字母和数字</small></label>
    <label className="field-label"><span>确认密码</span><div className="auth-input"><LockKeyhole size={17} /><input type={showPassword ? "text" : "password"} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" required /></div></label>
    {error && <p className="auth-error" role="alert">{error}</p>}<button className="button-primary auth-submit" disabled={busy}>{busy ? "正在创建..." : "注册并登录"}</button>
  </form><p className="auth-switch">已有账号？<Link href="/login">返回登录</Link></p></AuthShell>;
}
