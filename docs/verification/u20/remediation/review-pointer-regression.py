"""Bounded E07 regression on an actual changed-date public package."""
import json
from pathlib import Path
import sys
sys.path[:0] = ['regulatory-change-impact-brief/scripts', 'tests']
from rci.contracts import parse_json
from rci.evidence import EvidenceStore
from rci.reviews import ReviewerPolicy, AuthenticationContext, process_feedback
from rci.snapshots import read_chain

root = Path(sys.argv[1])
chain = read_chain(root, count=6)
state = chain[5]['state']
envelope = parse_json((root / 'analysis/feedback-input.json').read_bytes())
records = process_feedback(EvidenceStore(root, chain[0]['run_id']), state['review_requests'],
    state['proposed_actions'], envelope['feedback'], carry_forward=True,
    policy=ReviewerPolicy.from_dict(parse_json((root / 'analysis/reviewer-policy.json').read_bytes())),
    authentication=AuthenticationContext.from_dict(parse_json((root / 'analysis/authentication-context.json').read_bytes())))
feedback, = records
assert feedback['authentication'] == 'verified' and feedback['match_status'] == 'unresolved'
assert feedback['subject_ids'] == [] and feedback['request_id'] is None and 'revalidation' not in feedback
assert any('changed relevant' in reason for reason in feedback['reasons'])
assert feedback.get('reviewed_draft') == envelope['feedback'][0]['reviewed_draft'], 'Quarantine lost verified prior-draft pointer'
assert feedback['claimed_artifacts'] == envelope['feedback'][0]['claimed_artifacts']
print(json.dumps(dict(run_id=chain[0]['run_id'], assertion='passed', match_status=feedback['match_status'],
    reviewed_draft=feedback['reviewed_draft'], claimed_artifacts=feedback['claimed_artifacts'])))
