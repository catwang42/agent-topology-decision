"""The binding schema contract.

Every trace this repository generates must validate against the schema that was
exported from the measurement workbench, and the Langfuse shaped export must
convert back into a canonical trace that also validates. That second half is
what makes this generator usable as a converter fixture later: the conversion
is exercised here, not just described.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import gen_demo_traces as generator  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "schema" / "trace.schema.json"
TRACES_PATH = REPO_ROOT / "data" / "traces_sample.jsonl"
LANGFUSE_PATH = REPO_ROOT / "data" / "langfuse_export_sample.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        pytest.skip(f"{path.name} is missing. Run scripts/gen_demo_traces.py first.")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_schema_is_versioned_and_attributed():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["x-schema-version"], "the vendored schema must carry a version"
    provenance = schema["x-provenance"]
    assert provenance["source_repository"].endswith("agent-migration-workbench")
    assert provenance["source_path"] == "amw/traces/schema.py"
    assert len(provenance["source_commit"]) == 40, "pin the exact commit, not a branch"


def test_schema_keeps_the_wire_field_names():
    """`json_` is a python attribute name. The wire name is `json`."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    output = schema["$defs"]["TraceOutput"]["properties"]
    assert "json" in output and "json_" not in output


def test_every_generated_trace_validates(validator):
    traces = read_jsonl(TRACES_PATH)
    assert traces, "the generator produced no canonical traces"
    errors = [
        (index, error.message)
        for index, trace in enumerate(traces)
        for error in validator.iter_errors(trace)
    ]
    assert not errors, f"{len(errors)} traces do not validate: {errors[:3]}"


def test_langfuse_export_converts_and_then_validates(validator):
    """The round trip the future converter has to reproduce.

    Langfuse shaped observation in, canonical trace out, schema clean. If this
    breaks, the converter's fixture has drifted from the schema.
    """
    records = read_jsonl(LANGFUSE_PATH)
    assert records, "the generator produced no Langfuse shaped records"

    converted = [generator.langfuse_record_to_trace(record) for record in records]
    errors = [
        (index, error.message)
        for index, trace in enumerate(converted)
        for error in validator.iter_errors(trace)
    ]
    assert not errors, f"{len(errors)} converted traces do not validate: {errors[:3]}"


def test_conversion_preserves_the_identifying_fields():
    langfuse = read_jsonl(LANGFUSE_PATH)
    canonical = {trace["trace_id"]: trace for trace in read_jsonl(TRACES_PATH)}

    checked = 0
    for record in langfuse:
        converted = generator.langfuse_record_to_trace(record)
        original = canonical.get(converted["trace_id"])
        if original is None:
            continue
        checked += 1
        assert converted["subagent"] == original["subagent"]
        assert converted["model"] == original["model"]
        assert converted["usage"] == original["usage"]
        assert converted["status"] == original["status"]
    assert checked, "the two exports share no trace identifiers, so nothing was compared"


def test_everything_is_declared_synthetic():
    """Rule two: no number in this repository may imply measurement."""
    for trace in read_jsonl(TRACES_PATH):
        assert trace["provenance"] == "synthetic"
