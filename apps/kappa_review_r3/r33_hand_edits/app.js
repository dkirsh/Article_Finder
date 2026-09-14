"use strict";

const state = {
  data: null,
  reviewer: null,
  responses: {},
  drafts: {},
  profile: "David",
  persistenceBlocked: false,
  marks: {},
  paperStates: {},
  itemSessions: {},
  missedFindings: {},
  queue: [],
  currentIndex: 0,
  zoom: 1,
  activePaperId: null,
  activeItemId: null,
  activePageRef: null,
  pageEnteredAt: null,
  activeEvidenceMode: "image",
  evidenceModeEnteredAt: null,
  lastSavedAt: null,
  restoreError: false,
  saveError: false,
};

const byId = (id) => document.getElementById(id);
const legacyStorageKey = () =>
  `ae-hitl:${state.data.app_schema_version}:${state.data.study_id}:${state.data.pack_sha256}`;
const storageKey = () => {
  const session = new URLSearchParams(window.location.search).get("session");
  return `${legacyStorageKey()}:reviewer:${state.profile}${session ? `:session:${session}` : ""}`;
};
function profileFor(value) {
  const alias = String(value || "").trim().toLowerCase().replace(/\s+/g, "");
  if (["david", "davidkirsh"].includes(alias)) return "David";
  if (alias === "stephan") return "Stephan";
  return null;
}
function gateOpen() {
  return Boolean(state.data) && (!state.data.adjudication_gate || state.data.adjudication_gate.status === "open");
}
function openReviewerSettings(message = "") {
  captureDraft();
  capturePaperViewport();
  pauseTiming();
  byId("reviewScreen").classList.add("hidden");
  byId("completeScreen").classList.add("hidden");
  byId("startScreen").classList.remove("hidden");
  if (byId("fieldNavigator")) byId("fieldNavigator").open = false;
  byId("returnToPaperButton").disabled = !gateOpen();
  if (message) {
    byId("resumeNotice").textContent = message;
    byId("resumeNotice").classList.remove("hidden");
  }
  byId("independence").focus({preventScroll: true});
  syncSettingsButton();
}
function returnToPaper() {
  if (!gateOpen()) {
    openReviewerSettings("Adjudication is locked. The paper review cannot be opened until the gate is open.");
    return;
  }
  byId("startScreen").classList.add("hidden");
  byId("completeScreen").classList.add("hidden");
  byId("reviewScreen").classList.remove("hidden");
  syncSettingsButton();
  renderItem({focus: true});
}
function renderReviewerIdentity() {
  if (byId("reviewerSwitch")) byId("reviewerSwitch").value = state.profile;
  if (byId("reviewerStatus")) byId("reviewerStatus").textContent =
    `${state.reviewer?.reviewer_id || state.profile} · ${state.reviewer?.independent_of_candidate_author === true ? "independence confirmed" : "independence not yet confirmed"}`;
}
function ratingPermissionError() {
  if (!gateOpen()) return "Adjudication is locked. Ratings cannot be saved until the gate is open.";
  if (!state.reviewer || profileFor(state.reviewer.reviewer_id) !== state.profile)
    return "Confirm the reviewer identity in settings before saving a rating.";
  if (state.reviewer.independent_of_candidate_author !== true)
    return "Confirm your independence in reviewer settings before saving a rating.";
  if (state.persistenceBlocked) return "Saved profile data could not be restored. Start a separate session before rating; the existing data is preserved.";
  return null;
}
function captureDraft() {
  if (!state.activeItemId || !byId("decisionForm")) return;
  state.drafts[state.activeItemId] = {
    verdict: document.querySelector('input[name="verdict"]:checked')?.value || "",
    corrected_value: byId("correctedValue").value,
    rationale: byId("rationale").value,
    error_class: byId("errorClass").value,
    confidence: byId("confidence").value,
    context_sufficient: !byId("needsMoreContext").checked,
    context_request: byId("contextRequest").value,
  };
}
function navigateToItem(itemId) {
  if (!gateOpen()) return;
  const index = state.queue.indexOf(itemId);
  if (index < 0) return;
  captureDraft();
  state.currentIndex = index;
  byId("startScreen").classList.add("hidden");
  byId("completeScreen").classList.add("hidden");
  byId("reviewScreen").classList.remove("hidden");
  syncSettingsButton();
  renderItem({focus: true});
}
function switchProfile(value, freshSession = false) {
  const profile = profileFor(value);
  if (!profile) return;
  captureDraft();
  capturePaperViewport();
  pauseTiming();
  saveLocal();
  const url = new URL(window.location.href);
  url.searchParams.set("reviewer", profile);
  if (freshSession) url.searchParams.set("session", String(Date.now()));
  else url.searchParams.delete("session");
  window.location.assign(url.toString());
}
const normalized = (value) => (value || "").trim().toLocaleLowerCase().replace(/\s+/g, " ");

function timingEligible() {
  return window.innerWidth >= 700 &&
    document.visibilityState === "visible" &&
    document.hasFocus() &&
    byId("startScreen")?.classList.contains("hidden") === true &&
    !byId("reviewScreen")?.classList.contains("hidden");
}

function hasReviewerScopedState() {
  return Boolean(
    Object.keys(state.responses).length ||
    Object.keys(state.marks).length ||
    Object.keys(state.paperStates).length ||
    Object.keys(state.itemSessions).length ||
    Object.keys(state.missedFindings).length
  );
}

