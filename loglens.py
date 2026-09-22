from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

DEFAULT_SEVERITY_ORDER = ["CRITICAL", "ERROR", "WARN", "INFO", "DEBUG", "TRACE", "UNKNOWN"]

SEVERITY_RE = re.compile(
    r"\b(CRITICAL|FATAL|ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE|NOTICE)\b",
    re.IGNORECASE,
)

SEVERITY_RANK = {
    "CRITICAL": 0,
    "FATAL": 0,
    "ERROR": 1,
    "WARN": 2,
    "WARNING": 2,
    "INFO": 3,
    "DEBUG": 4,
    "TRACE": 5,
    "NOTICE": 3,
    "UNKNOWN": 99,
}


@dataclass(frozen=True)
class LogEntry:
    lineno: int
    severity: str
    message: str


@dataclass(frozen=True)
class Summary:
    total_lines: int
    parsed_lines: int
    skipped_lines: int
    severity_counts: Counter
    top_messages: Counter
    hotspots: List[LogEntry]


def _detect_severity(line: str) -> str:
    match = SEVERITY_RE.search(line)
    if not match:
        return "UNKNOWN"
    token = match.group(1).upper()
    return token if token in SEVERITY_RANK else token


def _normalize_message(line: str) -> str:
    text = line.strip()
    text = SEVERITY_RE.sub("", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ][0-9:+-]+\b", "", text)
    text = re.sub(r"\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b", "", text)
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b", "0xHEX", text)
    text = re.sub(r"\b(?:0x)?[0-9a-fA-F]{4,}\b", "0xHEX", text)
    text = re.sub(r"\b\d+\b", "N", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "(empty)"


def _read_lines(path: Path, max_lines: Optional[int]) -> Tuple[Optional[List[str]], Optional[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, str(exc)
    lines = text.splitlines()
    if max_lines is not None and max_lines >= 0:
        lines = lines[:max_lines]
    return lines, None


def analyze(
    paths: Sequence[Path],
    top: int,
    min_count: int,
    max_lines: Optional[int],
) -> Tuple[Summary, List[str]]:
    total_lines = 0
    parsed_lines = 0
    skipped_lines = 0
    severity_counts: Counter = Counter()
    message_counts: Counter = Counter()
    hotspots: List[LogEntry] = []
    errors: List[str] = []

    for path in paths:
        lines, err = _read_lines(path, max_lines)
        if lines is None:
            errors.append(f"cannot read {path}: {err}")
            continue
        file_hotspots: List[LogEntry] = []
        for lineno, line in enumerate(lines, start=1):
            total_lines += 1
            if not line.strip():
                skipped_lines += 1
                continue
            severity = _detect_severity(line)
            message = _normalize_message(line)
            severity_counts[severity] += 1
            message_counts[message] += 1
            parsed_lines += 1
            file_hotspots.append(LogEntry(lineno=lineno, severity=severity, message=message))

        file_hotspots.sort(key=lambda entry: SEVERITY_RANK.get(entry.severity, 99))
        hotspots.extend(file_hotspots[: max(0, top)])

    seen: set[str] = set()
    deduped: List[LogEntry] = []
    for entry in hotspots:
        if entry.message in seen:
            continue
        seen.add(entry.message)
        deduped.append(entry)
    hotspots = deduped[: top]

    top_messages = Counter({message: count for message, count in message_counts.items() if count >= min_count})
    return Summary(
        total_lines=total_lines,
        parsed_lines=parsed_lines,
        skipped_lines=skipped_lines,
        severity_counts=severity_counts,
        top_messages=top_messages,
        hotspots=hotspots,
    ), errors


def format_report(summary: Summary, paths: Sequence[Path], top: int, min_count: int, errors: List[str]) -> str:
    parts: List[str] = []
    for error in errors:
        parts.append(f"error: {error}")
    files = ", ".join(str(p) for p in paths) or "(stdin)"
    parts.append(f"files: {files}")
    parts.append(f"lines: {summary.total_lines}  parsed: {summary.parsed_lines}  skipped: {summary.skipped_lines}")
    parts.append("")

    ordered = sorted(
        summary.severity_counts.items(),
        key=lambda item: (SEVERITY_RANK.get(item[0], 99), item[0]),
    )
    if ordered:
        parts.append("severity:")
        for severity, count in ordered:
            parts.append(f"  {severity:<10} {count}")
    else:
        parts.append("severity: (none)")
    parts.append("")

    common = summary.top_messages.most_common(top)
    if common:
        parts.append(f"top messages (min_count={min_count}):")
        for message, count in common:
            parts.append(f"  {count:>6}  {message}")
    else:
        parts.append("top messages: (none)")
    parts.append("")

    if summary.hotspots:
        parts.append("hotspots:")
        for entry in summary.hotspots:
            parts.append(f"  [{entry.severity:<10}] {entry.message}")
    else:
        parts.append("hotspots: (none)")

    return "\n".join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loglens",
        description="Summarize log files by severity and recurring message patterns.",
    )
    parser.add_argument("files", nargs="*", type=Path, help="log files to analyze")
    parser.add_argument(
        "-n",
        "--top",
        type=int,
        default=10,
        help="number of top messages and hotspots to show",
    )
    parser.add_argument(
        "-c",
        "--min-count",
        type=int,
        default=2,
        help="minimum occurrences for a message to appear in top messages",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="cap number of lines read per file",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = list(args.files)
    if not paths:
        print("loglens: no input files provided", file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 2
    summary, errors = analyze(paths, top=args.top, min_count=args.min_count, max_lines=args.max_lines)
    print(format_report(summary, paths, top=args.top, min_count=args.min_count, errors=errors))
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
