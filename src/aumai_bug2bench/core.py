"""Core logic for aumai-bug2bench.

Implements heuristic bug report parsing and template-based pytest benchmark
case generation.  No LLM required — all logic is structural/regex-based
and fully deterministic.
"""

from __future__ import annotations

import re
import textwrap
import uuid
from pathlib import Path

from aumai_bug2bench.models import BenchmarkCase, BugReport, ConversionResult

__all__ = [
    "BugParser",
    "BenchmarkGenerator",
    "BenchmarkSuite",
]

# ---------------------------------------------------------------------------
# Section detection patterns for plain-text bug reports
# ---------------------------------------------------------------------------

_SECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\s*#+\s*title", re.IGNORECASE | re.MULTILINE), "title"),
    (re.compile(r"^\s*#+\s*description", re.IGNORECASE | re.MULTILINE), "description"),
    (
        re.compile(
            r"^\s*#+\s*(?:steps\s+to\s+reproduce|reproduction\s+steps?|how\s+to\s+reproduce)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "steps",
    ),
    (
        re.compile(
            r"^\s*#+\s*expected\s+(?:behavior|result|outcome)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "expected",
    ),
    (
        re.compile(
            r"^\s*#+\s*actual\s+(?:behavior|result|outcome)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "actual",
    ),
    (
        re.compile(
            r"^\s*#+\s*environment",
            re.IGNORECASE | re.MULTILINE,
        ),
        "environment",
    ),
]

# Inline label patterns (e.g. "Steps to Reproduce: ...")
_INLINE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(?:Title|Summary)\s*:\s*(.+)", re.IGNORECASE), "title"),
    (re.compile(r"^Description\s*:\s*(.+)", re.IGNORECASE), "description"),
    (re.compile(r"^Expected\s*:\s*(.+)", re.IGNORECASE), "expected"),
    (re.compile(r"^Actual\s*:\s*(.+)", re.IGNORECASE), "actual"),
]

# Ordered list item: "1. Step", "- step", "* step"
_LIST_ITEM_PATTERN = re.compile(r"^\s*(?:\d+[.)]\s+|[-*]\s+)(.+)")

# Environment key-value: "Python: 3.11", "OS: linux"
_ENV_KV_PATTERN = re.compile(r"^[-*]?\s*(\w[\w\s/]+?)\s*[:\-]\s*(.+)")


def _extract_steps(text: str) -> list[str]:
    """Extract ordered/unordered list items from a section of text."""
    steps: list[str] = []
    for line in text.splitlines():
        match = _LIST_ITEM_PATTERN.match(line)
        if match:
            steps.append(match.group(1).strip())
        elif line.strip() and steps:
            # Non-empty continuation line after at least one step found
            steps[-1] += " " + line.strip()
    return steps


def _extract_env(text: str) -> dict[str, str]:
    """Extract key-value environment pairs from a section of text."""
    env: dict[str, str] = {}
    for line in text.splitlines():
        match = _ENV_KV_PATTERN.match(line.strip())
        if match:
            key = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            env[key] = value
    return env


def _sanitise_identifier(text: str) -> str:
    """Convert a title/description to a valid Python identifier for test names."""
    # Lowercase, replace non-alphanumeric with underscores, collapse runs
    identifier = re.sub(r"[^a-z0-9]+", "_", text.lower())
    identifier = identifier.strip("_")
    return identifier[:60] or "bug"


# ---------------------------------------------------------------------------
# BugParser
# ---------------------------------------------------------------------------


class BugParser:
    """Parse raw bug report text or GitHub issue dicts into ``BugReport`` objects.

    Example::

        parser = BugParser()
        bug = parser.parse(open("bug.md").read())
        bug_from_gh = parser.parse_github_issue({"number": 42, "title": "...", "body": "..."})
    """

    def parse(self, text: str) -> BugReport:
        """Parse a plain-text or Markdown bug report.

        Detects sections by Markdown headings (``## Steps to Reproduce``) or
        by inline labels (``Expected: ...``).  Falls back to treating the
        entire text as the description if no structure is found.

        Args:
            text: Raw text content of the bug report.

        Returns:
            A ``BugReport`` with populated fields.
        """
        # Split text into sections by heading matches
        section_map: dict[str, str] = {}
        positions: list[tuple[int, str]] = []

        for pattern, section_name in _SECTION_PATTERNS:
            for match in pattern.finditer(text):
                positions.append((match.start(), section_name))

        positions.sort(key=lambda x: x[0])

        if positions:
            for idx, (start, name) in enumerate(positions):
                end = positions[idx + 1][0] if idx + 1 < len(positions) else len(text)
                # Skip the heading line itself
                section_content = text[start:end]
                heading_end = section_content.find("\n")
                if heading_end != -1:
                    section_content = section_content[heading_end + 1:]
                section_map[name] = section_content.strip()
        else:
            # No Markdown headings — try inline patterns
            for line in text.splitlines():
                for pattern, field_name in _INLINE_PATTERNS:
                    m = pattern.match(line)
                    if m:
                        section_map.setdefault(field_name, m.group(1).strip())

        # Extract title — first non-empty line if not found via heading
        title = section_map.get("title", "")
        if not title:
            for line in text.splitlines():
                stripped = line.strip().lstrip("#").strip()
                if stripped:
                    title = stripped
                    break

        description = section_map.get("description", "")
        if not description:
            # Use the full text minus the title line as description
            lines = text.splitlines()
            desc_lines = [ln for ln in lines[1:] if ln.strip()] if lines else []
            description = " ".join(desc_lines[:5])

        steps = _extract_steps(section_map.get("steps", ""))
        expected = section_map.get("expected", "")
        actual = section_map.get("actual", "")
        env = _extract_env(section_map.get("environment", ""))

        bug_id = str(uuid.uuid4())[:12]
        return BugReport(
            bug_id=bug_id,
            title=title,
            description=description,
            steps_to_reproduce=steps,
            expected_behavior=expected,
            actual_behavior=actual,
            environment=env,
        )

    def parse_github_issue(self, issue: dict[str, object]) -> BugReport:
        """Parse a GitHub API issue dict into a ``BugReport``.

        Expects keys: ``number`` or ``id``, ``title``, ``body``.

        Args:
            issue: A dict representing a GitHub issue (from the REST API).

        Returns:
            A ``BugReport`` extracted from the issue's title and body.
        """
        issue_number = issue.get("number") or issue.get("id") or uuid.uuid4().hex[:8]
        bug_id = f"gh-{issue_number}"
        title = str(issue.get("title", ""))
        body = str(issue.get("body", ""))

        # Parse body text for structured fields
        partial = self.parse(body)

        return BugReport(
            bug_id=bug_id,
            title=title or partial.title,
            description=partial.description,
            steps_to_reproduce=partial.steps_to_reproduce,
            expected_behavior=partial.expected_behavior,
            actual_behavior=partial.actual_behavior,
            environment=partial.environment,
        )


# ---------------------------------------------------------------------------
# BenchmarkGenerator
# ---------------------------------------------------------------------------

# Template for generating a pytest test function from a bug report
_TEST_TEMPLATE = '''\
"""Regression test generated from bug: {bug_id} — {title}"""
{setup_imports}


{test_function}
'''

_TEST_FUNCTION_TEMPLATE = '''\
def test_{test_name}() -> None:
    """Regression for: {title}

    Original bug: {bug_id}
    Expected: {expected}
    Actual (buggy): {actual}
    """
    # Steps to reproduce:
{steps_comments}
    # TODO: Replace with actual module/function call
    # The following assertion documents the expected correct behavior.
    # Run this test to confirm the bug is fixed.
    raise NotImplementedError(
        "Implement this test: reproduce the bug, then assert the fix."
        "\\nExpected: {expected}"
    )
'''


class BenchmarkGenerator:
    """Generate pytest benchmark cases from bug reports using templates.

    Example::

        gen = BenchmarkGenerator()
        result = gen.convert(bug)
        print(result.benchmark.test_code)
    """

    def convert(self, bug: BugReport) -> ConversionResult:
        """Convert a ``BugReport`` to a ``ConversionResult`` containing a pytest case.

        Confidence is estimated from the completeness of the bug report:
        - +0.25 if steps_to_reproduce is non-empty
        - +0.25 if expected_behavior is filled
        - +0.25 if actual_behavior is filled
        - +0.25 if description is filled

        Args:
            bug: The bug report to convert.

        Returns:
            A ``ConversionResult`` with setup code, test code, and confidence.
        """
        notes: list[str] = []
        confidence = 0.0

        if bug.steps_to_reproduce:
            confidence += 0.25
        else:
            notes.append("No steps to reproduce — test body will be a placeholder.")

        if bug.expected_behavior:
            confidence += 0.25
        else:
            notes.append("No expected behavior specified.")

        if bug.actual_behavior:
            confidence += 0.25
        else:
            notes.append("No actual behavior specified.")

        if bug.description:
            confidence += 0.25

        test_name = _sanitise_identifier(bug.title or bug.bug_id)
        steps_comments = "\n".join(
            f"    # {idx + 1}. {step}" for idx, step in enumerate(bug.steps_to_reproduce)
        ) or "    # No steps provided."

        test_function = _TEST_FUNCTION_TEMPLATE.format(
            test_name=test_name,
            title=bug.title.replace('"', '\\"'),
            bug_id=bug.bug_id,
            expected=bug.expected_behavior.replace('"', '\\"') or "see description",
            actual=bug.actual_behavior.replace('"', '\\"') or "see description",
            steps_comments=steps_comments,
        )

        setup_code = textwrap.dedent(
            """\
            import pytest
            # Add your module imports here, e.g.:
            # from mypackage.module import function_under_test
            """
        )

        test_code = _TEST_TEMPLATE.format(
            bug_id=bug.bug_id,
            title=bug.title,
            setup_imports="import pytest",
            test_function=test_function,
        )

        # Tags from environment and categories
        tags: list[str] = ["regression"]
        if bug.actual_behavior and "error" in bug.actual_behavior.lower():
            tags.append("error-handling")
        if bug.actual_behavior and "exception" in bug.actual_behavior.lower():
            tags.append("exception")

        benchmark = BenchmarkCase(
            case_id=str(uuid.uuid4())[:12],
            source_bug=bug.bug_id,
            setup_code=setup_code,
            test_code=test_code,
            expected_result=bug.expected_behavior or "no error",
            tags=tags,
        )

        return ConversionResult(
            bug=bug,
            benchmark=benchmark,
            confidence=round(confidence, 4),
            notes=notes,
        )


# ---------------------------------------------------------------------------
# BenchmarkSuite
# ---------------------------------------------------------------------------


class BenchmarkSuite:
    """A collection of benchmark cases that can be exported as pytest files.

    Example::

        suite = BenchmarkSuite()
        suite.add_case(case)
        suite.export_pytest("/tmp/benchmarks/")
    """

    def __init__(self) -> None:
        self._cases: list[BenchmarkCase] = []

    def add_case(self, case: BenchmarkCase) -> None:
        """Add a benchmark case to the suite.

        Args:
            case: The ``BenchmarkCase`` to add.
        """
        self._cases.append(case)

    def export_pytest(self, output_dir: str) -> None:
        """Write all benchmark cases as individual pytest files.

        Each case is written to ``test_<case_id>.py`` in ``output_dir``.
        A ``conftest.py`` is also created if it doesn't already exist.

        Args:
            output_dir: Directory path where pytest files will be written.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        conftest_path = out / "conftest.py"
        if not conftest_path.exists():
            conftest_path.write_text(
                '"""Conftest for aumai-bug2bench generated benchmarks."""\n',
                encoding="utf-8",
            )

        for case in self._cases:
            safe_id = re.sub(r"[^a-z0-9_]", "_", case.case_id.lower())
            file_path = out / f"test_{safe_id}.py"
            content = f"{case.setup_code}\n\n{case.test_code}"
            file_path.write_text(content, encoding="utf-8")

    @property
    def cases(self) -> list[BenchmarkCase]:
        """Read-only view of all cases in the suite."""
        return list(self._cases)
