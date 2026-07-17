"use client";

import {
  AudioLines,
  BarChart3,
  FileUp,
  History,
  Mic,
  MicOff,
  Pause,
  PhoneCall,
  PhoneOff,
  Play,
  RotateCcw,
  Send,
  Square,
  Volume2,
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useReducer, useRef, useState } from "react";
import {
  initialVoiceCallState,
  isLikelyPromptEcho,
  mergeVoiceTranscript,
  selectVoiceInputMode,
  speechStyleSettings,
  shouldAutoSubmitVoiceTurn,
  voiceCallReducer,
  voiceCallStatusLabels,
} from "../lib/interviewVoice";

type SpeechRecognitionResultLike = {
  isFinal: boolean;
  0: { transcript: string };
};
type SpeechRecognitionEventLike = Event & {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
};
type SpeechRecognitionErrorEventLike = Event & { error: string };
type BrowserSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};
type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

type Resume = { id: number; title: string; target_role: string; content: string };
type Job = { id: number; title: string; company_name: string; description: string };
type InterviewStatus = "configured" | "in_progress" | "completed" | "cancelled";
type Session = {
  id: number;
  resume_title_snapshot: string;
  job_title_snapshot: string;
  company_snapshot: string;
  target_role: string;
  interview_type: "comprehensive" | "behavioral" | "professional";
  pressure_level: "standard" | "challenging" | "intense";
  question_count: number;
  status: InterviewStatus;
  provider_name: string;
  created_at: string;
  completed_at: string | null;
};
type Turn = {
  id: number;
  role: "interviewer" | "candidate";
  content: string;
  pressure_signal: boolean;
  created_at: string;
};
type Report = {
  overall_score: number;
  dimension_scores: Record<string, number>;
  summary: string;
  strengths: string[];
  improvements: string[];
  evidence: string[];
  recommended_actions: string[];
};
type InterviewDetail = { session: Session; turns: Turn[]; report: Report | null };
type View = "workspace" | "history" | "operations";

