/**
 * Companion-AI Frontend Application Logic ("Maya").
 * Connects with FastAPI backend endpoints for chat, memory, and contradiction audits.
 */

const API_BASE = "";

// State
let currentTab = "chat-tab";

// DOM Elements
const navItems = document.querySelectorAll(".nav-item");
const tabPanels = document.querySelectorAll(".tab-panel");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const chatMessages = document.getElementById("chat-messages");
const btnSend = document.getElementById("btn-send");

const activeMemoryCountEl = document.getElementById("active-memory-count");
const supersededCountEl = document.getElementById("superseded-count");
const memoriesGrid = document.getElementById("memories-grid");
const supersededContainer = document.getElementById("superseded-container");
const profileContent = document.getElementById("profile-content");

const statusProvider = document.getElementById("status-provider");
const statusModel = document.getElementById("status-model");
const btnReset = document.getElementById("btn-reset-memory");
const btnRefreshMemories = document.getElementById("btn-refresh-memories");

const inspectForm = document.getElementById("inspect-form");
const inspectInput = document.getElementById("inspect-input");
const inspectResults = document.getElementById("inspect-results");

// Quick Fill Demo Buttons
const btnQuick1 = document.getElementById("btn-quick-fill-1");
const btnQuick2 = document.getElementById("btn-quick-fill-2");
const btnQuick3 = document.getElementById("btn-quick-fill-3");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  fetchHealthAndCounts();
  setupChat();
  setupInspect();
  setupQuickFills();

  btnReset.addEventListener("click", handleResetMemory);
  if (btnRefreshMemories) {
    btnRefreshMemories.addEventListener("click", loadMemories);
  }
});

// Navigation Tabs
function setupNavigation() {
  navItems.forEach((item) => {
    item.addEventListener("click", () => {
      const tabId = item.getAttribute("data-tab");
      navItems.forEach((n) => n.classList.remove("active"));
      tabPanels.forEach((p) => p.classList.remove("active"));

      item.classList.add("active");
      const activePanel = document.getElementById(tabId);
      if (activePanel) {
        activePanel.classList.add("active");
      }

      currentTab = tabId;
      if (tabId === "memories-tab") loadMemories();
      if (tabId === "superseded-tab") loadSuperseded();
      if (tabId === "profile-tab") loadProfile();
    });
  });
}

// Fetch Health & System Stats
async function fetchHealthAndCounts() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) return;
    const data = await res.json();
    statusProvider.textContent = data.llm_provider || "OpenAI";
    statusModel.textContent = data.model_name || "gpt-4o-mini";
    activeMemoryCountEl.textContent = data.active_facts || 0;
    supersededCountEl.textContent = data.superseded_facts || 0;
  } catch (err) {
    console.warn("Backend connection pending:", err);
  }
}

// Setup Chat
function setupChat() {
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;

    // Append User Bubble
    appendUserMessage(text);
    userInput.value = "";
    btnSend.disabled = true;

    // Loading indicator
    const typingBubble = appendTypingIndicator();

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, user_id: "default_user" }),
      });

      typingBubble.remove();

      if (!res.ok) {
        appendAssistantMessage("Sorry, I encountered an error processing that turn.", [], []);
        return;
      }

      const data = await res.json();
      appendAssistantMessage(data.reply, data.retrieved_memories, data.extracted_facts);

      // Refresh counts
      fetchHealthAndCounts();
    } catch (err) {
      typingBubble.remove();
      appendAssistantMessage("Could not connect to backend server. Please ensure server is running.", [], []);
    } finally {
      btnSend.disabled = false;
    }
  });

  // Enter sends message
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });
}

