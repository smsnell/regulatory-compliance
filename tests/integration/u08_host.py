"""Opt-in U08 actual invoking-skill check with synthetic report transport.

No live report route or real company report content is claimed by this check.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'tests'))
sys.path.insert(0, str(REPO/'regulatory-change-impact-brief/scripts'))
from runtime.test_u08 import CONFIG, ReportsReplay
from rci.contracts import json_bytes, parse_json
from rci.runner import capture_slice, validate_slice
from rci.evidence import EvidenceStore

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
config = deepcopy(CONFIG)
config['output_root'] = 'candidates'
config['host']['owner'] = 'U08 test operator (synthetic report, no production package)'
path = args.output/'config.json'
path.write_bytes(json_bytes(config))
with patch('rci.runtime.REPO', args.output):
    outcome = capture_slice(path, linked_reports=True, interpretation=True, reader_factory=ReportsReplay)
root = args.output/outcome['candidate']
validate_slice(EvidenceStore(root, outcome['run_id']))
print(root)
print(outcome)
if outcome.get('interpretation_disposition') in {'proposed', 'unresolved'}:
    handoff = parse_json((root/'analysis/accepted-candidates.json').read_bytes())
    print({'helper_disposition':handoff['disposition'], 'candidate_count':len(handoff['candidates']),
           'synthetic_report':True, 'production_package':False})
else:
    sys.exit(1)
