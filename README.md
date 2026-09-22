# loglens

Log summarizer CLI that counts severity levels, groups recurring messages, and highlights hotspots.

## About

`loglens` reads plain-text log files, normalizes similar lines, and emits a compact summary:
severity breakdown, most common messages, and top severity hotspots.

## Features

- Severity-aware grouping: `CRITICAL`, `ERROR`, `WARN`, `INFO`, `DEBUG`, `TRACE`
- Message normalization: collapses timestamps, IPs/ports, hex IDs, and numbers
- Hotspot detection: worst severity locations, deduped by normalized message
- Multi-file support with line caps

## Installation

```bash
python -m pip install -e .
```

## Usage

```bash
loglens app.log
loglens app.log error.log --top 20 --min-count 3 --max-lines 5000
```

## Options

| Flag | Default | Description |
| --- | --- | --- |
| `-n`, `--top` | `10` | number of top messages and hotspots to show |
| `-c`, `--min-count` | `2` | minimum occurrences for a message to appear |
| `--max-lines` | none | cap number of lines read per file |

## Project structure

```
loglens.py
tests/
  test_loglens.py
pyproject.toml
README.md
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Analysis completed successfully |
| `2` | No input files, or one or more files could not be read |

## Tags / keywords

logs, cli, severity, summarizer, developer-tools, python
