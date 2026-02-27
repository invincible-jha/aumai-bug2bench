"""aumai-bug2bench quickstart — convert bug reports to reproducible benchmarks.

Run this file directly:
    python examples/quickstart.py

No external services required. All parsing and code generation is
deterministic and regex-based, so these examples run fully offline.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from aumai_bug2bench import (
    BenchmarkGenerator,
    BenchmarkSuite,
    BugParser,
    BugReport,
    ConversionResult,
)


# ---------------------------------------------------------------------------
# Demo 1: Parse a Markdown-formatted bug report
# ---------------------------------------------------------------------------


def demo_parse_markdown_bug_report() -> BugReport:
    """Parse a GitHub-style Markdown bug report into a structured BugReport.

    BugParser detects sections via Markdown headings (## Steps to Reproduce)
    and inline labels (Expected: ...). Unstructured free-text is handled by
    a fallback that extracts the title from the first non-empty line.
    """
    print("=== Demo 1: Parse Markdown Bug Report ===")

    markdown_report = """\
## Title
AttributeError when processing empty string input

## Description
Calling `process_text("")` with an empty string raises an AttributeError
because the function dereferences `.strip()` on a value that can be None.

## Steps to Reproduce
1. Import the module: `from mylib.text import process_text`
2. Call the function with an empty string: `process_text("")`
3. Observe the traceback

## Expected Behavior
The function should return an empty string or raise a ValueError with a
clear message about invalid input.

## Actual Behavior
AttributeError: 'NoneType' object has no attribute 'strip'

## Environment
- Python: 3.11.4
- OS: Ubuntu 22.04
- mylib version: 0.8.2
"""

    parser = BugParser()
    bug = parser.parse(markdown_report)

    print(f"  Bug ID:       {bug.bug_id}")
    print(f"  Title:        {bug.title}")
    print(f"  Steps found:  {len(bug.steps_to_reproduce)}")
    for index, step in enumerate(bug.steps_to_reproduce, start=1):
        print(f"    {index}. {step}")
    print(f"  Expected:     {bug.expected_behavior[:60]}...")
    print(f"  Actual:       {bug.actual_behavior}")
    print(f"  Environment:  {bug.environment}")
    print()

    return bug


# ---------------------------------------------------------------------------
# Demo 2: Parse a GitHub API issue dict
# ---------------------------------------------------------------------------


def demo_parse_github_issue() -> BugReport:
    """Parse a GitHub REST API issue payload into a BugReport.

    In production you would pass the JSON response from the GitHub API.
    Here we construct a representative dict by hand to avoid network calls.
    """
    print("=== Demo 2: Parse GitHub Issue Payload ===")

    github_issue: dict[str, object] = {
        "number": 1042,
        "title": "KeyError raised on missing config key",
        "body": """\
## Description
When `config.json` is missing the `timeout` key the agent crashes with a
KeyError instead of falling back to the default value.

## Steps to Reproduce
- Remove the `timeout` key from `config.json`
- Start the agent: `python -m myagent.run`

## Expected Behavior
Agent should use a default timeout of 30 seconds.

## Actual Behavior
KeyError: 'timeout'

## Environment
- Python: 3.12.0
- OS: macOS 14.2
""",
    }

    parser = BugParser()
    bug = parser.parse_github_issue(github_issue)

    print(f"  Bug ID:      {bug.bug_id}")
    print(f"  Title:       {bug.title}")
    print(f"  Description: {bug.description[:80]}")
    print(f"  Steps found: {len(bug.steps_to_reproduce)}")
    print(f"  Expected:    {bug.expected_behavior[:60]}")
    print()

    return bug


# ---------------------------------------------------------------------------
# Demo 3: Convert a bug report to a pytest benchmark case
# ---------------------------------------------------------------------------


def demo_convert_to_benchmark(bug: BugReport) -> ConversionResult:
    """Convert a BugReport into a ConversionResult with a pytest test stub.

    BenchmarkGenerator scores confidence (0.0-1.0) based on how complete
    the bug report is, then emits a pytest function with reproduction steps
    embedded as comments and a NotImplementedError placeholder to force the
    developer to fill in the actual assertion.
    """
    print("=== Demo 3: Convert Bug to Benchmark Case ===")

    generator = BenchmarkGenerator()
    result = generator.convert(bug)

    print(f"  Case ID:       {result.benchmark.case_id}")
    print(f"  Source bug:    {result.benchmark.source_bug}")
    print(f"  Confidence:    {result.confidence:.0%}")
    print(f"  Tags:          {result.benchmark.tags}")

    if result.notes:
        print("  Notes:")
        for note in result.notes:
            print(f"    - {note}")

    print("\n  Generated test code preview:")
    lines = result.benchmark.test_code.strip().splitlines()
    for line in lines[:20]:
        print(f"    {line}")
    if len(lines) > 20:
        print(f"    ... ({len(lines) - 20} more lines)")
    print()

    return result


# ---------------------------------------------------------------------------
# Demo 4: Build a suite and export pytest files
# ---------------------------------------------------------------------------


def demo_export_suite(results: list[ConversionResult]) -> None:
    """Collect multiple benchmark cases into a BenchmarkSuite and write them.

    BenchmarkSuite.export_pytest() writes one test_<id>.py file per case
    plus a conftest.py into the target directory. The output is ready to run
    with `pytest` immediately (tests will raise NotImplementedError until you
    fill in the assertions).
    """
    print("=== Demo 4: Export BenchmarkSuite as Pytest Files ===")

    suite = BenchmarkSuite()
    for result in results:
        suite.add_case(result.benchmark)

    print(f"  Suite contains {len(suite.cases)} case(s)")

    with tempfile.TemporaryDirectory() as tmpdir:
        suite.export_pytest(tmpdir)
        exported = sorted(Path(tmpdir).iterdir())
        print(f"  Exported {len(exported)} file(s) to temporary directory:")
        for file_path in exported:
            size = file_path.stat().st_size
            print(f"    {file_path.name}  ({size} bytes)")
    print()


# ---------------------------------------------------------------------------
# Demo 5: Manual BugReport construction and inline conversion
# ---------------------------------------------------------------------------


def demo_manual_bug_report() -> None:
    """Construct a BugReport programmatically without parsing text.

    You can build BugReport objects directly when integrating with a ticketing
    system that already returns structured data (e.g. Jira, Linear).
    """
    print("=== Demo 5: Manual BugReport Construction ===")

    bug = BugReport(
        bug_id="JIRA-9931",
        title="Division by zero in token cost calculator",
        description=(
            "When output_tokens is 0 the cost calculator divides by zero "
            "instead of returning 0.0."
        ),
        steps_to_reproduce=[
            "Call estimate_cost('openai', 'gpt-4o', input_tokens=100, output_tokens=0)",
            "Observe ZeroDivisionError raised from pricing.py line 47",
        ],
        expected_behavior="estimate_cost should return 0.0 when output_tokens is 0.",
        actual_behavior="ZeroDivisionError: division by zero",
        environment={"python": "3.11", "aumai_costprov": "0.1.0"},
    )

    generator = BenchmarkGenerator()
    result = generator.convert(bug)

    print(f"  Bug ID:          {bug.bug_id}")
    print(f"  Confidence:      {result.confidence:.0%}")
    print(f"  Tags:            {result.benchmark.tags}")
    print(f"  Expected result: {result.benchmark.expected_result}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all quickstart demos in sequence."""
    print("\naumai-bug2bench quickstart\n")

    markdown_bug = demo_parse_markdown_bug_report()
    github_bug = demo_parse_github_issue()

    result_1 = demo_convert_to_benchmark(markdown_bug)
    result_2 = demo_convert_to_benchmark(github_bug)

    demo_export_suite([result_1, result_2])
    demo_manual_bug_report()

    print("All demos complete.")


if __name__ == "__main__":
    main()
