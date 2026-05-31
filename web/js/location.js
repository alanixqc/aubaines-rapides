/* Aubaines Rapides — Location Selector
   Demande le code postal et filtre les magasins selon la région.
*/

const FSA_CITY = {
  "J7Z": "Saint-Jérôme", "J7Y": "Saint-Jérôme", "J7V": "Saint-Jérôme",
  "J7T": "Saint-Jérôme", "J0R": "Saint-Jérôme", "J8R": "Saint-Jérôme",
  "J8S": "Saint-Jérôme", "J8T": "Saint-Jérôme",
  "H2X": "Montréal", "H2W": "Montréal", "H2T": "Montréal",
  "H2J": "Montréal", "H2L": "Montréal", "H2G": "Montréal",
  "H3A": "Montréal", "H3B": "Montréal", "H3G": "Montréal",
  "H3H": "Montréal", "H3K": "Montréal",
  "H4A": "Montréal", "H4B": "Montréal", "H4C": "Montréal",
  "H1A": "Montréal", "H1B": "Montréal",
  "G1V": "Québec", "G1W": "Québec", "G1X": "Québec",
  "G1K": "Québec", "G1L": "Québec", "G1M": "Québec",
  "G1N": "Québec", "G1P": "Québec",
  "G5T": "Rivière-du-Loup", "G5L": "Rimouski",
  "G6V": "Thetford Mines", "G6W": "Thetford Mines",
};

// Stores coverage zone: which stores are in which area
const STORE_CITIES = new Set([
  "Saint-Jérôme", "Montréal", "Laval", "Mirabel", "Blainville",
  "Terrebonne", "Repentigny", "Saint-Eustache", "Boisbriand",
  "Sainte-Thérèse", "Rosemère", "Prévost", "Saint-Sauveur"
]);

// Store name → known chains (these exist everywhere)
const CHAIN_STORES = new Set([
  "iga", "maxi", "metro", "super c", "provigo", "walmart",
  "costco", "adonis", "tigre géant", "tigre geant",
  "marches tradition", "marche tradition",
]);

const SUPPORTED_FSAS = new Set(["J7Z", "J7Y", "J7V", "J7T", "J0R", "J8R", "J8S", "J8T"]);

let currentLocation = null;

function loadLocation() {
  try {
    const stored = localStorage.getItem('aubaines_location');
    if (stored) {
      currentLocation = JSON.parse(stored);
      return currentLocation;
    }
  } catch(e) {}
  return null;
}

function saveLocation(loc) {
  currentLocation = loc;
  try {
    localStorage.setItem('aubaines_location', JSON.stringify(loc));
  } catch(e) {}
}

function parsePostalCode(input) {
  // Nettoyer: enlever espaces, mettre en maj
  let cp = input.trim().toUpperCase().replace(/\s+/g, '');
  // Format canadien: A#A #A# → A#A#A#
  if (/^[A-Z]\d[A-Z]\d[A-Z]\d$/.test(cp)) {
    return { full: cp, fsa: cp.slice(0, 3) };
  }
  // Juste FSA (3 chars) ou moins
  if (/^[A-Z]\d[A-Z]$/.test(cp.slice(0, 3))) {
    return { full: null, fsa: cp.slice(0, 3) };
  }
  // Code avec espace: A#A #A#
  const spaced = input.trim().toUpperCase();
  if (/^[A-Z]\d[A-Z] ?\d[A-Z]\d$/.test(spaced)) {
    const clean = spaced.replace(/\s/g, '');
    return { full: clean, fsa: clean.slice(0, 3) };
  }
  return null;
}

function getCityFromFSA(fsa) {
  return FSA_CITY[fsa] || null;
}

function isCovered(fsa) {
  return SUPPORTED_FSAS.has(fsa);
}

function isChainStore(storeName) {
  if (!storeName) return false;
  const n = storeName.toLowerCase();
  for (const chain of CHAIN_STORES) {
    if (n.includes(chain)) return true;
  }
  return false;
}

function getStoreCity(storeName) {
  // Simple mapping for known local stores vs chains
  // Chains are everywhere, independents are location-specific
  if (isChainStore(storeName)) return null; // chain = everywhere
  if (storeName && (storeName.includes("L'Inter-Marché") || storeName.includes("Inter-Marché"))) return "Saint-Jérôme";
  if (storeName && storeName.includes("5 Saveurs")) return "Saint-Jérôme";
  if (storeName && storeName.includes("Fruiterie Potager")) return "Saint-Jérôme";
  if (storeName && storeName.includes("Supermarché Aurès")) return "Saint-Jérôme";
  if (storeName && storeName.includes("Mayrand")) return "Laval";
  if (storeName && storeName.includes("Rachelle Béry")) return "Montréal";
  if (storeName && storeName.includes("Marché")) return "Saint-Jérôme"; // generic
  return null;
}

