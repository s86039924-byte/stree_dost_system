// DOM helpers --------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const stageEls = {
  intro: $("stageIntro"),
  loading: $("stageLoading"),
  qa: $("stageQA"),
  popups: $("stagePopups"),
};

const logBox = $("logBox");
const popupConsole = $("popupConsole");
const popupOverlay = $("popupOverlay");
const popupQueue = [];
let popupActive = false;
let popupTimer = null;

const loadingTextEl = $("loadingText");
const introHintEl = $("introHint");
const hintBox = $("hintBox");
const popupSummary = $("popupSummary");

const hudPanel = $("hudPanel");
const hudToggle = $("hudToggle");
const btnCloseHud = $("btnCloseHud");

const btnStart = $("btnStart");
const btnAnswer = $("btnAnswer");
const btnReset = $("btnReset");
const btnRestart = $("btnRestart");

const answerInput = $("answerInput");
const questionStem = $("questionStem");
const questionOptions = $("questionOptions");
const questionCounter = $("questionCounter");
const questionSubject = $("questionSubject");
const questionProgress = $("questionProgress");
const mutateBadge = $("mutateBadge");
const integerPanel = $("integerPanel");
const integerInput = $("integerInput");
const btnClearInteger = $("btnClearInteger");
const btnBackspace = $("btnBackspace");
const scoreMeta = $("scoreMeta");
const testHint = $("testHint");
const btnPrevQuestion = $("btnPrevQuestion");
const btnNextQuestion = $("btnNextQuestion");
const btnReloadQuestions = $("btnReloadQuestions");
const btnSubmitQuestion = $("btnSubmitQuestion");

// State --------------------------------------------------------------------
let sessionId = null;
let currentDomain = null;
let currentSlot = null;
let socket = null;
let socketInitialized = false;
let testQuestions = [];
let testQuestionIndex = 0;
let selectedOptions = {};
let answeredMap = {};
let mutationTimers = [];
let integerKeypadListenerAttached = false;

// Utility ------------------------------------------------------------------
function log(...args) {
  if (!logBox) return;
  const line = args
    .map((a) => (typeof a === "string" ? a : JSON.stringify(a)))
    .join(" ");
  logBox.textContent = (logBox.textContent + line + "\n").slice(-15000);
  logBox.scrollTop = logBox.scrollHeight;
}

async function getJSON(url) {
  const res = await fetch(url, { method: "GET", headers: { "Content-Type": "application/json" } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || data.error || `HTTP ${res.status}`);
  return data;
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.message || `HTTP ${res.status}`);
  return data;
}

function showStage(name, message) {
  Object.values(stageEls).forEach((el) => el?.classList.remove("active"));
  const stage = stageEls[name];
  if (stage) stage.classList.add("active");
  if (name === "loading" && message) setLoadingMessage(message);
}

function setLoadingMessage(message) {
  if (loadingTextEl) loadingTextEl.textContent = message || "Calibrating vibes…";
}

function setHint(text) {
  if (hintBox) hintBox.textContent = text || "";
}

function setIntroHint(text) {
  if (!introHintEl) return;
  introHintEl.textContent = text || "";
  if (text) {
    stageEls.intro?.classList.add("shake");
    setTimeout(() => stageEls.intro?.classList.remove("shake"), 400);
  }
}

function setSessionUI(id, domains) {
  sessionId = id;
  window.currentSessionId = id || null;
  $("sessionId").textContent = id || "—";
  $("sessionStatus").textContent = id ? `session: ${id.slice(0, 8)}…` : "session: none";
  $("activeDomains").textContent = domains && domains.length ? domains.join(", ") : "—";
}

function updateScoreMeta() {
  const totalAnswered = Object.keys(answeredMap).length;
  const correct = Object.values(answeredMap).filter((v) => v?.correct).length;
  const totalQuestions = testQuestions.length || totalAnswered;
  if (scoreMeta) scoreMeta.textContent = `Score: ${correct}/${totalQuestions || 0}`;
}

function setQuestionUI(data) {
  currentDomain = data.domain || null;
  currentSlot = data.slot || null;

  $("qMeta").textContent = `domain: ${currentDomain || "—"} | slot: ${currentSlot || "—"}`;
  $("questionText").textContent = data.question || "Your next question will bloom here.";
  setHint(data.hint || "");
  btnAnswer.disabled = false;
  answerInput.disabled = false;
  answerInput.focus();
}

