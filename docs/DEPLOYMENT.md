# 部署说明

Oracle Cloud Always Free + Docker + Nginx + HTTPS 的固定服务器方案见 `docs/ORACLE_CLOUD_DEPLOYMENT.md`。该方案使 Windows 浏览器和 Android APK 统一访问同一固定 HTTPS 域名及 `/api` 接口；现有 Cloudflare Quick Tunnel 仅保留为本机临时测试方式。

没有国际银行卡时，腾讯云轻量服务器部署入口见 `docs/TENCENT_CLOUD_DEPLOYMENT.md`；它复用同一套生产 Docker/Nginx/HTTPS 配置，可通过微信或 QQ 钱包购买服务器。

仅供少量人员临时测试且要求零费用时，使用 `docs/FREE_TEST_DEPLOYMENT.md` 中的 Render + Neon + GitHub Releases 方案。该方案不依赖开发者电脑，但存在休眠、SMTP 禁用和智联浏览器桥接不可用等限制。

## Docker Compose

1. 将 `.env.example` 复制为 `.env`。
2. 生产环境必须修改 PostgreSQL 密码和 CORS 域名。
3. 如需 OpenAI，设置 `AI_PROVIDER=openai` 与 `OPENAI_API_KEY`；不配置时使用本地提供商。
4. 执行 `docker compose up --build -d`。
5. 检查 `/api/health`、`/docs` 与前端首页。

应用启动时通过 SQLAlchemy `create_all` 创建缺失的面试模块表，不覆盖已有表和数据。正式环境首次升级前应备份 PostgreSQL；后续字段演进建议将全项目统一迁移到 Alembic 管理。

## 必需配置

- `DATABASE_URL`：PostgreSQL SQLAlchemy 连接串。
- `REDIS_URL`：Redis 连接串，为后续限流和任务队列保留。
- `BACKEND_CORS_ORIGINS`：允许的前端来源，多个来源使用逗号分隔。
- `NEXT_PUBLIC_API_BASE_URL`：浏览器可访问的后端地址。

## AI 与文件配置

- `AI_PROVIDER=local|openai`，默认 `local`。
- `OPENAI_TEXT_MODEL`：问题与报告模型。
- `OPENAI_TRANSCRIPTION_MODEL`：录音转写模型。
- `OPENAI_TTS_MODEL`、`OPENAI_TTS_VOICE`：语音合成模型与声音。
- `LOCAL_TRANSCRIPTION_MODEL`：未配置 OpenAI 时使用的本地 Whisper 模型，默认 `base`；首次转写会下载模型。
- `RESUME_UPLOAD_MAX_MB`、`AUDIO_UPLOAD_MAX_MB`：上传限制。
- `BROWSER_PROXY_URL`：本机 web-access 浏览器桥接地址，默认 `http://127.0.0.1:3456`。
- `BROWSER_PROXY_TIMEOUT_SECONDS`：浏览器页面操作超时时间。
- `APPLICATION_AUTOMATION_DAILY_LIMIT`：所有支持平台合计的每日外部提交尝试上限，默认 `20`，允许 `1-200`。
- `APPLICATION_AUTOMATION_COOLDOWN_SECONDS`：任意两次外部提交尝试的最小间隔，默认 `60` 秒，允许 `0-3600`。

API Key 只配置在后端，禁止写入 `NEXT_PUBLIC_*` 变量或前端代码。上传文件只在请求内解析，不将原文件写入容器磁盘；数据库保存文件元数据和提取后的文本。

投递次数在任务进入 `submitting` 时记录，因此后续失败或需人工核验也会占用当日配额。当前实现面向本机单进程；多实例生产部署需要集中式限流或数据库锁来避免并发绕过。

## 发布检查

```powershell
cd backend
python -m pytest -q

cd ../frontend
pnpm typecheck
pnpm build
```

发布后至少验证：创建面试、重复开始、连续回答、提前结束、报告重复读取、简历上传、浏览器麦克风权限与移动端布局。

## 本机在线部署

当前采用 Cloudflare Quick Tunnel，将本机 `127.0.0.1:3000` 暴露为临时 HTTPS 地址。Next.js 统一代理 `/api` 到本机 FastAPI，因此浏览器只需要访问一个公网域名。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-online.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\status-online.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-online.ps1
```

访问账号保存在被 Git 忽略的 `.env.online`。Quick Tunnel 地址保存在 `runtime/public-url.txt`，每次重建 Tunnel 可能变化，且没有可用性保证。要获得固定域名、开机自启和稳定 SLA，需要登录 Cloudflare 账号并创建 Named Tunnel。

## 固定域名正式启动

固定域名继续使用本机 FastAPI、Next.js 和 Edge 浏览器会话，以保留智联招聘桥接能力。先在 Cloudflare 控制台创建 Named Tunnel，将固定公网主机名指向 `http://localhost:3000`，再在被 Git 忽略的 `.env.online` 中配置：

```env
PUBLIC_BASE_URL=https://你的固定域名
CLOUDFLARE_TUNNEL_TOKEN=Named-Tunnel-令牌
AUTH_SECRET_KEY=至少32位随机字符串
BOOTSTRAP_ADMIN_PASSWORD=非默认强密码
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USERNAME=系统发件QQ邮箱@qq.com
SMTP_AUTHORIZATION_CODE=QQ邮箱SMTP授权码
SMTP_SENDER_NAME=CareerPilot AI
SMTP_USE_SSL=true
```

先执行只读预检，再启动正式环境：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-mvp-readiness.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-production.ps1
```

`start-production.ps1` 要求固定 HTTPS 域名、Named Tunnel token、强认证密钥、非默认管理员密码和 QQ SMTP 全部配置完成。密钥通过子进程环境变量传递，不拼入命令行；脚本只将固定公开地址和进程编号写入 `runtime/`。停止和状态检查继续使用 `stop-online.ps1` 与 `status-online.ps1`。

正式固定域名确定后，必须以该地址重新生成 Android release APK；临时 Quick Tunnel APK 不得作为长期发布包。

智联招聘自动化仍依赖本机 Edge 及 `web-access` 浏览器桥接。本机关闭、Edge 退出、远程调试未授权或代理 `127.0.0.1:7990` 不可用时，软件页面仍可访问，但平台登录检测和投递执行不可用。腾讯云 EdgeOne 等安全验证必须由用户手动完成，软件不得绕过。
