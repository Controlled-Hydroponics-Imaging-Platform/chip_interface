// ✅ Global function available to everyone
function updateKasaPlugsFor(selectElement) {
    console.log("Fetching Kasa devices...");
    const currentSelection = selectElement.value;
    fetch("/kasa_plug/get_kasa_devices")
        .then(response => response.json())
        .then(data => {
            selectElement.innerHTML = "";
            if (data.length === 0) {
                let option = document.createElement("option");
                option.text = "No Kasa devices found";
                selectElement.appendChild(option);
            } else {
                data.forEach(device => {
                    let option = document.createElement("option");
                    option.value = device.ip;
                    option.text = `${device.alias} (${device.ip})`;
                    if (device.ip === currentSelection) option.selected = true;
                    selectElement.appendChild(option);
                });
            }
        })
        .catch(error => console.error("Error fetching Kasa devices:", error));
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
    }
});