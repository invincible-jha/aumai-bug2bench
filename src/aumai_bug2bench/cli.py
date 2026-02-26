"""CLI entry point for aumai-bug2bench.

Commands:
  parse    Parse a bug report file and print structured JSON.
  convert  Convert a bug report to a pytest benchmark case.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from aumai_bug2bench.core import BenchmarkGenerator, BenchmarkSuite, BugParser

__all__ = ["cli"]


@click.group()
@click.version_option()
def cli() -> None:
    """AumAI Bug2Bench — convert bug reports to reproducible benchmarks."""


@cli.command("parse")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to the bug report file (Markdown or plain text).",
)
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(dir_okay=False, writable=True),
    help="Optional path to write JSON output.",
)
def parse_command(input_path: str, output_path: str | None) -> None:
    """Parse a bug report file and print structured JSON.

    Example:

    \b
        aumai-bug2bench parse --input bug.md
    """
    text = Path(input_path).read_text(encoding="utf-8")
    parser = BugParser()
    bug = parser.parse(text)

    json_output = json.dumps(bug.model_dump(), indent=2)
    if output_path:
        Path(output_path).write_text(json_output, encoding="utf-8")
        click.echo(f"Parsed bug report written to {output_path}")
    else:
        click.echo(json_output)


@cli.command("convert")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to the bug report file (Markdown or plain text).",
)
@click.option(
    "--output",
    "output_dir",
    default="benchmark",
    show_default=True,
    help="Output directory for generated pytest files.",
)
@click.option(
    "--json-output",
    "json_path",
    default=None,
    type=click.Path(dir_okay=False, writable=True),
    help="Optional path to write ConversionResult JSON.",
)
def convert_command(input_path: str, output_dir: str, json_path: str | None) -> None:
    """Convert a bug report to a pytest benchmark case.

    Example:

    \b
        aumai-bug2bench convert --input bug.md --output benchmark/
    """
    text = Path(input_path).read_text(encoding="utf-8")
    parser = BugParser()
    bug = parser.parse(text)

    generator = BenchmarkGenerator()
    result = generator.convert(bug)

    suite = BenchmarkSuite()
    suite.add_case(result.benchmark)
    suite.export_pytest(output_dir)

    click.echo(
        f"Benchmark case '{result.benchmark.case_id}' written to {output_dir}/ "
        f"(confidence: {result.confidence:.0%})"
    )

    if result.notes:
        click.echo("Notes:")
        for note in result.notes:
            click.echo(f"  - {note}")

    if json_path:
        json_output = json.dumps(result.model_dump(), indent=2, default=str)
        Path(json_path).write_text(json_output, encoding="utf-8")
        click.echo(f"Full conversion result written to {json_path}")


@cli.command("batch")
@click.option(
    "--input-dir",
    "input_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, readable=True),
    help="Directory containing bug report files (*.md or *.txt).",
)
@click.option(
    "--output",
    "output_dir",
    default="benchmark",
    show_default=True,
    help="Output directory for generated pytest files.",
)
@click.option(
    "--pattern",
    default="*.md",
    show_default=True,
    help="Glob pattern for bug report files.",
)
def batch_command(input_dir: str, output_dir: str, pattern: str) -> None:
    """Batch-convert all bug reports in a directory.

    Example:

    \b
        aumai-bug2bench batch --input-dir bugs/ --output benchmarks/
    """
    input_path = Path(input_dir)
    report_files = sorted(input_path.glob(pattern))

    if not report_files:
        click.echo(f"No files matching '{pattern}' found in {input_dir}.", err=True)
        sys.exit(1)

    parser = BugParser()
    generator = BenchmarkGenerator()
    suite = BenchmarkSuite()

    for report_file in report_files:
        text = report_file.read_text(encoding="utf-8")
        bug = parser.parse(text)
        result = generator.convert(bug)
        suite.add_case(result.benchmark)
        click.echo(f"Processed: {report_file.name} → confidence {result.confidence:.0%}")

    suite.export_pytest(output_dir)
    click.echo(f"\n{len(suite.cases)} benchmark(s) written to {output_dir}/")


# Allow both `aumai-bug2bench` and legacy `main` entry point names
main = cli

if __name__ == "__main__":
    cli()
