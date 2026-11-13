import json
from fastapi.testclient import TestClient
from trmap.app import create_app


def test_imports_and_conflicting_observations(tmp_path):
    with TestClient(create_app(tmp_path / 'db.sqlite')) as c:
        world = c.post('/api/worlds', json={'name':'s','season':'1','min_x':-2,'max_x':2,'min_y':-2,'max_y':2}).json()['id']
        url = f'/api/worlds/{world}/imports'
        sql = "INSERT INTO `x_world` VALUES (1,1,1,1,5,'村',10,'玩家',11,'盟',42,NULL,FALSE,NULL,NULL,NULL);"
        r = c.post(url, data={'kind':'map_sql', 'observed_at':'2026-01-01T00:00:00Z'}, files={'file':('map.sql',sql)})
        assert r.status_code == 201
        scan = {'village':[{'x':1,'y':1,'available':False,'Lumber':3,'Clay':3,'Iron':3,'Crop':9}], 'oasis':[], 'landscape':[]}
        r = c.post(url, data={'kind':'scan_json'}, files={'file':('scan.json',json.dumps(scan))})
        assert r.status_code == 201
        tile = c.get(f'/api/worlds/{world}/tiles', params={'min_x':1,'max_x':1,'min_y':1,'max_y':1}).json()[0]
        assert tile['village']['value']['village_name'] == '村'
        assert tile['terrain']['value']['Crop'] == 9
        assert tile['terrain']['observed_at'] is None
        assert c.post(url, data={'kind':'scan_json'}, files={'file':('scan.json',json.dumps(scan))}).status_code == 409
        bad = {'village': [], 'oasis': [], 'landscape':[{'x':3,'y':0,'type':'forest'}]}
        assert c.post(url, data={'kind':'scan_json'}, files={'file':('scan.json',json.dumps(bad))}).status_code == 422
        assert len(c.get(url).json()) == 2
