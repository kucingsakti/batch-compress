#!/usr/bin/env python3
"""
Batch Compress - CLI utility for batch compressing files using 7z.

Usage:
    python main.py --input <folder> --output <folder> [options]
    python main.py --check
    python main.py --version
"""

import argparse
import fnmatch
import json
import logging
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

__version__ = "2.0.0"

# Optional tqdm import for progress bar
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# Optional yaml import for config file
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def setup_logging(logfile: str, verbose: bool = False) -> None:
    """
    Configure dual-stream logging to console and file.

    Args:
        logfile: Path to the log file
        verbose: If True, set log level to DEBUG; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logfile, encoding="utf-8")
        ]
    )


def check_tools() -> dict[str, Optional[str]]:
    """
    Check availability of compression tools in system PATH.

    Returns:
        Dictionary mapping tool names to their paths (None if not found)
    """
    tools = ["7z", "zip", "rar"]
    results = {}
    logging.info("=== Checking compression tools ===")
    for tool in tools:
        path = shutil.which(tool)
        results[tool] = path
        if path:
            logging.info(f"{tool} found at: {path}")
        else:
            logging.warning(f"{tool} NOT found on system.")
    return results


def format_size(size_bytes: Union[int, float]) -> str:
    """
    Format byte size to human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def parse_size(size_str: str) -> int:
    """
    Parse human-readable size string to bytes.

    Args:
        size_str: Size string (e.g., "100M", "1G", "500K")

    Returns:
        Size in bytes

    Raises:
        ValueError: If format is invalid
    """
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?)B?$', size_str.upper())
    if not match:
        raise ValueError(f"Invalid size format: {size_str}")

    value = float(match.group(1))
    unit = match.group(2)

    multipliers = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
    return int(value * multipliers.get(unit, 1))


