import {esc, safeURL, plain, normalizeEvent, sourceCount, uniqueEvents, relativeTime, formatEventTime, faviconForDomain, getThreeBullets, renderMarkdown} from './mizan-model.js?v=2.7';
import {t, setLanguage, getLanguage} from './mizan-i18n.js?v=2.7';
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const icons = {
  feed: '<path d="M4 5h16M4 12h10M4 19h13"/><circle cx="19" cy="12" r="1"/>',
  globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 6h14M5 18h14"/>',
  bookmark: '<path d="M6 4h12v17l-6-4-6 4z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
  sparkles: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5zM20 2v4M18 4h4"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  'arrow-up': '<path d="M12 19V5m-5 5 5-5 5 5"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  sliders: '<path d="M4 7h9m4 0h3M4 17h3m4 0h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 6a8 8 0 0 1 14 6M18 18a8 8 0 0 1-14-6"/>',
  radio: '<path d="M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14M8 8a6 6 0 0 0 0 8M16 8a6 6 0 0 1 0 8"/><circle cx="12" cy="12" r="1.5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  verified: '<path fill="#1d9bf0" stroke="none" d="M22.25 12c0-1.43-.88-2.67-2.19-3.34.46-1.39.2-2.9-.81-3.91s-2.52-1.27-3.91-.81c-.66-1.31-1.91-2.19-3.34-2.19s-2.67.88-3.33 2.19c-1.4-.46-2.91-.2-3.92.81s-1.26 2.52-.8 3.91c-1.31.67-2.2 1.91-2.2 3.34s.89 2.67 2.2 3.34c-.46 1.39-.21 2.9.8 3.91s2.52 1.26 3.91.81c.67 1.31 1.91 2.19 3.34 2.19s2.68-.88 3.34-2.19c1.39.45 2.9.2 3.91-.81s1.27-2.52.81-3.91c1.31-.67 2.19-1.91 2.19-3.34zm-11.71 4.2L6.8 12.46l1.41-1.42 2.26 2.26 4.8-5.23 1.47 1.36-6.2 6.77z"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8zM2 12l10 5 10-5M2 16l10 5 10-5"/>',
  share: '<path d="M12 16V3m-4 4 4-4 4 4M5 12v8h14v-8"/>',
  heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z"/>',
  minus: '<path d="M5 12h14"/>',
  plus: '<path d="M5 12h14M12 5v14"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7"/>',
  play: '<path d="m8 4 13 8-13 8z"/>',
  code: '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  trash: '<path d="M3 6h18m-2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.info}</svg>`;
const hydrateIcons = (root = document) => root.querySelectorAll('[data-icon]').forEach(el => el.innerHTML = icon(el.dataset.icon));
const readLocal = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
const writeLocal = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} };
const CURRENT_EDITORIAL_VERSION = 'editorial-6';
const storedTimeWindow = (() => { try { const value=localStorage.getItem('mizan.timeWindow'); return value===null ? 24 : Number(value); } catch { return 24; } })();
const initialFeedCache = readLocal('mizan.feed-cache', null);

const defaultProfile = {
  username: 'default_user',
  display_name: '',
  interests: {},
  bio_markdown: '',
  rejection_rules: [],
  entity_watchlist: [],
  preferred_language: 'fr',
  min_score_threshold: 0.5
};

const state = {
  route: 'feed',
  profileTab: 'profile',
  timeWindow: Number.isFinite(storedTimeWindow) ? storedTimeWindow : 24,
  tab: 'for-you',
  topic: 'all',
  country: 'all',
  viewMode: 'list',
  query: '',
  items: Array.isArray(initialFeedCache?.items)
    ? initialFeedCache.items.filter(x=>x?.editorial_version === CURRENT_EDITORIAL_VERSION).map(normalizeEvent)
    : [],
  saved: [],
  mode: 'v2',
  profile: defaultProfile,
  health: null,
  loading: false,
  error: '',
  offset: 0,
  hasMore: false,
  libraryTab: 'saved',
  pending: 0,
  pendingItems: [],
  read: new Set(readLocal('mizan.read', [])),
  liked: new Set(readLocal('mizan.liked', [])),
  legacySaved: readLocal('mizan.legacy-saved', []),
  hidden: new Set(readLocal('mizan.hidden', [])),
  generation: 0
};

let atlasCleanup = null, loadObserver = null, toastTimer, detailGeneration = 0, searchGeneration = 0, routeGeneration = 0;
let profileDraft = null, libraryGeneration = 0, contentCache = null, feedController = null, feedDirty = false, isPageUnloading = false;
window.addEventListener('beforeunload', () => { isPageUnloading = true; });
window.addEventListener('pagehide', () => { isPageUnloading = true; });
const detailItems = new Map();
const setPreference = (key,value) => { try { localStorage.setItem(key,value); } catch {} };

export function applyTheme(theme) {
  const currentPalette = localStorage.getItem('mizan.palette') || 'standard';
  if (currentPalette === 'nightBlue') {
    document.documentElement.dataset.theme = 'dark';
    document.documentElement.dataset.themeSetting = theme;
    return;
  }
  const effective = theme === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : theme;
  document.documentElement.dataset.theme = effective;
  document.documentElement.dataset.themeSetting = theme;
}

export function applyPalette(palette) {
  document.documentElement.dataset.palette = palette || 'standard';
  applyTheme(localStorage.getItem('mizan.theme') || 'system');
}

export function applyFontStyle(fontStyle) {
  document.documentElement.dataset.fontStyle = fontStyle || 'modern';
}

const availableLanguages = [
  ['fr', '🇫🇷 Français'],
  ['en', '🇬🇧 English'],
  ['es', '🇪🇸 Español'],
  ['de', '🇩🇪 Deutsch'],
  ['it', '🇮🇹 Italiano'],
  ['pt', '🇵🇹 Português'],
  ['nl', '🇳🇱 Nederlands'],
  ['ru', '🇷🇺 Русский'],
  ['ar', '🇸🇦 العربية'],
  ['zh', '🇨🇳 中文'],
  ['ja', '🇯🇵 日本語']
];

const availableTimeWindows = [
  [1, '1 heure'],
  [6, '6 heures'],
  [12, '12 heures'],
  [24, '24 heures'],
  [48, '48 heures'],
  [72, '3 jours'],
  [168, '7 jours'],
  [0, 'Tout afficher']
];

const availablePalettes = [
  {
    id: 'standard',
    name: 'Papier Éditorial',
    subtitle: 'Papier clair et bleu MIZAN (#F6F8FB)',
    swatches: ['#f6f8fb', '#ffffff', '#386bff', '#101b2d']
  },
  {
    id: 'sepia',
    name: 'Sépia d’Archive',
    subtitle: 'Chaleur de bibliothèque (#F5F0E6)',
    swatches: ['#f5f0e6', '#faf6ec', '#8b572a', '#2d2319']
  },
  {
    id: 'nightBlue',
    name: 'Nuit Bleue',
    subtitle: 'Bleu marine profond nocturne (#0D1B2A)',
    swatches: ['#0d1b2a', '#1b2838', '#5c8dff', '#e6eef8']
  },
  {
    id: 'contrastInk',
    name: 'Encre & Contraste',
    subtitle: 'Blanc éclatant et encre noire pure',
    swatches: ['#fffef5', '#ffffff', '#0040dd', '#000000']
  }
];

const availableFontStyles = [
  {
    id: 'modern',
    name: 'Moderne Minimaliste',
    subtitle: 'Sans-serif épuré haute lisibilité (Twitter / SF Pro)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
  },
  {
    id: 'editorial',
    name: 'Éditorial Classique',
    subtitle: 'Serif traditionnel façon Le Monde & New York Times',
    fontFamily: '"Newsreader", "Charter", "Georgia", "Times New Roman", serif'
  },
  {
    id: 'financial',
    name: 'Gazette Financière',
    subtitle: 'Serif compact dense façon Financial Times',
    fontFamily: '"Playfair Display", "Times New Roman", "Georgia", serif'
  },
  {
    id: 'rounded',
    name: 'Presse Diplomatique',
    subtitle: 'Arrondi contemporain haute distinction',
    fontFamily: 'ui-rounded, "DM Sans", -apple-system, sans-serif'
  },
  {
    id: 'monospaced',
    name: 'Dépêche & Télégraphe',
    subtitle: 'Monospace technique brut façon téléscripteur d’agence',
    fontFamily: 'ui-monospace, "SF Mono", "Menlo", monospace'
  }
];

try {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if ((localStorage.getItem('mizan.theme') || 'system') === 'system') {
      applyTheme('system');
    }
  });
  applyPalette(localStorage.getItem('mizan.palette') || 'standard');
  applyFontStyle(localStorage.getItem('mizan.font-style') || 'modern');
} catch {}

export async function api(path, options = {}) {
  const {timeout:timeoutMs=25000,signal:externalSignal,...request}=options;
  const controller=new AbortController(),abort=()=>controller.abort();
  if(externalSignal?.aborted)controller.abort();
  externalSignal?.addEventListener('abort',abort,{once:true});
  const timer=setTimeout(abort,timeoutMs);
  try {
    const response=await fetch(path,{...request,signal:controller.signal,headers:{'Content-Type':'application/json',...request.headers}});
    let data;try{data=await response.json()}catch{throw new Error('Réponse du serveur illisible.');}
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:`Le serveur a répondu ${response.status}.`);
    return data;
  } catch(e) {if(e.name==='AbortError'&&!externalSignal?.aborted)throw new Error('Le serveur met trop de temps à répondre. Réessayez.');throw e;}
  finally{clearTimeout(timer);externalSignal?.removeEventListener('abort',abort);}
}

const post = (path, body) => api(path, {method: 'POST', body: JSON.stringify(body), timeout: 60000});

function toast(message) {
  const el = $('#toast');
  if (!el) return;
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.hidden = true, 4500);
}

const empty = (title, text, action = '', label = '') =>
  `<div class="empty-state">${icon('feed')}<h2>${esc(title)}</h2><p>${esc(text)}</p>${action ? `<button class="button" data-action="${esc(action)}">${esc(label)}</button>` : ''}</div>`;
