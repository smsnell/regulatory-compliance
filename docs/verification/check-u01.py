"""U01 documentary S/R checks only; no runtime logic/integration acceptance."""
import csv
from collections import Counter
from copy import deepcopy
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASELINE = {
    "REQUIREMENTS.md": "eed1f9d24fcdc9e86b95bd6235eb6e82ea62d915d01f28d6d409329df9cde2c3",
    "interviews/interview-B-3.md": "c3c0167379d0beaeef9ddd88826c6b585017e66620aee43e2ca5a26f9480c7fd",
    "snapshot.schema.json": "8de9874ded18fa97294e83012796e4c386aa60ccfd30f8eca89cabdf2a267ac3",
    "TECHNICAL-DESIGN-AND-IMPLEMENTATION-PLAN.md": "454480a0414f03816d1ebc6bb21a79f907a2d40ea8f176dc6a3c5762fe2e2963",
    "README.md": "1d72d3849dae49bdbbaeaebb1cc20c19f5a14e592094a0d8e4a506be425488b9",
}
FIELDS = [
    "requirement_id", "source_locator", "source_text", "context", "kind",
    "intended_units", "intended_component", "acceptance_owner", "acceptance_cases",
    "acceptance_assertion", "evidence_type", "case_reference", "status", "evidence_location",
    "exclusion_reason",
]


def check(condition, message):
    if not condition:
        raise SystemExit("FAIL: " + message)


for name, digest in BASELINE.items():
    check(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest,
          "changed authoritative input: " + name)

with (ROOT / "docs/requirements-traceability.csv").open(encoding="utf-8", newline="") as stream:
    reader = csv.DictReader(stream)
    check(reader.fieldnames == FIELDS, "CSV columns differ from documented contract")
    rows = list(reader)
ids = [row["requirement_id"] for row in rows]
check(len(ids) == len(set(ids)), "duplicate leaf IDs")
cases = (ROOT / "docs/acceptance-cases.md").read_text()
case_ids = re.findall(r"^## (T\d{2}) —", cases, re.M)
check(len(case_ids) == len(set(case_ids)) == 32, "case ID uniqueness/count")
check(set(case_ids) == {f"T{i:02}" for i in range(1, 33)}, "missing acceptance case")
covered = {}
for row in rows:
    required_fields = [field for field in FIELDS if field != "exclusion_reason"]
    if row.get("kind") == "conversational/non-normative":
        required_fields = ["requirement_id", "source_locator", "source_text", "context", "kind",
                           "status", "evidence_location", "exclusion_reason"]
    check(all(isinstance(row.get(field), str) and row[field].strip() for field in required_fields),
          "empty or malformed field: " + row.get("requirement_id", "unknown"))
    check(re.fullmatch(r"(?:R\d+(?:\.\d+)?|INT)-\d{3}", row["requirement_id"]), "bad leaf ID")
    path, line = row["source_locator"].rsplit(":L", 1)
    source_lines = (ROOT / path).read_text().splitlines()
    check(0 < int(line) <= len(source_lines), "bad source line")
    check(row["source_text"] in source_lines[int(line) - 1], "source text/locator mismatch")
    covered.setdefault(path, set()).add(int(line))
    check(row["kind"] in {"normative", "context", "conversational/non-normative"}, "unknown leaf kind")
    if row["kind"] == "conversational/non-normative":
        check(row["status"] == "not-applicable-with-basis", "conversation must be excluded with basis")
        check(all(row[field] == "" for field in ["intended_units", "intended_component",
                  "acceptance_owner", "acceptance_cases", "acceptance_assertion",
                  "evidence_type", "case_reference"]), "conversation has business acceptance obligations")
        continue
    check(row["exclusion_reason"] == "", "business leaf incorrectly excluded")
    check(row["status"] == "not-demonstrated", "U01 must not claim runtime acceptance")
    check(row["evidence_location"] == "not-yet-produced", "fabricated runtime evidence")
    check("U20" in row["acceptance_owner"], "missing closure owner")
    check(all(re.fullmatch(r"U(?:0[1-9]|1[0-9]|20)", unit)
              for unit in row["intended_units"].split("/")), "invalid unit owner")
    linked = row["acceptance_cases"].split(";")
    check(set(linked) <= set(case_ids), "unknown case reference")
    check(set(row["evidence_type"].split(";")) <= set("ASIRM"), "unknown evidence type")
    local, anchor = row["case_reference"].split("#")
    check((ROOT / local).is_file(), "missing case file")
    check(f'<a id="{anchor}"></a>' in (ROOT / local).read_text(), "missing case anchor")
    check(anchor == linked[0].lower(), "primary case/reference mismatch")

