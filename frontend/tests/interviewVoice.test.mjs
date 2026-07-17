import assert from "node:assert/strict";
import test from "node:test";

import {
  initialVoiceCallState,
  isLikelyPromptEcho,
  mergeVoiceTranscript,
  shouldAutoSubmitVoiceTurn,
  selectVoiceInputMode,
  speechStyleSettings,
  voiceCallReducer,
} from "../src/app/lib/interviewVoice.ts";

test("voice call follows speaking, interruption, processing and listening states", () => {
  let state = voiceCallReducer(initialVoiceCallState, { type: "connect" });
  assert.equal(state.status, "connecting");

  state = voiceCallReducer(state, { type: "ai_speaking" });
  assert.equal(state.status, "ai_speaking");

  state = voiceCallReducer(state, { type: "user_speech", interimText: "我负责过" });
  assert.equal(state.status, "listening");
  assert.equal(state.interimText, "我负责过");

  state = voiceCallReducer(state, { type: "processing", finalText: "我负责过账号运营" });
  assert.equal(state.status, "processing");
  assert.equal(state.finalText, "我负责过账号运营");

  state = voiceCallReducer(state, { type: "next_question" });
  assert.equal(state.status, "ai_speaking");
  assert.equal(state.interimText, "");
  assert.equal(state.finalText, "");
});

test("mute and unmute preserve an active call", () => {
  const connected = voiceCallReducer(initialVoiceCallState, { type: "listening" });
  const muted = voiceCallReducer(connected, { type: "mute" });
  assert.equal(muted.status, "muted");
  assert.equal(muted.muted, true);

  const unmuted = voiceCallReducer(muted, { type: "unmute" });
  assert.equal(unmuted.status, "listening");
  assert.equal(unmuted.muted, false);
});

test("voice transcripts are normalized and only valid turns auto-submit", () => {
  assert.equal(mergeVoiceTranscript("我负责过", " 账号运营。 "), "我负责过 账号运营。");
  assert.equal(mergeVoiceTranscript("", "  "), "");

  assert.equal(shouldAutoSubmitVoiceTurn({ active: true, muted: false, processing: false, text: "有内容" }), true);
  assert.equal(shouldAutoSubmitVoiceTurn({ active: true, muted: true, processing: false, text: "有内容" }), false);
  assert.equal(shouldAutoSubmitVoiceTurn({ active: true, muted: false, processing: true, text: "有内容" }), false);
  assert.equal(shouldAutoSubmitVoiceTurn({ active: false, muted: false, processing: false, text: "有内容" }), false);
  assert.equal(shouldAutoSubmitVoiceTurn({ active: true, muted: false, processing: false, text: "  " }), false);
});

test("prompt echo is ignored while a different user utterance can interrupt", () => {
  assert.equal(isLikelyPromptEcho("请介绍一下你的项目经历", "请介绍一下你的项目经历。"), true);
  assert.equal(isLikelyPromptEcho("介绍一下你的项目", "请介绍一下你的项目经历。"), true);
  assert.equal(isLikelyPromptEcho("我想先说明项目背景", "请介绍一下你的项目经历。"), false);
});

test("browsers without SpeechRecognition use the existing recorder and microphone path", () => {
  assert.equal(selectVoiceInputMode({ speechRecognition: true, mediaRecorder: true, microphone: true }), "recognition");
  assert.equal(selectVoiceInputMode({ speechRecognition: false, mediaRecorder: true, microphone: true }), "recorder");
  assert.equal(selectVoiceInputMode({ speechRecognition: false, mediaRecorder: false, microphone: true }), "unsupported");
});

test("cute speech style is lighter than the standard fallback", () => {
  assert.ok(speechStyleSettings.cute.pitch > speechStyleSettings.standard.pitch);
  assert.ok(speechStyleSettings.cute.rate > speechStyleSettings.standard.rate);
});

test("ending or failing a call clears live captions", () => {
  const listening = voiceCallReducer(initialVoiceCallState, { type: "user_speech", interimText: "测试" });
  const ended = voiceCallReducer(listening, { type: "end" });
  assert.equal(ended.status, "ended");
  assert.equal(ended.interimText, "");

  const failed = voiceCallReducer(listening, { type: "fail", error: "麦克风不可用" });
  assert.equal(failed.status, "error");
  assert.equal(failed.error, "麦克风不可用");
  assert.equal(failed.interimText, "");
});
