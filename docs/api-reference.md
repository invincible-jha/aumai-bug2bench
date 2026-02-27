# API Reference — aumai-bug2bench

Complete reference for all public classes, methods, and Pydantic models in `aumai-bug2bench`.

---

## Module: `aumai_bug2bench.core`

Three engine classes implementing parsing, generation, and suite management.

```python
from aumai_bug2bench import BugParser, BenchmarkGenerator, BenchmarkSuite
# or
from aumai_bug2bench.core import BugParser, BenchmarkGenerator, BenchmarkSuite
```

---

### `class BugParser`

Parse raw bug report text or GitHub issue dicts into `BugReport` objects.

All parsing is structural (regex + heuristics) with no LLM or external API requirements.

**Example:**

```python
from aumai_bug2bench import BugParser

parser = BugParser()
bug = parser.parse(open("bug.md").read())
bug_from_gh = parser.parse_github_issue({"number": 42, "title": "...", "body": "..."})
```

---

#### `BugParser.parse`

```python
def parse(
    self,
    text: str,
) -> BugReport
```

Parse a plain-text or Markdown bug report into a `BugReport`.

**Parsing strategy (in order):**

1. Scan for Markdown section headings using case-insensitive regex patterns for:
   `## Title`, `## Description`, `## Steps to Reproduce` (and variants),
   `## Expected Behavior` (and variants), `## Actual Behavior` (and variants),
   `## Environment`.
2. If headings are found: split the text at each heading boundary, skip the heading line
   itself, and assign the remaining content to the corresponding field.
3. If no headings are found: try inline label patterns (`Title: ...`, `Expected: ...`, etc.)
   on a line-by-line basis.
4. Extract steps from ordered (`1.`) and unordered (`-`, `*`) list items under the steps
   section.
5. Extract environment key-value pairs from `Key: Value` or `Key - Value` lines.
6. The title defaults to the first non-empty line if not found via a heading.
7. The description defaults to the first five non-empty lines after the title line if not
   found via a heading.
8. Assigns a random 12-character hex `bug_id`.

**Heading variants recognised:**

| Field                 | Recognised heading text                                          |
|-----------------------|------------------------------------------------------------------|
| `title`               | `# Title`, `# Summary`                                          |
| `description`         | `# Description`                                                 |
| `steps_to_reproduce`  | `# Steps to Reproduce`, `# Reproduction Steps`, `# How to Reproduce` |
| `expected_behavior`   | `# Expected Behavior`, `# Expected Result`, `# Expected Outcome`|
| `actual_behavior`     | `# Actual Behavior`, `# Actual Result`, `# Actual Outcome`      |
| `environment`         | `# Environment`                                                 |

**Parameters:**

| Parameter | Type | Description                             |
|-----------|------|-----------------------------------------|
| `text`    | str  | Raw text content of the bug report.     |

**Returns:** `BugReport` with populated fields. All fields have sensible defaults when not
found in the input.

**Example:**

```python
text = """## Title
Process crashes on empty string

## Steps to Reproduce
1. Call process('')
2. Observe the error

## Expected Behavior
Returns empty string.

## Actual Behavior
AttributeError raised.

## Environment
- Python: 3.11
- OS: linux
"""

parser = BugParser()
bug = parser.parse(text)
print(bug.title)               # "Process crashes on empty string"
print(bug.steps_to_reproduce)  # ["Call process('')", "Observe the error"]
print(bug.environment)         # {"python": "3.11", "os": "linux"}
```

---

#### `BugParser.parse_github_issue`

```python
def parse_github_issue(
    self,
    issue: dict[str, object],
) -> BugReport
```

Parse a GitHub REST API issue dict into a `BugReport`.

Extracts `number` (or `id`) for the bug ID prefix, uses `title` as-is, and delegates to
`parse()` to process the `body` field for structured fields.

**Parameters:**

| Parameter | Type                 | Description                                          |
|-----------|----------------------|------------------------------------------------------|
| `issue`   | dict[str, object]    | A GitHub issue dict with `number`/`id`, `title`, `body`. |

**Returns:** `BugReport` with `bug_id` set to `"gh-{number}"`.

**Expected dict keys:**

| Key        | Required | Description                                              |
|------------|----------|----------------------------------------------------------|
| `number`   | preferred| GitHub issue number (integer). Used if present.          |
| `id`       | fallback | Issue ID. Used if `number` is absent.                    |
| `title`    | yes      | Issue title string.                                      |
| `body`     | yes      | Issue body markdown text; parsed for structured fields.  |

