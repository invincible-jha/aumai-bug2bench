"""Comprehensive tests for aumai_bug2bench core logic."""

from __future__ import annotations

import pytest

from aumai_bug2bench.core import BenchmarkGenerator, BenchmarkSuite, BugParser
from aumai_bug2bench.models import BenchmarkCase, BugReport, ConversionResult


SAMPLE_MARKDOWN_BUG = """\
# Bug Report

## Title
AttributeError on empty input

## Description
Passing an empty string to the process() function causes an AttributeError.
This happens because the return value is None when the input is empty.

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
- Package version: 1.2.3
"""

SAMPLE_INLINE_BUG = """\
Title: KeyError when accessing missing config key
Expected: Should return default value
Actual: KeyError raised
"""

SAMPLE_PLAIN_BUG = """\
NullPointerException in DataProcessor
The data processor throws a NullPointerException when the input list is empty.
"""


# ---------------------------------------------------------------------------
# BugParser.parse tests
# ---------------------------------------------------------------------------


class TestBugParserParse:
    def test_parse_returns_bug_report(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_MARKDOWN_BUG)
        assert isinstance(bug, BugReport)

    def test_parse_extracts_title_from_heading(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_MARKDOWN_BUG)
        assert "AttributeError" in bug.title

    def test_parse_extracts_description(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_MARKDOWN_BUG)
        assert bug.description != ""

    def test_parse_extracts_steps_to_reproduce(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_MARKDOWN_BUG)
        assert len(bug.steps_to_reproduce) >= 2

    def test_parse_extracts_expected_behavior(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_MARKDOWN_BUG)
        assert "empty result" in bug.expected_behavior.lower()

    def test_parse_extracts_actual_behavior(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_MARKDOWN_BUG)
        assert "AttributeError" in bug.actual_behavior

    def test_parse_extracts_environment(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_MARKDOWN_BUG)
        assert "python" in bug.environment or "os" in bug.environment

    def test_parse_generates_bug_id(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_MARKDOWN_BUG)
        assert bug.bug_id != ""
        assert len(bug.bug_id) >= 8

    def test_parse_unique_ids(self) -> None:
        parser = BugParser()
        bug1 = parser.parse(SAMPLE_MARKDOWN_BUG)
        bug2 = parser.parse(SAMPLE_MARKDOWN_BUG)
        assert bug1.bug_id != bug2.bug_id

    def test_parse_inline_labels(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_INLINE_BUG)
        assert "KeyError" in bug.title
        assert bug.expected_behavior != "" or bug.actual_behavior != ""

    def test_parse_plain_text_falls_back_to_title(self) -> None:
        parser = BugParser()
        bug = parser.parse(SAMPLE_PLAIN_BUG)
        assert bug.title != ""

    def test_parse_empty_text_does_not_raise(self) -> None:
        parser = BugParser()
        bug = parser.parse("")
        assert isinstance(bug, BugReport)

    def test_parse_first_line_is_title_when_no_headings(self) -> None:
        text = "First line is the title\nSecond line is content."
        parser = BugParser()
        bug = parser.parse(text)
        assert bug.title == "First line is the title"

    def test_parse_unordered_list_steps(self) -> None:
        text = "## Steps to Reproduce\n- Step one\n- Step two\n- Step three\n"
        parser = BugParser()
        bug = parser.parse(text)
        assert len(bug.steps_to_reproduce) == 3


# ---------------------------------------------------------------------------
# BugParser.parse_github_issue tests
# ---------------------------------------------------------------------------


class TestBugParserParseGithubIssue:
    def test_parse_github_issue_returns_bug_report(self) -> None:
        parser = BugParser()
        issue = {"number": 42, "title": "Bug: crash on startup", "body": "It crashes."}
        bug = parser.parse_github_issue(issue)
        assert isinstance(bug, BugReport)

    def test_parse_github_issue_uses_number_as_id(self) -> None:
        parser = BugParser()
        issue = {"number": 42, "title": "Bug title", "body": ""}
        bug = parser.parse_github_issue(issue)
        assert bug.bug_id == "gh-42"

    def test_parse_github_issue_title_from_title_field(self) -> None:
        parser = BugParser()
        issue = {"number": 1, "title": "Specific title", "body": "body content"}
        bug = parser.parse_github_issue(issue)
        assert bug.title == "Specific title"

    def test_parse_github_issue_parses_body_for_steps(self) -> None:
        parser = BugParser()
        body = "## Steps to Reproduce\n1. Do this\n2. Do that\n"
        issue = {"number": 1, "title": "Title", "body": body}
        bug = parser.parse_github_issue(issue)
        assert len(bug.steps_to_reproduce) >= 1

    def test_parse_github_issue_uses_id_when_no_number(self) -> None:
        parser = BugParser()
        issue = {"id": 99, "title": "Title", "body": ""}
        bug = parser.parse_github_issue(issue)
        assert bug.bug_id == "gh-99"


# ---------------------------------------------------------------------------
# BenchmarkGenerator.convert tests
# ---------------------------------------------------------------------------


