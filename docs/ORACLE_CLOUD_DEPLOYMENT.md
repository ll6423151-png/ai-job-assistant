# Oracle Cloud Always Free 部署

本方案在现有项目内运行，不创建第二套产品。Oracle Ubuntu 实例运行 PostgreSQL、Redis、FastAPI 和 Next.js Docker 服务；宿主机 Nginx 只公开 80/443，Certbot 签发 HTTPS 证书。Android WebView 与 Windows 浏览器统一访问 `https://你的域名`，所有业务接口统一为 `https://你的域名/api/*`。

## 一、人工准备

1. 在 Oracle Cloud Home Region 创建 Always Free Ubuntu 实例，保存 SSH 私钥和公网 IP。
2. Oracle VCN 安全列表或 NSG 开放 TCP 22、80、443；数据库 5432、Redis 6379、FastAPI 8000 和 Next.js 3000 不对公网开放。
3. 准备一个域名，将 A 记录指向 Oracle 实例公网 IP。DNS 生效后才可申请 HTTPS 证书。
4. 将当前项目提交到公开 GitHub 仓库。自动部署脚本不会在服务器保存 GitHub Token；私有仓库需另行设计只读 Deploy Key。
5. 确保本机 SSH 私钥可用。默认路径为 `%USERPROFILE%\.ssh\id_rsa`。

Oracle Always Free 计算资源只能在账号 Home Region 创建；免费容量可能暂时不足。官方说明：https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm

## 二、一键部署

在项目根目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy-oracle.ps1 `
  -ServerHost "Oracle公网IP" `
  -SshUser "ubuntu" `
  -Domain "career.example.com" `
  -CertificateEmail "你的邮箱" `
  -RepositoryUrl "https://github.com/OWNER/REPO.git" `
  -AdminPassword "至少12位字母数字密码" `
  -SshKeyPath "$env:USERPROFILE\.ssh\id_rsa"
```

脚本会在本机生成随机 PostgreSQL 密码和认证密钥，临时环境文件上传后立即从本机删除；服务器私密配置保存为 `/opt/careerpilot/deploy/oracle/.env.oracle`，权限为 600。脚本安装 Docker、Nginx、Certbot，启动容器、初始化管理员、签发证书并检查 `/api/health`。

QQ SMTP 需要部署后人工编辑服务器 `.env.oracle`，填写 `SMTP_USERNAME` 和 `SMTP_AUTHORIZATION_CODE`，然后执行更新脚本。不要把授权码提交到 GitHub。

## 三、一键更新

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\update-oracle.ps1 `
  -ServerHost "Oracle公网IP" `
  -Domain "career.example.com" `
  -SshKeyPath "$env:USERPROFILE\.ssh\id_rsa"
```

服务器执行 `git pull --ff-only`，重建变更镜像、保留 PostgreSQL/Redis/上传卷并检查 HTTPS 健康接口。脚本不会覆盖 `.env.oracle`。

## 四、Android 与 GitHub Releases

安装并登录 GitHub CLI 后运行：

```powershell
gh auth login
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\publish-github-release.ps1 `
  -Tag "v1.0.0" `
  -BaseUrl "https://career.example.com" `
  -Repository "OWNER/REPO"
```

脚本使用同一固定域名重新构建并签名，默认只上传 APK：

- `CareerPilot-AI-release.apk`：供测试用户直接下载安装。
- `CareerPilot-AI-release.aab`：仍会留在本机，但不上传；只有以后需要应用商店时才使用 `-IncludeAab`。

GitHub CLI 官方发布命令说明：https://cli.github.com/manual/gh_release

## 五、Windows 客户端

当前项目没有独立 Electron/Tauri 客户端；Windows 客户端是同一 Next.js Web 应用。可运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\open-windows-client.ps1 `
  -BaseUrl "https://career.example.com"
```

Windows 浏览器与 Android APK 因此共享同一个账号、PostgreSQL 数据和 `/api` 接口。

## 六、限制

- Oracle Linux 云服务器不能复用当前 Windows 电脑上的 Edge 登录会话和 `web-access` 浏览器桥接。智联自动搜索/半自动投递在云端默认不可用，除非后续实现隔离的远程浏览器方案；验证码和最终投递仍必须人工确认。
- `faster-whisper` 首次转写会下载模型并消耗内存。Always Free 小规格实例可能出现内存不足，必要时暂时关闭本地实时转写或增加交换空间。
- Certbot 申请证书要求域名已经指向服务器，且 Oracle 安全列表和系统网络允许公网访问 80/443。Certbot 的 Nginx/Webroot 工作方式要求 80 端口可达：https://certbot.eff.org/instructions
- 正式上线前必须演练 PostgreSQL 备份与恢复；更新脚本保留数据卷，但数据卷不能替代异地备份。
