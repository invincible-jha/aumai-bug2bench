"""CLI tests for aumai-bug2bench."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from aumai_bug2bench.cli import cli


SAMPLE_MARKDOWN_BUG = """\
# Bug Report

## Title
AttributeError on empty input

## Description
Passing an empty string to the process() function causes an AttributeError.

## Steps to Reproduce
1. Import the module: `from mypackage import process`
2. Call `process('')` with an empty string
3. Observe the AttributeError traceback

## Expected Behavior
The function should return an empty result without raising an exception.

## Actual Behavior
AttributeError: 'NoneType' object has no attribute 'strip'

## Environment
- Python: 3.11
- OS: Linux
"""


def _extract_json(text: str) -> dict:
    start = text.index("{")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("No JSON object found")


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def bug_file(tmp_path: Path) -> Path:
    path = tmp_path / "bug.md"
    path.write_text(SAMPLE_MARKDOWN_BUG, encoding="utf-8")
    return path


@pytest.fixture()
def bug_dir(tmp_path: Path) -> Path:
    bugs_dir = tmp_path / "bugs"
    bugs_dir.mkdir()
    for i in range(3):
        bug_path = bugs_dir / f"bug_{i}.md"
        bug_path.write_text(
            f"# Bug {i}\n\n## Description\nBug number {i}.\n",
            encoding="utf-8",
        )
    return bugs_dir


class TestCLIGroup:
    def test_cli_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_cli_version(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0


class TestParseCommand:
    def test_parse_basic(self, runner: CliRunner, bug_file: Path) -> None:
        result = runner.invoke(cli, ["parse", "--input", str(bug_file)])
        assert result.exit_code == 0, result.output

    def test_parse_outputs_valid_json(self, runner: CliRunner, bug_file: Path) -> None:
        result = runner.invoke(cli, ["parse", "--input", str(bug_file)])
        data = _extract_json(result.output)
        assert "bug_id" in data
        assert "title" in data
        assert "steps_to_reproduce" in data

    def test_parse_title_present(self, runner: CliRunner, bug_file: Path) -> None:
        result = runner.invoke(cli, ["parse", "--input", str(bug_file)])
        data = _extract_json(result.output)
        assert "AttributeError" in data["title"]

    def test_parse_steps_extracted(self, runner: CliRunner, bug_file: Path) -> None:
        result = runner.invoke(cli, ["parse", "--input", str(bug_file)])
        data = _extract_json(result.output)
        assert len(data["steps_to_reproduce"]) >= 1

    def test_parse_writes_output_file(
        self, runner: CliRunner, bug_file: Path, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "bug.json"
        result = runner.invoke(
            cli, ["parse", "--input", str(bug_file), "--output", str(output_path)]
        )
        assert result.exit_code == 0
        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert "bug_id" in data

    def test_parse_missing_input_fails(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["parse", "--input", "/nonexistent/bug.md"])
        assert result.exit_code != 0


class TestConvertCommand:
    def test_convert_basic(
        self, runner: CliRunner, bug_file: Path, tmp_path: Path
    ) -> None:
        output_dir = str(tmp_path / "benchmarks")
        result = runner.invoke(
            cli, ["convert", "--input", str(bug_file), "--output", output_dir]
        )
        assert result.exit_code == 0, result.output

    def test_convert_creates_test_files(
        self, runner: CliRunner, bug_file: Path, tmp_path: Path
    ) -> None:
        output_dir = tmp_path / "benchmarks"
        runner.invoke(
            cli, ["convert", "--input", str(bug_file), "--output", str(output_dir)]
        )
        test_files = list(output_dir.glob("test_*.py"))
        assert len(test_files) >= 1

    def test_convert_reports_confidence(
        self, runner: CliRunner, bug_file: Path, tmp_path: Path
    ) -> None:
        output_dir = str(tmp_path / "benchmarks")
        result = runner.invoke(
            cli, ["convert", "--input", str(bug_file), "--output", output_dir]
        )
        assert "confidence" in result.output.lower() or "%" in result.output

    def test_convert_with_json_output(
        self, runner: CliRunner, bug_file: Path, tmp_path: Path
    ) -> None:
        output_dir = str(tmp_path / "benchmarks")
        json_path = tmp_path / "result.json"
        result = runner.invoke(
            cli,
            [
                "convert",
                "--input", str(bug_file),
                "--output", output_dir,
                "--json-output", str(json_path),
            ],
        )
        assert result.exit_code == 0
        assert json_path.exists()

    def test_convert_missing_input_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            cli,
            ["convert", "--input", "/nonexistent/bug.md", "--output", str(tmp_path)],
        )
        assert result.exit_code != 0


class TestBatchCommand:
    def test_batch_basic(
        self, runner: CliRunner, bug_dir: Path, tmp_path: Path
    ) -> None:
        output_dir = str(tmp_path / "benchmarks")
        result = runner.invoke(
            cli, ["batch", "--input-dir", str(bug_dir), "--output", output_dir]
        )
        assert result.exit_code == 0, result.output

    def test_batch_creates_multiple_test_files(
        self, runner: CliRunner, bug_dir: Path, tmp_path: Path
    ) -> None:
        output_dir = tmp_path / "benchmarks"
        runner.invoke(
            cli, ["batch", "--input-dir", str(bug_dir), "--output", str(output_dir)]
        )
        test_files = list(output_dir.glob("test_*.py"))
        assert len(test_files) == 3

    def test_batch_empty_dir_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        output_dir = str(tmp_path / "benchmarks")
        result = runner.invoke(
            cli, ["batch", "--input-dir", str(empty_dir), "--output", output_dir]
        )
        assert result.exit_code != 0

    def test_batch_reports_processed_count(
        self, runner: CliRunner, bug_dir: Path, tmp_path: Path
    ) -> None:
        output_dir = str(tmp_path / "benchmarks")
        result = runner.invoke(
            cli, ["batch", "--input-dir", str(bug_dir), "--output", output_dir]
        )
        assert "3" in result.output or "benchmark" in result.output.lower()
