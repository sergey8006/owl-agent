"""
Install document reading dependencies.
Usage: python install_deps.py
"""
import subprocess
import sys

PACKAGES = [
    "python-docx>=1.0",   # DOCX
    "openpyxl>=3.0",      # XLSX
    "xlrd>=2.0",          # XLS
    "PyPDF2>=3.0",        # PDF
]

print("Installing document reader dependencies...")
for pkg in PACKAGES:
    print(f"  Installing {pkg} ...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", pkg],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(f"    OK")
    else:
        print(f"    FAILED: {r.stderr.strip()}")

# System tools
print("\nFor better PDF/DOC support, install system tools:")
print("  pdftotext:  sudo apt install poppler-utils  (or choco install poppler)")
print("  catdoc:     sudo apt install catdoc          (or choco install catdoc)")
print("Done.")
