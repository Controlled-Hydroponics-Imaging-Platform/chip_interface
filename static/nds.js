window.pluginRegistry = window.pluginRegistry || [];
window.pluginRegistry.push({
    name: "nds_sensors",
    init: function () {
        console.log("✅ Initializing NDS Sensor Plugin");

        // KASA Control Update Socket Handling
        const controlButtons = document.querySelectorAll(".kasa-toggle-plug");
        controlButtons.forEach(button => {
            const deviceName = button.dataset.device;
            socket.on(`${deviceName}_control_update`, function (data) {
                console.log(`📡 [${deviceName}] Received Data:`, data);
                const isOn = data.data;  // True or False
                updateButtonState(button, isOn);
            });
        });

        // ✅ Start countdown and schedule display per control
        document.querySelectorAll(".kasa-plug-control").forEach(control => {
            const schedule = JSON.parse(control.dataset.schedule || "[]");
            const nextScheduleDiv = control.querySelector(".next-schedule");
            const button = control.querySelector(".kasa-toggle-plug");

            if (schedule.length && nextScheduleDiv) {
                startCountdown(schedule, button, nextScheduleDiv);
            }
        });

        // ✅ Countdown interval with seconds and weekly loop logic
        function startCountdown(schedule, button, nextScheduleDiv) {
            setInterval(() => {
                const isOn = button.classList.contains("on");
                const next = calculateNextEvent(schedule, isOn);

                if (next) {
                    const totalSec = next.inSeconds;
                    const hours = Math.floor(totalSec / 3600);
                    const minutes = Math.floor((totalSec % 3600) / 60);
                    const seconds = Math.floor(totalSec % 60);
                    nextScheduleDiv.innerHTML = `Next ${next.type} in ${hours}h ${minutes}m ${seconds}s`;
                } else {
                    nextScheduleDiv.innerHTML = "No schedule set";
                }
            }, 1000);
        }

        // ✅ Calculates the next ON or OFF based on the button state and loops weekly
        function calculateNextEvent(schedule, currentIsOn) {
            const now = new Date();
            const todayIndex = now.getDay(); // Sunday = 0
            const currentMinutes = now.getHours() * 60 + now.getMinutes();
            const currentSeconds = now.getSeconds();

            let nextEvent = null;
            let minTotalSeconds = Infinity;

            // Scan forward 7 days (weekly loop)
            for (let offset = 0; offset < 7; offset++) {
                const checkDayIndex = (todayIndex + offset) % 7;
                const dayName = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][checkDayIndex];

                schedule.forEach(block => {
                    if (block.days.includes(dayName)) {
                        const startParts = block.start.split(':').map(Number);
                        const endParts = block.end.split(':').map(Number);
                        const startMinutes = startParts[0] * 60 + startParts[1];
                        const endMinutes = endParts[0] * 60 + endParts[1];

                        let startTotalMinutes = startMinutes + (offset * 1440);
                        let endTotalMinutes = endMinutes + (offset * 1440);

                        // Adjust today's events if we're partway through the day
                        if (offset === 0) {
                            if (startMinutes <= currentMinutes) startTotalMinutes += 7 * 1440; // Push to next week
                            if (endMinutes <= currentMinutes) endTotalMinutes += 7 * 1440;   // Push to next week
                        }

                        // Time to turn ON
                        if (!currentIsOn) {
                            const startTotalSeconds = (startTotalMinutes - currentMinutes) * 60 - currentSeconds;
                            if (startTotalSeconds < minTotalSeconds) {
                                minTotalSeconds = startTotalSeconds;
                                nextEvent = { type: "ON", inSeconds: startTotalSeconds };
                            }
                        }

                        // Time to turn OFF
                        if (currentIsOn) {
                            const endTotalSeconds = (endTotalMinutes - currentMinutes) * 60 - currentSeconds;
                            if (endTotalSeconds < minTotalSeconds) {
                                minTotalSeconds = endTotalSeconds;
                                nextEvent = { type: "OFF", inSeconds: endTotalSeconds };
                            }
                        }
                    }
                });
            }

            return nextEvent;
        }

        function updateButtonState(button, isOn) {
            if (isOn) {
                button.textContent = "ON";
                button.classList.add("on");
                button.classList.remove("off");
            } else {
                button.textContent = "OFF";
                button.classList.add("off");
                button.classList.remove("on");
            }
        }

        // ✅ Serial sensor handling
        const sensorDivs = document.querySelectorAll("[id$='_sensors']");
        sensorDivs.forEach(sensorDiv => {
            const deviceName = sensorDiv.id.replace('_sensors', '');
            const statusElem = document.querySelector(`#${deviceName}_status`) || createStatusElement(deviceName);

            let reconnectInterval = null;
            function startReconnectCountdown(seconds) {
                let count = seconds;
                reconnectInterval = setInterval(() => {
                    count -= 1;
                    const countdownElem = statusElem.querySelector('#countdown');
                    if (countdownElem) countdownElem.textContent = count;
                    if (count <= 0) clearInterval(reconnectInterval);
                }, 1000);
            }

            function stopReconnectCountdown() {
                if (reconnectInterval) {
                    clearInterval(reconnectInterval);
                    reconnectInterval = null;
                }
            }

            socket.on(`${deviceName}_status_update`, function (data) {
                const portInfo = data.device ? ` (${data.device})` : "";
                if (data.status === "disconnected") {
                    statusElem.classList.remove('connected');
                    statusElem.classList.add('disconnected');
                    statusElem.innerHTML = `* Device disconnected${portInfo}: Reconnecting in <span id='countdown'>5</span> sec...`;
                    sensorDiv.innerHTML = `⚠️ Disconnected ${portInfo}`;
                    startReconnectCountdown(5);
                } else if (data.status === "connecting") {
                    stopReconnectCountdown();
                    statusElem.classList.remove('connected', 'disconnected');
                    statusElem.innerHTML = `* Connecting to device${portInfo}...`;
                    sensorDiv.innerHTML = `Waiting for response from${portInfo}...`;
                } else if (data.status === "connected") {
                    stopReconnectCountdown();
                    statusElem.classList.remove('disconnected');
                    statusElem.classList.add('connected');
                    statusElem.innerHTML = `* Device Connected${portInfo}`;
                    setTimeout(() => {
                        statusElem.innerText = "";
                        statusElem.classList.remove('connected', 'disconnected');
                    }, 10000);
                }
            });

            socket.on(`${deviceName}_sensor_update`, function (data) {
                console.log(`📡 [${deviceName}] Received Data:`, data);
                sensorDiv.innerHTML = "";
                for (const [key, item] of Object.entries(data.data)) {
                    const line = document.createElement('div');
                    line.classList.add('sensor-item');
                    line.innerHTML = `<strong>${key}</strong>: ${item.value} ${item.unit}`;
                    sensorDiv.appendChild(line);
                }
                const ts = document.createElement('div');
                ts.classList.add('timestamp');
                ts.innerHTML = `<strong>Last updated</strong>: ${data.timestamp}`;
                sensorDiv.appendChild(ts);
            });

            function createStatusElement(deviceName) {
                const statusEl = document.createElement('div');
                statusEl.id = `${deviceName}_status`;
                statusEl.classList.add('connection_status');
                sensorDiv.parentNode.insertBefore(statusEl, sensorDiv);
                return statusEl;
            }
        });
    }
});
