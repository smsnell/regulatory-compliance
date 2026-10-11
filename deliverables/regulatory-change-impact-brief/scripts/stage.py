#!/usr/bin/env python3
"""U03 deterministic exchange helper, invoked by the skill, not a supervisor."""
import argparse
import json
import os
from pathlib import Path
import sys
from rci.contracts import (json_bytes, parse_json, require, sha256_bytes,
                           validate_interpretation)
from rci.runtime import Providers
from rci.snapshots import read_chain


def submit(root, proposal_path):
    require(os.environ.get('RCI_CHILD_RUN') == root.name, 'stage requires active host run')
    request_bytes = (root/'analysis/request.json').read_bytes()
    request = parse_json(request_bytes)
    require(request['run_id'] == root.name, 'wrong helper run')
    proposal_bytes = proposal_path.read_bytes()
    proposal = parse_json(proposal_bytes)
    require(set(proposal) == {'disposition','diagnostic','candidates'}, 'invalid proposal fields')
    # Retain the exact agent output before constructing/validating its envelope.
    with (root/'analysis/proposal.json').open('xb') as stream:
        stream.write(proposal_bytes)
    response = {**proposal,'schema_version':'rci-interpretation-response/1',
                'run_id':request['run_id'],'stage':request['stage'],'packet_id':request['packet_id'],
                'packet_sha256':sha256_bytes(request_bytes),'responded_at':Providers().now(),
                'metadata':request['metadata']}
    raw = json_bytes(response)
    with (root/'analysis/response.json').open('xb') as stream:
        stream.write(raw)
    result = validate_interpretation(request_bytes, raw, root=root, run_id=request['run_id'],
                                    stage=request['stage'], upstream=read_chain(root,count=2))
    return {'disposition':result.disposition,'reason':result.reason,
            'response_sha256':sha256_bytes(raw),'production_package':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['submit','submit-report','submit-authority','submit-reconciliation','submit-impact','block'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--proposal',type=Path)
    args=parser.parse_args()
    try:
        root=args.root.resolve()
        if args.operation=='block':
            require(os.environ.get('RCI_CHILD_RUN')==root.name,'stage requires active host run')
            context=parse_json((root/'analysis/run-context.json').read_bytes())
            require(context['run_id']==root.name and context['mode']=='production-skeleton','wrong helper context')
            result={'run_id':root.name,'status':'blocked',
                    'reason':'U03 skeleton: live stage engines are not implemented'}
            with (root/'analysis/stage-outcome.json').open('xb') as stream:
                stream.write(json_bytes(result))
        else:
            require(args.proposal is not None,'proposal required for submit')
            if args.operation == 'submit-impact':
                require(os.environ.get('RCI_CHILD_RUN') == root.name, 'stage requires active host run')
                from rci.evidence import EvidenceStore
                from rci.impacts import submit_impact
                result = submit_impact(EvidenceStore(root, root.name), args.proposal.read_bytes())
            elif args.operation == 'submit-reconciliation':
                require(os.environ.get('RCI_CHILD_RUN') == root.name, 'stage requires active host run')
                from rci.evidence import EvidenceStore
                from rci.reconcile import submit_reconciliation
                result = submit_reconciliation(EvidenceStore(root, root.name), args.proposal.read_bytes())
            elif args.operation == 'submit-authority':
                require(os.environ.get('RCI_CHILD_RUN') == root.name, 'stage requires active host run')
                from rci.authority import submit_authority
                result = submit_authority(root, args.proposal.read_bytes())
            elif args.operation == 'submit-report':
                require(os.environ.get('RCI_CHILD_RUN') == root.name, 'stage requires active host run')
                from rci.interpretation import submit_report
                result = submit_report(root, args.proposal.read_bytes())
            else:
                result=submit(root,args.proposal)
    except (ValueError,OSError) as error:
        print(json.dumps({'status':'failed','reason':str(error)}))
        return 1
    print(json.dumps(result))
    return 0 if result.get('disposition')=='proposed' else 3


if __name__=='__main__':
    sys.exit(main())
