"""Analyse en profondeur des sections blanches de la circulaire
pour trouver les cartes produits individuelles."""
import cv2
import numpy as np
import os

IMG_PATH = r'C:\Users\Mark France\aubaines-rapides\cache\tigregeant\circulaire_2026-05-30.png'
OUT_DIR = r'C:\Users\Mark France\aubaines-rapides\cache\tigregeant'

img = cv2.imread(IMG_PATH)
h, w = img.shape[:2]

# Section blanche des produits: y=4322 à y=17288
y_start, y_end = 4322, 17288
products_img = img[y_start:y_end, :]
ph, pw = products_img.shape[:2]
print(f"Section produits: {pw}x{ph}")

# Sauvegarder pour inspection
cv2.imwrite(os.path.join(OUT_DIR, 'section_produits.png'), products_img)

# Analyser les colonnes: la grille a probablement des séparateurs verticaux
# Calculer la luminosité moyenne par colonne
gray = cv2.cvtColor(products_img, cv2.COLOR_BGR2GRAY)
col_brightness = np.mean(gray, axis=0)
# Normaliser
col_norm = (col_brightness - col_brightness.min()) / (col_brightness.max() - col_brightness.min())

# Détecter les colonnes sombres (séparateurs entre cartes)
col_edges = np.abs(np.diff(col_norm))
col_threshold = np.percentile(col_edges, 95)
col_transitions = np.where(col_edges > col_threshold)[0]

print(f"\nAnalyse verticale de la section produits:")
print(f"  Pics de changement par colonne (seuil {col_threshold:.4f}):")
print(f"  Positions: {col_transitions.tolist()}")

# Grouper les transitions verticales proches
v_clusters = []
if len(col_transitions) > 0:
    current = [col_transitions[0]]
    for i in range(1, len(col_transitions)):
        if col_transitions[i] - col_transitions[i-1] < 10:
            current.append(col_transitions[i])
        else:
            v_clusters.append(int(np.median(current)))
            current = [col_transitions[i]]
    v_clusters.append(int(np.median(current)))

print(f"  Colonnes séparatrices: {v_clusters}")

# Analyser les rangées horizontales dans la section produits
# Détecter les lignes horizontales (séparateurs entre rangées)
row_brightness = np.mean(gray, axis=1)
row_norm = (row_brightness - row_brightness.min()) / (row_brightness.max() - row_brightness.min())

# Variance locale pour trouver les zones de transition
variance = np.zeros_like(row_norm)
for i in range(1, len(row_norm)-1):
    variance[i] = abs(row_norm[i+1] - row_norm[i])

var_threshold = np.percentile(variance, 97)
row_transitions = np.where(variance > var_threshold)[0]

print(f"\nAnalyse horizontale de la section produits:")
print(f"  {len(row_transitions)} transitions (seuil {var_threshold:.4f})")
print(f"  Premières 30 positions Y: {row_transitions[:30].tolist()}")

# Grouper en rangées
h_clusters = []
if len(row_transitions) > 0:
    current = [row_transitions[0]]
    for i in range(1, len(row_transitions)):
        if row_transitions[i] - row_transitions[i-1] < 15:
            current.append(row_transitions[i])
        else:
            h_clusters.append(int(np.median(current)))
            current = [row_transitions[i]]
    h_clusters.append(int(np.median(current)))

print(f"  {len(h_clusters)} rangées détectées")
print(f"  Positions Y: {h_clusters}")

# Calculer les distances entre rangées (hauteurs des cartes)
if len(h_clusters) > 2:
    row_heights = np.diff(h_clusters)
    print(f"\n  Hauteurs entre rangées: {row_heights.tolist()}")
    print(f"  Hauteur moyenne: {np.mean(row_heights):.0f}px")

# Diviser la section produits en sous-sections égales et les analyser
# La section fait ~13k px de haut. Voyons la répartition de contenu.
# Échantillonnage vertical
num_samples = 10
sample_height = ph // num_samples
print(f"\nÉchantillons verticaux de la section produits ({num_samples} sections de ~{sample_height}px):")

for i in range(num_samples):
    sy = i * sample_height
    ey = min((i + 1) * sample_height, ph)
    sample = gray[sy:ey, :]
    
    # Couleur moyenne
    avg = np.mean(sample)
    
    # Détection de colonnes dans cette section
    col_sample = np.mean(sample, axis=0)
    col_var = np.var(np.diff(col_sample))
    
    # Nombre de colonnes distinctes (transitions clair-sombre)
    local_edges = np.abs(np.diff(col_sample))
    local_thresh = np.percentile(local_edges, 90)
    local_trans = np.where(local_edges > local_thresh)[0]
    
    print(f"  Section {i}: y={sy+4322}-{ey+4322}, luminosité={avg:.0f}, "
          f"var_col={col_var:.0f}, {len(local_trans)} transitions")

print(f"\n✅ Sections + analyse sauvegardées")
