"""Analyse la structure de la circulaire Tigre Géant avec OpenCV
pour détecter la grille de produits."""
import cv2
import numpy as np
import os

IMG_PATH = r'C:\Users\Mark France\aubaines-rapides\cache\tigregeant\circulaire_2026-05-30.png'
img = cv2.imread(IMG_PATH)
if img is None:
    print(f"ERREUR: Impossible de charger {IMG_PATH}")
    exit(1)

h, w = img.shape[:2]
print(f"Image: {w}x{h}")

# Convertir en niveaux de gris
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Seuil adaptatif pour détecter les contours
thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                cv2.THRESH_BINARY_INV, 11, 2)

# Détecter les lignes horizontales et verticales
# Horizontal lines
horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w//5, 1))
horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel)

# Vertical lines
vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h//30))
vertical = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel)

# Combiner
grid = cv2.add(horizontal, vertical)

# Trouver les contours des cellules
contours, hierarchy = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Filtrer les rectangles valides (produits)
min_area = (w * h) * 0.001  # Au moins 0.1% de l'image
max_area = (w * h) * 0.5    # Au plus 50% de l'image

rects = []
for cnt in contours:
    area = cv2.contourArea(cnt)
    if min_area < area < max_area:
        x, y, bw, bh = cv2.boundingRect(cnt)
        ratio = bw / bh
        # Une carte produit est généralement plus large que haute ou carrée
        # Ratio entre 0.3 et 3.0 (pas trop extrême)
        if 0.3 < ratio < 3.0:
            rects.append((x, y, bw, bh))

# Trier par position (haut->bas, gauche->droite)
rects.sort(key=lambda r: (r[1], r[0]))

print(f"\nContours trouvés (filtrés): {len(rects)}")
print(f"\nÉchantillon des 20 premiers rectangles:")
for i, (x, y, bw, bh) in enumerate(rects[:20]):
    print(f"  [{i}] ({x},{y}) {bw}x{bh} ratio={bw/bh:.2f} area={bw*bh}")

# Analyse des colonnes
# Regrouper par position X pour trouver les colonnes
x_positions = [r[0] for r in rects]
y_positions = [r[1] for r in rects]

print(f"\nPositions X: min={min(x_positions)}, max={max(x_positions)}")
print(f"Positions Y: min={min(y_positions)}, max={max(y_positions)}")

# Analyser les largeurs et hauteurs
widths = [r[2] for r in rects]
heights = [r[3] for r in rects]
print(f"\nLargeurs: min={min(widths)}, max={max(widths)}, moyenne={np.mean(widths):.0f}")
print(f"Hauteurs: min={min(heights)}, max={max(heights)}, moyenne={np.mean(heights):.0f}")

# Regrouper par grosseur de taille
from collections import Counter
w_rounded = [round(w/10)*10 for w in widths]
h_rounded = [round(h/10)*10 for h in heights]
print(f"\nTop largeurs: {Counter(w_rounded).most_common(10)}")
print(f"Top hauteurs: {Counter(h_rounded).most_common(10)}")

# Vérifier si la grille est régulière
print(f"\n--- Analyse de grille ---")
# Grouper les Y pour trouver les rangées
y_bins = sorted(set(round(y/20)*20 for y in y_positions))
print(f"Rangées Y (grouper par 20px): {len(y_bins)} rangées")
print(f"  Valeurs: {y_bins[:15]}...")

# Grouper les X pour trouver les colonnes
x_bins = sorted(set(round(x/20)*20 for x in x_positions))
print(f"Colonnes X (grouper par 20px): {len(x_bins)} colonnes")
print(f"  Valeurs: {x_bins[:15]}...")