function appendUserMessage(text) {
  const wrapper = document.createElement("div");
  wrapper.className = "message-wrapper user-wrapper";
  wrapper.innerHTML = `
    <div class="msg-avatar user-avatar"><i class="fa-solid fa-user"></i></div>
    <div class="message-bubble user-bubble">
      <div class="message-text">${escapeHtml(text)}</div>
      <div class="message-meta"><span class="msg-time">${formatTime()}</span></div>
    </div>
  `;
  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendAssistantMessage(text, retrieved = [], extracted = []) {
  const wrapper = document.createElement("div");
  wrapper.className = "message-wrapper assistant-wrapper";

  let metaBadges = "";
  if (retrieved && retrieved.length > 0) {
    metaBadges += `<span class="recalled-tag" title="${retrieved.map((r) => r.fact_text).join(' | ')}"><i class="fa-solid fa-brain"></i> Recalled ${retrieved.length} memory</span>`;
  }
  if (extracted && extracted.length > 0) {
    metaBadges += `<span class="stored-tag" title="${extracted.map((e) => e.fact_text).join(' | ')}"><i class="fa-solid fa-plus-circle"></i> Stored ${extracted.length} fact</span>`;
  }

  wrapper.innerHTML = `
    <div class="msg-avatar">🌸</div>
    <div class="message-bubble assistant-bubble">
      <div class="message-author">Maya</div>
      <div class="message-text">${escapeHtml(text)}</div>
      <div class="message-meta">
        <span class="msg-time">${formatTime()}</span>
        ${metaBadges}
      </div>
    </div>
  `;
  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendTypingIndicator() {
  const wrapper = document.createElement("div");
  wrapper.className = "message-wrapper assistant-wrapper";
  wrapper.innerHTML = `
    <div class="msg-avatar">🌸</div>
    <div class="message-bubble assistant-bubble">
      <div class="message-author">Maya</div>
      <div class="message-text" style="color: var(--text-muted);"><i class="fa-solid fa-circle-notch fa-spin"></i> Thinking...</div>
    </div>
  `;
  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return wrapper;
}

// Load Active Memories
async function loadMemories() {
  memoriesGrid.innerHTML = `<div class="placeholder-box"><i class="fa-solid fa-spinner fa-spin fa-2x"></i><p>Loading active memories...</p></div>`;
  try {
    const res = await fetch(`${API_BASE}/memories?all_history=false`);
    const memories = await res.json();

    if (!memories || memories.length === 0) {
      memoriesGrid.innerHTML = `
        <div class="placeholder-box" style="grid-column: 1/-1;">
          <i class="fa-solid fa-box-open fa-2x"></i>
          <p>No active memories stored yet. Tell Maya something personal in chat!</p>
        </div>`;
      return;
    }

    memoriesGrid.innerHTML = "";
    memories.forEach((m) => {
      const card = document.createElement("div");
      card.className = "memory-card";
      card.innerHTML = `
        <div class="memory-card-header">
          <span class="category-tag">${m.category}</span>
          <span class="badge" style="background: rgba(34, 197, 94, 0.15); color: #86efac;">${m.status}</span>
        </div>
        <div class="memory-text">${escapeHtml(m.fact_text)}</div>
        <div class="memory-metrics">
          <span>Imp: ${(m.importance || 0).toFixed(2)} | Conf: ${(m.confidence || 0).toFixed(2)}</span>
          <span><i class="fa-solid fa-eye"></i> ${m.access_count || 0} accesses</span>
        </div>
      `;
      memoriesGrid.appendChild(card);
    });
  } catch (err) {
    memoriesGrid.innerHTML = `<div class="placeholder-box" style="color: #f87171;"><p>Failed to load memories.</p></div>`;
  }
}

// Load Superseded Contradiction Audit
async function loadSuperseded() {
  supersededContainer.innerHTML = `<div class="placeholder-box"><i class="fa-solid fa-spinner fa-spin fa-2x"></i><p>Loading audit trail...</p></div>`;
  try {
    const res = await fetch(`${API_BASE}/superseded`);
    const data = await res.json();
    const list = data.superseded_facts || [];

    if (!list || list.length === 0) {
      supersededContainer.innerHTML = `
        <div class="placeholder-box">
          <i class="fa-solid fa-shield-check fa-2x" style="color: var(--accent-green);"></i>
          <p>No superseded facts yet. No contradictions detected.</p>
        </div>`;
      return;
    }

    supersededContainer.innerHTML = "";
    list.forEach((s) => {
      const card = document.createElement("div");
      card.className = "audit-card";
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="category-tag" style="background: rgba(239, 68, 68, 0.2); color: #fca5a5;">${s.category}</span>
          <span class="badge badge-warning">SUPERSEDED</span>
        </div>
        <div class="audit-superseded-text">${escapeHtml(s.fact_text)}</div>
        <div class="audit-meta">
          <span><i class="fa-solid fa-link"></i> Superseded by fact ID: ${s.superseded_by_id ? s.superseded_by_id.substring(0, 8) + '...' : 'New Statement'}</span>
          <span><i class="fa-regular fa-clock"></i> ${new Date(s.updated_at).toLocaleTimeString()}</span>
        </div>
      `;
      supersededContainer.appendChild(card);
    });
  } catch (err) {
    supersededContainer.innerHTML = `<div class="placeholder-box" style="color: #f87171;"><p>Failed to load superseded audit.</p></div>`;
  }
}

// Load Structured User Profile
async function loadProfile() {
  profileContent.innerHTML = `<div class="placeholder-box" style="grid-column: 1/-1;"><i class="fa-solid fa-spinner fa-spin fa-2x"></i><p>Loading profile...</p></div>`;
  try {
    const res = await fetch(`${API_BASE}/profile`);
    const data = await res.json();

    const prefs = Object.entries(data.key_preferences || {})
      .map(([k, v]) => `${k}: ${v}`)
      .join(", ");

    profileContent.innerHTML = `
      <div class="profile-item">
        <span class="profile-label">Name</span>
        <span class="profile-val">${escapeHtml(data.name || "Unknown / Not specified")}</span>
      </div>
      <div class="profile-item">
        <span class="profile-label">Occupation</span>
        <span class="profile-val">${escapeHtml(data.occupation || "Not specified")}</span>
      </div>
      <div class="profile-item">
        <span class="profile-label">Relationship Status</span>
        <span class="profile-val">${escapeHtml(data.relationship_status || "Not specified")}</span>
      </div>
      <div class="profile-item">
        <span class="profile-label">Partner</span>
        <span class="profile-val">${escapeHtml(data.partner_name || "None")}</span>
      </div>
      <div class="profile-item">
        <span class="profile-label">Pets</span>
        <span class="profile-val">${escapeHtml((data.pets || []).join(", ") || "None recorded")}</span>
      </div>
      <div class="profile-item" style="grid-column: 1/-1;">
        <span class="profile-label">Known Preferences</span>
        <span class="profile-val">${escapeHtml(prefs || "None recorded")}</span>
      </div>
    `;
  } catch (err) {
    profileContent.innerHTML = `<div class="placeholder-box" style="color: #f87171;"><p>Failed to load profile.</p></div>`;
  }
}

// Setup Retrieval Sandbox
function setupInspect() {
  inspectForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = inspectInput.value.trim();
    if (!query) return;

    inspectResults.innerHTML = `<div class="placeholder-box"><i class="fa-solid fa-spinner fa-spin fa-2x"></i><p>Calculating retrieval scores...</p></div>`;
    try {
      const res = await fetch(`${API_BASE}/inspect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query, top_k: 5 }),
      });
      const data = await res.json();
      const results = data.retrieved_memories || [];

      if (results.length === 0) {
        inspectResults.innerHTML = `
          <div class="placeholder-box">
            <i class="fa-solid fa-filter-circle-xmark fa-2x"></i>
            <p>No memories matched query above the relevance threshold.</p>
          </div>`;
        return;
      }

      inspectResults.innerHTML = "";
      results.forEach((r, idx) => {
        const item = document.createElement("div");
        item.className = "memory-card";
        item.innerHTML = `
          <div class="memory-card-header">
            <span class="category-tag">Rank #${idx + 1} • ${r.category}</span>
            <span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #7dd3fc;">Matched</span>
          </div>
          <div class="memory-text">${escapeHtml(r.fact_text)}</div>
          <div class="memory-metrics">
            <span>Importance: ${(r.importance || 0).toFixed(2)}</span>
            <span>Accesses: ${r.access_count || 0}</span>
          </div>
        `;
        inspectResults.appendChild(item);
      });
    } catch (err) {
      inspectResults.innerHTML = `<div class="placeholder-box" style="color: #f87171;"><p>Failed to run inspection.</p></div>`;
    }
  });
}

