#!/usr/bin/env python3
"""Public production launcher; no fixture or replay switches."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    try:
        if sys.version_info < (3,12):
            raise ValueError('Python 3.12 or later required')
        from rci.runtime import production
        outcome = production(args.config)
    except (ImportError, OSError, ValueError, TimeoutError) as error:
        # Config values/credentials are never echoed by validation.
        outcome = {'status':'failed','reason':str(error),'production_package':False}
    print(json.dumps(outcome))
    return {'complete':0,'partial':2,'blocked':3,'failed':1}[outcome['status']]


if __name__ == '__main__':
    sys.exit(main())