const statusLabels: Record<InterviewStatus, string> = {
  configured: "待开始",
  in_progress: "进行中",
  completed: "已完成",
  cancelled: "已取消",
};

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? "请求失败，请稍后重试");
  }
  return response.json() as Promise<T>;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function InterviewPanel({ apiBase }: { apiBase: string }) {
  const [view, setView] = useState<View>("workspace");
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [detail, setDetail] = useState<InterviewDetail | null>(null);
  const [resumeId, setResumeId] = useState("");
  const [jobId, setJobId] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [interviewType, setInterviewType] = useState<Session["interview_type"]>("comprehensive");
  const [pressureLevel, setPressureLevel] = useState<Session["pressure_level"]>("standard");
  const [questionCount, setQuestionCount] = useState(6);
  const [answer, setAnswer] = useState("");
  const [message, setMessage] = useState("正在读取面试数据...");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceMessage, setVoiceMessage] = useState("点击开始录音，或上传已有录音文件");
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [speechStyle, setSpeechStyle] = useState<"cute" | "standard">("cute");
  const [resumeMode, setResumeMode] = useState<"use" | "skip">("use");
  const [voiceCall, dispatchVoiceCall] = useReducer(voiceCallReducer, initialVoiceCallState);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const spokenTurnRef = useRef<number | null>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const recognitionRunningRef = useRef(false);
  const voiceCallActiveRef = useRef(false);
  const voiceMutedRef = useRef(false);
  const voiceProcessingRef = useRef(false);
  const voiceFinalTextRef = useRef("");
  const voiceLiveTextRef = useRef("");
  const currentQuestionRef = useRef("");
  const detailRef = useRef<InterviewDetail | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognitionRestartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fallbackStreamRef = useRef<MediaStream | null>(null);
  const fallbackRecorderRef = useRef<MediaRecorder | null>(null);
  const fallbackAudioContextRef = useRef<AudioContext | null>(null);
  const fallbackAnalyserRef = useRef<AnalyserNode | null>(null);
  const fallbackSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const fallbackChunksRef = useRef<Blob[]>([]);
  const fallbackVadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fallbackLastSpeechAtRef = useRef<number | null>(null);
  const fallbackDetectedAtRef = useRef<number | null>(null);

  async function loadData() {
    const [resumeData, jobData, sessionData] = await Promise.all([
      readJson<Resume[]>(await fetch(`${apiBase}/api/resumes`, { cache: "no-store" })),
      readJson<Job[]>(await fetch(`${apiBase}/api/jobs?include_blacklisted=true`, { cache: "no-store" })),
      readJson<Session[]>(await fetch(`${apiBase}/api/interviews`, { cache: "no-store" })),
    ]);
    setResumes(resumeData);
    setJobs(jobData);
    setSessions(sessionData);
    setResumeId((current) => current || String(resumeData[0]?.id ?? ""));
    setMessage("面试数据已更新");
  }

  useEffect(() => {
    loadData().catch((error: unknown) => setMessage(error instanceof Error ? error.message : "数据加载失败"));
  }, [apiBase]);

  useEffect(() => {
    detailRef.current = detail;
  }, [detail]);

  useEffect(() => () => {
    voiceCallActiveRef.current = false;
    recognitionRef.current?.abort();
    window.speechSynthesis?.cancel();
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    if (recognitionRestartTimerRef.current) clearTimeout(recognitionRestartTimerRef.current);
    if (fallbackVadTimerRef.current) clearTimeout(fallbackVadTimerRef.current);
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    fallbackStreamRef.current?.getTracks().forEach((track) => track.stop());
    void fallbackAudioContextRef.current?.close();
  }, []);

  const latestQuestion = [...(detail?.turns ?? [])].reverse().find((turn) => turn.role === "interviewer");
  useEffect(() => {
    currentQuestionRef.current = latestQuestion?.content ?? "";
  }, [latestQuestion?.content]);

  useEffect(() => {
    if (autoSpeak && !voiceCallActiveRef.current && latestQuestion && spokenTurnRef.current !== latestQuestion.id) {
      spokenTurnRef.current = latestQuestion.id;
      speak(latestQuestion.content);
    }
  }, [autoSpeak, latestQuestion?.id]);

  function speak(text: string, liveCall = false) {
    if (!("speechSynthesis" in window)) {
      setMessage("当前浏览器不支持语音朗读");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    const style = speechStyleSettings[speechStyle];
    utterance.rate = style.rate;
    utterance.pitch = style.pitch;
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find((voice) =>
      /zh[-_]?(cn|hans)?|中文|普通话|mandarin/i.test(`${voice.lang} ${voice.name}`)
      && (speechStyle === "standard" || /女|female|xiaoxiao|yaoyao|tingting|huihui/i.test(voice.name)),
    );
    if (preferredVoice) utterance.voice = preferredVoice;
    if (liveCall) {
      utterance.onstart = () => dispatchVoiceCall({ type: "ai_speaking" });
      utterance.onend = () => {
        if (!voiceCallActiveRef.current || voiceMutedRef.current || voiceProcessingRef.current) return;
        dispatchVoiceCall({ type: "listening" });
        ensureRecognitionRunning();
      };
      utterance.onerror = () => {
        if (!voiceCallActiveRef.current) return;
        dispatchVoiceCall({ type: "listening" });
        ensureRecognitionRunning();
      };
    }
    window.speechSynthesis.speak(utterance);
  }

  function clearVoiceTimers() {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    if (recognitionRestartTimerRef.current) clearTimeout(recognitionRestartTimerRef.current);
    silenceTimerRef.current = null;
    recognitionRestartTimerRef.current = null;
  }

  function scheduleVoiceSubmission() {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = setTimeout(() => void submitVoiceTurn(), 1100);
  }

  function ensureRecognition() {
    if (recognitionRef.current) return recognitionRef.current;
    const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Recognition) return null;

    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "zh-CN";
    recognition.onstart = () => {
      recognitionRunningRef.current = true;
    };
    recognition.onresult = (event) => {
      if (!voiceCallActiveRef.current || voiceMutedRef.current || voiceProcessingRef.current) return;
      let finalAddition = "";
      let interimText = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result[0]?.transcript ?? "";
        if (result.isFinal) finalAddition = mergeVoiceTranscript(finalAddition, transcript);
        else interimText = mergeVoiceTranscript(interimText, transcript);
      }

      const incoming = mergeVoiceTranscript(finalAddition, interimText);
      if (!incoming) return;
      if (window.speechSynthesis.speaking && isLikelyPromptEcho(incoming, currentQuestionRef.current)) return;
      if (window.speechSynthesis.speaking) window.speechSynthesis.cancel();

      if (finalAddition) voiceFinalTextRef.current = mergeVoiceTranscript(voiceFinalTextRef.current, finalAddition);
      const liveText = mergeVoiceTranscript(voiceFinalTextRef.current, interimText);
      voiceLiveTextRef.current = liveText;
      dispatchVoiceCall({ type: "user_speech", interimText: liveText });
      scheduleVoiceSubmission();
    };
    recognition.onerror = (event) => {
      recognitionRunningRef.current = false;
      if (event.error === "aborted" || event.error === "no-speech") return;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        recognitionRef.current?.abort();
        recognitionRef.current = null;
        void (async () => {
          if (voiceCallActiveRef.current && await startFallbackVoiceInput()) {
            dispatchVoiceCall({ type: "listening" });
            setMessage("浏览器语音识别未获授权，已切换为录音转写模式");
            return;
          }
          stopVoiceCall(false);
          dispatchVoiceCall({ type: "fail", error: "浏览器拒绝了麦克风权限，请允许后点击重试。" });
          setMessage("麦克风权限未开启，仍可使用文字或录音方式作答");
        })();
        return;
      }
      setMessage(`实时语音识别暂时中断（${event.error}），正在尝试恢复`);
    };
    recognition.onend = () => {
      recognitionRunningRef.current = false;
      if (!voiceCallActiveRef.current || voiceMutedRef.current || voiceProcessingRef.current) return;
      recognitionRestartTimerRef.current = setTimeout(ensureRecognitionRunning, 180);
    };
    recognitionRef.current = recognition;
    return recognition;
  }

  function ensureRecognitionRunning() {
    if (!voiceCallActiveRef.current || voiceMutedRef.current || voiceProcessingRef.current || recognitionRunningRef.current) return;
    const recognition = ensureRecognition();
    if (!recognition) return;
    try {
      recognitionRunningRef.current = true;
      recognition.start();
    } catch {
      recognitionRunningRef.current = false;
    }
  }

  function stopVoiceCall(showEndedState = true) {
    voiceCallActiveRef.current = false;
    voiceMutedRef.current = false;
    voiceProcessingRef.current = false;
    voiceFinalTextRef.current = "";
    voiceLiveTextRef.current = "";
    clearVoiceTimers();
    window.speechSynthesis?.cancel();
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    recognitionRunningRef.current = false;
    if (fallbackVadTimerRef.current) clearTimeout(fallbackVadTimerRef.current);
    fallbackVadTimerRef.current = null;
    if (fallbackRecorderRef.current && fallbackRecorderRef.current.state !== "inactive") fallbackRecorderRef.current.stop();
    fallbackRecorderRef.current = null;
    fallbackStreamRef.current?.getTracks().forEach((track) => track.stop());
    fallbackStreamRef.current = null;
    fallbackSourceRef.current?.disconnect();
    fallbackSourceRef.current = null;
    fallbackAnalyserRef.current = null;
    void fallbackAudioContextRef.current?.close();
    fallbackAudioContextRef.current = null;
    fallbackLastSpeechAtRef.current = null;
    fallbackDetectedAtRef.current = null;
    if (showEndedState) dispatchVoiceCall({ type: "end" });
  }

  async function transcribeFallbackAnswer(blob: Blob) {
    if (!voiceCallActiveRef.current || !blob.size) return;
    voiceProcessingRef.current = true;
    dispatchVoiceCall({ type: "processing", finalText: "正在转写你的回答..." });
    setMessage("正在转写实时回答，首次使用本地模型可能需要等待下载...");
    try {
      const form = new FormData();
      form.append("file", blob, "live-interview-answer.webm");
      const result = await readJson<{ text: string }>(
        await fetch(`${apiBase}/api/interview-audio/transcriptions`, { method: "POST", body: form }),
      );
      voiceProcessingRef.current = false;
      if (result.text.trim()) await continueVoiceTurn(result.text);
      else {
        dispatchVoiceCall({ type: "listening" });
        setMessage("没有识别到有效回答，请重新说一遍");
      }
    } catch (error) {
      voiceProcessingRef.current = false;
      dispatchVoiceCall({ type: "listening" });
      setMessage(error instanceof Error ? error.message : "实时语音转写失败，请改用文字或录音");
    }
  }

  function startFallbackRecorder() {
    if (fallbackRecorderRef.current || !fallbackStreamRef.current || !voiceCallActiveRef.current || voiceMutedRef.current) return;
    const preferredType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
    const recorder = new MediaRecorder(fallbackStreamRef.current, { mimeType: preferredType });
    fallbackChunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) fallbackChunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(fallbackChunksRef.current, { type: recorder.mimeType });
      fallbackRecorderRef.current = null;
      if (blob.size > 0 && voiceCallActiveRef.current) void transcribeFallbackAnswer(blob);
    };
    recorder.start(250);
    fallbackRecorderRef.current = recorder;
  }

  function monitorFallbackVoice() {
    if (!voiceCallActiveRef.current || voiceMutedRef.current || !fallbackAnalyserRef.current) return;
    const analyser = fallbackAnalyserRef.current;
    const samples = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(samples);
    const rms = Math.sqrt(samples.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / samples.length);
    const now = Date.now();
    const speaking = !voiceProcessingRef.current && rms > 0.045;
    if (speaking) {
      fallbackDetectedAtRef.current ??= now;
      fallbackLastSpeechAtRef.current = now;
      if (now - fallbackDetectedAtRef.current > 120) {
        if (window.speechSynthesis.speaking) {
          window.speechSynthesis.cancel();
          dispatchVoiceCall({ type: "listening" });
        }
        startFallbackRecorder();
      }
    } else {
      fallbackDetectedAtRef.current = null;
      if (fallbackRecorderRef.current && fallbackLastSpeechAtRef.current && now - fallbackLastSpeechAtRef.current > 950) {
        fallbackRecorderRef.current.stop();
        fallbackLastSpeechAtRef.current = null;
      }
    }
    fallbackVadTimerRef.current = setTimeout(monitorFallbackVoice, 80);
  }

  async function startFallbackVoiceInput() {
    if (!navigator.mediaDevices?.getUserMedia || !("MediaRecorder" in window)) return false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      fallbackStreamRef.current = stream;
      fallbackAudioContextRef.current = audioContext;
      fallbackSourceRef.current = source;
      fallbackAnalyserRef.current = analyser;
      monitorFallbackVoice();
      return true;
    } catch {
      return false;
    }
  }

  async function transcribeAudio(audio: Blob, filename: string) {
    setTranscribing(true);
    setVoiceMessage("正在转写语音，首次使用本地模型可能需要等待下载...");
    try {
      const form = new FormData();
      form.append("file", audio, filename);
      const result = await readJson<{ text: string; engine?: string }>(
        await fetch(`${apiBase}/api/interview-audio/transcriptions`, { method: "POST", body: form }),
      );
      setAnswer((current) => `${current}${current ? "\n" : ""}${result.text}`);
      setVoiceMessage(`转写完成${result.engine ? ` · ${result.engine}` : ""}，文字已加入回答框`);
    } catch (error) {
      setVoiceMessage(error instanceof Error ? error.message : "语音转写失败");
    } finally {
      setTranscribing(false);
    }
  }

  async function toggleRecording() {
    if (recording) {
      mediaRecorderRef.current?.stop();
      setVoiceMessage("录音已停止，正在准备转写...");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !("MediaRecorder" in window)) {
      setVoiceMessage("当前浏览器不支持录音，请使用“上传录音”或直接输入文字");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType: preferredType });
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType });
        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        mediaRecorderRef.current = null;
        setRecording(false);
        if (blob.size > 0) void transcribeAudio(blob, "interview-answer.webm");
        else setVoiceMessage("没有录到有效声音，请重试");
      };
      recorder.start(500);
      setRecording(true);
      setVoiceMessage("正在录音，请回答问题；完成后点击“停止录音”");
    } catch {
      setVoiceMessage("无法使用麦克风，请允许录音权限，或改用“上传录音”");
    }
  }

  async function uploadRecording(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    await transcribeAudio(file, file.name);
    input.value = "";
  }

  async function uploadResume(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    setBusy(true);
    setMessage(`正在上传并解析 ${file.name}...`);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", "");
      form.append("target_role", targetRole);
      const result = await readJson<{ resume_id: number; extracted_characters: number }>(
        await fetch(`${apiBase}/api/resume-uploads`, { method: "POST", body: form }),
      );
      await loadData();
      setResumeMode("use");
      setResumeId(String(result.resume_id));
      setMessage(`${file.name} 上传成功，已提取 ${result.extracted_characters} 个字符并自动选中`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "简历解析失败");
    } finally {
      setBusy(false);
      input.value = "";
    }
  }

  async function createInterview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (resumeMode === "use" && !resumeId) {
      setMessage("请先选择已有简历，或上传一份新简历");
      return;
    }
    setBusy(true);
    setMessage("正在创建面试...");
    try {
      const created = await readJson<InterviewDetail>(
        await fetch(`${apiBase}/api/interviews`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resume_id: resumeMode === "use" && resumeId ? Number(resumeId) : null,
            job_id: jobId ? Number(jobId) : null,
            target_role: targetRole,
            interview_type: interviewType,
            pressure_level: pressureLevel,
            question_count: questionCount,
          }),
        }),
      );
      setDetail(created);
      await loadData();
      setMessage("面试已创建，可以开始");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function runAction(action: "start" | "complete" | "cancel") {
    const currentDetail = detailRef.current;
    if (!currentDetail) return null;
    setBusy(true);
    setMessage(action === "start" ? "正在生成首题..." : "正在更新面试状态...");
    try {
      const next = await readJson<InterviewDetail>(
        await fetch(`${apiBase}/api/interviews/${currentDetail.session.id}/${action}`, { method: "POST" }),
      );
      setDetail(next);
      detailRef.current = next;
      await loadData();
      setMessage(action === "start" ? "面试已开始" : "面试状态已更新");
      return next;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswerText(content: string, sessionId?: number) {
    const normalized = content.trim();
    const targetSessionId = sessionId ?? detailRef.current?.session.id;
    if (!targetSessionId || !normalized) return null;
    setBusy(true);
    setMessage("正在分析回答并生成追问...");
    try {
      const next = await readJson<InterviewDetail>(
        await fetch(`${apiBase}/api/interviews/${targetSessionId}/answers`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: normalized, request_id: crypto.randomUUID() }),
        }),
      );
      setDetail(next);
      detailRef.current = next;
      setAnswer("");
      await loadData();
      setMessage(next.session.status === "completed" ? "面试完成，报告已生成" : "已生成下一道追问");
      return next;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "回答提交失败");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitAnswerText(answer);
  }

  async function continueVoiceTurn(content: string) {
    const currentDetail = detailRef.current;
    const normalizedContent = content.trim();
    if (!currentDetail || !shouldAutoSubmitVoiceTurn({
      active: voiceCallActiveRef.current,
      muted: voiceMutedRef.current,
      processing: voiceProcessingRef.current,
      text: normalizedContent,
    })) return;

    voiceProcessingRef.current = true;
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = null;
    recognitionRef.current?.abort();
    recognitionRunningRef.current = false;
    window.speechSynthesis.cancel();
    dispatchVoiceCall({ type: "processing", finalText: normalizedContent });

    const next = await submitAnswerText(normalizedContent, currentDetail.session.id);
    voiceFinalTextRef.current = "";
    voiceLiveTextRef.current = "";
    voiceProcessingRef.current = false;
    if (!voiceCallActiveRef.current) return;

    if (!next) {
      setAnswer(content);
      dispatchVoiceCall({ type: "listening" });
      ensureRecognitionRunning();
      return;
    }
    if (next.session.status === "completed") {
      stopVoiceCall();
      setMessage("实时面试已完成，评分报告已生成");
      return;
    }

    const nextQuestion = [...next.turns].reverse().find((turn) => turn.role === "interviewer");
    if (!nextQuestion) {
      stopVoiceCall(false);
      dispatchVoiceCall({ type: "fail", error: "没有收到下一道面试问题，请使用文字方式继续。" });
      return;
    }
    currentQuestionRef.current = nextQuestion.content;
    spokenTurnRef.current = nextQuestion.id;
    dispatchVoiceCall({ type: "next_question" });
    ensureRecognitionRunning();
    speak(nextQuestion.content, true);
  }

  async function submitVoiceTurn() {
    await continueVoiceTurn(voiceLiveTextRef.current);
  }

  async function startVoiceCall() {
    if (!detailRef.current) return;
    const inputMode = selectVoiceInputMode({
      speechRecognition: Boolean(window.SpeechRecognition ?? window.webkitSpeechRecognition),
      mediaRecorder: "MediaRecorder" in window,
      microphone: Boolean(navigator.mediaDevices?.getUserMedia),
    });
    if (!("speechSynthesis" in window) || inputMode === "unsupported") {
      dispatchVoiceCall({ type: "fail", error: "当前浏览器没有可用的语音输入或麦克风权限，请使用文字或录音方式。" });
      setMessage("实时语音不可用，现有文字和录音面试仍可使用");
      return;
    }

    stopVoiceCall(false);
    dispatchVoiceCall({ type: "connect" });
    voiceCallActiveRef.current = true;
    voiceMutedRef.current = false;
    setMessage("正在连接实时语音面试...");
    if (inputMode === "recognition") ensureRecognitionRunning();
    else if (!(await startFallbackVoiceInput())) {
      stopVoiceCall(false);
      dispatchVoiceCall({ type: "fail", error: "无法打开麦克风，请检查浏览器权限后重试。" });
      setMessage("麦克风不可用，仍可使用文字或录音面试");
      return;
    }

    let activeDetail: InterviewDetail | null = detailRef.current;
    if (activeDetail?.session.status === "configured") activeDetail = await runAction("start");
    if (!voiceCallActiveRef.current) return;
    if (!activeDetail || activeDetail.session.status !== "in_progress") {
      stopVoiceCall(false);
      dispatchVoiceCall({ type: "fail", error: "面试未能开始，请稍后重试或使用文字方式。" });
      return;
    }

    const question = [...activeDetail.turns].reverse().find((turn) => turn.role === "interviewer");
    if (!question) {
      stopVoiceCall(false);
      dispatchVoiceCall({ type: "fail", error: "没有收到面试问题，请稍后重试。" });
      return;
    }
    currentQuestionRef.current = question.content;
    spokenTurnRef.current = question.id;
    dispatchVoiceCall({ type: "ai_speaking" });
    speak(question.content, true);
    setMessage("实时语音面试进行中");
  }

  function toggleVoiceMute() {
    const nextMuted = !voiceMutedRef.current;
    voiceMutedRef.current = nextMuted;
    if (nextMuted) {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      recognitionRef.current?.abort();
      recognitionRunningRef.current = false;
      if (fallbackVadTimerRef.current) clearTimeout(fallbackVadTimerRef.current);
      fallbackVadTimerRef.current = null;
      if (fallbackRecorderRef.current && fallbackRecorderRef.current.state !== "inactive") fallbackRecorderRef.current.stop();
      fallbackRecorderRef.current = null;
      fallbackLastSpeechAtRef.current = null;
      fallbackDetectedAtRef.current = null;
      dispatchVoiceCall({ type: "mute" });
    } else {
      dispatchVoiceCall({ type: "unmute" });
      if (window.speechSynthesis.speaking) dispatchVoiceCall({ type: "ai_speaking" });
      ensureRecognitionRunning();
      if (fallbackAnalyserRef.current) monitorFallbackVoice();
    }
  }

  function interruptAiSpeech() {
    window.speechSynthesis.cancel();
    if (!voiceMutedRef.current) dispatchVoiceCall({ type: "listening" });
    ensureRecognitionRunning();
  }

  function repeatLatestQuestion() {
    const question = currentQuestionRef.current;
    if (!question) return;
    ensureRecognitionRunning();
    speak(question, true);
  }

  async function endVoiceCall() {
    const shouldComplete = detailRef.current?.session.status === "in_progress";
    stopVoiceCall();
    setMessage("实时语音通话已结束");
    if (shouldComplete) await runAction("complete");
  }

  async function openSession(sessionId: number) {
    stopVoiceCall(false);
    dispatchVoiceCall({ type: "reset" });
    setBusy(true);
    try {
      const data = await readJson<InterviewDetail>(await fetch(`${apiBase}/api/interviews/${sessionId}`));
      setDetail(data);
      setView("workspace");
      setMessage("已打开历史面试");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "读取面试失败");
    } finally {
      setBusy(false);
    }
  }

  function resetWorkspace() {
    stopVoiceCall(false);
    dispatchVoiceCall({ type: "reset" });
    setDetail(null);
    setAnswer("");
    spokenTurnRef.current = null;
    setMessage("可以配置一场新面试");
  }

  const completed = sessions.filter((session) => session.status === "completed").length;
  const active = sessions.filter((session) => session.status === "in_progress").length;
  const pressureSessions = sessions.filter((session) => session.pressure_level !== "standard").length;
  const voiceCallInProgress = !["idle", "ended", "error"].includes(voiceCall.status);

  return (
    <section>
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-xl font-semibold">AI 模拟面试</h2>
          <p className="mt-1 text-sm text-muted">基于已有简历和目标 JD 连续追问，保留证据化评分与复盘记录。</p>
        </div>
        <span className="text-xs text-muted" aria-live="polite">{message}</span>
      </div>

      <div className="interview-view-tabs" role="tablist" aria-label="面试视图">
        <button type="button" className={view === "workspace" ? "active" : ""} onClick={() => setView("workspace")}><Play size={15} />面试工作台</button>
        <button type="button" className={view === "history" ? "active" : ""} onClick={() => setView("history")}><History size={15} />历史记录</button>
        <button type="button" className={view === "operations" ? "active" : ""} onClick={() => setView("operations")}><BarChart3 size={15} />运营视图</button>
      </div>

      {view === "workspace" && !detail && (
        <div className="grid gap-8 pt-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <form onSubmit={createInterview} className="space-y-6">
            <div>
              <h3 className="text-sm font-semibold">面试配置</h3>
              <div className="mt-4 grid gap-5 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <span className="resume-mode-label">是否使用简历</span>
                  <div className="resume-mode-selector">
                    <label className="checkbox-option">
                      <input
                        type="radio"
                        name="resume-mode"
                        checked={resumeMode === "use"}
                        onChange={() => setResumeMode("use")}
                      />
                      <span>选择简历</span>
                    </label>
                    <label className="checkbox-option">
                      <input
                        type="radio"
                        name="resume-mode"
                        checked={resumeMode === "skip"}
                        onChange={() => setResumeMode("skip")}
                      />
                      <span>不选择简历</span>
                    </label>
                  </div>
                </div>
                {resumeMode === "use" ? (
                  <label className="field-label">
                    <span>已有简历</span>
                    <select required value={resumeId} onChange={(event) => setResumeId(event.target.value)}>
                      <option value="">请选择已有简历</option>
                      {resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.title}</option>)}
                    </select>
                    <small>没有可用简历时，可在右侧上传新简历。</small>
                  </label>
                ) : (
                  <div className="resume-mode-empty">
                    <strong>本次不使用简历</strong>
                    <span>AI 将根据目标岗位进行通用面试，不引用个人经历。</span>
                  </div>
                )}
                <label className="field-label">
                  <span>职位来源</span>
                  <select
                    value={jobId}
                    onChange={(event) => {
                      const nextJobId = event.target.value;
                      const job = jobs.find((item) => item.id === Number(nextJobId));
                      setJobId(nextJobId);
                      setTargetRole(job?.title ?? "");
                    }}
                  >
                    <option value="">手动填写岗位</option>
                    {jobs.map((job) => (
                      <option key={job.id} value={job.id}>
                        {job.title} · {job.company_name || "未填写公司"}
                      </option>
                    ))}
                  </select>
                </label>
                {!jobId && (
                  <label className="field-label manual-role-field">
                    <span>手动填写岗位名称 *</span>
                    <input
                      required
                      autoFocus
                      maxLength={160}
                      value={targetRole}
                      onChange={(event) => setTargetRole(event.target.value)}
                      placeholder="请输入岗位，例如：短视频运营实习生"
                    />
                    <small>该岗位名称将用于生成面试问题和评分报告。</small>
                  </label>
                )}
                {jobId && (
                  <div className="selected-job-summary">
                    <span>当前面试岗位</span>
                    <strong>{targetRole}</strong>
                    <small>{jobs.find((job) => job.id === Number(jobId))?.company_name || "未填写公司"}</small>
                  </div>
                )}
                <label className="field-label"><span>面试类型</span><select value={interviewType} onChange={(event) => setInterviewType(event.target.value as Session["interview_type"])}><option value="comprehensive">综合面试</option><option value="behavioral">行为面试</option><option value="professional">专业面试</option></select></label>
                <label className="field-label"><span>压力等级</span><select value={pressureLevel} onChange={(event) => setPressureLevel(event.target.value as Session["pressure_level"])}><option value="standard">标准</option><option value="challenging">挑战</option><option value="intense">高压</option></select><small>高压模式只提高追问强度，不包含攻击性问题。</small></label>
                <label className="field-label"><span>题目数量</span><input type="number" min={3} max={12} value={questionCount} onChange={(event) => setQuestionCount(Number(event.target.value))} /></label>
              </div>
            </div>
            <div className="flex justify-end border-t border-slate-200 pt-5"><button type="submit" className="button-primary" disabled={busy}>创建面试</button></div>
          </form>

          <aside className="interview-upload-panel">
            <div className="flex items-center gap-2"><FileUp size={17} className="text-brand" /><h3 className="text-sm font-semibold">上传新简历</h3></div>
            {resumeMode === "use" ? (
              <>
                <p className="mt-2 text-xs leading-5 text-muted">支持 PDF、DOCX、TXT、Markdown。选择文件后将自动上传、解析并选中。</p>
                <label className={`upload-drop mt-4 ${busy ? "upload-drop-disabled" : ""}`}>
                  <input type="file" accept=".pdf,.docx,.txt,.md" disabled={busy} onChange={uploadResume} />
                  <FileUp size={20} />
                  <span>{busy ? "正在处理简历..." : "点击选择并上传简历"}</span>
                </label>
                <p className="mt-3 text-xs leading-5 text-muted">单个文件不超过 8 MB。扫描版 PDF 需要先转换为可复制文字。</p>
              </>
            ) : (
              <div className="resume-upload-skipped">已选择“不选择简历”，本次无需上传。</div>
            )}
          </aside>
        </div>
      )}

      {view === "workspace" && detail && (
        <div className="pt-6">
          <div className="interview-session-bar">
            <div><strong>{detail.session.target_role}</strong><span>{detail.session.company_snapshot || "模拟岗位"} · {detail.session.question_count} 题 · {statusLabels[detail.session.status]}</span></div>
            <div className="flex flex-wrap gap-2">
              <label className="checkbox-option compact-button"><input type="checkbox" checked={autoSpeak} onChange={(event) => setAutoSpeak(event.target.checked)} />自动朗读</label>
              <label className="voice-style-selector"><span>音色</span><select value={speechStyle} onChange={(event) => setSpeechStyle(event.target.value as "cute" | "standard")}><option value="cute">可爱</option><option value="standard">标准</option></select></label>
              <button type="button" className="button-secondary compact-button" onClick={resetWorkspace}><RotateCcw size={15} />新建面试</button>
              {(detail.session.status === "configured" || detail.session.status === "in_progress") && !voiceCallInProgress && <button type="button" className="button-primary compact-button" disabled={busy} onClick={() => void startVoiceCall()}><PhoneCall size={15} />实时语音面试</button>}
              {detail.session.status === "configured" && !voiceCallInProgress && <button type="button" className="button-secondary compact-button" disabled={busy} onClick={() => void runAction("start")}><Play size={15} />文字面试</button>}
              {detail.session.status === "in_progress" && !voiceCallInProgress && <button type="button" className="button-secondary compact-button" disabled={busy} onClick={() => void runAction("complete")}><Square size={15} />提前结束</button>}
            </div>
          </div>

          {voiceCall.status !== "idle" && voiceCall.status !== "ended" && (
            <section className={`interview-live-call interview-live-call-${voiceCall.status}`} aria-label="实时语音面试" aria-live="polite">
              <div className="interview-live-call-main">
                <div className="interview-live-status">
                  <AudioLines size={18} />
                  <span>{voiceCallStatusLabels[voiceCall.status]}</span>
                </div>
                <p className="interview-live-question">{latestQuestion?.content ?? "正在准备面试问题..."}</p>
                <div className="interview-live-caption">
                  <strong>实时字幕</strong>
                  <span>{voiceCall.error || voiceCall.interimText || voiceCall.finalText || (voiceCall.status === "ai_speaking" ? "AI 面试官正在提问" : "等待你的回答...")}</span>
                </div>
              </div>
              {voiceCallInProgress && (
                <div className="interview-live-controls">
                  <button type="button" title={voiceCall.muted ? "开启麦克风" : "静音麦克风"} aria-label={voiceCall.muted ? "开启麦克风" : "静音麦克风"} aria-pressed={voiceCall.muted} onClick={toggleVoiceMute}>
                    {voiceCall.muted ? <MicOff size={18} /> : <Mic size={18} />}
                  </button>
                  <button type="button" title="打断 AI 说话" aria-label="打断 AI 说话" onClick={interruptAiSpeech} disabled={voiceCall.status !== "ai_speaking"}>
                    <Pause size={18} />
                  </button>
                  <button type="button" title="重复当前问题" aria-label="重复当前问题" onClick={repeatLatestQuestion}>
                    <Volume2 size={18} />
                  </button>
                  <button type="button" className="interview-end-call" onClick={() => void endVoiceCall()} disabled={busy}>
                    <PhoneOff size={17} />结束通话
                  </button>
                </div>
              )}
              {voiceCall.status === "error" && (
                <div className="interview-live-error-actions">
                  <button type="button" className="button-secondary compact-button" onClick={() => void startVoiceCall()} disabled={busy}>
                    <Mic size={15} />重试麦克风
                  </button>
                  <span>也可以继续使用下方文字或手动录音。</span>
                </div>
              )}
            </section>
          )}

          <div className="interview-transcript" aria-live="polite">
            {detail.turns.map((turn) => <article key={turn.id} className={`interview-turn interview-turn-${turn.role}`}><div><strong>{turn.role === "interviewer" ? "AI 面试官" : "我的回答"}</strong>{turn.pressure_signal && <span>压力追问</span>}</div><p>{turn.content}</p>{turn.role === "interviewer" && <button type="button" title="朗读问题" aria-label="朗读问题" onClick={() => speak(turn.content)}><Volume2 size={16} /></button>}</article>)}
            {!detail.turns.length && <div className="empty-panel">配置已保存，点击“开始”生成第一道问题。</div>}
          </div>

          {detail.session.status === "in_progress" && (
            <form onSubmit={submitAnswer} className="interview-answer-box">
              <label className="field-label"><span>回答</span><textarea rows={6} value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="建议按情境、任务、行动、结果组织回答" /></label>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap gap-2"><button type="button" className={`button-secondary icon-text-button ${recording ? "recording" : ""}`} onClick={() => void toggleRecording()} disabled={busy || transcribing}>{recording ? <Square size={16} /> : <Mic size={16} />}{recording ? "停止录音" : "开始录音"}</button><label className={`button-secondary icon-text-button cursor-pointer ${transcribing ? "pointer-events-none opacity-60" : ""}`}><FileUp size={16} />上传录音<input className="sr-only" type="file" accept=".mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm,audio/*" disabled={transcribing} onChange={uploadRecording} /></label></div>
                <button type="submit" className="button-primary icon-text-button" disabled={busy || transcribing || !answer.trim()}><Send size={16} />提交回答</button>
              </div>
              <p className={`voice-status ${recording ? "voice-status-recording" : ""}`} aria-live="polite">{voiceMessage}</p>
            </form>
          )}

          {detail.report && <InterviewReportView report={detail.report} />}
        </div>
      )}

      {view === "history" && <div className="divide-y divide-slate-200 pt-3">{sessions.map((session) => <button key={session.id} type="button" className="interview-history-row" onClick={() => void openSession(session.id)} disabled={busy}><div><strong>{session.target_role}</strong><span>{session.company_snapshot || "模拟岗位"} · {formatDate(session.created_at)}</span></div><div><span className={`interview-status interview-status-${session.status}`}>{statusLabels[session.status]}</span><small>{session.provider_name}</small></div></button>)}{!sessions.length && <div className="empty-panel mt-4">还没有面试记录。</div>}</div>}

      {view === "operations" && <div className="pt-6"><div className="analytics-metrics"><div className="metric-card"><span>累计面试</span><strong>{sessions.length}</strong><small>所有历史会话</small></div><div className="metric-card"><span>已完成</span><strong>{completed}</strong><small>完成率 {sessions.length ? Math.round(completed / sessions.length * 100) : 0}%</small></div><div className="metric-card"><span>进行中</span><strong>{active}</strong><small>可继续作答</small></div><div className="metric-card"><span>压力模式</span><strong>{pressureSessions}</strong><small>挑战及高压会话</small></div><div className="metric-card"><span>本地兜底</span><strong>{sessions.filter((item) => item.provider_name === "local").length}</strong><small>无 API Key 也可运行</small></div><div className="metric-card"><span>OpenAI</span><strong>{sessions.filter((item) => item.provider_name === "openai").length}</strong><small>模型驱动会话</small></div></div><div className="analytics-section mt-6"><h3>最近会话</h3><div className="mt-3 divide-y divide-slate-200">{sessions.slice(0, 8).map((session) => <button key={session.id} type="button" className="interview-history-row" onClick={() => void openSession(session.id)}><div><strong>{session.target_role}</strong><span>{session.interview_type} · {session.pressure_level}</span></div><span className={`interview-status interview-status-${session.status}`}>{statusLabels[session.status]}</span></button>)}</div></div></div>}
    </section>
  );
}

function InterviewReportView({ report }: { report: Report }) {
  return <section className="interview-report"><div className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-center"><div className="score-display"><strong>{report.overall_score}</strong><span>/ 100</span></div><div><h3 className="text-base font-semibold">面试分析报告</h3><p className="mt-1 text-sm leading-6 text-muted">{report.summary}</p></div></div><div className="mt-5 grid gap-4 sm:grid-cols-2">{Object.entries(report.dimension_scores).map(([name, score]) => <div key={name} className="distribution-row"><div><span>{name}</span><strong>{score}</strong></div><div className="distribution-track"><span style={{ width: `${score}%` }} /></div></div>)}</div><div className="mt-6 grid gap-6 lg:grid-cols-2"><ReportList title="优势" items={report.strengths} tone="positive" /><ReportList title="改进重点" items={report.improvements} tone="warning" /><ReportList title="评分证据" items={report.evidence} /><ReportList title="下一步行动" items={report.recommended_actions} /></div></section>;
}

function ReportList({ title, items, tone = "default" }: { title: string; items: string[]; tone?: "default" | "positive" | "warning" }) {
  return <div className={`report-list report-list-${tone}`}><h4>{title}</h4><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></div>;
}
