window.pluginRegistry = window.pluginRegistry || [];
window.pluginRegistry.push({
    name: "platform_control",
    init: function () {
        console.log("✅ Initializing Platform Control Plugin");

        // ✅ KASA Control Update Socket Handling
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

        // ✅ Update button state and store real device state
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
            button.dataset.isOn = isOn; // ✅ Store real device state
        }

        // ✅ Countdown interval with proper state memory
        function startCountdown(schedule, button, nextScheduleDiv) {
            let currentTarget = null;
            let targetTimestamp = null;
            let waitingForChange = false;  // ✅ NEW flag
            button.dataset.lastIsOn = button.dataset.isOn === 'true'; // Initialize memory
        
            setInterval(() => {
                const isOn = button.dataset.isOn === 'true';
                const lastIsOn = button.dataset.lastIsOn === 'true';
        
                // ✅ If we're waiting for the real state change, hold in "Please wait..."
                if (waitingForChange) {
                    nextScheduleDiv.innerHTML = "Please wait...";
                    return;
                }
        
                // ✅ Recalculate ONLY if state changed or no active target
                if (!currentTarget || isOn !== lastIsOn) {
                    const next = calculateNextEvent(schedule, isOn);
                    if (next) {
                        currentTarget = { ...next };
                        targetTimestamp = Date.now() + next.inSeconds * 1000;
                        button.dataset.lastIsOn = isOn;
                        console.log(`[STATE CHANGE] Target: ${next.type}, In ${next.inSeconds}s`);
                    } else {
                        nextScheduleDiv.innerHTML = "No schedule set";
                        currentTarget = null;
                        targetTimestamp = null;
                        return;
                    }
                }
        
                // ✅ Countdown from target timestamp
                const remainingMs = targetTimestamp - Date.now();
                const remainingSec = Math.max(0, Math.floor(remainingMs / 1000));
        
                if (remainingSec < 2) {
                    nextScheduleDiv.innerHTML = "Please wait...";
                } else {
                    const hours = Math.floor(remainingSec / 3600);
                    const minutes = Math.floor((remainingSec % 3600) / 60);
                    const seconds = remainingSec % 60;
                    nextScheduleDiv.innerHTML = `Next ${currentTarget.type} in ${hours}h ${minutes}m ${seconds}s`;
                }
        
                // ✅ When countdown hits 0, start waiting for confirmation
                if (remainingSec === 0) {
                    waitingForChange = true;  // ✅ Stop countdown, wait for real change
                    console.log("✅ Countdown finished. Waiting for device state change...");
                }
            }, 1000);
        
            // ✅ Hook into the same button's socket updates to detect real change
            const deviceName = button.dataset.device;
            socket.on(`${deviceName}_control_update`, function (data) {
                const isOn = data.data;
                updateButtonState(button, isOn);  // Update UI and dataset
        
                // ✅ If we were waiting and the device actually changed, resume countdown
                if (waitingForChange) {
                    const lastIsOnState = button.dataset.lastIsOn === 'true';
                    if (isOn !== lastIsOnState) {
                        console.log("✅ Device state changed, resuming countdown...");
                        waitingForChange = false;
                        button.dataset.lastIsOn = isOn; // Update last known
                        currentTarget = null;           // Force re-calc
                    }
                }
            });
        }
        // ✅ Calculates the next ON or OFF based on the real device state and loops weekly
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

    }
});
