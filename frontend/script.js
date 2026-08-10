/* ==========================================================================
   BMTC Assistant — Frontend logic
   Handles: sending questions to /chat, rendering bubbles, loading state,
   voice input (Web Speech API), text-to-speech, health check, and the
   ticket "REF" code / status dot.
   ========================================================================== */

const API_BASE = window.location.origin; // same-origin backend
const CHAT_ENDPOINT = `${API_BASE}/chat`;
const HEALTH_ENDPOINT = `${API_BASE}/health`;

const chatLog = document.getElementById("chatLog");
const composerForm = document.getElementById("composerForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");
const muteBtn = document.getElementById("muteBtn");
const typingIndicator = document.getElementById("typingIndicator");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const sessionRef = document.getElementById("sessionRef");
const ttsToggle = document.getElementById("ttsToggle");

// If the person switches "Voice reply" off, stop any speech that's
// currently playing right away rather than waiting for the next message.
ttsToggle.addEventListener("change", () => {
  if (!ttsToggle.checked && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
    muteBtn.hidden = true;
  }
});

const SOURCE_COLORS = {
  "Main Website": "#0C7C74",
  "Center Portal": "#D98F2B",
  "Client Portal": "#7C9CF2",
};

// Tracks which sendMessage() call is the most recent one. Used so that if an
// older request's response arrives late (out of order), its speech never
// plays over/instead of the current answer.
let currentTurnId = 0;

// ---------------------------------------------------------------------------
// Session ref (cosmetic, mirrors an admit-card reference number)
// ---------------------------------------------------------------------------
function generateRef() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let ref = "";
  for (let i = 0; i < 8; i++) ref += chars[Math.floor(Math.random() * chars.length)];
  return ref;
}
sessionRef.textContent = generateRef();

// ---------------------------------------------------------------------------
// Health check -> updates the status dot / subtitle
// ---------------------------------------------------------------------------
async function checkHealth() {
  try {
    const res = await fetch(HEALTH_ENDPOINT);
    if (!res.ok) throw new Error("bad status");
    const data = await res.json();
    if (data.index_ready) {
      statusDot.classList.remove("offline");
      statusDot.classList.add("online");
      statusText.textContent = `Knowledge base ready · ${data.total_vectors} indexed passages`;
    } else {
      statusDot.classList.remove("online");
      statusDot.classList.add("offline");
      statusText.textContent = "Knowledge base is empty — run the ingestion pipeline";
    }
  } catch (e) {
    statusDot.classList.remove("online");
    statusDot.classList.add("offline");
    statusText.textContent = "Unable to reach BMTC Assistant backend";
  }
}
checkHealth();

// ---------------------------------------------------------------------------
// Rendering helpers
// ---------------------------------------------------------------------------
function scrollToBottom() {
  chatLog.scrollTop = chatLog.scrollHeight;
}

function appendUserMessage(text) {
  const msg = document.createElement("div");
  msg.className = "msg msg--user";
  msg.innerHTML = `<div class="msg__bubble"></div>`;
  msg.querySelector(".msg__bubble").textContent = text;
  chatLog.appendChild(msg);
  scrollToBottom();
}

function confidenceBadgeClass(score) {
  if (score >= 0.6) return "high";
  if (score >= 0.35) return "med";
  return "low";
}

function appendBotMessage({ answer, confidence, sources, used_llm, isError, shouldSpeak = true }) {
  const msg = document.createElement("div");
  msg.className = "msg msg--bot" + (isError ? " msg--error" : "");

  const bubble = document.createElement("div");
  bubble.className = "msg__bubble";
  bubble.innerHTML = escapeAndLinkify(answer);
  msg.appendChild(bubble);

  const meta = document.createElement("div");
  meta.className = "msg__meta";

  if (!isError) {
    (sources || []).forEach((label) => {
      const stamp = document.createElement("span");
      stamp.className = "sourceStamp";
      const dot = document.createElement("span");
      dot.className = "sourceStamp__dot";
      dot.style.background = SOURCE_COLORS[label] || "#5B677A";
      stamp.appendChild(dot);
      stamp.appendChild(document.createTextNode(label));
      meta.appendChild(stamp);
    });

    if (typeof confidence === "number") {
      const badge = document.createElement("span");
      badge.className = `confBadge ${confidenceBadgeClass(confidence)}`;
      badge.textContent = `confidence ${(confidence * 100).toFixed(0)}%`;
      meta.appendChild(badge);
    }

    if (used_llm === false) {
      const badge = document.createElement("span");
      badge.className = "confBadge med";
      badge.textContent = "fallback mode";
      meta.appendChild(badge);
    }
  }

  msg.appendChild(meta);
  chatLog.appendChild(msg);
  scrollToBottom();

  if (ttsToggle.checked && !isError && shouldSpeak) {
    speak(answer);
  }
}

