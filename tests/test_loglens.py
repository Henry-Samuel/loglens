from __future__ import annotations

import sys
from collections import Counter

from loglens import LogEntry, analyze, format_report, main


SAMPLE_LOG = """2026-01-01 00:00:01 INFO  Starting service
2026-01-01 00:00:02 DEBUG Loading config from /etc/app/config.yaml
2026-01-01 00:00:03 INFO  Starting service
2026-01-01 00:00:04 ERROR Connection refused to 10.0.0.5:5432
2026-01-01 00:00:05 WARN  Retrying connection
2026-01-01 00:00:06 ERROR Connection refused to 10.0.0.5:5432
2026-01-01 00:00:07 CRITICAL Shutdown requested
2026-01-01 00:00:08 INFO  Starting service
2026-01-01 00:00:09 WARN  Memory usage high
2026-01-01 00:00:10 ERROR Disk write failed
"""


def _write_sample(tmp_path, name="app.log", content=SAMPLE_LOG):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_analyze_counts_severities():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_sample(Path(tmp))
        summary, _ = analyze([path], top=10, min_count=1, max_lines=None)
    assert summary.total_lines == len(SAMPLE_LOG.splitlines())
    assert summary.parsed_lines == summary.total_lines
    assert summary.skipped_lines == 0
    assert summary.severity_counts["INFO"] == 3
    assert summary.severity_counts["ERROR"] == 3
    assert summary.severity_counts["WARN"] == 2
    assert summary.severity_counts["CRITICAL"] == 1


def test_analyze_groups_messages():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_sample(Path(tmp))
        summary, _ = analyze([path], top=10, min_count=2, max_lines=None)
    most_common = dict(summary.top_messages.most_common())
    assert most_common["Starting service"] == 3
    assert most_common["Connection refused to 0xHEX"] == 2
    assert "Retrying connection" not in most_common


def test_analyze_min_count_filters_messages():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_sample(Path(tmp))
        summary, _ = analyze([path], top=10, min_count=5, max_lines=None)
    assert summary.top_messages == Counter()


def test_analyze_skips_blank_lines():
    log = "line1\n\nline3\n"
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_sample(Path(tmp), content=log)
        summary, _ = analyze([path], top=10, min_count=1, max_lines=None)
    assert summary.total_lines == 3
    assert summary.skipped_lines == 1
    assert summary.parsed_lines == 2


def test_analyze_limits_lines():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_sample(Path(tmp))
        summary, _ = analyze([path], top=10, min_count=1, max_lines=4)
    assert summary.total_lines == 4
    assert summary.parsed_lines == 4


def test_hotspots_are_sorted_by_severity():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_sample(Path(tmp))
        summary, _ = analyze([path], top=3, min_count=1, max_lines=None)
    severities = [entry.severity for entry in summary.hotspots]
    expected_rank = {
        "CRITICAL": 0, "FATAL": 0, "ERROR": 1, "WARN": 2,
        "WARNING": 2, "INFO": 3, "DEBUG": 4, "TRACE": 5, "UNKNOWN": 99
    }
    assert severities == sorted(severities, key=lambda s: (expected_rank.get(s, 99), s))


def test_report_contains_expected_sections():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_sample(Path(tmp))
        summary, _ = analyze([path], top=10, min_count=1, max_lines=None)
    report = format_report(summary, [path], top=10, min_count=1, errors=[])
    assert "severity:" in report
    assert "top messages" in report
    assert "hotspots:" in report


def test_main_returns_zero(capsys):
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_sample(Path(tmp))
        rc = main([str(path)])
    assert rc == 0
    out, err = capsys.readouterr()
    assert "severity:" in out


def test_main_missing_file_reports_error_and_returns_two(capsys):
    rc = main(["/tmp/loglens-missing-xyz.log"])
    assert rc == 2
    out, err = capsys.readouterr()
    assert "error: cannot read" in out
    assert "loglens-missing-xyz.log" in out


def test_main_no_args_returns_two(capsys):
    rc = main([])
    assert rc == 2
    out, err = capsys.readouterr()
    assert "no input files" in err
