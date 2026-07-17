# 用户登录与 QQ 邮箱配置

## 已实现能力

- 欢迎页、QQ 邮箱注册、密码登录、六位邮箱验证码登录、忘记密码和退出登录。
- 密码使用 Argon2id 哈希；数据库和日志不保存明文密码。
- 登录使用随机、不可预测且仅保存哈希的服务端会话令牌；浏览器只接收 `HttpOnly`、`SameSite=Lax` Cookie。
- 验证码为六位数字，5 分钟有效，60 秒内不能重复发送；单邮箱每小时最多请求 10 次，单个验证码最多错误 5 次。
- 密码重置后撤销该用户全部已有会话。
- 简历、岗位、用户资料、公司黑名单、岗位屏蔽词、匹配、优化、沟通、投递、自动化任务、面试和分析统计均按 `user_id` 隔离。
- 旧 `dev.db` 数据迁移给本机管理员 `admin`；本地首次测试密码为 `admin123`，密码在数据库内只保存 Argon2id 哈希。

## QQ SMTP 配置

普通注册用户只输入自己的 QQ 邮箱作为验证码接收地址，不需要提供 QQ 密码或 SMTP 授权码。所有验证码由系统配置的一个 QQ 发信邮箱统一发送。

1. 登录作为发件人的 QQ 邮箱网页版，进入邮箱设置并开启 SMTP 服务。
2. 生成 SMTP 授权码。授权码不是 QQ 登录密码。
3. 在本机 `.env` 或 `.env.online` 配置以下变量，禁止提交到版本库：

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USERNAME=你的发件QQ邮箱@qq.com
SMTP_AUTHORIZATION_CODE=QQ邮箱生成的SMTP授权码
SMTP_SENDER_NAME=CareerPilot AI
SMTP_USE_SSL=true
```

未配置 SMTP 时，密码登录和本机管理员登录仍可使用；注册、验证码登录和找回密码会明确返回“QQ 邮箱发信服务尚未配置”，不会伪造发送成功。

配置完成后先验证 SMTP 登录；提供收件地址时会额外发送一封不含登录验证码的测试邮件：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-smtp.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-smtp.ps1 -Recipient 你的QQ邮箱@qq.com
```

授权码只保存在被 Git 忽略的 `.env.online`，脚本不会输出授权码，也不会把授权码拼入子进程命令行。SMTP 测试通过后，还必须从注册页依次验证注册验证码、验证码登录和找回密码三种真实邮件。

## 认证环境变量

```env
AUTH_SECRET_KEY=至少32位随机字符串
AUTH_COOKIE_NAME=careerpilot_session
AUTH_SESSION_DAYS=30
AUTH_IDLE_MINUTES=120
AUTH_COOKIE_SECURE=false
BOOTSTRAP_ADMIN_ENABLED=true
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=admin123
```

公网 HTTPS 环境必须设置 `AUTH_COOKIE_SECURE=true`，将 `AUTH_SECRET_KEY` 换成随机值，并将默认管理员密码改成强密码。`scripts/start-online.ps1` 会拒绝使用 `admin123` 启动公网服务。

也可以使用初始化脚本创建或更新本机管理员。密码通过临时环境变量传入，不写进命令行或数据库明文字段：

```powershell
$env:INIT_USER_PASSWORD="你的强密码"
cd backend
.\.venv\Scripts\python.exe scripts\init_user.py --username admin --email admin@local.invalid --admin --legacy-owner --update-password
Remove-Item Env:INIT_USER_PASSWORD
```

## 历史数据与新用户

- 迁移前备份位于 `backend/backups/dev-pre-auth-*.db`。
- 现有历史数据归属本机管理员，避免自动交给第一个注册用户。
- 新 QQ 邮箱账号注册后获得空白独立工作区，不能读取管理员或其他用户的数据。
- 如需把历史数据转给特定 QQ 账号，应增加经过管理员确认的转移流程，不直接修改 `user_id`。