const loading = (text = 'Chargement…') =>
  `<div class="empty-state"><span class="loading-orbit"></span><p>${esc(text)}</p></div>`;

function setConnection(label, live = false) {
  const e = $('#connection');
  if (!e) return;
  e.textContent = label;
  e.classList.toggle('live', live);
}

function applyLanguage(lang) {
  setLanguage(lang);
  if (state.profile) {
    state.profile.preferred_language = lang;
  }
  const locale = lang === 'en' ? 'en-US' : (lang === 'es' ? 'es-ES' : (lang === 'ar' ? 'ar-SA' : `${lang}-${lang.toUpperCase()}`));
  try {
    const d = $('#edition-date');
    if (d) d.textContent = new Intl.DateTimeFormat(locale, {weekday: 'long', day: 'numeric', month: 'long'}).format(new Date());
  } catch (e) {}
  renderNav();
  if (state.route === 'feed') {
    state.items = [];
    state.offset = 0;
    state.hasMore = true;
    renderFeed();
    loadFeed();
  } else if (state.route === 'profile') {
    renderProfile();
  }
}

function renderNav() {
  const nav = [
    ['feed', 'feed', t('nav_feed')],
    ['atlas', 'globe', t('nav_explore')],
    ['library', 'bookmark', t('nav_bookmarks')],
    ['profile', 'user', t('nav_profile')]
  ].map(([route, name, label]) =>
    `<a class="nav-item ${route === state.route ? 'active' : ''}" href="#${route}" ${route === state.route ? 'aria-current="page"' : ''}>${icon(name)}<span>${label}</span></a>`
  ).join('');
  if ($('.primary-nav')) $('.primary-nav').innerHTML = nav;
  if ($('.mobile-nav')) $('.mobile-nav').innerHTML = nav;
  const name = state.profile?.display_name || t('account_profile');
  if ($('#account-name')) $('#account-name').textContent = name;
  if ($('#account-initial')) $('#account-initial').textContent = name.slice(0, 1).toUpperCase();
}

function renderRail() {
  const rail = $('#right-rail');
  if (rail) rail.innerHTML = '';
}

function formatRichSummary(text, isStory = false) {
  if (!text) return '';
  let str = String(text).trim();
  str = str.replace(/^\*\*(?:Faits confirmés|Recoupement éditorial|Recoupement editorial|Suivi éditorial|suivi editorial|Couverture source)\*\*\s*:\s*/gi, '');
  str = str.replace(/\b(?:Faits confirmés|Recoupement éditorial|Recoupement editorial|Suivi éditorial|suivi editorial|Couverture source)\b\s*:?\s*/gi, '');
  if (str.includes(' • ')) {
    const parts = str.split(' • ')
      .map(s => {
        let p = s.trim();
        p = p.replace(/^\*\*(?:Faits confirmés|Recoupement éditorial|Recoupement editorial|Suivi éditorial|suivi editorial|Couverture source)\*\*\s*:\s*/gi, '');
        p = p.replace(/\b(?:Faits confirmés|Recoupement éditorial|Recoupement editorial|Suivi éditorial|suivi editorial|Couverture source)\b\s*:?\s*/gi, '');
        return p.trim();
      })
      .filter(p => p.length > 5 && !p.toLowerCase().includes('information rapportée et recoupée') && !p.toLowerCase().includes('veille active'));
    return `<ul class="story-bullets">${parts.map(p => `<li>${renderMarkdown(p)}</li>`).join('')}</ul>`;
  }
  return `<p class="story-summary">${renderMarkdown(str)}</p>`;
}

// MARK: - FEED LIST TWEET CARD (Twitter/X Style Stream)
function storyCard(item, index = 0) {
  const count = sourceCount(item);
  const source = item.sources[0];
  const saved = item.saved || state.legacySaved.some(x => x.id === item.id);
  const isLiked = state.liked.has(item.id);
  const bullets = getThreeBullets(item);

  if (count > 1) {
    return `
      <article class="tweet-card story multi-source" data-story="${esc(item.id)}" style="animation-delay:${Math.min(index, 5) * 30}ms">
        <div class="tweet-multi-header-scroll">
          <div class="tweet-sources-track">
            ${item.sources.map(s => {
              const d = (s.domain || '').toLowerCase().replace(/^www\./, '');
              const fav = s.favicon || (d ? faviconForDomain(d) : '');
              const name = esc(s.name || d || 'Source');
              const av = fav
                ? `<img class="source-chip-logo" src="${esc(fav)}" alt="" loading="lazy" referrerpolicy="no-referrer"/>`
                : `<span class="source-chip-fallback">${esc(name.slice(0, 2).toUpperCase())}</span>`;
              return `<span class="source-chip">${av}<span class="source-chip-name">${name}</span></span>`;
            }).join('')}
          </div>
          <div class="tweet-multi-meta">
            <span class="tweet-dot">·</span>
            <time class="tweet-time" datetime="${esc(item.date)}">${esc(formatEventTime(item))}</time>
            <span class="tweet-multi-count">${count} ${t('sources_count')}</span>
            ${(item.countries || []).map(c => `<span class="badge-country" title="${esc(c.name)}">${c.flag}</span>`).join('')}
            ${item.isVo ? `<span class="badge-vo" title="${esc(t('badge_vo_title'))}">${t('badge_vo')}</span>` : ''}
          </div>
        </div>

        <button class="tweet-body" data-action="detail" data-id="${esc(item.id)}">
          <h2 class="tweet-title">${esc(item.title)}</h2>
          <ul class="tweet-bullets">
            ${bullets.map(b => `<li>${renderMarkdown(b)}</li>`).join('')}
          </ul>
          ${item.image ? `
            <div class="tweet-media">
              <img src="${esc(item.image)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">
            </div>
          ` : ''}
        </button>

        <footer class="tweet-actions">
          <button class="tweet-action-btn" data-action="detail" data-id="${esc(item.id)}" title="${esc(t('action_details'))}">
            ${icon('feed')} <span>${t('action_details')}</span>
          </button>
          <button class="tweet-action-btn multi" data-action="detail" data-id="${esc(item.id)}" title="${count} ${t('sources_count')}">
            ${icon('layers')} <span>${count} ${t('sources_count')}</span>
          </button>
          <button class="tweet-action-btn" data-action="reject" data-id="${esc(item.id)}" aria-label="${esc(t('action_less_like_this'))}" title="${esc(t('action_less_like_this'))}">${icon('minus')}</button>
          <button class="tweet-action-btn ${isLiked ? 'liked' : ''}" data-action="interest" data-id="${esc(item.id)}" aria-label="${esc(t('action_interested'))}" title="${esc(t('action_interested'))}" style="${isLiked ? 'color:#f91880;' : ''}">
            ${icon('heart')} <span>${isLiked ? t('action_like') : ''}</span>
          </button>
          <button class="tweet-action-btn ${saved ? 'saved' : ''}" data-action="save" data-id="${esc(item.id)}" aria-label="${esc(saved ? t('detail_remove_saved') : t('action_save'))}" aria-pressed="${saved}" title="${esc(saved ? t('action_saved') : t('action_save'))}">
            ${icon('bookmark')}
          </button>
          <button class="tweet-action-btn" data-action="share" data-id="${esc(item.id)}" aria-label="${esc(t('action_share'))}" title="${esc(t('action_share'))}">
            ${icon('share')}
          </button>
        </footer>
      </article>
    `;
  }

  const favicon = item.primaryFavicon || (source?.domain ? faviconForDomain(source.domain) : '');
  const avatarMarkup = favicon
    ? `<img class="tweet-avatar" src="${esc(favicon)}" alt="" loading="lazy" referrerpolicy="no-referrer"/>`
    : `<span class="tweet-avatar-fallback" aria-hidden="true">${esc((source?.name || 'M').slice(0, 2).toUpperCase())}</span>`;

  return `
    <article class="tweet-card story" data-story="${esc(item.id)}" style="animation-delay:${Math.min(index, 5) * 30}ms">
      <div class="tweet-left">
        ${avatarMarkup}
      </div>
      <div class="tweet-right">
        <header class="tweet-header">
          <span class="tweet-author">${esc(source?.name || 'Actualité')}</span>
          <span class="tweet-dot">·</span>
          <time class="tweet-time" datetime="${esc(item.date)}">${esc(formatEventTime(item))}</time>
          ${(item.countries || []).map(c => `<span class="badge-country" title="${esc(c.name)}">${c.flag}</span>`).join('')}
          ${item.isVo ? `<span class="badge-vo" title="${esc(t('badge_vo_title'))}">${t('badge_vo')}</span>` : ''}
        </header>

        <button class="tweet-body" data-action="detail" data-id="${esc(item.id)}">
          <h2 class="tweet-title">${esc(item.title)}</h2>
          <ul class="tweet-bullets">
            ${bullets.map(b => `<li>${renderMarkdown(b)}</li>`).join('')}
          </ul>
          ${item.image ? `
            <div class="tweet-media">
              <img src="${esc(item.image)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">
            </div>
          ` : ''}
        </button>

        <footer class="tweet-actions">
          <button class="tweet-action-btn" data-action="detail" data-id="${esc(item.id)}" title="${esc(t('action_details'))}">
            ${icon('feed')} <span>${t('action_details')}</span>
          </button>
          <button class="tweet-action-btn" data-action="detail" data-id="${esc(item.id)}" title="${item.sourceCount > 1 ? `${item.sourceCount} ${t('sources_count')}` : esc(source?.name || 'Source')}">
            ${icon('layers')} <span>${item.sourceCount > 1 ? `${item.sourceCount} ${t('sources_count')}` : esc(source?.name || 'Source')}</span>
          </button>
          <button class="tweet-action-btn" data-action="reject" data-id="${esc(item.id)}" aria-label="${esc(t('action_less_like_this'))}" title="${esc(t('action_less_like_this'))}">${icon('minus')}</button>
          <button class="tweet-action-btn ${isLiked ? 'liked' : ''}" data-action="interest" data-id="${esc(item.id)}" aria-label="${esc(t('action_interested'))}" title="${esc(t('action_interested'))}" style="${isLiked ? 'color:#f91880;' : ''}">
            ${icon('heart')} <span>${isLiked ? t('action_like') : ''}</span>
          </button>
          <button class="tweet-action-btn ${saved ? 'saved' : ''}" data-action="save" data-id="${esc(item.id)}" aria-label="${esc(saved ? t('detail_remove_saved') : t('action_save'))}" aria-pressed="${saved}" title="${esc(saved ? t('action_saved') : t('action_save'))}">
            ${icon('bookmark')}
          </button>
          <button class="tweet-action-btn" data-action="share" data-id="${esc(item.id)}" aria-label="${esc(t('action_share'))}" title="${esc(t('action_share'))}">
            ${icon('share')}
          </button>
        </footer>
      </div>
    </article>
  `;
}