**Example:**

```python
parser = BugParser()
issue = {
    "number": 42,
    "title": "AttributeError on empty string",
    "body": "## Steps to Reproduce\n1. Call process('')\n\n## Expected Behavior\nNo error.",
}
bug = parser.parse_github_issue(issue)
print(bug.bug_id)   # "gh-42"
print(bug.title)    # "AttributeError on empty string"
```

---

### `class BenchmarkGenerator`

Generate pytest benchmark cases from `BugReport` objects using string templates.

**Example:**

```python
from aumai_bug2bench import BenchmarkGenerator

gen = BenchmarkGenerator()
result = gen.convert(bug)
print(result.benchmark.test_code)
print(f"Confidence: {result.confidence:.0%}")
```

---

#### `BenchmarkGenerator.convert`

```python
def convert(
    self,
    bug: BugReport,
) -> ConversionResult
```

Convert a `BugReport` to a `ConversionResult` containing a complete pytest test file scaffold.

**Confidence scoring:**

Each of the four fields contributes +0.25 to the confidence score:

| Field populated          | Score contribution |
|--------------------------|--------------------|
| `steps_to_reproduce`     | +0.25              |
| `expected_behavior`      | +0.25              |
| `actual_behavior`        | +0.25              |
| `description`            | +0.25              |

A bug report with all four fields has confidence `1.0`. Missing fields are noted in
`ConversionResult.notes`.

**Generated test structure:**

- Function name: sanitised from the bug title (lowercase, non-alphanumeric → underscores,
  max 60 characters, defaults to `bug` if empty)
- Docstring: bug ID, expected behaviour, actual behaviour
- Body: numbered reproduction steps as `# N. Step` comments
- Footer: `NotImplementedError` with the expected behaviour embedded in the message

**Tag assignment:**

| Condition                                | Tag added         |
|------------------------------------------|-------------------|
| Always                                   | `regression`      |
| `actual_behavior` contains "error"       | `error-handling`  |
| `actual_behavior` contains "exception"   | `exception`       |

**Parameters:**

| Parameter | Type       | Description                    |
|-----------|------------|--------------------------------|
| `bug`     | BugReport  | The bug report to convert.     |

**Returns:** `ConversionResult` with:
- `bug`: the input `BugReport`
- `benchmark`: a `BenchmarkCase` with `setup_code` and `test_code`
- `confidence`: float 0.0–1.0
- `notes`: list of strings explaining missing fields

**Example:**

```python
from aumai_bug2bench import BugParser, BenchmarkGenerator

parser = BugParser()
bug = parser.parse("""
## Title
Crash on None input

## Steps to Reproduce
1. Pass None to transform()

## Expected Behavior
Raise TypeError with message.

## Actual Behavior
AttributeError raised instead.
""")

gen = BenchmarkGenerator()
result = gen.convert(bug)

print(f"Confidence: {result.confidence:.0%}")   # 75% (no description)
print(f"Tags: {result.benchmark.tags}")          # ['regression', 'error-handling', 'exception']
print(result.benchmark.test_code)
```

---

### `class BenchmarkSuite`

A collection of `BenchmarkCase` objects that can be exported as pytest files.

Maintains an ordered list of cases and writes each one as an individual test file when
`export_pytest` is called.

**Example:**

```python
from aumai_bug2bench import BenchmarkSuite

suite = BenchmarkSuite()
suite.add_case(case1)
suite.add_case(case2)
suite.export_pytest("/tmp/benchmarks/")
print(len(suite.cases))  # 2
```

---

#### `BenchmarkSuite.add_case`

```python
def add_case(
    self,
    case: BenchmarkCase,
) -> None
```

Add a benchmark case to the suite.

**Parameters:**

| Parameter | Type          | Description                    |
|-----------|---------------|--------------------------------|
| `case`    | BenchmarkCase | The case to add to the suite.  |

**Returns:** `None`

---

#### `BenchmarkSuite.export_pytest`

```python
def export_pytest(
    self,
    output_dir: str,
) -> None
```

Write all benchmark cases as individual pytest files to the output directory.

Each case is written to `test_<safe_case_id>.py` where `safe_case_id` is the `case_id` with
non-alphanumeric characters replaced by underscores and lowercased.

