"""Shared test fixtures for aumai-bug2bench."""

from __future__ import annotations

import pytest

from aumai_bug2bench.models import BugReport


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


@pytest.fixture()
def full_bug_report() -> BugReport:
    return BugReport(
        bug_id="BUG-001",
        title="AttributeError on empty input",
        description="Passing an empty string causes AttributeError.",
        steps_to_reproduce=["Call process('')", "Observe error"],
        expected_behavior="Should return empty result.",
        actual_behavior="AttributeError: 'NoneType' object has no attribute 'strip'",
        environment={"python": "3.11", "os": "linux"},
    )


@pytest.fixture()
def minimal_bug_report() -> BugReport:
    return BugReport(
        bug_id="BUG-002",
        title="Minimal bug",
    )
