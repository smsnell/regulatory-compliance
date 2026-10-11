"""Replay every permanent E07 case against one verified retained public baseline.

Run from the repository using the pinned interpreter. Fixture reuse avoids
another identical baseline acquisition; every variant executes the complete
public launcher and calls the permanent assertions without weakening them.
Synthetic authentication confers no organizational or Legal authorization.
"""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path[:0] = ['regulatory-change-impact-brief/scripts', 'tests']
from rci.contracts import json_bytes, parse_json, sha256_bytes
from rci.validate import validate_package
from runtime import test_feedback_remediation as cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    previous = validate_package(args.baseline)
    first = parse_json((args.baseline / 'analysis/outcome.json').read_bytes())
    assert first['package_acceptance'] and first['production_package']
    target = next(a for a in previous[5]['state']['proposed_actions'] if
                  a['system_id'] == 'AI-007' and a['action_kind'] == 'review-rule-change')
    assert target['existing_due_date'] == target['proposed_due_date'] == '2026-09-04'
    prior = args.baseline.parent, first, previous, target
    args.work_root.mkdir(parents=True, exist_ok=False)
    class Factory:
        def mktemp(self, prefix):
            path = args.work_root / prefix
            path.mkdir()
            return path
    records = []
    for variant in ['same','date','content']:
        case = cases.feedback_run.__wrapped__(SimpleNamespace(param=variant), Factory(), prior)
        cases.test_conditional_feedback_and_changed_basis_are_scoped(case)
        cases.test_all_artifacts_preserve_date_and_unmet_conditional_outcome(case)
        cases.test_exact_prior_artifacts_and_history_remain_intact(case)
        if variant == 'same':
            for artifact in cases.ARTIFACTS:
                path = args.work_root / ('tamper-' + artifact)
                path.mkdir()
                cases.test_independent_validator_rejects_changed_condition(case, path, artifact)
        state = case['current'][5]['state']
        feedback, = state['feedback']
        action = next(a for a in state['proposed_actions'] if a['action_id'] == target['action_id'])
        record = dict(variant=variant, outcome=case['outcome'], root=str(case['root']),
            prior_run_id=first['run_id'], run_id=case['outcome']['run_id'],
            action_id=action['action_id'], existing_due_date=action['existing_due_date'],
            proposed_due_date=action['proposed_due_date'], approval_status=action['approval_status'],
            feedback=feedback, reviewed_draft=case['reviewed'],
            artifacts=[dict(path=path, sha256=sha256_bytes((case['root']/path).read_bytes())) for path in cases.ARTIFACTS],
            assertions=dict(permanent_scope_match_assertions=True, independently_parsed_csv_brief_ics=True,
                exact_prior_package_and_bindings_retained=True, requests_unsent=True,
                independent_condition_tamper_checks=(variant=='same')))
        records.append(record)
        print(json.dumps(dict(variant=variant, run_id=record['run_id'],
            status=record['outcome']['status'], package_acceptance=record['outcome']['package_acceptance'],
            match_status=feedback['match_status'], assertions='passed')), flush=True)
        args.results.write_bytes(json_bytes(dict(synthetic_only=True, organizational_authorization_claimed=False,
            baseline=str(args.baseline), baseline_run_id=first['run_id'],
            baseline_artifacts=[dict(path=path, sha256=sha256_bytes((args.baseline/path).read_bytes())) for path in cases.ARTIFACTS],
            variants=records, all_cases_complete=(len(records)==3))))


if __name__ == '__main__':
    main()
