// ✅ Global function available to everyone
function updateKasaPlugsFor(selectElement) {
    console.log("Fetching Kasa devices...");
    const previousValue = selectElement.getAttribute("data-selected") || "";

    fetch("/kasa_plug/get_kasa_devices")
        .then(response => response.json())
        .then(data => {
            selectElement.innerHTML = "";

            const emptyOption = document.createElement("option");
            emptyOption.value = "";
            emptyOption.text = "-- None --";
            selectElement.appendChild(emptyOption);

            if (data.length === 0) {
                const noDevices = document.createElement("option");
                noDevices.text = "No Kasa devices found";
                noDevices.disabled = true;
                selectElement.appendChild(noDevices);
            } else {
                data.forEach(device => {
                    const option = document.createElement("option");
                    option.value = device.ip;
                    option.text = `${device.alias} (${device.ip})`;
                    if (device.ip === previousValue) option.selected = true;
                    selectElement.appendChild(option);
                });
            }
        })
        .catch(error => console.error("Error fetching Kasa devices:", error));
}


function updatePlugButtonState(button) {
    const plugIP = button.getAttribute("data-ip");

    fetch(`/kasa_plug/status?ip=${plugIP}`)
        .then(response => response.json())
        .then(data => {
            if (data.state) {
                button.setAttribute("data-state", "on");
                button.textContent = "Turn OFF";
            } else {
                button.setAttribute("data-state", "off");
                button.textContent = "Turn ON";
            }
        })
        .catch(err => console.error("Failed to fetch plug status:", err));
}


// ✅ Register plugin with global registry
window.pluginRegistry = window.pluginRegistry || [];
window.pluginRegistry.push({
    name: "kasa_plug",
    init: function() {
        console.log("✅ Initializing Kasa Plug Plugin");
        document.querySelectorAll(".refresh_kasa_plug").forEach(button => {
            button.addEventListener("click", function() {
                const select = this.closest('.kasa-plug-group').querySelector('.kasa_plug');
                console.log("🔄 Refreshing Kasa plug list for:", select);
                updateKasaPlugsFor(select);  // ✅ Now it works, globally available
            });
        });

        // Optional auto-load
        document.querySelectorAll(".kasa_plug").forEach(select => {
            updateKasaPlugsFor(select);
        });

        document.querySelectorAll(".kasa-toggle-plug").forEach(button => {
            // Initial state check from device
            updatePlugButtonState(button);
    
            button.addEventListener("click", () => {
                const plugIP = button.getAttribute("data-ip");
    
                fetch(`/kasa_plug/toggle?ip=${plugIP}`, { method: "POST" })
                    .then(response => response.json())
                    .then(data => {
                        // After toggle, sync the button again from real state
                        updatePlugButtonState(button);
                    })
                    .catch(err => console.error("Toggle failed:", err));
            });
        });
    }
});