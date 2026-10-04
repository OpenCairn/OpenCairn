# Artifact runtime preflight

Read the selected installed skill first, then choose an explicit diagnostic scope. Requirements differ: an artifact JS skill may allow a local runtime fallback when `load_workspace_dependencies` is unavailable; a PDF workflow may require Python/ReportLab and a marker without requiring artifact-tool. The checker does not infer a profile by searching skill text.

For an authorized JS artifact route, supply the actual task, skill and runtime paths:

```bash
python3 .claude/scripts/artifact-runtime-preflight.py --profile js-artifact --cwd /absolute/task-directory --skill /absolute/skill/SKILL.md --node /absolute/runtime/node --node-modules /absolute/runtime/node_modules --tool-registry /absolute/current-tools.json --requirement-provenance 'Selected skill runtime section allows these supplied dependencies' --vault /absolute/vault
```

Loader exposure is recorded separately and does not gate this default profile. Use loader-returned paths where required; use a local fallback only if the selected skill permits it. If the selected requirement forbids fallback, add `--require-loader` and a non-empty `--requirement-provenance` identifying that requirement. Absent exposure then fails; unavailable registry remains unknown. Neither filesystem presence nor a successful module import proves tool exposure.

For marker file diagnosis without inventing JS package requirements:

```bash
python3 .claude/scripts/artifact-runtime-preflight.py --profile marker-only --cwd /absolute/task-directory --skill /absolute/skill/SKILL.md --requirement-provenance 'Selected skill requires the operation marker; other dependencies are outside this check'
```

This profile does not require Node/node_modules or import artifact-tool. It reports untested authoring prerequisites as unknown, including any Python or rendering dependencies; marker presence alone cannot certify PDF authoring. Both profiles inspect the marker as a readable regular file and never invoke it. Run the skill's marker exactly where the skill requires it for a real operation.

The optional registry shape is `{"tools":[{"name":"load_workspace_dependencies"}]}`. Supply a current exposed-tool enumeration and retain its actual boundary. Omission or malformed input leaves registry exposure unknown. `--vault` independently checks canonical resolver/ingress/library files, shell syntax and executable prerequisites; it never invokes the ingress writer or tests a destination. Ingress cannot supply missing authoring dependencies.

JSON contains selected profile, checked requirements, caller provenance, actual argv/cwd/exit/stdout/stderr, file type/mode/hash and separate authoring/ingress results. Exit 0 means the selected diagnostic prerequisites are present, 1 means a checked prerequisite is unsupported, and 2 means a gated prerequisite or other dependencies in marker-only scope remain unknown. None certifies whole-skill support, successful marker execution, generated artifacts, artifact QA or a vault write. The JS profile executes only a module import; trust the supplied executable/module paths. Timeouts must be finite and positive.

Do not install substitutes, modify provider/plugin caches, invent tool exposure or inject a marker to clear a check. Follow the installed skill's supported fallback or report the named missing prerequisite. Keep authoring diagnosis separate from binary ingress of an existing file.
