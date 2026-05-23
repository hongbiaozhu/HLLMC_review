#!/usr/bin/env python3

import os
import re
import sys
from typing import List, Tuple, Dict


RIS_TAG_RE = re.compile(r"^([A-Z0-9]{2})\s{2}-\s?(.*)$")


def normalize_doi(doi: str) -> str:
    """Normalize DOI string for reliable comparison."""
    if doi is None:
        return ""
    d = doi.strip().lower()
    d = re.sub(r"^doi:\s*", "", d)
    return d


def normalize_title(title: str) -> str:
    """Normalize title by lowercasing, removing punctuation, and collapsing spaces."""
    if title is None:
        return ""
    t = title.strip().lower()
    # Remove punctuation (keep unicode word characters and whitespace)
    t = re.sub(r"[^\w\s]", "", t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t)
    return t


def parse_ris_records(lines: List[str]) -> List[Tuple[List[str], Dict[str, str]]]:
    """Parse RIS file lines into a list of (original_lines, fields) tuples.

    - original_lines: the list of lines belonging to the record (including tag lines and ER line)
    - fields: dict mapping RIS tags to their full (possibly multi-line) value
    """
    records = []
    cur_lines: List[str] = []
    cur_fields: Dict[str, str] = {}
    cur_tag = None

    for line in lines:
        stripped = line.rstrip("\n")
        # If this is the end of record marker, include it and push the record
        if stripped.startswith("ER  -"):
            cur_lines.append(stripped)
            # push record
            records.append((cur_lines[:], cur_fields.copy()))
            # reset
            cur_lines = []
            cur_fields = {}
            cur_tag = None
            continue

        # Normal line - append to record lines
        cur_lines.append(stripped)

        m = RIS_TAG_RE.match(stripped)
        if m:
            tag, val = m.group(1), m.group(2)
            cur_tag = tag
            # Keep the first value for each tag (append if tag repeats)
            if tag in cur_fields:
                # Some tags may appear multiple times (e.g., AU). Join with ' | ' for simplicity
                cur_fields[tag] = cur_fields[tag] + " | " + val
            else:
                cur_fields[tag] = val
        else:
            # Continuation of previous tag (no new tag at line start)
            if cur_tag is not None:
                cur_fields[cur_tag] = cur_fields.get(cur_tag, "") + " " + stripped.strip()
            else:
                # Malformed/unknown line at file start - ignore
                pass

    # If file didn't end with ER, but had accumulated lines, add them as a record
    # Only append if we collected any fields; ignore trailing blank lines (prevents
    # counting an extra empty record when file ends with blank lines).
    if cur_lines and cur_fields:
        records.append((cur_lines[:], cur_fields.copy()))
    elif cur_lines and not cur_fields:
        # Trailing stray lines (e.g., blank lines) — ignore them.
        pass

    return records


def remove_duplicates(records: List[Tuple[List[str], Dict[str, str]]]) -> List[List[str]]:
    """Return deduplicated list of records (as lists of original lines).

    Duplicate detection keys: DOI (preferred) or normalized Title. When a duplicate
    is found, prefer keeping the record that contains an abstract (`AB` tag).
    If both have (or both lack) AB, keep the first occurrence.
    """
    # Maps for seen keys -> info dict { 'idx': index_in_unique, 'has_ab': bool, 'doi': str, 'title': str }
    seen_by_doi: Dict[str, Dict] = {}
    seen_by_title: Dict[str, Dict] = {}

    unique_records: List[List[str]] = []

    for lines, fields in records:
        doi_raw = fields.get("DO", "")
        ti_raw = fields.get("TI", "")
        ab_raw = fields.get("AB", "")

        doi = normalize_doi(doi_raw)
        title = normalize_title(ti_raw)
        has_ab = bool(ab_raw and ab_raw.strip())

        found = None
        # Check DOI first
        if doi and doi in seen_by_doi:
            found = seen_by_doi[doi]
        # Then check title
        elif title and title in seen_by_title:
            found = seen_by_title[title]

        if not found:
            # New unique record
            idx = len(unique_records)
            unique_records.append(lines)
            info = {"idx": idx, "has_ab": has_ab, "doi": doi, "title": title}
            if doi:
                seen_by_doi[doi] = info
            if title:
                seen_by_title[title] = info
        else:
            # Duplicate found; prefer the record with abstract
            if found["has_ab"] and not has_ab:
                # existing has abstract, current no abstract -> skip current
                continue
            elif not found["has_ab"] and has_ab:
                # existing lacks abstract but current has -> replace stored record
                idx = found["idx"]
                unique_records[idx] = lines
                # update info
                found["has_ab"] = True
                # update DOI/title keys to point to this info
                if doi:
                    seen_by_doi[doi] = found
                if title:
                    seen_by_title[title] = found
                # also ensure stored DOI/title fields are set if previously empty
                if not found.get("doi") and doi:
                    found["doi"] = doi
                if not found.get("title") and title:
                    found["title"] = title
            else:
                # both have AB or both lack AB -> keep the first (skip current)
                continue

    return unique_records


def write_ris_records(out_path: str, records_lines: List[List[str]]) -> None:
    """Write RIS records (each as list of lines) to out_path."""
    with open(out_path, "w", encoding="utf-8") as f:
        for rec_lines in records_lines:
            for ln in rec_lines:
                f.write(ln.rstrip("\n") + "\n")
            # Ensure a blank line between records for readability
            f.write("\n")


def main():
   
    # Default file locations (relative to this script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, "ris", "refined", "qury_res.ris")
    output_path = os.path.join(script_dir, "ris", "refined", "qury_res_unique.ris")

    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    records = parse_ris_records(lines)
    total = len(records)

    unique = remove_duplicates(records)
    kept = len(unique)
    removed = total - kept

    write_ris_records(output_path, unique)

    print(f"Processed: {total} records")
    print(f"Kept: {kept} unique records")
    print(f"Removed duplicates: {removed}")
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
