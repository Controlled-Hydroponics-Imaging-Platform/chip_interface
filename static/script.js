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

    function updateSerialPortsFor(selectElement) {
        const currentSelection = selectElement.value;
        fetch("/get_serial_ports")
            .then(response => response.json())
            .then(data => {
                selectElement.innerHTML = ""; // Clear previous options
                if (data.length === 0) {
                    let option = document.createElement("option");
                    option.text = "No serial devices found";
                    selectElement.appendChild(option);
                } else {
                    data.forEach(port => {
                        let option = document.createElement("option");
                        option.value = port.device;
                        option.text = `${port.description === "n/a" ? "" : port.description} (${port.device})`;
                        if (port.device === currentSelection) {
                            option.selected = true;
                        }
                        selectElement.appendChild(option);
                    });
                }
            })
            .catch(error => console.error("Error fetching serial ports:", error));
    }

    // Attach click event to all refresh buttons
    document.querySelectorAll(".refresh_serial").forEach(button => {
        button.addEventListener("click", function() {
            const select = this.closest('.serial-group').querySelector('.serial_port');
            console.log("🔄 Refreshing serial ports for:", select);
            updateSerialPortsFor(select);
        });
    });

    // Optional: Initial load of all dropdowns
    document.querySelectorAll(".serial_port").forEach(select => {
        updateSerialPortsFor(select);
    });

});





// Load plugin scripts
document.addEventListener("DOMContentLoaded", () => {
    fetch('/plugin_scripts')
        .then(response => response.json())
        .then(scripts => {
            const loadPromises = scripts.map(script => new Promise((resolve, reject) => {
                const tag = document.createElement('script');
                tag.src = `/static/${script}`;
                tag.onload = () => {
                    console.log(`✅ Loaded: ${script}`);
                    resolve();
                };
                tag.onerror = () => reject(`❌ Failed to load: ${script}`);
                document.body.appendChild(tag);
            }));

            Promise.all(loadPromises).then(() => {
                console.log("✅ All plugins loaded, initializing...");
                if (window.pluginRegistry) {
                    window.pluginRegistry.forEach(plugin => {
                        console.log(`🛠️ Initializing plugin: ${plugin.name}`);
                        if (typeof plugin.init === "function") plugin.init();
                    });
                }
            }).catch(err => console.error(err));
        })
        .catch(err => console.error("Failed to load plugins:", err));
});