function resetFlow() {
  sessionId = null;
  currentDomain = null;
  currentSlot = null;
  btnAnswer.disabled = true;
  answerInput.value = "";
  $("initialText").value = "";
  setHint("");
  setIntroHint("");
  // Reset test question panel
  testQuestions = [];
  testQuestionIndex = 0;
  selectedOptions = {};
  answeredMap = {};
  if (questionStem) questionStem.textContent = "Questions will appear here with options.";
  if (questionOptions) questionOptions.innerHTML = "";
  if (questionCounter) questionCounter.textContent = "Questions —";
  if (questionSubject) questionSubject.textContent = "—";
  if (questionProgress) questionProgress.style.width = "0%";
  if (mutateBadge) mutateBadge.style.display = "none";
  if (integerPanel) integerPanel.style.display = "none";
  updateScoreMeta();
  setTestHint("");
  popupSummary.textContent = "We’re releasing your personalized pulses now. Watch the center top.";
  popupOverlay.innerHTML = "";
  log("reset_flow");
  setSessionUI(null, null);
  showStage("intro");
}

function clearMutationTimers() {
  mutationTimers.forEach((id) => clearTimeout(id));
  mutationTimers = [];
}

// Socket -------------------------------------------------------------------
function initSocket() {
  if (socketInitialized) return;
  socket = io({ transports: ["websocket"] });
  socketInitialized = true;

  socket.on("connect", () => {
    $("wsStatus").textContent = "WS: connected";
    log("WS connected", socket.id);
    logPopupEvent({ event: "connect", socket_id: socket.id });
  });

  socket.on("disconnect", () => {
    $("wsStatus").textContent = "WS: disconnected";
    log("WS disconnected");
    logPopupEvent({ event: "disconnect" });
  });

  socket.on("connect_error", (err) => {
    log("WS error", err.message || String(err));
    logPopupEvent({ event: "connect_error", error: err.message || String(err) });
  });

  socket.on("server_hello", (data) => log("server_hello", data));

  socket.on("joined", (data) => log("joined room", data));

  socket.on("popup", (payload) => {
    log("popup event", payload);
    logPopupEvent({ event: "popup", payload });
    enqueuePopup(payload);
  });

  socket.onAny((event, payload) => {
    if (event === "popup") return;
    logPopupEvent({ event, payload });
  });
}

function joinSessionRoom(targetId) {
  const id = targetId || sessionId;
  if (!id) return;
  if (!socketInitialized) initSocket();
  const payload = { session_id: id };
  const emitJoin = () => {
    socket.emit("join_session", payload);
    logPopupEvent({ event: "join_session", session_id: id });
  };

  if (socket.connected) emitJoin();
  else socket.once("connect", emitJoin);
}

// Popup rendering ----------------------------------------------------------
function logPopupEvent(obj) {
  if (!popupConsole) return;
  const row = document.createElement("div");
  row.className = "row";
  row.textContent = `[${new Date().toLocaleTimeString()}] ${JSON.stringify(obj)}`;
  popupConsole.prepend(row);
  if (popupConsole.children.length > 200) popupConsole.removeChild(popupConsole.lastChild);
}

function enqueuePopup(payload) {
  if (!payload) return;
  const message = String(payload.message || "");
  const parts = message
    .split("\n")
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length <= 1) {
    popupQueue.push(payload);
  } else {
    const ttl = payload.ttl || 4000;
    const perTtl = Math.max(2500, Math.floor(ttl / parts.length));
    parts.forEach((part) => {
      popupQueue.push({
        ...payload,
        message: part,
        ttl: perTtl,
      });
    });
  }
  processPopupQueue();
}

function processPopupQueue() {
  if (popupActive || popupQueue.length === 0) return;
  popupActive = true;
  const payload = popupQueue.shift();
  showPopupCard(payload, () => {
    popupActive = false;
    processPopupQueue();
  });
}

function showPopupCard(payload, done) {
  if (!popupOverlay) {
    done?.();
    return;
  }
  popupOverlay.innerHTML = "";
  const type = payload?.type || "pulse";
  const msg = payload?.message || "";

  const el = document.createElement("div");
  el.className = `popup ${escapeHTML(type)}`;
  el.innerHTML = `
    <div class="type">${escapeHTML(type)}</div>
    <div class="msg">${escapeHTML(msg)}</div>
  `;
  popupOverlay.prepend(el);

  clearTimeout(popupTimer);
  const duration = Math.min(Math.max(payload?.ttl || 3500, 2000), 7000);
  popupTimer = setTimeout(() => {
    el.remove();
    done?.();
  }, duration);
}

