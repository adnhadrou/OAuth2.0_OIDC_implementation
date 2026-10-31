"""Export only test names/statuses. Never copy tracebacks, variables or captured output."""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("junit", nargs="+")
parser.add_argument("--output", default="docs/observed-tests.md")
args = parser.parse_args()
lines = [
    "# Observed test cases",
    "",
    "Generated from JUnit; no captured output or credentials.",
    "",
    "| Test | Result |",
    "|---|---|",
]
cases = [case for path in args.junit for case in ET.parse(path).getroot().iter("testcase")]
for case in cases:
    status = "PASS"
    for tag, label in [("skipped", "SKIP"), ("failure", "FAIL"), ("error", "ERROR")]:
        if case.find(tag) is not None:
            status = label
    lines.append(f"| `{case.get('classname')}.{case.get('name')}` | {status} |")
Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
