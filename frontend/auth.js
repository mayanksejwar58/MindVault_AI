const API_BASE = window.location.origin;
const THEME_KEY = "mindvault_theme";

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_KEY, theme);
  const btn = document.getElementById("themeBtn");
  if (btn) {
    btn.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
  }
}

function toggleTheme() {
  const current = localStorage.getItem(THEME_KEY) || "dark";
  applyTheme(current === "dark" ? "light" : "dark");
}

applyTheme(localStorage.getItem(THEME_KEY) || "dark");

if (
  localStorage.getItem("token") &&
  (window.location.pathname.endsWith("login.html") || window.location.pathname.endsWith("signup.html"))
) {
  window.location.href = "index.html";
}

async function signup() {
  const email = document.getElementById("email").value.trim();
  const pass = document.getElementById("password").value;
  const confirm = document.getElementById("confirm").value;

  if (!email || !pass || !confirm) {
    alert("Please fill all fields");
    return;
  }

  if (pass !== confirm) {
    alert("Passwords do not match");
    return;
  }

  const res = await fetch(`${API_BASE}/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: pass }),
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    alert(data.detail || "Signup failed");
    return;
  }

  alert("Signup successful");
  window.location.href = "login.html";
}

async function login() {
  const email = document.getElementById("email").value.trim();
  const pass = document.getElementById("password").value;

  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: pass }),
  });

  const data = await res.json().catch(() => ({}));

  if (res.ok && data.access_token) {
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("email", email);
    window.location.href = "index.html";
  } else {
    alert(data.detail || "Login failed");
  }
}

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("email");
  window.location.href = "login.html";
}

window.toggleTheme = toggleTheme;