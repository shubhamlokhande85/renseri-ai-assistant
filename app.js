(() => {
  const CHART_PALETTE = [
    "#10b981",
    "#6366f1",
    "#f59e0b",
    "#06b6d4",
    "#ec4899",
    "#8b5cf6",
    "#22c55e",
    "#f97316",
  ];

  const state = {
    sessionId: null,
    dataset: null,
    dashboard: null,
    previewMode: "cleaned",
    aiProvider: "auto",
    history: [],
    aiConfig: null,
    activeTab: "chat",
    voiceListening: false,
    voiceSpeaking: false,
  };

  const els = {
    // Ribbon
    ribbonSearchForm: document.getElementById("ribbonSearchForm"),
    ribbonSearchInput: document.getElementById("ribbonSearchInput"),
    voiceMicBtn: document.getElementById("voiceMicBtn"),
    llmSettingsBtn: document.getElementById("llmSettingsBtn"),
    keyStatusDot: document.getElementById("keyStatusDot"),
    themeToggleBtn: document.getElementById("themeToggleBtn"),
    // Minimal Sidebar
    topProviderSelect: document.getElementById("topProviderSelect"),
    activeModelLabel: document.getElementById("activeModelLabel"),
    sidebarKeyBtn: document.getElementById("sidebarKeyBtn"),
    sidebarKeyStatus: document.getElementById("sidebarKeyStatus"),
    sidebarDatasetName: document.getElementById("sidebarDatasetName"),
    sidebarClearChatBtn: document.getElementById("sidebarClearChatBtn"),
    // Feature 1: AI Assistant
    assistantStatusHint: document.getElementById("assistantStatusHint"),
    clearChatBtn: document.getElementById("clearChatBtn"),
    chatFeed: document.getElementById("chatFeed"),
    suggestionsBar: document.getElementById("suggestionsBar"),
    chatForm: document.getElementById("chatForm"),
    chatInput: document.getElementById("chatInput"),
    chatVoiceMicBtn: document.getElementById("chatVoiceMicBtn"),
    sendChatBtn: document.getElementById("sendChatBtn"),
    // Feature 2: Upload Dataset
    dropzone: document.getElementById("dropzone"),
    fileInput: document.getElementById("fileInput"),
    uploadStatusText: document.getElementById("uploadStatusText"),
    pasteDatasetName: document.getElementById("pasteDatasetName"),
    pasteDatasetFormat: document.getElementById("pasteDatasetFormat"),
    pasteDatasetText: document.getElementById("pasteDatasetText"),
    submitPasteBtn: document.getElementById("submitPasteBtn"),
    sampleButtons: document.getElementById("sampleButtons"),
    // Feature 3: Data & Cleaning
    cleaningMetaBadge: document.getElementById("cleaningMetaBadge"),
    exportCsvBtn: document.getElementById("exportCsvBtn"),
    exportXlsxBtn: document.getElementById("exportXlsxBtn"),
    exportDbBtn: document.getElementById("exportDbBtn"),
    inspectorContent: document.getElementById("inspectorContent"),
    // Feature 4: Dashboard & Dataset Queries
    dashPromptForm: document.getElementById("dashPromptForm"),
    dashPromptInput: document.getElementById("dashPromptInput"),
    dashBuildAutoBtn: document.getElementById("dashBuildAutoBtn"),
    dashQueryOutput: document.getElementById("dashQueryOutput"),
    dashboardContent: document.getElementById("dashboardContent"),
    // Feature 5: Dataset Summary
    summaryContent: document.getElementById("summaryContent"),
    summaryEmptyState: document.getElementById("summaryEmptyState"),
    // Feature 6: Additional Cleaning
    customCleanDatasetHint: document.getElementById("customCleanDatasetHint"),
    strategySelect: document.getElementById("strategySelect"),
    textCaseSelect: document.getElementById("textCaseSelect"),
    fillTextInput: document.getElementById("fillTextInput"),
    roundDecimalsSelect: document.getElementById("roundDecimalsSelect"),
    optDedup: document.getElementById("optDedup"),
    optDates: document.getElementById("optDates"),
    optNumeric: document.getElementById("optNumeric"),
    optCols: document.getElementById("optCols"),
    replaceColSelect: document.getElementById("replaceColSelect"),
    findTextInput: document.getElementById("findTextInput"),
    replaceTextInput: document.getElementById("replaceTextInput"),
    dropColsList: document.getElementById("dropColsList"),
    recleanBtn: document.getElementById("recleanBtn"),
    resetCustomCleanBtn: document.getElementById("resetCustomCleanBtn"),
    customCleanLog: document.getElementById("customCleanLog"),
    // Feature 5: Power Query controls
    dtypeColSelect: document.getElementById("dtypeColSelect"),
    dtypeTargetSelect: document.getElementById("dtypeTargetSelect"),
    splitColSelect: document.getElementById("splitColSelect"),
    splitDelimInput: document.getElementById("splitDelimInput"),
    splitMaxSelect: document.getElementById("splitMaxSelect"),
    extractColSelect: document.getElementById("extractColSelect"),
    extractModeSelect: document.getElementById("extractModeSelect"),
    extractParamInput: document.getElementById("extractParamInput"),
    extractOutputCol: document.getElementById("extractOutputCol"),
    filterColSelect: document.getElementById("filterColSelect"),
    filterCondSelect: document.getElementById("filterCondSelect"),
    filterValInput: document.getElementById("filterValInput"),
    sortColSelect: document.getElementById("sortColSelect"),
    sortDirSelect: document.getElementById("sortDirSelect"),
    renameColSelect: document.getElementById("renameColSelect"),
    renameToInput: document.getElementById("renameToInput"),
    fillDirColSelect: document.getElementById("fillDirColSelect"),
    fillDirSelect: document.getElementById("fillDirSelect"),
    // API Key Modal
    aiModal: document.getElementById("aiModal"),
    closeAiModalBtn: document.getElementById("closeAiModalBtn"),
    llmProviderSelect: document.getElementById("llmProviderSelect"),
    groqApiKeyInput: document.getElementById("groqApiKeyInput"),
    groqModelSelect: document.getElementById("groqModelSelect"),
    groqKeyStatus: document.getElementById("groqKeyStatus"),
    groqTestMsg: document.getElementById("groqTestMsg"),
    testGroqBtn: document.getElementById("testGroqBtn"),
    clearGroqBtn: document.getElementById("clearGroqBtn"),
    geminiApiKeyInput: document.getElementById("geminiApiKeyInput"),
    geminiModelSelect: document.getElementById("geminiModelSelect"),
    geminiKeyStatus: document.getElementById("geminiKeyStatus"),
    geminiTestMsg: document.getElementById("geminiTestMsg"),
    testGeminiBtn: document.getElementById("testGeminiBtn"),
    clearGeminiBtn: document.getElementById("clearGeminiBtn"),
    persistEnvCheck: document.getElementById("persistEnvCheck"),
    clearAiKeyBtn: document.getElementById("clearAiKeyBtn"),
    saveAiKeyBtn: document.getElementById("saveAiKeyBtn"),
    toastContainer: document.getElementById("toastContainer"),
  };

  function escapeHtml(val) {
    return String(val ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatInlineMarkdown(text) {
    let safe = escapeHtml(text);
    safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
    safe = safe.replace(/\*(.+?)\*/g, "<em>$1</em>");
    safe = safe.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    return safe;
  }

  function formatMarkdownReply(text) {
    const raw = String(text || "").trim();
    if (!raw) return "";
    const parts = raw.split(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g);
    let html = "";
    for (let i = 0; i < parts.length; i++) {
      if (i % 3 === 1) continue;
      if (i % 3 === 2) {
        html += `<pre class="md-pre"><code>${escapeHtml(parts[i].trimEnd())}</code></pre>`;
        continue;
      }
      const lines = parts[i].split(/\r?\n/);
      let inUl = false;
      let inOl = false;
      let tableRows = [];
      const closeLists = () => {
        if (inUl) {
          html += "</ul>";
          inUl = false;
        }
        if (inOl) {
          html += "</ol>";
          inOl = false;
        }
      };
      const flushTable = () => {
        if (!tableRows.length) return;
        const parsed = tableRows.map((r) =>
          r.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim())
        );
        tableRows = [];
        if (parsed.length < 2) {
          parsed.forEach((cells) => {
            html += `<p>${formatInlineMarkdown(cells.join(" | "))}</p>`;
          });
          return;
        }
        const isSep = (cells) => cells.every((c) => /^:?-{2,}:?$/.test(c));
        const headers = parsed[0];
        const bodyRows = isSep(parsed[1]) ? parsed.slice(2) : parsed.slice(1);
        html += `<div class="md-table-wrap"><table class="md-table"><thead><tr>${headers
          .map((h) => `<th>${formatInlineMarkdown(h)}</th>`)
          .join("")}</tr></thead><tbody>`;
        bodyRows.forEach((rowCells) => {
          html += `<tr>${headers
            .map((_, idx) => `<td>${formatInlineMarkdown(rowCells[idx] ?? "")}</td>`)
            .join("")}</tr>`;
        });
        html += "</tbody></table></div>";
      };

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("|") && trimmed.includes("|", 1)) {
          closeLists();
          tableRows.push(trimmed);
          continue;
        }
        flushTable();
        if (!trimmed) {
          closeLists();
          continue;
        }
        if (trimmed.startsWith("#### ")) {
          closeLists();
          html += `<h5>${formatInlineMarkdown(trimmed.slice(5))}</h5>`;
        } else if (trimmed.startsWith("### ")) {
          closeLists();
          html += `<h4>${formatInlineMarkdown(trimmed.slice(4))}</h4>`;
        } else if (trimmed.startsWith("## ") || trimmed.startsWith("# ")) {
          closeLists();
          html += `<h3>${formatInlineMarkdown(trimmed.replace(/^#{1,3}\s+/, ""))}</h3>`;
        } else if (trimmed.startsWith("> ")) {
          closeLists();
          html += `<blockquote class="md-quote">${formatInlineMarkdown(trimmed.slice(2))}</blockquote>`;
        } else if (/^[-*•]\s+/.test(trimmed)) {
          if (inOl) {
            html += "</ol>";
            inOl = false;
          }
          if (!inUl) {
            html += "<ul>";
            inUl = true;
          }
          html += `<li>${formatInlineMarkdown(trimmed.replace(/^[-*•]\s+/, ""))}</li>`;
        } else if (/^\d+\.\s+/.test(trimmed)) {
          if (inUl) {
            html += "</ul>";
            inUl = false;
          }
          if (!inOl) {
            html += "<ol>";
            inOl = true;
          }
          html += `<li>${formatInlineMarkdown(trimmed.replace(/^\d+\.\s+/, ""))}</li>`;
        } else {
          closeLists();
          html += `<p>${formatInlineMarkdown(trimmed)}</p>`;
        }
      }
      flushTable();
      closeLists();
    }
    return html;
  }

  function showToast(msg, kind = "info") {
    const t = document.createElement("div");
    t.className = `toast ${kind}`;
    t.textContent = msg;
    els.toastContainer.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  function switchTab(target) {
    state.activeTab = target;
    document.querySelectorAll(".tab-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-tab") === target);
    });
    document.querySelectorAll(".tab-content").forEach((c) => {
      c.classList.toggle("active", c.id === `tab-${target}`);
    });
  }

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.getAttribute("data-tab")));
  });

  // Dataset Transformation: 3 Small Square Feature Subtabs (Dataset Summary, Data Cleaning, EDA Summary)
  function switchTransformationSubtab(target) {
    document.querySelectorAll(".trans-square-card").forEach((card) => {
      card.classList.toggle("active", card.getAttribute("data-subtab") === target);
    });
    document.querySelectorAll(".trans-subview").forEach((view) => {
      view.classList.toggle("active", view.id === `subview-${target}`);
    });
  }

  document.querySelectorAll(".trans-square-card").forEach((card) => {
    card.addEventListener("click", () => {
      switchTransformationSubtab(card.getAttribute("data-subtab"));
    });
  });

  // Theme toggle
  els.themeToggleBtn.addEventListener("click", () => {
    const root = document.documentElement;
    root.setAttribute("data-theme", root.getAttribute("data-theme") === "dark" ? "light" : "dark");
  });

  // ================= MINIMAL LEFT SIDEBAR & API KEY CONFIG =================
  function computeActiveModelDisplay(cfg) {
    const prov = cfg.default_provider || "auto";
    if (prov === "groq" || (prov === "auto" && cfg.groq_configured)) {
      return cfg.groq_model || "llama-3.3-70b-versatile";
    }
    if (prov === "gemini" || (prov === "auto" && cfg.gemini_configured)) {
      return cfg.gemini_model || "gemini-2.5-flash";
    }
    if (prov === "local") return "Local Web + Rules";
    return `${cfg.groq_model || "llama-3.3-70b-versatile"} / Web`;
  }

  function applyAiConfigToUi(cfg) {
    state.aiConfig = cfg;
    state.aiProvider = cfg.default_provider || "auto";
    els.topProviderSelect.value = state.aiProvider;
    els.llmProviderSelect.value = state.aiProvider;
    if (cfg.groq_model) els.groqModelSelect.value = cfg.groq_model;
    if (cfg.gemini_model) els.geminiModelSelect.value = cfg.gemini_model;

    els.activeModelLabel.textContent = computeActiveModelDisplay(cfg);

    els.groqKeyStatus.textContent = cfg.groq_configured
      ? `Configured (${cfg.groq_key_masked})`
      : "Not configured";
    els.groqKeyStatus.style.color = cfg.groq_configured ? "var(--success)" : "";

    els.geminiKeyStatus.textContent = cfg.gemini_configured
      ? `Configured (${cfg.gemini_key_masked})`
      : "Not configured";
    els.geminiKeyStatus.style.color = cfg.gemini_configured ? "var(--success)" : "";

    const activeList = [];
    if (cfg.groq_configured) activeList.push("Groq");
    if (cfg.gemini_configured) activeList.push("Gemini");
    els.sidebarKeyStatus.textContent = activeList.length
      ? `${activeList.join(" + ")} Ready`
      : "Add API Key";

    const anyKey = Boolean(cfg.groq_configured || cfg.gemini_configured);
    els.keyStatusDot.classList.toggle("active", anyKey);

    els.assistantStatusHint.textContent = cfg.groq_configured
      ? `Independent General Search · Groq (${cfg.groq_model})`
      : cfg.gemini_configured
      ? `Independent General Search · Google Gemini (${cfg.gemini_model})`
      : "General Search · Google/Web (Add Groq Key for full LLM)";
  }

  async function loadAiConfig() {
    try {
      const res = await fetch("/api/ai/config");
      if (!res.ok) return;
      const cfg = await res.json();
      applyAiConfigToUi(cfg);
    } catch (err) {
      console.error("Failed to load AI config:", err);
    }
  }

  async function persistAiConfig(payload) {
    const res = await fetch("/api/ai/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const cfg = await res.json();
    if (!res.ok) throw new Error(cfg.error || "Failed to save AI config");
    applyAiConfigToUi(cfg);
    return cfg;
  }

  els.topProviderSelect.addEventListener("change", async () => {
    try {
      const cfg = await persistAiConfig({
        default_provider: els.topProviderSelect.value,
        persist_env: true,
      });
      showToast(`Active AI Engine: ${cfg.default_provider.toUpperCase()}`, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  function openAiModal() {
    loadAiConfig();
    els.groqTestMsg.textContent = "";
    els.geminiTestMsg.textContent = "";
    els.aiModal.hidden = false;
  }

  els.llmSettingsBtn.addEventListener("click", openAiModal);
  els.sidebarKeyBtn.addEventListener("click", openAiModal);
  els.closeAiModalBtn.addEventListener("click", () => (els.aiModal.hidden = true));
  els.aiModal.addEventListener("click", (e) => {
    if (e.target === els.aiModal) els.aiModal.hidden = true;
  });

  els.clearAiKeyBtn.addEventListener("click", async () => {
    try {
      await persistAiConfig({ default_provider: "local", persist_env: els.persistEnvCheck.checked });
      els.aiModal.hidden = true;
      showToast("Switched to local engine.", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  els.clearGroqBtn.addEventListener("click", async () => {
    try {
      els.groqApiKeyInput.value = "";
      await persistAiConfig({ clear_groq: true, persist_env: els.persistEnvCheck.checked });
      els.groqTestMsg.textContent = "Cleared.";
      showToast("Groq API key cleared.", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  els.clearGeminiBtn.addEventListener("click", async () => {
    try {
      els.geminiApiKeyInput.value = "";
      await persistAiConfig({ clear_gemini: true, persist_env: els.persistEnvCheck.checked });
      els.geminiTestMsg.textContent = "Cleared.";
      showToast("Gemini API key cleared.", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  async function testProviderKey(provider, keyInput, modelSelect, msgEl) {
    msgEl.textContent = "Testing...";
    msgEl.style.color = "var(--text-muted)";
    try {
      const res = await fetch("/api/ai/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          api_key: keyInput.value.trim() || null,
          model: modelSelect.value,
        }),
      });
      const data = await res.json();
      msgEl.textContent = data.message || (data.ok ? "Connected" : "Failed");
      msgEl.style.color = data.ok ? "var(--success)" : "var(--danger)";
    } catch (err) {
      msgEl.textContent = err.message;
      msgEl.style.color = "var(--danger)";
    }
  }

  els.testGroqBtn.addEventListener("click", () =>
    testProviderKey("groq", els.groqApiKeyInput, els.groqModelSelect, els.groqTestMsg)
  );
  els.testGeminiBtn.addEventListener("click", () =>
    testProviderKey("gemini", els.geminiApiKeyInput, els.geminiModelSelect, els.geminiTestMsg)
  );

  els.saveAiKeyBtn.addEventListener("click", async () => {
    try {
      const payload = {
        default_provider: els.llmProviderSelect.value,
        groq_model: els.groqModelSelect.value,
        gemini_model: els.geminiModelSelect.value,
        persist_env: els.persistEnvCheck.checked,
      };
      if (els.groqApiKeyInput.value.trim()) {
        payload.groq_api_key = els.groqApiKeyInput.value.trim();
      }
      if (els.geminiApiKeyInput.value.trim()) {
        payload.gemini_api_key = els.geminiApiKeyInput.value.trim();
      }
      const cfg = await persistAiConfig(payload);
      els.groqApiKeyInput.value = "";
      els.geminiApiKeyInput.value = "";
      els.aiModal.hidden = true;
      showToast(`Saved AI settings (${cfg.default_provider.toUpperCase()}).`, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  function renderSidebarDataset() {
    if (!state.dataset) {
      els.sidebarDatasetName.className = "side-dataset-empty";
      els.sidebarDatasetName.textContent = "No dataset attached";
      return;
    }
    els.sidebarDatasetName.className = "side-dataset-pill";
    els.sidebarDatasetName.innerHTML = `
      <span title="${escapeHtml(state.dataset.filename)}">${escapeHtml(state.dataset.filename)}</span>
      <button type="button" class="side-detach-btn" id="detachDatasetBtn" title="Detach dataset">&times;</button>
    `;
    const detachBtn = document.getElementById("detachDatasetBtn");
    if (detachBtn) {
      detachBtn.addEventListener("click", () => {
        state.sessionId = null;
        state.dataset = null;
        state.dashboard = null;
        renderSidebarDataset();
        els.inspectorContent.innerHTML = `<div class="empty-state"><p>Attach a dataset in <strong>Upload Dataset</strong> to view the cleaning report and cleaned table.</p></div>`;
        els.dashboardContent.innerHTML = `<div class="empty-state"><p>Attach a dataset in <strong>Upload Dataset</strong> to query it, generate charts, and build an interactive dashboard.</p></div>`;
        els.dashQueryOutput.innerHTML = "";
        els.customCleanDatasetHint.textContent = "Attach a dataset first";
        els.dropColsList.innerHTML = `<span class="hint">Columns appear here once a dataset is attached.</span>`;
        els.customCleanLog.innerHTML = "";
        showToast("Dataset detached.", "info");
      });
    }
  }

  // ================= FEATURE 1: AI ASSISTANT (INDEPENDENT GENERAL SEARCH & GROQ LLM) =================
  function renderWelcomeAssistant() {
    els.chatFeed.innerHTML = `
      <div class="welcome-card" id="welcomeCard">
        <div class="wc-row">
          <div class="wc-left">
            <div class="welcome-badge">AI Assistant</div>
            <h2>Search &amp; Ask Anything</h2>
          </div>
          <div class="wc-chips">
            <button type="button" class="wc-chip interactive-tile" data-quick-prompt="tell me name of current prime minister of india">
              <span class="wc-chip-label">🌐 Live Facts</span>
            </button>
            <button type="button" class="wc-chip interactive-tile" data-quick-prompt="fetch current data from google about Artificial Intelligence news">
              <span class="wc-chip-label">📰 Google News</span>
            </button>
            <button type="button" class="wc-chip interactive-tile" data-quick-prompt="Explain SQL GROUP BY vs HAVING with a clean example">
              <span class="wc-chip-label">🤖 Ask Groq LLM</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function renderSuggestions(suggestions) {
    els.suggestionsBar.innerHTML = "";
    const list = suggestions?.length
      ? suggestions
      : [
          "Current Prime Minister of India",
          "Latest AI news from Google",
          "Explain Python async/await concisely",
        ];
    list.forEach((q) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip-btn";
      chip.textContent = q;
      chip.addEventListener("click", () => submitGeneralAssistant(q));
      els.suggestionsBar.appendChild(chip);
    });
  }

  function clearChatHistory() {
    stopSpeaking();
    state.history = [];
    renderWelcomeAssistant();
    renderSuggestions([]);
    if (state.activeTab !== "chat") {
      switchTab("chat");
    }
    showToast("Chat cleared.", "info");
  }

  els.clearChatBtn.addEventListener("click", clearChatHistory);
  if (els.sidebarClearChatBtn) {
    els.sidebarClearChatBtn.addEventListener("click", clearChatHistory);
  }

  // Ribbon Search Bar -> triggers Feature 1 independently from any tab
  els.ribbonSearchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = els.ribbonSearchInput.value.trim();
    if (!q) return;
    els.ribbonSearchInput.value = "";
    switchTab("chat");
    submitGeneralAssistant(q);
  });

  els.chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = els.chatInput.value.trim();
    if (!q) return;
    els.chatInput.value = "";
    els.chatInput.style.height = "auto";
    submitGeneralAssistant(q);
  });

  els.chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      els.chatForm.dispatchEvent(new Event("submit"));
    }
  });

  els.chatInput.addEventListener("input", () => {
    els.chatInput.style.height = "auto";
    els.chatInput.style.height = Math.min(els.chatInput.scrollHeight, 130) + "px";
  });

  async function submitGeneralAssistant(message, opts = {}) {
    const fromVoice = Boolean(opts.fromVoice);
    const welcome = document.getElementById("welcomeCard");
    if (welcome) welcome.remove();

    appendUserBubble(els.chatFeed, message);
    const historySnapshot = state.history.slice(-8);
    state.history.push({ role: "user", content: message });
    const loadingRow = appendBotLoading(els.chatFeed, "Searching & thinking...");

    try {
      const res = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: "",
          message,
          mode: "general",
          provider: state.aiProvider || "auto",
          history: historySnapshot,
        }),
      });
      const data = await res.json();
      loadingRow.remove();
      if (!res.ok) throw new Error(data.error || "Assistant request failed");
      if (data.reply) state.history.push({ role: "assistant", content: data.reply });
      const rendered = appendBotResponse(els.chatFeed, data);
      if (data.suggestions) renderSuggestions(data.suggestions);
      if (data.reply && fromVoice) {
        speakReply(data.reply, rendered?.speakBtn || null);
      }
    } catch (err) {
      loadingRow.remove();
      appendBotError(els.chatFeed, err.message);
    }
  }

  // ================= AI VOICE ASSISTANT (MIC ICON ONLY + TTS) =================
  const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  let activeRecognition = null;
  let activeMediaRecorder = null;
  let activeMediaStream = null;
  let recordedChunks = [];
  let activeSpeakBtn = null;

  const SPEAKER_ICON_SVG =
    '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>';
  const STOP_ICON_SVG =
    '<svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
  const COPY_SVG =
    '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
  const CHECK_SVG =
    '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>';

  function speechToPlainText(markdown) {
    return String(markdown || "")
      .replace(/```[\s\S]*?```/g, " Code is shown on screen. ")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, "$1")
      .replace(/https?:\/\/\S+/g, "")
      .replace(/[*_`#>|]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function pickPreferredVoice() {
    if (!("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    return (
      voices.find((v) => /en/i.test(v.lang) && /(natural|google|aria|guy|jenny|zira|david)/i.test(v.name)) ||
      voices.find((v) => /^en[-_]/i.test(v.lang)) ||
      voices[0] ||
      null
    );
  }

  function stopSpeaking() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    state.voiceSpeaking = false;
    if (activeSpeakBtn) {
      activeSpeakBtn.classList.remove("speaking");
      activeSpeakBtn.innerHTML = SPEAKER_ICON_SVG;
      activeSpeakBtn.title = "Listen";
      activeSpeakBtn = null;
    }
  }

  function speakReply(rawText, triggerBtn = null) {
    if (!("speechSynthesis" in window)) {
      showToast("Audio playback is not supported in this browser.", "error");
      return;
    }
    const clean = speechToPlainText(rawText);
    if (!clean) return;
    const wasSame = triggerBtn && activeSpeakBtn === triggerBtn && state.voiceSpeaking;
    stopSpeaking();
    if (wasSame) return;

    const utter = new SpeechSynthesisUtterance(clean.slice(0, 2200));
    const voice = pickPreferredVoice();
    if (voice) utter.voice = voice;
    utter.rate = 1.03;

    state.voiceSpeaking = true;
    if (triggerBtn) {
      activeSpeakBtn = triggerBtn;
      triggerBtn.classList.add("speaking");
      triggerBtn.innerHTML = STOP_ICON_SVG;
      triggerBtn.title = "Stop";
    }
    utter.onend = utter.onerror = () => {
      state.voiceSpeaking = false;
      if (triggerBtn) {
        triggerBtn.classList.remove("speaking");
        triggerBtn.innerHTML = SPEAKER_ICON_SVG;
        triggerBtn.title = "Listen";
      }
      if (activeSpeakBtn === triggerBtn) activeSpeakBtn = null;
    };
    window.speechSynthesis.speak(utter);
  }

  function setMicListeningUi(active) {
    state.voiceListening = active;
    [els.voiceMicBtn, els.chatVoiceMicBtn].forEach((btn) => {
      if (!btn) return;
      btn.classList.toggle("listening", active);
      btn.title = active ? "Listening... click to stop" : "Speak (Microphone)";
    });
  }

  function cleanupAudioStream() {
    if (activeMediaStream) {
      activeMediaStream.getTracks().forEach((t) => t.stop());
      activeMediaStream = null;
    }
    activeMediaRecorder = null;
  }

  async function startMediaRecorderFallback(targetInput) {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      showToast("Microphone input requires browser microphone support.", "error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      activeMediaStream = stream;
      recordedChunks = [];
      const recorder = new MediaRecorder(stream);
      activeMediaRecorder = recorder;
      recorder.ondataavailable = (ev) => {
        if (ev.data?.size > 0) recordedChunks.push(ev.data);
      };
      recorder.onstop = async () => {
        const blob = new Blob(recordedChunks, { type: recorder.mimeType || "audio/webm" });
        cleanupAudioStream();
        setMicListeningUi(false);
        try {
          const form = new FormData();
          form.append("audio", blob, "voice.webm");
          form.append("provider", state.aiProvider || "auto");
          const res = await fetch("/api/voice/transcribe", { method: "POST", body: form });
          const data = await res.json();
          if (!res.ok || !data.ok) throw new Error(data.error || "Transcription failed");
          targetInput.value = "";
          switchTab("chat");
          submitGeneralAssistant(data.text, { fromVoice: true });
        } catch (err) {
          showToast(err.message, "error");
        }
      };
      setMicListeningUi(true);
      recorder.start();
      showToast("Recording... click mic again to send.", "info");
    } catch (err) {
      cleanupAudioStream();
      setMicListeningUi(false);
      showToast(`Microphone error: ${err.message}`, "error");
    }
  }

  function stopVoiceListening() {
    if (activeRecognition) {
      try {
        activeRecognition.stop();
      } catch {
        // ignore
      }
      activeRecognition = null;
    }
    if (activeMediaRecorder && activeMediaRecorder.state !== "inactive") {
      activeMediaRecorder.stop();
      return;
    }
    cleanupAudioStream();
    setMicListeningUi(false);
  }

  function startVoiceListening(targetInput) {
    if (state.voiceSpeaking) stopSpeaking();
    if (state.voiceListening) {
      stopVoiceListening();
      return;
    }
    if (!SpeechRecognitionCtor) {
      startMediaRecorderFallback(targetInput);
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    activeRecognition = recognition;
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;

    let finalTranscript = "";
    let latestTranscript = "";
    let fellBack = false;

    recognition.onstart = () => setMicListeningUi(true);
    recognition.onresult = (event) => {
      let interim = "";
      finalTranscript = "";
      for (let i = 0; i < event.results.length; i++) {
        const piece = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) finalTranscript += piece + " ";
        else interim += piece;
      }
      latestTranscript = (finalTranscript + interim).trim();
      targetInput.value = latestTranscript;
    };
    recognition.onerror = (event) => {
      activeRecognition = null;
      setMicListeningUi(false);
      const code = event?.error || "";
      if ((code === "network" || code === "service-not-allowed") && !fellBack) {
        fellBack = true;
        startMediaRecorderFallback(targetInput);
        return;
      }
      if (code === "not-allowed") {
        showToast("Allow microphone access in your browser to use voice search.", "error");
      } else if (code && code !== "aborted" && code !== "no-speech") {
        showToast(`Speech error: ${code}`, "error");
      }
    };
    recognition.onend = () => {
      activeRecognition = null;
      if (fellBack) return;
      setMicListeningUi(false);
      const spoken = (finalTranscript || latestTranscript).trim();
      if (spoken) {
        targetInput.value = "";
        switchTab("chat");
        submitGeneralAssistant(spoken, { fromVoice: true });
      }
    };

    try {
      recognition.start();
    } catch {
      activeRecognition = null;
      startMediaRecorderFallback(targetInput);
    }
  }

  els.voiceMicBtn.addEventListener("click", () => startVoiceListening(els.ribbonSearchInput));
  els.chatVoiceMicBtn.addEventListener("click", () => startVoiceListening(els.chatInput));

  // ================= SHARED CHAT / RESULT BUBBLES =================
  function appendUserBubble(container, text) {
    const row = document.createElement("div");
    row.className = "msg-row user";
    row.innerHTML = `
      <div class="msg-header"><span>You</span><span class="avatar-dot avatar-user">U</span></div>
      <div class="msg-bubble"><div class="msg-text">${escapeHtml(text)}</div></div>
    `;
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
  }

  function appendBotLoading(container, msg) {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `
      <div class="msg-header"><span class="avatar-dot avatar-ai">RA</span><span>RENSERI AI ASSISTANT</span></div>
      <div class="msg-bubble"><div class="msg-text" style="color:var(--text-muted)">${escapeHtml(msg)}</div></div>
    `;
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
    return row;
  }

  function appendBotError(container, msg) {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `
      <div class="msg-header"><span class="avatar-dot avatar-ai">RA</span><span>RENSERI AI ASSISTANT</span></div>
      <div class="msg-bubble"><div class="error-banner">${escapeHtml(msg)}</div></div>
    `;
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
  }

  function formatEngineBadge(engine) {
    const e = String(engine || "").trim();
    if (!e) return "";
    if (e.includes("gemini")) return `Gemini (${e})`;
    if (e.includes("groq")) return `Groq (${e})`;
    if (e === "web_fetch") return "Live Google & Web";
    if (e === "local") return "Local";
    return e;
  }

  function appendBotResponse(container, data) {
    const row = document.createElement("div");
    row.className = "msg-row bot";

    const head = document.createElement("div");
    head.className = "msg-header";
    const engineLabel = formatEngineBadge(data.engine);
    head.innerHTML = `
      <span class="avatar-dot avatar-ai">RA</span>
      <span>RENSERI AI ASSISTANT</span>
      ${engineLabel ? `<span class="engine-pill">${escapeHtml(engineLabel)}</span>` : ""}
    `;

    let speakBtn = null;
    if (data.reply) {
      speakBtn = document.createElement("button");
      speakBtn.type = "button";
      speakBtn.className = "msg-speak-btn";
      speakBtn.title = "Listen";
      speakBtn.setAttribute("aria-label", "Listen");
      speakBtn.innerHTML = SPEAKER_ICON_SVG;
      speakBtn.addEventListener("click", () => speakReply(data.reply, speakBtn));
      head.appendChild(speakBtn);

      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "msg-copy-btn";
      copyBtn.title = "Copy reply";
      copyBtn.setAttribute("aria-label", "Copy reply");
      copyBtn.innerHTML = COPY_SVG;
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(data.reply);
          copyBtn.classList.add("copied");
          copyBtn.innerHTML = CHECK_SVG;
          showToast("Copied to clipboard.", "success");
          setTimeout(() => {
            copyBtn.classList.remove("copied");
            copyBtn.innerHTML = COPY_SVG;
          }, 1400);
        } catch {
          showToast("Clipboard unavailable.", "info");
        }
      });
      head.appendChild(copyBtn);
    }

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    // Render Topic Card with Images at top of answer if available
    if (data.topic_card && (data.topic_card.description || data.topic_card.image_url)) {
      const tc = data.topic_card;
      const card = document.createElement("div");
      card.className = "topic-card";

      if (tc.image_url && /^https?:\/\//i.test(tc.image_url)) {
        const media = document.createElement("div");
        media.className = "topic-card-media";
        const img = document.createElement("img");
        img.className = "topic-card-img";
        img.src = tc.image_url;
        img.alt = tc.title || "Topic image";
        img.loading = "lazy";
        img.addEventListener("error", () => media.remove());
        media.appendChild(img);
        card.appendChild(media);
      }

      const body = document.createElement("div");
      body.className = "topic-card-body";
      const safeTitle = escapeHtml(tc.title || "");
      const safeSub = tc.subtitle ? `<div class="topic-card-sub">${escapeHtml(tc.subtitle)}</div>` : "";
      const safeDesc = tc.description ? `<p class="topic-card-desc">${escapeHtml(tc.description)}</p>` : "";
      const safeLink =
        tc.url && /^https?:\/\//i.test(tc.url)
          ? `<a class="topic-card-link" href="${escapeHtml(tc.url)}" target="_blank" rel="noopener noreferrer">Read more on ${escapeHtml(tc.source || "Wikipedia")} &nearr;</a>`
          : "";

      // Thumbnail gallery for multi-image topics
      let galleryHtml = "";
      if (Array.isArray(tc.images) && tc.images.length > 1) {
        const otherImgs = tc.images.filter((im) => im?.url && im.url !== tc.image_url).slice(0, 4);
        if (otherImgs.length) {
          galleryHtml = `<div class="topic-gallery">` +
            otherImgs.map((im) => `
              <a class="topic-gallery-item" href="${escapeHtml(im.url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(im.caption || 'View full image')}">
                <img src="${escapeHtml(im.url)}" alt="${escapeHtml(im.caption || 'Topic photo')}" loading="lazy" />
              </a>
            `).join("") +
          `</div>`;
        }
      }

      body.innerHTML = `<div class="topic-card-title">${safeTitle}</div>${safeSub}${safeDesc}${safeLink}${galleryHtml}`;
      card.appendChild(body);
      bubble.appendChild(card);
    }

    const textDiv = document.createElement("div");
    textDiv.className = "msg-text md-reply";
    textDiv.innerHTML = formatMarkdownReply(data.reply || "");
    bubble.appendChild(textDiv);

    const showSourceChips = Array.isArray(data.sources) && data.sources.length > 0;
    if (showSourceChips) {
      const srcWrap = document.createElement("div");
      srcWrap.className = "sources-wrap";
      const srcTitle = document.createElement("div");
      srcTitle.className = "sources-label";
      srcTitle.textContent = `Sources (${data.sources.length})`;
      const srcList = document.createElement("div");
      srcList.className = "sources-list";
      data.sources.forEach((s) => {
        if (!s?.url) return;
        const link = document.createElement("a");
        link.className = "source-chip";
        link.href = s.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        const tag = s.source ? `<span class="source-tag">${escapeHtml(s.source)}</span>` : "";
        link.innerHTML = `${tag}<span>${escapeHtml(s.title || s.url)}</span>`;
        srcList.appendChild(link);
      });
      if (srcList.children.length) {
        srcWrap.append(srcTitle, srcList);
        bubble.appendChild(srcWrap);
      }
    }

    if (Array.isArray(data.quick_actions) && data.quick_actions.length) {
      const qaRow = document.createElement("div");
      qaRow.className = "quick-action-row";
      data.quick_actions.forEach((qa) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = qa.action === "upload" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm";
        btn.textContent = qa.label;
        btn.addEventListener("click", () => {
          if (qa.action === "upload") switchTab("upload");
          else if (qa.action === "keys") openAiModal();
          else if (qa.action === "sample") loadSampleDataset(qa.sample_id);
        });
        qaRow.appendChild(btn);
      });
      bubble.appendChild(qaRow);
    }

    row.append(head, bubble);
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
    return { row, speakBtn };
  }

  // ================= FEATURE 5: DATASET SUMMARY =================
  function renderDatasetSummary(data) {
    const container = els.summaryContent;
    container.innerHTML = "";

    const rep = data.report;
    const profiles = data.profiles || [];

    // ---- KPI row ----
    const totalCells = rep.cleaned_rows * rep.cleaned_cols;
    const nullPct = totalCells > 0 ? ((rep.cleaned_missing_cells / totalCells) * 100).toFixed(1) : "0.0";
    const typeCounts = { numeric: 0, text: 0, date: 0, boolean: 0, other: 0 };
    profiles.forEach((p) => {
      const t = p.semantic_type || "other";
      typeCounts[t] = (typeCounts[t] || 0) + 1;
    });
    const dupPct = rep.original_rows > 0
      ? ((rep.duplicates_removed / rep.original_rows) * 100).toFixed(1)
      : "0.0";

    const kpiRow = document.createElement("div");
    kpiRow.className = "summary-kpi-row";
    kpiRow.innerHTML = `
      <div class="summary-kpi">
        <div class="summary-kpi-label">Quality Score</div>
        <div class="summary-kpi-value">${rep.quality_score_after}%</div>
        <div class="summary-kpi-sub">Before: ${rep.quality_score_before}%</div>
      </div>
      <div class="summary-kpi">
        <div class="summary-kpi-label">Total Rows</div>
        <div class="summary-kpi-value">${rep.cleaned_rows.toLocaleString()}</div>
        <div class="summary-kpi-sub">Original: ${rep.original_rows.toLocaleString()}</div>
      </div>
      <div class="summary-kpi">
        <div class="summary-kpi-label">Columns</div>
        <div class="summary-kpi-value">${rep.cleaned_cols}</div>
        <div class="summary-kpi-sub">Numeric: ${typeCounts.numeric} · Text: ${typeCounts.text}</div>
      </div>
      <div class="summary-kpi">
        <div class="summary-kpi-label">Missing Cells</div>
        <div class="summary-kpi-value">${rep.cleaned_missing_cells}</div>
        <div class="summary-kpi-sub">${nullPct}% null rate</div>
      </div>
      <div class="summary-kpi">
        <div class="summary-kpi-label">Duplicates Removed</div>
        <div class="summary-kpi-value">${rep.duplicates_removed}</div>
        <div class="summary-kpi-sub">${dupPct}% of original</div>
      </div>
    `;
    container.appendChild(kpiRow);

    // ---- Insight chips ----
    const chips = [];
    if (rep.quality_score_after >= 90) chips.push({ cls: "chip-good", icon: "✅", text: "High quality dataset — ready to analyze" });
    else if (rep.quality_score_after >= 70) chips.push({ cls: "chip-info", icon: "ℹ️", text: `Moderate quality (${rep.quality_score_after}%) — some nulls remain` });
    else chips.push({ cls: "chip-warn", icon: "⚠️", text: `Low quality (${rep.quality_score_after}%) — consider cleaning` });

    if (typeCounts.numeric > 0) chips.push({ cls: "chip-info", icon: "🔢", text: `${typeCounts.numeric} numeric column${typeCounts.numeric > 1 ? "s" : ""} — suitable for aggregation` });
    if (typeCounts.date > 0) chips.push({ cls: "chip-info", icon: "📅", text: `${typeCounts.date} date column${typeCounts.date > 1 ? "s" : ""} — time-series analysis possible` });
    if (typeCounts.text > 0) chips.push({ cls: "chip-info", icon: "🔤", text: `${typeCounts.text} text column${typeCounts.text > 1 ? "s" : ""} — categorical or free-form` });
    if (rep.duplicates_removed > 0) chips.push({ cls: "chip-warn", icon: "🗑️", text: `${rep.duplicates_removed} duplicate rows removed automatically` });
    if (rep.empty_cols_removed > 0) chips.push({ cls: "chip-warn", icon: "🗂️", text: `${rep.empty_cols_removed} empty column${rep.empty_cols_removed > 1 ? "s" : ""} removed` });
    if (parseFloat(nullPct) > 20) chips.push({ cls: "chip-warn", icon: "⚠️", text: `High null rate (${nullPct}%) — imputation may help` });
    if (rep.cleaned_rows > 50000) chips.push({ cls: "chip-info", icon: "📦", text: `Large dataset (${rep.cleaned_rows.toLocaleString()} rows) — queries will be fast via SQL` });

    // High-null column warnings from report
    (rep.warnings || []).forEach((w) => {
      chips.push({ cls: "chip-warn", icon: "⚠️", text: w });
    });

    const insightPanel = document.createElement("div");
    insightPanel.className = "summary-insights-panel";
    insightPanel.innerHTML = `
      <div class="summary-insights-title">💡 Auto Insights</div>
      <div class="summary-insight-chips">
        ${chips.map((c) => `<span class="summary-insight-chip ${c.cls}">${c.icon} ${escapeHtml(c.text)}</span>`).join("")}
      </div>
    `;
    container.appendChild(insightPanel);

    // ---- Column stats table ----
    const colPanel = document.createElement("div");
    colPanel.className = "summary-col-panel";
    colPanel.innerHTML = `<div class="summary-col-title">📋 Column Statistics</div>`;

    const table = document.createElement("table");
    table.className = "summary-col-table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>#</th>
          <th>Column</th>
          <th>Type</th>
          <th>Non-Null</th>
          <th>Null %</th>
          <th>Unique</th>
          <th>Sample Values</th>
        </tr>
      </thead>
    `;
    const tbody = document.createElement("tbody");

    profiles.forEach((p, i) => {
      const nullCount = p.null_count ?? 0;
      const total = rep.cleaned_rows || 1;
      const colNullPct = ((nullCount / total) * 100).toFixed(1);
      const nonNull = total - nullCount;
      const fillPct = Math.max(0, Math.min(100, 100 - parseFloat(colNullPct)));
      const barCls = parseFloat(colNullPct) >= 30 ? "bar-danger" : parseFloat(colNullPct) >= 10 ? "bar-warn" : "";
      const typeCls = `type-${p.semantic_type || "other"}`;
      const sampleVals = (p.sample_values || p.top_values || []).slice(0, 3).map((v) => `<code>${escapeHtml(String(v ?? ""))}</code>`).join(", ");

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="color:var(--text-muted)">${i + 1}</td>
        <td style="font-weight:600">${escapeHtml(p.name)}</td>
        <td><span class="summary-type-badge ${typeCls}">${escapeHtml(p.semantic_type || "other")}</span></td>
        <td>${nonNull.toLocaleString()}</td>
        <td>
          <div class="null-bar-wrap">
            <div class="null-bar-bg"><div class="null-bar-fill ${barCls}" style="width:${colNullPct}%"></div></div>
            <span style="font-size:11px;color:var(--text-muted)">${colNullPct}%</span>
          </div>
        </td>
        <td>${p.unique_count ?? "—"}</td>
        <td style="color:var(--text-muted)">${sampleVals || "—"}</td>
      `;
      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    colPanel.appendChild(table);
    container.appendChild(colPanel);

    // ---- Exploratory Data Analysis (EDA) Panels ----
    const eda = data.eda || {};

    // 1. Numeric Summary Statistics (Mean, Std, Min, 25%, Median, 75%, Max, Skewness)
    if (Array.isArray(eda.numeric_stats) && eda.numeric_stats.length) {
      const numPanel = document.createElement("div");
      numPanel.className = "summary-col-panel";
      numPanel.innerHTML = `
        <div class="summary-col-title">📐 Exploratory Data Analysis: Five-Number &amp; Distribution Stats</div>
        <div class="table-scroll">
          <table class="summary-col-table">
            <thead>
              <tr>
                <th>Numeric Column</th>
                <th>Count</th>
                <th>Mean</th>
                <th>Std Dev</th>
                <th>Min</th>
                <th>25%</th>
                <th>Median (50%)</th>
                <th>75%</th>
                <th>Max</th>
                <th>Skew</th>
              </tr>
            </thead>
            <tbody>
              ${eda.numeric_stats.map((s) => `
                <tr>
                  <td style="font-weight:600">${escapeHtml(s.column)}</td>
                  <td>${s.count.toLocaleString()}</td>
                  <td>${s.mean.toLocaleString()}</td>
                  <td>${s.std.toLocaleString()}</td>
                  <td>${s.min.toLocaleString()}</td>
                  <td>${s.q25.toLocaleString()}</td>
                  <td style="font-weight:700;color:var(--accent)">${s.median.toLocaleString()}</td>
                  <td>${s.q75.toLocaleString()}</td>
                  <td>${s.max.toLocaleString()}</td>
                  <td style="color:${Math.abs(s.skew) > 1 ? 'var(--warning)' : 'var(--text-muted)'}">${s.skew}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
      container.appendChild(numPanel);
    }

    // 2. Correlation Matrix Findings
    if (Array.isArray(eda.correlations) && eda.correlations.length) {
      const corrPanel = document.createElement("div");
      corrPanel.className = "summary-insights-panel";
      corrPanel.innerHTML = `
        <div class="summary-insights-title">🔗 EDA: Statistical Correlation Pairs (Pearson r)</div>
        <div class="summary-insight-chips">
          ${eda.correlations.map((c) => {
            const isStrong = Math.abs(c.correlation) >= 0.7;
            const chipClass = isStrong ? (c.correlation > 0 ? "chip-good" : "chip-warn") : "chip-info";
            return `<span class="summary-insight-chip ${chipClass}">
              <strong>${escapeHtml(c.col1)}</strong> ↔ <strong>${escapeHtml(c.col2)}</strong>:
              <code>r = ${c.correlation}</code> (${escapeHtml(c.strength)})
            </span>`;
          }).join("")}
        </div>
      `;
      container.appendChild(corrPanel);
    }

    // 3. Categorical Distributions
    if (Array.isArray(eda.categorical_breakdown) && eda.categorical_breakdown.length) {
      const catPanel = document.createElement("div");
      catPanel.className = "summary-col-panel";
      catPanel.innerHTML = `<div class="summary-col-title">📊 EDA: Top Category Concentrations</div>`;
      const catGrid = document.createElement("div");
      catGrid.className = "custom-grid";
      eda.categorical_breakdown.forEach((cb) => {
        const cCard = document.createElement("div");
        cCard.className = "feature-tile";
        cCard.innerHTML = `
          <div class="ft-title">${escapeHtml(cb.column)} <span style="font-size:11px;color:var(--text-muted);font-weight:normal">(${cb.distinct_count} unique)</span></div>
          <div style="display:flex;flex-direction:column;gap:5px;margin-top:8px">
            ${(cb.top_categories || []).map((cat) => `
              <div style="font-size:12px;display:flex;justify-content:space-between;align-items:center">
                <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px" title="${escapeHtml(cat.label)}">${escapeHtml(cat.label)}</span>
                <span style="font-size:11px;color:var(--text-muted)">${cat.count} (${cat.pct}%)</span>
              </div>
              <div class="null-bar-bg" style="height:4px"><div class="null-bar-fill" style="width:${cat.pct}%"></div></div>
            `).join("")}
          </div>
        `;
        catGrid.appendChild(cCard);
      });
      catPanel.appendChild(catGrid);
      container.appendChild(catPanel);
    }

    // ---- Column mapping (if columns were renamed) ----
    const mapping = rep.column_mapping || {};
    const renames = Object.entries(mapping).filter(([k, v]) => k !== v);
    if (renames.length > 0) {
      const mapPanel = document.createElement("div");
      mapPanel.className = "summary-insights-panel";
      mapPanel.innerHTML = `
        <div class="summary-insights-title">🔄 Column Renames Applied</div>
        <div class="summary-insight-chips">
          ${renames.map(([orig, norm]) =>
            `<span class="summary-insight-chip chip-info"><code>${escapeHtml(orig)}</code> → <code>${escapeHtml(norm)}</code></span>`
          ).join("")}
        </div>
      `;
      container.appendChild(mapPanel);
    }
  }

  // ================= FEATURE 2: UPLOAD DATASET =================
  function getCleaningOptions() {
    const roundVal = els.roundDecimalsSelect.value;
    const dropCols = Array.from(
      els.dropColsList.querySelectorAll('input[type="checkbox"]:checked')
    ).map((cb) => cb.value);

    return {
      strategy: els.strategySelect.value,
      drop_duplicates: els.optDedup.checked,
      parse_dates: els.optDates.checked,
      parse_numeric: els.optNumeric.checked,
      normalize_columns: els.optCols.checked,
      trim_strings: true,
      fill_missing:
        els.strategySelect.value === "drop_rows"
          ? "drop_rows"
          : els.strategySelect.value === "keep_nulls" || els.strategySelect.value === "minimal"
          ? "none"
          : "smart",
      text_case: els.textCaseSelect.value || "none",
      fill_text_value: els.fillTextInput.value,
      round_decimals: roundVal === "none" ? null : Number(roundVal),
      drop_columns: dropCols,
      find_text: els.findTextInput.value || "",
      replace_text: els.replaceTextInput.value || "",
      replace_column: els.replaceColSelect.value || "",
      // Power Query style transforms
      dtype_column: (els.dtypeColSelect && els.dtypeColSelect.value) || "",
      dtype_target: (els.dtypeTargetSelect && els.dtypeTargetSelect.value) || "",
      split_column: (els.splitColSelect && els.splitColSelect.value) || "",
      split_delimiter: (els.splitDelimInput && els.splitDelimInput.value) || "",
      split_max_parts: parseInt((els.splitMaxSelect && els.splitMaxSelect.value) || "2", 10),
      extract_column: (els.extractColSelect && els.extractColSelect.value) || "",
      extract_mode: (els.extractModeSelect && els.extractModeSelect.value) || "",
      extract_param: (els.extractParamInput && els.extractParamInput.value) || "",
      extract_output_col: (els.extractOutputCol && els.extractOutputCol.value) || "",
      // Extended Power Query transforms
      filter_column: (els.filterColSelect && els.filterColSelect.value) || "",
      filter_condition: (els.filterCondSelect && els.filterCondSelect.value) || "",
      filter_value: (els.filterValInput && els.filterValInput.value) || "",
      sort_column: (els.sortColSelect && els.sortColSelect.value) || "",
      sort_direction: (els.sortDirSelect && els.sortDirSelect.value) || "asc",
      rename_column: (els.renameColSelect && els.renameColSelect.value) || "",
      rename_to: (els.renameToInput && els.renameToInput.value) || "",
      fill_direction_col: (els.fillDirColSelect && els.fillDirColSelect.value) || "",
      fill_direction: (els.fillDirSelect && els.fillDirSelect.value) || "",
    };
  }

  els.dropzone.addEventListener("click", () => els.fileInput.click());
  els.dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      els.fileInput.click();
    }
  });
  els.dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    els.dropzone.classList.add("dragover");
  });
  els.dropzone.addEventListener("dragleave", () => els.dropzone.classList.remove("dragover"));
  els.dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    els.dropzone.classList.remove("dragover");
    const file = e.dataTransfer?.files?.[0];
    if (file) uploadFile(file);
  });
  els.fileInput.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
    els.fileInput.value = "";
  });

  async function uploadFile(file) {
    els.uploadStatusText.textContent = `Uploading & cleaning ${file.name}...`;
    const form = new FormData();
    form.append("file", file);
    const opts = getCleaningOptions();
    Object.entries(opts).forEach(([k, v]) => {
      if (v !== null && v !== undefined) {
        form.append(k, Array.isArray(v) ? v.join(",") : String(v));
      }
    });

    try {
      const res = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");
      onDatasetReady(data, false);
    } catch (err) {
      els.uploadStatusText.textContent = "Upload failed — try another file";
      showToast(err.message, "error");
    }
  }

  els.submitPasteBtn.addEventListener("click", async () => {
    const text = (els.pasteDatasetText.value || "").trim();
    const name = (els.pasteDatasetName.value || "").trim() || "user_dataset";
    const format = els.pasteDatasetFormat.value || "auto";
    if (!text) {
      showToast("Paste CSV, TSV, or JSON rows first.", "error");
      return;
    }
    els.submitPasteBtn.disabled = true;
    els.submitPasteBtn.textContent = "Loading...";
    try {
      const res = await fetch("/api/dataset/from-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, format, text, options: getCleaningOptions() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to load dataset");
      onDatasetReady(data, false);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      els.submitPasteBtn.disabled = false;
      els.submitPasteBtn.textContent = "Load Pasted Dataset";
    }
  });

  async function loadSampleCatalog() {
    try {
      const res = await fetch("/api/samples");
      const data = await res.json();
      els.sampleButtons.innerHTML = "";
      (data.samples || []).forEach((s) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "sample-btn";
        btn.textContent = s.name;
        btn.title = s.description;
        btn.addEventListener("click", () => loadSampleDataset(s.id));
        els.sampleButtons.appendChild(btn);
      });
    } catch (err) {
      console.error("Failed to fetch samples:", err);
    }
  }

  async function loadSampleDataset(sampleId) {
    els.uploadStatusText.textContent = "Cleaning sample dataset...";
    try {
      const res = await fetch(`/api/samples/${encodeURIComponent(sampleId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(getCleaningOptions()),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Sample load failed");
      onDatasetReady(data, false);
    } catch (err) {
      els.uploadStatusText.textContent = "Upload failed";
      showToast(err.message, "error");
    }
  }

  function onDatasetReady(data, isReclean) {
    state.sessionId = data.session_id;
    state.dataset = data;
    state.dashboard = null;

    const rep = data.report;
    els.uploadStatusText.textContent = `Loaded ${data.filename} (${rep.cleaned_rows} rows cleaned, ${rep.quality_score_after}% quality)`;
    els.cleaningMetaBadge.textContent = `${data.filename} · Table: ${data.table_name} · Quality ${rep.quality_score_before}% → ${rep.quality_score_after}%`;

    renderSidebarDataset();
    renderInspector(data);
    renderDatasetSummary(data);
    populateCustomCleanControls(data);

    if (!isReclean) {
      fetchAndRenderDashboard({ prompt: "create analytics dashboard" });
      switchTab("dashboard");
    }
    showToast(`Dataset '${data.filename}' cleaned & attached!`, "success");
  }

  // ================= FEATURE 3: DATA & CLEANING + EXPORT + SQL =================
  function triggerExport(fmt) {
    if (!state.sessionId) {
      showToast("Attach a dataset in Upload Dataset first.", "info");
      return;
    }
    window.location.href = `/api/dataset/${state.sessionId}/export?format=${fmt}`;
  }
  els.exportCsvBtn.addEventListener("click", () => triggerExport("csv"));
  els.exportXlsxBtn.addEventListener("click", () => triggerExport("xlsx"));
  els.exportDbBtn.addEventListener("click", () => triggerExport("sqlite"));

  function renderInspector(data) {
    const rep = data.report;
    const container = els.inspectorContent;
    container.innerHTML = "";

    const metrics = document.createElement("div");
    metrics.className = "metrics-grid";
    metrics.innerHTML = `
      <div class="metric-card">
        <div class="metric-label">Quality Score</div>
        <div class="metric-value" style="color:var(--success)">${rep.quality_score_after}%</div>
        <div class="metric-sub">Before: ${rep.quality_score_before}%</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Rows</div>
        <div class="metric-value">${rep.cleaned_rows}</div>
        <div class="metric-sub">Original: ${rep.original_rows} (${rep.duplicates_removed} dupes removed)</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Columns</div>
        <div class="metric-value">${rep.cleaned_cols}</div>
        <div class="metric-sub">Original: ${rep.original_cols} (${rep.empty_cols_removed} empty dropped)</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Missing Cells</div>
        <div class="metric-value">${rep.cleaned_missing_cells}</div>
        <div class="metric-sub">Before: ${rep.original_missing_cells}</div>
      </div>
    `;
    container.appendChild(metrics);

    const auditPanel = document.createElement("div");
    auditPanel.className = "panel";
    auditPanel.innerHTML = `<div class="panel-header"><h2>Cleaning Audit Log</h2></div>`;
    const auditList = document.createElement("div");
    auditList.className = "audit-list";
    if (!rep.actions?.length) {
      auditList.innerHTML = `<div class="audit-item">No formatting issues detected.</div>`;
    } else {
      rep.actions.forEach((a) => {
        const div = document.createElement("div");
        div.className = "audit-item";
        div.textContent = a.description;
        auditList.appendChild(div);
      });
    }
    (rep.warnings || []).forEach((w) => {
      const div = document.createElement("div");
      div.className = "audit-item";
      div.style.borderLeftColor = "var(--warning)";
      div.textContent = `Warning: ${w}`;
      auditList.appendChild(div);
    });
    auditPanel.appendChild(auditList);
    container.appendChild(auditPanel);

    const prevPanel = document.createElement("div");
    prevPanel.className = "panel";
    const prevHead = document.createElement("div");
    prevHead.className = "panel-header";
    prevHead.innerHTML = `<h2>Data Preview (Before vs After Cleaning)</h2>`;
    const toggleGroup = document.createElement("div");
    toggleGroup.style.display = "flex";
    toggleGroup.style.gap = "6px";
    const btnCleaned = document.createElement("button");
    btnCleaned.type = "button";
    btnCleaned.textContent = `Cleaned (${data.cleaned_preview.total_rows} rows)`;
    const btnRaw = document.createElement("button");
    btnRaw.type = "button";
    btnRaw.textContent = `Raw (${data.raw_preview.total_rows} rows)`;
    const tableHolder = document.createElement("div");

    function renderPreviewTable() {
      const src = state.previewMode === "cleaned" ? data.cleaned_preview : data.raw_preview;
      btnCleaned.className = `btn btn-sm ${state.previewMode === "cleaned" ? "btn-primary" : "btn-secondary"}`;
      btnRaw.className = `btn btn-sm ${state.previewMode === "raw" ? "btn-primary" : "btn-secondary"}`;
      tableHolder.innerHTML = "";
      tableHolder.appendChild(buildSortableTable(src.columns, src.rows).element);
    }

    btnCleaned.addEventListener("click", () => {
      state.previewMode = "cleaned";
      renderPreviewTable();
    });
    btnRaw.addEventListener("click", () => {
      state.previewMode = "raw";
      renderPreviewTable();
    });

    toggleGroup.append(btnCleaned, btnRaw);
    prevHead.appendChild(toggleGroup);
    prevPanel.append(prevHead, tableHolder);
    renderPreviewTable();
    container.appendChild(prevPanel);
  }

  // ================= FEATURE 4: DASHBOARD & DATASET QUERIES =================
  els.dashBuildAutoBtn.addEventListener("click", () => {
    if (!state.sessionId) {
      showToast("Attach a dataset in Upload Dataset first.", "info");
      return;
    }
    els.dashQueryOutput.innerHTML = "";
    fetchAndRenderDashboard({ prompt: "create analytics dashboard" });
  });

  els.dashPromptForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const prompt = els.dashPromptInput.value.trim();
    if (!prompt) return;
    if (!state.sessionId) {
      showToast("Attach a dataset in Upload Dataset first.", "info");
      return;
    }

    if (/\bdashboard\b/i.test(prompt)) {
      await fetchAndRenderDashboard({ prompt });
      showToast("Updated dashboard from your prompt.", "success");
      return;
    }

    // Execute dataset query / build chart on the attached dataset (separate from Feature 1)
    els.dashQueryOutput.innerHTML = `<div class="dash-insight-card">Querying attached dataset...</div>`;
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          message: prompt,
          mode: "dataset",
          provider: state.aiProvider || "auto",
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Dataset query failed");

      if (data.type === "dashboard" && data.dashboard) {
        els.dashQueryOutput.innerHTML = "";
        state.dashboard = data.dashboard;
        renderDashboardTab(data.dashboard);
        return;
      }

      const card = document.createElement("div");
      card.className = "dash-insight-card";
      const replyDiv = document.createElement("div");
      replyDiv.className = "md-reply";
      replyDiv.innerHTML = formatMarkdownReply(data.reply || "");
      card.appendChild(replyDiv);
      if (data.sql) {
        card.appendChild(createEditableSqlBox(data.sql, data.engine || "sql", card));
      }
      const resHolder = document.createElement("div");
      card.appendChild(resHolder);
      if (data.result) {
        renderResultInto(resHolder, data.result, data.chart);
      }
      els.dashQueryOutput.innerHTML = "";
      els.dashQueryOutput.appendChild(card);
    } catch (err) {
      els.dashQueryOutput.innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
    }
  });

  async function fetchAndRenderDashboard(body) {
    if (!state.sessionId) return;
    els.dashboardContent.innerHTML = `<div class="empty-state">Building dashboard...</div>`;
    try {
      const res = await fetch("/api/dashboard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId, ...body }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Dashboard generation failed");
      state.dashboard = data;
      renderDashboardTab(data);
    } catch (err) {
      els.dashboardContent.innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
    }
  }

  function renderDashboardTab(dash) {
    const container = els.dashboardContent;
    container.innerHTML = "";

    const headerPanel = document.createElement("div");
    headerPanel.className = "dash-header-card";

    const left = document.createElement("div");
    left.innerHTML = `
      <h2 style="margin:0 0 4px;font-size:18px">${escapeHtml(dash.title)}</h2>
      <div class="hint">${escapeHtml(dash.subtitle)}</div>
    `;

    const controls = document.createElement("div");
    controls.className = "dash-controls";

    // Multi-Slicer interactive controls (Guaranteed at least 2 slicers)
    const slicers = Array.isArray(dash.slicers) && dash.slicers.length
      ? dash.slicers
      : (Array.isArray(dash.filter_options) ? dash.filter_options : []);

    const activeFilters = dash.active_filters || (dash.active_filter ? { [dash.active_filter.column]: dash.active_filter.value } : {});

    if (slicers.length) {
      slicers.forEach((slicer, idx) => {
        if (!slicer.values || !slicer.values.length) return;
        const sel = document.createElement("select");
        sel.className = "dash-filter-select";
        sel.setAttribute("aria-label", `Slicer: ${slicer.label || slicer.column}`);

        const allOpt = document.createElement("option");
        allOpt.value = "";
        allOpt.textContent = `${slicer.label || slicer.column}: All`;
        sel.appendChild(allOpt);

        slicer.values.forEach((v) => {
          const opt = document.createElement("option");
          opt.value = v;
          opt.textContent = `${v}`;
          if (activeFilters[slicer.column] === String(v)) opt.selected = true;
          sel.appendChild(opt);
        });

        sel.addEventListener("change", () => {
          const updatedFilters = { ...activeFilters };
          if (sel.value) {
            updatedFilters[slicer.column] = sel.value;
          } else {
            delete updatedFilters[slicer.column];
          }
          fetchAndRenderDashboard({
            prompt: dash.prompt || "dashboard",
            filters: updatedFilters,
          });
        });
        controls.appendChild(sel);
      });
    }

    if (Object.keys(activeFilters).length > 0) {
      const resetBtn = document.createElement("button");
      resetBtn.type = "button";
      resetBtn.className = "btn btn-secondary btn-sm";
      resetBtn.textContent = "Reset Slicers";
      resetBtn.addEventListener("click", () => fetchAndRenderDashboard({ prompt: dash.prompt || "dashboard", filters: {} }));
      controls.appendChild(resetBtn);
    }

    headerPanel.append(left, controls);
    container.appendChild(headerPanel);

    // 1. KPI Cards (At least 4)
    if (Array.isArray(dash.kpis) && dash.kpis.length) {
      container.appendChild(renderKpiStrip(dash.kpis));
    }

    // 2. Charts Grid (At least 4)
    if (Array.isArray(dash.charts) && dash.charts.length) {
      const grid = document.createElement("div");
      grid.className = "dash-charts-grid";
      dash.charts.forEach((c) => grid.appendChild(renderDashboardChartCard(c)));
      container.appendChild(grid);
    }

    // 3. Top Records Sample Table
    if (dash.top_table?.columns?.length) {
      const tblPanel = document.createElement("div");
      tblPanel.className = "panel";
      const head = document.createElement("div");
      head.className = "panel-header";
      head.innerHTML = `<h2>${escapeHtml(dash.top_table.title)}</h2>`;
      tblPanel.append(head, buildSortableTable(dash.top_table.columns, dash.top_table.rows).element);
      container.appendChild(tblPanel);
    }

    // 4. Executive Analytical Report & Strategic Recommendations (Generated after dashboard)
    if (dash.insights_report) {
      container.appendChild(renderExecutiveReport(dash.insights_report));
    }
  }

  function renderExecutiveReport(report) {
    const card = document.createElement("div");
    card.className = "panel exec-report-card";

    const summary = report.summary || {};
    const perf = report.performance_report || {};
    const topP = perf.top_performer || {};
    const focusP = perf.needs_focus || {};

    const head = document.createElement("div");
    head.className = "exec-report-header";
    head.innerHTML = `
      <div class="exec-title-row">
        <div>
          <h2 class="exec-main-title">${escapeHtml(report.title || "Business Performance & Executive Report")}</h2>
          <p class="exec-sub-title">${escapeHtml(summary.headline || report.subtitle || "Performance analysis, department focus, and strategic recommendations.")}</p>
        </div>
        ${summary.status ? `<span class="badge ${summary.status.toLowerCase().includes('increased') ? 'badge-good' : (summary.status.toLowerCase().includes('decreased') ? 'badge-warn' : 'badge-accent')}">${escapeHtml(summary.status)}</span>` : ""}
      </div>
    `;
    card.appendChild(head);

    const body = document.createElement("div");
    body.className = "exec-report-body";

    // 1. Executive Business Summary (Sales increased/decreased, company performance)
    const sec1 = document.createElement("div");
    sec1.className = "exec-block";
    const summaryPoints = Array.isArray(summary.points) && summary.points.length ? summary.points : [];
    sec1.innerHTML = `
      <h3 class="exec-block-title">📊 Executive Business Summary</h3>
      <div class="exec-summary-box">
        <p class="exec-summary-text">${escapeHtml(summary.overview || "Company operational and commercial performance evaluated across active indicators.")}</p>
        ${summaryPoints.length ? `
          <div class="exec-points-list">
            ${summaryPoints.map((pt, idx) => `
              <div class="exec-point-item">
                <span class="exec-point-num">${idx + 1}</span>
                <span class="exec-point-badge tag-${escapeHtml(pt.type || 'info')}">${escapeHtml(pt.tag || 'Key Finding')}</span>
                <span class="exec-point-text">${escapeHtml(pt.text || '')}</span>
              </div>
            `).join('')}
          </div>
        ` : (summary.trend_detail ? `
          <div class="exec-trend-line">
            <span class="exec-trend-tag">📈 Trajectory:</span>
            <span class="exec-trend-desc">${escapeHtml(summary.trend_detail)}</span>
          </div>
        ` : "")}
      </div>
    `;
    body.appendChild(sec1);

    // 2. Department Performance & Areas to Improve (Which department to focus, what to improve)
    const sec2 = document.createElement("div");
    sec2.className = "exec-block";
    const perfPoints = Array.isArray(perf.points) && perf.points.length ? perf.points : [];
    sec2.innerHTML = `
      <h3 class="exec-block-title">🔍 Department Performance &amp; Areas to Improve</h3>
      <div class="exec-perf-grid">
        <div class="exec-perf-card exec-perf-top">
          <div class="exec-perf-badge">🏆 Top Performing Department</div>
          <div class="exec-perf-name">${escapeHtml(topP.name || "Leading Segment")}</div>
          <div class="exec-perf-metric">${escapeHtml(topP.metric || "")} <span class="exec-perf-share">(${escapeHtml(topP.share || "Core Driver")})</span></div>
          <p class="exec-perf-desc">${escapeHtml(topP.detail || "")}</p>
        </div>

        <div class="exec-perf-card exec-perf-focus">
          <div class="exec-perf-badge">⚠️ Department Needing Focus</div>
          <div class="exec-perf-name">${escapeHtml(focusP.name || "Lagging Segment")}</div>
          <div class="exec-perf-metric">${escapeHtml(focusP.metric || "")} <span class="exec-perf-share">(${escapeHtml(focusP.share || "Needs Improvement")})</span></div>
          <p class="exec-perf-desc">${escapeHtml(focusP.detail || "")}</p>
        </div>
      </div>

      ${perfPoints.length ? `
        <div class="exec-points-list">
          ${perfPoints.map((pt, idx) => `
            <div class="exec-point-item">
              <span class="exec-point-num">${idx + 1}</span>
              <span class="exec-point-badge tag-${escapeHtml(pt.type || 'info')}">${escapeHtml(pt.tag || 'Action Item')}</span>
              <span class="exec-point-text">${escapeHtml(pt.text || '')}</span>
            </div>
          `).join('')}
        </div>
      ` : (perf.areas_to_improve ? `
        <div class="exec-improve-box">
          <strong class="exec-improve-head">🎯 What we have to improve:</strong>
          <span class="exec-improve-text">${escapeHtml(perf.areas_to_improve)}</span>
        </div>
      ` : "")}
    `;
    body.appendChild(sec2);

    // 3. Strategic Management Recommendations
    const sec3 = document.createElement("div");
    sec3.className = "exec-block";
    sec3.innerHTML = `<h3 class="exec-block-title">🎯 Strategic Recommendations</h3>`;
    const ol = document.createElement("ol");
    ol.className = "mgmt-recs-list";

    (report.recommendations || []).slice(0, 5).forEach((rec) => {
      const text = typeof rec === "string" ? rec : (rec.action ? (rec.rationale ? `${rec.action}: ${rec.rationale}` : rec.action) : JSON.stringify(rec));
      const li = document.createElement("li");
      li.className = "mgmt-rec-item";
      li.textContent = text;
      ol.appendChild(li);
    });
    sec3.appendChild(ol);
    body.appendChild(sec3);

    card.appendChild(body);
    return card;
  }

  function renderKpiStrip(kpis) {
    const grid = document.createElement("div");
    grid.className = "kpi-grid";
    kpis.forEach((k) => {
      const tile = document.createElement("div");
      tile.className = "kpi-tile";
      const num = Number(k.value);
      const formatted = Number.isFinite(num) ? num.toLocaleString() : String(k.value ?? 0);
      tile.innerHTML = `
        <div class="kpi-tile-label">${escapeHtml(k.label)}</div>
        <div class="kpi-tile-val">${escapeHtml(formatted)}</div>
      `;
      grid.appendChild(tile);
    });
    return grid;
  }

  function renderDashboardChartCard(chart) {
    const card = document.createElement("div");
    card.className = "chart-card";

    const head = document.createElement("div");
    head.className = "chart-card-head";
    head.innerHTML = `<div class="chart-title">${escapeHtml(chart.title)}</div>`;
    const sqlBtn = document.createElement("button");
    sqlBtn.type = "button";
    sqlBtn.className = "btn btn-ghost btn-sm";
    sqlBtn.textContent = "SQL";
    head.appendChild(sqlBtn);
    card.appendChild(head);

    if (chart.type === "donut") {
      card.appendChild(renderDonutChart(chart.points || [], chart.x_label || chart.title));
    } else if (chart.type === "hbar") {
      card.appendChild(renderHorizontalBars(chart.points || [], chart.x_label || chart.title));
    } else {
      card.appendChild(renderCartesianSvg(chart.type, chart.points || [], chart.x_label || chart.title));
    }

    if (chart.sql) {
      const pre = document.createElement("pre");
      pre.className = "sql-mini-pre";
      pre.textContent = chart.sql;
      pre.hidden = true;
      sqlBtn.addEventListener("click", () => {
        pre.hidden = !pre.hidden;
      });
      card.appendChild(pre);
    }
    return card;
  }

  // Interactive Chart Tooltips & Click-to-Inspect on Dashboard
  let sharedChartTooltip = null;
  function getChartTooltip() {
    if (!sharedChartTooltip) {
      sharedChartTooltip = document.createElement("div");
      sharedChartTooltip.className = "chart-tooltip";
      sharedChartTooltip.hidden = true;
      document.body.appendChild(sharedChartTooltip);
    }
    return sharedChartTooltip;
  }

  function showChartTooltip(ev, label, value, extra = "") {
    const tip = getChartTooltip();
    tip.innerHTML = `
      <div class="chart-tooltip-title">${escapeHtml(label)}</div>
      <div class="chart-tooltip-val">${escapeHtml(Number(value).toLocaleString())}${extra ? ` (${escapeHtml(extra)})` : ""}</div>
      ${state.sessionId ? `<div class="chart-tooltip-hint">Click to run dataset query</div>` : ""}
    `;
    tip.hidden = false;
    positionChartTooltip(ev);
  }

  function positionChartTooltip(ev) {
    if (!sharedChartTooltip || sharedChartTooltip.hidden) return;
    sharedChartTooltip.style.left = `${Math.min(window.innerWidth - 190, ev.clientX + 14)}px`;
    sharedChartTooltip.style.top = `${Math.max(12, ev.clientY - 56)}px`;
  }

  function hideChartTooltip() {
    if (sharedChartTooltip) sharedChartTooltip.hidden = true;
  }

  function handleChartPointClick(label, dimensionName) {
    hideChartTooltip();
    if (!state.sessionId || !label) return;
    switchTab("dashboard");
    const dim = dimensionName ? `${dimensionName} ` : "";
    els.dashPromptInput.value = `Show top rows for ${dim}${label}`;
    els.dashPromptForm.dispatchEvent(new Event("submit"));
  }

  function renderDonutChart(pts, dimensionName = "") {
    const wrap = document.createElement("div");
    wrap.className = "donut-wrap";
    const total = pts.reduce((acc, p) => acc + Math.max(0, p.value), 0) || 1;
    const size = 150, cx = 75, cy = 75, r = 52, circ = 2 * Math.PI * r;
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("width", size);
    svg.setAttribute("height", size);
    svg.setAttribute("viewBox", `0 0 ${size} ${size}`);

    const circles = [];
    const centerTxt = document.createElementNS(svgNS, "text");
    centerTxt.setAttribute("x", cx);
    centerTxt.setAttribute("y", cy + 4);
    centerTxt.setAttribute("text-anchor", "middle");
    centerTxt.setAttribute("font-size", "12");
    centerTxt.setAttribute("font-weight", "700");
    centerTxt.setAttribute("fill", "currentColor");
    centerTxt.textContent = `${pts.length} groups`;

    let offset = 0;
    pts.forEach((p, idx) => {
      const val = Math.max(0, p.value);
      const frac = val / total;
      const dash = frac * circ;
      const circle = document.createElementNS(svgNS, "circle");
      circle.setAttribute("cx", cx);
      circle.setAttribute("cy", cy);
      circle.setAttribute("r", r);
      circle.setAttribute("fill", "none");
      circle.setAttribute("stroke", CHART_PALETTE[idx % CHART_PALETTE.length]);
      circle.setAttribute("stroke-width", "22");
      circle.setAttribute("stroke-dasharray", `${dash} ${circ - dash}`);
      circle.setAttribute("stroke-dashoffset", String(-offset));
      circle.setAttribute("transform", `rotate(-90 ${cx} ${cy})`);
      circle.setAttribute("class", "interactive-svg-elem");
      circles.push(circle);
      svg.appendChild(circle);
      offset += dash;
    });
    svg.appendChild(centerTxt);

    const legend = document.createElement("div");
    legend.className = "donut-legend";
    pts.forEach((p, idx) => {
      const val = Math.max(0, p.value);
      const pct = ((val / total) * 100).toFixed(1) + "%";
      const item = document.createElement("div");
      item.className = "legend-item interactive-legend";
      item.innerHTML = `
        <div class="legend-left">
          <span class="legend-swatch" style="background:${CHART_PALETTE[idx % CHART_PALETTE.length]}"></span>
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(p.label)}</span>
        </div>
        <span style="font-family:var(--font-mono);color:var(--text-muted)">${pct}</span>
      `;
      const activate = (ev) => {
        circles[idx].setAttribute("stroke-width", "26");
        circles[idx].classList.add("active");
        item.classList.add("active");
        centerTxt.textContent = pct;
        if (ev) showChartTooltip(ev, p.label, val, pct);
      };
      const deactivate = () => {
        circles[idx].setAttribute("stroke-width", "22");
        circles[idx].classList.remove("active");
        item.classList.remove("active");
        centerTxt.textContent = `${pts.length} groups`;
        hideChartTooltip();
      };
      [circles[idx], item].forEach((el) => {
        el.addEventListener("mouseenter", activate);
        el.addEventListener("mousemove", positionChartTooltip);
        el.addEventListener("mouseleave", deactivate);
        el.addEventListener("click", () => handleChartPointClick(p.label, dimensionName));
      });
      legend.appendChild(item);
    });

    wrap.append(svg, legend);
    return wrap;
  }

  function renderHorizontalBars(pts, dimensionName = "") {
    const list = document.createElement("div");
    list.className = "hbar-list";
    const maxVal = Math.max(1, ...pts.map((p) => p.value));
    const total = pts.reduce((acc, p) => acc + Math.max(0, p.value), 0) || 1;
    pts.forEach((p) => {
      const pct = Math.max(4, (p.value / maxVal) * 100);
      const share = `${((Math.max(0, p.value) / total) * 100).toFixed(1)}%`;
      const row = document.createElement("div");
      row.className = "hbar-row interactive-hbar";
      row.innerHTML = `
        <div class="hbar-label" title="${escapeHtml(p.label)}">${escapeHtml(p.label)}</div>
        <div class="hbar-track"><div class="hbar-fill" style="width:${pct.toFixed(1)}%"></div></div>
        <div class="hbar-val">${escapeHtml(Number(p.value).toLocaleString())}</div>
      `;
      row.addEventListener("mouseenter", (ev) => showChartTooltip(ev, p.label, p.value, share));
      row.addEventListener("mousemove", positionChartTooltip);
      row.addEventListener("mouseleave", hideChartTooltip);
      row.addEventListener("click", () => handleChartPointClick(p.label, dimensionName));
      list.appendChild(row);
    });
    return list;
  }

  function renderCartesianSvg(chartType, pts, dimensionName = "") {
    const width = 560, height = 200, padL = 54, padR = 16, padT = 14, padB = 42;
    const innerW = width - padL - padR, innerH = height - padT - padB;
    const maxVal = Math.max(1, ...pts.map((p) => p.value));
    const total = pts.reduce((acc, p) => acc + Math.max(0, p.value), 0) || 1;
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.style.width = "100%";
    svg.style.maxHeight = "210px";

    [0, 0.5, 1].forEach((ratio) => {
      const y = padT + innerH * (1 - ratio);
      const line = document.createElementNS(svgNS, "line");
      line.setAttribute("x1", padL);
      line.setAttribute("x2", width - padR);
      line.setAttribute("y1", y);
      line.setAttribute("y2", y);
      line.setAttribute("stroke", "currentColor");
      line.setAttribute("stroke-opacity", "0.14");
      svg.appendChild(line);

      const lbl = document.createElementNS(svgNS, "text");
      lbl.setAttribute("x", padL - 6);
      lbl.setAttribute("y", y + 4);
      lbl.setAttribute("text-anchor", "end");
      lbl.setAttribute("font-size", "10");
      lbl.setAttribute("fill", "#90a2c6");
      lbl.textContent = Math.round(maxVal * ratio).toLocaleString();
      svg.appendChild(lbl);
    });

    if (chartType === "line" && pts.length > 1) {
      const pathPts = pts.map((p, i) => [
        padL + (i / (pts.length - 1)) * innerW,
        padT + innerH - (p.value / maxVal) * innerH,
        p,
      ]);
      const poly = document.createElementNS(svgNS, "polyline");
      poly.setAttribute("fill", "none");
      poly.setAttribute("stroke", "#10b981");
      poly.setAttribute("stroke-width", "2.6");
      poly.setAttribute("points", pathPts.map(([x, y]) => `${x},${y}`).join(" "));
      svg.appendChild(poly);

      pathPts.forEach(([x, y, p], idx) => {
        const c = document.createElementNS(svgNS, "circle");
        c.setAttribute("cx", x);
        c.setAttribute("cy", y);
        c.setAttribute("r", "4.5");
        c.setAttribute("fill", "#10b981");
        c.setAttribute("class", "interactive-svg-elem");
        c.addEventListener("mouseenter", (ev) => {
          c.setAttribute("r", "7");
          showChartTooltip(ev, p.label, p.value);
        });
        c.addEventListener("mousemove", positionChartTooltip);
        c.addEventListener("mouseleave", () => {
          c.setAttribute("r", "4.5");
          hideChartTooltip();
        });
        c.addEventListener("click", () => handleChartPointClick(p.label, dimensionName));
        svg.appendChild(c);

        if (pts.length <= 10 || idx % Math.ceil(pts.length / 8) === 0) {
          const xLbl = document.createElementNS(svgNS, "text");
          xLbl.setAttribute("x", x);
          xLbl.setAttribute("y", height - 12);
          xLbl.setAttribute("text-anchor", "middle");
          xLbl.setAttribute("font-size", "9.5");
          xLbl.setAttribute("fill", "#90a2c6");
          xLbl.textContent = p.label.slice(0, 10);
          svg.appendChild(xLbl);
        }
      });
    } else {
      const slot = innerW / Math.max(1, pts.length);
      const barW = Math.max(8, Math.min(38, slot * 0.65));
      pts.forEach((p, i) => {
        const barH = Math.max(2, (p.value / maxVal) * innerH);
        const x = padL + i * slot + (slot - barW) / 2;
        const y = padT + innerH - barH;
        const share = `${((Math.max(0, p.value) / total) * 100).toFixed(1)}%`;

        const rect = document.createElementNS(svgNS, "rect");
        rect.setAttribute("x", x);
        rect.setAttribute("y", y);
        rect.setAttribute("width", barW);
        rect.setAttribute("height", barH);
        rect.setAttribute("rx", "4");
        rect.setAttribute("fill", CHART_PALETTE[i % CHART_PALETTE.length]);
        rect.setAttribute("class", "interactive-svg-elem");
        rect.addEventListener("mouseenter", (ev) => showChartTooltip(ev, p.label, p.value, share));
        rect.addEventListener("mousemove", positionChartTooltip);
        rect.addEventListener("mouseleave", hideChartTooltip);
        rect.addEventListener("click", () => handleChartPointClick(p.label, dimensionName));
        svg.appendChild(rect);

        const xLbl = document.createElement("text");
        const xLblSvg = document.createElementNS(svgNS, "text");
        xLblSvg.setAttribute("x", x + barW / 2);
        xLblSvg.setAttribute("y", height - 12);
        xLblSvg.setAttribute("text-anchor", "middle");
        xLblSvg.setAttribute("font-size", "9.5");
        xLblSvg.setAttribute("fill", "#90a2c6");
        xLblSvg.textContent = p.label.slice(0, 10);
        svg.appendChild(xLblSvg);
      });
    }
    return svg;
  }

  function createEditableSqlBox(sql, engine, parentCard) {
    const box = document.createElement("div");
    box.className = "sql-box";
    const head = document.createElement("div");
    head.className = "sql-box-head";
    head.innerHTML = `<span>SQL (${escapeHtml(engine)})</span>`;
    const actions = document.createElement("div");
    actions.className = "sql-box-actions";
    const runBtn = document.createElement("button");
    runBtn.type = "button";
    runBtn.className = "btn btn-primary btn-sm";
    runBtn.textContent = "Re-run SQL";
    actions.appendChild(runBtn);
    head.appendChild(actions);

    const ta = document.createElement("textarea");
    ta.className = "sql-editor";
    ta.value = sql;
    ta.rows = Math.min(5, Math.max(2, sql.split("\n").length));

    runBtn.addEventListener("click", async () => {
      const editedSql = ta.value.trim();
      if (!editedSql || !state.sessionId) return;
      const outEl = parentCard.querySelector(".result-wrapper") || document.createElement("div");
      if (!outEl.parentElement) parentCard.appendChild(outEl);
      outEl.innerHTML = `<div class="hint" style="padding:8px 0">Executing SQL...</div>`;
      try {
        const res = await fetch("/api/sql", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: state.sessionId, sql: editedSql }),
        });
        const result = await res.json();
        renderResultInto(outEl, result, inferClientChart(result));
      } catch (err) {
        outEl.innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
      }
    });

    box.append(head, ta);
    return box;
  }

  function inferClientChart(result) {
    if (!result?.ok || !result.rows?.length || !result.columns?.length) return null;
    const rows = result.rows, cols = result.columns;
    if (rows.length === 1 && cols.length <= 4) {
      const kpis = cols.filter((c) => typeof rows[0][c] === "number").map((c) => ({ label: c, value: rows[0][c] }));
      if (kpis.length) return { type: "kpi", items: kpis };
    }
    if (rows.length >= 2 && rows.length <= 30 && cols.length >= 2) {
      const labelCol = cols[0];
      const numCol = cols.slice(1).find((c) => rows.some((r) => typeof r[c] === "number"));
      if (numCol) {
        return {
          type: labelCol.includes("date") || labelCol.includes("month") ? "line" : "bar",
          x_label: labelCol,
          y_label: numCol,
          points: rows.slice(0, 20).map((r) => ({ label: String(r[labelCol] ?? "NULL"), value: Number(r[numCol] ?? 0) })),
        };
      }
    }
    return null;
  }

  function renderResultInto(container, result, chart) {
    container.className = "result-wrapper";
    container.innerHTML = "";
    if (!result.ok) {
      container.innerHTML = `<div class="error-banner">SQL Error: ${escapeHtml(result.error)}</div>`;
      return;
    }
    if (chart) container.appendChild(renderSingleChartCard(chart));

    const cols = result.columns || [], rows = result.rows || [];
    if (!cols.length) return;
    const block = document.createElement("div");
    block.className = "result-block";
    const meta = document.createElement("div");
    meta.className = "result-meta";
    const metaLabel = document.createElement("span");
    metaLabel.textContent = `${rows.length} row(s) · ${result.execution_ms ?? 0} ms`;
    const filterInput = document.createElement("input");
    filterInput.type = "text";
    filterInput.className = "table-filter-input";
    filterInput.placeholder = "Filter rows...";
    meta.append(metaLabel, filterInput);

    const tableWidget = buildSortableTable(cols, rows);
    filterInput.addEventListener("input", () => tableWidget.applyFilter(filterInput.value));
    block.append(meta, tableWidget.element);
    container.appendChild(block);
  }

  function renderSingleChartCard(chart) {
    const card = document.createElement("div");
    card.className = "chart-card";
    if (chart.type === "kpi") {
      card.innerHTML = `<div class="chart-title" style="margin-bottom:8px">Key Metrics</div>`;
      card.appendChild(renderKpiStrip(chart.items));
      return card;
    }
    card.innerHTML = `<div class="chart-title" style="margin-bottom:8px">${escapeHtml(chart.y_label)} by ${escapeHtml(chart.x_label)}</div>`;
    card.appendChild(renderCartesianSvg(chart.type, chart.points || [], chart.x_label || ""));
    return card;
  }

  function buildSortableTable(columns, rows) {
    let sortCol = null, sortAsc = true, filterText = "";
    const scroll = document.createElement("div");
    scroll.className = "table-scroll";
    const table = document.createElement("table");
    table.className = "data-table";
    const thead = document.createElement("thead");
    const headTr = document.createElement("tr");
    columns.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      th.addEventListener("click", () => {
        if (sortCol === col) sortAsc = !sortAsc;
        else {
          sortCol = col;
          sortAsc = true;
        }
        renderBody();
      });
      headTr.appendChild(th);
    });
    thead.appendChild(headTr);
    const tbody = document.createElement("tbody");
    table.append(thead, tbody);

    function renderBody() {
      let view = rows.slice();
      if (filterText) {
        const needle = filterText.toLowerCase();
        view = view.filter((r) => columns.some((c) => String(r[c] ?? "").toLowerCase().includes(needle)));
      }
      if (sortCol) {
        view.sort((a, b) => {
          const va = a[sortCol], vb = b[sortCol];
          if (va === vb) return 0;
          if (va == null) return 1;
          if (vb == null) return -1;
          if (typeof va === "number" && typeof vb === "number") return sortAsc ? va - vb : vb - va;
          return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
        });
      }
      tbody.innerHTML = "";
      view.forEach((r) => {
        const tr = document.createElement("tr");
        columns.forEach((c) => {
          const td = document.createElement("td");
          const v = r[c];
          if (v === null || v === undefined) td.innerHTML = `<span class="null-pill">NULL</span>`;
          else td.textContent = typeof v === "number" ? v.toLocaleString() : String(v);
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }
    renderBody();
    scroll.appendChild(table);
    return {
      element: scroll,
      applyFilter(val) {
        filterText = val.trim();
        renderBody();
      },
    };
  }

  // ================= FEATURE 5: ADDITIONAL DATA CLEANING (USER RULES) =================
  function populateCustomCleanControls(data) {
    const profiles = data.profiles || [];
    els.customCleanDatasetHint.textContent = `${data.filename} (${data.report.cleaned_rows} rows, ${profiles.length} cols)`;

    els.replaceColSelect.innerHTML = `<option value="">All Text Columns</option>`;
    els.dropColsList.innerHTML = "";

    // Reset Power Query selects
    if (els.dtypeColSelect) els.dtypeColSelect.innerHTML = `<option value="">— choose column —</option>`;
    if (els.splitColSelect) els.splitColSelect.innerHTML = `<option value="">— choose column —</option>`;
    if (els.extractColSelect) els.extractColSelect.innerHTML = `<option value="">— choose column —</option>`;
    if (els.filterColSelect) els.filterColSelect.innerHTML = `<option value="">— choose column —</option>`;
    if (els.sortColSelect) els.sortColSelect.innerHTML = `<option value="">— choose column —</option>`;
    if (els.renameColSelect) els.renameColSelect.innerHTML = `<option value="">— choose column —</option>`;
    if (els.fillDirColSelect) els.fillDirColSelect.innerHTML = `<option value="">— choose column —</option>`;

    profiles.forEach((p) => {
      // Find & Replace text cols
      if (p.semantic_type === "text") {
        const opt = document.createElement("option");
        opt.value = p.name;
        opt.textContent = p.name;
        els.replaceColSelect.appendChild(opt);
      }
      // Drop columns (all)
      const lbl = document.createElement("label");
      lbl.className = "drop-col-chip";
      lbl.innerHTML = `<input type="checkbox" value="${escapeHtml(p.name)}" /> ${escapeHtml(p.name)}`;
      els.dropColsList.appendChild(lbl);
      // Change Data Type (all cols)
      if (els.dtypeColSelect) {
        const o = document.createElement("option");
        o.value = p.name; o.textContent = p.name;
        els.dtypeColSelect.appendChild(o);
      }
      // Split Column (text cols preferred but show all)
      if (els.splitColSelect) {
        const o = document.createElement("option");
        o.value = p.name; o.textContent = p.name;
        els.splitColSelect.appendChild(o);
      }
      // Extract (all cols)
      if (els.extractColSelect) {
        const o = document.createElement("option");
        o.value = p.name; o.textContent = p.name;
        els.extractColSelect.appendChild(o);
      }
      // Filter Rows (all cols)
      if (els.filterColSelect) {
        const o = document.createElement("option");
        o.value = p.name; o.textContent = p.name;
        els.filterColSelect.appendChild(o);
      }
      // Sort Rows (all cols)
      if (els.sortColSelect) {
        const o = document.createElement("option");
        o.value = p.name; o.textContent = p.name;
        els.sortColSelect.appendChild(o);
      }
      // Rename Column (all cols)
      if (els.renameColSelect) {
        const o = document.createElement("option");
        o.value = p.name; o.textContent = p.name;
        els.renameColSelect.appendChild(o);
      }
      // Fill Direction (all cols)
      if (els.fillDirColSelect) {
        const o = document.createElement("option");
        o.value = p.name; o.textContent = p.name;
        els.fillDirColSelect.appendChild(o);
      }
    });
  }

  els.recleanBtn.addEventListener("click", async () => {
    if (!state.sessionId) {
      showToast("Attach a dataset in Upload Dataset first.", "info");
      return;
    }
    try {
      const res = await fetch(`/api/dataset/${state.sessionId}/reclean`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(getCleaningOptions()),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Custom cleaning failed");
      onDatasetReady(data, true);
      fetchAndRenderDashboard({ prompt: "create analytics dashboard" });

      const rep = data.report;
      const logActions = (rep.actions || []).map((a) => `<li>${escapeHtml(a.description)}</li>`).join("");
      els.customCleanLog.innerHTML = `
        <div class="panel custom-clean-card">
          <div class="panel-header">
            <h2>Applied Custom Cleaning Result</h2>
            <span class="badge badge-score">Quality: ${rep.quality_score_before}% → ${rep.quality_score_after}%</span>
          </div>
          <ul style="margin:0;padding-left:18px;font-size:13px">${logActions || "<li>No changes required.</li>"}</ul>
        </div>
      `;
      showToast("Additional data cleaning applied!", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  els.resetCustomCleanBtn.addEventListener("click", () => {
    els.strategySelect.value = "smart";
    els.textCaseSelect.value = "none";
    els.fillTextInput.value = "Unknown";
    els.roundDecimalsSelect.value = "none";
    els.optDedup.checked = true;
    els.optDates.checked = true;
    els.optNumeric.checked = true;
    els.optCols.checked = true;
    els.replaceColSelect.value = "";
    els.findTextInput.value = "";
    els.replaceTextInput.value = "";
    els.dropColsList.querySelectorAll('input[type="checkbox"]').forEach((cb) => (cb.checked = false));
    // Reset Power Query controls
    if (els.dtypeColSelect) els.dtypeColSelect.value = "";
    if (els.dtypeTargetSelect) els.dtypeTargetSelect.value = "";
    if (els.splitColSelect) els.splitColSelect.value = "";
    if (els.splitDelimInput) els.splitDelimInput.value = "";
    if (els.splitMaxSelect) els.splitMaxSelect.value = "2";
    if (els.extractColSelect) els.extractColSelect.value = "";
    if (els.extractModeSelect) els.extractModeSelect.value = "";
    if (els.extractParamInput) els.extractParamInput.value = "";
    if (els.extractOutputCol) els.extractOutputCol.value = "";
    if (els.filterColSelect) els.filterColSelect.value = "";
    if (els.filterCondSelect) els.filterCondSelect.value = "";
    if (els.filterValInput) els.filterValInput.value = "";
    if (els.sortColSelect) els.sortColSelect.value = "";
    if (els.sortDirSelect) els.sortDirSelect.value = "asc";
    if (els.renameColSelect) els.renameColSelect.value = "";
    if (els.renameToInput) els.renameToInput.value = "";
    if (els.fillDirColSelect) els.fillDirColSelect.value = "";
    if (els.fillDirSelect) els.fillDirSelect.value = "";
    showToast("Reset additional cleaning rules to defaults.", "info");
  });

  // Global delegated quick prompt + keyboard shortcuts
  document.addEventListener("click", (e) => {
    const promptBtn = e.target.closest("[data-quick-prompt]");
    if (promptBtn) {
      submitGeneralAssistant(promptBtn.getAttribute("data-quick-prompt"));
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!els.aiModal.hidden) els.aiModal.hidden = true;
      if (state.voiceListening) stopVoiceListening();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      els.ribbonSearchInput.focus();
    } else if ((e.key === "Enter" || e.key === " ") && document.activeElement?.hasAttribute?.("data-quick-prompt")) {
      e.preventDefault();
      submitGeneralAssistant(document.activeElement.getAttribute("data-quick-prompt"));
    }
  });

  // Boot
  renderSidebarDataset();
  renderWelcomeAssistant();
  renderSuggestions([]);
  loadSampleCatalog();
  loadAiConfig();
})();
