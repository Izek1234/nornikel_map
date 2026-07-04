import sys
try:
    import fitz
    print("fitz OK:", fitz.__version__)
except Exception as e:
    print("fitz FAIL:", e)
