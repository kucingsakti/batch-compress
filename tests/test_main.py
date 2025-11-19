"""
Unit tests for batch-compress main module.

Run with: pytest tests/ -v
"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import (
    format_size,
    parse_size,
    get_files_flat,
    get_files_recursive,
    compress_batch,
    verify_archive,
    compress_in_batches,
    validate_args,
    check_tools,
    __version__
)


class TestFormatSize:
    """Tests for format_size function."""

    def test_bytes(self):
        assert format_size(500) == "500.00 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.00 KB"
        assert format_size(1536) == "1.50 KB"

    def test_megabytes(self):
        assert format_size(1024 * 1024) == "1.00 MB"
        assert format_size(1024 * 1024 * 2.5) == "2.50 MB"

    def test_gigabytes(self):
        assert format_size(1024 ** 3) == "1.00 GB"

    def test_terabytes(self):
        assert format_size(1024 ** 4) == "1.00 TB"

    def test_zero(self):
        assert format_size(0) == "0.00 B"


class TestParseSize:
    """Tests for parse_size function."""

    def test_plain_bytes(self):
        assert parse_size("100") == 100
        assert parse_size("100B") == 100

    def test_kilobytes(self):
        assert parse_size("1K") == 1024
        assert parse_size("1KB") == 1024
        assert parse_size("2.5K") == 2560

    def test_megabytes(self):
        assert parse_size("1M") == 1024 ** 2
        assert parse_size("100M") == 100 * 1024 ** 2

    def test_gigabytes(self):
        assert parse_size("1G") == 1024 ** 3
        assert parse_size("2G") == 2 * 1024 ** 3

    def test_terabytes(self):
        assert parse_size("1T") == 1024 ** 4

    def test_case_insensitive(self):
        assert parse_size("100m") == parse_size("100M")
        assert parse_size("1g") == parse_size("1G")

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_size("invalid")

        with pytest.raises(ValueError):
            parse_size("100X")


class TestGetFilesFlat:
    """Tests for get_files_flat function."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory with test files."""
        tmpdir = tempfile.mkdtemp()
        # Create test files
        (Path(tmpdir) / "file1.txt").touch()
        (Path(tmpdir) / "file2.txt").touch()
        (Path(tmpdir) / "file3.log").touch()
        (Path(tmpdir) / "subdir").mkdir()
        (Path(tmpdir) / "subdir" / "nested.txt").touch()
        yield tmpdir
        shutil.rmtree(tmpdir)

    def test_get_all_files(self, temp_dir):
        files = get_files_flat(Path(temp_dir), [])
        assert len(files) == 3  # Only top-level files

    def test_exclude_pattern(self, temp_dir):
        files = get_files_flat(Path(temp_dir), ["*.log"])
        assert len(files) == 2
        assert all(f.suffix != ".log" for f in files)

    def test_multiple_exclude_patterns(self, temp_dir):
        files = get_files_flat(Path(temp_dir), ["*.log", "file1.*"])
        assert len(files) == 1

    def test_sorted_output(self, temp_dir):
        files = get_files_flat(Path(temp_dir), [])
        names = [f.name for f in files]
        assert names == sorted(names)


class TestGetFilesRecursive:
    """Tests for get_files_recursive function."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory with nested files."""
        tmpdir = tempfile.mkdtemp()
        # Create nested structure
        (Path(tmpdir) / "file1.txt").touch()
        (Path(tmpdir) / "subdir").mkdir()
        (Path(tmpdir) / "subdir" / "file2.txt").touch()
        (Path(tmpdir) / "subdir" / "deep").mkdir()
        (Path(tmpdir) / "subdir" / "deep" / "file3.txt").touch()
        yield tmpdir
        shutil.rmtree(tmpdir)

    def test_get_all_recursive(self, temp_dir):
        files = get_files_recursive(Path(temp_dir), [])
        assert len(files) == 3

    def test_exclude_in_subdirs(self, temp_dir):
        # Add a log file in subdir
        (Path(temp_dir) / "subdir" / "test.log").touch()
        files = get_files_recursive(Path(temp_dir), ["*.log"])
        assert len(files) == 3
        assert all(f.suffix != ".log" for f in files)


