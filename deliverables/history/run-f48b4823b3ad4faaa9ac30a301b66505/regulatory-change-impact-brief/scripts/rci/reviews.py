"""U13 review preparation and explicitly authenticated, version bound feedback.

Payloads supply claims only. Policy, identity proof and condition resolution are
separate operator/channel inputs. This module never sends a review request.
"""
from copy import deepcopy
from dataclasses import dataclass
import re
from uuid import uuid4

from .contracts import (ContractError, SNAPSHOT_PATHS, json_bytes, package_path,
                        parse_json, require, sha256_bytes, validate_schema)
from .ids import new_record_id
from .snapshots import (ARTIFACT_PATHS, _instant, _review_subject_key,
                        _reviewed_request, read_chain, stage_records)


@dataclass(frozen=True)
class ReviewerAuthorization:
    identity: str
    roles: tuple[str, ...]
    channels: tuple[str, ...]
    system_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReviewerPolicy:
    reviewers: tuple[ReviewerAuthorization, ...]

    @classmethod
    def from_dict(cls, value):
        require(set(value) == {'reviewers'}, 'reviewer policy requires reviewers')
        reviewers = []
        for item in value['reviewers']:
            require(set(item) == {'identity', 'roles', 'channels', 'system_ids'},
                    'reviewer authorization fields differ')
            require(isinstance(item['identity'], str) and item['identity'].strip(), 'identity required')
            for key in ('roles', 'channels', 'system_ids'):
                require(isinstance(item[key], list) and item[key] and
                        all(isinstance(x, str) and x.strip() for x in item[key]), 'authorization requires ' + key)
            require(set(item['roles']) <= {'Legal', 'Operations', 'system-owner'}, 'unknown reviewer role')
            reviewers.append(ReviewerAuthorization(item['identity'], tuple(item['roles']),
                                                  tuple(item['channels']), tuple(item['system_ids'])))
        require(len({r.identity for r in reviewers}) == len(reviewers), 'ambiguous reviewer identity')
        return cls(tuple(reviewers))


@dataclass(frozen=True)
class AuthenticationContext:
    identity: str
    channel: str
    basis: str

    @classmethod
    def from_dict(cls, value):
        require(set(value) == {'identity', 'channel', 'basis'} and
                all(isinstance(x, str) and x.strip() for x in value.values()),
                'authenticated operator/channel proof requires identity, channel and basis')
        return cls(**value)


@dataclass(frozen=True)
class ConditionResolution:
    conditions: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    satisfied: bool


@dataclass(frozen=True)
class CarryForwardContext:
    reviewed_draft: dict
    upstream: tuple[dict, ...]
    subject_bindings: tuple[dict, ...]
    reviewed_records: dict
    current_records: dict
    condition_resolution: ConditionResolution | None = None


def create_review_request(*, run_id, draft_version, subject_ids, subject_system_ids,
                          source_versions, evidence_ids, question, required_reviewer,
                          summary=None):
    record = dict(id=new_record_id(run_id, 6, 'review-request'), record_type='review-request',
                  summary=summary or 'Review proposed draft decision: ' + question,
                  evidence_ids=sorted(set(evidence_ids)), request_id='review-' + uuid4().hex,
                  subject_ids=sorted(set(subject_ids)), subject_system_ids=sorted(set(subject_system_ids)),
                  run_id=run_id, draft_version=draft_version, source_versions=sorted(set(source_versions)),
                  question=question, required_reviewer=required_reviewer,
                  delivery_status='not-sent', delivery_evidence_ids=[])
    validate_schema(record, 'review-request')
    return record


def _strings(value):
    return list(dict.fromkeys(x for x in value if isinstance(x, str) and x.strip())) if isinstance(value, list) else []


