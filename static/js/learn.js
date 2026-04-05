/**
 * Minimal Add/Check demo for the /learn page (uses same Flask API as main app).
 */

const API =
  typeof window.__BF_API === "object" && window.__BF_API !== null
    ? window.__BF_API
    : { add: "/add", check: "/check" };

function $(id) {
  return document.getElementById(id);
}

function setOut(text) {
  const el = $("learn-demo-out");
  if (el) el.textContent = text;
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

function formatLearnResponse(label, res, data) {
  const status = `${label} - HTTP ${res.status}`;
  try {
    return `${status}\n\n${JSON.stringify(data, null, 2)}`;
  } catch {
    return `${status}\n\n${String(data)}`;
  }
}

async function runAdd() {
  const username = ($("learn-username") && $("learn-username").value.trim().toLowerCase()) || "saurabh";
  setOut("Adding…");
  const { res, data } = await postJson(API.add, { username });
  setOut(formatLearnResponse("Add", res, data));
}

async function runCheck() {
  const username = ($("learn-username") && $("learn-username").value.trim().toLowerCase()) || "saurabh";
  setOut("Checking…");
  const { res, data } = await postJson(API.check, { username });
  setOut(formatLearnResponse("Check", res, data));
}

function wire() {
  const addBtn = $("learn-btn-add");
  const checkBtn = $("learn-btn-check");
  if (addBtn) addBtn.addEventListener("click", () => runAdd());
  if (checkBtn) checkBtn.addEventListener("click", () => runCheck());
}

wire();