function filteredItems() {
  let items = state.items.filter(x => !state.hidden.has(x.id));
  if (state.timeWindow > 0) {
    const cutoff = Date.now() - state.timeWindow * 3600 * 1000;
    items = items.filter(x => {
      const t = Date.parse(x.date);
      return !isNaN(t) && t >= cutoff && t <= Date.now() + 5 * 60000;
    });
  }
  if (state.tab === 'multi') items = items.filter(x => sourceCount(x) > 1);
  if (state.tab === 'single') items = items.filter(x => sourceCount(x) <= 1);
  if (state.topic !== 'all') {
    const t = state.topic.toLocaleLowerCase('fr');
    items = items.filter(x => `${x.topic} ${x.title} ${x.summary}`.toLocaleLowerCase('fr').includes(t));
  }
  if (state.country !== 'all') {
    items = items.filter(x => (x.countryNames || []).includes(state.country));
  }
  if (state.tab === 'latest') items = [...items].sort((a, b) => (Date.parse(b.date) || 0) - (Date.parse(a.date) || 0));
  return items;
}

function retainedItems(items) {
  const now = Date.now();
  const hours = state.timeWindow > 0 ? state.timeWindow : 24 * 30;
  const cutoff = now - hours * 3600 * 1000;
  return uniqueEvents(items).filter(item => {
    const timestamp = Date.parse(item.date);
    return Number.isFinite(timestamp) && timestamp >= cutoff && timestamp <= now + 5 * 60000;
  }).slice(0, 500);
}

function persistFeed() {
  const kept = retainedItems(state.items);
  writeLocal('mizan.feed-cache', {date: Date.now(), items: kept.map(item => item.raw)});
}

function feedURL(offset=0) {
  const filterParam=['multi','single'].includes(state.tab)?`&filter=${state.tab}`:'';
  const windowParam=`&window_hours=${Math.max(0, Number(state.timeWindow)||0)}`;
  return `/api/v2/feed?limit=30&offset=${offset}&sort=${state.tab==='latest'?'recent':'personalized'}${filterParam}${windowParam}`;
}