function showLocationModal() {
  const overlay = document.createElement('div');
  overlay.className = 'location-overlay';
  overlay.id = 'locationOverlay';
  overlay.innerHTML = `
    <div class="location-modal">
      <button class="location-close" onclick="closeLocationModal()" aria-label="Fermer">✕</button>
      <h2>📍 Entrez votre code postal</h2>
      <p>Les deals d'épicerie varient selon votre région. Donnez-nous votre code postal pour voir les spéciaux près de chez vous.</p>
      <div class="location-input-group">
        <input type="text" id="postalInput" placeholder="H2X 1Y3" maxlength="7" autocomplete="off">
        <button onclick="submitLocation()">Valider</button>
      </div>
      <div class="location-error" id="locationError"></div>
      <div class="location-suggestions">
        <button onclick="quickLocation('J7Z')">Saint-Jérôme</button>
        <button onclick="quickLocation('H2X')">Montréal</button>
        <button onclick="quickLocation('G1V')">Québec</button>
      </div>
      <button class="location-skip" onclick="closeLocationModal()">Passer ➜</button>
    </div>
  `;
  document.body.appendChild(overlay);

  // Enter key
  document.getElementById('postalInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitLocation();
  });

  // Auto uppercase
  document.getElementById('postalInput').addEventListener('input', (e) => {
    e.target.value = e.target.value.toUpperCase();
  });

  setTimeout(() => document.getElementById('postalInput').focus(), 100);
}

function submitLocation() {
  const input = document.getElementById('postalInput').value;
  const parsed = parsePostalCode(input);
  const errorEl = document.getElementById('locationError');

  if (!parsed || !parsed.fsa) {
    errorEl.textContent = 'Format invalide. Ex: J7Z 1J6';
    errorEl.style.display = 'block';
    return;
  }

  const city = getCityFromFSA(parsed.fsa);
  if (!city) {
    errorEl.textContent = 'Code postal non reconnu. Essaie J7Z (Saint-Jérôme) ou H2X (Montréal).';
    errorEl.style.display = 'block';
    return;
  }

  saveLocation({
    postalCode: parsed.full || parsed.fsa,
    fsa: parsed.fsa,
    city: city,
    covered: isCovered(parsed.fsa),
  });

  closeLocationModal();
  applyLocationToPage();
}

function quickLocation(fsa) {
  const city = getCityFromFSA(fsa);
  if (!city) return;
  saveLocation({
    postalCode: fsa + ' 1A1',
    fsa: fsa,
    city: city,
    covered: isCovered(fsa),
  });
  closeLocationModal();
  applyLocationToPage();
}

function closeLocationModal() {
  const overlay = document.getElementById('locationOverlay');
  if (overlay) overlay.remove();
}

function updateLocationBadge() {
  if (!currentLocation) return;

  const badge = document.getElementById('locationBadge');
  if (!badge) return;

  const icon = currentLocation.covered ? '📍' : '📍';
  badge.innerHTML = `${icon} ${currentLocation.city}`;
  badge.title = currentLocation.postalCode;
  badge.style.display = 'inline-flex';
}

function applyLocationToPage() {
  updateLocationBadge();

  if (!currentLocation) return;

  // If not covered, show message
  if (!currentLocation.covered) {
    const mainContent = document.querySelector('.page') || document.querySelector('.hero-content');
    if (mainContent) {
      // Insert notice after hero/at top of page
      const notice = document.createElement('div');
      notice.className = 'location-unavailable';
      notice.innerHTML = `
        <h3>📍 ${currentLocation.city} — bientôt disponible !</h3>
        <p>On scrappe actuellement les circulaires pour <strong>Saint-Jérôme</strong> et ses environs.</p>
        <p>Ajouter votre région est dans notre TODO — plus on est de monde, plus vite ça arrive !</p>
        <p style="margin-top:16px; font-size:0.8em; color:var(--text-dim);">Code saisi : ${currentLocation.postalCode}</p>
      `;
      if (document.querySelector('.page')) {
        document.querySelector('.page').prepend(notice);
      } else {
        mainContent.after(notice);
      }
    }
  }
}

function initLocation() {
  const stored = loadLocation();
  if (!stored) {
    // Show modal on first visit
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', showLocationModal);
    } else {
      showLocationModal();
    }
    return;
  }

  currentLocation = stored;
  applyLocationToPage();
}

// Expose for inline use
window.submitLocation = submitLocation;
window.quickLocation = quickLocation;
window.currentLocation = () => currentLocation;
window.getLocation = () => currentLocation;

// Auto-init
initLocation();