function escapeHTML(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// Acadza question panel ----------------------------------------------------
function setTestHint(text) {
  if (testHint) testHint.textContent = text || "";
}

function renderTestQuestion() {
  if (!questionStem || !questionOptions || !questionCounter) return;

  if (!testQuestions.length) {
    questionStem.textContent = "Questions will appear here with options.";
    questionOptions.innerHTML = "";
    questionCounter.textContent = "Questions —";
    if (questionSubject) questionSubject.textContent = "—";
    if (questionProgress) questionProgress.style.width = "0%";
    if (mutateBadge) mutateBadge.style.display = "none";
    if (btnPrevQuestion) btnPrevQuestion.disabled = true;
    if (btnNextQuestion) btnNextQuestion.disabled = true;
    return;
  }

  testQuestionIndex = Math.min(Math.max(testQuestionIndex, 0), testQuestions.length - 1);
  const q = testQuestions[testQuestionIndex];
  if (questionCounter) {
    questionCounter.textContent = `Question ${testQuestionIndex + 1} of ${testQuestions.length}`;
  }
  if (questionSubject) {
    const parts = [];
    if (q.subject) parts.push(q.subject);
    if (q.difficulty) parts.push(q.difficulty);
    questionSubject.textContent = parts.join(" · ") || "—";
  }
  if (questionProgress) {
    const pct = ((testQuestionIndex + 1) / testQuestions.length) * 100;
    questionProgress.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  }
  if (mutateBadge) {
    const mutated = Boolean(q.mutated || (q.meta && q.meta.mutated));
    mutateBadge.style.display = mutated ? "inline-flex" : "none";
  }
  const qType = (q.question_type || "").toLowerCase();
  if (qType === "integer") {
    if (questionOptions) questionOptions.style.display = "none";
    if (integerPanel) {
      integerPanel.style.display = "flex";
      const existing = selectedOptions[q.question_id] || "";
      if (integerInput) integerInput.value = existing;
      attachKeypadListeners();
    }
  } else {
    if (questionOptions) questionOptions.style.display = "grid";
    if (integerPanel) integerPanel.style.display = "none";
  }
  const parts = [];
  if (q.question_html) {
    parts.push(q.question_html);
  }
  if (Array.isArray(q.question_images)) {
    q.question_images.forEach((src) => {
      parts.push(`<div class="q-img"><img src="${src}" alt="question image" /></div>`);
    });
  }
  questionStem.innerHTML = parts.join("");
  questionOptions.innerHTML = "";

  const opts = q.options || [];
  if (qType !== "integer" && !opts.length) {
    const empty = document.createElement("div");
    empty.className = "option-empty";
    empty.textContent = "No options provided.";
    questionOptions.appendChild(empty);
  } else if (qType !== "integer") {
    opts.forEach((opt) => {
      const wrapper = document.createElement("label");
      wrapper.className = "option";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = `option-${q.question_id}`;
      input.value = opt.label;
      input.checked = selectedOptions[q.question_id] === opt.label;
      input.addEventListener("change", () => {
        selectedOptions[q.question_id] = opt.label;
      });

      const body = document.createElement("div");
      const labelEl = document.createElement("div");
      labelEl.className = "option-label";
      labelEl.textContent = opt.label || "";
      const textEl = document.createElement("div");
      textEl.className = "option-text";
      textEl.innerHTML = opt.text || "";
      body.appendChild(labelEl);
      body.appendChild(textEl);

      wrapper.appendChild(input);
      wrapper.appendChild(body);
      questionOptions.appendChild(wrapper);
    });
  }

  if (btnPrevQuestion) btnPrevQuestion.disabled = testQuestionIndex === 0;
  if (btnNextQuestion) btnNextQuestion.disabled = testQuestionIndex >= testQuestions.length - 1;
  updateScoreMeta();
}

async function loadTestQuestions() {
  if (!questionStem || !questionCounter) return;
  setTestHint("Loading questions…");
  questionCounter.textContent = "Loading questions…";
  if (questionSubject) questionSubject.textContent = "—";
  if (questionProgress) questionProgress.style.width = "0%";
  clearMutationTimers();
  questionStem.textContent = "Fetching questions from server...";
  questionOptions.innerHTML = "";
  try {
    const data = await getJSON("/api/questions/load-test-questions");
    testQuestions = data.questions || [];
    testQuestionIndex = 0;
    if (!testQuestions.length) {
      setTestHint("No questions returned. Add IDs to data/question_ids.csv.");
      questionCounter.textContent = "Questions unavailable";
      return;
    }
    selectedOptions = {};
    answeredMap = {};
    setTestHint("");
    scheduleMutationsForQuestions();
    renderTestQuestion();
  } catch (err) {
    setTestHint(err.message || "Failed to load questions.");
    questionCounter.textContent = "Questions unavailable";
    log("questions_load_error", err.message || String(err));
  }
}

function gotoQuestion(delta) {
  if (!testQuestions.length) return;
  testQuestionIndex = Math.min(
    Math.max(testQuestionIndex + delta, 0),
    testQuestions.length - 1
  );
  renderTestQuestion();
}

function shouldMutateQuestion(q) {
  if (!q) return false;
  const type = (q.question_type || "").toLowerCase();
  if (!["scq", "integer"].includes(type)) return false;
  // Mutate any question that has digits in stem or options
  const hasDigits =
    /\d/.test(q.question_html || "") ||
    (Array.isArray(q.options) && q.options.some((opt) => /\d/.test(opt?.text || "")));
  return hasDigits && !q.mutated && !(q.meta && q.meta.mutated);
}

function scheduleMutationsForQuestions() {
  clearMutationTimers();
  testQuestions.forEach((q, idx) => {
    if (!shouldMutateQuestion(q)) return;
    const timerId = setTimeout(() => mutateQuestionAt(idx), 5000);
    mutationTimers.push(timerId);
  });
}

async function mutateQuestionAt(index) {
  const q = testQuestions[index];
  if (!q || q.mutated || (q.meta && q.meta.mutated)) return;
  try {
    const res = await fetch(`/api/questions/mutate/${q.question_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.question) {
      const mutated = data.question;
      mutated.mutated = Boolean(data.mutated);
      testQuestions[index] = mutated;
      if (index === testQuestionIndex) {
        renderTestQuestion();
      }
    } else {
      log("mutate_failed", data.message || data.error || res.status);
    }
  } catch (err) {
    log("mutate_error", err.message || String(err));
  }
}

function submitCurrentQuestion() {
  if (!testQuestions.length) {
    setTestHint("Load questions first.");
    return;
  }
  const q = testQuestions[testQuestionIndex];
  const picked = selectedOptions[q.question_id];
  const qType = (q.question_type || "").toLowerCase();

  if (qType === "integer") {
    const value = (picked || "").trim();
    if (!value) {
      setTestHint("Enter an integer answer first.");
      return;
    }
    const correctVal = q.integer_answer;
    let correct = false;
    if (correctVal !== undefined && correctVal !== null) {
      const numPicked = Number(value);
      const numCorrect = Number(correctVal);
      if (!Number.isNaN(numPicked) && !Number.isNaN(numCorrect)) {
        correct = Math.abs(numPicked - numCorrect) < 1e-6;
      } else {
        correct = value === String(correctVal).trim();
      }
    }
    answeredMap[q.question_id] = { selected: value, correct };
  } else {
    if (!picked) {
      setTestHint("Select an option before submitting.");
      return;
    }
    const correctAnswer = q.correct_answer || q.correct_answers;
    let correct = false;
    if (Array.isArray(correctAnswer)) {
      const pickedSet = new Set(Array.isArray(picked) ? picked : [picked]);
      const correctSet = new Set(correctAnswer.map((v) => String(v).trim().toUpperCase()));
      correct = pickedSet.size === correctSet.size && [...pickedSet].every((v) => correctSet.has(String(v).trim().toUpperCase()));
    } else if (typeof correctAnswer === "string") {
      correct = picked.trim().toUpperCase() === correctAnswer.trim().toUpperCase();
    }
    answeredMap[q.question_id] = { selected: picked, correct };
  }
  updateScoreMeta();
  setTestHint(correct ? "Correct ✅" : "Saved. (Either incorrect or no answer key provided.)");
}

// Flow ---------------------------------------------------------------------
async function startSessionFlow() {
  try {
    const text = $("initialText").value.trim();
    if (!text) {
      setIntroHint("Please share a few thoughts first.");
      return;
    }
    setIntroHint("");
    btnStart.disabled = true;
    showStage("loading", "Absorbing your story…");

    const data = await postJSON("/session/start", { text });
    log("start_session", data);

    setSessionUI(data.session_id, data.active_domains);
    joinSessionRoom(data.session_id);

    await fetchNextQuestion("Finding the first question…");
  } catch (err) {
    log("start_error", err.message);
    setIntroHint(err.message);
    showStage("intro");
  } finally {
    btnStart.disabled = false;
  }
}

async function fetchNextQuestion(message) {
  if (!sessionId) return;
  showStage("loading", message || "Designing your next cue…");
  try {
    const data = await postJSON(`/session/${sessionId}/next-question`, {});
    log("next_question", data);

    if (data.pending) {
      setHint(data.message || "Answer the current question first.");
      showStage("qa");
      return;
    }

    if (data.done) {
      await handleCompletion();
      return;
    }

    setQuestionUI(data);
    showStage("qa");
  } catch (err) {
    log("next_question_error", err.message);
    setHint(err.message);
    showStage("qa");
  }
}

async function submitAnswer() {
  if (!sessionId || btnAnswer.disabled) return;
  const answer = answerInput.value.trim();
  if (!answer) {
    hintBox.textContent = "Type a quick sentence first.";
    answerInput.classList.add("shake");
    setTimeout(() => answerInput.classList.remove("shake"), 400);
    return;
  }

  try {
    btnAnswer.disabled = true;
    showStage("loading", "Reading your answer…");

    const payload = {
      answer,
      domain: currentDomain,
      slot: currentSlot,
    };
    const data = await postJSON(`/session/${sessionId}/answer`, payload);
    log("answer", data);

    if (data.need_clarification) {
      setHint("Quick clarifier requested: keep it tight.");
      $("questionText").textContent = data.question || "Need a tiny clarification.";
      btnAnswer.disabled = false;
      showStage("qa");
      return;
    }

    answerInput.value = "";
    setHint("Noted. Crafting the next cue…");
    await fetchNextQuestion("Crafting the next question…");
  } catch (err) {
    log("answer_error", err.message);
    setHint(err.message);
    btnAnswer.disabled = false;
    showStage("qa");
  }
}

async function handleCompletion() {
  showStage("loading", "Designing your focus pulses…");
  try {
    const data = await postJSON(`/session/${sessionId}/start-simulation`, {});
    log("start_simulation", data);
    popupSummary.textContent = `Popups scheduled: ${data.popups_scheduled}. Keep an eye on the center top.`;
  } catch (err) {
    log("simulation_error", err.message);
    popupSummary.textContent = err.message;
  }
  await loadTestQuestions();
  showStage("popups");
}

// HUD ----------------------------------------------------------------------
function toggleHud(open) {
  if (!hudPanel) return;
  const shouldOpen = typeof open === "boolean" ? open : !hudPanel.classList.contains("open");
  hudPanel.classList.toggle("open", shouldOpen);
}

hudToggle?.addEventListener("click", () => toggleHud());
btnCloseHud?.addEventListener("click", () => toggleHud(false));

// Events -------------------------------------------------------------------
btnStart?.addEventListener("click", startSessionFlow);
btnAnswer?.addEventListener("click", submitAnswer);
btnRestart?.addEventListener("click", resetFlow);
btnReset?.addEventListener("click", resetFlow);
btnPrevQuestion?.addEventListener("click", () => gotoQuestion(-1));
btnNextQuestion?.addEventListener("click", () => gotoQuestion(1));
btnReloadQuestions?.addEventListener("click", () => loadTestQuestions());
btnSubmitQuestion?.addEventListener("click", submitCurrentQuestion);

function attachKeypadListeners() {
  if (integerKeypadListenerAttached) return;
  integerKeypadListenerAttached = true;
  const keypad = $("keypad");
  if (keypad) {
    keypad.addEventListener("click", (evt) => {
      const key = evt.target?.dataset?.key;
      if (!key) return;
      const q = testQuestions[testQuestionIndex];
      if (!q || (q.question_type || "").toLowerCase() !== "integer") return;
      const current = selectedOptions[q.question_id] || "";
      const next = current + key;
      selectedOptions[q.question_id] = next;
      if (integerInput) integerInput.value = next;
    });
  }
  btnClearInteger?.addEventListener("click", () => {
    const q = testQuestions[testQuestionIndex];
    if (!q) return;
    selectedOptions[q.question_id] = "";
    if (integerInput) integerInput.value = "";
  });
  btnBackspace?.addEventListener("click", () => {
    const q = testQuestions[testQuestionIndex];
    if (!q) return;
    const current = selectedOptions[q.question_id] || "";
    const next = current.slice(0, -1);
    selectedOptions[q.question_id] = next;
    if (integerInput) integerInput.value = next;
  });
  integerInput?.addEventListener("input", (evt) => {
    const q = testQuestions[testQuestionIndex];
    if (!q) return;
    selectedOptions[q.question_id] = evt.target.value;
  });
}

answerInput?.addEventListener("keydown", (evt) => {
  if (evt.key === "Enter" && (evt.metaKey || evt.ctrlKey)) {
    submitAnswer();
  }
});

// Init ---------------------------------------------------------------------
resetFlow();
initSocket();

// expose for console debugging
window.__stressApp = {
  resetFlow,
  fetchNextQuestion,
  submitAnswer,
  loadTestQuestions,
  submitCurrentQuestion,
};