function renderFeed() {
  if (state.route !== 'feed') return;
  loadObserver?.disconnect();
  const items = filteredItems();
  const topics = [...new Set(state.items.map(a => a.topic))].slice(0, 8);
  if (state.topic !== 'all' && !topics.includes(state.topic)) topics.unshift(state.topic);

  // Dynamic country counts across currently retained items
  const countryCounts = new Map();
  for (const it of state.items) {
    for (const c of (it.countries || [])) {
      const prev = countryCounts.get(c.name) || { name: c.name, flag: c.flag, count: 0 };
      prev.count++;
      countryCounts.set(c.name, prev);
    }
  }
  if (!countryCounts.has('France')) {
    countryCounts.set('France', { name: 'France', flag: '🇫🇷', count: 0 });
  }
  const sortedCountries = [...countryCounts.values()].sort((a, b) => {
    if (a.name === 'France') return -1;
    if (b.name === 'France') return 1;
    return b.count - a.count;
  });

  $('#page-content').innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
      <div class="tabs" aria-label="${esc(t('nav_feed'))}" style="margin-bottom:0;">
        ${[['for-you', t('tab_for_you')], ['latest', t('tab_latest')], ['multi', t('tab_multi')], ['single', t('tab_single')]].map(([tVal, label]) =>
          `<button class="tab ${state.tab === tVal ? 'active' : ''}" data-action="tab" data-value="${tVal}" aria-pressed="${state.tab === tVal}">${label}</button>`
        ).join('')}
      </div>
    </div>
    <div class="country-row" role="region" aria-label="Filtres par pays">
      <button class="chip country-chip ${state.country === 'all' ? 'active' : ''}" data-action="country" data-value="all">
        <span class="country-flag">🌍</span> <span>${esc(t('tab_all_countries') || 'Tous les pays')}</span>
      </button>
      ${sortedCountries.map(c => `
        <button class="chip country-chip ${state.country === c.name ? 'active' : ''}" data-action="country" data-value="${esc(c.name)}">
          <span class="country-flag">${c.flag}</span> <span>${esc(c.name)}</span>${c.count > 0 ? `<span class="count-badge">${c.count}</span>` : ''}
        </button>
      `).join('')}
    </div>
    <div class="topic-row">
      <button class="chip ${state.topic === 'all' ? 'active' : ''}" data-action="topic" data-value="all">${t('tab_all')}</button>
      ${topics.map(tVal => `<button class="chip ${state.topic === tVal ? 'active' : ''}" data-action="topic" data-value="${esc(tVal)}">${esc(tVal)}</button>`).join('')}
    </div>
    ${state.error ? `<div class="notice error" role="alert">${esc(state.error)} <button data-action="refresh">${t('refresh')}</button></div>` : ''}
    ${state.query ? `<div class="notice">${t('search_results_for')} « ${esc(state.query)} » <button class="icon-button" data-action="clear-search" aria-label="${esc(t('search_clear'))}">${icon('close')}</button></div>` : ''}
    ${items.length ? (
      `<div class="feed-list">${items.map(storyCard).join('')}</div>${state.hasMore && !state.query ? `<div class="load-more"><button class="button secondary" data-action="load-more">${t('load_more')}</button></div>` : items.length ? `<p class="feed-end">${t('feed_end')}</p>` : ''}`
    ) : state.loading ? loading(t('feed_loading')) : empty(
      state.query || state.topic !== 'all' || state.country !== 'all' ? t('empty_filter_title') : t('empty_feed_title'),
      state.query || state.topic !== 'all' || state.country !== 'all' ? t('empty_filter_desc') : t('empty_feed_desc'),
      state.query || state.topic !== 'all' || state.country !== 'all' ? 'clear-search' : 'scan',
      state.query || state.topic !== 'all' || state.country !== 'all' ? t('reset_filter') : t('scan_sources')
    )}
    ${!items.length&&state.hasMore&&!state.query?`<div class="load-more"><button class="button secondary" data-action="load-more">${t('load_more_search')}</button></div>`:''}
  `;

  if (loadObserver) {
    loadObserver.disconnect();
    loadObserver = null;
  }

  if (state.hasMore && items.length && 'IntersectionObserver' in window) {
    const more = $('.load-more');
    if (more) {
      loadObserver = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting && !state.loading) loadFeed(true);
      }, {rootMargin: '200px'});
      loadObserver.observe(more);
    }
  }
}

function appendFeed(newItems) {
  if (!newItems || !newItems.length) return;
  const matching = new Set(filteredItems().map(x=>x.id));
  const filtered = newItems.filter(x => matching.has(x.id));
  if (!filtered.length) return;

  const list = $('.feed-list');
  const more = $('.load-more');
  if (list) {
    const currentCount = list.querySelectorAll('.story').length;
    const newHtml = filtered.map((it, idx) => storyCard(it, currentCount + idx)).join('');
    list.insertAdjacentHTML('beforeend', newHtml);
    if (!state.hasMore && more) {
      more.innerHTML = '<p class="feed-end">Vous avez parcouru les informations disponibles.</p>';
      more.classList.remove('load-more');
      loadObserver?.disconnect();
    }
  }
}

async function loadFeed(append=false, isExplicit=false) {
  if(append&&(state.loading||state.query))return;
  feedController?.abort();feedController=new AbortController();
  const controller=feedController,generation=++state.generation;
  state.loading=true;
  let appended=[];
  try {
    let data,legacy=false;
    data=await api(feedURL(append?state.offset:0),{signal:controller.signal,timeout:90000});
    if(generation!==state.generation||isPageUnloading)return;
    let items=(data.items||[]).map(normalizeEvent);
    if(generation!==state.generation||isPageUnloading)return;
    state.mode=legacy?'legacy':'v2';state.hasMore=Boolean(data.has_more);state.offset=data.next_offset??((append?state.offset:0)+items.length);
    const existing=new Set(state.items.map(x=>x.id));
    state.items=retainedItems(append?[...state.items,...items]:[...items,...state.items]);
    appended=filteredItems().filter(x=>!existing.has(x.id));
    state.error='';persistFeed();
  } catch(e) {
    if(generation!==state.generation||controller.signal.aborted||isPageUnloading)return;
    if(!append&&!state.items.length){const cache=readLocal('mizan.feed-cache',null);if(Array.isArray(cache?.items))state.items=cache.items.filter(x=>x?.editorial_version===CURRENT_EDITORIAL_VERSION).map(normalizeEvent);}
    if(!state.items.length||isExplicit){
      state.error=state.items.length?'Connexion interrompue. Les news conservées sur cet appareil restent lisibles.':`Les news sont indisponibles. ${e.message}`;
    }
    if(!navigator.onLine){
      setConnection('Hors connexion');
    }
  } finally {
    if(generation===state.generation&&!isPageUnloading){state.loading=false;if(append&&appended.length&&!state.error){appendFeed(appended);if(!state.hasMore){loadObserver?.disconnect();document.querySelectorAll('.load-more').forEach(el=>el.innerHTML='<p class="feed-end">Vous avez parcouru les informations disponibles.</p>');}}else renderFeed();renderRail();}
  }
}

async function refresh() {
  if (state.route === 'atlas') { await route(); return; }
  state.query = '';
  state.topic = 'all';
  state.country = 'all';
  $('#search-input').value = '';
  await loadFeed(false, true);
  if (state.route === 'library') await renderLibrary();
  toast(state.error ? 'Le serveur est momentanément indisponible.' : 'Fil actualisé.');
}

function showSheet(label, title, body) {
  detailGeneration++;
  $('#sheet-label').textContent = label;
  $('#sheet-content').innerHTML = `<h2 id="sheet-title" class="sheet-title">${esc(title)}</h2>${body}`;
  if (!$('#sheet').open) $('#sheet').showModal();
  $('#sheet').scrollTop = 0;
}

function getItem(id) {
  return state.items.find(a => a.id === id) || state.saved.find(a => a.id === id) || state.legacySaved.find(a => a.id === id) || detailItems.get(id);
}

function sourcesMarkup(sources) {
  if (!sources || !sources.length) return '';
  return `<div class="detail-sources-horizontal">` + sources.map(s => {
    let url = safeURL(s.url || s.source_url || s.canonical_url || s.homepage_url);
    let name = s.name || s.canonical_name || s.domain || s.canonical_domain || 'Source';
    if (name.toLowerCase().startsWith('rss_')) name = name.slice(4).replace(/_/g, ' ').trim();
    name = name.replace(/^\*+|\*+$/g, '').trim();
    const domain = s.domain || s.canonical_domain || (url ? new URL(url).hostname : '');
    const cleanDomain = domain.replace(/^www\./, '');
    const fav = s.favicon || s.favicon_url || faviconForDomain(cleanDomain);
    const favIconMarkup = fav
      ? `<img class="detail-source-chip-logo" src="${esc(fav)}" alt="" loading="lazy"/>`
      : `<span class="detail-source-chip-fallback">${esc(name.slice(0, 2).toUpperCase())}</span>`;

    if (url) {
      return `
        <a class="detail-source-chip" href="${esc(url)}" target="_blank" rel="noopener noreferrer" title="${esc(name)}">
          ${favIconMarkup}
          <span class="detail-source-chip-name">${esc(name)}</span>
          <svg class="detail-source-chip-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17l9.2-9.2M17 17V8H8"/></svg>
        </a>
      `;
    }
    return `
      <div class="detail-source-chip inactive" title="${esc(name)}">
        ${favIconMarkup}
        <span class="detail-source-chip-name">${esc(name)}</span>
      </div>
    `;
  }).join('') + `</div>`;
}

async function openDetail(item) {
  if (!item) return;
  const count = sourceCount(item);
  const source = item.sources[0];
  const domain = (source?.domain || source?.name || 'source').toLowerCase().replace(/^www\./, '');
  const favicon = item.primaryFavicon || (source?.domain ? faviconForDomain(source.domain) : '');
  const avatarMarkup = favicon
    ? `<img class="article-avatar" src="${esc(favicon)}" alt="" loading="lazy"/>`
    : `<span class="article-avatar-fallback" aria-hidden="true">${esc((source?.name || 'M').slice(0, 2).toUpperCase())}</span>`;

  showSheet(item.topic, item.title, `
    <article class="twitter-article">
      ${count > 1 ? `
        <div class="twitter-article-multi-header">
          <div class="twitter-article-sources-track">
            ${item.sources.map(s => {
              const d = (s.domain || '').toLowerCase().replace(/^www\./, '');
              const fav = s.favicon || (d ? faviconForDomain(d) : '');
              const name = esc(s.name || d || 'Source');
              const av = fav
                ? `<img class="source-chip-logo" src="${esc(fav)}" alt="" loading="lazy"/>`
                : `<span class="source-chip-fallback">${esc(name.slice(0, 2).toUpperCase())}</span>`;
              return `<span class="source-chip">${av}<span class="source-chip-name">${name}</span></span>`;
            }).join('')}
          </div>
          <div class="twitter-article-meta">
            <time datetime="${esc(item.date)}">${esc(formatEventTime(item))}</time>
            <span>·</span>
            <span class="tweet-multi-pill">${icon('layers')} <span data-detail-source-count>${count}</span> ${t('sources_count')}</span>
            ${item.isVo ? `<span class="badge-vo" title="${esc(t('badge_vo_title'))}">${t('badge_vo')}</span>` : ''}
          </div>
        </div>
      ` : `
        <div class="twitter-article-byline">
          ${avatarMarkup}
          <div class="twitter-article-author-info">
            <div class="twitter-article-author-name">
              <strong>${esc(source?.name || 'Actualité')}</strong>
            </div>
            <div class="twitter-article-meta">
              <time datetime="${esc(item.date)}">${esc(formatEventTime(item))}</time>
              ${item.isVo ? `<span class="badge-vo" title="${esc(t('badge_vo_title'))}">${t('badge_vo')}</span>` : ''}
            </div>
          </div>
        </div>
      `}

      ${item.image ? `<img class="twitter-article-hero" src="${esc(item.image)}" alt="" referrerpolicy="no-referrer">` : ''}

      <div id="detail-narrative" class="twitter-article-body">
        ${item.v2 ? loading(t('detail_ai_synthesizing')) : ''}
      </div>

      <div class="twitter-article-sources">
        <h4 class="detail-sources-title">${t('detail_original_sources')} (<span data-detail-source-count>${item.sources.length}</span>)</h4>
        <div id="detail-sources">${sourcesMarkup(item.sources) || `<p class="muted">${t('detail_no_sources')}</p>`}</div>
      </div>

      <div class="twitter-article-footer">
        <button class="button secondary" data-action="save" data-id="${esc(item.id)}">${icon('bookmark')} ${item.saved ? t('detail_remove_saved') : t('detail_save')}</button>
        <button class="button ghost" data-action="share" data-id="${esc(item.id)}">${icon('share')} ${t('detail_share')}</button>
      </div>
    </article>
  `);
  $('#sheet-title').className = 'twitter-article-title';
  const generation = detailGeneration;
  state.read.add(item.id);
  writeLocal('mizan.read', [...state.read].slice(-500));
  interaction(item, 'open').catch(() => {});

  if (!item.v2) {
    const texts = [item.raw.context_explainer, item.raw.detailed_story].filter(Boolean);
    const narrativeHtml = texts.length
      ? texts.map((t, idx) => {
          let html = esc(plain(t)).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
          return `<p class="twitter-paragraph ${idx === 0 ? 'detail-lead-paragraph' : 'detail-body-paragraph'}">${html}</p>`;
        }).join('')
      : `<p class="twitter-paragraph detail-lead-paragraph">${esc(item.title)}. Suivi éditorial et analyse continue.</p>`;
    const container = $('#detail-narrative');
    if (container) container.innerHTML = narrativeHtml;
    return;
  }

  try {
    const detail = await api(`/api/v2/events/${encodeURIComponent(item.id)}`);
    if (generation !== detailGeneration || !$('#sheet').open) return;
    const summary = detail?.summary;
    const rawNarrative = summary?.article_body || summary?.detailed_story || summary?.detail_summary || summary?.long_summary || '';

    let paragraphs = [];
    if (rawNarrative) {
      paragraphs = rawNarrative
        .split(/\n\s*\n/)
        .map(p => p.replace(/^[•\-\*]\s*(\*\*.*?\*\*\s*:\s*)?/, '').trim())
        .map(p => p.replace(/^\*+(?:Politico|rss_[a-zA-Z0-9_]+)\*+\s*:?\s*/i, '').trim())
        .filter(p => p.length > 20 && !p.toLowerCase().startsWith('selon les sources') && !p.toLowerCase().startsWith("confirmation de l'événement"));
    }

    const narrativeHtml = paragraphs.length
      ? paragraphs.map((p, idx) => {
          let html = esc(p);
          html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
          html = html.replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, '<em>$1</em>');
          html = html.replace(/__(.*?)__/g, '<u>$1</u>');
          return `<p class="twitter-paragraph ${idx === 0 ? 'detail-lead-paragraph' : 'detail-body-paragraph'}">${html}</p>`;
        }).join('')
      : `<p class="twitter-paragraph detail-lead-paragraph">${esc(item.title)}. Informations détaillées et recoupements en cours de mise à jour.</p>`;

    const bullets = Array.isArray(summary?.bullet_points) ? summary.bullet_points : (item.bullets || []);
    const evidences = Array.isArray(summary?.evidence) ? summary.evidence : (item.evidence || []);
    const claims = Array.isArray(detail?.claims) ? detail.claims : [];

    let evidenceHtml = '';
    if (claims.length > 0) {
      evidenceHtml = `
        <div class="detail-evidence-box">
          <h4 class="detail-evidence-title">${icon('check')} ${t('detail_verified_facts')} (${claims.length})</h4>
          <div class="detail-evidence-list">
            ${claims.map(c => `
              <div class="evidence-item">
                <p class="evidence-claim"><strong>${t('detail_fact_label')}</strong> ${esc(c.claim_text)}</p>
                ${c.quote_passage ? `<blockquote class="evidence-quote">« ${esc(c.quote_passage)} »</blockquote>` : ''}
                <div class="evidence-meta">
                  <span class="evidence-source">${esc(c.canonical_name || 'Source')}</span>
                  ${c.source_url ? `<a href="${esc(c.source_url)}" target="_blank" rel="noopener noreferrer" class="evidence-link">${t('detail_consult_source')}</a>` : ''}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } else if (evidences.length > 0) {
      evidenceHtml = `
        <div class="detail-evidence-box">
          <h4 class="detail-evidence-title">${icon('check')} ${t('detail_certified_extracts')} (${evidences.length})</h4>
          <div class="detail-evidence-list">
            ${evidences.map((quote, idx) => `
              <div class="evidence-item">
                ${bullets[idx] ? `<p class="evidence-claim"><strong>${t('detail_summary_label')}</strong> ${esc(bullets[idx])}</p>` : ''}
                <blockquote class="evidence-quote">« ${esc(quote)} »</blockquote>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    const container = $('#detail-narrative');
    if (container) container.innerHTML = narrativeHtml + evidenceHtml;
    if (detail?.sources?.length) {
      $('#detail-sources').innerHTML = sourcesMarkup(detail.sources);
      $$('[data-detail-source-count]').forEach(el => { el.textContent = detail.sources.length; });
    }
  } catch (e) {
    if (generation === detailGeneration && $('#detail-narrative')) {
      $('#detail-narrative').innerHTML = `<p class="notice error">${esc(e.message)}</p>`;
    }
  }
}

async function interaction(item, type) {
  if (!item) throw new Error('Ce sujet n’est plus disponible.');
  if (!item.v2 && ['save','unsave'].includes(type)) return {};
  if (item.v2) {
    return post('/api/v2/interactions', {
      event_id: item.id,
      interaction_type: type,
      client_event_id: crypto.randomUUID(),
      surface: 'web',
      signal_kind: ['save', 'unsave', 'like', 'reject'].includes(type) ? 'explicit' : 'implicit'
    });
  }
  const actions = {open: 'read', like: 'interested', reject: 'rejected', share: 'shared'};
  return post('/api/feedback', {
    username: state.profile.username,
    cluster_id: item.cluster_id || item.id,
    alert_title: item.title,
    action: actions[type] || 'read'
  });
}

async function saveItem(item) {
  if (!item) return;
  const saved = item.saved || state.legacySaved.some(x => x.id === item.id);
  await interaction(item, saved ? 'unsave' : 'save');
  for (const entry of [...state.items, ...state.saved, ...detailItems.values()]) if (entry.id === item.id) entry.saved = !saved;
  item.saved = !saved;
  if (!item.v2) {
    state.legacySaved = state.legacySaved.filter(x => x.id !== item.id);
    if (!saved) state.legacySaved.push({...item, saved:true});
    writeLocal('mizan.legacy-saved',state.legacySaved);
  }
  $$('[data-action="save"]').forEach(button => {
    if (button.dataset.id !== item.id) return;
    button.classList.toggle('saved',!saved);button.classList.toggle('selected',!saved);
    button.setAttribute('aria-pressed',String(!saved));
    button.setAttribute('aria-label',saved?'Enregistrer le sujet':'Retirer de la bibliothèque');
    if (button.closest('#sheet')) button.innerHTML = `${icon('bookmark')} ${saved?'Garder pour plus tard':'Retirer de la bibliothèque'}`;
    else if (button.querySelector('span')) button.querySelector('span').textContent = saved?'Enregistrer':'Enregistré';
  });
  toast(saved?'Retiré de la bibliothèque.':item.v2?'Enregistré dans votre bibliothèque.':'Enregistré sur cet appareil.');
  if (state.route === 'library') await renderLibrary();
}

async function shareItem(item) {
  const url = item?.sources.map(s => safeURL(s.url)).find(Boolean);
  if (!url) { toast('Aucun lien d’origine disponible à partager.'); return; }
  try {
    if (navigator.share) await navigator.share({title: item.title, url});
    else {
      await navigator.clipboard.writeText(url);
      toast('Lien de la source copié.');
    }
    interaction(item, 'share').catch(() => {});
  } catch (e) {
    if (e.name !== 'AbortError') toast('Le partage est indisponible sur cet appareil.');
  }
}

async function search(query) {
  query = query.trim();
  feedController?.abort();state.generation++;state.loading=false;
  state.query = query;
  state.topic = 'all';
  if (!query) { await loadFeed(); return; }
  const generation = ++searchGeneration;
  if (state.route !== 'feed') { location.hash = 'feed'; await new Promise(r => setTimeout(r, 0)); }
  $('#page-content').innerHTML = loading('Recherche dans les sujets collectés…');
  try {
    const data = await api(`/api/v2/search?q=${encodeURIComponent(query)}&limit=100`);
    if (generation !== searchGeneration || state.query !== query) return;
    state.items = uniqueEvents((data.items || []).map(normalizeEvent));
    state.hasMore = false;
    state.error = '';
    renderFeed();
  } catch (e) {
    if (generation === searchGeneration && state.query===query) { state.error = e.message; renderFeed(); }
  }
}

async function route() {
  const generation = ++routeGeneration;
  atlasCleanup?.();
  atlasCleanup = null;
  loadObserver?.disconnect();
  const rawHash = location.hash.slice(1);
  const [baseRoute, subRoute] = rawHash.split('/');
  if (!rawHash.startsWith('profile')) profileDraft = null;
  state.route = ['feed', 'atlas', 'library', 'profile'].includes(baseRoute) ? baseRoute : 'feed';
  if (state.route === 'profile') {
    state.profileTab = ['profile', 'appearance', 'sources'].includes(subRoute) ? subRoute : 'profile';
  }
  document.body.classList.toggle('atlas-view', state.route === 'atlas');
  const titles = {
    atlas: ['', 'Globe'],
    library: ['', 'Bibliothèque'],
    profile: {
      profile: ['', 'Profil'],
      appearance: ['', 'Mon espace'],
      sources: ['', 'Sources & connexions']
    }
  };
  const isFeed = state.route === 'feed';
  const heading = $('.page-heading');
  if (heading) heading.style.display = isFeed ? 'none' : 'flex';
  if (!isFeed && titles[state.route]) {
    const titleInfo = state.route === 'profile' ? (titles.profile[state.profileTab || 'profile'] || titles.profile.profile) : titles[state.route];
    const eyebrow = $('.page-heading .eyebrow');
    if (eyebrow) {
      eyebrow.textContent = titleInfo[0] || '';
      eyebrow.style.display = titleInfo[0] ? '' : 'none';
    }
    $('.page-heading h1').innerHTML = `${titleInfo[1]}<span class="blue">.</span>`;
  }
  $('.searchbar').hidden = !isFeed;
  renderNav();
  if (state.route === 'feed') { renderFeed(); if (feedDirty) { feedDirty=false; await loadFeed(); } }
  else if (state.route === 'profile') await renderProfile();
  else if (state.route === 'library') await renderLibrary();
  else {
    $('#page-content').innerHTML = '<div id="atlas-mount" class="atlas-mount"></div>';
    try {
      const {mountAtlas} = await import('./atlas.js');
      if (generation !== routeGeneration) return;
      const clean = await mountAtlas($('#atlas-mount'), {
        onNews: event => {
          const existing = getItem(event.id);
          const item = existing || normalizeEvent({
            ...event,
            alert_id: event.id,
            push_title: event.title,
            bullet_points: event.summary ? [event.summary] : [],
            sources: event.sources?.length ? event.sources : event.source_url ? [{name: event.source_name || 'Source', url: event.source_url}] : []
          });
          detailItems.set(item.id,item);
          openDetail(item);
        }
      });
      if (generation !== routeGeneration) clean?.();
      else atlasCleanup = clean;
    } catch (e) {
      if (generation === routeGeneration) $('#page-content').innerHTML = empty('La carte est indisponible.', 'La carte n’a pas pu démarrer. Réessayez dans quelques instants.', 'refresh', 'Réessayer');
    }
  }
}

// MARK: - PROFILE SUBPAGES & TABS
function profileTabsMarkup() {
  const tab = state.profileTab || 'profile';
  return `
    <nav class="profile-tabs tabs">
      <a class="tab ${tab === 'profile' ? 'active' : ''}" href="#profile">${icon('user')} Profil & Intérêts</a>
      <a class="tab ${tab === 'appearance' ? 'active' : ''}" href="#profile/appearance">${icon('sliders')} Mon espace</a>
      <a class="tab ${tab === 'sources' ? 'active' : ''}" href="#profile/sources">${icon('radio')} Sources & connexions</a>
    </nav>
  `;
}

function renderProfileAppearanceMarkup() {
  const currentTheme = localStorage.getItem('mizan.theme') || 'system';
  const currentPalette = localStorage.getItem('mizan.palette') || 'standard';
  const currentFontStyle = localStorage.getItem('mizan.font-style') || 'modern';
  const currentDensity = document.documentElement.dataset.density || 'comfortable';
  const currentTimeWindow = state.timeWindow;
  const currentLang = state.profile?.preferred_language || localStorage.getItem('mizan.lang') || 'fr';

  return `
    <div class="appearance-section">
      <div class="setting-row">
        <span>Mode d’affichage<small>Suivez les réglages de votre système ou personnalisez le mode.</small></span>
        <div class="segmented">
          <button class="${currentTheme === 'system' ? 'active' : ''}" data-action="set-theme" data-value="system">💻 Système</button>
          <button class="${currentTheme === 'light' ? 'active' : ''}" data-action="set-theme" data-value="light">☀️ Clair</button>
          <button class="${currentTheme === 'dark' ? 'active' : ''}" data-action="set-theme" data-value="dark">🌙 Sombre</button>
        </div>
      </div>
    </div>

    <div class="appearance-section">
      <div class="appearance-header">
        <strong>Palette Visuelle</strong>
        <small>Personnalisez l’atmosphère de lecture avec nos teintes d’encre et de papier noble.</small>
      </div>
      <div class="appearance-palette-grid">
        ${availablePalettes.map(p => `
          <button type="button" class="appearance-palette-card ${currentPalette === p.id ? 'active' : ''}" data-action="set-palette" data-value="${p.id}">
            <div class="palette-swatch-row">
              ${p.swatches.map(color => `<span class="palette-swatch-dot" style="background:${color};"></span>`).join('')}
            </div>
            <strong class="palette-name">${esc(p.name)}</strong>
            <small class="palette-subtitle">${esc(p.subtitle)}</small>
          </button>
        `).join('')}
      </div>
    </div>

    <div class="appearance-section">
      <div class="appearance-header">
        <strong>Style Typographique</strong>
        <small>Sélectionnez la typographie pour les grands titres, résumés et dépêches.</small>
      </div>
      <div class="appearance-font-list">
        ${availableFontStyles.map(f => `
          <button type="button" class="appearance-font-card ${currentFontStyle === f.id ? 'active' : ''}" data-action="set-font" data-value="${f.id}">
            <div class="appearance-font-info">
              <span class="appearance-font-preview" style="font-family:${f.fontFamily};">${esc(f.name)}</span>
              <small class="appearance-font-subtitle">${esc(f.subtitle)}</small>
            </div>
            <span class="appearance-font-sample" style="font-family:${f.fontFamily};">Aa 123</span>
          </button>
        `).join('')}
      </div>
    </div>

    <div class="appearance-section">
      <div class="setting-row">
        <span>Densité du texte<small>Ajuste l’espacement et la taille des cartes d’information.</small></span>
        <div class="segmented">
          <button class="${currentDensity === 'comfortable' ? 'active' : ''}" data-action="set-density" data-value="comfortable">Confortable</button>
          <button class="${currentDensity === 'compact' ? 'active' : ''}" data-action="set-density" data-value="compact">Compact</button>
        </div>
      </div>
    </div>

    <div class="appearance-section">
      <div class="setting-row">
        <span>Fenêtre temporelle<small>Filtre les actualités pour n’afficher que les événements publiés dans cette plage.</small></span>
        <select class="appearance-select" data-action="change-time-window">
          ${availableTimeWindows.map(([val, label]) => `
            <option value="${val}" ${currentTimeWindow === val ? 'selected' : ''}>${esc(label)}</option>
          `).join('')}
        </select>
      </div>
      <div class="setting-row">
        <span>Langue de synthèse<small>Toutes les dépêches internationales seront traduites dans cette langue.</small></span>
        <select class="appearance-select" data-action="change-language">
          ${availableLanguages.map(([code, name]) => `
            <option value="${code}" ${currentLang === code ? 'selected' : ''}>${esc(name)}</option>
          `).join('')}
        </select>
      </div>
    </div>
  `;
}

let sourcesCache = null;
let sourcesCacheTime = 0;
const SOURCES_CACHE_TTL = 300000; // 5 minutes

async function renderProfileSources() {
  const container = $('#profile-sources-container');
  if (!container) return;
  try {
    let catalog = null;
    let health = null;
    if (sourcesCache && (Date.now() - sourcesCacheTime < SOURCES_CACHE_TTL)) {
      catalog = sourcesCache.catalog;
      health = sourcesCache.health;
    } else {
      const results = await Promise.allSettled([api('/api/sources'), api('/api/sources/health')]);
      if (state.route !== 'profile' || state.profileTab !== 'sources' || !$('#profile-sources-container')) return;
      catalog = results[0].status === 'fulfilled' ? results[0].value : null;
      health = results[1].status === 'fulfilled' ? results[1].value : null;
      if (catalog && health) {
        sourcesCache = { catalog, health };
        sourcesCacheTime = Date.now();
      }
    }

    $('#profile-sources-container').innerHTML = `
      <div class="stat-grid">
        <div class="stat-tile"><strong>${esc(catalog?.total_sources_count ?? '—')}</strong><span>Sources cataloguées</span></div>
        <div class="stat-tile"><strong>${esc(health?.ok_count ?? '—')}</strong><span>Dernier relevé réussi</span></div>
        <div class="stat-tile"><strong>${esc(health?.error_count ?? '—')}</strong><span>En erreur</span></div>
      </div>
      <p class="muted">Les relevés décrivent la dernière collecte connue. Un connecteur catalogué ne garantit pas un accès continu.</p>
      
      <div class="panel-actions-card">
        <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;">
          <button class="button secondary" data-action="scan">${icon('refresh')} Relancer la collecte</button>
          <button class="button ghost" data-action="catchup">${icon('clock')} Rattraper les dernières 24 h</button>
          <button class="button ghost" data-action="threshold">${icon('sliders')} Régler les alertes</button>
        </div>
        <button class="button danger-solid" data-action="clear-feed">
          ${icon('trash')} ${esc(t('clear_feed'))}
        </button>
      </div>

      <label class="field">
        Chercher une source
        <input id="source-filter" type="search" placeholder="Nom ou domaine">
      </label>
      <div id="source-results" class="source-directory"></div>
      <section class="detail-section">
        <h3>Autres connecteurs</h3>
        ${(catalog?.streaming_connectors || []).map(c => `
          <div class="source-link">${icon('radio')}<span>${esc(c.name)}<small>${esc(c.category || c.type || 'Connecteur catalogué')}</small></span></div>
        `).join('')}
      </section>
      <div class="form-actions" style="margin-top:28px;border-top:1px solid var(--subtle);padding-top:20px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
          <button class="button secondary" data-action="scan">${icon('refresh')} Relancer la collecte</button>
          <button class="button ghost" data-action="catchup">${icon('clock')} Rattraper les dernières 24 h</button>
          <button class="button ghost" data-action="threshold">${icon('sliders')} Régler les alertes</button>
        </div>
        <button class="button danger-solid" data-action="clear-feed">${icon('trash')} ${esc(t('clear_feed'))}</button>
      </div>
    `;

    const observations = new Map((health?.sources || []).map(x => [x.feed_url, x]));
    const render = () => {
      const q = ($('#source-filter')?.value || '').toLowerCase();
      const items = (catalog?.rss_sources || health?.sources || []).filter(x => `${x.name} ${x.url || x.feed_url}`.toLowerCase().includes(q));
      const resEl = $('#source-results');
      if (!resEl) return;
      resEl.innerHTML = items.slice(0, 80).map(s => {
        const report = observations.get(s.url || s.feed_url), url = safeURL(s.url || s.feed_url);
        return `<div class="source-link">${icon('radio')}<span>${esc(s.name)}<small>${esc(report?.last_status === 'ok' ? 'Dernière collecte réussie' : report?.last_status === 'error' ? 'Dernière collecte en erreur' : 'Non mesuré')}${report?.last_seen_at ? ' · ' + esc(relativeTime(report.last_seen_at)) : ''}</small></span>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Ouvrir la source ${esc(s.name)}">${icon('external')}</a>` : ''}</div>`;
      }).join('') || '<p class="muted">Aucune source trouvée.</p>';
      if (items.length > 80) resEl.insertAdjacentHTML('beforeend', `<p class="muted">80 résultats sur ${items.length}. Précisez votre recherche.</p>`);
    };
    $('#source-filter')?.addEventListener('input', render);
    render();
  } catch (err) {
    if ($('#profile-sources-container')) {
      $('#profile-sources-container').innerHTML = `<p class="notice error">${esc(err.message)}</p>`;
    }
  }
}

