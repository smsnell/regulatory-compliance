"""RFC 5545 all-day tentative proposals, serialized by the pinned library."""
from datetime import date, datetime, timedelta
from icalendar import Calendar, Event


def render(model):
    calendar = Calendar()
    calendar.add('prodid', '-//Quillhaven//Regulatory Draft Actions//EN')
    calendar.add('version', '2.0')
    for a in sorted(model['actions'], key=lambda a:a['action_id']):
        if a['proposed_due_date'] is None: continue
        event = Event()
        event.add('uid', a['action_id']+'@regulatory-change-impact-brief')
        event.add('dtstamp', datetime.fromisoformat(model['created_at'].replace('Z','+00:00')))
        day=date.fromisoformat(a['proposed_due_date'])
        event.add('dtstart',day)
        event.add('dtend',day+timedelta(days=1))
        event.add('summary',a['summary'])
        event.add('status','TENTATIVE')
        event.add('description','\n'.join([
            'Action: '+a['action_id'], 'System: '+a['system_id'],
            'Responsible role: '+(a['owner'] or 'Unresolved; owner confirmation required'),
            'Source/decision basis: '+';'.join(a.get('source_basis', [])),
            'Date basis: '+a['date_basis'], 'Approval: '+a['approval_status'],
            'Run: '+model['run_id'], 'Evidence: '+';'.join(a['evidence_ids']),
            'Draft proposal; human review required.']))
        calendar.add_component(event)
    return calendar.to_ical()
