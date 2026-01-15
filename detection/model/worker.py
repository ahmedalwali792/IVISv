#!/usr/bin/env python
"""
Lightweight worker script for safe, killable model inference.

Usage: python worker.py <input_npy_path>

This script is intentionally simple: it loads the model, reads a numpy
array from the provided .npy file, runs `model.predict`, and prints the
JSON result to stdout.

The runner calls this script as a subprocess with a timeout so the OS
can kill it if it exceeds allowed time.
"""
import sys
import os
import json
import numpy as np

from detection.model.loader import load_model


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "missing input path"}))
        sys.exit(2)

    input_path = sys.argv[1]

    if not os.path.exists(input_path):
        print(json.dumps({"error": f"input file not found: {input_path}"}))
        sys.exit(3)

    try:
        model = load_model()
    except Exception as e:
        print(json.dumps({"error": f"model load failed: {e}"}))
        sys.exit(4)

    try:
        arr = np.load(input_path)
    except Exception as e:
        print(json.dumps({"error": f"failed to load npy: {e}"}))
        sys.exit(5)

    try:
        out = model.predict(arr)
        print(json.dumps(out))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"error": f"inference failed: {e}"}))
        sys.exit(6)


if __name__ == "__main__":
    main()