// MARK: - COMPLETE PROFILE VIEW
async function renderProfile() {
  const tab = state.profileTab || 'profile';

  if (tab === 'appearance') {
    $('#page-content').innerHTML = `
      <div class="panel">
        ${profileTabsMarkup()}
        ${renderProfileAppearanceMarkup()}
      </div>
    `;
    return;
  }

  if (tab === 'sources') {
    const hasCache = sourcesCache && (Date.now() - sourcesCacheTime < SOURCES_CACHE_TTL);
    $('#page-content').innerHTML = `
      <div class="panel">
        ${profileTabsMarkup()}
        <div id="profile-sources-container">
          ${hasCache ? '' : loading('Lecture de l’état des sources…')}
        </div>
      </div>
    `;
    await renderProfileSources();
    return;
  }

  const p = profileDraft ||= structuredClone(state.profile);
  const interestsList = Object.entries(p.interests || {});
  const watchlist = p.entity_watchlist || [];
  const rules = p.rejection_rules || [];

  $('#page-content').innerHTML = `
    <div class="panel">
      ${profileTabsMarkup()}
      <div class="profile-identity">
        <span class="avatar">${esc((p.display_name || 'U').slice(0, 1).toUpperCase())}</span>
        <div>
          <h2>${esc(p.display_name || 'Mon Profil')}</h2>
        </div>
      </div>

      <form id="profile-form">
        <label class="field">
          Nom d’affichage
          <input type="text" id="profile-name" value="${esc(p.display_name || '')}" placeholder="Votre prénom ou pseudo" required>
        </label>

        <label class="field">
          Ce qui vous intéresse
          <textarea id="profile-bio" placeholder="Ex: Journaliste tech, passionné d’IA, d’astronomie et de géopolitique...">${esc(p.bio_markdown || '')}</textarea>
          <small>Vos sujets, votre contexte et ce que vous souhaitez apprendre orientent les recommandations.</small>
        </label>

        <div class="field-row">
          <label class="field">
            Langue des synthèses
            <select id="profile-lang">
              ${availableLanguages.map(([code, name]) => `
                <option value="${code}" ${p.preferred_language === code ? 'selected' : ''}>${esc(name)}</option>
              `).join('')}
            </select>
          </label>
        </div>

        <section style="margin:25px 0;">
          <h3>Vos centres d’intérêt</h3>
          <div class="rail-chips" id="interests-container" style="margin-bottom:12px;">
            ${interestsList.map(([topic]) => `
              <span class="chip" data-topic="${esc(topic)}">
                ${esc(topic)}
                <button type="button" data-action="remove-interest" data-topic="${esc(topic)}" style="padding:0;margin-left:4px;">${icon('close')}</button>
              </span>
            `).join('')}
          </div>
          <div class="inline-form">
            <input type="text" id="new-interest-topic" placeholder="Nouveau sujet (ex: Intelligence Artificielle, Espace)">
            <button type="button" class="button secondary" data-action="add-interest">${icon('plus')} Ajouter</button>
          </div>
        </section>

        <section style="margin:25px 0;">
          <h3>Personnes et organisations à suivre</h3>
          <div class="rail-chips" id="watchlist-container" style="margin-bottom:12px;">
            ${watchlist.map(w => `<span class="chip">${esc(w)} <button type="button" data-action="remove-watch" data-entity="${esc(w)}" style="padding:0;margin-left:4px;">${icon('close')}</button></span>`).join('')}
          </div>
          <div class="inline-form">
            <input type="text" id="new-entity-input" placeholder="Entité à surveiller (ex: OpenAI, TSMC, Emmanuel Macron)">
            <button type="button" class="button secondary" data-action="add-entity">${icon('plus')} Suivre</button>
          </div>
        </section>

        <section style="margin:25px 0;">
          <h3>Ce que vous préférez éviter</h3>
          <div class="rail-chips" id="rejections-container" style="margin-bottom:12px;">
            ${rules.map(r => `<span class="chip" style="background:var(--subtle);color:var(--danger);">${esc(r)} <button type="button" data-action="remove-rule" data-rule="${esc(r)}" style="padding:0;margin-left:4px;">${icon('close')}</button></span>`).join('')}
          </div>
          <div class="inline-form">
            <input type="text" id="new-rule-input" placeholder="Terme ou sujet à masquer (ex: faits divers, téléréalité)">
            <button type="button" class="button secondary" data-action="add-rule">${icon('plus')} Masquer</button>
          </div>
        </section>

        <div class="form-actions">
          <button type="submit" class="button">${icon('check')} Enregistrer les modifications</button>
        </div>
      </form>
    </div>
  `;

  $('#profile-form').onsubmit = async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const currentInterests = profileDraft.interests || state.profile?.interests || {};
      const interests = {};
      $$('#interests-container [data-topic]').forEach(el => {
        const topic = el.dataset.topic;
        interests[topic] = currentInterests[topic] || 0.85;
      });
      const updated = {
        ...profileDraft,
        display_name: $('#profile-name').value.trim(),
        bio_markdown: $('#profile-bio').value.trim(),
        preferred_language: $('#profile-lang').value,
        min_score_threshold: profileDraft.min_score_threshold || state.profile?.min_score_threshold || 0.65,
        interests,
        entity_watchlist: profileDraft.entity_watchlist || [],
        rejection_rules: profileDraft.rejection_rules || []
      };
      await post('/api/profile', updated);
      state.profile = updated;
      profileDraft = structuredClone(updated);
      feedDirty = true;
      applyLanguage(updated.preferred_language);
      toast(t('profile_saved_toast'));
    } catch (err) {
      toast('Erreur: ' + err.message);
    } finally {
      btn.disabled = false;
    }
  };
}