function itemById(itemId) {
  return state.data.items.find((item) => item.item_id === itemId);
}

function currentItem() {
  return itemById(state.queue[state.currentIndex]);
}

function paperFor(paperId) {
  return state.data.papers[paperId];
}

function buildQueue() {
  const result = AEHITLQueueLogic.efficientQueue(state.data, state.responses);
  state.queue = result.queue;
  state.stopState = result.stopState;
  state.skippedCount = (result.skipped || []).length;
}

function flushPageDwell(continueTiming = timingEligible()) {
  if (!state.activePaperId || !state.activeItemId || !state.activePageRef || state.pageEnteredAt === null) return;
  const paperState = state.paperStates[state.activePaperId];
  const session = itemSession(state.activeItemId);
  const elapsed = Math.max(0, performance.now() - state.pageEnteredAt);
  paperState.dwell_ms_by_page[state.activePageRef] =
    (paperState.dwell_ms_by_page[state.activePageRef] || 0) + elapsed;
  session.dwell_ms_by_page[state.activePageRef] =
    (session.dwell_ms_by_page[state.activePageRef] || 0) + elapsed;
  state.pageEnteredAt = continueTiming ? performance.now() : null;
}

function flushModeDwell(continueTiming = timingEligible()) {
  if (!state.activeItemId || state.evidenceModeEnteredAt === null) return;
  const session = itemSession(state.activeItemId);
  const elapsed = Math.max(0, performance.now() - state.evidenceModeEnteredAt);
  session.dwell_ms_by_mode[state.activeEvidenceMode] =
    (session.dwell_ms_by_mode[state.activeEvidenceMode] || 0) + elapsed;
  state.evidenceModeEnteredAt = continueTiming ? performance.now() : null;
}

function pauseTiming() {
  flushModeDwell(false);
  flushPageDwell(false);
  saveLocal();
}

function resumeTiming() {
  if (!timingEligible() || !state.activeItemId) return;
  const now = performance.now();
  if (state.pageEnteredAt === null) state.pageEnteredAt = now;
  if (state.evidenceModeEnteredAt === null) state.evidenceModeEnteredAt = now;
}

function saveLocal() {
  if (!state.data || !state.reviewer || state.persistenceBlocked) return;
  const savedAt = new Date().toISOString();
  try {
    localStorage.setItem(storageKey(), JSON.stringify({
      reviewer: state.reviewer,
      responses: state.responses,
      drafts: state.drafts,
      marks: state.marks,
      paperStates: state.paperStates,
      itemSessions: state.itemSessions,
      missedFindings: state.missedFindings,
      currentIndex: state.currentIndex,
      savedAt,
    }));
    state.lastSavedAt = savedAt;
    state.saveError = false;
  } catch (_error) {
    state.saveError = true;
  }
  renderSaveStatus();
}

function restoreLocal() {
  let saved;
  let scoped = false;
  try {
    const raw = localStorage.getItem(storageKey());
    scoped = raw !== null;
    const legacy = !scoped && !new URLSearchParams(window.location.search).has("session")
      ? localStorage.getItem(legacyStorageKey()) : null;
    saved = JSON.parse(raw || legacy || "null");
    if (!saved) return;
    if (profileFor(saved.reviewer?.reviewer_id) !== state.profile) {
      if (scoped) throw new Error("profile_identity_mismatch");
      return; // A legacy review is only copied to its matching profile; never relabelled.
    }
  } catch (_error) {
    state.restoreError = true;
    state.persistenceBlocked = scoped;
    return;
  }
  state.reviewer = saved.reviewer;
  state.responses = saved.responses || {};
  state.drafts = saved.drafts || {};
  state.marks = saved.marks || {};
  state.paperStates = saved.paperStates || {};
  state.itemSessions = saved.itemSessions || {};
  state.missedFindings = saved.missedFindings || {};
  state.currentIndex = Number.isInteger(saved.currentIndex) ? Math.max(0, saved.currentIndex) : 0;
  state.lastSavedAt = saved.savedAt || null;
}

function renderSaveStatus() {
  const button = byId("backupButton");
  if (!state.reviewer) {
    byId("saveStatus").textContent = state.restoreError
      ? "Saved browser data could not be read"
      : "Autosave starts when the review begins";
    button.disabled = true;
    return;
  }
  if (state.saveError || state.persistenceBlocked) {
    byId("saveStatus").textContent = "Browser autosave failed; download a backup now";
    button.disabled = false;
    return;
  }
  const answered = Object.keys(state.responses).length;
  const time = state.lastSavedAt
    ? new Date(state.lastSavedAt).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})
    : "not yet";
  byId("saveStatus").textContent = `${answered} answers saved locally at ${time}`;
  button.disabled = false;
}

function itemSession(itemId) {
  if (!state.itemSessions[itemId]) {
    state.itemSessions[itemId] = {
      viewed_page_refs: [],
      dwell_ms_by_page: {},
      visit_count_by_page: {},
      viewed_modes: [],
      dwell_ms_by_mode: {},
      mode_visit_count: {},
    };
  }
  return state.itemSessions[itemId];
}

