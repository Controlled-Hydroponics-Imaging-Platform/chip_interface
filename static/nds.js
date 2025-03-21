const sensorElem = document.getElementById("nds_sensors");
const statusElem = document.getElementById("connection_status");
let reconnectInterval = null;


socket.on("nds_status_update", function(data) {
    const portInfo = data.device ? ` (${data.device})` : "";

    if (data.status === "disconnected") {
        statusElem.classList.remove('connected');
        statusElem.classList.add('disconnected');
        statusElem.innerHTML = `* Device disconnected${portInfo}: Attempting to reconnect in <span id='countdown'>5</span> seconds...`;
        sensorElem.innerHTML = `⚠️ Disconnected ${portInfo}`;
        startCountdown(5);
    } else if (data.status === "connecting") {
        stopCountdown();
        statusElem.classList.remove('connected', 'disconnected');
        statusElem.innerHTML = `* Connecting to device${portInfo}...`;
        sensorElem.innerHTML = `Waiting for response from${portInfo}...`;
    } else if (data.status === "connected") {
        stopCountdown();
        statusElem.classList.remove('disconnected');
        statusElem.classList.add('connected');
        statusElem.innerHTML = `* Device Connected${portInfo}`;

        // Clear the status message after 10 seconds
        setTimeout(() => {
            statusElem.innerText = "";
            statusElem.classList.remove('connected', 'disconnected');
        }, 10000);
    }
});



socket.on("nds_sensor_update", function(data) {
    console.log("Received Data:", data);  // Debugging output

    if (!sensorElem) {
        console.warn("'sensor' element not found in DOM");
        return;
    }

    // Clear previous values
    sensorElem.innerHTML = "";

    // Loop through each key-value pair and display it
    for (const [key, value] of Object.entries(data)) {
        const line = document.createElement('div');
        line.classList.add('sensor-item');
        line.textContent = `${key}: ${value}`;
        sensorElem.appendChild(line);
    }
});


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