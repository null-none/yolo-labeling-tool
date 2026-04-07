"""
Removes images from dataset/train that have no corresponding .txt annotation file.
"""

import os

TRAIN_DIR = os.path.join(os.path.dirname(__file__), "dataset", "train")

deleted = 0
for fname in os.listdir(TRAIN_DIR):
    if not fname.endswith(".jpg"):
        continue
    txt_path = os.path.join(TRAIN_DIR, fname.replace(".jpg", ".txt"))
    if not os.path.exists(txt_path):
        os.remove(os.path.join(TRAIN_DIR, fname))
        print(f"Deleted: {fname}")
        deleted += 1

print(f"\nDone. Files deleted: {deleted}")
