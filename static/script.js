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

