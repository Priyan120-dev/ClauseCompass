/**
 * Main Application Orchestration Module
 * WCAG 2.1 AA Compliant, Safe DOM Rendering, Vanilla ES Modules
 */

import {
  fetchHealth,
  fetchSamples,
  fetchSampleText,
  analyzeDocumentWithStream,
  askQuestion,
  compareDocuments,
  downloadExport,
} from "./api.js";

import { speakText, stopSpeaking } from "./speech.js";

// Global App State
const state = {
  currentAnalysis: null,
  activeFilter: "all",
  activeParagraphHighlight: null,
  fontSizeMultiplier: 1.0,
};

// DOM Element References
const elements = {
  demoBanner: document.getElementById("demo-banner"),
  srAnnouncer: document.getElementById("sr-announcer"),
  themeToggleBtn: document.getElementById("theme-toggle-btn"),
  themeIcon: document.getElementById("theme-icon"),
  fontDecBtn: document.getElementById("font-decrease-btn"),
  fontResetBtn: document.getElementById("font-reset-btn"),
  fontIncBtn: document.getElementById("font-increase-btn"),

  // Tabs
  tabs: {
    understand: document.getElementById("tab-understand"),
    ask: document.getElementById("tab-ask"),
    compare: document.getElementById("tab-compare"),
  },
  panels: {
    understand: document.getElementById("panel-understand"),
    ask: document.getElementById("panel-ask"),
    compare: document.getElementById("panel-compare"),
  },

  // Understand Form & Inputs
  analyzeForm: document.getElementById("analyze-form"),
  docFileInput: document.getElementById("doc-file-input"),
  docTextInput: document.getElementById("doc-text-input"),
  roleSelect: document.getElementById("role-select"),
  docTypeSelect: document.getElementById("doctype-select"),
  langSelect: document.getElementById("lang-select"),
  readingSelect: document.getElementById("reading-select"),
  piiMaskToggle: document.getElementById("pii-mask-toggle"),
  analyzeBtn: document.getElementById("analyze-btn"),
  clearBtn: document.getElementById("clear-btn"),

  // Sample Buttons
  sampleRentalBtn: document.getElementById("load-sample-rental"),
  sampleFreelanceV1Btn: document.getElementById("load-sample-freelance-v1"),
  sampleFreelanceV2Btn: document.getElementById("load-sample-freelance-v2"),

  // Progress
  progressContainer: document.getElementById("progress-container"),
  progressStatusText: document.getElementById("progress-status-text"),
  progressPercent: document.getElementById("progress-percent"),
  progressFill: document.getElementById("progress-fill"),

  // Results
  analysisResults: document.getElementById("analysis-results"),
  metricVerificationScore: document.getElementById("metric-verification-score"),
  metricHighRisk: document.getElementById("metric-high-risk"),
  metricMedRisk: document.getElementById("metric-med-risk"),
  metricLowRisk: document.getElementById("metric-low-risk"),
  totalClausesCount: document.getElementById("total-clauses-count"),
  clausesList: document.getElementById("clauses-list"),
  missingClausesList: document.getElementById("missing-clauses-list"),
  docViewer: document.getElementById("document-paragraphs-viewer"),
  filterBtns: document.querySelectorAll(".filter-btn"),

  // Export Toolbar
  exportIcsBtn: document.getElementById("export-ics-btn"),
  exportBriefBtn: document.getElementById("export-brief-btn"),
  exportMdBtn: document.getElementById("export-md-btn"),
  printViewBtn: document.getElementById("print-view-btn"),

  // Q&A
  qaForm: document.getElementById("qa-form"),
  qaInput: document.getElementById("qa-question-input"),
  qaLoading: document.getElementById("qa-loading"),
  qaResponseBox: document.getElementById("qa-response-box"),
  quickQBtns: document.querySelectorAll(".quick-q-btn"),

  // Compare
  compareForm: document.getElementById("compare-form"),
  compareDocA: document.getElementById("compare-doc-a"),
  compareDocB: document.getElementById("compare-doc-b"),
  compareSubmitBtn: document.getElementById("compare-submit-btn"),
  compareLoading: document.getElementById("compare-loading"),
  compareResults: document.getElementById("compare-results"),
  loadCompareSamplesBtn: document.getElementById("load-compare-samples-btn"),
};

