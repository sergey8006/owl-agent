"""
File Organizer — sort files in a directory by type.
Usage: python organize.py /path/to/directory [--dry-run] [--recursive] [--skip-empty]

Categories:
  Images, Documents, Video, Music, Archives, Code, Other
"""
import os
import sys
import shutil
from pathlib import Path

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".tif", ".raw", ".cr2", ".nef"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".md", ".epub", ".mobi"},
    "Video": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".3gp"},
    "Music": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".aiff"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".dmg"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sql", ".r", ".swift", ".kt", ".scala", ".vue", ".jsx", ".tsx"},
    "Data": {".csv", ".tsv", ".json", ".xml", ".parquet", ".db", ".sqlite", ".sqlite3"},
    "Executables": {".exe", ".msi", ".app", ".deb", ".rpm", ".apk"},
    "Fonts": {".ttf", ".otf", ".woff", ".woff2", ".eot"},
}

# Reverse map: ext -> category
EXT_TO_CAT = {}
for cat, exts in CATEGORIES.items():
    for ext in exts:
        EXT_TO_CAT[ext] = cat


def organize(directory, dry_run=False, recursive=False, skip_empty=True):
    """Sort files in directory into subfolders by type."""
    d = Path(directory)
    if not d.is_dir():
        print(f"Error: {directory} is not a directory")
        return 0

    moved = 0
    errors = 0
    skipped = 0

    def process_dir(target_dir):
        nonlocal moved, errors, skipped
        try:
            entries = list(target_dir.iterdir())
        except PermissionError:
            print(f"  Permission denied: {target_dir}")
            return

        for f in entries:
            if f.is_dir():
                if recursive and f.name not in CATEGORIES:
                    process_dir(f)
                continue
            if not f.is_file():
                continue

            # Skip the script itself
            if f.name == os.path.basename(__file__):
                continue

            ext = f.suffix.lower()
            target_cat = EXT_TO_CAT.get(ext, "Other")
            dest = target_dir / target_cat

            # Don't move if already in correct folder
            if f.parent.name == target_cat:
                skipped += 1
                continue

            if dry_run:
                print(f"  {f.name} → {target_cat}/")
            else:
                try:
                    dest.mkdir(exist_ok=True)
                    dest_file = dest / f.name
                    # Handle name conflicts
                    if dest_file.exists():
                        stem = f.stem
                        counter = 1
                        while dest_file.exists():
                            dest_file = dest / f"{stem}_{counter}{f.suffix}"
                            counter += 1
                    shutil.move(str(f), str(dest_file))
                    print(f"  {f.name} → {target_cat}/")
                except Exception as e:
                    print(f"  ERROR moving {f.name}: {e}")
                    errors += 1
                    continue
            moved += 1

    process_dir(d)

    mode = "Would move" if dry_run else "Moved"
    print(f"\n{mode} {moved} files" + (f", {errors} errors" if errors else "") + (f", {skipped} already sorted" if skipped else ""))
    return moved


def undo_organize(directory):
    """Move all files from category subfolders back to the root directory."""
    d = Path(directory)
    if not d.is_dir():
        print(f"Error: {directory} is not a directory")
        return

    moved = 0
    for cat_dir in d.iterdir():
        if not cat_dir.is_dir():
            continue
        if cat_dir.name not in CATEGORIES and cat_dir.name != "Other":
            continue
        for f in cat_dir.iterdir():
            if f.is_file():
                dest = d / f.name
                if dest.exists():
                    stem = f.stem
                    counter = 1
                    while dest.exists():
                        dest = d / f"{stem}_{counter}{f.suffix}"
                        counter += 1
                shutil.move(str(f), str(dest))
                moved += 1
        # Remove empty category dirs
        try:
            cat_dir.rmdir()
        except OSError:
            pass

    print(f"Unmoved {moved} files back to {d}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    recursive = "--recursive" in sys.argv
    undo = "--undo" in sys.argv

    # Filter out flags to get the path
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "."

    if undo:
        undo_organize(path)
    else:
        organize(path, dry, recursive)
