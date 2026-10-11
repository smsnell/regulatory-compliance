[0;93m2026-10-10 14:58:20.659849788 [W:onnxruntime:Default, telemetry.cc:800 operator()] Failed to persist telemetry device ID; using an in-memory identifier[m
# Agent Skill Security Scan Report

**Skill:** regulatory-change-impact-brief
**Directory:** /home/mike/regulatory-compliance/regulatory-change-impact-brief
**Status:** [FAIL] ISSUES FOUND
**Max Severity:** HIGH
**Scan Duration:** 1.62s
**Timestamp:** 2026-10-10T18:58:21.684604+00:00

## Summary

- **Total Findings:** 5
- **Critical:** 0
- **High:** 1
- **Medium:** 3
- **Low:** 0
- **Info:** 1

## Findings

### HIGH Severity

#### [HIGH] Infinite loop without clear exit condition

**Severity:** HIGH
**Category:** resource_abuse
**Rule ID:** RESOURCE_ABUSE_INFINITE_LOOP
**Location:** scripts/rci/adapters/reads.py:168

**Description:** Pattern detected: while True:

**Code Snippet:**
```
while True:
```

**Remediation:** Add proper exit conditions or limits to loops

### MEDIUM Severity

#### [MEDIUM] Outbound network request primitives that can transmit data externally

**Severity:** MEDIUM
**Category:** data_exfiltration
**Rule ID:** DATA_EXFIL_NETWORK_REQUESTS
**Location:** scripts/rci/snapshots.py:318

**Description:** Pattern detected: requests.get(

**Code Snippet:**
```
request = requests.get(record['request_id'])
```

**Remediation:** Ensure network operations are necessary and document allowed destinations

#### [MEDIUM] Outbound network request primitives that can transmit data externally

**Severity:** MEDIUM
**Category:** data_exfiltration
**Rule ID:** DATA_EXFIL_NETWORK_REQUESTS
**Location:** scripts/rci/snapshots.py:323

**Description:** Pattern detected: requests.get(

**Code Snippet:**
```
request = requests.get(record['request_id'])
```

**Remediation:** Ensure network operations are necessary and document allowed destinations

#### [MEDIUM] Outbound network request primitives that can transmit data externally

**Severity:** MEDIUM
**Category:** data_exfiltration
**Rule ID:** DATA_EXFIL_NETWORK_REQUESTS
**Location:** scripts/rci/snapshots.py:556

**Description:** Pattern detected: requests.get(

**Code Snippet:**
```
request = requests.get(binding['request_id'])
```

**Remediation:** Ensure network operations are necessary and document allowed destinations

### INFO Severity

#### [INFO] Skill does not specify a license

**Severity:** INFO
**Category:** policy_violation
**Rule ID:** MANIFEST_MISSING_LICENSE
**Location:** SKILL.md

**Description:** Skill manifest does not include a 'license' field. Specifying a license helps users understand usage terms.

**Remediation:** Add 'license' field to SKILL.md frontmatter (e.g., MIT, Apache-2.0)

## Analyzers

The following analyzers were used:

- static_analyzer
- bytecode
- pipeline