def load_config(config_path: str) -> dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    if not YAML_AVAILABLE:
        logging.error("PyYAML not installed. Run: pip install pyyaml")
        sys.exit(1)

    with open(config_path, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """
    Validate command line arguments.

    Args:
        args: Parsed arguments
        parser: ArgumentParser instance for error reporting

    Raises:
        SystemExit: If validation fails
    """
    if args.check or args.version:
        return

    if not args.input or not args.output:
        parser.error("--input and --output are required unless using --check or --version")

    if args.batch < 1:
        parser.error("--batch must be at least 1")

    if args.threads < 1:
        parser.error("--threads must be at least 1")

    if args.compression_level < 0 or args.compression_level > 9:
        parser.error("--compression-level must be between 0 and 9")

    # Validate input folder exists
    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input folder does not exist: {args.input}")

    if not input_path.is_dir():
        parser.error(f"Input path is not a directory: {args.input}")

    # Sanitize prefix (remove potentially dangerous characters)
    invalid_chars = '<>:"/\\|?*'
    if any(char in args.prefix for char in invalid_chars):
        parser.error(f"--prefix contains invalid characters: {invalid_chars}")

    # Validate split size if provided
    if args.split_size:
        try:
            parse_size(args.split_size)
        except ValueError as e:
            parser.error(str(e))


def get_files_recursive(folder: Path, exclude_patterns: list[str]) -> list[Path]:
    """
    Get all files recursively from folder.

    Args:
        folder: Root folder to scan
        exclude_patterns: Glob patterns to exclude

    Returns:
        Sorted list of file paths
    """
    files = []
    for f in folder.rglob('*'):
        if f.is_file():
            # Check exclude patterns
            excluded = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(f.name, pattern) or fnmatch.fnmatch(str(f), pattern):
                    excluded = True
                    break
            if not excluded:
                files.append(f)
    return sorted(files)


def get_files_flat(folder: Path, exclude_patterns: list[str]) -> list[Path]:
    """
    Get all files from folder (non-recursive).

    Args:
        folder: Folder to scan
        exclude_patterns: Glob patterns to exclude

    Returns:
        Sorted list of file paths
    """
    files = []
    for f in folder.iterdir():
        if f.is_file():
            # Check exclude patterns
            excluded = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(f.name, pattern):
                    excluded = True
                    break
            if not excluded:
                files.append(f)
    return sorted(files)


def compress_batch(
    batch_files: list[Path],
    archive_name: Path,
    compression_level: int = 5,
    password: Optional[str] = None,
    split_size: Optional[str] = None
) -> tuple[bool, Optional[int]]:
    """
    Compress a batch of files into a single archive using 7z.

    Args:
        batch_files: List of file paths to compress
        archive_name: Output archive path
        compression_level: Compression level 0-9
        password: Optional password for encryption
        split_size: Optional split volume size (e.g., "100M")

    Returns:
        Tuple of (success: bool, archive_size: int or None)
    """
    cmd = ["7z", "a", f"-mx={compression_level}", str(archive_name)]

    # Add password if provided
    if password:
        cmd.extend([f"-p{password}", "-mhe=on"])  # -mhe encrypts headers too

    # Add split size if provided
    if split_size:
        cmd.append(f"-v{split_size}")

    cmd.extend([str(f) for f in batch_files])

    logging.info(f"Compressing {len(batch_files)} files into {archive_name.name}")
    logging.debug("Executing: " + " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False
        )

        if result.returncode == 0:
            logging.info(f"Successfully created {archive_name.name}")
            # Get archive size
            if archive_name.exists():
                size = archive_name.stat().st_size
                return (True, size)
            return (True, None)
        else:
            logging.error(f"Failed to create {archive_name.name}, return code {result.returncode}")
            if result.stderr:
                logging.error(f"7z stderr: {result.stderr.strip()}")
            return (False, None)

    except FileNotFoundError:
        logging.error("7z executable not found in PATH")
        return (False, None)
    except Exception as e:
        logging.error(f"Unexpected error compressing {archive_name.name}: {e}")
        return (False, None)


def verify_archive(archive_path: Path) -> bool:
    """
    Verify archive integrity using 7z.

    Args:
        archive_path: Path to archive file

    Returns:
        True if archive is valid, False otherwise
    """
    cmd = ["7z", "t", str(archive_path)]
    logging.info(f"Verifying {archive_path.name}...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
        if result.returncode == 0:
            logging.info(f"Verification passed: {archive_path.name}")
            return True
        else:
            logging.error(f"Verification failed: {archive_path.name}")
            if result.stderr:
                logging.error(f"7z stderr: {result.stderr.strip()}")
            return False
    except Exception as e:
        logging.error(f"Error verifying {archive_path.name}: {e}")
        return False


def compress_in_batches(
    input_folder: str,
    output_folder: str,
    batch_size: int = 80,
    output_prefix: str = "archive",
    extension: str = "7z",
    auto: bool = False,
    threads: int = 1,
    dry_run: bool = False,
    compression_level: int = 5,
    exclude_patterns: Optional[list[str]] = None,
    overwrite: bool = False,
    password: Optional[str] = None,
    split_size: Optional[str] = None,
    verify: bool = False,
    recursive: bool = False,
    metadata_file: Optional[str] = None
) -> tuple[int, int, int, int]:
    """
    Compress files from input folder into batched archives.

    Args:
        input_folder: Source folder containing files to compress
        output_folder: Destination folder for archives
        batch_size: Number of files per archive
        output_prefix: Prefix for archive filenames
        extension: Archive format (7z, zip, rar)
        auto: Skip confirmation prompts if True
        threads: Number of parallel compression workers
        dry_run: Preview operations without executing if True
        compression_level: Compression level 0-9
        exclude_patterns: List of glob patterns to exclude
        overwrite: Overwrite existing archives if True
        password: Optional password for encryption
        split_size: Optional split volume size
        verify: Verify archives after creation
        recursive: Scan subdirectories recursively
        metadata_file: Path to export metadata JSON

    Returns:
        Tuple of (successful_count, failed_count, total_input_size, total_output_size)
    """
    folder = Path(input_folder)
    exclude_patterns = exclude_patterns or []

    # Get files based on recursive mode
    if recursive:
        files = get_files_recursive(folder, exclude_patterns)
    else:
        files = get_files_flat(folder, exclude_patterns)

    if not files:
        logging.error(f"No files found in folder: {input_folder}")
        return (0, 0, 0, 0)

    # Calculate total input size
    total_input_size = sum(f.stat().st_size for f in files)

    total_batches = (len(files) + batch_size - 1) // batch_size
    logging.info(f"Found {len(files)} files ({format_size(total_input_size)}), will create {total_batches} archive(s)")

    if exclude_patterns:
        logging.info(f"Excluding patterns: {', '.join(exclude_patterns)}")

    if dry_run:
        logging.info("=== DRY RUN MODE - No files will be created ===")

    Path(output_folder).mkdir(parents=True, exist_ok=True)

    # Prepare all batches first
    batches: list[tuple[int, list[Path], Path, int]] = []
    metadata: dict[str, Any] = {
        "created_at": datetime.now().isoformat(),
        "input_folder": str(input_folder),
        "output_folder": str(output_folder),
        "total_files": len(files),
        "total_input_size": total_input_size,
        "batch_size": batch_size,
        "compression_level": compression_level,
        "archives": []
    }

    for i in range(0, len(files), batch_size):
        batch_num = i // batch_size + 1
        batch_files = files[i:i + batch_size]
        archive_name = Path(output_folder) / f"{output_prefix}_{batch_num}.{extension}"

        # Check if archive exists
        if archive_name.exists() and not overwrite:
            logging.warning(f"Skipping {archive_name.name} (already exists, use --overwrite to replace)")
            continue

        batch_input_size = sum(f.stat().st_size for f in batch_files)
        batches.append((batch_num, batch_files, archive_name, batch_input_size))

    if not batches:
        logging.info("No batches to process (all archives exist)")
        return (0, 0, total_input_size, 0)

    # Preview all batches
    for batch_num, batch_files, archive_name, batch_size_bytes in batches:
        logging.info(f"Batch {batch_num}/{total_batches}: {len(batch_files)} files ({format_size(batch_size_bytes)}) -> {archive_name.name}")
        for f in batch_files:
            logging.debug(f"  - {f.name}")

    if dry_run:
        logging.info("=== DRY RUN COMPLETE - No changes made ===")
        return (len(batches), 0, total_input_size, 0)

    # Confirmation prompt (outside of ThreadPool)
    if not auto:
        confirm = input(f"\nProceed with compression of {len(batches)} batch(es)? (y/n): ").strip().lower()
        if confirm != "y":
            logging.warning("Operation cancelled by user.")
            return (0, 0, total_input_size, 0)

    # Execute compression
    success_count = 0
    fail_count = 0
    total_output_size = 0

    # Use tqdm if available
    if TQDM_AVAILABLE and not dry_run:
        pbar = tqdm(total=len(batches), desc="Compressing", unit="batch")
    else:
        pbar = None

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {}
        for batch_num, batch_files, archive_name, batch_input_size in batches:
            future = executor.submit(
                compress_batch,
                batch_files,
                archive_name,
                compression_level,
                password,
                split_size
            )
            futures[future] = (batch_num, batch_files, archive_name, batch_input_size)

        for future in as_completed(futures):
            batch_num, batch_files, archive_name, batch_input_size = futures[future]
            try:
                success, archive_size = future.result()
                if success:
                    success_count += 1
                    if archive_size:
                        total_output_size += archive_size

                    # Verify if requested
                    if verify and not verify_archive(archive_name):
                        logging.error(f"Verification failed for {archive_name.name}")
                        success_count -= 1
                        fail_count += 1
                    else:
                        # Add to metadata
                        metadata["archives"].append({
                            "batch_num": batch_num,
                            "archive_name": archive_name.name,
                            "file_count": len(batch_files),
                            "input_size": batch_input_size,
                            "output_size": archive_size,
                            "files": [str(f.name) for f in batch_files]
                        })
                else:
                    fail_count += 1
            except Exception as e:
                logging.error(f"Batch {batch_num} raised exception: {e}")
                fail_count += 1

            if pbar:
                pbar.update(1)

    if pbar:
        pbar.close()

    # Export metadata if requested
    if metadata_file and success_count > 0:
        metadata["total_output_size"] = total_output_size
        metadata["compression_ratio"] = (1 - total_output_size / total_input_size) * 100 if total_input_size > 0 else 0

        with open(metadata_file, 'w', encoding='utf-8') as mf:
            json.dump(metadata, mf, indent=2, ensure_ascii=False)
        logging.info(f"Metadata exported to {metadata_file}")

    return (success_count, fail_count, total_input_size, total_output_size)


def main() -> int:
    """
    Main entry point for the batch compression utility.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Compress files in batches using 7z",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --check
  %(prog)s --version
  %(prog)s --input ./files --output ./archives
  %(prog)s --input ./files --output ./archives --batch 50 --auto --threads 4
  %(prog)s --input ./files --output ./archives --dry-run
  %(prog)s --input ./files --output ./archives --exclude "*.tmp" --exclude "*.log"
  %(prog)s --input ./files --output ./archives --compression-level 9
  %(prog)s --input ./files --output ./archives --recursive --metadata output.json
  %(prog)s --config compress.yaml
        """
    )

    # Basic arguments
    parser.add_argument("--input", help="Path to input folder")
    parser.add_argument("--output", help="Path to output folder")
    parser.add_argument("--batch", type=int, default=80,
                        help="Number of files per batch (default: 80)")
    parser.add_argument("--prefix", default="archive",
                        help="Prefix for archive file names (default: archive)")
    parser.add_argument("--ext", choices=["7z", "zip", "rar"], default="7z",
                        help="Archive extension (default: 7z)")

    # Execution control
    parser.add_argument("--auto", action="store_true",
                        help="Run automatically without confirmation")
    parser.add_argument("--threads", type=int, default=1,
                        help="Number of parallel threads (default: 1)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview operations without executing")

    # Compression options
    parser.add_argument("--compression-level", type=int, default=5,
                        help="Compression level 0-9 (default: 5)")
    parser.add_argument("--password", help="Password for encrypted archives")
    parser.add_argument("--split-size",
                        help="Split archive into volumes (e.g., 100M, 1G)")

    # File filtering
    parser.add_argument("--exclude", action="append", default=[],
                        help="Glob pattern to exclude (can be used multiple times)")
    parser.add_argument("--recursive", "-r", action="store_true",
                        help="Scan subdirectories recursively")

    # Output control
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing archives")
    parser.add_argument("--verify", action="store_true",
                        help="Verify archives after creation")
    parser.add_argument("--metadata",
                        help="Export metadata to JSON file")

    # Utility options
    parser.add_argument("--check", action="store_true",
                        help="Check if 7z, zip, rar tools are available")
    parser.add_argument("--logfile", default="compress_batches.log",
                        help="Log file path (default: compress_batches.log)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose/debug output")
    parser.add_argument("--version", action="store_true",
                        help="Show version and exit")
    parser.add_argument("--config",
                        help="Load settings from YAML config file")

    args = parser.parse_args()

    # Handle version flag early
    if args.version:
        print(f"batch-compress version {__version__}")
        return 0

    # Load config file if provided
    if args.config:
        config = load_config(args.config)
        # Apply config values as defaults (CLI args override)
        for key, value in config.items():
            arg_key = key.replace('-', '_')
            if hasattr(args, arg_key) and getattr(args, arg_key) in [None, False, [], 80, 5, 1, "archive", "7z", "compress_batches.log"]:
                setattr(args, arg_key, value)

    setup_logging(args.logfile, args.verbose)

    # Log version
    logging.debug(f"batch-compress version {__version__}")

    # Validate arguments
    validate_args(args, parser)

    if args.check:
        check_tools()
        return 0

    # Check 7z availability before starting
    if not shutil.which("7z"):
        logging.error("7z not found in PATH. Please install 7-Zip first.")
        logging.error("Download from: https://www.7-zip.org/")
        return 1

    # Check optional dependencies
    if not TQDM_AVAILABLE:
        logging.debug("tqdm not installed. Progress bar disabled. Install with: pip install tqdm")

    # Run compression
    success, failed, input_size, output_size = compress_in_batches(
        args.input,
        args.output,
        args.batch,
        args.prefix,
        args.ext,
        args.auto,
        args.threads,
        args.dry_run,
        args.compression_level,
        args.exclude,
        args.overwrite,
        args.password,
        args.split_size,
        args.verify,
        args.recursive,
        args.metadata
    )

    # Print summary
    total = success + failed
    if total > 0:
        logging.info("=" * 50)
        logging.info("SUMMARY")
        logging.info("=" * 50)
        logging.info(f"Total batches:    {total}")
        logging.info(f"Successful:       {success}")
        logging.info(f"Failed:           {failed}")
        logging.info(f"Input size:       {format_size(input_size)}")

        if output_size > 0:
            logging.info(f"Output size:      {format_size(output_size)}")
            ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
            logging.info(f"Compression:      {ratio:.1f}% reduced")

        if failed > 0:
            logging.warning("Some batches failed. Check log for details.")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
