#!/usr/bin/env python3
"""Debug OCR block structure."""
import os, pytesseract
from PIL import Image

os.environ['TESSDATA_PREFIX'] = 'C:/Users/Mark France/tessdata/'
pytesseract.pytesseract.tesseract_cmd = 'C:/Program Files/Tesseract-OCR/tesseract.exe'

img = Image.open('C:/Users/Mark France/aubaines-rapides/cache/marchestradition/page_01.jpg')
w, h = img.size
img = img.resize((w*2, h*2), Image.LANCZOS)
if img.mode != 'L':
    img = img.convert('L')

data = pytesseract.image_to_data(img, lang='fra', config='--psm 6 --oem 3', output_type=pytesseract.Output.DICT)

blocks = {}
n = len(data['text'])
for i in range(n):
    text = data['text'][i].strip()
    conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 0
    if text and conf > 10:
        bn = data['block_num'][i]
        if bn not in blocks:
            blocks[bn] = []
        blocks[bn].append({
            'text': text,
            'top': data['top'][i],
            'left': data['left'][i],
        })

for bn in sorted(blocks.keys()):
    words = blocks[bn]
    avg_y = sum(w['top'] for w in words) / len(words)
    avg_x = sum(w['left'] for w in words) / len(words)
    full_text = ' '.join(w['text'] for w in words)
    short = full_text[:200].replace('\n', ' ')
    print(f'Block {bn:2d} | y={avg_y:7.0f} x={avg_x:7.0f} | {len(words):3d}w | {short}')