class TestCompressBatch:
    """Tests for compress_batch function."""

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for compression."""
        tmpdir = tempfile.mkdtemp()
        files = []
        for i in range(3):
            f = Path(tmpdir) / f"test{i}.txt"
            f.write_text(f"Content {i}" * 100)
            files.append(f)
        yield tmpdir, files
        shutil.rmtree(tmpdir)

    @patch('main.subprocess.run')
    def test_successful_compression(self, mock_run, temp_files):
        tmpdir, files = temp_files
        archive = Path(tmpdir) / "test.7z"

        # Mock successful compression
        mock_run.return_value = MagicMock(returncode=0)

        # Create a dummy archive file for size check
        archive.write_bytes(b"dummy")

        success, size = compress_batch(files, archive)
        assert success is True
        assert size is not None

    @patch('main.subprocess.run')
    def test_failed_compression(self, mock_run, temp_files):
        tmpdir, files = temp_files
        archive = Path(tmpdir) / "test.7z"

        mock_run.return_value = MagicMock(returncode=1, stderr="Error")

        success, size = compress_batch(files, archive)
        assert success is False

    @patch('main.subprocess.run')
    def test_compression_with_level(self, mock_run, temp_files):
        tmpdir, files = temp_files
        archive = Path(tmpdir) / "test.7z"

        mock_run.return_value = MagicMock(returncode=0)
        archive.write_bytes(b"dummy")

        compress_batch(files, archive, compression_level=9)

        # Check that compression level was passed
        call_args = mock_run.call_args[0][0]
        assert "-mx=9" in call_args

    @patch('main.subprocess.run')
    def test_compression_with_password(self, mock_run, temp_files):
        tmpdir, files = temp_files
        archive = Path(tmpdir) / "test.7z"

        mock_run.return_value = MagicMock(returncode=0)
        archive.write_bytes(b"dummy")

        compress_batch(files, archive, password="secret")

        call_args = mock_run.call_args[0][0]
        assert "-psecret" in call_args
        assert "-mhe=on" in call_args


class TestVerifyArchive:
    """Tests for verify_archive function."""

    @patch('main.subprocess.run')
    def test_valid_archive(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = verify_archive(Path("test.7z"))
        assert result is True

    @patch('main.subprocess.run')
    def test_invalid_archive(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="CRC Error")

        result = verify_archive(Path("test.7z"))
        assert result is False


class TestCompressInBatches:
    """Integration tests for compress_in_batches function."""

    @pytest.fixture
    def temp_setup(self):
        """Create input and output directories."""
        tmpdir = tempfile.mkdtemp()
        input_dir = Path(tmpdir) / "input"
        output_dir = Path(tmpdir) / "output"
        input_dir.mkdir()

        # Create test files
        for i in range(10):
            (input_dir / f"file{i:02d}.txt").write_text(f"Content {i}")

        yield str(input_dir), str(output_dir)
        shutil.rmtree(tmpdir)

    def test_dry_run(self, temp_setup):
        input_dir, output_dir = temp_setup

        success, failed, in_size, out_size = compress_in_batches(
            input_dir, output_dir,
            batch_size=5,
            auto=True,
            dry_run=True
        )

        assert success == 2  # 10 files / 5 per batch
        assert failed == 0
        assert in_size > 0
        # No archives created in dry run
        assert not Path(output_dir).exists() or len(list(Path(output_dir).glob("*.7z"))) == 0

    def test_empty_folder(self, temp_setup):
        input_dir, output_dir = temp_setup

        # Create empty folder
        empty_dir = Path(input_dir).parent / "empty"
        empty_dir.mkdir()

        success, failed, in_size, out_size = compress_in_batches(
            str(empty_dir), output_dir,
            auto=True
        )

        assert success == 0
        assert failed == 0

    def test_exclude_patterns(self, temp_setup):
        input_dir, output_dir = temp_setup

        # Add files to exclude
        (Path(input_dir) / "exclude.tmp").write_text("temp")
        (Path(input_dir) / "exclude.log").write_text("log")

        success, failed, in_size, out_size = compress_in_batches(
            input_dir, output_dir,
            exclude_patterns=["*.tmp", "*.log"],
            auto=True,
            dry_run=True
        )

        # Should still be 10 files (excluding .tmp and .log)
        assert success == 2


class TestValidateArgs:
    """Tests for validate_args function."""

    @pytest.fixture
    def parser(self):
        """Create argument parser."""
        import argparse
        return argparse.ArgumentParser()

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir)

    def test_valid_args(self, parser, temp_dir):
        args = MagicMock()
        args.check = False
        args.version = False
        args.input = temp_dir
        args.output = "/tmp/output"
        args.batch = 80
        args.threads = 4
        args.compression_level = 5
        args.prefix = "archive"
        args.split_size = None

        # Should not raise
        validate_args(args, parser)

    def test_invalid_batch(self, parser, temp_dir):
        args = MagicMock()
        args.check = False
        args.version = False
        args.input = temp_dir
        args.output = "/tmp/output"
        args.batch = 0
        args.threads = 1
        args.compression_level = 5
        args.prefix = "archive"
        args.split_size = None

        with pytest.raises(SystemExit):
            validate_args(args, parser)

    def test_invalid_threads(self, parser, temp_dir):
        args = MagicMock()
        args.check = False
        args.version = False
        args.input = temp_dir
        args.output = "/tmp/output"
        args.batch = 80
        args.threads = -1
        args.compression_level = 5
        args.prefix = "archive"
        args.split_size = None

        with pytest.raises(SystemExit):
            validate_args(args, parser)

    def test_invalid_compression_level(self, parser, temp_dir):
        args = MagicMock()
        args.check = False
        args.version = False
        args.input = temp_dir
        args.output = "/tmp/output"
        args.batch = 80
        args.threads = 1
        args.compression_level = 10
        args.prefix = "archive"
        args.split_size = None

        with pytest.raises(SystemExit):
            validate_args(args, parser)

    def test_invalid_prefix_characters(self, parser, temp_dir):
        args = MagicMock()
        args.check = False
        args.version = False
        args.input = temp_dir
        args.output = "/tmp/output"
        args.batch = 80
        args.threads = 1
        args.compression_level = 5
        args.prefix = "test<invalid>"
        args.split_size = None

        with pytest.raises(SystemExit):
            validate_args(args, parser)


class TestCheckTools:
    """Tests for check_tools function."""

    @patch('main.shutil.which')
    def test_all_tools_found(self, mock_which):
        mock_which.return_value = "/usr/bin/7z"

        results = check_tools()

        assert "7z" in results
        assert "zip" in results
        assert "rar" in results

    @patch('main.shutil.which')
    def test_some_tools_missing(self, mock_which):
        def which_side_effect(tool):
            return "/usr/bin/7z" if tool == "7z" else None

        mock_which.side_effect = which_side_effect

        results = check_tools()

        assert results["7z"] == "/usr/bin/7z"
        assert results["zip"] is None
        assert results["rar"] is None


class TestVersion:
    """Tests for version."""

    def test_version_exists(self):
        assert __version__ is not None
        assert len(__version__) > 0

    def test_version_format(self):
        # Check semantic versioning format
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)


class TestMetadataExport:
    """Tests for metadata JSON export."""

    @pytest.fixture
    def temp_setup(self):
        """Create input and output directories."""
        tmpdir = tempfile.mkdtemp()
        input_dir = Path(tmpdir) / "input"
        output_dir = Path(tmpdir) / "output"
        input_dir.mkdir()

        for i in range(5):
            (input_dir / f"file{i}.txt").write_text(f"Content {i}")

        yield tmpdir, str(input_dir), str(output_dir)
        shutil.rmtree(tmpdir)

    @patch('main.subprocess.run')
    def test_metadata_export(self, mock_run, temp_setup):
        tmpdir, input_dir, output_dir = temp_setup
        metadata_file = Path(tmpdir) / "metadata.json"

        # Mock successful compression
        mock_run.return_value = MagicMock(returncode=0)

        # Create dummy archive for size check
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        archive = Path(output_dir) / "archive_1.7z"
        archive.write_bytes(b"dummy" * 100)

        compress_in_batches(
            input_dir, output_dir,
            batch_size=5,
            auto=True,
            metadata_file=str(metadata_file)
        )

        # Check metadata file
        assert metadata_file.exists()

        with open(metadata_file) as f:
            metadata = json.load(f)

        assert "created_at" in metadata
        assert "total_files" in metadata
        assert metadata["total_files"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
