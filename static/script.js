var socket = io.connect("http://" + document.domain + ":" + location.port);

socket.on("connect", function() {
    console.log("Connected to WebSocket");
});

function sendCommand() {
    fetch("/api/send_command", { method: "POST" })
    .then(response => response.json())
    .then(data => alert("Command Sent: " + data.response));
}

// function refreshWifiList() {
//     fetch('/scan_wifi')
//         .then(response => response.json())
//         .then(data => {
//             const select = document.getElementById('ssid');
//             select.innerHTML = '';
//             data.networks.forEach(net => {
//                 const option = document.createElement('option');
//                 option.value = net.ssid;
//                 option.text = `${net.ssid} (${net.signal}%)`;
//                 select.appendChild(option);
//             });
//         });
// }


function restartPi() {
    if (confirm("⚠️ Are you sure you want to restart the Raspberry Pi?")) {
        fetch('/restart', { method: 'POST' })
            .then(response => {
                if (response.ok) {
                    alert("✅ Raspberry Pi is restarting...");
                } else {
                    alert("❌ Failed to restart the Pi.");
                }
            })
            .catch(err => {
                console.error("Restart error:", err);
                alert("❌ Restart request failed.");
            });
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // Wi-Fi Setup
    if (document.getElementById('wifi_dropdown')) {
        scanWiFi();
    }

    if (document.getElementById('current_ssid')) {
        getCurrentWiFi();
    }

    const refreshBtn = document.getElementById('refresh_wifi');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', scanWiFi);
    }

    const wifiDropdown = document.getElementById('wifi_dropdown');
    if (wifiDropdown) {
        wifiDropdown.addEventListener('change', function () {
            const selectedSSID = this.value;
            if (selectedSSID) {
                const ssidInput = document.getElementById('ssid_input');
                if (ssidInput) ssidInput.value = selectedSSID;
            }
        });
    }

    const wifiForm = document.getElementById('wifi_form');
    if (wifiForm) {
        wifiForm.addEventListener('submit', function (e) {
            alert("✅ Wi-Fi settings saved. The Raspberry Pi will now restart to apply changes. Please reconnect once it's back online.");
        });
    }

    function getCurrentWiFi() {
        fetch('/current_wifi')
            .then(response => response.json())
            .then(data => {
                const ssid = data.ssid || 'Not connected';
                const currentElem = document.getElementById('current_ssid');
                if (currentElem) currentElem.textContent = ssid;
            });
    }

    function scanWiFi() {
        fetch('/scan_wifi')
            .then(response => response.json())
            .then(data => {
                const dropdown = document.getElementById('wifi_dropdown');
                if (!dropdown) return;
                dropdown.innerHTML = '<option value="">-- Select a Network --</option>';
                data.networks.forEach(network => {
                    const option = document.createElement('option');
                    option.value = network.ssid;
                    option.textContent = `${network.ssid} (${network.signal}%)`;
                    dropdown.appendChild(option);
                });
            });
    }

    // Serial Port Handling
    function updateSerialPortsFor(selectElement) {
        const previousValue = selectElement.getAttribute("data-selected") || "";
    
        fetch("/get_serial_ports")
            .then(response => response.json())
            .then(data => {
                selectElement.innerHTML = "";
    
                const emptyOption = document.createElement("option");
                emptyOption.value = "";
                emptyOption.text = "-- None --";
                selectElement.appendChild(emptyOption);
    
                if (data.length === 0) {
                    const noPorts = document.createElement("option");
                    noPorts.text = "No serial devices found";
                    noPorts.disabled = true;
                    selectElement.appendChild(noPorts);
                } else {
                    data.forEach(port => {
                        const option = document.createElement("option");
                        option.value = port.device;
                        option.text = `${port.description === "n/a" ? "" : port.description} (${port.device})`;
                        if (port.device === previousValue) option.selected = true;
                        selectElement.appendChild(option);
                    });
                }
            })
            .catch(error => console.error("Error fetching serial ports:", error));
    }
    

    // Attach click to all serial refresh buttons
    document.querySelectorAll(".refresh_serial").forEach(button => {
        button.addEventListener("click", function () {
            const select = this.closest('.serial-group')?.querySelector('.serial_port');
            if (select) {
                console.log("🔄 Refreshing serial ports for:", select);
                updateSerialPortsFor(select);
            }
        });
    });

    // Initial load of serial dropdowns
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