/**
 * Bloom filter demo UI: stats, add/check flows, bit grid visualization.
 */

const API =
  typeof window.__BF_API === "object" && window.__BF_API !== null
    ? window.__BF_API
    : {
        stats: "/stats",
        previewBits: "/preview_bits",
        add: "/add",
        check: "/check",
      };

const $ = (id) => document.getElementById(id);

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function clearSteps() {
  $("steps-log").innerHTML = "";
}

function pushStep(text, done = false) {
  const ol = $("steps-log");
  const li = document.createElement("li");
  li.textContent = text;
  if (done) li.classList.add("done");
  ol.appendChild(li);
  return li;
}

function markStepDone(li) {
  if (li) li.classList.add("done");
}

function formatBytes(num) {
  if (num == null || Number.isNaN(num)) return "-";
  const n = Number(num);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MiB`;
}

function storageBackendLabel(backend) {
  if (backend === "bitarray") return "bitarray buffer";
  if (backend === "python_list") return "Python list fallback";
  return backend || "";
}

function renderStats(data) {
  const ul = $("stats-list");
  ul.innerHTML = "";
  const memBytes = data.bloom_filter_memory_bytes_approx;
  const memBackend = storageBackendLabel(data.bloom_filter_storage_backend);
  const memLine =
    memBytes != null
      ? `${formatBytes(memBytes)} <span class="stats-detail">(${memBackend}, approx.)</span>`
      : "-";
  const csvBytes = data.users_csv_bytes;
  const csvLine =
    csvBytes != null
      ? `${formatBytes(csvBytes)} <span class="stats-detail">(users.csv on disk)</span>`
      : '<span class="stats-detail">users.csv not found</span>';
  const rows = [
    ["Users in set (unique)", data.total_users_inserted ?? data.total_keys_in_set],
    ["API add clicks", data.api_add_operations],
    ["Bit array size <em>m</em>", data.bit_array_size_m],
    ["Hash functions <em>k</em>", data.hash_functions_k],
    ["Target FPR", data.target_false_positive_rate],
    ["Estimated FPR (model)", data.estimated_false_positive_rate],
    ["users.csv size", csvLine],
    ["Bloom filter memory", memLine],
  ];
  for (const [label, val] of rows) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${label}:</strong> ${val}`;
    ul.appendChild(li);
  }
}

async function refreshStats() {
  const res = await fetch(API.stats);
  if (!res.ok) return;
  const data = await res.json();
  renderStats(data);
}

function buildBitGrid(bits, activeInFirst200, flippedInFirst200) {
  const grid = $("bit-grid");
  grid.innerHTML = "";
  const active = new Set(activeInFirst200 || []);
  const flipped = new Set(flippedInFirst200 || []);
  bits.forEach((bit, i) => {
    const cell = document.createElement("div");
    cell.className = "bit-cell";
    cell.title = `index ${i} = ${bit}`;
    if (bit) cell.classList.add("on");
    if (active.has(i)) cell.classList.add("active");
    if (flipped.has(i)) cell.classList.add("flipped");
    grid.appendChild(cell);
  });
}

function renderHashCells(cells, mode) {
  const wrap = $("hash-cells");
  wrap.innerHTML = "";
  cells.forEach((c) => {
    const div = document.createElement("div");
    div.className = "hash-cell";
    const vClass = c.value ? "val-1" : "val-0";
    const flip =
      mode === "add" && c.flipped
        ? " <span class='val-1'>(was 0→1)</span>"
        : "";
    div.innerHTML = `<span class="idx">#${c.index}</span><span class="${vClass}">bit ${c.value}</span>${flip}`;
    wrap.appendChild(div);
  });
}

function indicesInFirst200(hashIndices) {
  return hashIndices.filter((i) => i >= 0 && i < 200);
}

/**
 * Short human-readable hash explanation; optional per-bit lines for check.
 */
function renderHashBrief(hb, perBit, mode) {
  const el = $("hash-brief");
  if (!el || !hb || hb.m == null) return;
  const k = hb.k ?? 0;
  const parts = [
    `mmh3 gives two bases: h₁=${hb.h1}, h₂=${hb.h2} (with h₂ tweaked so steps never stall).`,
    `Then k=${k} positions: (h₁ + i·h₂) mod m for i = 0…${k - 1}.`,
    `Indices: ${(hb.indices || []).join(", ")}.`,
  ];
  if (mode === "check" && perBit && perBit.length) {
    const bits = perBit.map((p) => `${p.index}→${p.value}`).join(", ");
    parts.push(`Checked bits: ${bits}.`);
  }
  el.textContent = parts.join(" ");
}