async function renderLibrary() {
  const generation=++libraryGeneration, tab=state.libraryTab;
  const tabs=`<div class="tabs">${[['saved','Enregistrés'],['videos','Vidéos'],['releases','Sorties']].map(([key,label])=>`<button class="tab ${key===tab?'active':''}" data-action="library-tab" data-value="${key}" aria-pressed="${key===tab}">${label}</button>`).join('')}<button class="tab" data-action="subscriptions">${icon('plus')} Mes suivis</button></div>`;
  $('#page-content').innerHTML=tabs+'<div id="library-content">'+loading('Ouverture de votre bibliothèque…')+'</div>';
  try {
    let html;
    if (tab==='saved') {
      const data=await api('/api/v2/saved?limit=100');
      state.saved=uniqueEvents([...(data.items||[]).map(x=>normalizeEvent({...x,saved:true})),...state.legacySaved]);
      html=state.saved.length?`<div class="feed-list">${state.saved.map(storyCard).join('')}</div>`:empty('Gardez ce qui vous intéresse.','Les sujets enregistrés dans les news vous attendront ici.');
    } else {
      if (!contentCache || Date.now()-contentCache.fetched>180000) contentCache={...await api('/api/content/feed',{timeout:90000}),fetched:Date.now()};
      const items=contentCache[tab]||[];
      html=items.length?items.map(c=>{const url=safeURL(c.url||c.source_url),image=safeURL(c.thumbnail_url||c.artwork_url);return `<article class="content-card">${image?`<img src="${esc(image)}" alt="" loading="lazy" referrerpolicy="no-referrer">`:''}<div class="content-meta">${icon(tab==='videos'?'play':'code')} ${esc(c.channel_name||c.product_name||c.category||'Sortie')} · ${esc(relativeTime(c.published_at))}</div><h2>${esc(c.title)}</h2>${c.summary_ai?`<p>${esc(plain(c.summary_ai))}</p>`:''}${url?`<a class="button secondary" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${tab==='videos'?'Regarder la vidéo':'Voir la sortie'} ${icon('external')}</a>`:''}</article>`}).join(''):empty(tab==='videos'?'Vos prochaines découvertes.':'Aucune sortie pour le moment.','Ajoutez les chaînes, logiciels et applications que vous souhaitez suivre.','subscriptions','Choisir mes suivis');
    }
    if(generation===libraryGeneration&&state.route==='library')$('#library-content').innerHTML=html;
  } catch(e) {if(generation===libraryGeneration&&state.route==='library')$('#library-content').innerHTML=empty('La bibliothèque est indisponible.',e.message,'retry-library','Réessayer');}
}

