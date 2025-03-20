var socket = io.connect("http://" + document.domain + ":" + location.port);

socket.on("connect", function() {
    console.log("Connected to WebSocket");
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
        if (!serialDropdown) {
            console.warn("⚠️ serial_port dropdown not found");
            return;
        }

        const currentSelection = serialDropdown.value;
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
                        option.value = port.device;
                        option.text = `${port.description === "n/a" ? "" : port.description} (${port.device})`;

                        if (port.device === currentSelection) {
                            option.selected = true;
                        }

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




// Load plugin scripts
document.addEventListener("DOMContentLoaded", () => {
    fetch('/plugin_scripts')
        .then(response => response.json())
        .then(scripts => {
        scripts.forEach(script => {
            const tag = document.createElement('script');
            tag.src = `/static/${script}`;
            tag.async = false;  // Optional: preserves execution order if needed
            tag.onload = () => {
            console.log(`✅ Loaded: ${script}`);
            };
            tag.onerror = () => {
            console.error(`❌ Failed to load: ${script}`);
            };
            document.body.appendChild(tag);
        });
        })
        .catch(err => console.error("Failed to load plugins:", err));


});