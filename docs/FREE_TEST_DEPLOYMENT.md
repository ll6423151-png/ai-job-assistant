# 免费临时测试部署

目标：几名测试者从 GitHub Releases 下载 APK，并在开发者电脑关机时继续使用。该方案使用 Render 免费 Web 服务、Neon 免费 PostgreSQL 和 GitHub Releases，不需要银行卡或应用商店。

## 运行关系

- `careerpilot-web-33387.onrender.com`：Next.js 页面，也是 Android APK 内置地址。
- `careerpilot-api-33387.onrender.com`：FastAPI 后端。
- Neon：持久 PostgreSQL 数据库，避免 Render 重启后丢失 SQLite。
- GitHub Releases：存放签名 APK。

Android 和 Windows 浏览器都从 Web 地址进入，页面的 `/api/*` 请求由 Next.js 代理到同一个 Render FastAPI 服务。

## 一、创建 Neon 数据库

1. 打开 https://neon.com 并注册免费账号。
2. 创建项目和数据库。
3. 在 Connection Details 中复制 SQLAlchemy 可用的 PostgreSQL 连接串。
4. 不要把连接串发到聊天或提交 GitHub；后面只粘贴到 Render 的 `DATABASE_URL` Secret。

Neon Free 无时间限制且不要求信用卡：https://neon.com/pricing

## 二、准备 GitHub 仓库

1. 注册或登录 GitHub。
2. 创建一个仓库并上传当前项目，确保 `render.yaml` 位于仓库根目录。
3. `.env`、`.env.online`、`deploy/oracle/.env.oracle`、Android 签名目录和数据库文件必须保持忽略状态。

当前电脑尚未安装 GitHub CLI，且项目还没有 `.git`，因此首次仓库创建和登录必须先人工完成。

## 三、在 Render 创建 Blueprint

1. 登录 https://dashboard.render.com 。
2. 选择 New -> Blueprint，连接刚创建的 GitHub 仓库。
3. Render 读取根目录 `render.yaml`，创建 `careerpilot-api-33387` 和 `careerpilot-web-33387` 两个免费 Web Service。
4. 创建过程中填写两个 Secret：
   - `DATABASE_URL`：Neon PostgreSQL 连接串。
   - `BOOTSTRAP_ADMIN_PASSWORD`：至少 12 位、包含字母和数字的测试管理员密码。
   - `BOOTSTRAP_TEST_PASSWORD`：可选的普通测试账号密码；默认用户名为 `tester`，默认邮箱为 `tester@local.invalid`。该账号不授予管理员权限，不应存放真实个人资料。
   - `BOOTSTRAP_TEST2_PASSWORD`、`BOOTSTRAP_TEST3_PASSWORD`：可选的第二、第三个普通测试账号密码；默认用户名分别为 `tester2`、`tester3`，数据彼此隔离。
5. 等待两个服务状态变为 Live，打开：
   - `https://careerpilot-api-33387.onrender.com/api/health`
   - `https://careerpilot-web-33387.onrender.com`

如果服务名称被占用，需要同时修改 `render.yaml` 中的服务名、前端 `INTERNAL_API_BASE_URL`、后端 `BACKEND_CORS_ORIGINS` 和 `PUBLIC_BASE_URL`。

## 四、生成测试 APK

Web 服务可访问后运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-free-test-apk.ps1
```

输出为 `dist/android/CareerPilot-AI-release.apk`。该 APK 内置 Render Web 地址，因此开发者电脑关闭后仍可使用。

## 五、发布 APK

安装并登录 GitHub CLI 后运行：

```powershell
gh auth login
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\publish-github-release.ps1 `
  -Tag "v1.0.0-test" `
  -BaseUrl "https://careerpilot-web-33387.onrender.com" `
  -Repository "OWNER/REPO"
```

脚本默认只上传 APK。把 GitHub Release 下载链接发给测试者即可。

## 免费方案限制

- Render 服务闲置 15 分钟后休眠，第一次打开通常需要等待约一分钟。
- Render 免费服务本地文件会在重启或重新部署后丢失，所以只能把业务数据放在 Neon。
- Render 免费服务禁止访问 SMTP 25/465/587，因此 QQ 邮箱验证码、邮箱注册和找回密码不可用。测试者优先使用预置普通测试账号；不要把正式个人密码设为测试密码。未设置 `BOOTSTRAP_TEST_PASSWORD` 时才回退使用管理员账号。
- 免费服务不是正式生产环境，Render 可能重启或暂停服务。
- 智联自动搜索/投递依赖本机 Windows Edge，不会迁移到 Render；测试者仍可使用简历、岗位管理、匹配、沟通、记录和基础面试等不依赖浏览器桥接的功能。
- 本地 Whisper 可能因免费实例内存、冷启动和模型下载而失败；实时语音不作为本方案验收项。
