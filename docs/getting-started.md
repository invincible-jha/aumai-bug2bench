# Getting Started with aumai-bug2bench

This guide walks you from a fresh install through parsing, converting, and batch-processing
bug reports in about 15 minutes.

---

## Prerequisites

- Python 3.11 or later
- pip or a compatible package manager
- One or more bug reports in Markdown or plain text format (or GitHub issue data)

---

## Installation

### Standard install

```bash
pip install aumai-bug2bench
```

### Development install (editable)

```bash
git clone https://github.com/aumai/aumai-bug2bench
cd aumai-bug2bench
pip install -e ".[dev]"
```

### Verify your installation

```bash
aumai-bug2bench --version
python -c "import aumai_bug2bench; print(aumai_bug2bench.__version__)"
```

---

## Step-by-step tutorial

### Step 1: Write a bug report

Create a file `bug.md` with this content:

```markdown
## Title
AttributeError on empty input

## Description
Calling `process('')` with an empty string causes an AttributeError instead of returning
an empty result. This breaks any pipeline that handles optional input.

## Steps to Reproduce
1. Install the package
2. Import the `process` function from `mypackage.core`
3. Call `process('')`
4. Observe the AttributeError

## Expected Behavior
`process('')` should return an empty string or an empty list without raising any exception.

## Actual Behavior
`AttributeError: 'NoneType' object has no attribute 'strip'`

## Environment
- Python: 3.11
- OS: linux
- Package version: 2.1.0
```

### Step 2: Parse the bug report

```bash
aumai-bug2bench parse --input bug.md
```

Output:

```json
{
  "bug_id": "a1b2c3d4e5f6",
  "title": "AttributeError on empty input",
  "description": "Calling `process('')` with an empty string causes an AttributeError...",
  "steps_to_reproduce": [
    "Install the package",
    "Import the `process` function from `mypackage.core`",
    "Call `process('')`",
    "Observe the AttributeError"
  ],
  "expected_behavior": "`process('')` should return an empty string or an empty list without raising any exception.",
  "actual_behavior": "`AttributeError: 'NoneType' object has no attribute 'strip'`",
  "environment": {
    "python": "3.11",
    "os": "linux",
    "package_version": "2.1.0"
  }
}
```

### Step 3: Convert to a pytest test

```bash
aumai-bug2bench convert --input bug.md --output benchmark/
```

Output:

```
Benchmark case 'b7c8d9e0f1a2' written to benchmark/ (confidence: 100%)
```

The `benchmark/` directory now contains:

```
benchmark/
  conftest.py
  test_b7c8d9e0f1a2.py
```

Open `test_b7c8d9e0f1a2.py`:

```python
import pytest


def test_attributeerror_on_empty_input() -> None:
    """Regression for: AttributeError on empty input

    Original bug: a1b2c3d4e5f6
    Expected: `process('')` should return an empty string or an empty list without raising any exception.
    Actual (buggy): `AttributeError: 'NoneType' object has no attribute 'strip'`
    """
    # Steps to reproduce:
    # 1. Install the package
    # 2. Import the `process` function from `mypackage.core`
    # 3. Call `process('')`
    # 4. Observe the AttributeError
    # TODO: Replace with actual module/function call
    raise NotImplementedError(
        "Implement this test: reproduce the bug, then assert the fix."
        "\nExpected: `process('')` should return an empty string..."
    )
```

### Step 4: Implement the test

Replace the `NotImplementedError` with the actual test logic:

```python
from mypackage.core import process


def test_attributeerror_on_empty_input() -> None:
    """Regression for: AttributeError on empty input ..."""
    # Steps to reproduce:
    # 1. Install the package
    # 2. Import the process function from mypackage.core
    # 3. Call process('')
    # 4. Observe the AttributeError

    # Assert the fix
    result = process('')
    assert result == '' or result == []  # should not raise
```

### Step 5: Run the test

```bash
pytest benchmark/ -v
```

The test passes once the bug is fixed. Add it to your regression suite to prevent future
regressions.

---

## Common patterns and recipes

### Pattern 1: Parsing a GitHub issue dict

When you pull issues from the GitHub API (or `gh issue list --json`), use
`parse_github_issue` which handles the `number`/`id`/`title`/`body` structure directly:

```python
import json
from aumai_bug2bench import BugParser, BenchmarkGenerator, BenchmarkSuite

parser = BugParser()
generator = BenchmarkGenerator()
suite = BenchmarkSuite()

# Simulating the GitHub API response
github_issues = [
    {
        "number": 42,
        "title": "Bug: crash on empty list input",
        "body": """## Steps to Reproduce
1. Pass an empty list to `transform([])`
2. Observe the IndexError

## Expected Behavior
Should return an empty list.

## Actual Behavior
IndexError: list index out of range
""",
    }
]

for issue in github_issues:
    bug = parser.parse_github_issue(issue)
    result = generator.convert(bug)
    suite.add_case(result.benchmark)
    print(f"#{issue['number']} -> {result.benchmark.case_id} (confidence: {result.confidence:.0%})")

suite.export_pytest("tests/regressions/")
```

### Pattern 2: Filtering by confidence score

