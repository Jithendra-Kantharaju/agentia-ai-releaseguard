"""Converts the LogChunks dataset (real CI build logs with human-labelled failure chunks) to JSONL.

LogChunks (Brandt, Panichella, Beller, TU Delft, CC BY 4.0): https://zenodo.org/records/3632351
  logs/<language>/<owner@repo>/failed/<build-id>.log
  build-failure-reason/<owner@repo>.xml   one entry per log: log path, failure chunk, keywords, category

The paper lists the XML fields (log path, chunk, keywords, category) but not the exact tag names, so the
reader below looks for entries by structure instead of by tag name. Always run `inspect-logchunks` first and
check that `prepare-logchunks` reports a sensible number of entries.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

from .evidence import normalize_log, strip_ansi

LOG_PATH_RE = re.compile(r"\.log\s*$")


def find_dirs(src: Path) -> tuple[Path, Path] | None:
    """Find the 'logs' and 'build-failure-reason' folders within a few levels of src."""
    src = Path(src)
    candidates = [src] + [p for p in src.rglob("*") if p.is_dir() and len(p.relative_to(src).parts) <= 3]
    for base in candidates:
        logs = next((d for d in base.iterdir() if d.is_dir() and d.name.lower() == "logs"), None) if base.is_dir() else None
        reasons = next((d for d in base.iterdir() if d.is_dir() and d.name.lower() == "build-failure-reason"), None) if base.is_dir() else None
        if logs and reasons:
            return logs, reasons
    return None


def inspect_logchunks(src: Path, say: Callable[[str], None] = print) -> bool:
    dirs = find_dirs(src)
    if not dirs:
        say(f"Could not find 'logs' and 'build-failure-reason' folders under {src}.")
        say("Download LogChunks.zip from https://zenodo.org/records/3632351 and extract it, then pass that folder.")
        return False
    logs_dir, xml_dir = dirs
    xml_files = sorted(xml_dir.rglob("*.xml"))
    log_files = list(logs_dir.rglob("*.log"))
    say(f"logs folder:   {logs_dir}  ({len(log_files)} .log files)")
    say(f"labels folder: {xml_dir}  ({len(xml_files)} .xml files)")
    if xml_files:
        sample = xml_files[0]
        text = sample.read_text(encoding="utf-8", errors="replace")
        say(f"\nFirst label file: {sample.name} (first 1200 characters)")
        say("-" * 60)
        say(text[:1200])
        say("-" * 60)
    return True


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _fields(elem: ET.Element) -> dict[str, str]:
    """Attributes and direct children of an element as name -> text."""
    fields = {k.lower(): v for k, v in elem.attrib.items()}
    for child in elem:
        text = "".join(child.itertext()).strip()
        if text:
            fields.setdefault(_local(child.tag), text)
    return fields


def extract_entries(root: ET.Element) -> list[dict]:
    """Find entries by structure: an element that has a single-line value ending in '.log' plus a chunk of text."""
    entries: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for elem in root.iter():
        fields = _fields(elem)
        log_field = next(
            (k for k, v in fields.items() if "\n" not in v.strip() and len(v.strip()) < 300 and LOG_PATH_RE.search(v.strip())),
            None,
        )
        if not log_field:
            continue
        log_path = fields[log_field].strip()
        others = {k: v for k, v in fields.items() if k != log_field}
        keyword_text = next((v for k, v in others.items() if "keyword" in k), "")
        category = next((v for k, v in others.items() if "categor" in k), None)
        chunk_candidates = {k: v for k, v in others.items() if "keyword" not in k and "categor" not in k}
        if not chunk_candidates:
            continue
        chunk = max(chunk_candidates.values(), key=len)
        key = (log_path, chunk[:80])
        if key in seen:
            continue
        seen.add(key)
        keywords = [k.strip() for k in re.split(r"[;,\n]", keyword_text) if k.strip()]
        entries.append({"log": log_path, "chunk": chunk, "keywords": keywords, "category": category})
    return entries


def locate_chunk(log: str, chunk: str) -> list[int]:
    """1-based line numbers of the labelled chunk inside the log, or [] if it cannot be found."""
    log = normalize_log(log)
    chunk = normalize_log(chunk).strip()
    if not chunk:
        return []
    index = log.find(chunk)
    if index >= 0:
        start = log.count("\n", 0, index) + 1
        return list(range(start, start + chunk.count("\n") + 1))
    log_lines = [line.rstrip() for line in log.split("\n")]
    chunk_lines = [line.rstrip() for line in chunk.split("\n")]
    n = len(chunk_lines)
    if len(log_lines) * n > 5_000_000:
        return []
    for start in range(len(log_lines) - n + 1):
        if log_lines[start : start + n] == chunk_lines:
            return list(range(start + 1, start + n + 1))
    return []


def _clean(text: str) -> str:
    return strip_ansi(normalize_log(text))


def prepare_logchunks(src: Path, out_path: Path, max_lines: int = 20000, say: Callable[[str], None] = print) -> dict:
    dirs = find_dirs(src)
    if not dirs:
        raise FileNotFoundError("Could not find the 'logs' and 'build-failure-reason' folders. Run inspect-logchunks.")
    logs_dir, xml_dir = dirs

    by_tail: dict[str, Path] = {}
    by_name: dict[str, list[Path]] = {}
    for path in logs_dir.rglob("*.log"):
        tail = "/".join(path.parts[-3:])
        by_tail[tail] = path
        by_name.setdefault(path.name, []).append(path)

    stats = {"xml_files": 0, "xml_errors": 0, "entries": 0, "written": 0, "log_not_found": 0, "chunk_not_found": 0, "too_long": 0}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as out:
        for xml_file in sorted(xml_dir.rglob("*.xml")):
            stats["xml_files"] += 1
            repo = xml_file.stem
            try:
                root = ET.parse(xml_file).getroot()
            except ET.ParseError:
                stats["xml_errors"] += 1
                continue
            for entry in extract_entries(root):
                stats["entries"] += 1
                rel = entry["log"].replace("\\", "/")
                base = Path(rel).name
                candidates = [logs_dir / rel, Path(src) / rel, by_tail.get(f"{repo}/failed/{base}")]
                if len(by_name.get(base, [])) == 1:
                    candidates.append(by_name[base][0])
                log_file = next((c for c in candidates if c and c.exists()), None)
                if not log_file:
                    stats["log_not_found"] += 1
                    continue
                log = _clean(log_file.read_text(encoding="utf-8", errors="replace"))
                if log.count("\n") + 1 > max_lines:
                    stats["too_long"] += 1
                    continue
                gold = locate_chunk(log, _clean(entry["chunk"]))
                if not gold:
                    stats["chunk_not_found"] += 1
                    continue
                try:
                    parts = log_file.relative_to(logs_dir).parts
                except ValueError:
                    parts = ()
                record = {
                    "id": f"{repo}:{Path(base).stem}",
                    "repo": repo,
                    "language": parts[0] if len(parts) >= 4 else None,
                    "log": log,
                    "gold_lines": gold,
                    "keywords": entry["keywords"],
                    "category": entry["category"],
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                stats["written"] += 1
    say(json.dumps(stats, indent=2))
    return stats
