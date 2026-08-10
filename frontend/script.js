/* ==========================================================================
   BMTC Assistant — Frontend logic (glassmorphism UI)
   Wires up: chat send (button + Enter), typing indicator, voice input,
   auto text-to-speech of replies, health status, textarea auto-resize.
   ========================================================================== */

const API_BASE = window.location.origin;
const CHAT_ENDPOINT = `${API_BASE}/chat`;
const HEALTH_ENDPOINT = `${API_BASE}/health`;

const chatBox = document.getElementById("chat-box");
const typingIndicator = document.getElementById("typing");
const questionInput = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");
const voiceBtn = document.getElementById("voice-btn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

// Tracks the most recent sendMessage() call, so a late/out-of-order response
// never speaks over (or instead of) the answer to a newer question.
let currentTurnId = 0;

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
async function checkHealth() {
  try {
    const res = await fetch(HEALTH_ENDPOINT);
    if (!res.ok) throw new Error("bad status");
    const data = await res.json();
    if (data.index_ready) {
      statusDot.style.background = "#22c55e";
      statusText.textContent = "Online";
    } else {
      statusDot.style.background = "#f59e0b";
      statusText.textContent = "Knowledge base empty";
    }
  } catch (e) {
    statusDot.style.background = "#ef4444";
    statusText.textContent = "Offline";
  }
}
checkHealth();

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function scrollToBottom() {
  chatBox.scrollTop = chatBox.scrollHeight;
}

function appendUserMessage(text) {
  const el = document.createElement("div");
  el.className = "user-message";
  el.textContent = text;
  chatBox.appendChild(el);
  scrollToBottom();
}

function formatAnswer(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML.replace(/\n/g, "<br>");
}

function appendBotMessage({ answer, confidence, sources, used_llm, isError, shouldSpeak = true }) {
  const el = document.createElement("div");
  el.className = "bot-message";

  const header = document.createElement("div");
  header.className = "message-header";
  header.innerHTML = `<i class="fa-solid fa-robot"></i> BMTC Assistant`;
  el.appendChild(header);

  const body = document.createElement("div");
  body.className = "message-body";
  body.innerHTML = formatAnswer(answer);
  el.appendChild(body);

  if (!isError && (sources?.length || typeof confidence === "number")) {
    const meta = document.createElement("div");
    meta.style.marginTop = "10px";
    meta.style.fontSize = "12px";
    meta.style.opacity = "0.65";
    const parts = [];
    if (sources?.length) parts.push(sources.join(" · "));
    if (typeof confidence === "number") parts.push(`confidence ${(confidence * 100).toFixed(0)}%`);
    if (used_llm === false) parts.push("fallback mode");
    meta.textContent = parts.join("  •  ");
    el.appendChild(meta);
  }

  chatBox.appendChild(el);
  scrollToBottom();

  if (!isError && shouldSpeak) {
    speak(answer);
  }
}

function setLoading(isLoading) {
  sendBtn.disabled = isLoading;
  questionInput.disabled = isLoading;
  typingIndicator.style.display = isLoading ? "flex" : "none";
  if (isLoading) scrollToBottom();
}

// ---------------------------------------------------------------------------
// Send message
// ---------------------------------------------------------------------------
async function sendMessage() {
  const question = questionInput.value.trim();
  if (!question) return;

  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  const thisTurnId = ++currentTurnId;

  appendUserMessage(question);
  questionInput.value = "";
  autoResizeTextarea();
  setLoading(true);

  try {
    const res = await fetch(CHAT_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `Request failed with status ${res.status}`);
    }

    const data = await res.json();
    appendBotMessage({
      answer: data.answer,
      confidence: data.confidence,
      sources: data.sources,
      used_llm: data.used_llm,
      shouldSpeak: thisTurnId === currentTurnId,
    });
  } catch (err) {
    console.error("Chat request failed:", err);
    appendBotMessage({
      answer: "I couldn't reach the BMTC Assistant service. Please try again in a moment.",
      isError: true,
    });
  } finally {
    setLoading(false);
    questionInput.focus();
  }
}

sendBtn.addEventListener("click", sendMessage);

// Enter sends; Shift+Enter inserts a newline (textarea, not a form)
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-grow the textarea as the person types, up to the CSS max-height (140px)
function autoResizeTextarea() {
  questionInput.style.height = "auto";
  questionInput.style.height = Math.min(questionInput.scrollHeight, 140) + "px";
}
questionInput.addEventListener("input", autoResizeTextarea);

// ---------------------------------------------------------------------------
// Voice input (Web Speech API)
// ---------------------------------------------------------------------------
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;
let isListening = false;

if (SpeechRecognition) {
  recognizer = new SpeechRecognition();
  recognizer.continuous = false;
  recognizer.interimResults = false;
  recognizer.lang = "en-IN";

  recognizer.onstart = () => {
    isListening = true;
    voiceBtn.classList.add("listening");
    voiceBtn.style.background = "#ef4444";
  };
  recognizer.onend = () => {
    isListening = false;
    voiceBtn.classList.remove("listening");
    voiceBtn.style.background = "";
  };
  recognizer.onerror = (e) => {
    console.warn("Speech recognition error:", e.error);
    isListening = false;
    voiceBtn.classList.remove("listening");
    voiceBtn.style.background = "";
  };
  recognizer.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    questionInput.value = transcript;
    autoResizeTextarea();
    questionInput.focus();
  };

  voiceBtn.addEventListener("click", () => {
    if (isListening) {
      recognizer.stop();
    } else {
      try {
        recognizer.start();
      } catch (e) {
        console.warn("Could not start recognizer:", e);
      }
    }
  });
} else {
  voiceBtn.disabled = true;
  voiceBtn.title = "Voice input not supported in this browser";
  voiceBtn.style.opacity = "0.4";
}

// ---------------------------------------------------------------------------
// Text-to-speech (auto-speaks every bot reply; picks a real Hindi voice if
// one is installed, otherwise falls back gracefully instead of failing silently)
// ---------------------------------------------------------------------------
let cachedVoices = [];

function loadVoices() {
  if ("speechSynthesis" in window) cachedVoices = window.speechSynthesis.getVoices();
}
loadVoices();
if ("speechSynthesis" in window) window.speechSynthesis.onvoiceschanged = loadVoices;

function findVoiceForLang(prefix) {
  return cachedVoices.find((v) => v.lang.toLowerCase().startsWith(prefix)) || null;
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();

  const isHindi = /[\u0900-\u097F]/.test(text);
  const utterance = new SpeechSynthesisUtterance(text);

  if (isHindi) {
    const hindiVoice = findVoiceForLang("hi");
    if (hindiVoice) {
      utterance.voice = hindiVoice;
      utterance.lang = hindiVoice.lang;
    } else {
      utterance.lang = "hi-IN"; // will fall back to a default voice if none installed
    }
  } else {
    utterance.lang = "en-IN";
    const enVoice = findVoiceForLang("en-in") || findVoiceForLang("en");
    if (enVoice) utterance.voice = enVoice;
  }

  utterance.rate = 1.0;
  window.speechSynthesis.speak(utterance);
}

// Focus input on load
window.addEventListener("load", () => questionInput.focus());