def _candidate(run_id, payload):
    require(isinstance(payload, dict), 'feedback must be an object')
    def text(key):
        value = payload.get(key)
        return value if isinstance(value, str) and value.strip() else None
    artifacts = payload.get('claimed_artifacts', [])
    artifacts = [deepcopy(a) for a in artifacts if isinstance(a, dict) and set(a) == {'path', 'sha256'}
                 and isinstance(a['path'], str) and a['path'].strip() and isinstance(a['sha256'], str)
                 and re.fullmatch(r'sha256:[0-9a-f]{64}', a['sha256'])] if isinstance(artifacts, list) else []
    at = text('reviewer_response_at')
    if at:
        try:
            require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})', at)),
                    'response must be RFC3339')
            require(_instant(at).tzinfo is not None, 'response timezone required')
        except (ValueError, ContractError):
            at = None
    record = dict(id=new_record_id(run_id, 6, 'feedback'), record_type='feedback',
                  summary='Unresolved reviewer feedback', evidence_ids=[],
                  responder_identity=text('responder_identity') or 'unidentified',
                  responder_role=payload.get('responder_role') if payload.get('responder_role') in
                  ('Legal', 'Operations', 'system-owner') else 'Legal',
                  reviewer_response_at=at, outcome=payload.get('outcome') if payload.get('outcome') in
                  ('approved', 'rejected', 'conditional', 'unresolved') else 'unresolved',
                  reasons=_strings(payload.get('reasons')) or ['Feedback requires authentication and version matching'],
                  conditions=_strings(payload.get('conditions')), authentication='unverified', authentication_basis=None,
                  claimed_subject_ids=_strings(payload.get('claimed_subject_ids')),
                  claimed_request_id=text('claimed_request_id'), claimed_run_id=text('claimed_run_id'),
                  claimed_draft_version=text('claimed_draft_version'),
                  claimed_source_versions=_strings(payload.get('claimed_source_versions')),
                  claimed_artifacts=artifacts, subject_ids=[], request_id=None, match_status='unresolved')
    validate_schema(record, 'feedback')
    return record


def _quarantine(record, reason):
    record = deepcopy(record)
    record['summary'] = 'Unresolved reviewer feedback: ' + reason
    record['reasons'] = list(dict.fromkeys(record['reasons'] + [reason]))
    record['subject_ids'], record['request_id'], record['match_status'] = [], None, 'unresolved'
    record.pop('revalidation', None)
    validate_schema(record, 'feedback')
    return record


def _basis(record, index, seen=()):
    """Compare relevant content exactly while remapping run-local graph IDs."""
    require(record['id'] not in seen, 'cyclic review basis')
    seen = (*seen, record['id'])
    ignored = {'id', 'local_reference', 'capture_id', 'attempt_id', 'attempt_ids',
               'approval_status', 'feedback_ids', 'created_at', 'retrieved_at'}
    def normalize(value):
        if isinstance(value, str) and value in index:
            return _basis(index[value], index, seen)
        if isinstance(value, list):
            return sorted((normalize(x) for x in value), key=lambda x: json_bytes({'value': x}))
        if isinstance(value, dict):
            # Fresh reads change acquisition time even when the reviewed
            # assertion and retained content are unchanged. Nested assertions
            # retain their factual observation dates and all other meanings.
            return {key: normalize(v) for key, v in value.items() if key != 'retrieved_at'}
        return value
    return {key: normalize(value) for key, value in record.items() if key not in ignored}


def _evidence(record, index, seen=None):
    seen = set() if seen is None else seen
    if record['id'] in seen:
        return set()
    seen.add(record['id'])
    found = {record['id']} if record['record_type'] == 'evidence' else set()
    for key in ('evidence_ids', 'fact_ids', 'impact_ids', 'subject_ids', 'rule_id'):
        values = record.get(key, [])
        if isinstance(values, str):
            values = [values]
        for identity in values:
            if identity in index:
                found.update(_evidence(index[identity], index, seen))
    return found


