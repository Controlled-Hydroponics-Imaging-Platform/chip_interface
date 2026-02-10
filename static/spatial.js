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
                    setStatus(deviceName, `Connected ${deviceName}`, "connected");
                } else if (status === "connecting") {
                    setStatus(deviceName, `Connecting ${deviceName}...`, null);
                } else if (status === "disconnected") {
                    setStatus(deviceName, `Disconnected ${deviceName}`, "disconnected");
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

        ///////////////// Motion Joystick Functionality /////////////////////

        document.querySelectorAll(".joystick-control-panel").forEach((panel) => {
        const device = panel.getAttribute("joystick-control-device");
        if (!device) {
            console.warn("Missing joystick-control-device on panel", panel);
            return;
        }

        const joy  = panel.querySelector(".joy");
        const knob = panel.querySelector(".knob");
        const out  = panel.querySelector(".out");
        const btn  = panel.querySelector(".joyToggle");
        const zUp  = panel.querySelector(".z-up");
        const zDown= panel.querySelector(".z-down");

        if (!joy || !knob || !out || !btn || !zUp || !zDown) {
            console.warn("Panel missing joystick elements for device:", device);
            return;
        }

        let joystickEnabled = false;
        let sendTimer = null;

        let x = 0, y = 0, z = 0;

        const SEND_HZ = 20;
        const SEND_MS = 1000 / SEND_HZ;

        function deadzone(v, dz = 0.05) {
            return Math.abs(v) < dz ? 0 : v;
        }

        function sendXYZ() {
            
            const payload = {
                device,
                enabled: joystickEnabled,
                x: deadzone(x),
                y: deadzone(y),
                z,
                ts: Date.now()
            };
            // console.log(payload);
            socket.emit("joystick_xyz", payload);
        }

        function startSending() {
            if (sendTimer) return;
            sendTimer = setInterval(sendXYZ, SEND_MS);
            sendXYZ();
        }

        function stopSending() {
            if (sendTimer) {
            clearInterval(sendTimer);
            sendTimer = null;
            }
            x = 0; y = 0; z = 0;
            socket.emit("joystick_xyz", { device, enabled: false, x: 0, y: 0, z: 0, ts: Date.now() });
            updateOutput();
        }

        function updateOutput() {
            out.textContent = `(${device}) x=${x.toFixed(2)} y=${y.toFixed(2)} z=${z.toFixed(2)}`;
        }

        // Toggle button
        btn.addEventListener("click", () => {
            joystickEnabled = !joystickEnabled;
            btn.textContent = joystickEnabled ? "Joystick Mode: ON" : "Joystick Mode: OFF";
            joystickEnabled ? startSending() : stopSending();
        });

        // XY joystick
        const radius = joy.clientWidth / 2;
        const knobR  = knob.clientWidth / 2;
        const max = radius - knobR;

        let active = false, pointerId = null;

        function setKnob(dx, dy) {
            const len = Math.hypot(dx, dy);
            if (len > max) {
            dx = dx / len * max;
            dy = dy / len * max;
            }
            knob.style.transform = `translate(${dx}px, ${dy}px) translate(-50%, -50%)`;
            x = dx / max;
            y = -dy / max;
            updateOutput();
        }

        function center() {
            knob.style.transform = `translate(0px,0px) translate(-50%, -50%)`;
            x = 0; y = 0;
            updateOutput();
        }

        joy.addEventListener("pointerdown", (e) => {
            if (!joystickEnabled) return;
            active = true;
            pointerId = e.pointerId;
            joy.setPointerCapture(pointerId);
        });

        joy.addEventListener("pointermove", (e) => {
            if (!joystickEnabled || !active || e.pointerId !== pointerId) return;
            const r = joy.getBoundingClientRect();
            setKnob(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
        });

        joy.addEventListener("pointerup", (e) => {
            if (e.pointerId !== pointerId) return;
            active = false;
            pointerId = null;
            center();
        });

        joy.addEventListener("pointercancel", center);

        // Z buttons
        function zSet(val) { z = val; updateOutput(); }

        zUp.addEventListener("pointerdown", () => { if (joystickEnabled) zSet(1); });
        zDown.addEventListener("pointerdown", () => { if (joystickEnabled) zSet(-1); });

        ["pointerup", "pointercancel", "pointerleave"].forEach(ev => {
            zUp.addEventListener(ev, () => zSet(0));
            zDown.addEventListener(ev, () => zSet(0));
        });

        updateOutput();
        });


        ///////////////// Move_to Functionality /////////////////////
        document.querySelectorAll(".moveto-control-panel").forEach(panel => {
        const device = panel.getAttribute("control-device");

        const xEl = panel.querySelector(".moveto-x");
        const yEl = panel.querySelector(".moveto-y");
        const zEl = panel.querySelector(".moveto-z");
        const vEl = panel.querySelector(".moveto-v");
        const btn = panel.querySelector(".moveto-send");
        const status = panel.querySelector(".moveto-status");

        function setStatus(msg){
            if (status) status.textContent = msg;
        }

        function parseNum(el){
            const v = el.value.trim();
            if (v === "") return null;
            const n = Number(v);
            return Number.isFinite(n) ? n : null;
        }

        btn.addEventListener("click", () => {
            if (!device){
            setStatus("missing device");
            return;
            }

            const x = parseNum(xEl);
            const y = parseNum(yEl);
            const z = parseNum(zEl);
            const v = parseNum(vEl);   // velocity mm/s

            if (x === null || y === null || z === null || v === null){
            setStatus("enter valid x y z v");
            return;
            }
            if (v <= 0){
            setStatus("velocity must be > 0");
            return;
            }

            const payload = {
            device,
            x, y, z,
            v,              // mm/s
            ts: Date.now()
            };

            console.log("⬆️ emitting moveto_xyzv:", payload);
            socket.emit("moveto_xyzv", payload);
            setStatus(`sent (${x}, ${y}, ${z}) @ ${v} mm/s`);
        });

        // Press Enter to send
        [xEl, yEl, zEl, vEl].forEach(el => {
            el.addEventListener("keydown", (e) => {
            if (e.key === "Enter") btn.click();
            });
        });
        });

    }
});