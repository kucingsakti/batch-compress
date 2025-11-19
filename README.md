# Batch Compress

A powerful Python CLI utility for batch compressing files into archives using 7z.

[![CI](https://github.com/YOUR_USERNAME/batch-compress/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/batch-compress/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Batch compression** - Split files into configurable batch sizes
- **Multiple formats** - Support for 7z, zip, and rar archives
- **Parallel processing** - Multi-threaded compression for faster execution
- **Compression levels** - Adjustable compression (0-9) for speed vs size tradeoff
- **File filtering** - Exclude patterns and recursive directory scanning
- **Encryption** - Password-protected archives with header encryption
- **Split volumes** - Create multi-part archives for large backups
- **Verification** - Automatic integrity check after compression
- **Progress bar** - Visual progress tracking (with tqdm)
- **Metadata export** - JSON report with compression statistics
- **Config files** - YAML configuration for reusable settings
- **Dry-run mode** - Preview operations before execution

## Requirements

- Python 3.9+
- 7-Zip installed and available in PATH

### Installing 7-Zip

- **Windows**: Download from [7-zip.org](https://www.7-zip.org/)
- **Linux**: `sudo apt install p7zip-full`
- **macOS**: `brew install p7zip`

## Installation

1. Clone or download this repository:
```bash
git clone https://github.com/YOUR_USERNAME/batch-compress.git
cd batch-compress
```

2. Install optional dependencies (recommended):
```bash
pip install -r requirements.txt
```

3. Verify installation:
```bash
python main.py --check
python main.py --version
```

## Quick Start

### Basic Usage

```bash
python main.py --input <input_folder> --output <output_folder>
```

This will:
- Read all files from input folder
- Split into batches of 80 files (default)
- Show preview and ask for confirmation
- Create archives named `archive_1.7z`, `archive_2.7z`, etc.

### Common Examples

**Auto mode with custom batch size:**
```bash
python main.py --input ./documents --output ./archives --batch 100 --auto
```

**High compression with verification:**
```bash
python main.py --input ./files --output ./backup --compression-level 9 --verify --auto
```

**Exclude temporary files:**
```bash
python main.py --input ./project --output ./archives --exclude "*.tmp" --exclude "*.log" --auto
```

**Encrypted backup:**
```bash
python main.py --input ./sensitive --output ./secure --password "MySecret123" --auto
```

**Split into 100MB volumes:**
```bash
python main.py --input ./large-files --output ./backup --split-size 100M --auto
```

**Recursive scan with metadata export:**
```bash
python main.py --input ./project --output ./backup --recursive --metadata report.json --auto
```

**Using config file:**
```bash
python main.py --config compress.yaml
```

**Parallel compression with progress bar:**
```bash
python main.py --input ./files --output ./archives --threads 4 --auto
```

**Dry run to preview:**
```bash
python main.py --input ./files --output ./archives --dry-run
```

## CLI Options

### Basic Options

| Option | Default | Description |
|--------|---------|-------------|
| `--input` | Required | Path to folder containing files to compress |
| `--output` | Required | Path to folder for output archives |
| `--batch` | 80 | Number of files per archive |
| `--prefix` | "archive" | Prefix for archive filenames |
| `--ext` | "7z" | Archive format: `7z`, `zip`, or `rar` |

### Execution Control

| Option | Default | Description |
|--------|---------|-------------|
| `--auto` | False | Skip confirmation prompts |
| `--threads` | 1 | Number of parallel compression threads |
| `--dry-run` | False | Preview operations without executing |

### Compression Options

| Option | Default | Description |
|--------|---------|-------------|
| `--compression-level` | 5 | Compression level 0-9 (0=store, 9=ultra) |
| `--password` | None | Password for encrypted archives |
| `--split-size` | None | Split into volumes (e.g., `100M`, `1G`) |

### File Filtering

| Option | Default | Description |
|--------|---------|-------------|
| `--exclude` | [] | Glob pattern to exclude (repeatable) |
| `--recursive`, `-r` | False | Scan subdirectories recursively |

### Output Control

| Option | Default | Description |
|--------|---------|-------------|
| `--overwrite` | False | Overwrite existing archives |
| `--verify` | False | Verify archives after creation |
| `--metadata` | None | Export metadata to JSON file |

### Utility Options

| Option | Default | Description |
|--------|---------|-------------|
| `--check` | False | Check if compression tools are available |
| `--version` | False | Show version and exit |
| `--config` | None | Load settings from YAML config file |
| `--logfile` | "compress_batches.log" | Path to log file |
| `--verbose`, `-v` | False | Enable debug-level output |

## Configuration File

Create a `compress.yaml` file for reusable settings:

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
  - "node_modules/*"
auto: true
recursive: false
verify: true
```

See `compress.yaml.example` for a complete template.

## Output

### Archive Naming

Archives are created with the pattern: `{prefix}_{batch_number}.{extension}`

```
archive_1.7z
archive_2.7z
archive_3.7z
...
```

### Summary Report

After compression, a summary is displayed:

```
==================================================
SUMMARY
==================================================
Total batches:    10
Successful:       10
Failed:           0
Input size:       125.50 MB
Output size:      45.20 MB
Compression:      64.0% reduced
```

### Metadata Export

When using `--metadata output.json`, a detailed report is generated:

```json
{
  "created_at": "2024-01-01T12:00:00",
  "input_folder": "./files",
  "output_folder": "./archives",
  "total_files": 100,
  "total_input_size": 131596288,
  "total_output_size": 47414784,
  "compression_ratio": 64.0,
  "batch_size": 50,
  "compression_level": 5,
  "archives": [
    {
      "batch_num": 1,
      "archive_name": "archive_1.7z",
      "file_count": 50,
      "input_size": 65798144,
      "output_size": 23707392,
      "files": ["file1.txt", "file2.txt", "..."]
    }
  ]
}
```

## Logging

All operations are logged to both console and a log file:

- Timestamp
- Log level (INFO, WARNING, ERROR, DEBUG)
- Operation details
- Success/failure status for each batch
- Compression statistics

Use `--verbose` for detailed debug output.

## Exit Codes

- `0` - Success (all batches completed)
- `1` - Error (validation failed, 7z not found, or some batches failed)

## Development

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=main --cov-report=html
```

### Code Quality

```bash
# Type checking
pip install mypy
mypy main.py --ignore-missing-imports

# Linting
pip install ruff
ruff check main.py
```

## Project Structure

```
batch-compress/
├── main.py                    # Main application (~675 lines)
├── requirements.txt           # Python dependencies
├── pytest.ini                 # Pytest configuration
├── compress.yaml.example      # Example config file
├── README.md                  # This file
├── CLAUDE.md                  # Claude Code guidance
├── tests/
│   ├── __init__.py
│   └── test_main.py          # Unit tests
└── .github/
    └── workflows/
        └── ci.yml            # GitHub Actions CI
```

## Changelog

### v2.0.0
- Added compression level control (0-9)
- Added file exclusion patterns
- Added password encryption support
- Added split volume support
- Added archive verification
- Added recursive directory scanning
- Added metadata JSON export
- Added YAML config file support
- Added progress bar (tqdm)
- Added dry-run mode
- Added file size reporting with compression ratio
- Improved error handling and validation
- Added comprehensive unit tests
- Added GitHub Actions CI pipeline

### v1.0.0
- Initial release
- Basic batch compression
- Multi-threading support
- Multiple archive formats

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Submit a pull request

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/YOUR_USERNAME/batch-compress/issues) page.
