var socket = io.connect("http://" + document.domain + ":" + location.port);

socket.on("connect", function() {
    console.log("Connected to WebSocket");
});

socket.on("sensor_update", function(data) {
    console.log("Received Data:", data.value);  // Debugging output
    document.getElementById("sensor").innerText = data.value;
});

function sendCommand() {
    fetch("/api/send_command", { method: "POST" })
    .then(response => response.json())
    .then(data => alert("Command Sent: " + data.response));
}

// Serial port loader
document.addEventListener("DOMContentLoaded", function() {
    const serialDropdown = document.getElementById("serial_port");

    function updateSerialPorts() {
        fetch("/get_serial_ports")
            .then(response => response.json())
            .then(data => {
                serialDropdown.innerHTML = ""; // Clear previous options
                if (data.length === 0) {
                    let option = document.createElement("option");
                    option.text = "No serial devices found";
                    serialDropdown.appendChild(option);
                } else {
                    data.forEach(port => {
                        let option = document.createElement("option");
                        option.value = port;
                        option.text = port;
                        serialDropdown.appendChild(option);
                    });
                }
            })
            .catch(error => console.error("Error fetching serial ports:", error));
    }

    // Auto-refresh every 5 seconds
    setInterval(updateSerialPorts, 5000); 

    // Run immediately when the page loads
    updateSerialPorts();
});