socket.on("nds_sensor_update", function(data) {
    console.log("Received Data:", data);  // Debugging output

    const sensorElem = document.getElementById("nds_sensors");
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