A `conftest.py` is also created in `output_dir` if one does not already exist. The conftest
contains only a module docstring and is intentionally minimal — add your own fixtures to it.

The output directory is created with `parents=True, exist_ok=True`.

**File content format:**

```
{setup_code}

{test_code}
```

**Parameters:**

| Parameter    | Type | Description                                              |
|--------------|------|----------------------------------------------------------|
| `output_dir` | str  | Directory path where pytest files will be written.       |

**Returns:** `None`

**Example:**

```python
suite = BenchmarkSuite()
suite.add_case(result.benchmark)
suite.export_pytest("tests/regressions/")
# Creates: tests/regressions/test_<case_id>.py
# Creates: tests/regressions/conftest.py (if not exists)
```

---

#### `BenchmarkSuite.cases` (property)

```python
@property
def cases(self) -> list[BenchmarkCase]
```

Read-only view of all cases in the suite. Returns a copy of the internal list.

**Returns:** `list[BenchmarkCase]`

---

## Module: `aumai_bug2bench.models`

All Pydantic v2 data models.

```python
from aumai_bug2bench import BugReport, BenchmarkCase, ConversionResult
# or
from aumai_bug2bench.models import BugReport, BenchmarkCase, ConversionResult
```

All models use:
- `str_strip_whitespace=True` — leading/trailing whitespace stripped from all strings
- `validate_assignment=True` — validation re-runs on every attribute assignment

---

### `class BugReport`

A structured representation of a software bug report, extracted from raw text.

```python
class BugReport(BaseModel):
    bug_id: str                          # Field(min_length=1)
    title: str                           # Field(default="")
    description: str                     # Field(default="")
    steps_to_reproduce: list[str]        # Field(default_factory=list)
    expected_behavior: str               # Field(default="")
    actual_behavior: str                 # Field(default="")
    environment: dict[str, Any]          # Field(default_factory=dict)
```

**Fields:**

| Field                  | Type           | Required | Default | Description                                           |
|------------------------|----------------|----------|---------|-------------------------------------------------------|
| `bug_id`               | str (min 1)    | yes      | —       | Unique identifier; e.g. `"gh-42"` or a 12-char hex   |
| `title`                | str            | no       | `""`    | Short summary of the bug                              |
| `description`          | str            | no       | `""`    | Longer description of the problem                     |
| `steps_to_reproduce`   | list[str]      | no       | `[]`    | Ordered steps that trigger the bug                    |
| `expected_behavior`    | str            | no       | `""`    | What the correct behaviour should be                  |
| `actual_behavior`      | str            | no       | `""`    | What the buggy behaviour is                           |
| `environment`          | dict[str, Any] | no       | `{}`    | Environment key-value pairs (python, os, version, etc)|

**Examples:**

```python
from aumai_bug2bench.models import BugReport

bug = BugReport(
    bug_id="BUG-001",
    title="AttributeError on empty input",
    description="Passing an empty string causes AttributeError.",
    steps_to_reproduce=["Call process('')", "Observe AttributeError"],
    expected_behavior="Should return empty result.",
    actual_behavior="AttributeError: 'NoneType' object has no attribute 'strip'",
    environment={"python": "3.11", "os": "linux"},
)

# Serialise
data = bug.model_dump()
# Deserialise
bug2 = BugReport.model_validate(data)

# Check completeness
has_steps = bool(bug.steps_to_reproduce)
has_expected = bool(bug.expected_behavior)
```

---

### `class BenchmarkCase`

A pytest-compatible benchmark case generated from a bug report.

```python
class BenchmarkCase(BaseModel):
    case_id: str              # Field(min_length=1)
    source_bug: str           # Field(min_length=1)
    setup_code: str           # Field(default="")
    test_code: str            # Field(default="")
    expected_result: str      # Field(default="")
    tags: list[str]           # Field(default_factory=list)
```

**Fields:**

| Field            | Type      | Required | Default | Description                                            |
|------------------|-----------|----------|---------|--------------------------------------------------------|
| `case_id`        | str       | yes      | —       | Unique identifier for this benchmark case              |
| `source_bug`     | str       | yes      | —       | The `bug_id` of the originating bug report             |
| `setup_code`     | str       | no       | `""`    | Preamble code (imports, fixtures) for the test file    |
| `test_code`      | str       | no       | `""`    | The full `def test_...():` function as a string        |
| `expected_result`| str       | no       | `""`    | Human-readable description of the expected outcome     |
| `tags`           | list[str] | no       | `[]`    | Tags: always `["regression"]`, plus `error-handling`, `exception` |

