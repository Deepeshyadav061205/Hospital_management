document.addEventListener("DOMContentLoaded", function () {
  // Mobile navbar toggle
  const toggleBtn = document.getElementById("nav-toggle");
  const navLinks = document.getElementById("nav-links");
  if (toggleBtn && navLinks) {
    toggleBtn.addEventListener("click", function () {
      navLinks.classList.toggle("open");
    });
  }

  // Highlight selected slot radio card
  const slotRadios = document.querySelectorAll('input[name="slot_id"]');
  slotRadios.forEach(function (radio) {
    radio.addEventListener("change", function () {
      document.querySelectorAll(".slot-option").forEach(function (card) {
        card.classList.remove("slot-selected");
      });
      if (radio.checked) {
        radio.closest(".slot-option").classList.add("slot-selected");
      }
    });
  });

  // Confirm destructive/cancel actions
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (event) {
      if (!window.confirm(el.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });

  // Initialize Leaflet hospital map when present
  const mapEl = document.getElementById("hospital-map");
  if (mapEl && typeof window.L !== "undefined") {
    const hospitals = JSON.parse(mapEl.getAttribute("data-hospitals") || "[]");
    const centerLat = parseFloat(mapEl.getAttribute("data-center-lat"));
    const centerLng = parseFloat(mapEl.getAttribute("data-center-lng"));
    const zoom = parseInt(mapEl.getAttribute("data-zoom") || "5", 10);

    const map = window.L.map(mapEl).setView(
      [!isNaN(centerLat) ? centerLat : 21.1458, !isNaN(centerLng) ? centerLng : 79.0882],
      zoom
    );

    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);

    const bounds = [];
    hospitals.forEach(function (h) {
      const marker = window.L.marker([h.lat, h.lng]).addTo(map);
      const popupHtml =
        "<strong>" +
        h.name +
        "</strong><br>" +
        "Beds: " +
        h.available_beds +
        " / " +
        h.total_beds +
        "<br>" +
        "ICU: " +
        h.available_icu +
        " / " +
        h.total_icu +
        "<br>" +
        '<a href="' +
        h.url +
        '">View details</a>';
      marker.bindPopup(popupHtml);
      bounds.push([h.lat, h.lng]);
    });

    if (bounds.length > 1 && isNaN(centerLat)) {
      map.fitBounds(bounds, { padding: [24, 24] });
    }
  }
});