function paperState(paperId, item) {
  if (!state.paperStates[paperId]) {
    // Every paper opens at page 1 (DK ruling 2026-09-14); the machine's
    // suggested evidence pages remain available as chips, never as the start.
    state.paperStates[paperId] = {
      active_page_ref: 1,
      active_mode: "image",
      viewed_page_refs: [],
      dwell_ms_by_page: {},
      visit_count_by_page: {},
      page_view_state: {},
    };
  }
  const value = state.paperStates[paperId];
  value.active_mode = value.active_mode || "image";
  value.page_view_state = value.page_view_state || {};
  return value;
}

function renderProgress() {
  const answered = state.queue.filter((id) => state.responses[id]).length;
  byId("progressLabel").textContent = state.reviewer
    ? `${answered} of ${state.queue.length} questions in the current queue`
    : "Not started";
  byId("progressBar").max = Math.max(1, state.queue.length);
  byId("progressBar").value = answered;
  renderStrataStatus();
  renderStartProgress();
}

function renderStartProgress() {
  const host = byId("startProgress");
  if (!host) return;
  const answered = state.queue.filter((id) => state.responses[id]).length;
  host.textContent = answered
    ? `${answered} of ${state.queue.length} questions answered so far. Entering the review returns you to your next unanswered question, on the page where you left off.`
    : `0 of ${state.queue.length} questions answered so far. Entering the review begins at the first question.`;
  host.classList.remove("hidden");
}

function syncSettingsButton() {
  const button = byId("reviewerSettingsButton");
  if (button) button.disabled = !byId("startScreen").classList.contains("hidden");
}

function renderStrataStatus() {
  // Progress counts only — never verdicts. Showing a field's fate mid-review
  // would anchor the reviewer's remaining judgments (review amendment A1).
  const host = byId("strataStatus");
  if (!host || !state.stopState) { if (host) host.replaceChildren(); return; }
  host.replaceChildren(...Object.entries(state.stopState)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([stratum, s]) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "stratum-chip";
      const done = s.n + s.undecided;
      chip.title = `${done} of ${s.total_items} answered so far in this field`;
      chip.textContent = `${stratum.replaceAll("_", " ")} ${done}/${s.total_items}`;
      const eligible = state.queue.filter((id) => itemById(id)?.stratum === stratum);
      const target = eligible.find((id) => !state.responses[id]) || eligible[0];
      chip.disabled = !target;
      if (currentItem()?.stratum === stratum) chip.setAttribute("aria-current", "true");
      chip.addEventListener("click", () => {
        if (!target) return;
        if (byId("fieldNavigator")) byId("fieldNavigator").open = false;
        navigateToItem(target);
      });
      return chip;
    }));
}

function activateTabUi(tab) {
  const image = tab === "image";
  byId("imageView").classList.toggle("hidden", !image);
  byId("textView").classList.toggle("hidden", image);
  byId("imageTab").classList.toggle("active", image);
  byId("textTab").classList.toggle("active", !image);
}

function pageViewState(paperId, pageRef) {
  const item = itemById(state.activeItemId) || currentItem();
  const pState = paperState(paperId, item);
  const key = String(pageRef);
  pState.page_view_state[key] = pState.page_view_state[key] || {
    zoom: 1,
    image_scroll_top: 0,
    image_scroll_left: 0,
    text_scroll_top: 0,
  };
  return pState.page_view_state[key];
}

function capturePaperViewport() {
  if (!state.activePaperId || !state.activePageRef) return;
  const view = pageViewState(state.activePaperId, state.activePageRef);
  view.zoom = state.zoom;
  view.image_scroll_top = byId("imageCanvas").scrollTop;
  view.image_scroll_left = byId("imageCanvas").scrollLeft;
  view.text_scroll_top = byId("pageText").scrollTop;
}

function restorePaperViewport(paperId, pageRef) {
  const view = pageViewState(paperId, pageRef);
  state.zoom = view.zoom;
  applyZoom();
  requestAnimationFrame(() => {
    byId("imageCanvas").scrollTop = view.image_scroll_top;
    byId("imageCanvas").scrollLeft = view.image_scroll_left;
    byId("pageText").scrollTop = view.text_scroll_top;
  });
}

function setTab(tab) {
  capturePaperViewport();
  flushModeDwell();
  activateTabUi(tab);
  state.activeEvidenceMode = tab;
  state.evidenceModeEnteredAt = timingEligible() ? performance.now() : null;
  if (state.activeItemId) {
    paperState(state.activePaperId, currentItem()).active_mode = tab;
    const session = itemSession(state.activeItemId);
    if (!session.viewed_modes.includes(tab)) session.viewed_modes.push(tab);
    session.mode_visit_count[tab] = (session.mode_visit_count[tab] || 0) + 1;
    restorePaperViewport(state.activePaperId, state.activePageRef);
    saveLocal();
  }
}

function prettyLabel(key) {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "Not reported";
  if (Array.isArray(value)) return value.map(displayValue).join("; ");
  if (typeof value === "object") {
    return Object.entries(value).map(([key, nested]) => `${prettyLabel(key)}: ${displayValue(nested)}`).join("; ");
  }
  return String(value);
}

