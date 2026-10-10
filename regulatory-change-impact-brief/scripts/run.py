#!/usr/bin/env python3
"""Public production launcher; no fixture or replay switches."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--capture-slice', action='store_true',
                        help='Run only U07 Stage 01/02 in an isolated candidate')
    parser.add_argument('--scope', type=Path, help='Authorized declared scope JSON (capture slice only)')
    parser.add_argument('--linked-reports', action='store_true', help='Extend the capture slice with U08 linked report reads')
    parser.add_argument('--interpret-reports', action='store_true', help='Invoke the restricted skill for captured U08 reports')
    parser.add_argument('--authority', action='store_true', help='Capture legal extracts and run U09 through Stage 03 only')
    parser.add_argument('--reconcile', action='store_true', help='Run authority then U10 reconciliation through Stage 04 only')
    parser.add_argument('--supersedes-run-id', help='Retained occurrence being retried (capture slice only)')
    parser.add_argument('--change-reason', help='Reason for a new scope or retry')
    args = parser.parse_args()
    try:
        if sys.version_info < (3,12):
            raise ValueError('Python 3.12 or later required')
        if args.capture_slice:
            from rci.runner import capture_slice
            outcome = capture_slice(args.config, scope_path=args.scope,
                                    supersedes_run_id=args.supersedes_run_id,
                                    change_reason=args.change_reason,
                                    linked_reports=args.linked_reports or args.interpret_reports or args.authority,
                                    interpretation=args.interpret_reports, authority=args.authority,
                                    reconciliation=args.reconcile)
        else:
            if args.scope or args.supersedes_run_id or args.change_reason or args.linked_reports or args.interpret_reports or args.authority or args.reconcile:
                raise ValueError('scope/retry options require --capture-slice')
            from rci.runtime import production
            outcome = production(args.config)
    except (ImportError, OSError, ValueError, TimeoutError) as error:
        # Config values/credentials are never echoed by validation.
        outcome = {'status':'failed','reason':str(error),'production_package':False}
    print(json.dumps(outcome))
    return {'complete':0,'partial':2,'blocked':3,'failed':1}[outcome['status']]


if __name__ == '__main__':
    sys.exit(main())
