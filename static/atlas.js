/** Shared Atlas surface for the web app and the iOS WKWebView. */
const ASSETS = new URL('.', import.meta.url).href;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeURL = value => { try { const u = new URL(value); return /https?:/.test(u.protocol) ? u.href : null; } catch { return null; } };
const scripts = new Map();
function script(name, global) {
  if (window[global]) return Promise.resolve(window[global]);
  if (!scripts.has(name)) scripts.set(name, new Promise((resolve, reject) => {
    const element = document.createElement('script'); element.src = ASSETS + 'vendor/' + name;
    element.onload = () => resolve(window[global]); element.onerror = () => { scripts.delete(name); element.remove(); reject(new Error('Carte indisponible')); };
    document.head.append(element);
  }));
  return scripts.get(name);
}

const colors = {
  news: '#3B82F6',
  conflicts: '#EF4444',
  earthquakes: '#F59E0B',
  nature: '#10B981',
  flights: '#06B6D4',
  ships: '#38BDF8',
  fires: '#F97316',
  society: '#A78BFA',
  weather: '#60A5FA',
  nuclear: '#D6F43A',
  military: '#94A3B8',
  cables: '#22D3EE',
  pipelines: '#F59E0B'
};
const labels = {
  news: 'Actualités',
  conflicts: 'Conflits',
  earthquakes: 'Séismes',
  nature: 'Nature',
  flights: 'Vols',
  ships: 'Navires AIS',
  fires: 'Feux satellite',
  society: 'Société',
  weather: 'Météo extrême',
  nuclear: 'Nucléaire',
  military: 'Bases militaires',
  cables: 'Câbles sous-marins',
  pipelines: 'Pipelines'
};
const emojis = {news:'🗞️',conflicts:'💣',earthquakes:'🌋',nature:'🪾',flights:'✈️',ships:'🛳️',fires:'🔥',society:'📢',weather:'🌦️',nuclear:'☢️',military:'△',cables:'〰️',pipelines:'〰️'};
const weatherEmojis = {cyclone:'🌀',flood:'🌊',fire:'🔥',volcano:'🌋',heat:'☀️',snow:'❄️',weather:'🌦️'};
const providerLayers = ['earthquakes','nature','weather','fires','flights','ships','society','military','nuclear','cables','pipelines'];

const svgIcon = path => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
const icons = {
  globe: svgIcon('<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>'),
  layers: svgIcon('<path d="m12 3 10 6-10 6L2 9l10-6Z"/><path d="m3 14 9 5 9-5M3 18l9 5 9-5"/>'),
  search: svgIcon('<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>'),
  arrow: svgIcon('<path d="M5 12h14m-5-5 5 5-5 5"/>'),
  refresh: svgIcon('<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 6M4 12l2 6a7 7 0 0 0 12-1"/>'),
  clock: svgIcon('<circle cx="12" cy="12" r="9"/><polyline points="12 6 12 12 16 14"/>'),
  chevronDown: svgIcon('<path d="m6 9 6 6 6-6"/>'),
  chevronUp: svgIcon('<path d="m18 15-6-6-6 6"/>'),
};

function ago(date) {
  const delta = Date.now() - new Date(date).getTime();
  if (!Number.isFinite(delta)) return 'Date non disponible';
  const min = Math.max(0, Math.floor(delta / 60000));
  return min < 1 ? 'À l’instant' : min < 60 ? `Il y a ${min} min` : min < 1440 ? `Il y a ${Math.floor(min / 60)} h` : `Il y a ${Math.floor(min / 1440)} j`;
}
function countryCode(country) { const p = country.properties; return p.ISO_A2 !== '-99' ? p.ISO_A2 : p.ISO_A2_EH; }
function countryName(country) { return country.properties.NAME_FR || country.properties.ADMIN; }

