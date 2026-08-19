#!/usr/bin/env python3
"""Export the workbench trace schema to schema/trace.schema.json.

Contract C1. The canonical trace record lives in the agent migration workbench
at amw/traces/schema.py as a pydantic model. This script turns that model into
a versioned, vendored JSON Schema document so this repository can validate the
traces it generates without importing the workbench at run time.

The export is deliberately one directional and recorded. The generated file
carries a provenance block naming the source repository, the commit the model
was read at, and the date, so a schema drift shows up as a diff in this
repository rather than as a silent reinterpretation.

Usage:

    python3 scripts/export_schema.py --workbench ../agent-migration-workbench

Run it again after the workbench changes its schema, then run the tests. A
failing round trip test means the generator and the schema have diverged.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKBENCH = REPO_ROOT.parent / "agent-migration-workbench"
OUTPUT = REPO_ROOT / "schema" / "trace.schema.json"

# Bumped by hand when the exported shape changes in a way consumers must notice.
SCHEMA_VERSION = "1.0.0"

SOURCE_REPOSITORY = "https://github.com/catwang42/agent-migration-workbench"
SOURCE_PATH = "amw/traces/schema.py"


def git_commit_for(workbench: Path, relative_path: str) -> str:
    """The commit the source file was last changed in, or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "-C", str(workbench), "log", "-1", "--format=%H", "--", relative_path],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def export(workbench: Path) -> dict:
    source = workbench / SOURCE_PATH
    if not source.exists():
        raise SystemExit(
            f"STOP: cannot find {SOURCE_PATH} under {workbench}.\n"
            f"The workbench must publish the canonical trace model at that path."
        )

    sys.path.insert(0, str(workbench))
    try:
        from amw.traces.schema import Trace  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment problem, not logic
        raise SystemExit(
            f"STOP: {SOURCE_PATH} exists but will not import ({exc}).\n"
            f"The workbench must publish it as an importable module with pydantic available."
        ) from exc

    # mode="serialization" so the wire name `json` is used rather than the
    # python attribute name `json_`. The workbench writes with by_alias=True,
    # so serialization mode is the shape an exported corpus actually has.
    schema = Trace.model_json_schema(mode="serialization")

    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/catwang42/agent-topology-decision/schema/trace.schema.json"
    schema["title"] = "Trace"
    schema["description"] = (
        "One recorded model call. Exported from the agent migration workbench "
        "canonical trace model. Do not hand edit; regenerate with "
        "scripts/export_schema.py."
    )
    schema["x-schema-version"] = SCHEMA_VERSION
    schema["x-provenance"] = {
        "source_repository": SOURCE_REPOSITORY,
        "source_path": SOURCE_PATH,
        "source_commit": git_commit_for(workbench, SOURCE_PATH),
        "exported_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "exported_by": "scripts/export_schema.py",
        "note": (
            "Structural contract only. This repository generates synthetic "
            "traces that conform to this shape. No measured values are carried "
            "across from the workbench."
        ),
    }

    return schema


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbench",
        type=Path,
        default=DEFAULT_WORKBENCH,
        help="path to a checkout of the agent migration workbench",
    )
    args = parser.parse_args()

    schema = export(args.workbench.resolve())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    provenance = schema["x-provenance"]
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)}")
    print(f"  schema version {SCHEMA_VERSION}")
    print(f"  source commit  {provenance['source_commit']}")
    print(f"  exported on    {provenance['exported_on']}")


if __name__ == "__main__":
    main()