Low-confidence conversions produce tests with entirely placeholder content. Filter them to
avoid generating useless test files:

```python
from pathlib import Path
from aumai_bug2bench import BugParser, BenchmarkGenerator, BenchmarkSuite

parser = BugParser()
generator = BenchmarkGenerator()
suite = BenchmarkSuite()

skipped = []
processed = []

for report_file in Path("bugs/").glob("*.md"):
    bug = parser.parse(report_file.read_text(encoding="utf-8"))
    result = generator.convert(bug)

    if result.confidence < 0.5:
        skipped.append((report_file.name, result.confidence, result.notes))
    else:
        suite.add_case(result.benchmark)
        processed.append(report_file.name)

suite.export_pytest("tests/regressions/")

print(f"\nProcessed: {len(processed)} reports")
print(f"Skipped (low confidence): {len(skipped)} reports")
for filename, confidence, notes in skipped:
    print(f"  {filename} ({confidence:.0%}): {'; '.join(notes)}")
```

### Pattern 3: Inline-label format for quick reports

For quick bug reports that don't need full Markdown structure:

```
Title: Process function crashes on None input
Description: Passing None instead of a string causes an unhandled exception.
Expected: Should raise a TypeError with a helpful message.
Actual: AttributeError with no useful context.
```

```python
from aumai_bug2bench import BugParser, BenchmarkGenerator

quick_report = """
Title: Process function crashes on None input
Description: Passing None instead of a string causes an unhandled exception.
Expected: Should raise a TypeError with a helpful message.
Actual: AttributeError with no useful context.
"""

parser = BugParser()
bug = parser.parse(quick_report)
print(bug.title)    # "Process function crashes on None input"
print(bug.expected_behavior)  # "Should raise a TypeError with a helpful message."

generator = BenchmarkGenerator()
result = generator.convert(bug)
print(f"Confidence: {result.confidence:.0%}")  # 75% (no steps provided)
```

### Pattern 4: Batch processing a bugs directory

Use the CLI `batch` command or the Python API to process many reports at once:

```bash
# CLI
aumai-bug2bench batch \
  --input-dir bugs/ \
  --output tests/regressions/ \
  --pattern "*.md"
```

```python
# Python equivalent
from pathlib import Path
from aumai_bug2bench import BugParser, BenchmarkGenerator, BenchmarkSuite

parser = BugParser()
generator = BenchmarkGenerator()
suite = BenchmarkSuite()

for report in sorted(Path("bugs/").glob("*.md")):
    bug = parser.parse(report.read_text())
    result = generator.convert(bug)
    suite.add_case(result.benchmark)

suite.export_pytest("tests/regressions/")
print(f"Total cases: {len(suite.cases)}")
```

### Pattern 5: Persisting the parsed bug report as JSON

Save the `BugReport` as JSON for downstream processing (e.g., feeding into aumai-maintainer
or a ticketing system):

```python
import json
from aumai_bug2bench import BugParser

parser = BugParser()
bug = parser.parse(open("bug.md").read())

with open("bug_structured.json", "w") as f:
    json.dump(bug.model_dump(), f, indent=2)
```

---

## Troubleshooting FAQ

**Q: The parser returns an empty `steps_to_reproduce` list**

The step extractor looks for ordered list items (`1.`, `2.`, etc.) or unordered items
(`-`, `*`) under a `## Steps to Reproduce` section heading. If your report uses prose
instead of a list, steps will not be extracted. Reformat the steps section as a numbered
or bulleted list.

**Q: The title in the parsed output is the heading text (`## Title`) rather than the title itself**

The parser strips the heading line (the `##` line itself) and takes the content below it as
the section body. If your `## Title` heading has the title on the same line (which is unusual
for Markdown), use the inline label format instead: `Title: My bug title`.

**Q: The `convert` command produces a test with `confidence: 0%`**

Zero confidence means none of the four key fields (`steps_to_reproduce`, `expected_behavior`,
`actual_behavior`, `description`) were found. Check that your report uses the supported
heading formats and that the content is below the headings (not on the same line as the `##`).

**Q: The generated test name contains underscores but is very short (just `bug`)**

The test name is derived from the bug title. If the title is empty or contains no
alphanumeric characters, the name defaults to `bug`. Ensure your bug report has a meaningful
title in the `## Title` section.

**Q: `export_pytest` is overwriting existing test files**

`export_pytest` names files using the `case_id` (a short UUID). Collisions are extremely
unlikely, but if you are re-running the same report twice, you will get a new `case_id` each
time. The `conftest.py` is only written if it does not already exist.

**Q: I want to customise the generated test template**

The test template strings are module-level constants in `core.py` (`_TEST_TEMPLATE` and
`_TEST_FUNCTION_TEMPLATE`). To customise them, either subclass `BenchmarkGenerator` and
override the `convert` method, or post-process the `test_code` field on the returned
`BenchmarkCase` object before calling `export_pytest`.

---

## Next steps

- Read the [API Reference](api-reference.md) for complete class and method documentation
- Explore the [quickstart example](../examples/quickstart.py)
- See the [README](../README.md) for integration with aumai-maintainer and GitHub Actions
- Join the [AumAI Discord](https://discord.gg/aumai)