**Examples:**

```python
from aumai_bug2bench.models import BenchmarkCase

case = BenchmarkCase(
    case_id="bench-001",
    source_bug="BUG-001",
    setup_code="import pytest\n# from mypackage.module import function_under_test",
    test_code="def test_empty_input():\n    raise NotImplementedError('implement me')",
    expected_result="no exception raised",
    tags=["regression", "error-handling"],
)

# Write to file manually
from pathlib import Path
Path("test_bench_001.py").write_text(case.setup_code + "\n\n" + case.test_code)
```

---

### `class ConversionResult`

The complete result of converting a bug report to a benchmark case, including metadata.

```python
class ConversionResult(BaseModel):
    bug: BugReport
    benchmark: BenchmarkCase
    confidence: float        # Field(default=0.0, ge=0.0, le=1.0)
    notes: list[str]         # Field(default_factory=list)
```

**Fields:**

| Field        | Type          | Required | Default | Constraints | Description                                           |
|--------------|---------------|----------|---------|-------------|-------------------------------------------------------|
| `bug`        | BugReport     | yes      | —       | —           | The source bug report                                 |
| `benchmark`  | BenchmarkCase | yes      | —       | —           | The generated test case                               |
| `confidence` | float         | no       | `0.0`   | 0.0 – 1.0   | Completeness score of the source bug report           |
| `notes`      | list[str]     | no       | `[]`    | —           | Human-readable notes about missing or low-quality fields |

**Confidence interpretation:**

| Range      | Meaning                                                                 |
|------------|-------------------------------------------------------------------------|
| 1.0        | All four key fields present; fully detailed test can be generated       |
| 0.75       | Three of four fields present; test will be mostly complete              |
| 0.50       | Two fields present; test body will be largely placeholder               |
| 0.25       | One field present; only a minimal scaffold is possible                  |
| 0.0        | No structured fields found; test is entirely placeholder                |

**Example:**

```python
import json
from aumai_bug2bench import BugParser, BenchmarkGenerator

parser = BugParser()
generator = BenchmarkGenerator()

bug = parser.parse(open("bug.md").read())
result = generator.convert(bug)

print(f"Confidence: {result.confidence:.0%}")
print(f"Notes: {result.notes}")

# Serialise full result
data = result.model_dump()
print(json.dumps(data, indent=2, default=str))
```

---

## Module: `aumai_bug2bench.cli`

The Click-based command-line interface.

```
aumai-bug2bench --help
aumai-bug2bench parse --help
aumai-bug2bench convert --help
aumai-bug2bench batch --help
```

The `cli` object can be imported for programmatic use or testing:

```python
from aumai_bug2bench.cli import cli
from click.testing import CliRunner

runner = CliRunner()
with runner.isolated_filesystem():
    # write test files, then invoke
    result = runner.invoke(cli, ["parse", "--input", "bug.md"])
    print(result.output)
```

---

## Public exports (`aumai_bug2bench.__init__`)

```python
from aumai_bug2bench import (
    BugReport,             # models.BugReport
    BenchmarkCase,         # models.BenchmarkCase
    ConversionResult,      # models.ConversionResult
    BugParser,             # core.BugParser
    BenchmarkGenerator,    # core.BenchmarkGenerator
    BenchmarkSuite,        # core.BenchmarkSuite
)

print(aumai_bug2bench.__version__)  # "1.0.0"
```

---

## Internal helpers (not exported)

These functions are used internally by `BugParser` and are not part of the public API, but
they are documented here for contributors:

| Function                    | Description                                                              |
|-----------------------------|--------------------------------------------------------------------------|
| `_extract_steps(text)`      | Extracts ordered/unordered list items from a text section                |
| `_extract_env(text)`        | Extracts `Key: Value` environment pairs from a text section              |
| `_sanitise_identifier(text)`| Converts a title string to a valid Python identifier for test names      |

---

## Error handling

All Pydantic models raise `pydantic.ValidationError` on invalid input:

```python
from pydantic import ValidationError
from aumai_bug2bench.models import BugReport

try:
    BugReport(bug_id="")  # empty bug_id violates min_length=1
except ValidationError as exc:
    print(exc)
```

The CLI exits with code `1` on missing input files (enforced by Click's `exists=True`
parameter). Parsing errors in the report text are handled gracefully with fallbacks.