class TestBenchmarkGeneratorConvert:
    def test_convert_returns_conversion_result(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        assert isinstance(result, ConversionResult)

    def test_convert_confidence_full_report(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        assert result.confidence == 1.0

    def test_convert_confidence_minimal_report(self, minimal_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(minimal_bug_report)
        # No steps, expected, actual, description → 0.0
        assert result.confidence == 0.0

    def test_convert_confidence_partial_report(self) -> None:
        bug = BugReport(
            bug_id="BUG-003",
            title="Partial bug",
            steps_to_reproduce=["Step 1"],
            expected_behavior="Should work",
        )
        generator = BenchmarkGenerator()
        result = generator.convert(bug)
        assert result.confidence == 0.5  # steps + expected = 0.25 + 0.25

    def test_convert_benchmark_has_test_code(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        assert "def test_" in result.benchmark.test_code

    def test_convert_test_name_from_title(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        # Title: "AttributeError on empty input" → test_attributeerror_on_empty_input
        assert "attributeerror" in result.benchmark.test_code.lower()

    def test_convert_steps_in_test_code(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        assert "process" in result.benchmark.test_code

    def test_convert_notes_missing_expected(self) -> None:
        bug = BugReport(
            bug_id="BUG-004",
            title="No expected behavior",
            steps_to_reproduce=["Step 1"],
        )
        generator = BenchmarkGenerator()
        result = generator.convert(bug)
        assert any("expected" in note.lower() for note in result.notes)

    def test_convert_notes_missing_steps(self) -> None:
        bug = BugReport(bug_id="BUG-005", title="No steps")
        generator = BenchmarkGenerator()
        result = generator.convert(bug)
        assert any("steps" in note.lower() or "reproduce" in note.lower() for note in result.notes)

    def test_convert_benchmark_has_regression_tag(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        assert "regression" in result.benchmark.tags

    def test_convert_error_in_actual_adds_tag(self) -> None:
        bug = BugReport(
            bug_id="BUG-006",
            title="Error test",
            actual_behavior="error: something went wrong",
        )
        generator = BenchmarkGenerator()
        result = generator.convert(bug)
        assert "error-handling" in result.benchmark.tags

    def test_convert_setup_code_has_import(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        assert "import pytest" in result.benchmark.setup_code

    def test_convert_source_bug_matches(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        assert result.benchmark.source_bug == full_bug_report.bug_id

    def test_convert_expected_result_in_benchmark(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        assert result.benchmark.expected_result != ""


# ---------------------------------------------------------------------------
# BenchmarkSuite tests
# ---------------------------------------------------------------------------


class TestBenchmarkSuite:
    def test_add_case(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        suite = BenchmarkSuite()
        suite.add_case(result.benchmark)
        assert len(suite.cases) == 1

    def test_cases_property_returns_copy(self, full_bug_report: BugReport) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        suite = BenchmarkSuite()
        suite.add_case(result.benchmark)
        cases = suite.cases
        cases.clear()
        assert len(suite.cases) == 1  # original not mutated

    def test_export_pytest_creates_directory(
        self, full_bug_report: BugReport, tmp_path
    ) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        suite = BenchmarkSuite()
        suite.add_case(result.benchmark)
        output_dir = str(tmp_path / "benchmarks")
        suite.export_pytest(output_dir)
        assert (tmp_path / "benchmarks").exists()

    def test_export_pytest_creates_test_files(
        self, full_bug_report: BugReport, tmp_path
    ) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        suite = BenchmarkSuite()
        suite.add_case(result.benchmark)
        output_dir = str(tmp_path / "benchmarks")
        suite.export_pytest(output_dir)
        test_files = list((tmp_path / "benchmarks").glob("test_*.py"))
        assert len(test_files) == 1

    def test_export_pytest_creates_conftest(
        self, full_bug_report: BugReport, tmp_path
    ) -> None:
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        suite = BenchmarkSuite()
        suite.add_case(result.benchmark)
        output_dir = str(tmp_path / "benchmarks")
        suite.export_pytest(output_dir)
        conftest = tmp_path / "benchmarks" / "conftest.py"
        assert conftest.exists()

    def test_export_pytest_multiple_cases(self, tmp_path) -> None:
        generator = BenchmarkGenerator()
        suite = BenchmarkSuite()
        for i in range(3):
            bug = BugReport(bug_id=f"BUG-{i:03d}", title=f"Bug number {i}")
            result = generator.convert(bug)
            suite.add_case(result.benchmark)
        output_dir = str(tmp_path / "benchmarks")
        suite.export_pytest(output_dir)
        test_files = list((tmp_path / "benchmarks").glob("test_*.py"))
        assert len(test_files) == 3

    def test_export_pytest_does_not_overwrite_conftest(
        self, full_bug_report: BugReport, tmp_path
    ) -> None:
        output_dir = tmp_path / "benchmarks"
        output_dir.mkdir()
        conftest = output_dir / "conftest.py"
        conftest.write_text("# existing conftest\n", encoding="utf-8")
        generator = BenchmarkGenerator()
        result = generator.convert(full_bug_report)
        suite = BenchmarkSuite()
        suite.add_case(result.benchmark)
        suite.export_pytest(str(output_dir))
        assert conftest.read_text(encoding="utf-8") == "# existing conftest\n"

    def test_empty_suite_export_creates_only_conftest(self, tmp_path) -> None:
        suite = BenchmarkSuite()
        output_dir = str(tmp_path / "benchmarks")
        suite.export_pytest(output_dir)
        conftest = tmp_path / "benchmarks" / "conftest.py"
        assert conftest.exists()
        test_files = list((tmp_path / "benchmarks").glob("test_*.py"))
        assert len(test_files) == 0
