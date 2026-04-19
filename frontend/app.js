const API_BASE = window.location.origin;
const THEME_KEY = "mindvault_theme";

function getTokenOrRedirect() {
  const token = localStorage.getItem("token");
  if (!token) {
    window.location.href = "login.html";
    return null;
  }
  return token;
}

function authHeaders(extra = {}) {
  const token = getTokenOrRedirect();
  return {
    Authorization: `Bearer ${token}`,
    ...extra,
  };
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_KEY, theme);
  const btn = document.getElementById("themeToggleBtn");
  if (btn) {
    btn.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
  }
}

function toggleTheme() {
  const current = localStorage.getItem(THEME_KEY) || "dark";
  applyTheme(current === "dark" ? "light" : "dark");
}

function toggleUserMenu() {
  const sidebar = document.getElementById("userSidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  if (!sidebar || !backdrop) return;
  const willOpen = !sidebar.classList.contains("open");
  sidebar.classList.toggle("open");
  backdrop.classList.toggle("show");
  document.body.classList.toggle("menu-open", willOpen);
}

function closeUserMenu() {
  const sidebar = document.getElementById("userSidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  if (!sidebar || !backdrop) return;
  sidebar.classList.remove("open");
  backdrop.classList.remove("show");
  document.body.classList.remove("menu-open");
}

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("email");
  window.location.href = "login.html";
}

async function deleteAccount() {
  const ok = window.confirm("Delete your account and all your data permanently?");
  if (!ok) return;

  try {
    const res = await fetch(`${API_BASE}/account`, {
      method: "DELETE",
      headers: authHeaders(),
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || data.message || "Failed to delete account");
      return;
    }

    alert("Account deleted successfully");
    logout();
  } catch (error) {
    alert(`Delete account failed: ${error.message}`);
  }
}

async function changePassword() {
  const currentPassword = window.prompt("Enter current password:");
  if (!currentPassword) return;

  const newPassword = window.prompt("Enter new password (min 6 chars):");
  if (!newPassword) return;

  if (newPassword.length < 6) {
    alert("New password must be at least 6 characters");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/account/change-password`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Failed to change password");
      return;
    }

    alert("Password changed successfully");
  } catch (error) {
    alert(`Change password failed: ${error.message}`);
  }
}

window.logout = logout;
window.deleteAccount = deleteAccount;
window.changePassword = changePassword;
window.toggleTheme = toggleTheme;
window.toggleUserMenu = toggleUserMenu;
window.closeUserMenu = closeUserMenu;

applyTheme(localStorage.getItem(THEME_KEY) || "dark");

fetch("navbar.html")
  .then((res) => res.text())
  .then((data) => {
    document.getElementById("navbar").innerHTML = data;
    const emailEl = document.getElementById("userEmail");
    const sidebarEmail = document.getElementById("sidebarUserEmail");
    const email = localStorage.getItem("email") || "";
    if (emailEl) {
      emailEl.innerText = email;
    }
    if (sidebarEmail) sidebarEmail.innerText = email;
    applyTheme(localStorage.getItem(THEME_KEY) || "dark");
  });

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeUserMenu();
});

function enterApp(scrollToApp = true) {
  const welcomeSection = document.getElementById("welcome");
  const appSection = document.getElementById("app");
  const openBtn = document.getElementById("openWorkspaceBtn");
  const headerActions = document.querySelector(".app-header-actions");
  if (welcomeSection) welcomeSection.classList.add("hidden");
  if (appSection) {
    appSection.classList.remove("hidden");
    if (scrollToApp) {
      appSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
  if (headerActions) headerActions.classList.add("hidden");
  if (openBtn) {
    openBtn.textContent = "Workspace Open";
    openBtn.disabled = true;
  }
}

function switchTab(tabName, event) {
  closeUserMenu();

  const appSection = document.getElementById("app");
  const welcomeSection = document.getElementById("welcome");
  const headerActions = document.querySelector(".app-header-actions");
  if (appSection && appSection.classList.contains("hidden")) {
    appSection.classList.remove("hidden");
  }
  if (welcomeSection && !welcomeSection.classList.contains("hidden")) {
    welcomeSection.classList.add("hidden");
  }
  if (headerActions) headerActions.classList.add("hidden");

  document.querySelectorAll(".tab-content").forEach((tab) => tab.classList.remove("active"));
  document.querySelectorAll(".tab-button").forEach((btn) => btn.classList.remove("active"));

  document.getElementById(tabName).classList.add("active");
  if (event && event.target && event.target.classList.contains("tab-button")) {
    event.target.classList.add("active");
  } else {
    const map = { upload: 0, search: 1, summary: 2, info: 3 };
    const i = map[tabName];
    if (typeof i === "number") {
      const btn = document.querySelectorAll(".tab-button")[i];
      if (btn) btn.classList.add("active");
    }
  }
}

window.addEventListener("DOMContentLoaded", () => {
  enterApp(false);
});

function showStatus(elementId, message, type = "info") {
  const statusEl = document.getElementById(elementId);
  statusEl.innerText = message;
  statusEl.className = `status show ${type}`;
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 20000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

function renderSearchFallback(results) {
  const summaryBox = document.getElementById("summaryBox");
  const summaryContent = document.getElementById("summaryContent");
  summaryBox.classList.add("show");
  const rows = (results || [])
    .map((r, idx) => {
      const text = (r.document || "").slice(0, 350);
      return `<div style="margin-bottom:14px;"><b>Result ${idx + 1}</b><div style="margin-top:6px;">${text}</div></div>`;
    })
    .join("");
  summaryContent.innerHTML = rows || "<div class='summary-loading'>No matching results</div>";
}

async function uploadFile() {
  const fileInput = document.getElementById("fileInput");
  const file = fileInput.files[0];

  if (!file) {
    showStatus("uploadStatus", "Please select a PDF file", "error");
    return;
  }

  showStatus("uploadStatus", "Uploading and processing...", "loading");
  document.getElementById("uploadResults").classList.remove("show");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });

    const data = await res.json();
    if (!res.ok || data.status !== "success") {
      throw new Error(data.detail || data.message || `HTTP ${res.status}`);
    }

    showStatus(
      "uploadStatus",
      `Successfully uploaded\n${data.filename}\nPages: ${data.pages}, Chunks: ${data.chunks}`,
      "success"
    );

    document.getElementById("resultPages").innerText = data.pages;
    document.getElementById("resultChunks").innerText = data.chunks;
    document.getElementById("uploadResults").classList.add("show");
    fileInput.value = "";
  } catch (error) {
    showStatus("uploadStatus", `Upload failed: ${error.message}`, "error");
  }
}

async function queryVectors() {
  const query = document.getElementById("queryInput").value.trim();

  if (!query) {
    showStatus("searchStatus", "Please enter a search query", "error");
    return;
  }

  showStatus("searchStatus", "Searching...", "loading");
  document.getElementById("summaryBox").classList.remove("show");

  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/query?q=${encodeURIComponent(query)}`,
      { headers: authHeaders() },
      25000
    );
    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.detail || data.error || `HTTP ${res.status}`);
    }

    if (data.results_count > 0) {
      renderSearchFallback(data.results);
      showStatus("searchStatus", "Search complete. Generating summary...", "loading");
      await getSummary(query, data.results);
    } else {
      showStatus("searchStatus", `No results found for \"${query}\"`, "error");
      document.getElementById("summaryBox").classList.remove("show");
    }
  } catch (error) {
    showStatus("searchStatus", `Search failed: ${error.message}`, "error");
  }
}

