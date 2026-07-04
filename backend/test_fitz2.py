import sys
import subprocess

# Check what python the uvicorn process is using
print("Python:", sys.executable)
print("Prefix:", sys.prefix)

# Try import
try:
    import fitz
    print("fitz version:", fitz.__version__)
    # Quick test
    doc = fitz.open()
    print("fitz open() OK")
except Exception as e:
    print("fitz FAIL:", type(e).__name__, e)

# Also try alternative
try:
    import pymupdf
    print("pymupdf version:", pymupdf.__version__)
except Exception as e:
    print("pymupdf FAIL:", type(e).__name__, e)
