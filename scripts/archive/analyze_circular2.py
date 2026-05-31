"""Analyse la circulaire Tigre Géant — version améliorée.
Détecte les cartes produits par analyse de colonnes + sauts de couleur."""
import cv2
import numpy as np
from collections import Counter
import os

IMG_PATH = r'C:\Users\Mark France\aubaines-rapides\cache\tigregeant\circulaire_2026-05-30.png'
OUT_DIR = r'C:\Users\Mark France\aubaines-rapides\cache\tigregeant'

# Charger l'image
img = cv2.imread(IMG_PATH)
h, w = img.shape[:2]
print(f"Image: {w}x{h}")

# Réduire la résolution pour l'analyse
scale = 0.25
small = cv2.resize(img, (int(w*scale), int(h*scale)))
gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
sh, sw = gray.shape
print(f"Redimensionné: {sw}x{sh}")

# Méthode 1: Analyser l'histogramme horizontal pour trouver les rangées
# Une carte-produit a une couleur de fond différente des espaces entre les rangées
# Calculer la luminosité moyenne par ligne
row_brightness = np.mean(gray, axis=1)  # moyenne par ligne

# Normaliser
row_brightness_norm = (row_brightness - row_brightness.min()) / (row_brightness.max() - row_brightness.min())

# Détecter les changements brusques de luminosité (bordures entre rangées)
diff = np.abs(np.diff(row_brightness_norm))
threshold = np.percentile(diff, 90)
edges_y = np.where(diff > threshold)[0]

print(f"\nMéthode 1 - Lignes avec changements brusques de luminosité:")
print(f"  Seuil: {threshold:.4f}")
print(f"  {len(edges_y)} changements détectés")

# Grouper les edges proches
clusters = []
if len(edges_y) > 0:
    current_cluster = [edges_y[0]]
    for i in range(1, len(edges_y)):
        if edges_y[i] - edges_y[i-1] < 5:
            current_cluster.append(edges_y[i])
        else:
            clusters.append(int(np.median(current_cluster)))
            current_cluster = [edges_y[i]]
    clusters.append(int(np.median(current_cluster)))

print(f"  {len(clusters)} clusters de changements")
print(f"  Positions (échelle originale): {[int(c/scale) for c in clusters[:30]]}")

# Méthode 2: Analyser les lignes horizontales (séparateurs entre cartes)
# Chercher des lignes horizontales uniformes
horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (sw//4, 1))
morph = cv2.morphologyEx(255 - gray, cv2.MORPH_CLOSE, horizontal_kernel)
lines_h = cv2.HoughLinesP(morph, 1, np.pi/180, threshold=sw//2, 
                          minLineLength=sw//3, maxLineGap=10)

print(f"\nMéthode 2 - Lignes horizontales (Hough):")
if lines_h is not None:
    print(f"  {len(lines_h)} lignes trouvées")
    # Trier par Y
    y_positions = sorted(set(int((y1+y2)/2) for x1, y1, x2, y2 in lines_h[:,0]))
    print(f"  {len(y_positions)} positions Y uniques (premières 20): {[int(y/scale) for y in y_positions[:20]]}")
else:
    print("  Aucune ligne trouvée")

# Méthode 3: Analyser la variance verticale pour trouver des zones "actives"
# Les cartes produits ont du contenu (texte, images) → haute variance
# Les espaces entre rangées sont vides → basse variance
variance = np.var(gray.astype(float), axis=1)
var_norm = (variance - variance.min()) / (variance.max() - variance.min())

# Lisser
kernel_size = 15
kernel = np.ones(kernel_size) / kernel_size
var_smooth = np.convolve(var_norm, kernel, mode='same')

# Détecter les "vallées" (faible variance = séparateurs entre rangées)
var_binary = (var_smooth < 0.2).astype(np.uint8)
transitions = np.diff(var_binary)
gaps_start = np.where(transitions == 1)[0]
gaps_end = np.where(transitions == -1)[0]

print(f"\nMéthode 3 - Espaces entre rangées (faible variance):")
print(f"  Débuts: {len(gaps_start)}, Fins: {len(gaps_end)}")
print(f"  5 premiers gaps: positions {[int(g/scale) for g in gaps_start[:5]]} -> {[int(g/scale) for g in gaps_end[:5]]}")

# Méthode 4: Échantillonner l'image et sauvegarder des sections
# pour inspection visuelle
print(f"\nMéthode 4 - Échantillons visuels:")
step = h // 5  # Diviser en 5 sections
for i in range(5):
    y_start = i * step
    y_end = min((i + 1) * step, h)
    section = img[y_start:y_end, :]
    section_path = os.path.join(OUT_DIR, f'section_{i}.png')
    cv2.imwrite(section_path, section)
    # Analyser les couleurs dominantes
    avg_color = np.mean(section.reshape(-1, 3), axis=0)
    print(f"  Section {i}: y={y_start}-{y_end}, couleur moyenne RGB=({avg_color[2]:.0f},{avg_color[1]:.0f},{avg_color[0]:.0f})")

print(f"\n✅ Sections sauvegardées dans {OUT_DIR}")
print(f"  Ouvre-les avec MEDIA pour voir la structure de la circulaire")
