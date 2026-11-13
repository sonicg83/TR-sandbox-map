import re


_PREFIX = re.compile(r'\s*INSERT\s+INTO\s+`?x_world`?\s+VALUES\s*\(', re.I)


def parse_map_sql(text: str) -> list[dict]:
    records = []
    i = 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i == len(text):
            break
        match = _PREFIX.match(text, i)
        if not match:
            raise ValueError(f'Unsupported SQL at character {i}')
        i = match.end()
        values = []
        while True:
            while i < len(text) and text[i].isspace():
                i += 1
            if i >= len(text):
                raise ValueError('Truncated SQL')
            if text[i] == "'":
                i += 1
                value = ''
                while i < len(text):
                    if text[i] == '\\':
                        i += 1
                        if i >= len(text):
                            raise ValueError('Truncated escape')
                        value += {'n': '\n', 'r': '\r', 't': '\t', '0': '\0'}.get(text[i], text[i])
                        i += 1
                    elif text[i] == "'":
                        if i + 1 < len(text) and text[i + 1] == "'":
                            value += "'"
                            i += 2
                        else:
                            i += 1
                            break
                    else:
                        value += text[i]
                        i += 1
                else:
                    raise ValueError('Unterminated string')
            else:
                start = i
                while i < len(text) and text[i] not in ',)':
                    i += 1
                token = text[start:i].strip()
                if token.upper() == 'NULL':
                    value = None
                elif token.upper() in ('TRUE', 'FALSE'):
                    value = token.upper() == 'TRUE'
                elif re.fullmatch(r'-?\d+', token):
                    value = int(token)
                else:
                    raise ValueError(f'Invalid value: {token}')
            values.append(value)
            while i < len(text) and text[i].isspace():
                i += 1
            if i >= len(text):
                raise ValueError('Truncated SQL')
            if text[i] == ',':
                i += 1
                continue
            if text[i:i+2] != ');':
                raise ValueError('Invalid SQL terminator')
            i += 2
            break
        if len(values) != 16 or not all(type(values[n]) is int for n in (1, 2, 3, 4)):
            raise ValueError('Unexpected x_world record')
        records.append(dict(x=values[1], y=values[2], tribe=values[3], village_id=values[4], village_name=values[5], player_id=values[6], player_name=values[7], alliance_id=values[8], alliance_name=values[9], population=values[10], capital=values[12]))
    if not records:
        raise ValueError('No records')
    return records