# Independently inventory ALL substantive requirement lines (stronger than just
# checking bullets). Headings, blank lines, separators and code fences are syntax.
expected = set()
for number, line in enumerate((ROOT / "REQUIREMENTS.md").read_text().splitlines(), 1):
    stripped = line.strip()
    if stripped and stripped != "---" and not stripped.startswith(("#", "```")):
        expected.add(number)
check(covered["REQUIREMENTS.md"] == expected, "orphan requirement line or unexpected mapping")

INVENTORY_PATH = "docs/verification/interview-meaning-inventory.csv"
with (ROOT / INVENTORY_PATH).open(encoding="utf-8", newline="") as stream:
    inventory = list(csv.DictReader(stream))


def validate_interview(matrix, inventory_rows):
    """Check each fixed, source-reviewed meaning; never regenerate it from matrix."""
    mapped = {row["requirement_id"]: row for row in matrix}
    entries = {entry["inventory_id"]: entry for entry in inventory_rows}
    check(len(entries) == len(inventory_rows), "duplicate interview inventory ID")
    source_lines = (ROOT / "interviews/interview-B-3.md").read_text().splitlines()
    stakeholder_lines = set()
    speaker = ""
    for number, line in enumerate(source_lines, 1):
        if line.startswith("**"):
            speaker = line.split("**")[1]
        elif speaker == "Compliance and Operations Manager" and line.strip():
            stakeholder_lines.add(number)
    spans = {}
    referenced = set()
    for entry in inventory_rows:
        iid = entry["inventory_id"]
        check(re.fullmatch(r"IM-\d{3}", iid), "bad interview inventory ID")
        path, number = entry["source_locator"].rsplit(":L", 1)
        number = int(number)
        check(path == "interviews/interview-B-3.md" and number in stakeholder_lines,
              "inventory does not reference stakeholder source")
        start, end = int(entry["start"]), int(entry["end"])
        check(0 <= start < end <= len(source_lines[number - 1]), "invalid source span: " + iid)
        check(source_lines[number - 1][start:end] == entry["source_text"], "inventory text mismatch: " + iid)
        covered_chars = spans.setdefault(number, set())
        check(not covered_chars.intersection(range(start, end)), "overlapping inventory spans: " + iid)
        covered_chars.update(range(start, end))
        classification = entry["classification"]
        check(classification in {"normative", "context", "duplicate", "conversational/non-normative"},
              "unknown interview classification")
        rid = entry["requirement_id"]
        if classification in {"normative", "context"}:
            check(rid in mapped, "missing interview meaning: " + rid)
            check(entry["duplicate_of"] == entry["exclusion_reason"] == "", "meaning improperly excluded")
        elif classification == "duplicate":
            target = entries.get(entry["duplicate_of"])
            check(target is not None and target["classification"] in {"normative", "context"},
                  "duplicate lacks canonical meaning: " + iid)
            original_url = re.search(r"\((https?://[^)]+)\)", target["source_text"])
            repeated_url = re.search(r"\((https?://[^)]+)\)", entry["source_text"])
            same_route = original_url and repeated_url and original_url.group(1) == repeated_url.group(1)
            same_text = target["source_text"].replace(",", "").lower() == entry["source_text"].replace(",", "").lower()
            check(same_route or same_text, "unjustified duplicate exclusion: " + iid)
            check(entry["exclusion_reason"].strip(), "duplicate lacks exclusion reason")
        else:
            check(entry["exclusion_reason"].strip() and not entry["duplicate_of"], "conversation lacks exclusion reason")
        if rid:
            check(rid in mapped, "missing inventoried matrix row: " + rid)
            row = mapped[rid]
            check(row["source_locator"] == entry["source_locator"] and row["source_text"] == entry["source_text"],
                  "meaning/leaf source mismatch: " + rid)
            expected_kind = target["classification"] if classification == "duplicate" else classification
            check(row["kind"] == expected_kind, "meaning/leaf classification mismatch: " + rid)
            if classification == "conversational/non-normative":
                check(row["exclusion_reason"] == entry["exclusion_reason"], "conversation exclusion mismatch")
            referenced.add(rid)
    check(referenced == {row["requirement_id"] for row in matrix if row["requirement_id"].startswith("INT-")},
          "matrix interview row absent from independent inventory")
    for number in stakeholder_lines:
        expected_chars = {i for i, char in enumerate(source_lines[number - 1]) if not char.isspace()}
        check(expected_chars <= spans.get(number, set()), f"uninventoried stakeholder text at line {number}")


