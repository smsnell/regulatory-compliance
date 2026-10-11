"""Attended seven-stage supervisor. Acquisition is fresh; interpretations are bounded."""
from copy import deepcopy
from pathlib import Path
import shutil

from .adapters import ReadAdapters
from .contracts import (CONTRACT_VERSION, SNAPSHOT_PATHS, STAGES, json_bytes, package_path,
                        parse_json, require, sha256_bytes)
from .evidence import EvidenceStore, _write
from .runtime import Providers, SKILL, output_directory, validate_config, writer_lock
from .snapshots import stage_records


def _fingerprints(store, config, chain):
    from .recovery import stage_fingerprints
    modules=[['runner.py','runtime.py','pipeline.py','snapshots.py','contracts.py','ids.py',
              'evidence.py','decisions.py','validation_cache.py','history.py','recovery.py'],
        ['normalize.py','source_manifest.py','adapters/reads.py','adapters/reports.py',
         'adapters/anonymous_sheets.py','adapters/readiness.py'],
        ['authority.py','authority_representations.py','interpretation.py'], ['reconcile.py'], ['impacts.py'], ['actions.py','reviews.py'],
        ['validate.py','renderers/csv_register.py','renderers/brief.py','renderers/calendar.py']]
    bases={stage:{'contract':CONTRACT_VERSION,'code':{m:sha256_bytes((SKILL/'scripts/rci'/m).read_bytes()) for m in names}}
        for stage,names in zip(STAGES,modules)}
    bases[STAGES[0]].update(scope=chain[0]['state']['systems_in_scope'],
        config={k:v for k,v in config.items() if k!='output_root'})
    scope_input=store.root/'analysis/scope-input.json'
    bases[STAGES[0]]['declared_scope_basis']=sha256_bytes(scope_input.read_bytes()) if scope_input.exists() else None
    references=[['schemas/runtime-config.schema.json','schemas/scope-input.schema.json',
                 'schemas/contracts.schema.json','contracts.md'],
        ['schemas/field-dictionary.schema.json','schemas/normalized-values.schema.json',
         'schemas/capture-accounting.schema.json','schemas/u08-capture-accounting.schema.json','schemas/linked-reports.schema.json'],
        ['authority-policy.md','schemas/authority-basis.schema.json','schemas/runtime-proposal.schema.json'],
        ['reconciliation.md','schemas/reconciliation-basis.schema.json','schemas/reconciliation-accounting.schema.json'],
        ['impacts.md','g3-fact-and-impact-contract.md'],[],[]]
    for stage,names in zip(STAGES,references):
        bases[stage]['references']={name:sha256_bytes((SKILL/'references'/name).read_bytes()) for name in names}
    bases[STAGES[2]]['skill_instructions']=sha256_bytes((SKILL/'SKILL.md').read_bytes())
    bases[STAGES[1]].update(captures=sorted([
        {'source':a['source_id'],'hash':a['content_hash'],'retrieval_status':a['retrieval_status'],
         'identity_check':a['identity_check'],'date_suitability':a.get('date_suitability')}
        for a in chain[1]['state']['attempts']],key=json_bytes),
        dictionary=sha256_bytes((SKILL/'references/field-dictionary.json').read_bytes()))
    bases[STAGES[5]]['feedback']={name:sha256_bytes((store.root/'analysis'/name).read_bytes())
        for name in ('feedback-input.json','reviewer-policy.json','authentication-context.json') if (store.root/'analysis'/name).exists()}
    return stage_fingerprints(bases)


def _retain_feedback(root, candidate, feedback_path, policy_path, authentication_path):
    if feedback_path is None:
        require(policy_path is None and authentication_path is None,'review policy/authentication requires feedback')
        return
    require(policy_path is not None and authentication_path is not None,
            'feedback requires separately authorized reviewer policy and authenticated operator context')
    for path,name in [(feedback_path,'feedback-input.json'),(policy_path,'reviewer-policy.json'),
                      (authentication_path,'authentication-context.json')]:
        require(not path.resolve().is_relative_to(root.resolve()),'feedback input overlaps managed output')
        _write(candidate,'analysis/'+name,path.read_bytes())
    value=parse_json(feedback_path.read_bytes())
    require(isinstance(value.get('feedback'),list),'feedback input requires feedback list')
    for payload in value['feedback']:
        reference=payload.get('reviewed_draft',{}) if isinstance(payload,dict) else {}
        claimed=payload.get('claimed_run_id') if isinstance(payload,dict) else None
        relative=reference.get('root')
        if not isinstance(claimed,str) or relative!='history/'+claimed: continue
        source=package_path(root,relative)
        if not source.is_dir(): continue  # Intake preserves an unmatched decision.
        target=package_path(candidate,relative)
        if target.exists(): continue
        from .history import inventory
        # Copy files individually through checked package paths; no outside symlink reads.
        from .evidence import _read
        target.mkdir(parents=True)
        for row in inventory(source):
            if row['sha256'] is not None:
                _write(target,row['path'],_read(source,row['path']))
        manifest=source/'.history-inventory.json'
        if manifest.is_file(): _write(target,'.history-inventory.json',manifest.read_bytes())


