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

// ---------------------------------------------------------------------------
// Mobile speech-synthesis unlock
// ---------------------------------------------------------------------------
// Mobile browsers (most strictly iOS Safari, but also some Android browsers)
// only allow speechSynthesis.speak() to actually produce audio if it's
// triggered synchronously within a direct user gesture (a real tap/click).
// Our real speak() calls happen after the /chat network request resolves,
// which is too late — by then the browser no longer considers it "from" a
// user gesture, so it silently does nothing on mobile (desktop browsers are
// more lenient about this, which is why it worked there).
//
// The fix: the first time the person actually taps/clicks anywhere on the
// page, fire one silent, near-empty utterance synchronously inside that
// gesture. This "unlocks" the speech engine for the rest of the page
// session, so later programmatic speak() calls (after a fetch resolves)
// are then allowed to produce audio.
let speechUnlocked = false;
function unlockSpeechSynthesisOnce() {
  if (speechUnlocked || !("speechSynthesis" in window)) return;
  speechUnlocked = true;
  try {
    const silent = new SpeechSynthesisUtterance(" ");
    silent.volume = 0;
    window.speechSynthesis.speak(silent);
  } catch (e) {
    console.warn("Could not unlock speech synthesis:", e);
  }
}
document.addEventListener("touchstart", unlockSpeechSynthesisOnce, { once: true, passive: true });
document.addEventListener("click", unlockSpeechSynthesisOnce, { once: true });

const SOURCE_COLORS = {
  "Main Website": "#0C7C74",
  "Center Portal": "#D98F2B",
  "Client Portal": "#7C9CF2",
};

// Tracks which sendMessage() call is the most recent one. Used so that if an
// older request's response arrives late (out of order), its speech never
// plays over/instead of the current answer.
let currentTurnId = 0;

// If the person switches "Voice reply" off, stop any speech that's
// currently playing right away rather than waiting for the next message.
ttsToggle.addEventListener("change", () => {
  if (!ttsToggle.checked) stopSpeaking();
});

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
  // Escape HTML special characters first (safety — never trust model output
  // as raw HTML), then render a small, safe subset of markdown that Gemini
  // commonly uses in answers: **bold**, "* " bullet lists, and "1. " numbered
  // lists. This avoids showing literal asterisks/numbers-with-dots to the
  // person while still keeping the structure of the answer readable.
  const escapeDiv = document.createElement("div");
  escapeDiv.textContent = text;
  const escaped = escapeDiv.innerHTML;

  const lines = escaped.split("\n");
  let html = "";
  let inUl = false;
  let inOl = false;

  const closeLists = () => {
    if (inUl) { html += "</ul>"; inUl = false; }
    if (inOl) { html += "</ol>"; inOl = false; }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    const withBold = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    if (/^\*\s+/.test(line)) {
      // Bullet list item ("* text") — strip the marker, render as <li>
      if (!inUl) { closeLists(); html += "<ul>"; inUl = true; }
      html += `<li>${withBold.replace(/^\*\s+/, "")}</li>`;
    } else if (/^\d+\.\s+/.test(line)) {
      // Numbered list item ("1. text") — strip the marker, render as <li>
      if (!inOl) { closeLists(); html += "<ol>"; inOl = true; }
      html += `<li>${withBold.replace(/^\d+\.\s+/, "")}</li>`;
    } else if (line === "") {
      closeLists();
      html += "<br>";
    } else {
      closeLists();
      html += withBold + "<br>";
    }
  }
  closeLists();
  return html;
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
  stopSpeaking();
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
// Voice input (Web Speech API) — unchanged from before
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
// Text-to-speech (browser-native Web Speech API — client-side, no backend
// changes). Fixes the Hindi voice-selection issue by:
//   1. Loading speechSynthesis.getVoices() AND listening for the async
//      'voiceschanged' event, since voice lists often populate late.
//   2. Explicitly detecting Hindi replies via the Devanagari Unicode range
//      (U+0900–U+097F) rather than trusting the browser to guess.
//   3. Actively searching the loaded voice list for a Hindi (hi / hi-IN)
//      voice and assigning it directly via utterance.voice — setting only
//      utterance.lang is not enough; browsers silently fall back to a
//      default (usually English) voice if no matching voice is assigned.
//   4. Preferring a LOCAL/offline Hindi voice over a remote network voice
//      when both are available, since remote voices (e.g. Chrome's
//      "Google हिन्दी") can silently fail to produce audio depending on
//      network conditions even though the browser lists them as available.
//   5. Falling back gracefully (with a one-time in-chat notice) if no
//      Hindi voice is installed at all, instead of failing silently.
// ---------------------------------------------------------------------------
let cachedVoices = [];
let hindiVoiceWarningShown = false;
let currentUtterance = null;

function loadVoices() {
  if ("speechSynthesis" in window) {
    cachedVoices = window.speechSynthesis.getVoices();
  }
}
// Voices often load asynchronously — populate now, and again once the
// browser fires 'voiceschanged' (Chrome/Edge commonly need this event).
loadVoices();
if ("speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = loadVoices;
}

function findVoiceForLang(langPrefix) {
  const matches = cachedVoices.filter((v) => v.lang.toLowerCase().startsWith(langPrefix));
  if (matches.length === 0) return null;
  // Prefer a local/offline voice over a remote (network) one — remote
  // voices depend on reaching an external TTS server and can silently
  // produce no audio if that's blocked or unreliable on this network.
  const localMatch = matches.find((v) => v.localService === true);
  return localMatch || matches[0];
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  stopSpeaking(); // stop any ongoing speech before starting new speech

  const isHindi = /[\u0900-\u097F]/.test(text);
  const utterance = new SpeechSynthesisUtterance(text);

  if (isHindi) {
    // Try hi-IN first (most specific), then fall back to any 'hi*' voice.
    const hindiVoice = findVoiceForLang("hi-in") || findVoiceForLang("hi");
    if (hindiVoice) {
      utterance.voice = hindiVoice;
      utterance.lang = hindiVoice.lang;
    } else {
      // No Hindi voice installed on this system/browser. Setting the lang
      // tag alone will NOT make it speak Hindi — most browsers silently
      // substitute a default (usually English) voice instead. Let the
      // person know once, rather than failing silently and looking broken.
      utterance.lang = "hi-IN";
      if (!hindiVoiceWarningShown) {
        hindiVoiceWarningShown = true;
        appendBotMessage({
          answer:
            "Note: this browser/OS doesn't have a Hindi voice installed, so voice " +
            "reply may sound off or default to English for Hindi answers. On Windows: " +
            "Settings → Time & Language → Speech → Add a voice → Hindi. " +
            "In Chrome/Edge, a Hindi voice ('Google हिन्दी' or a Microsoft Hindi voice) " +
            "should then appear automatically — no restart of this page needed, though " +
            "restarting the browser helps it register the new voice.",
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
  utterance.onend = () => { muteBtn.hidden = true; currentUtterance = null; };
  utterance.onerror = () => { muteBtn.hidden = true; currentUtterance = null; };

  currentUtterance = utterance;
  window.speechSynthesis.speak(utterance);
}

// Shared stop helper — used by the mute button, the "Voice reply" toggle
// being switched off, and whenever a new message is sent.
function stopSpeaking() {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  currentUtterance = null;
  muteBtn.hidden = true;
}

// Dedicated mute button: instantly stops whatever is currently being read
// aloud, without affecting the "Voice reply" toggle for future messages.
muteBtn.addEventListener("click", stopSpeaking);

// Focus input on load for fast typing
window.addEventListener("load", () => messageInput.focus());
