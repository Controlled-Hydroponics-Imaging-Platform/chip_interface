window.pluginRegistry = window.pluginRegistry || [];
window.pluginRegistry.push({
  name: "atmino",
  init: function () {
    if (typeof socket === "undefined") {
      console.warn("[atmino] socket.io client not found");
      return;
    }

    // Collect all device names present in the DOM
    const devices = new Set();
    document.querySelectorAll("[data-device]").forEach(el => {
      const name = el.dataset.device?.trim();
      if (name) devices.add(name);
    });
    if (devices.size === 0) {
      console.warn("[atmino] No elements with data-device");
      return;
    }

    // Map per device: { statusEl, msgEl, lastSeenTs }
    const state = {};
    const STALE_MS = 30_000;   // mark disconnected if no events for 30s
    const now = () => Date.now();

    // Helpers
    function setStatus(deviceName, text, cls) {
      const s = state[deviceName];
      if (!s || !s.statusEl) return;
      s.statusEl.textContent = text;
      s.statusEl.classList.remove("connected", "disconnected");
      if (cls) s.statusEl.classList.add(cls);
    }
    function bumpSeen(deviceName) {
      const s = state[deviceName];
      if (s) s.lastSeenTs = now();
    }

    // Initialize per-device elements and default status
    devices.forEach(deviceName => {
      const statusEl = document.querySelector(`.mqtt-status[data-device="${deviceName}"]`);
      const msgEl    = document.querySelector(`.mqtt-message[data-device="${deviceName}"]`);
      if (!statusEl || !msgEl) {
        console.warn(`[atmino] Missing containers for ${deviceName}`);
        return;
      }
      state[deviceName] = { statusEl, msgEl, lastSeenTs: 0 };

      // Default status on page load
      setStatus(deviceName, "Connecting...", null);
    });

    // Per-device handlers
    devices.forEach(deviceName => {
      const s = state[deviceName];
      if (!s) return;

      // STATUS UPDATES from backend
      socket.on(`${deviceName}_status_update`, data => {
        const broker = data?.broker ? ` (${data.broker})` : "";
        const status = data?.status || "unknown";
        if (status === "connected") {
          setStatus(deviceName, `Connected${broker}`, "connected");
        } else if (status === "connecting") {
          setStatus(deviceName, `Connecting${broker}...`, null);
        } else if (status === "disconnected") {
          setStatus(deviceName, `Disconnected${broker}`, "disconnected");
        } else if (status === "error") {
          const err = data?.error ? `: ${data.error}` : "";
          setStatus(deviceName, `Error${broker}${err}`, "disconnected");
        } else {
          setStatus(deviceName, `Status${broker}: ${status}`, null);
        }
        bumpSeen(deviceName);
      });

      // DATA UPDATES imply device is alive -> mark connected if not already
      socket.on(`${deviceName}_mqtt_update`, packet => {
        const topic = packet?.topic || "";
        const timestamp = packet?.timestamp || "";
        let payload = packet?.data;

        // Normalize possible string payloads
        if (typeof payload === "string") {
          let stext = payload.trim();
          if (topic && stext.startsWith(topic)) {
            stext = stext.slice(topic.length).trim();
          }
          const cleaned = stext
            .replace(/\bNaN\b/gi, "null")
            .replace(/\bInfinity\b/gi, "null")
            .replace(/\b-Infinity\b/gi, "null");
          if (cleaned.startsWith("{") || cleaned.startsWith("[")) {
            try { payload = JSON.parse(cleaned); } catch { payload = stext; }
          } else {
            payload = stext;
          }
        }

        // Render
        const msgEl = s.msgEl;
        msgEl.innerHTML = "";
        if (payload && typeof payload === "object" && !Array.isArray(payload)) {
          const list = document.createElement("div");
          list.className = "kv-list";
          Object.entries(payload).forEach(([k, v]) => {
            const row = document.createElement("div");
            row.className = "kv-row";
            row.innerHTML = `<span class="k">${escapeHtml(k)}</span><span class="v">${formatVal(v)}</span>`;
            list.appendChild(row);
          });
          msgEl.appendChild(list);
        } else if (Array.isArray(payload)) {
          const pre = document.createElement("pre");
          pre.textContent = JSON.stringify(payload, null, 2);
          msgEl.appendChild(pre);
        } else {
          const pre = document.createElement("pre");
          pre.textContent = String(payload ?? "");
          msgEl.appendChild(pre);
        }
        const meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent = `topic: ${topic}${timestamp ? " | " + timestamp : ""}`;
        msgEl.appendChild(meta);

        // If we never saw a status yet, treat data as connected signal
        if (!s.statusEl.classList.contains("connected")) {
          setStatus(deviceName, "Connected", "connected");
        }
        bumpSeen(deviceName);
      });
    });

    // Socket transport hooks as a fallback
    socket.on("connect", () => {
      devices.forEach(name => {
        // Transport connected doesn't guarantee MQTT connected,
        // but show "Connecting..." until we see a device event.
        setStatus(name, "Connecting...", null);
      });
    });
    socket.on("disconnect", () => {
      devices.forEach(name => {
        setStatus(name, "Disconnected (socket)", "disconnected");
      });
    });

    // Watchdog to mark devices disconnected if stale
    setInterval(() => {
      const t = now();
      devices.forEach(name => {
        const s = state[name];
        if (!s) return;
        if (s.lastSeenTs === 0) return; // no events yet
        if (t - s.lastSeenTs > STALE_MS) {
          setStatus(name, "Disconnected (timeout)", "disconnected");
        }
      });
    }, 5000);

    // Helpers
    function escapeHtml(str) {
      return String(str)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }
    function formatVal(v) {
      if (v === null) return "null";
      if (typeof v === "number") {
        return Number.isFinite(v) ? String(Math.round(v * 10000) / 10000) : String(v);
      }
      if (typeof v === "object") {
        try { return escapeHtml(JSON.stringify(v)); } catch { return "[unserializable]"; }
      }
      return escapeHtml(String(v));
    }
  }
});
