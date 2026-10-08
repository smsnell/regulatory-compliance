"""Opt-in live U03 host check, outside default deterministic tests."""
import argparse
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'regulatory-change-impact-brief/scripts'))
from u03_harness import run_live

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--timeout',type=int,default=180)
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
root,outcome=run_live(args.output,args.timeout)
print(root)
print(outcome)
sys.exit(0 if outcome['status']=='complete' else 1)
