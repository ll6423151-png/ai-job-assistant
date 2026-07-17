# AI 模拟面试模块设计

## 产品边界

本模块集成在现有 AI Job Assistant 中，复用当前用户档案、简历和职位数据，不引入第二套账号或导航体系。目标用户可以选择已有简历和职位，完成连续追问、压力面试、实时语音通话、录音或文字作答、评分复盘和历史查询。

## 核心流程

1. 用户选择已有简历，或上传 PDF、DOCX、TXT 自动解析为一个简历版本。
2. 用户选择已有职位或手动填写目标岗位，配置面试类型、压力等级和题数。
3. 系统生成首题；每次作答后基于简历、JD 和上下文继续追问。
4. 达到题数或用户主动结束后，仅生成一次报告。
5. 历史会话保留简历和职位快照，即使源数据被删除仍可复盘。

## 实时语音通话

- 用户可在已配置或进行中的会话点击“实时语音面试”。配置中的会话会复用现有 `/start` 接口生成首题。
- 浏览器朗读 AI 问题并持续监听麦克风；识别到与当前问题不同的用户语音时取消朗读，实现插话打断。
- 用户停止说话约 1.1 秒后，前端把本轮实时字幕作为答案提交到现有 `/answers` 接口；返回追问后自动朗读下一题。
- 通话区显示连接、AI 说话、聆听、处理、静音和错误状态，并提供静音、打断 AI、重复问题和结束通话控制。
- 浏览器不支持实时识别或麦克风未授权时，明确降级到现有文字输入、录音转写和音频上传，不阻塞面试。
- 当浏览器没有 `SpeechRecognition` 但支持 `getUserMedia` 和 `MediaRecorder` 时，实时模式使用 `AudioContext` 音量检测：检测到用户开始说话就打断 AI 并录制，连续静音约 0.95 秒后调用现有本地 Whisper 转写接口，再自动提交答案。
- 如果浏览器已经提供 `SpeechRecognition` 但返回 `not-allowed`/`service-not-allowed`，前端不会直接结束会话，而是再次尝试录音降级；只有浏览器连 `getUserMedia` 也拒绝时才显示重试麦克风和文字/手动录音回退。
- AI 朗读默认使用“可爱”风格：优先匹配浏览器已安装的中文女声，找不到时使用较高音调和轻快语速；面试工作台可切换到“标准”。
- 当前实现使用浏览器 `SpeechRecognition` 与 `speechSynthesis` 完成自然轮流对话和插话，不是 OpenAI Realtime，也不是模型级同时双向音频流。音频不由本功能新增持久化，只有识别后的答案文字按既有规则保存。

## 状态机

`configured -> in_progress -> completed`

`configured` 或 `in_progress` 可转为 `cancelled`。重复开始、重复结束和携带相同 `request_id` 的重复答案均返回当前状态，不重复生成问题或报告。

## 数据模型

- `interview_sessions`：配置、状态、简历/职位引用和不可变快照。
- `interview_turns`：面试官问题与候选人回答，按序号保存。
- `interview_reports`：总分、分项分数、证据、优势和改进建议。
- `resume_assets`：上传文件元数据和解析结果，解析正文仍写入现有 `resumes` 表。

## AI 架构

- `local`：默认提供商，采用确定性规则生成问题和证据化评分，离线可测试。
- `openai`：配置 `AI_PROVIDER=openai` 和 API Key 后启用；调用失败时单次请求自动降级到本地提供商。
- 简历和 JD 均作为不可信资料片段处理并限制长度，不能覆盖系统面试规则。
- 评分不补写简历事实，每项分数必须返回对应回答证据。

## API

- `POST /api/resume-uploads`：上传并解析简历。
- `POST /api/interviews`：创建会话。
- `GET /api/interviews`：会话历史，可按状态筛选。
- `GET /api/interviews/{id}`：会话、轮次和报告详情。
- `POST /api/interviews/{id}/start`：生成首题。
- `POST /api/interviews/{id}/answers`：提交答案并生成追问或报告。
- `POST /api/interviews/{id}/complete`：提前结束并幂等生成报告。
- `POST /api/interviews/{id}/cancel`：取消未完成会话。
- `GET /api/interviews/{id}/report`：读取报告。
- `POST /api/interview-audio/transcriptions`：OpenAI 语音转写，可选。
- `POST /api/interview-audio/speech`：OpenAI 语音合成，可选；前端默认可用浏览器语音能力。

## 评分维度

- 岗位相关性：回答是否覆盖岗位职责和关键技能。
- 结构表达：回答是否具备情境、任务、行动、结果结构。
- 证据质量：是否提供数字、结果或可核验细节。
- 沟通清晰度：回答长度、完整性和表达聚焦度。
- 压力应对：在追问和质疑下是否仍能说明取舍、复盘与边界。

压力模式只提高追问强度，不使用侮辱、歧视、诱导泄密或与岗位无关的问题。
