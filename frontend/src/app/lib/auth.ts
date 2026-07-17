export type AuthUser = {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  email_verified: boolean;
};

export async function readApiError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string | { msg?: string }[] };
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) return payload.detail.map((item) => item.msg ?? "输入内容有误").join("；");
  } catch {
    // The fallback below handles non-JSON gateway errors.
  }
  return response.status >= 500 ? "服务暂时不可用，请稍后重试" : "操作失败，请检查输入";
}

export async function sendEmailCode(email: string, purpose: "register" | "login" | "reset_password") {
  const response = await fetch("/api/auth/email-codes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, purpose }),
  });
  if (!response.ok) throw new Error(await readApiError(response));
}