export async function mountAtlas(element, options = {}) {
  if (!document.querySelector('link[data-atlas-css]')) {
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = ASSETS + 'atlas.css'; css.dataset.atlasCss = ''; document.head.append(css);
  }
  const controller = new AbortController();
  const fetchJSON = options.fetchJSON || (async path => {
    const response = await fetch(path, {signal: controller.signal, cache:'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });

  let dead = false, globe, flatSVG, projection, countries = [], geoPath, resizeObserver, poll, renderFrame;
  let news = [], arcs = [], providers = {}, newsStatus = 'loading', updatedAt;
  let selectedCountry = null, selectedPoint = null, activeEvent = null, query = '', rangeHours = 24, radius = 500, mode = '3d', style = 'night', rotation = false, heat = true, links = true, busy = false, flatZoom = 1;
  const layers = new Set(['news', 'conflicts', 'earthquakes', 'nature', 'weather']);
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isFull = options.fullscreen || !!window.webkit?.messageHandlers?.atlasNews || document.body.classList.contains('atlas-fullscreen');

  if (isFull) {
    document.documentElement.classList.add('atlas-ios');
    element.classList.add('atlas-fullscreen');
  }
  element.classList.add('atlas-host');
  element.innerHTML = `
    <section class="atlas ${isFull ? 'atlas-fullscreen' : ''}" aria-label="Atlas des actualités" data-style="night">
      <div class="atlas-stage">
        <div class="atlas-canvas" role="img" aria-label="Globe interactif"></div>
        <div class="atlas-map-message" role="status">Préparation de votre atlas…</div>
        
        <div class="atlas-top">
          <div class="atlas-top-left">
            <div class="atlas-mode" aria-label="Projection">
              <button data-mode="3d" aria-pressed="true">${icons.globe} Globe</button>
              <button data-mode="flat" aria-pressed="false">Carte</button>
            </div>
            <span class="atlas-observation"><i></i><span>En direct</span></span>
          </div>
          <div class="atlas-top-right">
            <button class="atlas-refresh" aria-label="Actualiser les observations">${icons.refresh}</button>
            <button class="atlas-layer-button" aria-expanded="false">${icons.layers}<span>Calques</span></button>
          </div>
        </div>

        <div class="atlas-quick-chips" aria-label="Filtres rapides">
          ${['news','conflicts','earthquakes','nature','flights','ships','fires','society','weather'].map(id => `<button class="atlas-chip ${layers.has(id)?'active':''}" data-chip="${id}"><span>${emojis[id]}</span>${labels[id]}</button>`).join('')}
          <button class="atlas-chip active" data-chip="links"><i style="--dot:#818CF8"></i>Liens</button>
        </div>

        <div class="atlas-layer-panel" hidden>
          <strong>Affichage & Calques</strong>
          ${Object.entries(labels).map(([id,name]) => `<label><span>${emojis[id]} ${name}</span><input type="checkbox" data-layer="${id}" ${layers.has(id)?'checked':''}></label>`).join('')}
          <label><span>🌈 Heatmap des signaux</span><input type="checkbox" data-option="heat" checked></label>
          <label><span>Liens thématiques</span><input type="checkbox" data-option="links" checked></label>
          <label class="atlas-style"><span>Ambiance</span><select aria-label="Ambiance de la carte"><option value="night">Minuit</option><option value="blue">Cobalt</option><option value="paper">Clair</option></select></label>
          <div class="atlas-provider-notes"></div>
        </div>

        <div class="atlas-side-controls">
          <div class="atlas-side-btn atlas-side-country" title="Choisir un pays">
            ${icons.globe}
            <span class="side-badge">Pays</span>
            <select class="atlas-country" aria-label="Choisir un pays"><option value="">Tous les pays</option></select>
          </div>
          <div class="atlas-side-btn atlas-side-time" title="Période">
            ${icons.clock}
            <span class="side-badge">24h</span>
            <select class="atlas-time" aria-label="Période">
              <option value="24">24h</option>
              <option value="72">3j</option>
              <option value="168">7j</option>
              <option value="0">Tout</option>
            </select>
          </div>
          <div class="atlas-zoom-group">
            <button data-zoom="in" aria-label="Zoomer">+</button>
            <button data-zoom="out" aria-label="Dézoomer">−</button>
            <button data-zoom="reset" aria-label="Recentrer le globe">⌖</button>
            <button data-rotate aria-label="Rotation automatique" aria-pressed="false">↻</button>
          </div>
        </div>

        <div class="atlas-presets" aria-label="Vues rapides">
          <button data-preset="world" class="active">Monde</button>
          <button data-preset="europe">Europe</button>
          <button data-preset="americas">Amériques</button>
          <button data-preset="asia">Asie</button>
        </div>

        <div class="atlas-spotlight" hidden></div>

        <div class="atlas-news-tray collapsed">
          <div class="atlas-tray-header">
            <div class="atlas-tray-title">
              <span class="atlas-tray-place">Actualités</span>
              <span class="count atlas-count">0</span>
              <div class="atlas-selection" hidden>
                <span></span>
                <select aria-label="Rayon autour du point"><option value="100">100 km</option><option value="500" selected>500 km</option><option value="1500">1 500 km</option></select>
                <button aria-label="Effacer la sélection géographique">×</button>
              </div>
            </div>
            <button class="atlas-tray-toggle" aria-label="Réduire ou agrandir les actualités">${icons.chevronUp}</button>
          </div>
          <div class="atlas-events" aria-live="polite"></div>
        </div>

        <div class="atlas-bottom-search">
          <label class="atlas-search">
            ${icons.search}
            <input aria-label="Rechercher dans les actualités" placeholder="Rechercher un lieu, un sujet…" type="search">
            <button class="atlas-search-clear" hidden aria-label="Effacer">×</button>
          </label>
        </div>
      </div>
    </section>`;

  const root = element.querySelector('.atlas'), $ = selector => root.querySelector(selector), $$ = selector => [...root.querySelectorAll(selector)];
  const canvas = $('.atlas-canvas');

  let lastSelectTime = 0;
  let pointerStartX = 0, pointerStartY = 0, hasDragged = false;
  canvas.addEventListener('pointerdown', e => {
    pointerStartX = e.clientX;
    pointerStartY = e.clientY;
    hasDragged = false;
  }, { passive: true });
  canvas.addEventListener('pointermove', e => {
    if (Math.hypot(e.clientX - pointerStartX, e.clientY - pointerStartY) > 8) {
      hasDragged = true;
    }
  }, { passive: true });

  const cleanup = () => {
    dead = true; controller.abort(); clearInterval(poll); cancelAnimationFrame(renderFrame); resizeObserver?.disconnect();
    document.removeEventListener('visibilitychange', onVisibility);
    if (globe) { globe.pauseAnimation(); globe._destructor?.(); }
    element.classList.remove('atlas-host'); element.replaceChildren();
  };

  function isConflict(event) {
    return event.layer === 'conflicts' || event.is_conflict || /\b(guerre|conflit|frappe|militaire|invasion|war|conflict|missile|arm[ée]e|terroris|attaque|combat)\b/i.test(`${event.title} ${event.category || ''} ${event.summary || ''}`);
  }

  function markerEmoji(event) {
    return event.layer === 'weather' ? (weatherEmojis[event.subtype] || weatherEmojis.weather) : (emojis[event.layer] || emojis.news);
  }

  function detailLevel() {
    if (mode === 'flat') return flatZoom;
    const altitude = globe?.pointOfView?.().altitude || 2.3;
    return Math.max(1, Math.min(10, 4.6 / altitude));
  }

  function visibleAtZoom(event) {
    const detail = detailLevel();
    if (['military','nuclear'].includes(event.layer)) return detail >= 2.1;
    if (['flights','ships'].includes(event.layer)) return detail >= 1.35;
    return true;
  }

  function clusterEvents(events) {
    const detail = detailLevel();
    if (detail >= 5) return events;
    const cell = detail < 1.7 ? 24 : detail < 3 ? 11 : 5;
    const buckets = new Map();
    for (const event of events.filter(visibleAtZoom)) {
      const key = `${Math.floor((event.latitude + 90) / cell)}:${Math.floor((event.longitude + 180) / cell)}`;
      const bucket = buckets.get(key) || [];
      bucket.push(event); buckets.set(key, bucket);
    }
    return [...buckets.entries()].map(([key, members]) => members.length === 1 ? members[0] : ({
      id:`cluster:${cell}:${key}`, layer:'cluster', count:members.length, members,
      latitude:members.reduce((sum,item)=>sum+item.latitude,0)/members.length,
      longitude:members.reduce((sum,item)=>sum+item.longitude,0)/members.length,
      title:`${members.length} observations`, summary:[...new Set(members.map(markerEmoji))].slice(0,4).join(' ')
    }));
  }

  function countryNameForEvent(event) {
    return countries.find(c => countryCode(c) === event.country_code)?.properties.NAME_FR || '';
  }

  function availableEvents() {
    const items = [];
    const showNews = layers.has('news');
    const showConflicts = layers.has('conflicts');

    if (showNews && showConflicts) {
      items.push(...news.map(e => isConflict(e) ? { ...e, is_conflict: true, layer: 'conflicts' } : e));
    } else if (showNews) {
      items.push(...news);
    } else if (showConflicts) {
      items.push(...news.filter(isConflict).map(e => ({ ...e, is_conflict: true, layer: 'conflicts' })));
    }

    for (const id of providerLayers) {
      if (layers.has(id)) {
        items.push(...(providers[id]?.events || []));
      }
    }

    return items.filter(event => {
      if (!Number.isFinite(event.latitude) || !Number.isFinite(event.longitude)) return false;
      if (rangeHours && event.timestamp && !['flights','ships','military','nuclear','nature','fires','weather'].includes(event.layer) && new Date(event.timestamp).getTime() < Date.now() - rangeHours * 3600000) return false;
      if (query && ![event.title, event.location_name, event.country_code, event.category, event.airline, countryNameForEvent(event)].some(value => String(value || '').toLowerCase().includes(query))) return false;
      return true;
    });
  }

  function inSelection(event) {
    if (selectedCountry) return event.country_code === countryCode(selectedCountry) || window.d3?.geoContains?.(selectedCountry, [event.longitude, event.latitude]);
    if (selectedPoint) return window.d3?.geoDistance?.([event.longitude, event.latitude], [selectedPoint.lng, selectedPoint.lat]) * 6371 <= radius;
    return true;
  }

  function pointColor(event) {
    if (event.layer === 'cluster') return '#7EA2FF';
    if (event.layer === 'conflicts' || event.is_conflict) return '#EF4444';
    if (event.layer === 'earthquakes') {
      const mag = event.magnitude || 4.5;
      return mag >= 6.0 ? '#DC2626' : mag >= 5.0 ? '#F97316' : '#FBBF24';
    }
    return colors[event.layer] || colors.news;
  }

  function pointRadius(event) {
    if (event.layer === 'cluster') return Math.min(3.2, 1.2 + Math.log10(event.count + 1));
    if (event.layer === 'flights') return 1.0;
    if (event.layer === 'conflicts' || event.is_conflict) return 1.4;
    if (event.layer === 'earthquakes') {
      const mag = event.magnitude || 4.5;
      return Math.max(1.1, Math.min(2.6, (mag - 2.5) * 0.45 + 0.9));
    }
    if (event.layer === 'nature') return 1.25;
    return 1.1;
  }

  function pointAltitude(event) {
    if (event.layer === 'cluster') return 0.055;
    if (event.layer === 'flights') return 0.085;
    if (event.layer === 'conflicts' || event.is_conflict) return 0.042;
    if (event.layer === 'earthquakes') return 0.032;
    if (event.layer === 'nature') return 0.035;
    return 0.024;
  }

  function tooltip(event) {
    if (event.layer === 'cluster') return `<div class="atlas-tooltip"><b>${event.count} observations</b><span>${esc(event.summary)}</span><small>Zoomez pour les détailler</small></div>`;
    return `<div class="atlas-tooltip">
      <small style="color:${pointColor(event)}">${markerEmoji(event)} ${esc(labels[event.layer] || 'Observation')}</small>
      <b>${esc(event.title)}</b>
      <span>${esc([event.location_name,event.timestamp ? ago(event.timestamp) : ''].filter(Boolean).join(' · '))}</span>
    </div>`;
  }

  function openMarker(event) {
    if (event.layer === 'cluster') {
      flyTo(event.latitude, event.longitude, Math.max(0.45, (globe?.pointOfView?.().altitude || 2.3) * 0.56));
      setTimeout(updateMap, reduced ? 0 : 880);
      return;
    }
    selectEvent(event);
  }

  function markerElement(event) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `atlas-globe-marker${event.layer === 'cluster' ? ' is-cluster' : ''}`;
    button.style.setProperty('--marker-color', pointColor(event));
    button.innerHTML = event.layer === 'cluster' ? `<span>${esc(event.summary)}</span><b>${event.count}</b>` : markerEmoji(event);
    button.title = event.title;
    button.setAttribute('aria-label', event.title);
    button.onclick = click => { click.stopPropagation(); openMarker(event); };
    return button;
  }

  function countryFill(country) {
    if (country === selectedCountry) return '#628AFF';
    const code = countryCode(country);
    const count = availableEvents().filter(event => event.country_code === code && ['conflicts','society','weather','fires','nature'].includes(event.layer)).length;
    if (heat && count) return `rgba(${count > 10 ? '239,68,68' : count > 4 ? '249,115,22' : '66,111,229'},${Math.min(0.92, 0.28 + count * 0.06)})`;
    return style === 'paper' ? '#D0DCED' : style === 'blue' ? '#264C98' : '#233A56';
  }

  function getVisibleArcs(events) {
    const list = [];
    if (links && arcs.length) {
      if (activeEvent) {
        const activeArcs = arcs.filter(a => a.from_id === activeEvent.id || a.to_id === activeEvent.id);
        list.push(...(activeArcs.length ? activeArcs : arcs));
      } else if (selectedCountry) {
        const cCode = countryCode(selectedCountry);
        const countryArcs = arcs.filter(a => {
          const ev1 = news.find(n => n.id === a.from_id);
          const ev2 = news.find(n => n.id === a.to_id);
          return ev1?.country_code === cCode || ev2?.country_code === cCode;
        });
        list.push(...(countryArcs.length ? countryArcs : arcs));
      } else {
        list.push(...arcs);
      }
    }

    if (activeEvent?.layer === 'flights' && activeEvent.from_lat !== undefined && activeEvent.to_lat !== undefined) {
      list.push({
        id: `flight_corridor_${activeEvent.id}`,
        kind: 'flight_corridor',
        from_id: activeEvent.id,
        from_lat: activeEvent.from_lat,
        from_lon: activeEvent.from_lon,
        from_name: activeEvent.origin,
        to_id: `dest_${activeEvent.id}`,
        to_lat: activeEvent.to_lat,
        to_lon: activeEvent.to_lon,
        to_name: activeEvent.destination,
        label: `${activeEvent.title} : ${activeEvent.origin} ➔ ${activeEvent.destination}`
      });
    }

    return list;
  }

  function getRingsData(events) {
    const rings = [];
    if (activeEvent) rings.push(activeEvent);
    for (const e of events) {
      if (e === activeEvent) continue;
      if (e.layer === 'earthquakes') rings.push(e);
      else if (e.layer === 'conflicts' || e.is_conflict) rings.push(e);
      else if (['nature','weather','fires'].includes(e.layer)) rings.push(e);
      else if (e.layer === 'flights' && e.id === activeEvent?.id) rings.push(e);
    }
    return rings.slice(0, 35);
  }

  function updateMap() {
    if (dead) return;
    const events = availableEvents();
    const displayed = clusterEvents(events);
    const visibleArcs = getVisibleArcs(events);
    const rings = getRingsData(events);
    const visiblePaths = detailLevel() >= 1.8 ? providerLayers.flatMap(id => layers.has(id) ? (providers[id]?.paths || []) : []) : [];

    if (globe && mode === '3d') {
      globe.pointsData([])
        .pointRadius(pointRadius)
        .pointAltitude(pointAltitude)
        .pointColor(e => inSelection(e) ? pointColor(e) : '#334155')
        .htmlElementsData(displayed)
        .polygonCapColor(countryFill)
        .arcsData(visibleArcs)
        .ringsData(rings)
        .pathsData(visiblePaths);

      const material = globe.globeMaterial();
      material.color.set(style === 'paper' ? '#EDF2F8' : style === 'blue' ? '#0C2356' : '#091927');
      globe.backgroundColor('rgba(0,0,0,0)');
    }

    if (mode === 'flat' && flatSVG && projection) {
      drawFlat(displayed, visibleArcs, visiblePaths);
    }

    renderList(events.filter(inSelection));
  }

  function renderList(events) {
    const ordered = [...events].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    const countEl = $('.atlas-count');
    if (countEl) countEl.textContent = `${ordered.length}`;
    const placeEl = $('.atlas-tray-place');
    if (placeEl) placeEl.textContent = selectedCountry ? countryName(selectedCountry) : selectedPoint ? 'Autour du point' : 'Actualités mondiales';
    const selection = $('.atlas-selection');
    if (selection) {
      selection.hidden = !selectedCountry && !selectedPoint;
      const span = selection.querySelector('span');
      if (span) span.textContent = selectedCountry ? countryName(selectedCountry) : selectedPoint ? `${selectedPoint.lat.toFixed(2)}°, ${selectedPoint.lng.toFixed(2)}°` : '';
      const sel = selection.querySelector('select');
      if (sel) sel.hidden = !selectedPoint;
    }
    const countrySel = $('.atlas-country');
    if (countrySel) countrySel.value = selectedCountry ? countryCode(selectedCountry) : '';
    const countryBadge = $('.atlas-side-country .side-badge');
    if (countryBadge) countryBadge.textContent = selectedCountry ? countryCode(selectedCountry) : 'Pays';

    if (!ordered.length) {
      const loading = busy || newsStatus === 'loading';
      $('.atlas-events').innerHTML = `<div class="atlas-empty">${icons.globe}<h3>${loading ? 'Recherche des actualités…' : 'Aucune observation'}</h3><p>${loading ? 'Les observations vont apparaître ici.' : newsStatus === 'unavailable' && layers.has('news') ? 'Les actualités sont momentanément inaccessibles.' : 'Aucune observation dans cette sélection. Élargissez la période ou activez d’autres calques.'}</p></div>`;
      return;
    }

    $('.atlas-events').innerHTML = ordered.slice(0, 80).map(event => `
      <button class="atlas-event" data-event="${esc(event.id)}">
        <span class="atlas-event-symbol" style="--dot:${pointColor(event)}">${markerEmoji(event)}</span>
        <span class="atlas-event-body">
          <span class="atlas-event-meta">
            <span style="color:${pointColor(event)}">${esc(event.location_name || event.category || labels[event.layer] || 'Observation')}</span>
            <time>${esc(ago(event.timestamp))}</time>
          </span>
          <strong>${esc(event.title)}</strong>
          <span class="atlas-event-summary">${esc(event.summary || '')}</span>
          <span class="atlas-event-source">${esc(event.source_name || event.sources_names?.join(' · ') || 'Source')}</span>
        </span>
        ${icons.arrow}
      </button>
    `).join('');

    $$('.atlas-event').forEach(button => button.addEventListener('click', () => selectEvent(events.find(e => e.id === button.dataset.event))));
    if (ordered.length > 80) $('.atlas-events').insertAdjacentHTML('beforeend', '<p class="atlas-more">80 observations affichées. Précisez la recherche pour explorer la suite.</p>');
  }

  function selectEvent(event) {
    if (!event) return;
    lastSelectTime = Date.now();
    activeEvent = event;
    selectedPoint = { lat: event.latitude, lng: event.longitude };
    flyTo(event.latitude, event.longitude, event.layer === 'flights' ? 1.25 : 1.15);

    const panel = $('.atlas-spotlight');
    if (panel) {
      panel.hidden = false;
      const source = safeURL(event.source_url || event.sources?.[0]?.url);
      let detailsHTML = '';

      if (['flights','ships'].includes(event.layer)) {
        const facts = [
          event.airline && `<b>Compagnie :</b> ${esc(event.airline)}`,
          event.origin && event.destination && `<b>Itinéraire :</b> ${esc(event.origin)} ➔ ${esc(event.destination)}`,
          Number.isFinite(event.altitude_m) && `<b>Altitude :</b> ${Math.round(event.altitude_m)} m`,
          Number.isFinite(event.speed_kmh) && `<b>Vitesse :</b> ${Math.round(event.speed_kmh)} km/h`,
          Number.isFinite(event.speed_knots) && `<b>Vitesse :</b> ${Number(event.speed_knots).toFixed(1)} nœuds`,
          Number.isFinite(event.heading) && `<b>Cap :</b> ${Math.round(event.heading)}°`,
          `<b>Position :</b> ${event.latitude.toFixed(2)}°, ${event.longitude.toFixed(2)}°`
        ].filter(Boolean);
        detailsHTML = `
          <div style="background:rgba(6,182,212,0.08);border:1px solid rgba(6,182,212,0.25);border-radius:12px;padding:12px;margin:10px 0;font-size:12px;">
            ${facts.map(fact => `<p style="margin:0 0 6px;">${fact}</p>`).join('')}
          </div>
        `;
      } else if (event.layer === 'earthquakes') {
        detailsHTML = `
          <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);border-radius:12px;padding:12px;margin:10px 0;font-size:12px;">
            <p style="margin:0 0 6px;"><b>Magnitude :</b> M${event.magnitude || '—'} · <b>Lieu :</b> ${esc(event.location_name || 'Épicentre')}</p>
            <p style="margin:0;"><b>Source :</b> Réseau sismologique mondial USGS</p>
          </div>
        `;
      }

      panel.innerHTML = `
        <button class="atlas-spotlight-close" aria-label="Fermer le détail">×</button>
        <span class="atlas-eyebrow" style="color:${pointColor(event)}">${markerEmoji(event)} ${esc(labels[event.layer] || 'Observation')}${event.timestamp ? ` · ${esc(ago(event.timestamp))}` : ''}</span>
        <h2>${esc(event.title)}</h2>
        ${detailsHTML}
        <p>${esc(event.detailed_story || event.summary || 'Observation enregistrée sur le réseau.')}</p>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;gap:8px;flex-wrap:wrap;">
          <span>${esc(event.source_name || event.sources_names?.join(' · ') || '')}</span>
          ${(event.layer === 'news' || event.is_conflict) && options.onNews ? '<button class="atlas-read" style="background:#386BFF;color:#fff;border:0;padding:8px 14px;border-radius:14px;font-size:11.5px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px;">Explorer l’information ' + icons.arrow + '</button>' : source ? `<a href="${esc(source)}" target="_blank" rel="noopener noreferrer" style="color:#60A5FA;font-size:12px;text-decoration:none;">Voir la source ${icons.arrow}</a>` : ''}
        </div>
      `;

      panel.querySelector('.atlas-spotlight-close').onclick = () => { activeEvent = null; selectedPoint = null; panel.hidden = true; updateMap(); };
      panel.querySelector('.atlas-read')?.addEventListener('click', () => options.onNews(event));
      panel.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'nearest' });
    }
    updateMap();
  }

  function selectCountry(country) {
    selectedCountry = country; selectedPoint = null; activeEvent = null;
    const p = $('.atlas-spotlight'); if (p) p.hidden = true;
    if (country) flyTo(country.properties.LABEL_Y, country.properties.LABEL_X, 1.35);
    const tray = $('.atlas-news-tray');
    if (tray) {
      tray.classList.remove('collapsed');
      const toggle = $('.atlas-tray-toggle');
      if (toggle) toggle.innerHTML = icons.chevronDown;
    }
    updateMap();
  }

  function flyTo(lat, lng, altitude = 1.8) {
    rotation = false; $('[data-rotate]').setAttribute('aria-pressed', 'false');
    if (globe) { globe.controls().autoRotate = false; globe.pointOfView({ lat, lng, altitude }, reduced ? 0 : 850); }
    if (mode === 'flat' && flatSVG && projection) {
      const point = projection([lng, lat]), w = canvas.clientWidth, h = canvas.clientHeight;
      const scale = altitude > 2 ? 1 : altitude < 1.3 ? 3 : 2;
      flatSVG.transition().duration(reduced ? 0 : 550).call(flatSVG.zoomBehavior.transform, window.d3.zoomIdentity.translate(w / 2 - scale * point[0], h / 2 - scale * point[1]).scale(scale));
    }
  }

  function drawFlat(events, visibleArcs, visiblePaths) {
    const group = flatSVG.select('g');
    group.selectAll('path.atlas-country-path').data(countries).join('path').attr('class', 'atlas-country-path').attr('d', geoPath).attr('fill', countryFill).attr('stroke', style === 'paper' ? '#F6F8FB' : '#547294').attr('stroke-width', 0.45)
      .on('click', (ev, c) => { ev.stopPropagation(); selectCountry(c); }).selectAll('title').data(c => [c]).join('title').text(countryName);
    group.selectAll('path.atlas-arc-path').data(visibleArcs).join('path').attr('class', 'atlas-arc-path').attr('d', a => geoPath({ type: 'LineString', coordinates: [[a.from_lon, a.from_lat], [a.to_lon, a.to_lat]] })).attr('fill', 'none').attr('stroke', '#38BDF8').attr('stroke-width', 0.8).attr('stroke-dasharray', '3,3');
    group.selectAll('path.atlas-infrastructure-path').data(visiblePaths, p => p.id).join('path').attr('class', p => `atlas-infrastructure-path ${p.layer}`).attr('d', p => geoPath({type:'LineString',coordinates:p.points.map(([lat,lng])=>[lng,lat])})).attr('fill','none').attr('stroke',p=>colors[p.layer]).attr('stroke-width',1.4).attr('opacity',.8);
    group.selectAll('text.atlas-point').data(events, e => e.id).join('text').attr('class', e => `atlas-point${e.layer === 'cluster' ? ' is-cluster' : ''}`).attr('x', e => projection([e.longitude, e.latitude])[0]).attr('y', e => projection([e.longitude, e.latitude])[1]).attr('text-anchor','middle').attr('dominant-baseline','central').attr('font-size',e=>e.layer==='cluster'?10:13).attr('paint-order','stroke').attr('stroke','#071526').attr('stroke-width',2.5).attr('fill','#fff').attr('opacity', e => e.layer === 'cluster' || inSelection(e) ? 1 : 0.3).text(e => e.layer === 'cluster' ? e.count : markerEmoji(e)).on('click', (ev, e) => { ev.stopPropagation(); openMarker(e); }).selectAll('title').data(e => [e]).join('title').text(e => e.title);
  }

  function setMode(next) {
    mode = next; $$('.atlas-mode button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === next)));
    $('[data-rotate]').hidden = next === 'flat';
    if (globe) { globe.renderer().domElement.parentElement.style.display = next === '3d' ? 'block' : 'none'; next === '3d' ? globe.resumeAnimation() : globe.pauseAnimation(); }
    if (flatSVG) flatSVG.style('display', next === 'flat' ? 'block' : 'none');
    updateMap();
  }

  function statusUI() {
    const activeProviders = Object.values(providers).filter(p => layers.has(p.id));
    const unavailable = activeProviders.some(p => p.status === 'unavailable') || (layers.has('news') && newsStatus === 'unavailable');
    const stale = activeProviders.some(p => p.status === 'stale') || (layers.has('news') && newsStatus === 'stale');
    const status = $('.atlas-observation');
    status.dataset.state = unavailable ? 'unavailable' : stale ? 'stale' : 'live';
    status.querySelector('span').textContent = busy ? 'Actualisation…' : unavailable ? 'Certaines sources indisponibles' : stale ? 'Dernières données conservées' : updatedAt ? `Actualisé à ${new Date(updatedAt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}` : 'En direct';
    $('.atlas-provider-notes').innerHTML = Object.values(providers).filter(p => layers.has(p.id)).map(p => `<p><b>${esc(p.provider)}</b> · ${{live:'Connecté',stale:'Données conservées',limited:'Couverture partielle',static:'Données locales',unavailable:'Indisponible'}[p.status] || 'Indisponible'}<br>${esc(p.note)}${p.fetched_at ? `<br>Relevé : ${esc(new Date(p.fetched_at).toLocaleString('fr-FR'))}` : ''}</p>`).join('');
  }

  async function refresh() {
    if (busy || dead) return;
    busy = true; statusUI();
    const activeProviderLayers = providerLayers.filter(id => layers.has(id));
    const include = activeProviderLayers.join(',');
    await Promise.all([
      fetchJSON('/api/globe/events').then(data => {
        if (dead) return;
        news = (data.events || []).map(e => ({ ...e, id: e.alert_id || e.id, layer: 'news' }));
        arcs = data.arcs || [];
        newsStatus = 'live';
      }).catch(() => { newsStatus = news.length ? 'stale' : 'unavailable'; }),
      (include ? fetchJSON('/api/atlas/layers?include=' + include) : Promise.resolve({layers:[]})).then(data => {
        if (dead) return;
        for (const p of data.layers || []) providers[p.id] = p;
      }).catch(() => {
        for (const id of activeProviderLayers) providers[id] = { id, provider: labels[id], events: [], paths: [], status: 'unavailable', note: 'Connexion aux observations indisponible.' };
      })
    ]);
    busy = false;
    if (dead) return;
    updatedAt = new Date().toISOString();
    statusUI();
    updateMap();
  }

  function toggleChip(chipName) {
    if (chipName === 'links') {
      links = !links;
      const chip = $(`[data-chip="links"]`);
      if (chip) chip.classList.toggle('active', links);
      const input = $('[data-option="links"]');
      if (input) input.checked = links;
    } else {
      if (layers.has(chipName)) {
        layers.delete(chipName);
      } else {
        layers.add(chipName);
        if (providerLayers.includes(chipName) && !providers[chipName]) refresh();
      }
      const chip = $(`[data-chip="${chipName}"]`);
      if (chip) chip.classList.toggle('active', layers.has(chipName));
      const input = $(`[data-layer="${chipName}"]`);
      if (input) input.checked = layers.has(chipName);
    }
    updateMap();
    statusUI();
  }

  function onVisibility() {
    if (dead) return;
    if (document.hidden) globe?.pauseAnimation();
    else {
      if (mode === '3d') globe?.resumeAnimation();
      refresh();
    }
  }

  // Event handlers
  $('.atlas-refresh').onclick = refresh;
  $('.atlas-layer-button').onclick = () => {
    const p = $('.atlas-layer-panel');
    p.hidden = !p.hidden;
    $('.atlas-layer-button').setAttribute('aria-expanded', String(!p.hidden));
  };
  $$('.atlas-mode button').forEach(b => b.onclick = () => setMode(b.dataset.mode));

  $$('[data-chip]').forEach(chip => {
    chip.onclick = () => toggleChip(chip.dataset.chip);
  });

  $$('[data-layer]').forEach(input => input.onchange = () => {
    input.checked ? layers.add(input.dataset.layer) : layers.delete(input.dataset.layer);
    const chip = $(`[data-chip="${input.dataset.layer}"]`);
    if (chip) chip.classList.toggle('active', input.checked);
    if (input.checked && providerLayers.includes(input.dataset.layer) && !providers[input.dataset.layer]) refresh();
    updateMap();
    statusUI();
  });

  $('[data-option="heat"]').onchange = e => { heat = e.target.checked; updateMap(); };
  $('[data-option="links"]').onchange = e => {
    links = e.target.checked;
    const chip = $(`[data-chip="links"]`);
    if (chip) chip.classList.toggle('active', links);
    updateMap();
  };
  $('.atlas-style select').onchange = e => { style = e.target.value; root.dataset.style = style; updateMap(); };

  const searchInput = $('.atlas-search input');
  const searchClear = $('.atlas-search-clear');
  if (searchInput) {
    searchInput.oninput = e => {
      query = e.target.value.trim().toLowerCase();
      if (searchClear) searchClear.hidden = !query;
      if (query) {
        $('.atlas-news-tray')?.classList.remove('collapsed');
        const toggle = $('.atlas-tray-toggle');
        if (toggle) toggle.innerHTML = icons.chevronDown;
      }
      updateMap();
    };
  }
  if (searchClear) {
    searchClear.onclick = () => {
      if (searchInput) searchInput.value = '';
      query = '';
      searchClear.hidden = true;
      updateMap();
    };
  }

  $('.atlas-country').onchange = e => selectCountry(countries.find(c => countryCode(c) === e.target.value) || null);
  $('.atlas-time').onchange = e => {
    rangeHours = Number(e.target.value);
    const badge = $('.atlas-side-time .side-badge');
    if (badge) badge.textContent = { 24: '24h', 72: '3j', 168: '7j', 0: 'Tout' }[rangeHours] || '24h';
    updateMap();
  };

  const tray = $('.atlas-news-tray');
  const trayToggle = $('.atlas-tray-toggle');
  const trayHeader = $('.atlas-tray-header');
  if (tray && trayHeader) {
    trayHeader.onclick = e => {
      if (e.target.closest('.atlas-selection select') || e.target.closest('.atlas-selection button')) return;
      tray.classList.toggle('collapsed');
      const isCollapsed = tray.classList.contains('collapsed');
      if (trayToggle) trayToggle.innerHTML = isCollapsed ? icons.chevronUp : icons.chevronDown;
    };
  }

  $('.atlas-selection button').onclick = () => { selectedCountry = null; selectedPoint = null; updateMap(); };
  $('.atlas-selection select').onchange = e => { radius = Number(e.target.value); updateMap(); };

  $$('[data-preset]').forEach(button => button.onclick = () => {
    const p = { world: [22, 12, 2.3], europe: [48, 15, 1.15], americas: [23, -95, 1.6], asia: [30, 105, 1.5] }[button.dataset.preset];
    selectedCountry = null; selectedPoint = null; flyTo(...p); updateMap();
    $$('[data-preset]').forEach(b => b.classList.toggle('active', b === button));
  });

  $$('[data-zoom]').forEach(button => button.onclick = () => {
    const action = button.dataset.zoom;
    if (action === 'reset') { selectedCountry = null; selectedPoint = null; flyTo(22, 12, 2.3); updateMap(); return; }
    if (mode === 'flat' && flatSVG) { flatSVG.transition().duration(250).call(flatSVG.zoomBehavior.scaleBy, action === 'in' ? 1.35 : 1 / 1.35); return; }
    if (globe) { const pov = globe.pointOfView(); globe.pointOfView({ ...pov, altitude: Math.max(0.35, Math.min(4.5, pov.altitude * (action === 'in' ? 0.78 : 1.28))) }, reduced ? 0 : 350); }
  });

  $('[data-rotate]').onclick = () => {
    rotation = !rotation;
    if (globe) globe.controls().autoRotate = rotation;
    $('[data-rotate]').setAttribute('aria-pressed', String(rotation));
  };

  try {
    const [Globe, d3, geo] = await Promise.all([
      script('globe.gl-2.46.2.min.js', 'Globe'),
      script('d3-7.9.0.min.js', 'd3'),
      fetch(ASSETS + 'countries.geojson', { signal: controller.signal }).then(r => { if (!r.ok) throw Error('Fond de carte indisponible'); return r.json(); })
    ]);
    if (dead) return cleanup;
    countries = geo.features.filter(c => c.properties.ADMIN !== 'Antarctica');
    $('.atlas-country').insertAdjacentHTML('beforeend', [...countries].sort((a, b) => countryName(a).localeCompare(countryName(b), 'fr')).map(c => `<option value="${esc(countryCode(c))}">${esc(countryName(c))}</option>`).join(''));

    try {
      const globeMount = document.createElement('div'); globeMount.className = 'atlas-webgl'; canvas.append(globeMount);
      globe = new Globe(globeMount, { animateIn: !reduced, rendererConfig: { antialias: true, alpha: true } })
        .width(canvas.clientWidth).height(canvas.clientHeight).backgroundColor('rgba(0,0,0,0)').showAtmosphere(true).atmosphereColor('#6497FA').atmosphereAltitude(0.15)
        .showGraticules(false).polygonsData(countries).polygonAltitude(0.003).polygonCapColor(countryFill).polygonSideColor(() => '#102643').polygonStrokeColor(() => '#587598')
        .polygonLabel(c => `<div class="atlas-tooltip"><b>${esc(countryName(c))}</b><small>Explorer les observations</small></div>`).polygonsTransitionDuration(reduced ? 0 : 180)
        .onPolygonClick(selectCountry).onPolygonHover(country => { canvas.style.cursor = country ? 'pointer' : 'grab'; })
        .pointLat('latitude').pointLng('longitude').pointAltitude(pointAltitude).pointRadius(pointRadius).pointColor(pointColor).pointLabel(tooltip).onPointClick(selectEvent).pointsTransitionDuration(reduced ? 0 : 200)
        .htmlLat('latitude').htmlLng('longitude').htmlAltitude(e => e.layer === 'cluster' ? 0.06 : 0.035).htmlElement(markerElement)
        .pathPoints('points').pathPointLat(point => point[0]).pathPointLng(point => point[1]).pathColor(path => colors[path.layer] || '#38BDF8').pathStroke(path => path.layer === 'pipelines' ? 1.2 : 0.8).pathDashLength(path => path.layer === 'pipelines' ? 0.25 : 1).pathDashGap(path => path.layer === 'pipelines' ? 0.08 : 0).pathDashAnimateTime(reduced ? 0 : 5000)
        .arcStartLat('from_lat').arcStartLng('from_lon').arcEndLat('to_lat').arcEndLng('to_lon')
        .arcColor(a => {
          if (a.kind === 'flight_corridor') return ['#00F2FE', '#3B82F6'];
          if (a.from_id === activeEvent?.id || a.to_id === activeEvent?.id) return ['#00F2FE', '#6366F1'];
          return ['#06B6D4AA', '#818CF8AA'];
        })
        .arcDashLength(0.4).arcDashGap(0.25).arcDashAnimateTime(reduced ? 0 : 2200)
        .arcStroke(a => a.kind === 'flight_corridor' || a.from_id === activeEvent?.id || a.to_id === activeEvent?.id ? 2.2 : 0.95)
        .arcAltitudeAutoScale(0.3)
        .arcLabel(a => `<div class="atlas-tooltip"><b>${esc(a.kind === 'flight_corridor' ? 'Trajectoire de vol' : 'Lien thématique')}</b><span>${esc(a.label || 'Observation')}</span><small>${esc(a.from_name || '')} ↔ ${esc(a.to_name || '')}</small></div>`)
        .ringLat('latitude').ringLng('longitude')
        .ringColor(e => {
          if (e.layer === 'earthquakes') {
            const mag = e.magnitude || 4.5;
            const c = mag >= 6.0 ? '220, 38, 38' : mag >= 5.0 ? '249, 115, 22' : '245, 158, 11';
            return t => `rgba(${c}, ${Math.max(0, 1 - t)})`;
          }
          if (e.layer === 'conflicts' || e.is_conflict) return t => `rgba(239, 68, 68, ${Math.max(0, 1 - t)})`;
          if (e.layer === 'nature') return t => `rgba(16, 185, 129, ${Math.max(0, 1 - t)})`;
          if (e.layer === 'flights') return t => `rgba(6, 182, 212, ${Math.max(0, 1 - t)})`;
          return t => `rgba(56, 189, 248, ${Math.max(0, 1 - t)})`;
        })
        .ringMaxRadius(e => e.layer === 'earthquakes' ? Math.max(3.2, (e.magnitude || 4) * 0.85) : e.layer === 'flights' ? 2.8 : 4.2)
        .ringPropagationSpeed(reduced ? 0 : 1.3)
        .ringRepeatPeriod(reduced ? 0 : 1700)
        .onGlobeClick(() => {
          if (Date.now() - lastSelectTime < 700) return;
          if (hasDragged) return;
          if (selectedPoint || selectedCountry || activeEvent) {
            selectedCountry = null;
            selectedPoint = null;
            activeEvent = null;
            const p = $('.atlas-spotlight'); if (p) p.hidden = true;
            updateMap();
          }
        });

      globe.controls().autoRotate = false; globe.controls().autoRotateSpeed = 0.4; globe.controls().enableDamping = true;
      globe.controls().addEventListener('end', () => { cancelAnimationFrame(renderFrame); renderFrame = requestAnimationFrame(updateMap); });
      globe.pointOfView({ lat: 22, lng: 12, altitude: 2.3 }, 0);
      globe.renderer().setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    } catch {
      globe = null; mode = 'flat'; $('[data-mode="3d"]').disabled = true;
    }

    flatSVG = d3.select(canvas).append('svg').attr('class', 'atlas-flat').attr('aria-label', 'Carte plane interactive').style('display', mode === 'flat' ? 'block' : 'none'); flatSVG.append('g');
    flatSVG.zoomBehavior = d3.zoom().scaleExtent([1, 10]).on('zoom', e => { flatZoom = e.transform.k; flatSVG.select('g').attr('transform', e.transform); }).on('end', () => { cancelAnimationFrame(renderFrame); renderFrame = requestAnimationFrame(updateMap); }); flatSVG.call(flatSVG.zoomBehavior);
    flatSVG.on('click', event => {
      if (Date.now() - lastSelectTime < 700) return;
      if (hasDragged) return;
      const point = d3.zoomTransform(flatSVG.node()).invert(d3.pointer(event)); const coords = projection.invert(point);
      if (!coords || !coords.every(Number.isFinite) || Math.abs(coords[1]) > 90) return;
      if (selectedPoint || selectedCountry || activeEvent) {
        selectedCountry = null; selectedPoint = null; activeEvent = null;
        updateMap();
      }
    });

    const resize = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight; if (!w || !h) return;
      if (globe) globe.width(w).height(h);
      flatSVG.attr('viewBox', `0 0 ${w} ${h}`);
      projection = d3.geoNaturalEarth1().fitExtent([[20, 80], [w - 20, h - 70]], { type: 'Sphere' }); geoPath = d3.geoPath(projection); updateMap();
    };

    resizeObserver = new ResizeObserver(resize); resizeObserver.observe(canvas); resize(); setMode(mode);
    $('.atlas-map-message').hidden = true;
    document.addEventListener('visibilitychange', onVisibility);

    await refresh();
    poll = setInterval(() => { if (!document.hidden) refresh(); }, 120000);
  } catch (error) {
    if (!dead) {
      $('.atlas-map-message').textContent = 'Le fond de carte ne peut pas être chargé. Les observations restent accessibles ci-dessous.';
      await refresh();
    }
  }

  return cleanup;
}
