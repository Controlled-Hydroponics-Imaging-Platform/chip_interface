window.pluginRegistry = window.pluginRegistry || [];
window.pluginRegistry.push({
    name: "nds_sensor",
    init: function () {
        console.log("✅ Initializing NDS Sensor Plugin");

        const sensorElem = document.getElementById("nds_sensors");
        const statusElem = document.getElementById("connection_status");
        const timestampElem = document.getElementById("last_updated");
        let reconnectInterval = null;

        function startCountdown(seconds) {
            let count = seconds;
            reconnectInterval = setInterval(() => {
                count -= 1;
                const countdownElem = document.getElementById('countdown');
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

        // Handle device status updates
        socket.on("nds_status_update", function (data) {
            const portInfo = data.device ? ` (${data.device})` : "";

            if (data.status === "disconnected") {
                statusElem?.classList.remove('connected');
                statusElem?.classList.add('disconnected');
                statusElem.innerHTML = `* Device disconnected${portInfo}: Attempting to reconnect in <span id='countdown'>5</span> seconds...`;
                sensorElem.innerHTML = `⚠️ Disconnected ${portInfo}`;
                startCountdown(5);
            } else if (data.status === "connecting") {
                stopCountdown();
                statusElem?.classList.remove('connected', 'disconnected');
                statusElem.innerHTML = `* Connecting to device${portInfo}...`;
                sensorElem.innerHTML = `Waiting for response from${portInfo}...`;
            } else if (data.status === "connected") {
                stopCountdown();
                statusElem?.classList.remove('disconnected');
                statusElem?.classList.add('connected');
                statusElem.innerHTML = `* Device Connected${portInfo}`;

                // Optional: Clear the status message after 10 seconds
                setTimeout(() => {
                    statusElem.innerText = "";
                    statusElem.classList.remove('connected', 'disconnected');
                }, 10000);
            }
        });

        // Handle sensor data
        socket.on("nds_sensor_update", function (data) {
            console.log("Received Data:", data);

            if (!sensorElem) {
                console.warn("'nds_sensors' element not found in DOM");
                return;
            }

            // Clear previous values
            sensorElem.innerHTML = "";

            // Loop through sensor data and display
            for (const [key, item] of Object.entries(data.data)) {
                const line = document.createElement('div');
                line.classList.add('sensor-item');
                line.innerHTML = `<strong>${key}</strong>: ${item.value} ${item.unit}`;
                sensorElem.appendChild(line);
            }

            const ts = document.createElement('div');
            ts.classList.add('timestamp');
            ts.innerHTML = `<strong>Last updated</strong>: ${data.timestamp}`;
            sensorElem.appendChild(ts);
        });
    }
});