function renderCandidate(candidate) {
  const omitted = new Set(["result_id", "study_id", "page_refs", "source_locator", "source_quote", "design_evidence_locator", "design_evidence_quote"]);
  const entries = candidate && typeof candidate === "object" && !Array.isArray(candidate)
    ? Object.entries(candidate).filter(([key]) => !omitted.has(key))
    : [["value", candidate]];
  byId("candidateValue").replaceChildren(...entries.map(([key, value]) => {
    const row = document.createElement("dl");
    row.className = "candidate-row";
    const term = document.createElement("dt");
    term.textContent = prettyLabel(key);
    const definition = document.createElement("dd");
    definition.textContent = displayValue(value);
    row.append(term, definition);
    return row;
  }));
}

function missedFindingsFor(paperId) {
  state.missedFindings[paperId] = state.missedFindings[paperId] || [];
  return state.missedFindings[paperId];
}

function renderMissedFindings(item) {
  const rows = missedFindingsFor(item.paper_id);
  byId("missedFindingList").replaceChildren(...rows.map((row, index) => {
    const card = document.createElement("article");
    card.className = "missed-finding-item";
    const heading = document.createElement("strong");
    heading.textContent = row.field_name;
    const value = document.createElement("p");
    value.textContent = row.proposed_value;
    const pages = document.createElement("small");
    pages.textContent = `Evidence pages: ${row.page_refs.join(", ")}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      state.missedFindings[item.paper_id].splice(index, 1);
      renderMissedFindings(item);
      saveLocal();
    });
    card.append(heading, value, pages, remove);
    return card;
  }));
}

function renderMacrostructures(paper, pageRef) {
  const regions = (paper.macrostructure_regions || []).filter(
    (region) => region.page_ref === pageRef
  );
  byId("macrostructureGallery").replaceChildren(...regions.map((region) => {
    const figure = document.createElement("figure");
    const image = document.createElement("img");
    image.src = region.crop_path;
    image.alt = region.caption || `${region.kind} crop on page ${pageRef}`;
    const caption = document.createElement("figcaption");
    const label = region.caption ? ` · ${region.caption}` : "";
    caption.textContent = `${prettyLabel(region.kind)} · ${region.confidence} geometry confidence${label}`;
    figure.append(image, caption);
    return figure;
  }));
  byId("macrostructureGallery").classList.toggle("hidden", regions.length === 0);
}

function updateVisitedDisplay(paperId) {
  const paper = paperFor(paperId);
  const viewed = paperState(paperId, currentItem()).viewed_page_refs.length;
  byId("visitedPages").textContent = `${viewed} of ${paper.page_count} pages viewed`;
}

function applyZoom() {
  byId("pageImage").style.width = `${Math.round(100 * state.zoom)}%`;
}

function renderMarks(item) {
  const marks = state.marks[item.item_id] || [];
  byId("markedCount").textContent = marks.length
    ? `${marks.length} passage${marks.length === 1 ? "" : "s"} marked for this answer`
    : "No passages marked yet";
  byId("markedTextList").replaceChildren(...marks.map((mark, index) => {
    const block = document.createElement("div");
    block.className = "marked-text-item";
    const quote = document.createElement("q");
    quote.textContent = mark.excerpt;
    const meta = document.createElement("small");
    meta.textContent = `Page ${mark.page_ref}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove mark";
    remove.addEventListener("click", () => {
      state.marks[item.item_id].splice(index, 1);
      renderMarks(item);
      saveLocal();
    });
    block.append(quote, meta, remove);
    return block;
  }));
}

function togglePassageMark(item, pageRef, excerpt) {
  state.marks[item.item_id] = state.marks[item.item_id] || [];
  const index = state.marks[item.item_id].findIndex(
    (mark) => mark.page_ref === pageRef && mark.excerpt === excerpt
  );
  if (index >= 0) {
    state.marks[item.item_id].splice(index, 1);
  } else {
    state.marks[item.item_id].push({
      page_ref: pageRef,
      excerpt,
      captured_at: new Date().toISOString(),
    });
  }
  renderMarks(item);
  const page = paperFor(item.paper_id).pages.find((entry) => entry.page_ref === pageRef);
  renderPaperText(item, page);
  saveLocal();
}

function splitPassages(text) {
  const sentences = text
    .split(/(?<=[.!?])\s+(?=[A-Z0-9])/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 20);
  const passages = [];
  for (const sentence of sentences) {
    if (sentence.length <= 1200) {
      passages.push(sentence);
      continue;
    }
    for (let start = 0; start < sentence.length; start += 900) {
      passages.push(sentence.slice(start, start + 900).trim());
    }
  }
  return passages;
}

function renderPaperText(item, page) {
  const marked = state.marks[item.item_id] || [];
  byId("pageText").replaceChildren(...splitPassages(page.text).map((passage) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "passage-button";
    button.textContent = passage;
    button.classList.toggle(
      "marked",
      marked.some((mark) => mark.page_ref === page.page_ref && mark.excerpt === passage)
    );
    button.addEventListener("click", () => togglePassageMark(item, page.page_ref, passage));
    return button;
  }));
}