def validate_contexts(matrix):
    """Global prose must not inherit a preceding list's qualifiers."""
    source_lines = (ROOT / "REQUIREMENTS.md").read_text().splitlines()
    for row in matrix:
        if not row["source_locator"].startswith("REQUIREMENTS.md:"):
            continue
        text = source_lines[int(row["source_locator"].split(":L")[1]) - 1].strip()
        list_item = re.match(r"^- |^\d+\. ", text)
        literal_or_tree = (text.startswith("`") and text.endswith("`")) or any(char in text for char in "├└│") or text.endswith("/")
        if not list_item and not literal_or_tree:
            check(" / " not in row["context"], "stale list context: " + row["requirement_id"])
    mapped = {row["requirement_id"]: row for row in matrix}
    for rid in ["R3-031", "R3-032"]:
        row = mapped[rid]
        check(row["context"] == "3. Required States", "date invariant is not global: " + rid)
        check(row["acceptance_cases"].split(";")[0] == "T09", "wrong date oracle: " + rid)
    check(mapped["INT-082"]["acceptance_cases"].split(";")[0] == "T13", "wrong authenticated-feedback oracle")


validate_interview(rows, inventory)
validate_contexts(rows)

# S/R negative checks mutate copies only; repository and source inputs are unchanged.
def rejects(label, operation):
    try:
        operation()
    except SystemExit as error:
        check(str(error).startswith("FAIL:"), "unexpected diagnostic: " + label)
        print("NEGATIVE PASS: " + label + " -> " + str(error))
    else:
        check(False, "omission/regression accepted: " + label)


for rid in ["INT-082", "INT-118", "INT-119"]:
    rejects("remove " + rid, lambda rid=rid: validate_interview(
        [row for row in rows if row["requirement_id"] != rid], inventory))
rejects("remove inventory meaning IM-174", lambda: validate_interview(
    rows, [entry for entry in inventory if entry["inventory_id"] != "IM-174"]))
rejects("remove both meaning and leaf", lambda: validate_interview(
    [row for row in rows if row["requirement_id"] != "INT-118"],
    [entry for entry in inventory if entry["inventory_id"] != "IM-174"]))
regression = deepcopy(rows)
next(row for row in regression if row["requirement_id"] == "R3-032")["context"] = "Approval State / For unresolved or conflicting items, preserve:"
rejects("restore stale date context", lambda: validate_contexts(regression))
regression = deepcopy(rows)
next(row for row in regression if row["requirement_id"] == "R3-031")["acceptance_cases"] = "T04;T09"
rejects("restore wrong date oracle", lambda: validate_contexts(regression))
regression = deepcopy(rows)
next(row for row in regression if row["requirement_id"] == "INT-080")["kind"] = "normative"
rejects("classify courtesy as normative", lambda: validate_interview(regression, inventory))

decisions = (ROOT / "references/decision-log.md").read_text()
decision_ids = re.findall(r"^## (D\d{3}) —", decisions, re.M)
check(len(decision_ids) == len(set(decision_ids)) == 15, "decision ID uniqueness/count")
for block in re.split(r"^## D\d{3} —.*$", decisions, flags=re.M)[1:]:
    for field in ["id", "summary", "evidence_ids", "concern", "options_considered",
                  "source_basis", "chosen_behavior", "rationale", "tradeoffs", "downstream_effect"]:
        check(re.search(rf"^- {field}: \S.+$", block, re.M), "missing decision field: " + field)

# Check only actual documentation links. Planned runtime filenames are text,
# explicitly not promises that later-unit code already exists.
doc_names = ["docs/acceptance-cases.md", "references/contracts.md", "references/decision-log.md",
             "docs/verification/u01.md"]
for name in doc_names:
    doc = ROOT / name
    check(doc.is_file(), "missing baseline doc: " + name)
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", doc.read_text()):
        if not target.startswith(("http:", "https:")):
            check((doc.parent / target.split("#")[0]).is_file(), "broken local link: " + target)

for name in doc_names + ["docs/requirements-traceability.csv", "docs/verification/check-u01.py", INVENTORY_PATH]:
    content = (ROOT / name).read_text()
    check(content.endswith("\n"), "missing final newline: " + name)
    check(all(line == line.rstrip() for line in content.splitlines()), "trailing whitespace: " + name)

print(f"S PASS: {len(rows)} unique matrix IDs, {len(decision_ids)} decisions, {len(case_ids)} cases; local references and five fingerprints valid")
print(f"R STRUCTURAL PASS: {len(expected)} requirement lines and {len(inventory)} source inventory entries accounted for; every normative leaf has owner/assertion/evidence type")
print(f"CLASSIFICATION: {dict(Counter(row['kind'] for row in rows))}")
print("M semantic acceptance requires source/meaning inspection; structural PASS alone cannot establish it.")
print("Runtime acceptance: not-demonstrated. A/I: not applicable in U01. M: see u01.md.")
