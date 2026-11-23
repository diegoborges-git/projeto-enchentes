const number = new Intl.NumberFormat("pt-BR");

const metricLabels = {
  deaths: "Tamanho do círculo por óbitos",
  affectedPopulation: "Tamanho do círculo pela população afetada",
  displaced: "Tamanho do círculo por pessoas desalojadas"
};

const metricNames = {
  deaths: "Óbitos",
  missing: "Desaparecidos",
  rescued: "Resgatados",
  displaced: "Desalojados",
  affectedPopulation: "População afetada"
};

let map;
let markerLayer;
let municipalities = [];

function valueOrDash(value) {
  return value == null ? "Não informado" : number.format(value);
}

function popupTemplate(item) {
  const rows = [
    ["Óbitos", item.deaths],
    ["Desaparecidos", item.missing],
    ["Resgatados", item.rescued],
    ["Desalojados", item.displaced],
    ["População afetada", item.affectedPopulation]
  ];

  return `
    <div class="popup-name">${item.name}</div>
    <div class="popup-grid">
      ${rows.map(([label, value]) => `<span>${label}</span><strong>${valueOrDash(value)}</strong>`).join("")}
    </div>
  `;
}

function markerRadius(item, metric) {
  const value = item[metric];
  if (!value) return 5;
  const maxValue = Math.max(...municipalities.map((entry) => entry[metric] || 0));
  return 6 + Math.sqrt(value / Math.max(maxValue, 1)) * 22;
}

function renderMarkers(metric = "deaths", query = "") {
  if (!map || !markerLayer) return;
  markerLayer.clearLayers();
  const normalizedQuery = query.trim().toLocaleLowerCase("pt-BR");

  municipalities
    .filter((item) => !normalizedQuery || item.name.toLocaleLowerCase("pt-BR").includes(normalizedQuery))
    .forEach((item) => {
      const marker = L.circleMarker([item.lat, item.lon], {
        radius: markerRadius(item, metric),
        weight: 1,
        color: item.deaths > 0 ? "#ff8a7a" : "#76d7c4",
        fillColor: item.deaths > 0 ? "#ef5b67" : "#3dbfb1",
        fillOpacity: 0.78
      });
      marker.bindPopup(popupTemplate(item));
      marker.addTo(markerLayer);
      if (normalizedQuery) marker.openPopup();
    });
}

function renderSummary(summary) {
  const cards = [
    ["pessoas_potencialmente_afetadas", "Pessoas potencialmente afetadas"],
    ["pessoas_diretamente_afetadas", "Pessoas diretamente afetadas"],
    ["desalojados", "Desalojados"],
    ["feridos", "Feridos"]
  ];

  document.querySelector("#summary").innerHTML = cards
    .map(([key, label]) => `
      <article class="stat-card">
        <strong>${number.format(summary[key] || 0)}</strong>
        <span>${label}</span>
      </article>
    `).join("");
}

function renderRanking() {
  const top = [...municipalities]
    .filter((item) => item.deaths > 0)
    .sort((a, b) => b.deaths - a.deaths)
    .slice(0, 5);

  document.querySelector("#ranking").innerHTML = top
    .map((item) => `
      <article class="ranking-item">
        <span>${item.name}</span>
        <strong>${number.format(item.deaths)} óbitos</strong>
      </article>
    `).join("");
}

async function init() {
  const response = await fetch("./data/municipios.json");
  if (!response.ok) throw new Error("Não foi possível carregar os dados do mapa.");
  const data = await response.json();
  municipalities = data.municipalities;

  renderSummary(data.summary);
  renderRanking();

  map = L.map("map", {
    scrollWheelZoom: false,
    zoomControl: true
  }).setView([-30.0346, -51.2177], 7);

  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19,
    attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ"
  }).addTo(map);

  markerLayer = L.layerGroup().addTo(map);
  renderMarkers();

  document.querySelectorAll("[data-metric]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-metric]").forEach((entry) => entry.classList.remove("active"));
      button.classList.add("active");
      const metric = button.dataset.metric;
      document.querySelector("#map-caption").textContent = metricLabels[metric];
      renderMarkers(metric, document.querySelector("#municipality-search").value);
    });
  });

  document.querySelector("#municipality-search").addEventListener("input", (event) => {
    const metric = document.querySelector("[data-metric].active").dataset.metric;
    renderMarkers(metric, event.target.value);
  });

  document.querySelector("#ranking-toggle").addEventListener("click", (event) => {
    const ranking = document.querySelector("#ranking");
    ranking.classList.toggle("hidden");
    const expanded = !ranking.classList.contains("hidden");
    event.currentTarget.setAttribute("aria-expanded", String(expanded));
    event.currentTarget.textContent = expanded ? "Recolher" : "Expandir";
  });
}

init().catch((error) => {
  document.querySelector("#map").innerHTML = `<p style="padding:20px">${error.message}</p>`;
});
