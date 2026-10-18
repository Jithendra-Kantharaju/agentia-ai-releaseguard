from releaseguard.evidence import evidence_hash, normalize_log, short, strip_ansi

WORK = {"id": "US-1", "title": "T", "acceptance_criteria": ["a"], "security_findings": {"critical": 0}}
TESTS = {"passed": 5, "failed": 0}


def test_hash_is_stable():
    assert evidence_hash(WORK, TESTS, "log") == evidence_hash(dict(WORK), dict(TESTS), "log")


def test_hash_changes_when_log_changes():
    assert evidence_hash(WORK, TESTS, "log") != evidence_hash(WORK, TESTS, "log2")


def test_hash_changes_when_tests_change():
    assert evidence_hash(WORK, TESTS, "log") != evidence_hash(WORK, {"passed": 4, "failed": 1}, "log")


def test_hash_changes_when_security_findings_change():
    other = {**WORK, "security_findings": {"critical": 1}}
    assert evidence_hash(WORK, TESTS, "log") != evidence_hash(other, TESTS, "log")


def test_volatile_work_item_fields_do_not_change_the_hash():
    noisy = {**WORK, "lastModifiedDate": "2026-10-17T10:00:00Z"}
    assert evidence_hash(WORK, TESTS, "log") == evidence_hash(noisy, TESTS, "log")


def test_line_endings_do_not_change_the_hash():
    assert evidence_hash(WORK, TESTS, "a\nb") == evidence_hash(WORK, TESTS, "a\r\nb")


def test_normalize_and_strip_helpers():
    assert normalize_log("a\r\nb\rc") == "a\nb\nc"
    assert strip_ansi("\x1b[31mred\x1b[0m") == "red"
    assert short("abcdef0123456789", 4) == "abcd"
