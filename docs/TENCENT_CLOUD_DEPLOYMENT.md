# 腾讯云轻量服务器部署

本方案用于没有国际银行卡的情况。腾讯云支持余额、网银、微信支付和 QQ 钱包；购买完成后控制台会显示公网 IP。部署代码继续复用 `deploy/oracle/` 下的通用 Ubuntu Docker、Nginx 和 Certbot 引擎，不复制业务代码。

## 一、购买服务器

1. 登录腾讯云并完成实名认证。
2. 购买“轻量应用服务器”，操作系统选择 Ubuntu 22.04 或 24.04。
3. 基础测试可使用 2 核 2GB；需要本地 Whisper 时建议至少 2 核 4GB。
4. 需要马上公网测试且暂时不备案时，可选择中国香港地域；中国内地服务器提供公开网站或 APP 服务需要按腾讯云要求备案。
5. 在轻量服务器防火墙中确认 TCP 22、80、443 已开放；不要开放 3000、8000、5432、6379。

腾讯云购买与支付说明：https://cloud.tencent.com/document/product/213/506

## 二、绑定 SSH 密钥

本机已生成：

- 私钥：`C:\Users\33387\.ssh\careerpilot_oracle`
- 公钥：`C:\Users\33387\.ssh\careerpilot_oracle.pub`

在腾讯云轻量服务器控制台进入“SSH 密钥”，选择导入已有公钥，上传 `.pub` 文件并绑定实例。Ubuntu 默认登录用户为 `ubuntu`。私钥不得上传到聊天、GitHub 或云盘。

腾讯云密钥管理说明：https://cloud.tencent.com/document/product/1207/44573

## 三、固定域名

正式 Android APK 必须使用固定 HTTPS 地址。准备域名并把 A 记录指向服务器公网 IP；DNS 生效后再执行部署。没有域名时可以先完成服务器和 SSH 检查，但不能生成长期分发 APK。

## 四、一键部署

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy-tencent.ps1 `
  -ServerHost "腾讯云公网IP" `
  -Domain "career.example.com" `
  -CertificateEmail "你的邮箱" `
  -RepositoryUrl "https://github.com/OWNER/REPO.git" `
  -AdminPassword "至少12位字母数字密码"
```

脚本会完成 Docker、PostgreSQL、Redis、FastAPI、Next.js、Nginx、HTTPS 和健康检查。后续更新继续使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\update-oracle.ps1 `
  -ServerHost "腾讯云公网IP" `
  -Domain "career.example.com" `
  -SshKeyPath "$env:USERPROFILE\.ssh\careerpilot_oracle"
```

## 五、仍然需要人工完成

- 腾讯云购买付款和实名认证。
- 域名购买、解析及中国内地备案。
- GitHub 登录、创建仓库和首次推送。
- QQ SMTP 授权码写入服务器私密环境文件。
- 智联验证码、登录和最终逐条投递确认。

腾讯云 Linux 本身不能复用本机 Windows Edge 登录会话，因此智联浏览器桥接不会随 Docker 部署自动迁移。

## 六、仅分发 APK

当前目标不包含应用商店。固定 HTTPS 部署完成后运行 `scripts/publish-github-release.ps1`，默认只把 `CareerPilot-AI-release.apk` 上传到 GitHub Releases。其他人从 Release 页面下载并安装 APK；运行时访问腾讯云服务器，因此开发者电脑可以完全关机。AAB 不上传、不影响 APK 使用。
