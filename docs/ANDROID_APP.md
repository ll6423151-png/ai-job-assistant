# CareerPilot AI Android 应用

## 架构

Android 客户端位于现有仓库的 `android/`，不是独立产品。它使用原生 Android WebView 加载部署后的 Next.js 前端，因此继续复用同一套 FastAPI API、账号、会话和按 `user_id` 隔离的数据库。

正式 APK 的服务器地址由构建参数 `CAREERPILOT_BASE_URL` 注入。构建脚本拒绝 `localhost`、`127.0.0.1`、Android 模拟器回环地址和非 HTTPS 地址，避免把只能在开发机访问的地址发布给手机用户。

## Android 能力

- 应用 ID：`com.careerpilot.ai`；应用名称：`CareerPilot AI`。
- 最低 Android 7.0（API 24），目标 API 35。
- 网络状态与 HTTPS WebView；正式版禁用明文 HTTP和混合内容。
- HttpOnly Cookie 持久化登录；服务端仍负责会话到期、撤销和用户数据隔离。
- 原生文件选择器支持上传 PDF、DOCX、TXT/Markdown 简历。
- 麦克风运行时权限只授予应用自己的 HTTPS 来源，用于 AI 面试录音；其他网页来源不能取得麦克风。
- 外部智联招聘链接在系统浏览器打开，不在应用 WebView 内共享或保存招聘平台账号密码。
- 网络错误页、重试、系统深色模式、安全区、44px 级触控目标和手机端横向标签导航。
- 自适应公文包应用图标与 Android 12/旧版本启动页。

## 安装隔离工具链

项目脚本只把 JDK 和 Android SDK 安装到被 Git 忽略的 `tools/android-build/`，不修改系统 Java 或 Android Studio：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-android-toolchain.ps1
```

脚本使用 Microsoft OpenJDK 21、Android command-line tools、Android 35 平台/Build Tools 35.0.0、Gradle 8.11.1，并按上游提供的校验值长度执行 SHA-1 或 SHA-256 完整性校验。

## 生成 APK

先准备可公网访问的 HTTPS 前端地址。该前端必须把 `/api` 转发到同一套 FastAPI 后端：

```powershell
$env:CAREERPILOT_BASE_URL="https://你的正式域名"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-android.ps1
Remove-Item Env:CAREERPILOT_BASE_URL
```

输出：

- `dist/android/CareerPilot-AI-debug.apk`
- `dist/android/CareerPilot-AI-release.apk`
- `dist/android/CareerPilot-AI-release.aab`

`APK` 用于直接安装和真机测试；`AAB` 用于提交 Google Play 等支持 Android App Bundle 的应用商店，不能直接点击安装。

2026-07-16 的临时测试构建已通过 Android 单元测试、Lint、debug/release 构建和 v2 签名验证。该 release 内置的是临时 Quick Tunnel，仅用于当前测试；地址失效后需用固定 HTTPS 地址重新构建。

第一次构建会在被忽略的 `android/keystore/` 创建 release 签名。该目录必须离线备份；丢失后无法用同一签名为已安装用户发布覆盖升级。脚本不会在终端输出签名密码，并会用 `apksigner verify --print-certs` 验证两个 APK。

## 安装与检查

启用手机“允许安装未知应用”后直接打开 release APK，或通过 USB 调试安装：

```powershell
.\tools\android-build\android-sdk\platform-tools\adb.exe install -r .\dist\android\CareerPilot-AI-release.apk
```

至少检查以下场景：

1. 冷启动出现图标/启动页，断网时出现重试页。
2. QQ 邮箱注册、密码登录、验证码登录、退出；关闭并重开应用仍保持有效登录。
3. 两个账号分别创建简历/岗位，互相不可见。
4. 上传简历文件、编辑资料、匹配、优化、沟通内容、黑名单、统计和面试录音。
5. 浅色/深色系统模式，以及 360x640、390x844、412x915、平板宽度。
6. 智联岗位链接从系统浏览器打开；登录、验证码和最终单条投递仍需人工确认。

## 已知平台边界

岗位搜索和自动投递后端目前依赖运行后端那台电脑的 Edge + CDP Proxy 登录会话。Android APK 能调用这些 API 和查看任务，但手机自己的智联 App/浏览器登录状态不会自动同步给服务端 Edge。要让不同手机用户独立使用该能力，需要新增每用户隔离的远程浏览器会话或改为平台允许的官方 API，并重新完成账号安全、验证码和逐条确认设计；不能通过 WebView 绕过招聘平台登录或风控。

Cloudflare Quick Tunnel 只能用于临时安装测试，地址会变化。对外分发必须使用固定 HTTPS 域名、持久数据库、备份、强 `AUTH_SECRET_KEY`、非默认管理员密码和已配置的 QQ SMTP 发件邮箱。