async function getSummary(query, results) {
  try {
    document.getElementById("summaryBox").classList.add("show");
    document.getElementById("summaryContent").innerHTML =
      '<div class="summary-loading">Generating summary...</div>';

    const res = await fetchWithTimeout(
      `${API_BASE}/summarize`,
      {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ query, results }),
      },
      30000
    );

    const data = await res.json();

    if (!res.ok || data.error) {
      renderSearchFallback(results);
      showStatus("searchStatus", `Summary unavailable: ${data.detail || data.error}`, "error");
    } else {
      const formattedSummary = (data.summary || "")
        .split("\n")
        .map((line) => `<div>${line}</div>`)
        .join("");
      document.getElementById("summaryContent").innerHTML = formattedSummary;
      showStatus("searchStatus", `Search completed for \"${query}\"`, "success");
    }
  } catch (error) {
    renderSearchFallback(results);
    showStatus("searchStatus", "Summary timeout/connection issue. Showing top results.", "error");
  }
}

async function generateFullSummary() {
  showStatus("summaryTabStatus", "Fetching all documents...", "loading");
  document.getElementById("summaryTabBox").classList.remove("show");

  try {
    const res = await fetch(`${API_BASE}/all-documents`, { headers: authHeaders() });
    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.detail || data.error || `HTTP ${res.status}`);
    }

    if (data.total_count > 0) {
      await generateFullSummaryContent(data.documents);
    } else {
      showStatus("summaryTabStatus", "No documents found in collection", "error");
      document.getElementById("summaryTabBox").classList.remove("show");
    }
  } catch (error) {
    showStatus("summaryTabStatus", `Connection error: ${error.message}`, "error");
  }
}

async function generateFullSummaryContent(documentList) {
  try {
    document.getElementById("summaryTabBox").classList.add("show");
    document.getElementById("summaryTabContent").innerHTML =
      '<div class="summary-loading">Generating comprehensive summary...</div>';
    showStatus("summaryTabStatus", "Generating AI summary...", "loading");

    const results = documentList.map((doc) => ({ document: doc }));

    const res = await fetch(`${API_BASE}/summarize`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        query: "Complete document collection overview and key insights",
        results,
      }),
    });

    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.detail || data.error || `HTTP ${res.status}`);
    }

    const formattedSummary = (data.summary || "")
      .split("\n")
      .map((line) => `<div>${line}</div>`)
      .join("");

    document.getElementById("summaryTabContent").innerHTML = formattedSummary;
    showStatus("summaryTabStatus", "Full document summary generated successfully", "success");
  } catch (error) {
    document.getElementById("summaryTabContent").innerHTML =
      `<div class="summary-loading">Error: ${error.message}</div>`;
    showStatus("summaryTabStatus", "Error generating summary", "error");
  }
}

async function getCollectionInfo() {
  showStatus("infoStatus", "Loading collection info...", "loading");
  document.getElementById("infoResults").classList.remove("show");

  try {
    const res = await fetch(`${API_BASE}/info`, { headers: authHeaders() });
    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.detail || data.error || `HTTP ${res.status}`);
    }

    showStatus("infoStatus", "Collection loaded", "success");
    document.getElementById("collectionName").innerText = data.collection_name || "mindvault";
    document.getElementById("totalVectors").innerText = data.total_vectors;
    document.getElementById("collectionStatus").innerText = (data.status || "").toUpperCase();
    document.getElementById("infoResults").classList.add("show");
  } catch (error) {
    showStatus("infoStatus", `Connection error: ${error.message}`, "error");
  }
}