def run(config_path, *, scope_path=None, change_reason=None, supersedes_run_id=None,
        feedback_path=None, reviewer_policy_path=None, authentication_path=None,
        providers=None, reader_factory=None):
    from . import runtime
    from .runner import declared_scope, run_stages, ScopeUnavailable
    from .source_manifest import manifest
    from .authority import interpret_authority
    from .reconcile import interpret_reconciliation
    from .impacts import interpret_impacts
    from .actions import freeze_actions
    from .renderers import render_all
    from .validate import freeze_publication, validate_package
    from .history import inspect_current, recover_run_id, archive_current
    from .recovery import classify_change, promote_candidate
    config_raw=config_path.read_bytes();config=validate_config(parse_json(config_raw))
    root=output_directory(config['output_root'],config_path)
    runtime.preflight(config)
    providers=providers or Providers()
    scope_raw=scope_path.read_bytes() if scope_path is not None else None
    if scope_raw is not None:
        declared_scope(scope_raw)
        require(not scope_path.resolve().is_relative_to(root),'scope input overlaps output root')
    run_id=providers.run_id();candidate=root/'.staging'/run_id
    prior=None;reader=None;candidate_created=False
    affected_stage='output-lock';affected_outputs=['.writer.lock']
    try:
        with writer_lock(root):
            affected_stage='current-package-inspection'
            affected_outputs=list(SNAPSHOT_PATHS)+['impact-register.csv','compliance-brief.md','action-calendar.ics']
            inspection=inspect_current(root,validator=validate_package)
            prior=inspection.get('run_id')
            from .snapshots import INCOMPLETE_MARKER, validate_marker
            marker_path=root/INCOMPLETE_MARKER
            if marker_path.exists() or marker_path.is_symlink():
                marker=parse_json(marker_path.read_bytes())
                validate_marker(marker,'incomplete-marker',root)
                prior=marker['new_run_id']
            if supersedes_run_id is not None:
                require(prior in (None,supersedes_run_id),'explicit supersession disagrees with current occurrence')
                if prior is None:
                    retained=root/'.staging'/supersedes_run_id/'analysis/outcome.json'
                    require(retained.is_file() and parse_json(retained.read_bytes()).get('run_id')==supersedes_run_id,
                            'superseded occurrence is not retained')
                    prior=supersedes_run_id
            affected_stage='candidate-initialization'
            affected_outputs=[str(candidate.relative_to(root))]
            require(not candidate.parent.is_symlink(),'unsafe staging root')
            candidate.mkdir(parents=True,exist_ok=False);candidate_created=True
            store=EvidenceStore(candidate,run_id,providers)
            affected_outputs=['analysis/config.json']
            _write(candidate,affected_outputs[0],config_raw)
            if scope_raw is not None:
                affected_outputs=['analysis/scope-input.json']
                _write(candidate,affected_outputs[0],scope_raw)
            started=providers.now();reason=change_reason or (('Fresh full recomputation of current inputs' if inspection['accepted'] else 'Fresh recovery after failed or incomplete current package inspection') if prior else None)
            affected_outputs=['analysis/run-context.json']
            _write(candidate,affected_outputs[0],json_bytes(dict(run_id=run_id,mode='production',started_at=started,
                supersedes_run_id=prior,change_reason=reason)))
            affected_outputs=['analysis/prior-inspection.json']
            _write(candidate,affected_outputs[0],json_bytes(inspection))
            if feedback_path is not None and prior and (root/SNAPSHOT_PATHS[0]).is_file():
                affected_stage='feedback-archive';affected_outputs=['history/'+prior]
                archive_current(root,prior,created_at=providers.now())
            affected_stage='feedback-retention'
            affected_outputs=['analysis/feedback-input.json','analysis/reviewer-policy.json','analysis/authentication-context.json']
            _retain_feedback(root,candidate,feedback_path,reviewer_policy_path,authentication_path)
            affected_stage='scope-and-source-capture';affected_outputs=list(SNAPSHOT_PATHS[:2])
            reader=(reader_factory or ReadAdapters)(store)
            comparison,capture_status=run_stages(store,config,manifest(config),reader,config_bytes=config_raw,
                providers=providers,scope_bytes=scope_raw,supersedes_run_id=prior,change_reason=reason,
                linked_reports=True,legal_extracts=True,policy_extracts=True)
            require(capture_status!='failed','technical source capture failure')
            reader.close();reader=None
            affected_stage='authority-and-timing';affected_outputs=[SNAPSHOT_PATHS[2]]
            interpret_authority(store,config,timeout=600)
            affected_stage='evidence-reconciliation';affected_outputs=[SNAPSHOT_PATHS[3]]
            interpret_reconciliation(store,config,timeout=600)
            affected_stage='impact-analysis';affected_outputs=[SNAPSHOT_PATHS[4]]
            interpret_impacts(store,config,timeout=600)
            affected_stage='actions-and-approvals';affected_outputs=[SNAPSHOT_PATHS[5]]
            sixth=freeze_actions(store)
            affected_stage='publication-validation'
            affected_outputs=[SNAPSHOT_PATHS[6],'impact-register.csv','compliance-brief.md','action-calendar.ics']
            for name,raw in render_all(sixth['state']['export_model']).items(): _write(candidate,name,raw)
            final=freeze_publication(store)
            require(final['status']!='failed','final artifact validation failed')
            chain=validate_package(candidate)
            require(chain[0]['run_id']==run_id,'foreign candidate run')
            from datetime import datetime
            instant=lambda s:datetime.fromisoformat(s.replace('Z','+00:00'))
            require(all(instant(a['started_at'])>=instant(started) for a in chain[1]['state']['attempts']),
                    'source attempts predate invocation')
            fingerprints=_fingerprints(store,config,chain)
            previous_path=root/'analysis/stage-fingerprints.json'
            previous=parse_json(previous_path.read_bytes()) if previous_path.is_file() else None
            _write(candidate,'analysis/stage-fingerprints.json',json_bytes(fingerprints))
            _write(candidate,'analysis/recomputation.json',json_bytes(classify_change(previous,fingerprints)))
            outcome=dict(run_id=run_id,status=final['status'],publication_status=final['state']['publication_status'],
                reason='Seven-stage draft; review requests await authorized humans.',production_package=True,
                package_acceptance=final['state']['publication_status']=='validated',candidate=str(candidate.relative_to(root.parent)),
                supersedes_run_id=prior,missing_snapshots=[],missing_artifacts=[])
            _write(candidate,'analysis/outcome.json',json_bytes(outcome))
            affected_stage='package-promotion';affected_outputs=list(SNAPSHOT_PATHS)+affected_outputs[1:]
            promote_candidate(root,candidate,new_run_id=run_id,created_at=providers.now(),
                validator=validate_package,lock_held=True)
            return outcome
    except (ValueError,OSError,KeyboardInterrupt,TimeoutError) as error:
        outcome=dict(run_id=run_id,status='blocked' if isinstance(error,ScopeUnavailable) else 'failed',
            reason=str(error) or 'Execution interrupted',production_package=False,package_acceptance=False,
            candidate=str(candidate.relative_to(root.parent)),candidate_created=candidate_created,supersedes_run_id=prior,
            missing_snapshots=[p for p in SNAPSHOT_PATHS if not candidate_created or not (candidate/p).is_file()],
            missing_artifacts=[p for p in ('impact-register.csv','compliance-brief.md','action-calendar.ics') if not candidate_created or not (candidate/p).is_file()],
            affected_stage=affected_stage,affected_outputs=affected_outputs,
            recovery_action='Preserve this candidate and any current/history bytes; inspect the retained reason, attempt journal and host diagnostics, resolve the cause, then rerun the documented launcher with fresh source attempts and a new run ID.',
            next_owner='Operator',diagnostic_persistence='unavailable',diagnostic_record=None)
        # Only our successfully created isolated candidate is writable here. A
        # lock or mkdir failure must not create output or touch another occurrence.
        if candidate_created:
            path='analysis/failure-outcome.json' if (candidate/'analysis/outcome.json').exists() else 'analysis/outcome.json'
            outcome.update(diagnostic_persistence='retained',diagnostic_record=path)
            try:
                _write(candidate,path,json_bytes(outcome))
            except (OSError,ValueError) as storage_error:
                outcome.update(diagnostic_persistence='unavailable',diagnostic_record=None,
                               diagnostic_error=str(storage_error))
            else:
                try:
                    archive_current(candidate,run_id,created_at=providers.now())
                except (OSError,ValueError) as archive_error:
                    # The retained outcome remains valid even if an additional
                    # diagnostic archive cannot be written. Make no archive claim.
                    import sys
                    print('Diagnostic outcome retained; its archive could not be preserved: '+str(archive_error),file=sys.stderr)
        return outcome
    finally:
        if reader is not None:
            try:
                reader.close()
            except (OSError,ValueError) as close_error:
                # Cleanup must not erase the original failure/run context.
                import sys
                print('Source reader cleanup failed: '+str(close_error),file=sys.stderr)