def match_feedback(*, run_id, request, reviewed_request, review_binding, payload,
                   policy, authentication, current_time, reviewed_at, carry_forward=None):
    """Only explicit revalidation can resolve feedback into a newer draft.

    The binding and record indexes are trusted inputs verified from disk by
    process_feedback. Pure callers must provide equivalent verified fixtures.
    """
    record = _candidate(run_id, payload)
    try:
        for field in ('responder_identity', 'responder_role', 'outcome', 'claimed_subject_ids',
                      'claimed_request_id', 'claimed_run_id', 'claimed_draft_version',
                      'claimed_source_versions', 'claimed_artifacts', 'reviewer_response_at',
                      'conditions'):
            require(field in payload and payload[field] == record[field], 'malformed or missing feedback claim: ' + field)
        require(isinstance(payload.get('reasons'), list) and
                payload['reasons'] == _strings(payload['reasons']) and
                bool(payload['reasons'] or record['conditions']), 'feedback requires actual reasons or conditions')
        validate_schema(request, 'review-request')
        validate_schema(reviewed_request, 'review-request')
        require(authentication is not None and isinstance(authentication, AuthenticationContext),
                'missing authenticated identity proof')
        require(authentication.identity == record['responder_identity'] and authentication.basis.strip(),
                'authenticated identity differs from responder claim')
        identities = [r for r in policy.reviewers if r.identity == authentication.identity]
        require(len(identities) == 1 and authentication.channel in identities[0].channels,
                'identity or channel is not authorized')
        allowed = identities[0]
        require(record['responder_role'] in allowed.roles and
                record['responder_role'] == request['required_reviewer'] == reviewed_request['required_reviewer'],
                'wrong authorized reviewer role')
        require(set(request['subject_system_ids']) <= set(allowed.system_ids) and
                set(reviewed_request['subject_system_ids']) <= set(allowed.system_ids), 'reviewer outside authorized scope')
        record['authentication'], record['authentication_basis'] = 'verified', authentication.channel + ': ' + authentication.basis
        require(record['claimed_request_id'] == reviewed_request['request_id'] == review_binding['request_id'], 'wrong request')
        require(record['claimed_run_id'] == reviewed_request['run_id'] == review_binding['run_id'] and
                record['claimed_draft_version'] == reviewed_request['draft_version'] == review_binding['draft_version'],
                'wrong reviewed run or superseded draft version')
        require(record['claimed_subject_ids'] and
                set(record['claimed_subject_ids']) <= set(reviewed_request['subject_ids']), 'wrong reviewed subject')
        require(sorted(record['claimed_source_versions']) == sorted(reviewed_request['source_versions']), 'wrong source version')
        require(len(review_binding['artifacts']) == len(record['claimed_artifacts']) == 3 and
                {a['path'] for a in review_binding['artifacts']} == ARTIFACT_PATHS and
                sorted(record['claimed_artifacts'], key=lambda a: a['path']) ==
                sorted(review_binding['artifacts'], key=lambda a: a['path']), 'wrong artifact binding or hash')
        require(record['reviewer_response_at'] is not None and
                _instant(reviewed_at) <= _instant(record['reviewer_response_at']) <= _instant(current_time),
                'response missing or outside reviewed/current time boundary')
        require(record['outcome'] != 'conditional' or bool(record['conditions']), 'conditional feedback has no conditions')
        require(carry_forward is not None, 'older draft feedback awaits explicit revalidation')
        context = carry_forward
        require(run_id == request['run_id'] and run_id != reviewed_request['run_id'], 'carry-forward must target a new run')
        require(context.reviewed_draft['root'] == 'history/' + reviewed_request['run_id'], 'wrong retained reviewed draft')
        validate_schema(context.reviewed_draft, 'reviewed-draft')
        pairs = list(context.subject_bindings)
        require(len(pairs) == len(record['claimed_subject_ids']) and
                {p['reviewed_id'] for p in pairs} == set(record['claimed_subject_ids']) and
                len({p['current_id'] for p in pairs}) == len(pairs) and
                {p['current_id'] for p in pairs} <= set(request['subject_ids']), 'wrong current subject correspondence')
        require(sorted(request['source_versions']) == sorted(reviewed_request['source_versions']),
                'changed relevant source versions')
        require(sorted(request['subject_system_ids']) == sorted(reviewed_request['subject_system_ids']), 'changed relevant scope')
        evidence = set()
        for pair in pairs:
            old, current = context.reviewed_records[pair['reviewed_id']], context.current_records[pair['current_id']]
            require(_review_subject_key(old) is not None and _review_subject_key(old) == _review_subject_key(current),
                    'changed semantic subject')
            require(_basis(old, context.reviewed_records) == _basis(current, context.current_records),
                    'changed relevant facts, dates, rule basis or conditions')
            evidence.update(_evidence(current, context.current_records))
        require(evidence, 'revalidation has no current claim evidence')
        for identity in evidence:
            require(context.current_records[identity]['record_type'] == 'evidence', 'invalid revalidation evidence')
        resolution = context.condition_resolution
        if resolution is not None:
            require(set(resolution.conditions) == set(record['conditions']), 'condition resolution belongs to another decision')
            for identity in resolution.evidence_ids:
                require(identity in context.current_records and
                        context.current_records[identity]['record_type'] == 'evidence', 'conditions lack current evidence')
        record['subject_ids'] = sorted(p['current_id'] for p in pairs)
        record['request_id'], record['match_status'] = request['request_id'], 'matched'
        record['summary'] = 'Authenticated feedback explicitly revalidated for current proposed draft'
        record['reviewed_draft'] = deepcopy(context.reviewed_draft)
        record['revalidation'] = dict(current_run_id=run_id, current_request_id=request['request_id'],
            current_draft_version=request['draft_version'], current_source_versions=request['source_versions'],
            reviewed_stage07_sha256=context.reviewed_draft['stage07']['sha256'], upstream=deepcopy(list(context.upstream)),
            subject_bindings=deepcopy(pairs), checks={key: dict(result='passed', evidence_ids=sorted(evidence),
                reason='Explicit exact relevant basis comparison passed; reviewer conditions remain attached')
                for key in ('facts', 'source_versions', 'scope', 'conditions')})
        validate_schema(record, 'feedback')
        return record
    except (ContractError, KeyError, TypeError, ValueError, AttributeError) as error:
        return _quarantine(record, str(error))