async function openSubscriptions() {
  showSheet('VOTRE BIBLIOTHÈQUE','Mes suivis',loading('Ouverture des abonnements…'));
  const generation=detailGeneration;
  const data=await api('/api/content/watchlist');
  if(generation!==detailGeneration||!$('#sheet').open)return;
  const groups=[['youtube','Chaînes YouTube',data.youtube_channels||[]],['github','Dépôts GitHub',data.github_repos||[]],['app','Applications',data.tracked_apps||[]],['twitter','Comptes X',data.twitter_accounts||[]]];
  showSheet('VOTRE BIBLIOTHÈQUE','Mes suivis',`<form id="track-form"><label class="field">Type de contenu<select name="type"><option value="youtube">Chaîne YouTube</option><option value="github">Dépôt GitHub</option><option value="app">Application</option><option value="twitter">Compte X</option></select></label><label class="field">Adresse ou identifiant<input name="target" required maxlength="300" placeholder="@chaine, organisation/depot, nom de l’application"><small>La disponibilité dépend des sources et des accès configurés sur votre serveur.</small></label><button class="button" type="submit">${icon('plus')} Ajouter à mes suivis</button></form>${groups.map(([type,label,items])=>`<section class="detail-section"><h3>${label} · ${items.length}</h3>${items.map(item=>{const target=typeof item==='string'?item:type==='youtube'?item.id:item.handle;return `<div class="watch-item"><span>${esc(typeof item==='string'?item:item.name||item.handle||item.id)}</span><button class="icon-button" data-action="untrack" data-type="${type}" data-target="${esc(target)}" aria-label="Ne plus suivre ${esc(typeof item==='string'?item:item.name||item.handle||item.id)}">${icon('minus')}</button></div>`}).join('')||'<p class="muted">Aucun suivi.</p>'}</section>`).join('')}`);
  $('#track-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('button[type=submit]');button.disabled=true;try{const fields=new FormData(form);await post('/api/content/track',{type:fields.get('type'),target:fields.get('target').trim()});contentCache=null;toast('Suivi ajouté.');await openSubscriptions();}catch(err){toast(err.message);}finally{if(button.isConnected)button.disabled=false;}};
}

// MARK: - MODALS FOR SOURCES & APPEARANCE

async function openSourcesModal() {
  location.hash = 'profile/sources';
}

async function openThreshold() {
  const h=await api('/api/health'),c=h.criticality_settings||{};
  showSheet('ALERTES','Votre seuil de suivi',`<form id="threshold-form"><label class="field">Nombre minimum de sources<input name="min_sources" type="number" min="1" max="50" required value="${Number(c.min_sources)||3}"></label><label class="field">Fenêtre de couverture (minutes)<input name="window_minutes" type="number" min="1" max="1440" required value="${Number(c.window_minutes)||20}"></label><p class="muted">Une couverture multisource n’est pas une certification des faits.</p><button class="button" type="submit">Enregistrer</button></form>`);
  $('#threshold-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('button');button.disabled=true;try{const fields=new FormData(form);await post('/api/settings/criticality',{min_sources:Number(fields.get('min_sources')),window_minutes:Number(fields.get('window_minutes'))});toast('Seuil enregistré.');$('#sheet').close();}catch(err){toast(err.message)}finally{button.disabled=false}};
}

function openAppearanceModal() {
  location.hash = 'profile/appearance';
}

function captureProfileDraft() {
  if (!$('#profile-form')) return;
  const currentInterests = profileDraft?.interests || state.profile?.interests || {};
  const activeTopics = new Set([...$$('#interests-container [data-topic]')].map(el => el.dataset.topic));
  const newInterests = {};
  for (const topic of activeTopics) {
    newInterests[topic] = currentInterests[topic] || 0.85;
  }
  profileDraft = {
    ...(profileDraft || state.profile),
    display_name: $('#profile-name')?.value || '',
    bio_markdown: $('#profile-bio')?.value || '',
    preferred_language: $('#profile-lang')?.value || 'fr',
    min_score_threshold: profileDraft?.min_score_threshold || state.profile?.min_score_threshold || 0.65,
    interests: newInterests
  };
}
async function secondaryAction(actionName, btn) {
  if (actionName==='library-tab') {state.libraryTab=btn.dataset.value;await renderLibrary();return;}
  if (actionName==='retry-library') return renderLibrary();
  if (actionName==='subscriptions') return openSubscriptions();
  if (actionName==='untrack') {btn.disabled=true;await post('/api/content/untrack',{type:btn.dataset.type,target_id:btn.dataset.target});contentCache=null;toast('Suivi retiré.');await openSubscriptions();return;}
  if (actionName==='catchup') {sourcesCache=null;sourcesCacheTime=0;btn.disabled=true;await post('/api/stream/deep-scan-24h',{});toast('Rattrapage lancé. Les sujets arriveront dans vos news.');return;}
  if (actionName==='clear-feed') {
    if (!confirm(t('clear_feed_confirm') || 'Vider le flux ?')) return;
    sourcesCache = null;
    sourcesCacheTime = 0;
    btn.disabled = true;
    try {
      await post('/api/purge', {});
      state.items = [];
      state.offset = 0;
      state.hasMore = false;
      state.pending = 0;
      state.pendingItems = [];
      feedDirty = true;
      try { localStorage.removeItem('mizan.feed-cache'); } catch {}
      persistFeed();
      toast(t('clear_feed_done') || 'Le flux a été entièrement vidé.');
    } catch (err) {
      toast(err.message || 'Erreur lors de la purge.');
    } finally {
      if (btn.isConnected) btn.disabled = false;
    }
    return;
  }
  if (actionName==='threshold') return openThreshold();
  if (['add-entity','remove-watch','add-rule','remove-rule','add-interest','remove-interest'].includes(actionName)) captureProfileDraft();
  if (actionName === 'sources') { location.hash = 'profile/sources'; return; }
  if (actionName === 'appearance') { location.hash = 'profile/appearance'; return; }
  if (actionName === 'set-font') {
    applyFontStyle(btn.dataset.value);
    setPreference('mizan.font-style', btn.dataset.value);
    if (state.route === 'profile' && state.profileTab === 'appearance') await renderProfile();
    return;
  }
  if (actionName === 'set-palette') {
    applyPalette(btn.dataset.value);
    setPreference('mizan.palette', btn.dataset.value);
    if (state.route === 'profile' && state.profileTab === 'appearance') await renderProfile();
    return;
  }
  if (actionName === 'set-theme') {
    applyTheme(btn.dataset.value);
    setPreference('mizan.theme', btn.dataset.value);
    if (state.route === 'profile' && state.profileTab === 'appearance') await renderProfile();
    return;
  }
  if (actionName === 'set-density') {
    document.documentElement.dataset.density = btn.dataset.value;
    setPreference('mizan.density', btn.dataset.value);
    if (state.route === 'profile' && state.profileTab === 'appearance') await renderProfile();
    return;
  }
  if (actionName === 'remove-interest') {
    const topic = btn.dataset.topic;
    if (profileDraft?.interests) delete profileDraft.interests[topic];
    btn.closest('.chip')?.remove();
    return;
  }
  if (actionName === 'add-interest') {
    const tInput = $('#new-interest-topic');
    const t = tInput.value.trim();
    if (!t) return;
    if (!profileDraft.interests) profileDraft.interests = {};
    if (Object.keys(profileDraft.interests).some(k => k.toLowerCase() === t.toLowerCase())) {
      toast('Ce sujet est déjà dans vos intérêts.');
      return;
    }
    profileDraft.interests[t] = 0.85;
    tInput.value = '';
    renderProfile();
    return;
  }
  if (actionName === 'add-entity') {
    const input = $('#new-entity-input');
    const entity = input.value.trim();
    if (!entity) return;
    profileDraft.entity_watchlist = profileDraft.entity_watchlist || [];
    if (!profileDraft.entity_watchlist.includes(entity)) {
      profileDraft.entity_watchlist.push(entity);
      renderProfile();
    }
    input.value = '';
    return;
  }
  if (actionName === 'remove-watch') {
    const entity = btn.dataset.entity;
    profileDraft.entity_watchlist = (profileDraft.entity_watchlist || []).filter(e => e !== entity);
    renderProfile();
    return;
  }
  if (actionName === 'add-rule') {
    const input = $('#new-rule-input');
    const rule = input.value.trim();
    if (!rule) return;
    profileDraft.rejection_rules = profileDraft.rejection_rules || [];
    if (!profileDraft.rejection_rules.includes(rule)) {
      profileDraft.rejection_rules.push(rule);
      renderProfile();
    }
    input.value = '';
    return;
  }
  if (actionName === 'remove-rule') {
    const rule = btn.dataset.rule;
    profileDraft.rejection_rules = (profileDraft.rejection_rules || []).filter(r => r !== rule);
    renderProfile();
    return;
  }

}

async function action(e) {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const a = btn.dataset.action, id = btn.dataset.id, item = id ? getItem(id) : null;
  try {
    if (a === 'close') { $('#sheet').close(); return; }
    if (a === 'profile') { location.hash = 'profile'; return; }
    if (a === 'refresh') { await refresh(); return; }
    if (a === 'tab') {
      const newTab = btn.dataset.value;
      if (newTab === state.tab) return;
      state.tab = newTab;
      state.offset = 0;
      renderFeed();
      await loadFeed();
      return;
    }
    if (a === 'topic') { state.topic = btn.dataset.value; state.route === 'feed' ? renderFeed() : location.hash = 'feed'; return; }
    if (a === 'country') { state.country = btn.dataset.value; state.route === 'feed' ? renderFeed() : location.hash = 'feed'; return; }
    if (a === 'clear-search') { state.query = ''; state.topic = 'all'; state.country = 'all'; $('#search-input').value = ''; await loadFeed(); return; }
    if (a === 'load-more') { await loadFeed(true); return; }
    if (a === 'detail') { await openDetail(item); return; }
    if (a === 'save') { btn.disabled = true; await saveItem(item); return; }
    if (a === 'share') { await shareItem(item); return; }
    if (a === 'interest') {
      if(state.liked.has(id)){toast('Votre intérêt pour ce sujet est déjà enregistré.');return;}
      btn.disabled=true;await interaction(item,'like');state.liked.add(id);writeLocal('mizan.liked',[...state.liked]);
      $$('[data-action="interest"]').forEach(b=>{if(b.dataset.id!==id)return;b.classList.add('liked');b.setAttribute('aria-pressed','true');});
      toast('Votre intérêt a été pris en compte.');return;
    }
    if (a === 'reject') {
      btn.disabled=true;await interaction(item,'reject');state.hidden.add(id);writeLocal('mizan.hidden',[...state.hidden]);
      renderFeed();toast('Moins de sujets similaires dans vos recommandations.');return;
    }
    if (a === 'new-stories') {
      $('#new-stories').hidden = true;
      state.pending = 0;
      if (state.pendingItems.length) {
        state.items = retainedItems([...state.pendingItems, ...state.items]);
        state.pendingItems = [];
        persistFeed();
        renderFeed();
      } else {
        await loadFeed();
      }
      window.scrollTo({top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
      return;
    }
    if (a === 'scan') {
      sourcesCache = null;
      sourcesCacheTime = 0;
      btn.disabled = true;
      await post('/api/stream/trigger-tick', {});
      toast('Collecte lancée. Les nouveaux sujets apparaîtront dans les news.');
      return;
    }
    await secondaryAction(a, btn);
  } catch (error) {
    toast(error.message || 'L’action n’a pas pu être enregistrée.');
  } finally {
    if (btn.isConnected) btn.disabled = false;
  }
}

document.addEventListener('click', action);
document.addEventListener('change', async event => {
  const target = event.target;
  if (target.dataset.action === 'change-time-window') {
    state.timeWindow = Number(target.value);
    setPreference('mizan.timeWindow', state.timeWindow);
    await loadFeed();
    toast(`Fenêtre temporelle : ${target.options[target.selectedIndex]?.text}`);
  } else if (target.dataset.action === 'change-language') {
    const lang = target.value;
    if (state.profile) {
      state.profile.preferred_language = lang;
      post('/api/profile/default_user', {preferred_language: lang}).catch(()=>{});
    }
    setPreference('mizan.lang', lang);
    applyLanguage(lang);
    toast(t('profile_saved_toast'));
  }
});
document.addEventListener('error', event => {
  if (event.target instanceof HTMLImageElement) event.target.hidden = true;
}, true);

$('#search-form').addEventListener('submit', e => {
  e.preventDefault();
  search($('#search-input').value);
});
$('#search-input').addEventListener('search', () => {
  if (!$('#search-input').value) search('');
});

$('#sheet').addEventListener('close', () => { detailGeneration++; });
$('#sheet').addEventListener('click', e => {
  if (e.target === $('#sheet')) {
    const r = e.target.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) e.target.close();
  }
});

window.addEventListener('hashchange', () => {
  route().catch(e => toast(e.message));
  window.scrollTo(0, 0);
});

window.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    location.hash = 'feed';
    $('#search-input').focus();
    return;
  }
});

