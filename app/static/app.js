(function () {
  const GRID_SIZE = 30;
  const SCREENS = ["name", "play", "over", "leaderboard"];
  const VALID_NAME_RE = /^[\p{L}\p{N} _\-]+$/u;

  const canvas = document.getElementById("game-canvas");
  const ctx = canvas.getContext("2d");
  const cellSize = canvas.width / GRID_SIZE;

  const nameInput = document.getElementById("name-input");
  const nameError = document.getElementById("name-error");
  const startBtn = document.getElementById("start-btn");
  const againBtn = document.getElementById("again-btn");
  const scoreLine = document.getElementById("score-line");
  const pausedLine = document.getElementById("paused-line");
  const overScore = document.getElementById("over-score");
  const overReason = document.getElementById("over-reason");
  const overRank = document.getElementById("over-rank");
  const lbBody = document.querySelector("#lb-table tbody");
  const lbEmpty = document.getElementById("lb-empty");
  const langSelect = document.getElementById("lang-select");

  let ws = null;
  let lastState = null;
  let lastGameOver = null;
  let storedName = localStorage.getItem("playerName") || "";
  nameInput.value = storedName;

  // ---- i18n bootstrap ----
  const initialLang = window.i18n.detectLang();
  langSelect.value = initialLang;
  window.i18n.setLang(initialLang);
  langSelect.addEventListener("change", function () { window.i18n.setLang(langSelect.value); });
  document.addEventListener("langchange", function () {
    refreshDynamicTexts();
    if (currentScreen() === "leaderboard") loadLeaderboard();
  });

  // ---- router ----
  function currentScreen() {
    const hash = location.hash.replace(/^#\//, "");
    return SCREENS.indexOf(hash) >= 0 ? hash : "name";
  }
  function showScreen(name) {
    for (const id of SCREENS) {
      document.getElementById("screen-" + id).hidden = id !== name;
    }
    for (const link of document.querySelectorAll("nav a")) {
      link.classList.toggle("active", link.getAttribute("href") === "#/" + name);
    }
    if (name !== "play") disconnect();
    if (name === "play") onEnterPlay();
    if (name === "over") onEnterOver();
    if (name === "leaderboard") loadLeaderboard();
  }
  function navigate(name) {
    if (location.hash !== "#/" + name) location.hash = "#/" + name;
    else showScreen(name);
  }
  window.addEventListener("hashchange", function () { showScreen(currentScreen()); });

  // ---- name screen ----
  function validateName(name) {
    const trimmed = name.trim();
    if (!trimmed) return "name.error_empty";
    if (trimmed.length > 20) return "name.error_too_long";
    if (!VALID_NAME_RE.test(trimmed)) return "name.error_invalid_chars";
    return null;
  }
  startBtn.addEventListener("click", function () {
    const err = validateName(nameInput.value);
    if (err) {
      nameError.textContent = window.i18n.t(err);
      nameError.hidden = false;
      return;
    }
    nameError.hidden = true;
    storedName = nameInput.value.trim();
    localStorage.setItem("playerName", storedName);
    navigate("play");
  });
  againBtn.addEventListener("click", function () { navigate("play"); });

  // ---- play screen ----
  function onEnterPlay() {
    if (!storedName) { navigate("name"); return; }
    connectAndStart();
  }

  function connectAndStart() {
    disconnect();
    paused = false;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(proto + "//" + location.host + "/ws/play");
    ws.addEventListener("open", function () {
      ws.send(JSON.stringify({ type: "start", name: storedName }));
    });
    ws.addEventListener("message", function (ev) {
      const msg = JSON.parse(ev.data);
      if (msg.type === "state") {
        lastState = msg;
        render(msg);
      } else if (msg.type === "game_over") {
        lastGameOver = msg;
        navigate("over");
      } else if (msg.type === "error") {
        console.warn("server error:", msg.message);
      }
    });
    ws.addEventListener("close", function () { ws = null; });
  }
  function disconnect() {
    if (ws && ws.readyState <= 1) { try { ws.close(); } catch (e) {} }
    ws = null;
  }

  // ---- renderer ----
  function render(state) {
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (const cell of state.bad) {
      drawCell(cell[0], cell[1], "#4c1d95");
      ctx.fillStyle = "#e2e8f0";
      ctx.font = Math.floor(cellSize * 0.7) + "px " + getComputedStyle(document.body).fontFamily;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("✕", cell[0] * cellSize + cellSize / 2, cell[1] * cellSize + cellSize / 2 + 1);
    }
    drawCell(state.apple[0], state.apple[1], "#ef4444");
    for (let i = 0; i < state.snake.length; i++) {
      const c = state.snake[i];
      const isHead = i === state.snake.length - 1;
      drawCell(c[0], c[1], isHead ? "#bef264" : "#84cc16");
    }
    scoreLine.textContent = window.i18n.t("play.score", { score: state.score });
    pausedLine.hidden = !state.paused;
  }
  function drawCell(x, y, color) {
    ctx.fillStyle = color;
    const pad = 1;
    ctx.fillRect(x * cellSize + pad, y * cellSize + pad, cellSize - 2 * pad, cellSize - 2 * pad);
  }

  // ---- input ----
  const KEY_DIR = {
    ArrowUp: "up", w: "up", W: "up",
    ArrowDown: "down", s: "down", S: "down",
    ArrowLeft: "left", a: "left", A: "left",
    ArrowRight: "right", d: "right", D: "right",
  };
  let paused = false;
  document.addEventListener("keydown", function (e) {
    if (currentScreen() !== "play" || !ws || ws.readyState !== 1) return;
    if (e.key === " " || e.key === "Spacebar") {
      paused = !paused;
      ws.send(JSON.stringify({ type: paused ? "pause" : "resume" }));
      e.preventDefault();
      return;
    }
    const dir = KEY_DIR[e.key];
    if (dir) {
      ws.send(JSON.stringify({ type: "input", dir: dir }));
      e.preventDefault();
    }
  });

  // ---- game over screen ----
  function onEnterOver() {
    if (!lastGameOver) { navigate("name"); return; }
    overScore.textContent = window.i18n.t("over.score", { score: lastGameOver.score });
    overReason.textContent = window.i18n.t("over.reason_" + lastGameOver.reason);
    overRank.textContent = lastGameOver.rank
      ? window.i18n.t("over.rank", { rank: lastGameOver.rank })
      : window.i18n.t("over.no_rank");
  }

  // ---- leaderboard ----
  async function loadLeaderboard() {
    const resp = await fetch("/leaderboard");
    const rows = await resp.json();
    while (lbBody.firstChild) lbBody.removeChild(lbBody.firstChild);
    lbEmpty.hidden = rows.length > 0;
    rows.forEach(function (r, idx) {
      const tr = document.createElement("tr");
      const td1 = document.createElement("td");
      const td2 = document.createElement("td");
      const td3 = document.createElement("td");
      td1.textContent = String(idx + 1);
      td2.textContent = r.name;
      td3.textContent = String(r.score);
      tr.appendChild(td1);
      tr.appendChild(td2);
      tr.appendChild(td3);
      lbBody.appendChild(tr);
    });
  }

  function refreshDynamicTexts() {
    if (lastState) {
      scoreLine.textContent = window.i18n.t("play.score", { score: lastState.score });
    }
    if (lastGameOver && currentScreen() === "over") onEnterOver();
  }

  // ---- boot ----
  showScreen(currentScreen());
})();
