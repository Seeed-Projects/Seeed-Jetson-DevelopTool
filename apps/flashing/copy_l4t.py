#!/usr/bin/env python3
"""Copy L4TData.json from source to package data directory."""
import shutil
import os

src = os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'jetson', 'L4TData.json')
dst = os.path.join(os.path.dirname(__file__), 'seeed_jetson_flash', 'data', 'l4t_data.json')

src = os.path.abspath(src)
dst = os.path.abspath(dst)

print(f"Copying {src} -> {dst}")
shutil.copy2(src, dst)
print("Done!")
