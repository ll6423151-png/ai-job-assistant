export type VoiceCallStatus =
  | "idle"
  | "connecting"
  | "ai_speaking"
  | "listening"
  | "processing"
  | "muted"
  | "ended"
  | "error";

export type VoiceCallState = {
  status: VoiceCallStatus;
  muted: boolean;
  interimText: string;
  finalText: string;
  error: string;
};

export type VoiceCallAction =
  | { type: "connect" }
  | { type: "ai_speaking" }
  | { type: "listening" }
  | { type: "user_speech"; interimText: string }
  | { type: "processing"; finalText: string }
  | { type: "next_question" }
  | { type: "mute" }
  | { type: "unmute" }
  | { type: "end" }
  | { type: "fail"; error: string }
  | { type: "reset" };

export const initialVoiceCallState: VoiceCallState = {
  status: "idle",
  muted: false,
  interimText: "",
  finalText: "",
  error: "",
};

export const voiceCallStatusLabels: Record<VoiceCallStatus, string> = {
  idle: "未连接",
  connecting: "正在连接",
  ai_speaking: "AI 正在说话",
  listening: "正在聆听",
  processing: "正在分析回答",
  muted: "麦克风已静音",
  ended: "通话已结束",
  error: "实时语音不可用",
};

export const speechStyleSettings = {
  cute: { rate: 1.02, pitch: 1.16 },
  standard: { rate: 0.95, pitch: 1 },
} as const;

export function selectVoiceInputMode({
  speechRecognition,
  mediaRecorder,
  microphone,
}: {
  speechRecognition: boolean;
  mediaRecorder: boolean;
  microphone: boolean;
}) {
  if (speechRecognition) return "recognition" as const;
  if (mediaRecorder && microphone) return "recorder" as const;
  return "unsupported" as const;
}

export function mergeVoiceTranscript(current: string, addition: string) {
  const left = current.trim();
  const right = addition.trim();
  if (!right) return left;
  return left ? `${left} ${right}` : right;
}

export function shouldAutoSubmitVoiceTurn({
  active,
  muted,
  processing,
  text,
}: {
  active: boolean;
  muted: boolean;
  processing: boolean;
  text: string;
}) {
  return active && !muted && !processing && Boolean(text.trim());
}

export function isLikelyPromptEcho(transcript: string, prompt: string) {
  const normalize = (value: string) => value.toLowerCase().replace(/[\s，。！？、,.!?：:；;“”"'（）()]/g, "");
  const candidate = normalize(transcript);
  const question = normalize(prompt);
  return candidate.length >= 2 && question.length >= 2 && (question.includes(candidate) || candidate.includes(question));
}

export function voiceCallReducer(state: VoiceCallState, action: VoiceCallAction): VoiceCallState {
  switch (action.type) {
    case "connect":
      return { ...initialVoiceCallState, status: "connecting" };
    case "ai_speaking":
      return { ...state, status: state.muted ? "muted" : "ai_speaking", error: "" };
    case "listening":
      return { ...state, status: state.muted ? "muted" : "listening", error: "" };
    case "user_speech":
      return { ...state, status: state.muted ? "muted" : "listening", interimText: action.interimText, error: "" };
    case "processing":
      return { ...state, status: "processing", finalText: action.finalText, interimText: "", error: "" };
    case "next_question":
      return { ...state, status: state.muted ? "muted" : "ai_speaking", interimText: "", finalText: "", error: "" };
    case "mute":
      return { ...state, status: "muted", muted: true };
    case "unmute":
      return { ...state, status: "listening", muted: false, error: "" };
    case "end":
      return { ...initialVoiceCallState, status: "ended" };
    case "fail":
      return { ...initialVoiceCallState, status: "error", error: action.error };
    case "reset":
      return initialVoiceCallState;
    default:
      return state;
  }
}
