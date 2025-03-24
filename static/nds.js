window.pluginRegistry = window.pluginRegistry || [];
window.pluginRegistry.push({
    name: "nds_sensors",
    init: function () {
        console.log("✅ Initializing NDS Sensor Plugin");

        // You could dynamically generate the device list if needed
        const sensorDivs = document.querySelectorAll("[id$='_sensors']");

        sensorDivs.forEach(sensorDiv => {
            const deviceName = sensorDiv.id.replace('_sensors', '');
            const statusElem = document.querySelector(`#${deviceName}_status`) || createStatusElement(deviceName);

            let reconnectInterval = null;

            function startCountdown(seconds) {
                let count = seconds;
                reconnectInterval = setInterval(() => {
                    count -= 1;
                    const countdownElem = statusElem.querySelector('#countdown');
                    if (countdownElem) countdownElem.textContent = count;
                    if (count <= 0) clearInterval(reconnectInterval);
                }, 1000);
            }

            function stopCountdown() {
                if (reconnectInterval) {
                    clearInterval(reconnectInterval);
                    reconnectInterval = null;
                }
            }

            // Status handler per device
            socket.on(`${deviceName}_status_update`, function (data) {
                const portInfo = data.device ? ` (${data.device})` : "";

                if (data.status === "disconnected") {
                    statusElem.classList.remove('connected');
                    statusElem.classList.add('disconnected');
                    statusElem.innerHTML = `* Device disconnected${portInfo}: Reconnecting in <span id='countdown'>5</span> sec...`;
                    sensorDiv.innerHTML = `⚠️ Disconnected ${portInfo}`;
                    startCountdown(5);
                } else if (data.status === "connecting") {
                    stopCountdown();
                    statusElem.classList.remove('connected', 'disconnected');
                    statusElem.innerHTML = `* Connecting to device${portInfo}...`;
                    sensorDiv.innerHTML = `Waiting for response from${portInfo}...`;
                } else if (data.status === "connected") {
                    stopCountdown();
                    statusElem.classList.remove('disconnected');
                    statusElem.classList.add('connected');
                    statusElem.innerHTML = `* Device Connected${portInfo}`;

                    // Clear the status message after 10 sec
                    setTimeout(() => {
                        statusElem.innerText = "";
                        statusElem.classList.remove('connected', 'disconnected');
                    }, 10000);
                }
            });

            // Data handler per device
            socket.on(`${deviceName}_sensor_update`, function (data) {
                console.log(`📡 [${deviceName}] Received Data:`, data);
                sensorDiv.innerHTML = "";

                // Populate sensor data
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
