# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Single-file Python CLI utility for batch compressing files using 7z. Takes an input folder of files, splits them into configurable batches, and creates compressed archives with support for encryption, split volumes, verification, and metadata export.

## Commands

```bash
# Run the application
python main.py --input <input_folder> --output <output_folder> [options]

# Check if compression tools (7z, zip, rar) are available
python main.py --check

# Show version
python main.py --version

# Auto mode with custom settings (skips confirmation prompts)
python main.py --input ./files --output ./archives --batch 50 --prefix backup --ext zip --auto --threads 4

# Dry run to preview without creating archives
python main.py --input ./files --output ./archives --dry-run

# Verbose mode for debugging
python main.py --input ./files --output ./archives --verbose

# Exclude patterns
python main.py --input ./files --output ./archives --exclude "*.tmp" --exclude "*.log"

# Recursive with metadata export
python main.py --input ./files --output ./archives --recursive --metadata output.json

# High compression with verification
python main.py --input ./files --output ./archives --compression-level 9 --verify --auto

# Encrypted archives
python main.py --input ./files --output ./archives --password "secret" --auto

# Split large archives
python main.py --input ./files --output ./archives --split-size 100M --auto

# Use config file
python main.py --config compress.yaml

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ -v --cov=main
```

## Architecture

The application consists of a single file (`main.py`, ~675 lines) with these main functions:

### Core Functions
- **`setup_logging()`** - Dual-stream logging (console + file) with verbose support
- **`check_tools()`** - Verifies 7z/zip/rar are in PATH, returns availability dict
- **`validate_args()`** - Validates CLI arguments (paths, numeric ranges, prefix characters)
- **`compress_batch()`** - Executes single 7z compression with error handling, returns success/failure and size
- **`verify_archive()`** - Tests archive integrity using 7z
- **`compress_in_batches()`** - Main orchestrator: scans input, batches files, manages ThreadPoolExecutor
- **`main()`** - Entry point: parses args, validates, runs compression, prints summary

### Utility Functions
- **`format_size()`** - Converts bytes to human-readable format (KB, MB, GB)
- **`parse_size()`** - Parses human-readable size strings (100M, 1G) to bytes
- **`load_config()`** - Loads YAML configuration file
- **`get_files_flat()`** - Lists files in directory (non-recursive)
- **`get_files_recursive()`** - Lists files recursively with pattern exclusion

**Control flow**: Parse args → Load config → Init logging → Validate args → Check 7z availability → Get files (with exclusions) → Preview batches → Confirm (unless auto/dry-run) → Submit to thread pool with progress bar → Verify archives (optional) → Export metadata → Print summary → Return exit code

## Key Technical Details

- **Dependencies**: Python stdlib only for core functionality (pathlib, argparse, subprocess, concurrent.futures, logging, json, fnmatch, re)
- **Optional dependencies**: `tqdm` (progress bar), `pyyaml` (config files)
- **External tools**: Requires 7z binary in PATH
- **Threading**: Uses ThreadPoolExecutor for I/O-bound parallel compression
- **Batch naming**: Output follows `{prefix}_{batch_num}.{ext}` pattern (1-indexed)
- **Input handling**: Files sorted alphabetically before batching
- **Error handling**: Captures subprocess output, validates inputs, proper exit codes
- **Type hints**: Full type annotations on all functions
- **Version**: Semantic versioning (__version__ = "2.0.0")

## CLI Parameters

### Basic Options
| Flag | Default | Description |
|------|---------|-------------|
| `--input` | Required | Source folder path |
| `--output` | Required | Archive destination path |
| `--batch` | 80 | Files per archive (must be >= 1) |
| `--prefix` | "archive" | Archive name prefix (no special chars) |
| `--ext` | "7z" | Format: 7z, zip, rar |

### Execution Control
| Flag | Default | Description |
|------|---------|-------------|
| `--auto` | False | Skip confirmation prompts |
| `--threads` | 1 | Parallel compression workers (must be >= 1) |
| `--dry-run` | False | Preview operations without executing |

### Compression Options
| Flag | Default | Description |
|------|---------|-------------|
| `--compression-level` | 5 | Compression level 0-9 (0=store, 9=ultra) |
| `--password` | None | Password for encrypted archives |
| `--split-size` | None | Split into volumes (e.g., 100M, 1G) |

### File Filtering
| Flag | Default | Description |
|------|---------|-------------|
| `--exclude` | [] | Glob pattern to exclude (repeatable) |
| `--recursive`, `-r` | False | Scan subdirectories recursively |

### Output Control
| Flag | Default | Description |
|------|---------|-------------|
| `--overwrite` | False | Overwrite existing archives |
| `--verify` | False | Verify archives after creation |
| `--metadata` | None | Export metadata to JSON file |

### Utility Options
| Flag | Default | Description |
|------|---------|-------------|
| `--check` | False | Check tool availability only |
| `--version` | False | Show version and exit |
| `--config` | None | Load settings from YAML file |
| `--logfile` | "compress_batches.log" | Log file path |
| `--verbose`, `-v` | False | Enable debug-level output |

## Exit Codes

- `0` - Success (all batches completed)
- `1` - Error (validation failed, 7z not found, or some batches failed)

## Configuration File

Create a `compress.yaml` file (see `compress.yaml.example`):

```yaml
input: ./files
output: ./archives
batch: 100
prefix: backup
compression_level: 7
threads: 4
exclude:
  - "*.tmp"
  - "*.log"
auto: true
recursive: false
verify: true
```

## Metadata Export

When using `--metadata output.json`, exports:

```json
{
  "created_at": "2024-01-01T12:00:00",
  "input_folder": "./files",
  "output_folder": "./archives",
  "total_files": 100,
  "total_input_size": 1048576,
  "total_output_size": 524288,
  "compression_ratio": 50.0,
  "batch_size": 50,
  "compression_level": 5,
  "archives": [
    {
      "batch_num": 1,
      "archive_name": "archive_1.7z",
      "file_count": 50,
      "input_size": 524288,
      "output_size": 262144,
      "files": ["file1.txt", "file2.txt", ...]
    }
  ]
}
```

## Project Structure

```
batch-compress/
├── main.py                    # Main application
├── requirements.txt           # Python dependencies
├── pytest.ini                 # Pytest configuration
├── compress.yaml.example      # Example config file
├── CLAUDE.md                  # This file
├── tests/
│   ├── __init__.py
│   └── test_main.py          # Unit tests
└── .github/
    └── workflows/
        └── ci.yml            # GitHub Actions CI
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=main --cov-report=html

# Type checking (optional)
pip install mypy
mypy main.py --ignore-missing-imports

# Linting (optional)
pip install ruff
ruff check main.py
```
