import { NextRequest, NextResponse } from "next/server.js";

const PUBLIC_PATHS = new Set(["/welcome", "/login", "/register", "/forgot-password"]);

function redirectTo(request: NextRequest, pathname: string) {
  const destination = request.nextUrl.clone();
  const forwardedHost = request.headers.get("x-forwarded-host")?.split(",", 1)[0]?.trim();
  const requestHost = forwardedHost || request.headers.get("host")?.trim();
  const forwardedProtocol = request.headers.get("x-forwarded-proto")?.split(",", 1)[0]?.trim();
  const hostMatch = requestHost?.match(/^([a-z0-9.-]+)(?::(\d+))?$/i);
  if (hostMatch) {
    destination.hostname = hostMatch[1];
    const publicHttpsRequest = forwardedProtocol === "https" || destination.protocol === "https:";
    const forwardedPrivatePort = publicHttpsRequest && hostMatch[2] === "3000";
    destination.port = forwardedPrivatePort ? "" : hostMatch[2] ?? "";
  }

  if (forwardedProtocol === "http" || forwardedProtocol === "https") destination.protocol = `${forwardedProtocol}:`;
  destination.pathname = pathname;
  destination.search = "";
  return NextResponse.redirect(destination);
}

export function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;
  if (path.startsWith("/api/") || path.startsWith("/_next/") || path === "/favicon.ico") return NextResponse.next();

  const hasSession = Boolean(request.cookies.get("careerpilot_session")?.value);
  if (!hasSession && !PUBLIC_PATHS.has(path)) return redirectTo(request, "/welcome");
  return NextResponse.next();
}

export const config = { matcher: ["/((?!_next/static|_next/image).*)"] };
