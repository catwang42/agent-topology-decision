# Where this schema came from

`trace.schema.json` is not written by hand. It is exported from the canonical
trace model in the measurement workbench and vendored here so this repository
has a fixed target to generate against.

| | |
| --- | --- |
| Source repository | https://github.com/catwang42/agent-migration-workbench |
| Source path | `amw/traces/schema.py` |
| Source commit | `88a1448d8340bc5a5cd63e006e1963c51512932f` |
| Exported by | `scripts/export_schema.py` |
| Exported on | 2026-08-18 |
| Schema version | 1.0.0 |
| Dialect | JSON Schema draft 2020-12 |

## What crossed the boundary

The shape, and only the shape. Field names, types, required fields, nested
definitions, and the `additionalProperties: false` that makes the contract
strict rather than advisory.

No value crossed. No scorecard, no benchmark result, no price, no latency. The
export is a structural contract, which is why it can be vendored into a
repository whose second rule is that every number in it is synthetic.

## Two details worth knowing

**The wire name is `json`, not `json_`.** The python model calls the field
`json_` because `json` is a module name, and declares `json` as its alias. The
export runs `model_json_schema(mode="serialization")` so the schema carries the
alias, which is what actually appears on the wire. `tests/test_schema_roundtrip.py`
pins this, because getting it wrong would produce traces that look right in
python and fail validation everywhere else.

**Unknown fields are rejected.** The model sets `extra="forbid"`, which becomes
`additionalProperties: false`. A trace with a stray key fails validation rather
than passing quietly. That is the behaviour we want from a converter fixture:
drift shows up as a test failure, not as a field silently dropped.

## Re-exporting

```
python3 scripts/export_schema.py --workbench ../agent-migration-workbench
python3 -m pytest tests/test_schema_roundtrip.py
```

The script refuses rather than guesses. If it cannot find `amw/traces/schema.py`
under the path it was given, it stops and says what it was looking for.

Bump `SCHEMA_VERSION` in the script when the workbench model changes in a way
that would invalidate traces this repository has already generated. Adding an
optional field is a patch. Adding a required field, renaming one, or tightening
a type is a major, because it breaks the round trip.