// Screen Reader Announcer Helper
function announce(message) {
  if (elements.srAnnouncer) {
    elements.srAnnouncer.textContent = "";
    setTimeout(() => {
      elements.srAnnouncer.textContent = message;
    }, 50);
  }
}

// -------------------------------------------------------------
// Initialization & Theme / Font Scaling
// -------------------------------------------------------------
async function initApp() {
  initTheme();
  initFontControls();
  initTabs();
  initEventListeners();

  // Check health and demo mode (Amendment 8)
  try {
    const health = await fetchHealth();
    if (health.demo_mode) {
      elements.demoBanner.hidden = false;
    }
  } catch (err) {
    console.warn("Health check error:", err);
    elements.demoBanner.hidden = false;
  }
}

function initTheme() {
  const saved = localStorage.getItem("clausecompass-theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
  updateThemeIcon(saved);

  elements.themeToggleBtn.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("clausecompass-theme", next);
    updateThemeIcon(next);
    announce(`Switched to ${next} theme`);
  });
}

function updateThemeIcon(theme) {
  elements.themeIcon.textContent = theme === "dark" ? "☀️" : "🌙";
  elements.themeToggleBtn.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} theme`);
}

function initFontControls() {
  elements.fontIncBtn.addEventListener("click", () => {
    if (state.fontSizeMultiplier < 1.35) {
      state.fontSizeMultiplier += 0.08;
      applyFontSize();
    }
  });

  elements.fontDecBtn.addEventListener("click", () => {
    if (state.fontSizeMultiplier > 0.85) {
      state.fontSizeMultiplier -= 0.08;
      applyFontSize();
    }
  });

  elements.fontResetBtn.addEventListener("click", () => {
    state.fontSizeMultiplier = 1.0;
    applyFontSize();
  });
}

function applyFontSize() {
  const newSize = Math.round(16 * state.fontSizeMultiplier);
  document.documentElement.style.setProperty("--base-font-size", `${newSize}px`);
  announce(`Text size adjusted to ${Math.round(state.fontSizeMultiplier * 100)}%`);
}

// -------------------------------------------------------------
// Accessible Tabs Switching
// -------------------------------------------------------------
function initTabs() {
  const tabKeys = ["understand", "ask", "compare"];

  tabKeys.forEach((key) => {
    const btn = elements.tabs[key];
    btn.addEventListener("click", () => switchTab(key));
    btn.addEventListener("keydown", (e) => {
      let targetIndex = null;
      const currentIndex = tabKeys.indexOf(key);

      if (e.key === "ArrowRight") {
        targetIndex = (currentIndex + 1) % tabKeys.length;
      } else if (e.key === "ArrowLeft") {
        targetIndex = (currentIndex - 1 + tabKeys.length) % tabKeys.length;
      }

      if (targetIndex !== null) {
        e.preventDefault();
        const targetKey = tabKeys[targetIndex];
        elements.tabs[targetKey].focus();
        switchTab(targetKey);
      }
    });
  });
}

function switchTab(activeKey) {
  stopSpeaking();
  const tabKeys = ["understand", "ask", "compare"];

  tabKeys.forEach((key) => {
    const btn = elements.tabs[key];
    const panel = elements.panels[key];
    const isActive = key === activeKey;

    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", isActive ? "true" : "false");
    btn.setAttribute("tabindex", isActive ? "0" : "-1");

    panel.classList.toggle("active", isActive);
    panel.hidden = !isActive;
  });

  announce(`Active tab: ${activeKey}`);
}

// -------------------------------------------------------------
// Sample Document Loaders
// -------------------------------------------------------------
async function loadSample(sampleId, defaultRole, defaultDocType) {
  try {
    elements.progressContainer.hidden = false;
    elements.progressStatusText.textContent = `Loading sample ${sampleId}...`;
    elements.progressPercent.textContent = "";
    elements.progressFill.style.width = "30%";

    const sample = await fetchSampleText(sampleId);
    elements.docTextInput.value = sample.text;
    elements.docFileInput.value = "";
    elements.roleSelect.value = defaultRole;
    elements.docTypeSelect.value = defaultDocType;

    elements.progressContainer.hidden = true;
    announce(`Loaded sample: ${sampleId}`);
  } catch (err) {
    elements.progressContainer.hidden = true;
    alert(`Failed to load sample: ${err.message}`);
  }
}

// -------------------------------------------------------------
// Document Analysis & Rendering
// -------------------------------------------------------------
async function handleAnalyze(e) {
  e.preventDefault();
  stopSpeaking();

  const file = elements.docFileInput.files[0];
  const text = elements.docTextInput.value.trim();

  if (!file && !text) {
    alert("Please upload a file or paste contract text.");
    return;
  }

  const formData = new FormData();
  if (file) {
    formData.append("file", file);
  } else {
    formData.append("raw_text", text);
  }

  formData.append("role", elements.roleSelect.value);
  formData.append("doc_type", elements.docTypeSelect.value);
  formData.append("language", elements.langSelect.value);
  formData.append("reading_level", elements.readingSelect.value);
  formData.append("pii_mask", elements.piiMaskToggle.checked ? "true" : "false");

  elements.analyzeBtn.disabled = true;
  elements.progressContainer.hidden = false;
  elements.analysisResults.hidden = true;
  announce("Starting document analysis...");

  try {
    const analysis = await analyzeDocumentWithStream(formData, (update) => {
      if (update.message) {
        elements.progressStatusText.textContent = update.message;
      }
      if (typeof update.progress === "number") {
        elements.progressPercent.textContent = `${update.progress}%`;
        elements.progressFill.style.width = `${update.progress}%`;
      }
    });

    state.currentAnalysis = analysis;
    renderAnalysis(analysis);
    elements.analysisResults.hidden = false;
    announce(`Analysis complete. Verification score: ${analysis.verification_score}%`);
  } catch (err) {
    console.error("Analysis failed:", err);
    alert(`Analysis error: ${err.message}`);
    announce("Analysis failed.");
  } finally {
    elements.analyzeBtn.disabled = false;
    elements.progressContainer.hidden = true;
  }
}

function renderAnalysis(analysis) {
  // 1. Metrics Scorecard
  elements.metricVerificationScore.textContent = `${analysis.verification_score}%`;
  elements.metricHighRisk.textContent = analysis.high_risk_count;
  elements.metricMedRisk.textContent = analysis.medium_risk_count;
  elements.metricLowRisk.textContent = analysis.low_risk_count;
  elements.totalClausesCount.textContent = analysis.total_clauses;

  // 2. Render Document Paragraphs in Viewer
  renderDocumentViewer(analysis.paragraphs);

  // 3. Render Clauses List
  renderClausesList(analysis.clauses);

  // 4. Render Missing Clauses Checklist
  renderMissingClauses(analysis.missing_clauses);
}

function renderDocumentViewer(paragraphs) {
  elements.docViewer.innerHTML = "";

  paragraphs.forEach((p) => {
    const block = document.createElement("div");
    block.className = "para-block";
    block.id = `viewer-${p.paragraph_id}`;
    block.setAttribute("data-pid", p.paragraph_id);

    const tag = document.createElement("span");
    tag.className = "para-id-tag";
    tag.textContent = `[${p.paragraph_id}]`;

    const content = document.createElement("span");
    content.textContent = p.text;

    block.appendChild(tag);
    block.appendChild(content);
    elements.docViewer.appendChild(block);
  });
}

function renderClausesList(clauses) {
  elements.clausesList.innerHTML = "";

  const filtered = clauses.filter((c) => {
    if (state.activeFilter === "all") return true;
    return c.risk_level.toLowerCase() === state.activeFilter;
  });

  if (filtered.length === 0) {
    const emptyMsg = document.createElement("p");
    emptyMsg.className = "input-hint";
    emptyMsg.textContent = "No clauses match the selected filter.";
    elements.clausesList.appendChild(emptyMsg);
    return;
  }

  filtered.forEach((c) => {
    const card = document.createElement("article");
    card.className = "clause-card";
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-label", `${c.title} clause, risk level ${c.risk_level}`);

    // Header
    const header = document.createElement("div");
    header.className = "clause-card-header";

    const titleGroup = document.createElement("div");
    titleGroup.className = "clause-title-group";

    const title = document.createElement("h4");
    title.textContent = c.title;

    const cat = document.createElement("span");
    cat.className = "clause-category";
    cat.textContent = c.category;

    titleGroup.appendChild(title);
    titleGroup.appendChild(cat);

    // Badges Group (Risk + Verified)
    const badgesGroup = document.createElement("div");
    badgesGroup.className = "badges-group";

    // Risk Badge (Accessible Icon + Text)
    const riskBadge = document.createElement("span");
    riskBadge.className = `badge-risk badge-risk-${c.risk_level.toLowerCase()}`;
    const riskIcon = c.risk_level === "high" ? "🔴" : c.risk_level === "medium" ? "🟡" : "🟢";
    riskBadge.textContent = `${riskIcon} ${c.risk_level.toUpperCase()} RISK`;

    // Quote Verified Badge (Amendment 1)
    const firstEv = c.evidence && c.evidence[0];
    const isVerified = firstEv && firstEv.verification_status === "VERIFIED";
    const verBadge = document.createElement("span");
    verBadge.className = isVerified ? "badge-verified" : "badge-unverified";
    verBadge.textContent = isVerified ? "✓ Quote verified" : "⚠️ Unverified quote";

    badgesGroup.appendChild(riskBadge);
    badgesGroup.appendChild(verBadge);

    header.appendChild(titleGroup);
    header.appendChild(badgesGroup);

    // Summary
    const summary = document.createElement("p");
    summary.className = "clause-summary";
    summary.textContent = c.plain_language_summary;

    // Risk Reason & Impact
    const riskReason = document.createElement("div");
    riskReason.className = "clause-risk-reason";
    riskReason.textContent = `Why: ${c.risk_reason} (${c.user_role_impact})`;

    // Action Recommendation
    let recDiv = null;
    if (c.actionable_recommendation) {
      recDiv = document.createElement("div");
      recDiv.className = "missing-ask";
      recDiv.style.marginBottom = "0.75rem";
      recDiv.textContent = `Suggested Action / Question: ${c.actionable_recommendation}`;
    }

    // Card Footer (Show source + Read aloud)
    const footer = document.createElement("div");
    footer.className = "clause-card-footer";

    const sourceBtn = document.createElement("button");
    sourceBtn.className = "btn btn-outline";
    sourceBtn.style.padding = "0.25rem 0.65rem";
    sourceBtn.style.fontSize = "0.75rem";
    sourceBtn.textContent = `Show source (${firstEv ? firstEv.paragraph_id : "doc"})`;
    sourceBtn.addEventListener("click", () => {
      if (firstEv) {
        highlightSourceInViewer(firstEv.paragraph_id, firstEv.exact_quote);
      }
    });

    const speechBtn = document.createElement("button");
    speechBtn.className = "btn-speech";
    speechBtn.title = "Read clause aloud";
    speechBtn.setAttribute("aria-label", `Read ${c.title} aloud`);
    speechBtn.textContent = "🔊 Read aloud";
    speechBtn.addEventListener("click", () => {
      const activeLang = elements.langSelect.value || "en";
      speakText(`${c.title}. ${c.plain_language_summary}. ${c.actionable_recommendation || ""}`, activeLang);
    });

    footer.appendChild(sourceBtn);
    footer.appendChild(speechBtn);

    card.appendChild(header);
    card.appendChild(summary);
    card.appendChild(riskReason);
    if (recDiv) card.appendChild(recDiv);
    card.appendChild(footer);

    elements.clausesList.appendChild(card);
  });
}

function renderMissingClauses(missingItems) {
  elements.missingClausesList.innerHTML = "";

  missingItems.forEach((m) => {
    const card = document.createElement("div");
    card.className = "missing-clause-card";

    const header = document.createElement("div");
    header.className = "missing-header";

    const title = document.createElement("h4");
    title.textContent = m.clause_name;

    const badge = document.createElement("span");
    const isFound = m.status === "FOUND";
    badge.className = isFound ? "badge-missing-found" : "badge-missing-notfound";
    badge.textContent = isFound ? "FOUND IN CONTRACT" : "NOT STATED IN CONTRACT";

    header.appendChild(title);
    header.appendChild(badge);

    const why = document.createElement("p");
    why.className = "missing-details";
    why.textContent = `Why it matters: ${m.why_it_matters}`;

    const ask = document.createElement("div");
    ask.className = "missing-ask";
    ask.textContent = `Question to ask: "${m.question_to_ask}"`;

    card.appendChild(header);
    card.appendChild(why);
    card.appendChild(ask);

    elements.missingClausesList.appendChild(card);
  });
}

function highlightSourceInViewer(paragraphId, exactQuote) {
  // Remove previous highlights
  if (state.activeParagraphHighlight) {
    state.activeParagraphHighlight.classList.remove("para-active-highlight");
  }

  const target = document.getElementById(`viewer-${paragraphId}`);
  if (target) {
    target.classList.add("para-active-highlight");
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    state.activeParagraphHighlight = target;
    announce(`Scrolled to source paragraph ${paragraphId}`);
  }
}

// -------------------------------------------------------------
// Grounded Q&A Handling
// -------------------------------------------------------------
async function handleQA(questionText) {
  if (!state.currentAnalysis) {
    alert("Please analyze a document in the 'Understand' tab first, or paste document text.");
    return;
  }

  elements.qaLoading.hidden = false;
  elements.qaResponseBox.hidden = true;
  announce("Processing grounded question...");

  try {
    const result = await askQuestion({
      paragraphs: state.currentAnalysis.paragraphs,
      question: questionText,
      role: elements.roleSelect.value,
      language: elements.langSelect.value,
    });

    renderQAResponse(result);
    elements.qaResponseBox.hidden = false;
    announce(`Answer received with status ${result.status}`);
  } catch (err) {
    alert(`Q&A error: ${err.message}`);
  } finally {
    elements.qaLoading.hidden = true;
  }
}

function renderQAResponse(res) {
  elements.qaResponseBox.innerHTML = "";

  const statusRow = document.createElement("div");
  statusRow.className = "qa-status-row";

  const questionTitle = document.createElement("strong");
  questionTitle.textContent = res.question;

  const statusBadge = document.createElement("span");
  statusBadge.className = `badge-status badge-status-${res.status.toLowerCase()}`;
  statusBadge.textContent = res.status;

  statusRow.appendChild(questionTitle);
  statusRow.appendChild(statusBadge);

  const answer = document.createElement("div");
  answer.className = "qa-answer-text";
  answer.textContent = res.answer;

  elements.qaResponseBox.appendChild(statusRow);
  elements.qaResponseBox.appendChild(answer);

  // Citations
  if (res.citations && res.citations.length > 0) {
    const citBox = document.createElement("div");
    citBox.className = "qa-citations";
    const citTitle = document.createElement("strong");
    citTitle.textContent = "Verified Grounded Citations:";
    citBox.appendChild(citTitle);

    res.citations.forEach((c) => {
      const p = document.createElement("p");
      p.style.marginTop = "0.25rem";
      const isVer = c.verification_status === "VERIFIED";
      p.textContent = `[${c.paragraph_id}] "${c.exact_quote}" (${isVer ? "✓ Quote verified" : "⚠️ Unverified"})`;
      citBox.appendChild(p);
    });
    elements.qaResponseBox.appendChild(citBox);
  }

  // What's missing / Question to ask
  if (res.whats_missing_or_to_ask) {
    const missingDiv = document.createElement("div");
    missingDiv.className = "qa-missing-ask";
    missingDiv.textContent = `What to ask / Missing: ${res.whats_missing_or_to_ask}`;
    elements.qaResponseBox.appendChild(missingDiv);
  }
}

// -------------------------------------------------------------
// Document Compare Handling
// -------------------------------------------------------------
async function handleCompare(e) {
  e.preventDefault();
  const docA = elements.compareDocA.value.trim();
  const docB = elements.compareDocB.value.trim();

  if (!docA || !docB) {
    alert("Please enter text for both Document A and Document B.");
    return;
  }

  elements.compareLoading.hidden = false;
  elements.compareResults.hidden = true;
  announce("Comparing documents...");

  try {
    const result = await compareDocuments({
      doc_a_text: docA,
      doc_b_text: docB,
      role: elements.roleSelect.value,
      language: elements.langSelect.value,
      doc_a_name: "Original Version",
      doc_b_name: "Revised Version",
    });

    renderCompareResults(result);
    elements.compareResults.hidden = false;
    announce("Comparison complete.");
  } catch (err) {
    alert(`Comparison error: ${err.message}`);
  } finally {
    elements.compareLoading.hidden = true;
  }
}

function renderCompareResults(compareData) {
  elements.compareResults.innerHTML = "";

  const summaryCard = document.createElement("div");
  summaryCard.className = "card";
  summaryCard.style.marginBottom = "1rem";
  summaryCard.innerHTML = `
    <h3>Version Comparison Summary</h3>
    <p style="margin: 0.5rem 0; font-size: var(--text-sm);">${compareData.overall_summary}</p>
    <span class="badge-status badge-status-answered">${compareData.total_differences} Aligned Differences Analyzed</span>
  `;
  elements.compareResults.appendChild(summaryCard);

  compareData.items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "compare-item-card";

    const header = document.createElement("div");
    header.className = "compare-item-header";

    const titleGroup = document.createElement("div");
    titleGroup.innerHTML = `<strong>${item.title}</strong> <span style="font-size: var(--text-xs); color: var(--text-muted);">(${item.category})</span>`;

    const diffBadge = document.createElement("span");
    diffBadge.className = `badge-diff badge-diff-${item.diff_type.toLowerCase()}`;
    diffBadge.textContent = item.diff_type;

    header.appendChild(titleGroup);
    header.appendChild(diffBadge);

    const sidesGrid = document.createElement("div");
    sidesGrid.className = "compare-sides-grid";
    sidesGrid.innerHTML = `
      <div>
        <strong>Original:</strong>
        <p>${item.doc_a_summary || "<em>Clause not present</em>"}</p>
      </div>
      <div>
        <strong>Revised:</strong>
        <p>${item.doc_b_summary || "<em>Clause not present</em>"}</p>
      </div>
    `;

    const metaRow = document.createElement("div");
    metaRow.className = "compare-meta-row";
    metaRow.innerHTML = `
      <span><strong>Who Benefits:</strong> ${item.who_benefits}</span>
      <span><strong>Risk Delta:</strong> ${item.risk_delta.toUpperCase()}</span>
    `;

    const explanation = document.createElement("p");
    explanation.style.fontSize = "var(--text-xs)";
    explanation.style.marginTop = "0.5rem";
    explanation.textContent = item.explanation;

    card.appendChild(header);
    card.appendChild(sidesGrid);
    card.appendChild(metaRow);
    card.appendChild(explanation);

    elements.compareResults.appendChild(card);
  });
}

// -------------------------------------------------------------
// Event Listeners Binding
// -------------------------------------------------------------
function initEventListeners() {
  // Analyze Form
  elements.analyzeForm.addEventListener("submit", handleAnalyze);
  elements.clearBtn.addEventListener("click", () => {
    elements.analyzeForm.reset();
    elements.analysisResults.hidden = true;
    state.currentAnalysis = null;
    announce("Form cleared.");
  });

  // Filter Buttons
  elements.filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      elements.filterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.activeFilter = btn.getAttribute("data-filter");
      if (state.currentAnalysis) {
        renderClausesList(state.currentAnalysis.clauses);
      }
    });
  });

  // Quick Samples
  elements.sampleRentalBtn.addEventListener("click", () => {
    loadSample("rental_agreement", "tenant", "rental");
  });
  elements.sampleFreelanceV1Btn.addEventListener("click", () => {
    loadSample("freelance_v1", "freelancer", "freelance");
  });
  elements.sampleFreelanceV2Btn.addEventListener("click", () => {
    loadSample("freelance_v2", "freelancer", "freelance");
  });

  // Exports
  elements.exportIcsBtn.addEventListener("click", () => {
    if (state.currentAnalysis) {
      downloadExport("ics", state.currentAnalysis, `deadlines_${state.currentAnalysis.doc_type}.ics`);
    }
  });
  elements.exportBriefBtn.addEventListener("click", () => {
    if (state.currentAnalysis) {
      downloadExport("brief", state.currentAnalysis, `lawyer_questions_${state.currentAnalysis.doc_type}.md`);
    }
  });
  elements.exportMdBtn.addEventListener("click", () => {
    if (state.currentAnalysis) {
      downloadExport("markdown", state.currentAnalysis, `clausecompass_report_${state.currentAnalysis.doc_type}.md`);
    }
  });
  elements.printViewBtn.addEventListener("click", () => {
    window.print();
  });

  // Q&A Form
  elements.qaForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = elements.qaInput.value.trim();
    if (q) handleQA(q);
  });

  // Quick Questions
  elements.quickQBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-q");
      elements.qaInput.value = q;
      handleQA(q);
    });
  });

  // Compare Form & Samples
  elements.compareForm.addEventListener("submit", handleCompare);
  elements.loadCompareSamplesBtn.addEventListener("click", async () => {
    try {
      const v1 = await fetchSampleText("freelance_v1");
      const v2 = await fetchSampleText("freelance_v2");
      elements.compareDocA.value = v1.text;
      elements.compareDocB.value = v2.text;
      announce("Loaded Freelance V1 and V2 sample texts into comparison inputs.");
    } catch (err) {
      alert("Failed to load compare samples.");
    }
  });
}

// Start application
document.addEventListener("DOMContentLoaded", initApp);
