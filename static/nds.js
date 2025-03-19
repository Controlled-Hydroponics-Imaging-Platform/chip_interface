socket.on("sensor_update", function(data) {
    console.log("Received Data:", data.value);  // Debugging output
    document.getElementById("sensor").innerText = data.value;
});
