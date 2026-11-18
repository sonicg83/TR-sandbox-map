import json
from fastapi.testclient import TestClient
from trmap.app import create_app

def scan_document(old):
    tiles = []
    for category, entries in old.items():
        for entry in entries:
            static = {'landscape_type': entry['type']} if category == 'landscape' else {'resources': {k: entry[k] for k in ('Lumber', 'Clay', 'Iron', 'Crop')}}
            fields = {} if category == 'landscape' else {'occupied': not entry['available']}
            tiles.append({'x': entry['x'], 'y': entry['y'], 'kind': category, 'static': static, 'observations': [{'fields': fields}]})
    return {'schema_version': 1, 'metadata': {}, 'tiles': tiles}



def test_unknown_timestamp_causes_conflict_and_old_time_does_not_win(tmp_path):
    with TestClient(create_app(tmp_path / 'db.sqlite')) as c:
        w=c.post('/api/worlds',json={'name':'test','season':'1','min_x':-2,'max_x':2,'min_y':-2,'max_y':2}).json()['id']
        url=f'/api/worlds/{w}/imports'
        def upload(crop, when=None):
            body={'village':[{'x':0,'y':0,'available':True,'Lumber':3,'Clay':3,'Iron':3,'Crop':crop}],'oasis':[],'landscape':[]}
            return c.post(url,data={'kind':'scan_json',**({'observed_at':when} if when else {})},files={'file':('data.json',json.dumps(scan_document(body)))})
        assert upload(9,'2026-01-02T00:00:00Z').status_code == 201
        assert upload(6,'2026-01-01T00:00:00Z').status_code == 201
        path=f'/api/worlds/{w}/tiles?min_x=0&max_x=0&min_y=0&max_y=0'
        assert c.get(path).json()[0]['terrain']['value']['Crop']==9
        assert upload(15).status_code==201
        assert c.get(path).json()[0]['terrain']['status']=='conflict'


def test_unrelated_origin_cannot_create_world(tmp_path):
    with TestClient(create_app(tmp_path / 'db.sqlite')) as c:
        r=c.post('/api/worlds',headers={'Origin':'https://untrusted.example'},json={'name':'x','season':'1','min_x':-2,'max_x':2,'min_y':-2,'max_y':2})
        assert r.status_code == 403


def test_search_does_not_return_obsolete_name(tmp_path):
    with TestClient(create_app(tmp_path / 'db.sqlite')) as c:
        w=c.post('/api/worlds',json={'name':'test','season':'1','min_x':-2,'max_x':2,'min_y':-2,'max_y':2}).json()['id']
        url=f'/api/worlds/{w}/imports'
        def upload(name, when):
            sql=f"INSERT INTO `x_world` VALUES (1,1,1,1,5,'{name}',10,'player',11,'ally',42,NULL,FALSE,NULL,NULL,NULL);"
            return c.post(url,data={'kind':'map_sql','observed_at':when},files={'file':('map.sql',sql)})
        assert upload('old','2026-01-01T00:00:00Z').status_code==201
        assert upload('new','2026-01-02T00:00:00Z').status_code==201
        assert c.get(f'/api/worlds/{w}/search',params={'q':'old'}).json()==[]
        assert c.get(f'/api/worlds/{w}/search',params={'q':'new'}).json()[0]['village_name']=='new'


def test_same_content_new_time_is_new_observation_and_identical_unknown_is_not_conflict(tmp_path):
    with TestClient(create_app(tmp_path/'db.sqlite')) as c:
        w=c.post('/api/worlds',json={'name':'test','season':'1','min_x':-2,'max_x':2,'min_y':-2,'max_y':2}).json()['id']
        url=f'/api/worlds/{w}/imports'
        scan={'village':[], 'oasis':[], 'landscape':[{'x':0,'y':0,'type':'forest'}]}
        raw=json.dumps(scan_document(scan))
        assert c.post(url,data={'kind':'scan_json','observed_at':'2026-01-01T00:00:00Z'},files={'file':('s.json',raw)}).status_code==201
        assert c.post(url,data={'kind':'scan_json','observed_at':'2026-01-02T00:00:00Z'},files={'file':('s.json',raw)}).status_code==201
        assert c.post(url,data={'kind':'scan_json'},files={'file':('s.json',json.dumps(scan_document(scan),indent=2))}).status_code==201
        tile=c.get(f'/api/worlds/{w}/tiles?min_x=0&max_x=0&min_y=0&max_y=0').json()[0]
        assert tile['terrain']['status']=='known'
        assert len(tile['terrain']['candidates'])==3
