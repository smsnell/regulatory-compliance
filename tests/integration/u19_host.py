"""Opt-in real selected-host evaluation through the public launcher.

Only transport is deterministic synthetic data. No manually supplied interpretation,
fixture production switch, live legal conclusion, or external write is introduced.
"""
import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch

sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'tests'),str(REPO/'regulatory-change-impact-brief/scripts')]
from runtime.test_u10 import CompanyReplay
from runtime.test_u07 import CONFIG, DECLARED
from rci.contracts import json_bytes, parse_json
from rci.runtime import SKILL

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
config=deepcopy(CONFIG);config['output_root']='deliverables'
config['host']['owner']='Mike: authorized synthetic acceptance evaluation'
path=args.output/'config.json';path.write_bytes(json_bytes(config))
scope=args.output/'scope.json';scope.write_bytes(json_bytes(DECLARED))
spec=importlib.util.spec_from_file_location('public_launcher',SKILL/'scripts/run.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
with patch('rci.runtime.REPO',args.output.resolve()),patch('rci.pipeline.ReadAdapters',CompanyReplay), \
     patch.object(sys,'argv',['run.py','--config',str(path),'--scope',str(scope)]):
    result=launcher.main()
# The real exit meaning is retained; blocked synthetic authority is an honest output.
print('public_exit',result)
sys.exit(0 if result in (0,2,3) and (args.output/'deliverables/snapshots/07-publication-validation.json').is_file() else 1)
