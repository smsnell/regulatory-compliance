"""Pure draft renderers; callers own filesystem writes."""
from .csv_register import render as csv_register
from .brief import render as brief
from .calendar import render as calendar


def render_all(model):
    return {'impact-register.csv': csv_register(model),
            'compliance-brief.md': brief(model), 'action-calendar.ics': calendar(model)}
