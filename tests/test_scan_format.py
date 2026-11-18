import json
from fastapi.testclient import TestClient
from trmap.app import create_app


def test_new_scan_format_preserves_metadata_and_tile_observations(tmp_path):
    metadata = {'source': 'scanner', 'complete': True, 'coverage': {'kind': 'world'}}
    tiles = [
        {'x': i, 'y': 0, 'kind': kind, 'static': static,
         'observations': [{'source': 'position', 'observed_at': '2026-01-01T00:00:00Z', 'fields': fields}]}
        for i, (kind, static, fields) in enumerate([
            ('village', {'resources': None}, {'occupied': True, 'village': {'name': 'Example'}}),
            ('village', {'resources': {'Lumber': 3, 'Clay': 4, 'Iron': 5, 'Crop': 6}}, {'occupied': False}),
            ('oasis', {'resources': {'Lumber': 25, 'Clay': 0, 'Iron': 0, 'Crop': 0}}, {'occupied': True, 'player': {'name': 'Example'}}),
            ('oasis', {'resources': {'Lumber': 0, 'Clay': 0, 'Iron': 0, 'Crop': 25}}, {'occupied': False, 'animals': {'Rat': 2}}),
            ('landscape', {'landscape_type': 'Lake'}, {}),
        ])]
    with TestClient(create_app(tmp_path / 'db')) as c:
        w = c.post('/api/worlds', json={'name':'test','season':'1','min_x':0,'max_x':4,'min_y':0,'max_y':0}).json()['id']
        url = f'/api/worlds/{w}/imports'
        r = c.post(url, data={'kind':'scan_json'}, files={'file':('scan.json',json.dumps({'schema_version':1,'metadata':metadata,'tiles':tiles}))})
        assert r.status_code == 201, r.text
        assert c.get(url).json()[0]['metadata'] == metadata
        result = c.get(f'/api/worlds/{w}/tiles',params={'min_x':0,'max_x':4,'min_y':0,'max_y':0}).json()
        for actual, expected in zip(sorted(result,key=lambda t:t['x']), tiles):
            terrain = actual['terrain']
            assert terrain['observed_at'] == '2026-01-01T00:00:00+00:00'
            assert terrain['value']['static'] == expected['static']
            assert terrain['value']['fields'] == expected['observations'][0]['fields']
            assert terrain['value']['category'] == expected['kind']
        assert result[0]['terrain']['value']['available'] is False
        assert result[1]['terrain']['value']['available'] is True

def test_tile_observations_use_their_own_times_and_preserve_unknowns(tmp_path):
    tile = {'x': 0, 'y': 0, 'kind': 'village', 'static': {'resources': None}, 'observations': [
        {'source': 'position', 'observed_at': '2026-01-02T00:00:00Z', 'fields': {'occupied': True}},
        {'source': 'position', 'observed_at': '2026-01-01T00:00:00Z', 'fields': {'occupied': False}},
    ]}
    with TestClient(create_app(tmp_path / 'db')) as c:
        w = c.post('/api/worlds', json={'name':'test','season':'1','min_x':0,'max_x':0,'min_y':0,'max_y':0}).json()['id']
        url = f'/api/worlds/{w}/imports'
        assert c.post(url, data={'kind':'scan_json'}, files={'file':('s.json',json.dumps({'schema_version':1,'metadata':{},'tiles':[tile]}))}).status_code == 201
        terrain = c.get(f'/api/worlds/{w}/tiles?min_x=0&max_x=0&min_y=0&max_y=0').json()[0]['terrain']
        assert terrain['status'] == 'known'
        assert terrain['value']['fields']['occupied'] is True
        assert terrain['value']['static']['resources'] is None