// Quick Fill Demo Buttons
function setupQuickFills() {
  btnQuick1.addEventListener("click", () => {
    userInput.value = "Hey Maya, I'm working as a Senior Product Designer at Figma and I've been dating Alex for 8 months.";
    userInput.focus();
  });
  btnQuick2.addEventListener("click", () => {
    userInput.value = "Alex and I broke up last night. We are done, I'm single now. Also I just accepted a new job offer at Stripe!";
    userInput.focus();
  });
  btnQuick3.addEventListener("click", () => {
    userInput.value = "Should I invite Alex to the Figma office party this Friday?";
    userInput.focus();
  });
}

// Reset Memory
async function handleResetMemory() {
  if (!confirm("Are you sure you want to wipe all stored memory facts?")) return;
  try {
    await fetch(`${API_BASE}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: "default_user" }),
    });
    chatMessages.innerHTML = `
      <div class="message-wrapper assistant-wrapper">
        <div class="msg-avatar">🌸</div>
        <div class="message-bubble assistant-bubble">
          <div class="message-author">Maya</div>
          <div class="message-text">All memories have been wiped clean! A fresh start. How are you doing today?</div>
        </div>
      </div>
    `;
    fetchHealthAndCounts();
    if (currentTab === "memories-tab") loadMemories();
    if (currentTab === "superseded-tab") loadSuperseded();
    if (currentTab === "profile-tab") loadProfile();
  } catch (err) {
    alert("Error resetting memory.");
  }
}

// Helper utilities
function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatTime() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