def approval_for_feedback(*, run_id, request, feedback=None, condition_resolution=None):
    """Unanswered, mismatched and unsatisfied conditional decisions stay pending."""
    status, feedback_ids, subjects = 'pending', [], request['subject_ids']
    valid = (feedback is not None and feedback['authentication'] == 'verified' and
             feedback['match_status'] == 'matched' and feedback['request_id'] == request['request_id'] and
             feedback['responder_role'] == request['required_reviewer'] and feedback['subject_ids'] and
             set(feedback['subject_ids']) <= set(request['subject_ids']))
    conditions_ok = False
    if valid:
        subjects, feedback_ids = feedback['subject_ids'], [feedback['id']]
        conditions_ok = (not feedback['conditions'] or (condition_resolution is not None and
            set(condition_resolution.conditions) == set(feedback['conditions']) and
            condition_resolution.satisfied is True and bool(condition_resolution.evidence_ids)))
        if feedback['outcome'] == 'rejected':
            status = 'rejected'
        elif feedback['outcome'] in {'approved', 'conditional'} and conditions_ok:
            status = 'approved'
    record = dict(id=new_record_id(run_id, 6, 'approval'), record_type='approval',
                  summary='Reviewer decision for proposed draft: ' + status, evidence_ids=request['evidence_ids'],
                  subject_ids=subjects, required_reviewer=request['required_reviewer'], status=status,
                  request_id=request['request_id'], feedback_ids=feedback_ids)
    if valid and feedback['conditions'] and conditions_ok:
        record.update(conditions_satisfied=True, condition_evidence_ids=list(condition_resolution.evidence_ids))
    validate_schema(record, 'approval')
    return record


def process_feedback(store, requests, actions, inputs, *, policy, authentication, carry_forward=False,
                     condition_resolution=None):
    """Disk-backed intake. Missing archives or ambiguous subjects are quarantined.

    inputs is a list of untrusted payload dictionaries. reviewed_draft points to
    retained history snapshots; every snapshot and final artifact is verified.
    Separate authenticated input is valid only for this supplied intake batch.
    """
    chain = read_chain(store.root, count=5)
    current = {r['id']: r for s in chain for r in stage_records(s)}
    current.update({r['id']: r for r in [*actions, *requests]})
    upstream = tuple(dict(snapshot_id=s['snapshot_id'], path=SNAPSHOT_PATHS[i],
                          sha256=sha256_bytes(package_path(store.root, SNAPSHOT_PATHS[i]).read_bytes()))
                     for i, s in enumerate(chain))
    outputs = []
    for payload in inputs:
        record = _candidate(store.run_id, payload)
        try:
            require(isinstance(payload.get('reviewed_draft'), dict), 'missing retained reviewed draft')
            record['reviewed_draft'] = deepcopy(payload['reviewed_draft'])
            validate_schema(record['reviewed_draft'], 'reviewed-draft')
            previous, old_request = _reviewed_request(record, store.root, store.run_id)
            archive = package_path(store.root, record['reviewed_draft']['root'])
            final = parse_json(package_path(archive, SNAPSHOT_PATHS[6]).read_bytes())
            binding = next(b for b in final['state']['review_bindings'] if b['request_id'] == old_request['request_id'])
            matching = []
            for request in requests:
                if request['required_reviewer'] != old_request['required_reviewer']:
                    continue
                pairs = []
                for old_id in record['claimed_subject_ids']:
                    key = _review_subject_key(previous[old_id])
                    matches = [identity for identity in request['subject_ids']
                               if key is not None and _review_subject_key(current[identity]) == key]
                    if len(matches) != 1:
                        break
                    pairs.append(dict(reviewed_id=old_id, current_id=matches[0]))
                if len(pairs) == len(record['claimed_subject_ids']) and pairs:
                    matching.append((request, pairs))
            require(len(matching) == 1, 'missing or ambiguous current review request')
            request, pairs = matching[0]
            context = CarryForwardContext(record['reviewed_draft'], upstream, tuple(pairs), previous, current,
                                          condition_resolution) if carry_forward else None
            outputs.append(match_feedback(run_id=store.run_id, request=request, reviewed_request=old_request,
                review_binding=binding, payload=payload, policy=policy, authentication=authentication,
                current_time=store.providers.now(), reviewed_at=final['created_at'], carry_forward=context))
        except (ContractError, KeyError, TypeError, ValueError, StopIteration, OSError) as error:
            record.pop('reviewed_draft', None)
            outputs.append(_quarantine(record, str(error)))
    return outputs
