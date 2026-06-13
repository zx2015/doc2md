import re

def collapse_whitespace(text: str) -> str:
    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip trailing spaces on each line
    text = '\n'.join([line.rstrip() for line in text.split('\n')])
    return text
