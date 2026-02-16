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

        ///////////////// Move_to Functionality /////////////////////
        document.querySelectorAll(".moveto-control-panel").forEach(panel => {
            const device = panel.getAttribute("control-device");
            if (!device) return;

            const xEl = panel.querySelector(".moveto-x");
            const yEl = panel.querySelector(".moveto-y");
            const zEl = panel.querySelector(".moveto-z");
            const vEl = panel.querySelector(".moveto-v");
            const send_btn = panel.querySelector(".moveto-send");
            const home_btn = panel.querySelector(".moveto-home");
            const calibrate_btn = panel.querySelector(".moveto-calibrate");
            const standby_btn = panel.querySelector(".moveto-standby");

            const status = panel.querySelector(".moveto-status");

            const curX = panel.querySelector(".moveto-cur-x");
            const curY = panel.querySelector(".moveto-cur-y");
            const curZ = panel.querySelector(".moveto-cur-z");
            const curStale = panel.querySelector(".moveto-cur-stale");
            const curTs = panel.querySelector(".moveto-cur-ts");
            
            const POLL_MS = 1000; // 1 Hz

            let standbyOn = false;

            function updateStandbyUI(){
                standby_btn.textContent = standbyOn ? "Standby: ON" : "Standby: OFF";
                standby_btn.classList.toggle("is-on", standbyOn);
            }

            async function pollPose() {
                try {
                const res = await fetch(`/spatial/processed_data?device=${encodeURIComponent(device)}`, {
                    cache: "no-store"
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);

                const json = await res.json();

                const pose = json?.pose_data;
                const ts = json?.timestamp;

                const x = pose?.x;
                const y = pose?.y;
                const z = pose?.z;
                const stale = !!pose?.pose_is_stale;

                standbyOn = !!pose?.standby_mode;
                updateStandbyUI();

                curX.textContent = (x === null || x === undefined) ? "—" : Number(x).toFixed(2);
                curY.textContent = (y === null || y === undefined) ? "—" : Number(y).toFixed(2);
                curZ.textContent = (z === null || z === undefined) ? "—" : Number(z).toFixed(2);

                // curX.textContent = Number.isFinite(Number(x)) ? Number(x).toFixed(2) : "—";
                // curY.textContent = Number.isFinite(Number(y)) ? Number(y).toFixed(2) : "—";
                // curZ.textContent = Number.isFinite(Number(z)) ? Number(z).toFixed(2) : "—";

                curStale.textContent = stale ? " (STALE)" : " (OK)";
                curStale.style.opacity = stale ? "1" : "0.7";

                curTs.textContent = ts ? ` @ ${ts}` : "";
                } catch (err) {
                // optional: show fetch error in the stale field
                curStale.textContent = ` (fetch error)`;
                curTs.textContent = "";
                }
            }


            pollPose();
            setInterval(pollPose, POLL_MS);
            updateStandbyUI();



            function setStatus(msg){
                if (status) status.textContent = msg;
            }

            function parseNum(el){
                const v = el.value.trim();
                if (v === "") return null;
                const n = Number(v);
                return Number.isFinite(n) ? n : null;
            }

            send_btn.addEventListener("click", () => {
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
                v,
                command:"move_to",
                ts: Date.now()
                };

                console.log("⬆️ emitting platform_command_parser:", payload);
                socket.emit("platform_command_parser", payload);
                setStatus(`sent (${x}, ${y}, ${z}) @ ${v} mm/s`);
            });

            home_btn.addEventListener("click", () => {
                if (!device){
                setStatus("missing device");
                return;
                }

                const payload = {
                device,
                command:"home",
                ts: Date.now()
                };

                console.log("⬆️ emitting platform_command_parser:", payload);
                socket.emit("platform_command_parser", payload);
                setStatus(`sent (default home position`);
            });

            calibrate_btn.addEventListener("click", () => {
                if (!device){
                setStatus("missing device");
                return;
                }

                const payload = {
                device,
                command:"home_calibrate",
                ts: Date.now()
                };

                console.log("⬆️ emitting platform_command_parser:", payload);
                socket.emit("platform_command_parser", payload);
                setStatus(`sent (calibration`);
            });

            standby_btn.addEventListener("click", () => {
                if (!device){
                setStatus("missing device");
                return;
                }

                standbyOn = !standbyOn;
                updateStandbyUI();

                const payload = {
                device,
                command:"standby",
                state:standbyOn,
                ts: Date.now()
                };

                console.log("⬆️ emitting platform_command_parser:", payload);
                socket.emit("platform_command_parser", payload);
                setStatus(`sent (standby`);
            });

            // Press Enter to send
            [xEl, yEl, zEl, vEl].forEach(el => {
                el.addEventListener("keydown", (e) => {
                if (e.key === "Enter") send_btn.click();
                });
            });
        
        });

        ///////////////// Teach pendant Functionality /////////////////////

        document.querySelectorAll(".teach-panel").forEach(panel => {
            const device = panel.getAttribute("control-device");
            const rowsTbody = panel.querySelector(".teach-rows");
            const startBtn = panel.querySelector(".teach-start");
            const stopBtn = panel.querySelector(".teach-stop");
            const saveBtn = panel.querySelector(".teach-savejson");
            const statusEl = panel.querySelector(".teach-status");

            const curX = panel.querySelector(".teach-cur-x");
            const curY = panel.querySelector(".teach-cur-y");
            const curZ = panel.querySelector(".teach-cur-z");
            const curStale = panel.querySelector(".teach-cur-stale");
            const curTs = panel.querySelector(".teach-cur-ts");

            let teaching = false;
            let activeRowId = null;
            let lastPose = { x: null, y: null, z: null, pose_is_stale: true, ts: null };

            const sequence = []; // array of {x,y,z,v, ts, note?}
            const POLL_MS = 1000;

            function setStatus(msg){ statusEl.textContent = msg || ""; }

            function fmt(n){
                return (n === null || n === undefined) ? "—" : Number(n).toFixed(2);
            }

            function updateCurrentPoseUI(pose, ts){
                curX.textContent = fmt(pose?.x);
                curY.textContent = fmt(pose?.y);
                curZ.textContent = fmt(pose?.z);

                const stale = !!pose?.pose_is_stale;
                curStale.textContent = stale ? " (STALE)" : " (OK)";
                curStale.style.opacity = stale ? "1" : "0.7";
                curTs.textContent = ts ? `@ ${ts}` : "";
            }

            function createRow(index){
                const tr = document.createElement("tr");
                tr.dataset.follow = "1";
                const rowId = (window.crypto && crypto.randomUUID)
                    ? crypto.randomUUID()
                    : "row_" + Date.now() + "_" + Math.floor(Math.random() * 1000000);

                tr.dataset.rowId = rowId;

                tr.innerHTML = `
                    <td>${index + 1}</td>
                    <td><input class="tx" type="number" step="1" placeholder="mm"></td>
                    <td><input class="ty" type="number" step="1" placeholder="mm"></td>
                    <td><input class="tz" type="number" step="1" placeholder="mm"></td>
                    <td><input class="tv" type="number" step="1" min="0" placeholder="mm/s" value="50"></td>
                    <td>
                    <button class="teach-btn save-pos">Save Position</button>
                    <button class="teach-btn del-pos">Delete</button>
                    </td>
                `;

                const savePosBtn = tr.querySelector(".save-pos");
                const delBtn = tr.querySelector(".del-pos");

                // If user edits X/Y/Z manually, stop follow mode
                [".tx", ".ty", ".tz"].forEach(sel => {
                    const input = tr.querySelector(sel);
                    input.addEventListener("input", () => {
                        tr.dataset.follow = "0";
                    });
                });

                savePosBtn.addEventListener("click", () => {
                    if (!teaching) return;

                    const x = Number(tr.querySelector(".tx").value);
                    const y = Number(tr.querySelector(".ty").value);
                    const z = Number(tr.querySelector(".tz").value);
                    const v = Number(tr.querySelector(".tv").value);

                    if (![x,y,z,v].every(Number.isFinite)) {
                        setStatus("Enter valid numbers before saving.");
                        return;
                    }
                    if (v <= 0) {
                        setStatus("Velocity must be > 0.");
                        return;
                    }

                    // lock row
                    lockRow(tr);

                    // persist into sequence at this index
                    const allRows = Array.from(rowsTbody.querySelectorAll("tr"));
                    const idx = allRows.indexOf(tr);

                    sequence[idx] = { x, y, z, v };
                    // sequence[idx] = { x, y, z, v, saved_at: new Date().toISOString() };
                    setStatus(`Saved position #${idx+1}: (${x}, ${y}, ${z}) @ ${v} mm/s`);

                    // auto-create next row
                    addNewActiveRow();
                });

                delBtn.addEventListener("click", () => {
                    // delete row + shift sequence
                    const rid = tr.dataset.rowId;
                    const allRows = Array.from(rowsTbody.querySelectorAll("tr"));
                    const idx = allRows.findIndex(r => r.dataset.rowId === rid);
                    if (idx >= 0) {
                    allRows[idx].remove();
                    sequence.splice(idx, 1);
                    renumberRows();

                    // if deleted row was active, pick last row as active (or none)
                    if (activeRowId === rid) {
                        activeRowId = null;
                        const remaining = rowsTbody.querySelectorAll("tr");
                        if (remaining.length) setActiveRow(remaining[remaining.length - 1]);
                    }
                    }
                });

                return tr;
            }

            function lockRow(tr){
                tr.classList.add("teach-row-locked");
                tr.classList.remove("teach-row-active");
                tr.querySelectorAll("input").forEach(inp => inp.disabled = true);
                tr.querySelector(".save-pos").disabled = true;
            }

            function setActiveRow(tr){
                rowsTbody.querySelectorAll("tr").forEach(r => r.classList.remove("teach-row-active"));
                tr.classList.add("teach-row-active");
                activeRowId = tr.dataset.rowId;
            }

            function addNewActiveRow(){
                const index = rowsTbody.querySelectorAll("tr").length;
                const tr = createRow(index);
                rowsTbody.appendChild(tr);
                setActiveRow(tr);

                // Immediately populate from latest pose if we have it
                // if (lastPose.x !== null) autopopulateActiveRow();
                autopopulateActiveRow();
                saveBtn.disabled = false;
            }

            function renumberRows(){
            Array.from(rowsTbody.querySelectorAll("tr")).forEach((tr, i) => {
                tr.children[0].textContent = String(i + 1);
            });
            }

            function autopopulateActiveRow() {
                if (!teaching || !activeRowId) return;
                
                // Optional safety: don’t fill if pose is stale
                // if (lastPose.pose_is_stale) return;

                if (![lastPose.x, lastPose.y, lastPose.z].every(Number.isFinite)) return;

                const tr = rowsTbody.querySelector(`tr[data-row-id="${activeRowId}"]`);
                if (!tr) return;

                // Only update if still in follow mode
                if (tr.dataset.follow !== "1") return;

                tr.querySelector(".tx").value = lastPose.x.toFixed(2);
                tr.querySelector(".ty").value = lastPose.y.toFixed(2);
                tr.querySelector(".tz").value = lastPose.z.toFixed(2);
            }

            function startTeaching(){
            teaching = true;
            startBtn.disabled = true;
            stopBtn.disabled = false;
            saveBtn.disabled = false;
            setStatus("Teaching started. Move robot, row will auto-fill, then click Save Position.");

            // start with fresh table
            rowsTbody.innerHTML = "";
            sequence.length = 0;
            activeRowId = null;

            addNewActiveRow();
            }

            function stopTeaching(){
            teaching = false;
            startBtn.disabled = false;
            stopBtn.disabled = true;
            setStatus("Teaching stopped.");
            // keep rows as-is
            }

            async function saveSequenceToServer() {
                const cleaned = sequence.filter(p => p && Number.isFinite(p.x));

                if (cleaned.length === 0) {
                    setStatus("No points to save.");
                    return;
                }

                const payload = {
                    device,
                    created_at: new Date().toISOString(),
                    points: cleaned
                };

                try {
                    const res = await fetch(`/spatial/motion_routine/${device}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload)
                    });

                    if (!res.ok) {
                    const text = await res.text();
                    throw new Error(`Server error: ${text}`);
                    }

                    const json = await res.json();
                    // const res_msg=JSON.stringify(json)
                    setStatus(`Sequence saved successfully (${json.points_saved}).`);

                } catch (err) {
                    setStatus(`Save failed: ${err.message}`);
                }
            }


            startBtn.addEventListener("click", startTeaching);
            stopBtn.addEventListener("click", stopTeaching);
            saveBtn.addEventListener("click", saveSequenceToServer);

            async function pollPose() {
            try {
                const res = await fetch(`/spatial/processed_data?device=${encodeURIComponent(device)}`, {
                cache: "no-store"
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);

                const json = await res.json();

                const pose = json?.pose_data;
                const ts = json?.timestamp;

                const x = pose?.x;
                const y = pose?.y;
                const z = pose?.z;
                const stale = !!pose?.pose_is_stale;

                curX.textContent = (x === null || x === undefined) ? "—" : Number(x).toFixed(2);
                curY.textContent = (y === null || y === undefined) ? "—" : Number(y).toFixed(2);
                curZ.textContent = (z === null || z === undefined) ? "—" : Number(z).toFixed(2);

                // curX.textContent = Number.isFinite(Number(x)) ? Number(x).toFixed(2) : "—";
                // curY.textContent = Number.isFinite(Number(y)) ? Number(y).toFixed(2) : "—";
                // curZ.textContent = Number.isFinite(Number(z)) ? Number(z).toFixed(2) : "—";

                curStale.textContent = stale ? " (STALE)" : " (OK)";
                curStale.style.opacity = stale ? "1" : "0.7";
                curTs.textContent = ts ? ` @ ${ts}` : "";

                lastPose = {
                            x: (x === null || x === undefined) ? null : Number(x),
                            y: (y === null || y === undefined) ? null : Number(y),
                            z: (z === null || z === undefined) ? null : Number(z),
                            pose_is_stale: stale,
                            ts
                        };
                autopopulateActiveRow();   // fills current active teach row

            } catch (err) {
                curStale.textContent = ` (fetch error)`;
                curTs.textContent = "";
            }
            }

            pollPose();
            setInterval(pollPose, POLL_MS);


            // Initialize UI
            updateCurrentPoseUI({x:null,y:null,z:null,pose_is_stale:true}, null);
            saveBtn.disabled = true;
            stopBtn.disabled = true;
        });




    }
});