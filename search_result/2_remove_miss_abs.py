#!/usr/bin/env python3
"""Remove RIS records without abstracts.

This script looks for an RIS file in sensible default locations under the
script's directory (prefers `ris/refined/qury_res_unique.ris` if present) and
writes a filtered file keeping only records that contain an abstract tag
(`AB`, `N1`, or `N2`). The script runs without any command-line arguments.
"""

from pathlib import Path
import re
import sys


def find_ris_file(base: Path) -> Path:
    # Prefer the specific file if present
    candidate = base / "ris" / "refined" / "qury_res_unique.ris"
    if candidate.exists():
        return candidate

    # Search common directories underneath base
    for sub in (base / "ris" / "refined", base / "ris", base):
        if not sub.exists():
            continue
        ris_files = sorted(sub.glob("*.ris"))
        if ris_files:
            return ris_files[0]

    # Fallback: search recursively for any .ris
    all_ris = sorted(base.rglob("*.ris"))
    if all_ris:
        return all_ris[0]

    raise FileNotFoundError("No .ris file found under {}".format(base))


def split_records(text: str) -> list:
    """Split RIS text into records. Each record starts with 'TY  -' and ends with 'ER  -'.

    This implementation avoids counting whitespace-only chunks (e.g., blank lines
    between records) as records by ensuring we only append a record when it
    contains at least one non-whitespace line.
    """
    lines = text.splitlines(keepends=True)
    records = []
    current = []
    for ln in lines:
        if re.match(r'^\s*TY\s*-', ln) and current:
            # Start of a new record -> finalize previous only if it has content
            if any(l.strip() for l in current):
                records.append(''.join(current))
            current = [ln]
            continue
        current.append(ln)
        if re.match(r'^\s*ER\s*-', ln):
            # End of record -> finalize only if it has content
            if any(l.strip() for l in current):
                records.append(''.join(current))
            current = []
    if any(l.strip() for l in current):
        # Final record without explicit ER
        records.append(''.join(current))
    return records


def has_abstract(record: str) -> bool:
    """Return True if record contains an abstract-like tag with non-empty content."""
    # Check common abstract tags: AB, N1, N2
    # Look for lines like 'AB  - <text>' where <text> contains non-whitespace
    return bool(re.search(r'^\s*(?:AB|N1|N2)\s*-\s*\S', record, flags=re.M))


def write_filtered(records: list, out_path: Path) -> None:
    content = '\n\n'.join(r.strip('\n') for r in records) + '\n'
    out_path.write_text(content, encoding='utf-8')


def main() -> int:
    base = Path(__file__).parent.resolve()
    try:
        in_path = find_ris_file(base)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2

    print(f"Reading: {in_path}")
    text = in_path.read_text(encoding='utf-8', errors='replace')
    records = split_records(text)
    total = len(records)

    kept = [r for r in records if has_abstract(r)]
    kept_count = len(kept)
    removed = total - kept_count

    # Prepare output path
    out_path = in_path.with_name(in_path.stem + "_with_abstracts.ris")
    # Avoid overwriting existing file without notice: if exists, add numeric suffix
    if out_path.exists():
        i = 1
        while True:
            candidate = out_path.with_name(f"{in_path.stem}_with_abstracts_{i}.ris")
            if not candidate.exists():
                out_path = candidate
                break
            i += 1

    write_filtered(kept, out_path)

    print(f"Total records: {total}")
    print(f"Kept (with abstract): {kept_count}")
    print(f"Removed  (without abstract): {removed}")
    print(f"Filtered file written to: {out_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
