"""T07: benign register layout changes survive the entire public workflow."""
import csv
from unittest.mock import patch

from rci.validate import validate_package
from runtime.test_u17_complete import FullReplay, execute_full


def test_register_reordering_and_extra_column_preserve_final_draft_meaning(tmp_path):
    class Reordered(FullReplay):
        def table(self, table):
            rows=super().table(table)
            return [list(reversed(rows[0]))+['unrelated extra']] + [
                list(reversed(row))+['ignored layout metadata'] for row in reversed(rows[1:])]

    original=tmp_path/'original';original.mkdir()
    changed=tmp_path/'reordered';changed.mkdir()
    first,first_root,first_exit,_=execute_full(original)
    with patch('runtime.test_u17_complete.FullReplay',Reordered):
        second,second_root,second_exit,_=execute_full(changed)
    assert first_exit==second_exit==0
    assert first['status']==second['status']=='complete'
    assert first['run_id']!=second['run_id']
    before,after=validate_package(first_root),validate_package(second_root)
    def fields(chain):
        return sorted((r['source_id'],r['source_business_id'],r['values']['fields'])
                      for r in chain[1]['state']['normalized_rows'])
    assert fields(before)==fields(after)
    assert {a['attempt_key'] for a in before[1]['state']['attempts']}.isdisjoint(
        a['attempt_key'] for a in after[1]['state']['attempts'])
    def meanings(root):
        with (root/'impact-register.csv').open(newline='') as stream:
            rows=list(csv.DictReader(stream))
        columns=('impact_id','system_id','rule_ref','state','owner','proposed_action',
                 'proposed_due_date','approval_status','action_ids','basis_type','assigned_review_date')
        return sorted(tuple(row[c] for c in columns) for row in rows)
    assert meanings(first_root)==meanings(second_root)
    assert len(meanings(second_root))==16
    # No run/retrieval/hash equality is expected: the source bytes really changed.
    for source in ('SYSTEMS','EVIDENCE','CALENDAR'):
        hashes=lambda c:{a['content_hash'] for a in c[1]['state']['attempts']
                         if a['source_id']==source and a['retrieval_status']=='retrieved'}
        assert hashes(before)!=hashes(after)
    for root,chain in ((first_root,before),(second_root,after)):
        assert all(r['delivery_status']=='not-sent' for r in chain[5]['state']['review_requests'])
        assert all(a['approval_status']=='pending' for a in chain[5]['state']['proposed_actions'])
        assert chain[-1]['state']['publication_status']=='validated'
