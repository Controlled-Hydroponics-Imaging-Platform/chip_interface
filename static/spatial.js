window.pluginRegistry = window.pluginRegistry || [];
window.pluginRegistry.push({
    name: "spatial",
    init: function () {
        if (typeof socket === "undefined") {
            console.warn("[spatial] socket.io client not found");
            return;
        }
        
        // Collect all device names present in the DOM
        const devices = new Set();
        document.querySelectorAll("[data-device]").forEach(el => {
            const name = el.dataset.device?.trim();
            if (name) devices.add(name);
        });
        if (devices.size === 0) {
            console.warn("[spatial] No elements with data-device");
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
            const statusEl = document.querySelector(`.motion-status[data-device="${deviceName}"]`);
            const msgEl    = document.querySelector(`.motion-message[data-device="${deviceName}"]`);
            if (!statusEl || !msgEl) {
                console.warn(`[spatial] Missing containers for ${deviceName}`);
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
                // const broker = data?.broker ? ` (${data.broker})` : "";
                const status = data?.status || "unknown";
                if (status === "connected") {
                    setStatus(deviceName, `Connected${deviceName}`, "connected");
                } else if (status === "connecting") {
                    setStatus(deviceName, `Connecting${deviceName}...`, null);
                } else if (status === "disconnected") {
                    setStatus(deviceName, `Disconnected${deviceName}`, "disconnected");
                } else if (status === "error") {
                const err = data?.error ? `: ${data.error}` : "";
                    setStatus(deviceName, `Error${deviceName}${err}`, "disconnected");
                } else {
                    setStatus(deviceName, `Status${deviceName}: ${status}`, null);
                }
                bumpSeen(deviceName);
            });

            // DATA UPDATES imply device is alive -> mark connected if not already
            socket.on(`${deviceName}_sensor_update`, packet => {
                // const topic = packet?.topic || "";
                const timestamp = packet?.timestamp || "";
                let payload = packet?.data;

                // Normalize possible string payloads
                if (typeof payload === "string") {
                    let stext = payload.trim();
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
                    const axes = Object.keys(payload); // ["x","y","z"]

                    // Collect all field names (direction, position_rev, ...)
                    const fields = new Set();
                    axes.forEach(axis => {
                        Object.keys(payload[axis] || {}).forEach(f => fields.add(f));
                    });

                    const table = document.createElement("div");
                    table.className = "axis-table";

                    // Header row
                    const header = document.createElement("div");
                    header.className = "axis-row axis-header";
                    header.innerHTML =
                        `<span class="axis-label"></span>` +
                        axes.map(a => `<span class="axis-col">${escapeHtml(a)}</span>`).join("");
                    table.appendChild(header);

                    // Data rows
                    fields.forEach(field => {
                        const row = document.createElement("div");
                        row.className = "axis-row";

                        const label = `<span class="axis-label">${escapeHtml(field)}</span>`;
                        const cols = axes.map(axis => {
                            const val = payload[axis]?.[field];
                            return `<span class="axis-col">${formatVal(val)}</span>`;
                        }).join("");

                        row.innerHTML = label + cols;
                        table.appendChild(row);
                    });

                    msgEl.appendChild(table);

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
                // meta.textContent = `topic: ${topic}${timestamp ? " | " + timestamp : ""}`;
                meta.textContent = `${timestamp ? timestamp : ""}`;
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