function showPaperPage(pageRef) {
  const item = currentItem();
  const paper = paperFor(item.paper_id);
  const page = paper.pages.find((entry) => entry.page_ref === pageRef);
  if (!page) return;
  capturePaperViewport();
  flushModeDwell(false);
  flushPageDwell(false);
  const pState = paperState(item.paper_id, item);
  const session = itemSession(item.item_id);
  pState.active_page_ref = pageRef;
  if (!pState.viewed_page_refs.includes(pageRef)) pState.viewed_page_refs.push(pageRef);
  pState.viewed_page_refs.sort((a, b) => a - b);
  pState.visit_count_by_page[pageRef] = (pState.visit_count_by_page[pageRef] || 0) + 1;
  if (!session.viewed_page_refs.includes(pageRef)) session.viewed_page_refs.push(pageRef);
  session.viewed_page_refs.sort((a, b) => a - b);
  session.visit_count_by_page[pageRef] = (session.visit_count_by_page[pageRef] || 0) + 1;
  if (!session.viewed_modes.includes(state.activeEvidenceMode)) {
    session.viewed_modes.push(state.activeEvidenceMode);
  }
  session.mode_visit_count[state.activeEvidenceMode] =
    (session.mode_visit_count[state.activeEvidenceMode] || 0) + 1;
  state.activePaperId = item.paper_id;
  state.activeItemId = item.item_id;
  state.activePageRef = pageRef;
  const now = performance.now();
  state.pageEnteredAt = timingEligible() ? now : null;
  state.evidenceModeEnteredAt = timingEligible() ? now : null;
  byId("evidenceTitle").textContent = `${item.paper_id} / page ${pageRef} of ${paper.page_count}`;
  byId("pageImage").src = page.image_path;
  byId("pageImage").alt = `${item.paper_id}, page ${pageRef}`;
  renderMacrostructures(paper, pageRef);
  renderPaperText(item, page);
  byId("pageSelect").value = String(pageRef);
  byId("pagePrevious").disabled = pageRef === 1;
  byId("pageNext").disabled = pageRef === paper.page_count;
  restorePaperViewport(item.paper_id, pageRef);
  updateVisitedDisplay(item.paper_id);
  saveLocal();
}

