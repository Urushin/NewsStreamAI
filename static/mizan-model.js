// Shared normalization keeps source data inert and handles both API generations.
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function safeURL(value) {
  if (!value || typeof value !== 'string') return '';
  try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password ? u.href : ''; } catch { return ''; }
}
export function plain(value) {
  if (Array.isArray(value)) return value.map(plain).filter(Boolean).join('\n');
  if (typeof value !== 'string') return '';
  return value.replace(/\*\*(.*?)\*\*/g, '$1').replace(/^#{1,6}\s/gm, '').trim();
}
export function topicOf(event) {
  if (event.category && !['general','général','actualité'].includes(event.category.toLowerCase())) return event.category;
  const s = `${event.headline || event.canonical_title || event.push_title || ''}`.toLowerCase();
  for (const [topic, pattern] of [['Intelligence artificielle',/\b(llm|openai|chatgpt|anthropic|claude|gemini|ia)\b|artificial intelligence|intelligence artificielle/],['Tech',/\b(apple|google|microsoft|software|logiciel|github|iphone|cyber|linux)\b/],['Science',/\b(nasa|spacex|espace|scientific|scientifique|recherche|research|space)\b/],['Économie',/\b(bourse|inflation|banque|market|économ|crypto|bitcoin|finance|investment|investissement)/],['Monde',/\b(guerre|ukraine|russie|gaza|iran|election|élection|politique|government|war|conflict)/],['Culture',/\b(cinéma|film|manga|anime|musique|culture|série|gaming|nintendo|playstation)\b/],['Planète',/\b(climat|énergie|séisme|earthquake|environment|incendie|ecolog|écolog)/]]) if (pattern.test(s)) return topic;
  return 'À découvrir';
}
export function faviconForDomain(domain) {
  if (!domain) return '';
  const clean = String(domain).toLowerCase().replace(/^www\./, '').split('/')[0];
  return clean ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(clean)}&sz=64` : '';
}

import { t, getLanguage } from './mizan-i18n.js';

export const COUNTRY_DEFINITIONS = [
  {
    id: 'france',
    name: 'France',
    flag: '🇫🇷',
    patterns: [
      /\b(france|français|française|françaises|paris|macron|matignon|élysée|elysee|le pen|barnier|retailleau|bardella|attal|borne|darmanin|mélenchon|melenchon|ciotti|senat|assemblée nationale|cac\s*40|sncf|ratp|marseille|lyon|bordeaux|toulouse|nice|nantes|strasbourg|lille|rennes|grenoble)\b/i
    ]
  },
  {
    id: 'us',
    name: 'États-Unis',
    flag: '🇺🇸',
    patterns: [
      /\b(états-unis|etats-unis|usa|américain|américaine|américains|américaines|washington|trump|biden|fed|federal reserve|wall street|pentagone|white house|maison blanche|californie|new york|senate|congress|fbi|cia|sec|nasdaq|dow jones|floride|texas)\b/i
    ]
  },
  {
    id: 'ukraine',
    name: 'Ukraine',
    flag: '🇺🇦',
    patterns: [/\b(ukraine|ukrainien|ukrainienne|ukrainiens|kyiv|kiev|zelensky|zelenskyy|donbass|odessa|kharkiv|koursk|kursk)\b/i]
  },
  {
    id: 'russie',
    name: 'Russie',
    flag: '🇷🇺',
    patterns: [/\b(russie|russe|russes|moscou|moscow|poutine|putin|kremlin|crémelin|douma)\b/i]
  },
  {
    id: 'uk',
    name: 'Royaume-Uni',
    flag: '🇬🇧',
    patterns: [
      /\b(royaume-uni|britannique|britanniques|londres|london|angleterre|starmer|downing street|king charles|sunak|westminster)\b/i
    ]
  },
  {
    id: 'japon',
    name: 'Japon',
    flag: '🇯🇵',
    patterns: [/\b(japon|japonais|japonaise|tokyo|kyoto|osaka|kishida|ishiba|yen)\b/i]
  },
  {
    id: 'chine',
    name: 'Chine',
    flag: '🇨🇳',
    patterns: [/\b(chine|chinois|chinoise|chinoises|pékin|beijing|shanghai|xi jinping|taiwan|taïwan|yuan)\b/i]
  },
  {
    id: 'allemagne',
    name: 'Allemagne',
    flag: '🇩🇪',
    patterns: [/\b(allemagne|allemand|allemande|allemands|berlin|scholz|bundestag|frankfurt|merz)\b/i]
  },
  {
    id: 'israel_palestine',
    name: 'Proche-Orient',
    flag: '🕊️',
    patterns: [/\b(israël|israel|israélien|israélienne|palestine|palestinien|palestinienne|gaza|tel aviv|jérusalem|jerusalem|netanyahou|netanyahu|cisjordanie|tsahal|hamas)\b/i]
  },
  {
    id: 'liban',
    name: 'Liban',
    flag: '🇱🇧',
    patterns: [/\b(liban|libanais|libanaise|beyrouth|beirut|hezbollah)\b/i]
  },
  {
    id: 'iran',
    name: 'Iran',
    flag: '🇮🇷',
    patterns: [/\b(iran|iranien|iranienne|iraniens|téhéran|tehran|khamenei|pasdaran)\b/i]
  },
  {
    id: 'coree',
    name: 'Corée',
    flag: '🇰🇷',
    patterns: [/\b(corée|coréen|coréenne|séoul|seoul|pyongyang|kim jong un)\b/i]
  },
  {
    id: 'italie',
    name: 'Italie',
    flag: '🇮🇹',
    patterns: [/\b(italie|italien|italienne|rome|milan|meloni)\b/i]
  },
  {
    id: 'espagne',
    name: 'Espagne',
    flag: '🇪🇸',
    patterns: [/\b(espagne|espagnol|espagnole|madrid|barcelone|sanchez)\b/i]
  },
  {
    id: 'canada',
    name: 'Canada',
    flag: '🇨🇦',
    patterns: [/\b(canada|canadien|canadienne|ottawa|montréal|quebec|québec|trudeau|carney)\b/i]
  }
];

export function extractCountries(raw) {
  const text = `${raw.headline || raw.canonical_title || raw.push_title || raw.title || ''} ${raw.short_summary || raw.summary || ''} ${(raw.bullet_points || []).join(' ')}`;
  const found = [];
  const seen = new Set();

  for (const def of COUNTRY_DEFINITIONS) {
    const patternMatch = def.patterns.some(p => p.test(text));
    if (patternMatch) {
      if (!seen.has(def.name)) {
        seen.add(def.name);
        found.push({ name: def.name, flag: def.flag });
      }
    }
  }
  return found;
}

export function normalizeEvent(raw) {
  const sources = (Array.isArray(raw.sources) ? raw.sources : []).map(s => {
    const sourceURL = safeURL(s.url || s.canonical_url || s.source_url);
    const d = s.domain || s.canonical_domain || (sourceURL ? new URL(sourceURL).hostname : '');
    return {
      name: s.name || s.canonical_name || s.domain || s.canonical_domain || 'Source',
      domain: d,
      url: safeURL(s.url || s.canonical_url || s.source_url),
      favicon: faviconForDomain(d)
    };
  });
  const topic = topicOf(raw);
  const countries = extractCountries(raw);
  const primaryDomain = sources[0]?.domain || '';
  const primaryFavicon = faviconForDomain(primaryDomain);
  const image = safeURL(raw.image_url);
  return {
    id: String(raw.event_id || raw.alert_id || raw.cluster_id || raw.id || ''),
    v2: Boolean(raw.event_id),
    cluster_id: raw.cluster_id,
    title: plain(raw.headline || raw.canonical_title || raw.push_title || raw.title) || 'Information sans titre',
    summary: String(raw.short_summary || raw.summary || ''),
    bullets: Array.isArray(raw.bullet_points) ? raw.bullet_points.map(s => String(s || '').trim()).filter(Boolean) : [],
    evidence: Array.isArray(raw.evidence) ? raw.evidence : [],
    detailEvidence: Array.isArray(raw.detail_evidence) ? raw.detail_evidence : [],
    editorialVersion: raw.editorial_version || '',
    sourceCount: Math.max(1, Number(raw.source_count || sources.length || 1)),
    sources,
    image,
    date: raw.published_at || raw.last_source_update_at || raw.first_seen_at || '',
    publishedAt: raw.published_at || '',
    firstSeenAt: raw.first_seen_at || '',
    eventStartedAt: raw.event_started_at || '',
    lastSourceUpdateAt: raw.last_source_update_at || '',
    lastActivityAt: raw.last_activity_at || '',
    topic,
    countries,
    countryNames: countries.map(c => c.name),
    score: Number(raw.final_score ?? raw.hybrid_score ?? raw.relevance_score ?? 0),
    saved: Boolean(raw.saved),
    isVo: Boolean(raw.is_vo),
    language: raw.language || '',
    originalLanguage: raw.original_language || '',
    raw
  };
}
export const sourceCount = item => Math.max(1, Number(item?.source_count || item?.sourceCount || item?.raw?.source_count || (Array.isArray(item?.sources) ? item.sources.length : 1)));
export function uniqueEvents(items) { const seen=new Set();return items.filter(item=>item.id && !seen.has(item.id) && seen.add(item.id)); }
export function relativeTime(value, now = Date.now(), lang = null) {
  const currentLang = lang || getLanguage() || 'fr';
  if (!value) return t('time_recently');
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return t('time_recently');
  const diff = Math.max(0, now - timestamp);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return t('time_just_now');
  if (minutes < 60) return t('time_ago_min', { n: minutes });
  if (minutes < 1440) return t('time_ago_hours', { n: Math.floor(minutes / 60) });
  if (minutes < 10080) return t('time_ago_days', { n: Math.floor(minutes / 1440) });
  const locale = currentLang === 'en' ? 'en-US' : (currentLang === 'es' ? 'es-ES' : (currentLang === 'ar' ? 'ar-SA' : `${currentLang}-${currentLang.toUpperCase()}`));
  try {
    return new Intl.DateTimeFormat(locale, {
      day: 'numeric',
      month: 'short',
      year: new Date(timestamp).getFullYear() !== new Date(now).getFullYear() ? 'numeric' : undefined
    }).format(timestamp);
  } catch (e) {
    return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' }).format(timestamp);
  }
}

export function formatEventTime(item, now = Date.now(), lang = null) {
  const pub = item?.publishedAt;
  if (!pub) return t('time_unknown');
  const lastAct = item?.lastActivityAt;
  let text = relativeTime(pub, now, lang);
  if (lastAct && pub) {
    const pubTs = Date.parse(pub);
    const actTs = Date.parse(lastAct);
    if (Number.isFinite(pubTs) && Number.isFinite(actTs) && actTs - pubTs > 1800000) {
      text += ` · ${t('time_updated')} ${relativeTime(lastAct, now, lang).toLowerCase()}`;
    }
  }
  return text;
}

export function renderMarkdown(text) {
  if (!text) return '';
  let s = esc(String(text).trim());
  // Fix orphan closing ** e.g. "Projet** : " -> "**Projet** : "
  s = s.replace(/^([^*<\n]+?)\*\*\s*:/, '<strong>$1</strong> :');
  // Bold: **text**
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic: *text*
  s = s.replace(/(?<!\*)\*([^*<\n]+?)\*(?!\*)/g, '<em>$1</em>');
  return s;
}

export function getThreeBullets(item) {
  let list = [];
  if (Array.isArray(item.bullets) && item.bullets.length > 0) {
    list = item.bullets;
  } else if (Array.isArray(item.raw?.bullet_points) && item.raw.bullet_points.length > 0) {
    list = item.raw.bullet_points;
  } else if (typeof item.summary === 'string' && item.summary.includes(' • ')) {
    list = item.summary.split(' • ');
  } else if (typeof item.summary === 'string' && item.summary.includes('\n')) {
    list = item.summary.split('\n');
  } else if (typeof item.summary === 'string' && item.summary.trim()) {
    const sents = item.summary.split(/(?<=[.!?])\s+/).map(s => s.trim()).filter(Boolean);
    list = sents.length >= 2 ? sents : [item.summary.trim()];
  }

  let cleaned = list
    .map(s => {
      let str = String(s || '').replace(/^[•\-\s]+/, '').trim();
      str = str.replace(/^\*\*(?:Faits confirmés|Recoupement éditorial|Recoupement editorial|Suivi éditorial|suivi editorial|Couverture source)\*\*\s*:\s*/i, '');
      str = str.replace(/\b(?:Faits confirmés|Recoupement éditorial|Recoupement editorial|Suivi éditorial|suivi editorial|Couverture source)\b\s*:?\s*/i, '');
      return str.trim();
    })
    .filter(s => {
      if (!s || s.length < 5) return false;
      const lower = s.toLowerCase();
      if (lower.startsWith('selon les sources') && s.length < 35) return false;
      if (lower.startsWith("confirmation de l'événement") && s.length < 40) return false;
      if (lower.includes('information rapportée et recoupée par les rédactions') && s.length < 70) return false;
      if (lower.includes('veille active sur') && s.length < 50) return false;
      return true;
    });

  return cleaned.slice(0, 3);
}