function renderHashRawJson(obj) {
  const pre = $("hash-json");
  if (!pre) return;
  if (obj == null) {
    pre.textContent = "-";
    return;
  }
  pre.textContent = JSON.stringify(obj, null, 2);
}

function setResult(text, kind) {
  const el = $("result-text");
  el.textContent = text;
  el.className = "result-text";
  if (kind === "not") el.classList.add("definite-not");
  if (kind === "maybe") el.classList.add("possible");
  if (kind === "err") el.classList.add("error");
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

async function runAddFlow() {
  const name = $("username").value.trim().toLowerCase();
  if (!name) {
    setResult("Enter a username.", "err");
    return;
  }
  clearSteps();
  setResult("Working…", "");
  $("btn-add").disabled = true;
  $("btn-check").disabled = true;

  const stepHash = pushStep("Hashing (mmh3 → h₁, h₂, then hᵢ = (h₁ + i·h₂) mod m)…");
  await delay(350);
  markStepDone(stepHash);

  const { res, data } = await postJson(API.add, { username: name });
  if (!res.ok || !data.ok) {
    setResult(data.error || "Add failed.", "err");
    $("btn-add").disabled = false;
    $("btn-check").disabled = false;
    return;
  }

  const stepSet = pushStep("Setting bits at hashed indices (0→1 where needed)…");
  await delay(350);
  markStepDone(stepSet);

  const hb = data.hash_breakdown || {};
  renderHashBrief(hb, null, "add");
  renderHashRawJson({
    h1: hb.h1,
    h2: hb.h2,
    m: hb.m,
    k: hb.k,
    indices: hb.indices,
    derived: hb.derived,
  });

  const viz = data.updated_bit_positions || {};
  const first = viz.first_200_bits || [];
  const hashIdx = data.hash_indices || [];
  const flipped = (data.flipped_indices || []).filter((i) => i < 200);

  buildBitGrid(first, indicesInFirst200(hashIdx), flipped);
  renderHashCells(viz.hash_cells || [], "add");

  pushStep("Done - Bloom filter updated.", true);
  setResult(`Added "${data.username}" (may have been already implicitly present).`, "");

  $("btn-add").disabled = false;
  $("btn-check").disabled = false;
  await refreshStats();
}

async function runCheckFlow() {
  const name = $("username").value.trim().toLowerCase();
  if (!name) {
    setResult("Enter a username.", "err");
    return;
  }
  clearSteps();
  setResult("Working…", "");
  $("btn-add").disabled = true;
  $("btn-check").disabled = true;

  const stepHash = pushStep("Hashing the query the same way as on insert…");
  await delay(350);
  markStepDone(stepHash);

  const { res, data } = await postJson(API.check, { username: name });
  if (!res.ok || !data.ok) {
    setResult(data.error || "Check failed.", "err");
    $("btn-add").disabled = false;
    $("btn-check").disabled = false;
    return;
  }

  const stepProbe = pushStep("Checking bits: if any hashed bit is 0 → definitely not in the set.");
  await delay(400);
  markStepDone(stepProbe);

  const hb = data.hash_breakdown || {};
  renderHashBrief(hb, data.per_bit, "check");
  renderHashRawJson({
    h1: hb.h1,
    h2: hb.h2,
    m: hb.m,
    k: hb.k,
    indices: hb.indices,
    per_bit: data.per_bit,
  });

  const viz = data.check_bits || {};
  const first = viz.first_200_bits || [];
  const hashIdx = data.hash_indices || [];
  buildBitGrid(first, indicesInFirst200(hashIdx), []);

  const cells = (viz.hash_cells || []).map((c) => ({ ...c, flipped: false }));
  renderHashCells(cells, "check");

  const definiteNot = data.verdict === "definitely_not_present";
  if (definiteNot) {
    setResult("Definitely Not Present - at least one probed bit was 0.", "not");
    pushStep("Result: ✅ Definitely Not Present", true);
  } else {
    setResult("Possibly Present - all probed bits are 1 (could be a false positive).", "maybe");
    pushStep("Result: ⚠️ Possibly Present", true);
  }

  $("btn-add").disabled = false;
  $("btn-check").disabled = false;
  await refreshStats();
}

function wire() {
  $("btn-add").addEventListener("click", () => runAddFlow());
  $("btn-check").addEventListener("click", () => runCheckFlow());
}

async function boot() {
  wire();
  await refreshStats();
  const r = await fetch(API.previewBits);
  const prev = r.ok ? await r.json() : {};
  const first = prev.first_200_bits || Array(200).fill(0);
  buildBitGrid(first, [], []);
}

boot();