function renderPaper(item) {
  const paper = paperFor(item.paper_id);
  const pState = paperState(item.paper_id, item);
  state.activeEvidenceMode = pState.active_mode;
  activateTabUi(pState.active_mode);
  byId("evidenceHint").textContent = `${item.evidence_hint} These are suggested starting points; the complete ${paper.page_count}-page paper is available.`;
  byId("pageSelect").replaceChildren(...paper.pages.map((page) => {
    const option = document.createElement("option");
    option.value = String(page.page_ref);
    option.textContent = String(page.page_ref);
    return option;
  }));
  byId("focusNav").replaceChildren(...item.evidence_pages.map((page) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${page.role === "focus" ? "Suggested" : "Adjacent"} page ${page.page_ref}`;
    button.addEventListener("click", () => showPaperPage(page.page_ref));
    return button;
  }));
  showPaperPage(pState.active_page_ref);
}

function setRadio(name, value) {
  document.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
    input.checked = input.value === value;
  });
}

function renderItem({focus = false, preserveDraft = true} = {}) {
  if (preserveDraft) captureDraft();
  capturePaperViewport();
  flushModeDwell(false);
  flushPageDwell(false);
  buildQueue();
  if (state.currentIndex >= state.queue.length) state.currentIndex = Math.max(0, state.queue.length - 1);
  const item = currentItem();
  if (!item) {
    state.activeItemId = null; state.activePaperId = null; state.activePageRef = null;
    byId("question").textContent = "No questions are available in the current queue.";
    byId("decisionForm").classList.add("hidden");
    byId("previousButton").disabled = true;
    renderProgress(); saveLocal(); return;
  }
  byId("decisionForm").classList.remove("hidden");
  const response = state.drafts[item.item_id] || state.responses[item.item_id];
  byId("decisionForm").reset();
  byId("paperId").textContent = item.paper_id;
  byId("stratum").textContent = item.stratum_label;
  byId("queueReason").textContent = item.phase === "extension" ? "Added after a prior repair signal" : "Diagnostic item";
  byId("question").textContent = item.question;
  byId("answerGuidance").textContent = item.answer_guidance;
  renderCandidate(item.candidate_display);
  if (response) {
    setRadio("verdict", response.verdict);
    byId("correctedValue").value = response.corrected_value || "";
    byId("rationale").value = response.rationale || "";
    byId("errorClass").value = response.error_class || "";
    byId("confidence").value = String(response.confidence || "");
    byId("needsMoreContext").checked = response.context_sufficient === false;
    byId("contextRequest").value = response.context_request || "";
  }
  renderPaper(item);
  renderMarks(item);
  renderMissedFindings(item);
  updateConditionalFields();
  byId("previousButton").disabled = state.currentIndex === 0;
  byId("formError").textContent = "";
  byId("markError").textContent = "";
  renderProgress();
  saveLocal();
  if (byId("fieldNavigationLabel")) byId("fieldNavigationLabel").textContent = `${item.stratum_label} · choose field`;
  const question = byId("question");
  question.setAttribute("tabindex", "-1");
  const panel = question.closest(".question-panel");
  if (panel) panel.scrollTop = 0;
  if (focus) question.focus({preventScroll: true});
}

function updateConditionalFields() {
  const verdict = document.querySelector('input[name="verdict"]:checked')?.value;
  byId("correctionWrap").classList.toggle("hidden", !["substantively_correct_needs_wording", "incorrect"].includes(verdict));
  byId("rationaleWrap").classList.toggle("hidden", !["substantively_correct_needs_wording", "incorrect", "source_does_not_answer", "cannot_decide"].includes(verdict));
  byId("contextRequestWrap").classList.toggle("hidden", !byId("needsMoreContext").checked);
}

function navigationSnapshot(itemId) {
  flushModeDwell();
  flushPageDwell();
  const session = itemSession(itemId);
  return {
    viewed_page_refs: [...session.viewed_page_refs],
    dwell_ms_by_page: Object.fromEntries(
      Object.entries(session.dwell_ms_by_page).map(([page, duration]) => [page, Math.round(duration)])
    ),
    visit_count_by_page: {...session.visit_count_by_page},
    viewed_modes: [...session.viewed_modes],
    dwell_ms_by_mode: Object.fromEntries(
      Object.entries(session.dwell_ms_by_mode).map(([mode, duration]) => [mode, Math.round(duration)])
    ),
    mode_visit_count: {...session.mode_visit_count},
  };
}

function inferredEvidenceExposure(session) {
  const modes = new Set(session.viewed_modes);
  if (modes.has("image") && modes.has("text")) return "both";
  return modes.has("text") ? "text" : "image";
}

function collectResponse() {
  const permissionError = ratingPermissionError();
  if (permissionError) return [null, permissionError];
  if (window.innerWidth < 700) return [null, "Use a tablet or wider window (at least 700 pixels) to save a timed rating."];
  const item = currentItem();
  if (!item) return [null, "No question is available to rate."];
  const verdict = document.querySelector('input[name="verdict"]:checked')?.value;
  const session = itemSession(item.item_id);
  const needsMoreContext = byId("needsMoreContext").checked;
  const exposedPages = [...session.viewed_page_refs];
  const response = {
    item_id: item.item_id,
    verdict,
    corrected_value: byId("correctedValue").value.trim(),
    rationale: byId("rationale").value.trim(),
    error_class: byId("errorClass").value,
    evidence_exposure: inferredEvidenceExposure(session),
    confidence: Number(byId("confidence").value),
    page_exposure_refs: exposedPages,
    marked_text: state.marks[item.item_id] || [],
    paper_navigation_snapshot: navigationSnapshot(item.item_id),
    context_sufficient: !needsMoreContext,
    context_request: byId("contextRequest").value.trim(),
    answered_at: new Date().toISOString(),
  };
  if (!verdict) return [null, "Choose a ruling."];
  if (["substantively_correct_needs_wording", "incorrect"].includes(verdict) && !response.corrected_value) return [null, "State the corrected value."];
  if (![1, 2, 3, 4].includes(response.confidence)) return [null, "State your confidence."];
  if (!exposedPages.length) return [null, "Open at least one paper page before ruling."];
  if (!response.context_sufficient && !response.context_request) return [null, "Describe the additional context needed."];
  return [response, null];
}

function reliabilityDisagreements() {
  return state.data.items.filter((item) => item.repeat_of && state.responses[item.item_id] && state.responses[item.repeat_of])
    .filter((item) => {
      const current = state.responses[item.item_id];
      const original = state.responses[item.repeat_of];
      return current.verdict !== original.verdict || normalized(current.corrected_value) !== normalized(original.corrected_value);
    });
}

function showComplete() {
  pauseTiming();
  const activeResponses = state.queue
    .map((itemId) => state.responses[itemId])
    .filter(Boolean);
  const answered = activeResponses.length;
  const lowConfidence = activeResponses.filter((row) => row.confidence <= 2).length;
  const disagreements = reliabilityDisagreements().length;
  const unresolved = activeResponses.filter(
    (response) => response.confidence <= 2 || response.context_sufficient === false || response.verdict === "cannot_decide"
  ).length;
  byId("reviewScreen").classList.add("hidden");
  byId("completeScreen").classList.remove("hidden");
  byId("completeTitle").textContent = disagreements || unresolved
    ? "The bounded queue is complete, but adjudication is not"
    : "The current annotation packet is complete";
  byId("completeMessage").textContent = disagreements
    ? "The same scientific issue received different rulings. Preserve both answers and export the disagreement for independent resolution."
    : unresolved
      ? "An item remains uncertain or context-limited. Export it so a follow-up packet can supply what was requested."
      : "The queue stopped because the sampling plan has the answers it needs from every field; deferred items can return to the queue if later answers call for them.";
  const stat = (value, label) => `<div><strong>${value}</strong><span>${label}</span></div>`;
  byId("completionStats").innerHTML = [
    stat(answered, "answers"),
    stat(lowConfidence, "tentative or guessing"),
    stat(disagreements, "consistency disagreements"),
  ].join("");
  byId("returnButton").disabled = disagreements > 0;
  renderProgress();
}

function buildExportPayload(exportKind) {
  const responseItemIds = state.queue.filter((itemId) => state.responses[itemId]);
  return {
    schema_version: "ae_scientific_hitl_export.v2",
    study_id: state.data.study_id,
    pack_sha256: state.data.pack_sha256,
    reviewer: state.reviewer,
    responses: responseItemIds.map((itemId) => state.responses[itemId]),
    missed_findings: Object.values(state.missedFindings).flat(),
    exported_at: new Date().toISOString(),
    export_state: {
      kind: exportKind,
      answered_count: responseItemIds.length,
      current_queue_count: state.queue.length,
      current_item_id: state.queue[state.currentIndex] || null,
      unanswered_item_ids: state.queue.filter((itemId) => !state.responses[itemId]),
    },
    browser_stopping_state: {
      current_queue_item_ids: state.queue,
      reliability_disagreement_item_ids: reliabilityDisagreements().map((item) => item.item_id),
      strata_stop_state: state.stopState || null,
      skipped_item_count: state.skippedCount || 0,
      corpus_accuracy_certified: false,
      model_training_authorized: false,
    },
  };
}

function downloadExport(exportKind) {
  capturePaperViewport();
  pauseTiming();
  const payload = buildExportPayload(exportKind);
  const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], {type: "application/json"});
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(blob);
  const reviewerId = state.reviewer.reviewer_id.replace(/[^a-z0-9._-]+/gi, "-");
  const suffix = exportKind === "partial_backup" ? "partial-backup" : "adjudications";
  anchor.download = `${state.data.study_id}__${reviewerId}__${suffix}.json`;
  anchor.click();
  URL.revokeObjectURL(anchor.href);
  resumeTiming();
}

function exportReview() {
  downloadExport("completed_queue");
}

function markSelectedText() {
  const item = currentItem();
  const selection = window.getSelection();
  const excerpt = selection?.toString().trim() || "";
  const anchor = selection?.anchorNode;
  if (!excerpt || !anchor || !byId("pageText").contains(anchor)) {
    byId("markError").textContent = "Select text from the displayed article page first.";
    return;
  }
  if (excerpt.length > 4000) {
    byId("markError").textContent = "Select a more focused passage (4,000 characters or fewer).";
    return;
  }
  state.marks[item.item_id] = state.marks[item.item_id] || [];
  if (!state.marks[item.item_id].some((mark) => mark.page_ref === state.activePageRef && mark.excerpt === excerpt)) {
    state.marks[item.item_id].push({page_ref: state.activePageRef, excerpt, captured_at: new Date().toISOString()});
  }
  selection.removeAllRanges();
  byId("markError").textContent = "";
  renderMarks(item);
  saveLocal();
}

async function init() {
  state.profile = profileFor(new URLSearchParams(window.location.search).get("reviewer")) || "David";
  const response = await fetch("review_data.json", {cache: "no-store"});
  if (!response.ok) throw new Error("review_data_load_failed");
  state.data = await response.json();
  byId("studyTitle").textContent = state.data.title;
  byId("purpose").textContent = state.data.purpose;
  byId("reviewerBrief").textContent = state.data.reviewer_brief;
  const gate = state.data.adjudication_gate;
  if (gate && gate.status !== "open") {
    byId("gateStatus").textContent = "Adjudication is locked pending David's taskboard RATIFY row.";
    byId("gateStatus").classList.remove("hidden");
    byId("reviewerForm").querySelector('button[type="submit"]').disabled = true;
    byId("returnToPaperButton").disabled = true;
  }
  restoreLocal();
  if (!state.reviewer) state.reviewer = {
    reviewer_id: state.profile, expertise: "", independent_of_candidate_author: null,
    started_at: new Date().toISOString(),
  };
  renderReviewerIdentity();
  buildQueue();
  renderProgress();
  renderSaveStatus();
  if (state.reviewer) {
    byId("reviewerId").value = state.reviewer.reviewer_id || "";
    byId("expertise").value = state.reviewer.expertise || "";
    byId("independence").checked = state.reviewer.independent_of_candidate_author === true;
    const answerCount = Object.keys(state.responses).length;
    const savedTime = state.lastSavedAt
      ? new Date(state.lastSavedAt).toLocaleString()
      : "an earlier session";
    if (answerCount) {
      byId("resumeNotice").textContent = `Welcome back, ${state.reviewer.reviewer_id}: your answers were last saved ${savedTime}.`;
      byId("resumeNotice").classList.remove("hidden");
    }
    byId("resetSavedButton").classList.remove("hidden");
  }
  // The review always opens on this page (DK ruling 2026-09-14): a returning
  // reviewer sees their progress here first, then re-enters at their place.
  syncSettingsButton();
}

byId("reviewerForm").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!gateOpen()) {
    openReviewerSettings("Adjudication is locked. Reviewer settings cannot open the gate.");
    return;
  }
  const reviewerId = byId("reviewerId").value.trim();
  if (profileFor(reviewerId) !== state.profile) {
    openReviewerSettings("Use the reviewer selector to switch profiles. Existing answers will keep their original identity.");
    return;
  }
  if (state.reviewer && state.reviewer.reviewer_id !== reviewerId && hasReviewerScopedState()) {
    byId("resumeNotice").textContent = "This browser contains another review. Choose Start a new review before changing reviewer identity.";
    byId("resumeNotice").classList.remove("hidden");
    return;
  }
  state.reviewer = {
    reviewer_id: reviewerId,
    expertise: byId("expertise").value.trim(),
    independent_of_candidate_author: byId("independence").checked,
    started_at: state.reviewer?.started_at || new Date().toISOString(),
  };
  renderReviewerIdentity();
  saveLocal();
  byId("startScreen").classList.add("hidden");
  byId("reviewScreen").classList.remove("hidden");
  syncSettingsButton();
  renderItem();
});

byId("decisionForm").addEventListener("change", () => { updateConditionalFields(); captureDraft(); saveLocal(); });
byId("decisionForm").addEventListener("input", () => { captureDraft(); saveLocal(); });
byId("reviewerSwitch")?.addEventListener("change", (event) => switchProfile(event.target.value));
byId("reviewerSettingsButton")?.addEventListener("click", () => openReviewerSettings());
byId("returnToPaperButton").addEventListener("click", returnToPaper);
byId("decisionForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const currentId = currentItem()?.item_id;
  const [response, error] = collectResponse();
  if (error) {
    byId("formError").textContent = error;
    if (ratingPermissionError()) openReviewerSettings(error);
    return;
  }
  state.responses[response.item_id] = response;
  delete state.drafts[response.item_id];
  buildQueue();
  const currentPosition = state.queue.indexOf(currentId);
  const laterUnanswered = state.queue.findIndex((itemId, index) => index > currentPosition && !state.responses[itemId]);
  const anyUnanswered = state.queue.findIndex((itemId) => !state.responses[itemId]);
  const nextIndex = laterUnanswered >= 0 ? laterUnanswered : anyUnanswered;
  if (nextIndex >= 0) {
    state.currentIndex = nextIndex;
    saveLocal();
    renderItem({focus: true, preserveDraft: false});
  } else {
    saveLocal();
    showComplete();
  }
});
byId("previousButton").addEventListener("click", () => {
  if (state.currentIndex > 0) navigateToItem(state.queue[state.currentIndex - 1]);
});
byId("returnButton").addEventListener("click", () => {
  byId("completeScreen").classList.add("hidden");
  byId("reviewScreen").classList.remove("hidden");
  state.currentIndex = 0;
  renderItem();
});
byId("exportButton").addEventListener("click", exportReview);
byId("backupButton").addEventListener("click", () => downloadExport("partial_backup"));
byId("resetSavedButton").addEventListener("click", () => {
  switchProfile(state.profile, true);
});
byId("imageTab").addEventListener("click", () => setTab("image"));
byId("textTab").addEventListener("click", () => setTab("text"));
byId("openMarkingButton").addEventListener("click", () => {
  setTab("text");
  byId("textView").scrollIntoView({block: "start", behavior: "smooth"});
  byId("markTextButton").focus();
});
byId("pagePrevious").addEventListener("click", () => showPaperPage(state.activePageRef - 1));
byId("pageNext").addEventListener("click", () => showPaperPage(state.activePageRef + 1));
byId("pageSelect").addEventListener("change", () => showPaperPage(Number(byId("pageSelect").value)));
byId("markTextButton").addEventListener("click", markSelectedText);
byId("addMissedFindingButton").addEventListener("click", () => {
  byId("missedFindingForm").classList.remove("hidden");
  byId("missedFieldName").focus();
});
byId("cancelMissedFindingButton").addEventListener("click", () => {
  byId("missedFindingForm").reset();
  byId("missedFindingForm").classList.add("hidden");
  byId("missedFindingError").textContent = "";
});
byId("missedFindingForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const permissionError = ratingPermissionError();
  if (permissionError) { openReviewerSettings(permissionError); return; }
  if (!currentItem()) return;
  const item = currentItem();
  const paper = paperFor(item.paper_id);
  const pageRefs = [...new Set(
    byId("missedPageRefs").value.split(",").map((value) => Number(value.trim()))
  )].filter((value) => Number.isInteger(value) && value >= 1 && value <= paper.page_count);
  if (!pageRefs.length) {
    byId("missedFindingError").textContent = "Enter at least one valid supporting page number.";
    return;
  }
  const rows = missedFindingsFor(item.paper_id);
  rows.push({
    missed_finding_id: `${item.paper_id}-missed-${String(rows.length + 1).padStart(3, "0")}`,
    paper_id: item.paper_id,
    evaluation_role: paper.evaluation_role,
    field_name: byId("missedFieldName").value.trim(),
    proposed_value: byId("missedValue").value.trim(),
    page_refs: pageRefs.sort((left, right) => left - right),
    note: byId("missedFindingNote").value.trim(),
    recorded_at: new Date().toISOString(),
  });
  byId("missedFindingForm").reset();
  byId("missedFindingForm").classList.add("hidden");
  byId("missedFindingError").textContent = "";
  renderMissedFindings(item);
  saveLocal();
});
byId("zoomOut").addEventListener("click", () => { state.zoom = Math.max(.5, state.zoom - .25); applyZoom(); capturePaperViewport(); saveLocal(); });
byId("zoomReset").addEventListener("click", () => { state.zoom = 1; applyZoom(); capturePaperViewport(); saveLocal(); });
byId("zoomIn").addEventListener("click", () => { state.zoom = Math.min(3, state.zoom + .25); applyZoom(); capturePaperViewport(); saveLocal(); });
byId("imageCanvas").addEventListener("scroll", capturePaperViewport, {passive: true});
byId("pageText").addEventListener("scroll", capturePaperViewport, {passive: true});
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") pauseTiming();
  else resumeTiming();
});
window.addEventListener("blur", pauseTiming);
window.addEventListener("focus", resumeTiming);
window.addEventListener("resize", () => {
  if (timingEligible()) resumeTiming();
  else pauseTiming();
});
window.addEventListener("beforeunload", () => { captureDraft(); pauseTiming(); capturePaperViewport(); saveLocal(); });

init().catch((error) => {
  byId("purpose").textContent = `Could not load the review packet: ${error.message}`;
});
