import json
from datetime import datetime, timezone


def normalize_time(value):
    if value is None or value == '':
        return None
    if not isinstance(value, str):
        raise ValueError('Invalid observation time')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Observation time needs timezone')
    return dt.astimezone(timezone.utc).isoformat()


def parse_scan_json(text: str) -> tuple[dict, list[dict]]:
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1 or not isinstance(data.get('metadata'), dict) or not isinstance(data.get('tiles'), list):
            raise ValueError('Invalid scan format or schema version')
        seen = set()
        for tile in data['tiles']:
            if not isinstance(tile, dict) or type(tile.get('x')) is not int or type(tile.get('y')) is not int:
                raise ValueError('Invalid coordinates')
            key = tile['x'], tile['y']
            if key in seen:
                raise ValueError('Duplicate coordinate')
            seen.add(key)
            kind, static, observations = tile.get('kind'), tile.get('static'), tile.get('observations')
            if kind not in ('village', 'oasis', 'landscape') or not isinstance(static, dict) or not isinstance(observations, list):
                raise ValueError('Invalid tile')
            if kind == 'landscape':
                if not isinstance(static.get('landscape_type'), str) or not static['landscape_type']:
                    raise ValueError('Invalid landscape')
            else:
                resources = static.get('resources')
                if resources is not None and (not isinstance(resources, dict) or any(type(resources.get(k)) is not int or resources[k] < 0 for k in ('Lumber', 'Clay', 'Iron', 'Crop'))):
                    raise ValueError('Invalid resources')
            for observation in observations:
                if not isinstance(observation, dict) or not isinstance(observation.get('fields'), dict):
                    raise ValueError('Invalid observation')
                occupied = observation['fields'].get('occupied')
                if occupied is not None and type(occupied) is not bool:
                    raise ValueError('Invalid occupancy')
                normalize_time(observation.get('observed_at'))
                normalize_time(observation.get('started_at'))
        return data['metadata'], data['tiles']
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError('Invalid scan JSON') from exc
