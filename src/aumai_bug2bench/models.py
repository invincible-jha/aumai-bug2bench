"""Pydantic v2 models for aumai-bug2bench.

Provides typed structures for bug reports, benchmark cases, and conversion
results used by the bug-to-benchmark conversion engine.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BugReport",
    "BenchmarkCase",
    "ConversionResult",
]


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class BugReport(BaseModel):
    """A structured representation of a software bug report.

    Example::

        bug = BugReport(
            bug_id="BUG-001",
            title="AttributeError on empty input",
            description="Passing an empty string causes AttributeError.",
            steps_to_reproduce=["Call process('')"],
            expected_behavior="Should return empty result.",
            actual_behavior="AttributeError: 'NoneType' object has no attribute 'strip'",
            environment={"python": "3.11", "os": "linux"},
        )
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    bug_id: str = Field(min_length=1)
    title: str = Field(default="")
    description: str = Field(default="")
    steps_to_reproduce: list[str] = Field(default_factory=list)
    expected_behavior: str = Field(default="")
    actual_behavior: str = Field(default="")
    environment: dict[str, Any] = Field(default_factory=dict)


class BenchmarkCase(BaseModel):
    """A pytest-compatible benchmark case generated from a bug report.

    Example::

        case = BenchmarkCase(
            case_id="bench-001",
            source_bug="BUG-001",
            setup_code="from mymodule import process",
            test_code="def test_empty_input():\\n    result = process('')\\n    assert result is not None",
            expected_result="no exception raised",
            tags=["regression", "input-validation"],
        )
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    case_id: str = Field(min_length=1)
    source_bug: str = Field(min_length=1)
    setup_code: str = Field(default="")
    test_code: str = Field(default="")
    expected_result: str = Field(default="")
    tags: list[str] = Field(default_factory=list)


class ConversionResult(BaseModel):
    """The result of converting a bug report to a benchmark case.

    Example::

        result = ConversionResult(
            bug=bug,
            benchmark=case,
            confidence=0.85,
            notes=["Steps clearly described", "Environment info available"],
        )
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    bug: BugReport
    benchmark: BenchmarkCase
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
