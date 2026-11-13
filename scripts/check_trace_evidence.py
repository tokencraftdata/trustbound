"""Recheck exported local trace evidence without running Lean or a provider."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trustbound.trace_evidence import audit_traces


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_traces(json.loads(args.traces.read_text()))
    with args.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"checks_passed": True, "scenarios_checked": len(report["scenarios"])}))


if __name__ == "__main__":
    main()
