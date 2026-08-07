"""
Migration script: Clear persons, import from Excel, match photos.

Usage:
    cd backend
    python migrate_persons.py [--dry-run]
"""

import sys
import io
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from importer import import_persons_from_excel, match_photos_to_persons


def main():
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("Step 1: Import persons from Excel")
    print("=" * 60)
    result = import_persons_from_excel(dry_run=dry_run)

    if dry_run:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    if "error" in result:
        print(f"[ERROR] {result['error']}")
        return

    print(f"\nInserted: {result['inserted']}")
    print(f"Unmatched departments: {result.get('unmatched_count', 0)}")

    if result.get("unmatched"):
        print("Unmatched entries (first 20):")
        for item in result["unmatched"]:
            print(f"  - {item['name']}: dept1=[{item['dept1']}], dept2=[{item['dept2']}] → [{item['resolved']}]")

    print()
    print("=" * 60)
    print("Step 2: Match photos to persons by name")
    print("=" * 60)
    photo_result = match_photos_to_persons()

    print(f"\nPhoto match result:")
    print(f"  Matched: {photo_result['matched']}/{photo_result['total_photos']}")
    if photo_result.get("unmatched_photos"):
        print(f"  Unmatched photos: {len(photo_result['unmatched_photos'])}")
        for f in photo_result["unmatched_photos"]:
            print(f"    - {f}")

    print("\n[DONE] Migration completed.")


if __name__ == "__main__":
    main()
