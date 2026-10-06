from ..schemas import Notes


def notes_markdown(notes: Notes):
    parts = ['## Summary', notes.summary or 'Not specified']
    for title, entries in [('Key Discussion Points', notes.key_points), ('Decisions', notes.decisions)]:
        parts += [f'## {title}', '\n'.join(f'- {value}' for value in entries) or 'None recorded.']
    parts += ['## Action Items', '\n'.join(
        f'- [{"x" if a.completed else " "}] {a.task}\n  Owner: {a.owner}\n  Deadline: {a.deadline}'
        for a in notes.action_items) or 'None recorded.']
    for title, entries in [('Open Questions', notes.open_questions), ('Important Dates', notes.important_dates)]:
        parts += [f'## {title}', '\n'.join(f'- {value}' for value in entries) or 'None recorded.']
    return '\n\n'.join(parts) + '\n'
