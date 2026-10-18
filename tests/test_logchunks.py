import json
import xml.etree.ElementTree as ET

from releaseguard.logchunks import extract_entries, find_dirs, locate_chunk, prepare_logchunks

LOG = "Step 1\r\nStep 2\nERROR: compile failed\n  at Foo.java:10\nStep 5\n"

ELEMENT_XML = """<entries><entry>
<log>logs/java/own@repo/failed/101.log</log>
<chunk>ERROR: compile failed
  at Foo.java:10</chunk>
<keywords>compile failed; Foo.java</keywords>
<category>compilation</category>
</entry></entries>"""

ATTRIBUTE_XML = """<build-failure log="logs/java/own@repo/failed/101.log" category="compilation">
<chunk>ERROR: compile failed</chunk></build-failure>"""


def test_locate_chunk_finds_exact_and_crlf_lines():
    assert locate_chunk(LOG, "ERROR: compile failed\n  at Foo.java:10") == [3, 4]
    assert locate_chunk(LOG, "Step 1") == [1]


def test_locate_chunk_missing_or_empty():
    assert locate_chunk(LOG, "never happened") == []
    assert locate_chunk(LOG, "   ") == []


def test_locate_chunk_tolerates_trailing_whitespace():
    assert locate_chunk("a  \nb\t\nc", "a\nb") == [1, 2]


def test_extract_element_style():
    entries = extract_entries(ET.fromstring(ELEMENT_XML))
    assert len(entries) == 1
    assert entries[0]["log"].endswith("101.log")
    assert entries[0]["chunk"].startswith("ERROR: compile failed")
    assert entries[0]["keywords"] == ["compile failed", "Foo.java"]
    assert entries[0]["category"] == "compilation"


def test_extract_attribute_style():
    entries = extract_entries(ET.fromstring(ATTRIBUTE_XML))
    assert len(entries) == 1 and entries[0]["category"] == "compilation"
    assert entries[0]["chunk"] == "ERROR: compile failed"


def make_tree(tmp_path, xml=ELEMENT_XML):
    (tmp_path / "logs" / "java" / "own@repo" / "failed").mkdir(parents=True)
    (tmp_path / "build-failure-reason").mkdir()
    (tmp_path / "logs" / "java" / "own@repo" / "failed" / "101.log").write_bytes(LOG.encode("utf-8"))
    (tmp_path / "build-failure-reason" / "own@repo.xml").write_text(xml, encoding="utf-8")
    return tmp_path


def test_find_dirs_and_prepare(tmp_path):
    src = make_tree(tmp_path / "src")
    assert find_dirs(src) is not None
    out = tmp_path / "out" / "lc.jsonl"
    stats = prepare_logchunks(src, out, say=lambda _m: None)
    assert stats["written"] == 1 and stats["log_not_found"] == 0 and stats["chunk_not_found"] == 0
    record = json.loads(out.read_text(encoding="utf-8").strip())
    assert record["repo"] == "own@repo" and record["gold_lines"] == [3, 4]
    assert record["language"] == "java" and "\r" not in record["log"]


def test_prepare_counts_missing_logs_chunks_and_bad_xml(tmp_path):
    src = make_tree(tmp_path / "src")
    (src / "build-failure-reason" / "bad@xml.xml").write_text("<oops", encoding="utf-8")
    (src / "build-failure-reason" / "other@repo.xml").write_text(
        ELEMENT_XML.replace("101.log", "999.log"), encoding="utf-8"
    )
    (src / "build-failure-reason" / "own@repo.xml").write_text(
        ELEMENT_XML.replace("ERROR: compile failed\n  at Foo.java:10", "text not in log"), encoding="utf-8"
    )
    stats = prepare_logchunks(src, tmp_path / "o.jsonl", say=lambda _m: None)
    assert stats["xml_errors"] == 1 and stats["log_not_found"] == 1 and stats["chunk_not_found"] == 1
    assert stats["written"] == 0


def test_find_dirs_returns_none_for_wrong_folder(tmp_path):
    assert find_dirs(tmp_path) is None