function escapeAndLinkify(text) {
  const div = document.createElement("div");
  div.textContent = text;
  let escaped = div.innerHTML;
  escaped = escaped.replace(/\n/g, "<br>");
  return escaped;
}

function setLoading(isLoading) {
  sendBtn.disabled = isLoading;
  messageInput.disabled = isLoading;
  typingIndicator.hidden = !isLoading;
  if (isLoading) scrollToBottom();
}

// ---------------------------------------------------------------------------
// Send message to backend
// ---------------------------------------------------------------------------
async function sendMessage(question) {
  question = question.trim();
  if (!question) return;

  // Stop any speech from a previous answer the instant a new question is
  // sent, and mark this as the new "latest" turn so a late-arriving older
  // response can never speak over / instead of the current one.
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
    muteBtn.hidden = true;
  }
  const thisTurnId = ++currentTurnId;

  appendUserMessage(question);
  messageInput.value = "";
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
      shouldSpeak: thisTurnId === currentTurnId, // only speak if still the latest turn
    });
  } catch (err) {
    console.error("Chat request failed:", err);
    appendBotMessage({
      answer: "I couldn't reach the BMTC Assistant service. Please check your connection and try again in a moment.",
      isError: true,
    });
  } finally {
    setLoading(false);
    messageInput.focus();
  }
}

composerForm.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(messageInput.value);
});

// Enter key support (native via form submit); Shift+Enter not needed for single-line input.

// Quick-ask buttons in the brand rail
document.querySelectorAll(".quickAsk__btn").forEach((btn) => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.q));
});

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
  recognizer.lang = "en-IN"; // supports Hindi speech reasonably well too; user can still type Hindi directly

  recognizer.onstart = () => {
    isListening = true;
    micBtn.classList.add("listening");
  };
  recognizer.onend = () => {
    isListening = false;
    micBtn.classList.remove("listening");
  };
  recognizer.onerror = (e) => {
    console.warn("Speech recognition error:", e.error);
    isListening = false;
    micBtn.classList.remove("listening");
  };
  recognizer.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    messageInput.value = transcript;
    messageInput.focus();
  };

  micBtn.addEventListener("click", () => {
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
  micBtn.disabled = true;
  micBtn.title = "Voice input not supported in this browser";
  micBtn.style.opacity = "0.4";
}

// ---------------------------------------------------------------------------
// Text-to-speech
// ---------------------------------------------------------------------------
let cachedVoices = [];
let hindiVoiceWarningShown = false;

function loadVoices() {
  if ("speechSynthesis" in window) {
    cachedVoices = window.speechSynthesis.getVoices();
  }
}
// Voices often load asynchronously — populate now and again when ready.
loadVoices();
if ("speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = loadVoices;
}

function findVoiceForLang(langPrefix) {
  return cachedVoices.find((v) => v.lang.toLowerCase().startsWith(langPrefix)) || null;
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel(); // stop any ongoing speech

  const isHindi = /[\u0900-\u097F]/.test(text);
  const utterance = new SpeechSynthesisUtterance(text);

  if (isHindi) {
    const hindiVoice = findVoiceForLang("hi");
    if (hindiVoice) {
      utterance.voice = hindiVoice;
      utterance.lang = hindiVoice.lang;
    } else {
      // No Hindi voice installed on this system/browser — setting the lang
      // tag alone won't make it speak Hindi; most browsers silently
      // substitute a default (usually English) voice instead. Let the user
      // know once, rather than failing silently and looking broken.
      utterance.lang = "hi-IN";
      if (!hindiVoiceWarningShown) {
        hindiVoiceWarningShown = true;
        appendBotMessage({
          answer:
            "Note: your browser/OS doesn't have a Hindi voice installed, so voice " +
            "reply may sound off or default to English for Hindi answers. On Windows, " +
            "you can add one via Settings → Time & Language → Speech → Add a voice → Hindi.",
          isError: false,
          sources: [],
          confidence: null,
        });
      }
    }
  } else {
    utterance.lang = "en-IN";
    const enVoice = findVoiceForLang("en-in") || findVoiceForLang("en");
    if (enVoice) utterance.voice = enVoice;
  }

  utterance.rate = 1.0;

  utterance.onstart = () => { muteBtn.hidden = false; };
  utterance.onend = () => { muteBtn.hidden = true; };
  utterance.onerror = () => { muteBtn.hidden = true; };

  window.speechSynthesis.speak(utterance);
}

// Dedicated mute button: instantly stops whatever is currently being read
// aloud, without affecting the "Voice reply" toggle for future messages.
muteBtn.addEventListener("click", () => {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  muteBtn.hidden = true;
});

// Focus input on load for fast typing
window.addEventListener("load", () => messageInput.focus());