function connectStream() {
  const stream = new EventSource('/api/stream/live');
  stream.onopen = () => setConnection('Connecté', true);
  stream.addEventListener('connected', () => setConnection('Connecté', true));
  stream.onerror = () => {
    if (!isPageUnloading && !navigator.onLine) {
      setConnection('Hors connexion');
    } else if (!isPageUnloading) {
      setConnection('Reconnexion…');
    }
  };
  let probeTimer;
  const update = () => {
    clearTimeout(probeTimer);
    probeTimer=setTimeout(async()=>{
      try {
        const data=await api(feedURL(0),{timeout:90000});
        const known=new Set(state.items.map(item=>item.id));
        const fresh=(data.items||[]).map(normalizeEvent).filter(item=>!known.has(item.id));
        if(!fresh.length)return;
        state.pendingItems=uniqueEvents([...fresh,...state.pendingItems]);
        state.pending=state.pendingItems.length;
        $('#new-stories').hidden=false;
        $('#new-stories span:last-child').textContent=state.pending===1?'1 nouvelle news':`${state.pending} nouvelles news`;
      } catch {}
    },750);
  };
  ['alert', 'v2_event_created', 'v2_event_updated'].forEach(type => stream.addEventListener(type, update));
  stream.addEventListener('resync', () => {
    setConnection('Connecté', true);
  });
  window.addEventListener('pagehide', () => stream.close(), {once: true});
}

async function init() {
  hydrateIcons();
  connectStream();
  if (!state.items.length) {
    const cache = readLocal('mizan.feed-cache', null);
    if (Array.isArray(cache?.items) && cache.items.length) {
      state.items = cache.items.filter(x => x?.editorial_version === CURRENT_EDITORIAL_VERSION).map(normalizeEvent);
    }
  }
  $('#edition-date').textContent = new Intl.DateTimeFormat('fr-FR', {weekday: 'long', day: 'numeric', month: 'long'}).format(new Date());
  renderNav();
  renderRail();
  await route();
  const tasks = [
    api('/api/profile/default_user'),
    api('/api/health')
  ];
  if (state.route === 'feed' || !state.items.length) {
    tasks.push(loadFeed());
  }
  const results = await Promise.allSettled(tasks);
  if (results[0].status === 'fulfilled') {state.profile = {...defaultProfile, ...results[0].value};profileDraft=null;}
  if (results[1].status === 'fulfilled') state.health = results[1].value;
  renderNav();
  renderRail();
  if (state.route === 'profile') renderProfile();
}

init().catch(e => {
  setConnection('Indisponible');
  toast(e.message);
});
