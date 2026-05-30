/* Aubaines Rapides — Main JS
   Data loading + shared utilities
*/

const DATA_BASE = 'data/';

let dealsData = null;
let statsData = null;
let trendsData = null;
let productsData = null;

async function loadJSON(url) {
  const res = await fetch(DATA_BASE + url);
  if (!res.ok) throw new Error(`Failed to load ${url}: ${res.status}`);
  return res.json();
}

async function loadAllData() {
  try {
    [dealsData, statsData, productsData] = await Promise.all([
      loadJSON('deals.json'),
      loadJSON('stats.json'),
      loadJSON('products.json'),
    ]);
    return true;
  } catch (e) {
    console.error('Data load error:', e);
    return false;
  }
}

async function loadTrends() {
  if (!trendsData) {
    trendsData = await loadJSON('trends.json');
  }
  return trendsData;
}

const MEAT_EMOJI = {
  boeuf: '🥩', poulet: '🍗', porc: '🥓',
  legume: '🥦', viande: '🥩', poisson: '🐟',
};

const STORE_EMOJI = {
  'iga': '🟢', 'maxi': '🟠', 'super c': '🟡', 'metro': '🔴',
  'provigo': '🟣', 'walmart': '🔵', 'costco': '🔵',
  'tigre géant': '🐯', 'marches tradition': '🟤',
  'inter-marché': '🏪', 'mayrand': '🏪', 'adonis': '🏪',
  'rachelle béry': '🌿', 'm&m': '🧊', 'choix du président': '🏪',
};

function storeEmoji(name) {
  if (!name) return '🏪';
  const n = name.toLowerCase();
  for (const [k, v] of Object.entries(STORE_EMOJI)) {
    if (n.includes(k)) return v;
  }
  return '🏪';
}

function shortName(name, max = 35) {
  if (!name) return '';
  if (name.length <= max) return name;
  return name.slice(0, max - 1) + '…';
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  // 2026-06-03 → 3 juin
  const months = ['janv', 'févr', 'mars', 'avr', 'mai', 'juin',
                  'juil', 'août', 'sept', 'oct', 'nov', 'déc'];
  const [y, m, d] = dateStr.split('-');
  return `${parseInt(d)} ${months[parseInt(m)-1]}`;
}

function createDealCard(deal, rank = null) {
  const div = document.createElement('div');
  div.className = 'deal-card';

  // Rank
  if (rank) {
    const rankEl = document.createElement('div');
    rankEl.className = `deal-rank ${rank <= 3 ? 'top' + rank : ''}`;
    rankEl.textContent = rank <= 3 ? ['🥇','🥈','🥉'][rank-1] : rank;
    div.appendChild(rankEl);
  }

  // Image
  if (deal.image_url) {
    const img = document.createElement('img');
    img.className = 'deal-img';
    img.src = deal.image_url;
    img.alt = deal.name_short || deal.name;
    img.loading = 'lazy';
    div.appendChild(img);
  }

  // Info
  const info = document.createElement('div');
  info.className = 'deal-info';

  const store = document.createElement('div');
  store.className = 'deal-store';
  store.textContent = `${storeEmoji(deal.store)} ${deal.store}`;
  info.appendChild(store);

  const name = document.createElement('div');
  name.className = 'deal-name';
  name.textContent = shortName(deal.name, 40);
  info.appendChild(name);

  const meta = document.createElement('div');
  meta.className = 'deal-meta';
  if (deal.meat_type !== 'autre') {
    const badge = document.createElement('span');
    badge.className = `meat-badge ${deal.meat_type}`;
    badge.textContent = `${MEAT_EMOJI[deal.meat_type] || ''} ${deal.meat_type}`;
    meta.appendChild(badge);
  }
  if (deal.valid_to) {
    meta.append(' · ⏳ ' + formatDate(deal.valid_to));
  }
  if (deal.source === 'reel') {
    meta.append(' ✅');
  }
  info.appendChild(meta);

  div.appendChild(info);

  // Prices
  const prices = document.createElement('div');
  prices.className = 'deal-prices';

  const price = document.createElement('div');
  price.className = 'deal-price';
  price.textContent = deal.price ? `${deal.price.toFixed(2)}$` : '—';
  prices.appendChild(price);

  if (deal.per_kg) {
    const perKg = document.createElement('div');
    perKg.className = 'deal-perkg';
    perKg.textContent = `${deal.per_kg.toFixed(2)}$/kg`;
    prices.appendChild(perKg);
  }

  div.appendChild(prices);

  return div;
}

function renderDeals(container, dealsList, startRank = 1) {
  container.innerHTML = '';
  if (!dealsList || dealsList.length === 0) {
    container.innerHTML = '<div class="loading">Aucun deal trouvé</div>';
    return;
  }
  dealsList.forEach((d, i) => {
    container.appendChild(createDealCard(d, startRank + i));
  });
}

// Search highlighting
function highlightText(text, query) {
  if (!query) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escaped})`, 'gi');
  return text.replace(regex, '<mark>$1</mark>');
}
