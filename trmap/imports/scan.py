import json


def parse_scan_json(text: str) -> list[dict]:
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or set(data) != {'village', 'oasis', 'landscape'}:
            raise ValueError('Invalid scan categories')
        result = []
        seen = set()
        for category, entries in data.items():
            if not isinstance(entries, list):
                raise ValueError('Expected list')
            for entry in entries:
                if not isinstance(entry, dict) or type(entry.get('x')) is not int or type(entry.get('y')) is not int:
                    raise ValueError('Invalid coordinates')
                key = entry['x'], entry['y']
                if key in seen:
                    raise ValueError('Duplicate coordinate')
                seen.add(key)
                if category == 'landscape':
                    if not isinstance(entry.get('type'), str) or not entry['type']:
                        raise ValueError('Invalid landscape')
                elif type(entry.get('available')) is not bool or any(type(entry.get(k)) is not int or entry[k] < 0 for k in ('Lumber', 'Clay', 'Iron', 'Crop')):
                    raise ValueError('Invalid resources')
                result.append({**entry, 'category': category})
        return result
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError('Invalid scan JSON') from exc
