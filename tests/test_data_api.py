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



def test_imports_and_conflicting_observations(tmp_path):
    with TestClient(create_app(tmp_path / 'db.sqlite')) as c:
        world = c.post('/api/worlds', json={'name':'s','season':'1','min_x':-2,'max_x':2,'min_y':-2,'max_y':2}).json()['id']
        url = f'/api/worlds/{world}/imports'
        sql = "INSERT INTO `x_world` VALUES (1,1,1,1,5,'村',10,'玩家',11,'盟',42,NULL,FALSE,NULL,NULL,NULL);"
        r = c.post(url, data={'kind':'map_sql', 'observed_at':'2026-01-01T00:00:00Z'}, files={'file':('map.sql',sql)})
        assert r.status_code == 201
        scan = {'village':[{'x':1,'y':1,'available':False,'Lumber':3,'Clay':3,'Iron':3,'Crop':9}], 'oasis':[], 'landscape':[]}
        r = c.post(url, data={'kind':'scan_json'}, files={'file':('scan.json',json.dumps(scan_document(scan)))})
        assert r.status_code == 201
        tile = c.get(f'/api/worlds/{world}/tiles', params={'min_x':1,'max_x':1,'min_y':1,'max_y':1}).json()[0]
        assert tile['village']['value']['village_name'] == '村'
        assert tile['terrain']['value']['Crop'] == 9
        assert tile['terrain']['observed_at'] is None
        assert c.post(url, data={'kind':'scan_json'}, files={'file':('scan.json',json.dumps(scan_document(scan)))}).status_code == 409
        bad = {'village': [], 'oasis': [], 'landscape':[{'x':3,'y':0,'type':'forest'}]}
        assert c.post(url, data={'kind':'scan_json'}, files={'file':('scan.json',json.dumps(scan_document(bad)))}).status_code == 422
        assert len(c.get(url).json()) == 2

def test_overview_returns_all_observed_tiles_and_conflicts(tmp_path):
    with TestClient(create_app(tmp_path / 'db')) as c:
        w=c.post('/api/worlds',json={'name':'test','season':'1','min_x':0,'max_x':2,'min_y':0,'max_y':0}).json()['id']
        url=f'/api/worlds/{w}/imports'
        def upload(tiles):
            data={'schema_version':1,'metadata':{},'tiles':tiles}
            return c.post(url,data={'kind':'scan_json'},files={'file':('s.json',json.dumps(data))})
        def tile(x, kind, static, fields):
            return {'x':x,'y':0,'kind':kind,'static':static,'observations':[{'fields':fields}]}
        village=tile(0,'village',{'resources':None},{'occupied':True})
        landscape=tile(1,'landscape',{'landscape_type':'Lake'},{})
        other=tile(2,'landscape',{'landscape_type':'Lake'},{})
        assert upload([village,landscape,other]).status_code==201
        assert upload([tile(2,'landscape',{'landscape_type':'Hill'}, {})]).status_code==201
        res=c.get(f'/api/worlds/{w}/tiles',params={'min_x':0,'max_x':2,'min_y':0,'max_y':0,'overview':'true'}).json()
        assert {x['x'] for x in res}=={0,1,2}
        assert next(x for x in res if x['x']==2)['terrain']['status']=='conflict'

        selected=c.get(f'/api/worlds/{w}/tiles',params={'min_x':0,'max_x':2,'min_y':0,'max_y':0,'overview':'true','selected_x':1,'selected_y':0}).json()
        assert {x['x'] for x in selected}=={0,1,2}


def test_large_tile_response_supports_gzip_and_uncompressed_clients(tmp_path):
    with TestClient(create_app(tmp_path / 'db')) as c:
        w = c.post('/api/worlds', json={'name':'compression','season':'1','min_x':0,'max_x':20,'min_y':0,'max_y':0}).json()['id']
        tiles = [{'x':x,'y':0,'kind':'landscape','static':{'landscape_type':'Lake'},'observations':[]} for x in range(21)]
        assert c.post(f'/api/worlds/{w}/imports', data={'kind':'scan_json'}, files={'file':('scan.json',json.dumps({'schema_version':1,'metadata':{},'tiles':tiles}))}).status_code == 201
        path=f'/api/worlds/{w}/tiles?min_x=0&max_x=20&min_y=0&max_y=0&overview=true'
        compressed=c.get(path,headers={'Accept-Encoding':'gzip'})
        plain=c.get(path,headers={'Accept-Encoding':'identity'})
        assert compressed.headers.get('content-encoding') == 'gzip'
        assert 'content-encoding' not in plain.headers
        assert compressed.json() == plain.json()
        assert len(compressed.json()) == len(tiles)


def test_village_overview_finds_villages_and_related_conflicts_across_world(tmp_path):
    with TestClient(create_app(tmp_path / 'db')) as c:
        w=c.post('/api/worlds',json={'name':'overview','season':'1','min_x':0,'max_x':500,'min_y':0,'max_y':0}).json()['id']
        def tile(x, kind, fields):
            return {'x':x,'y':0,'kind':kind,'static':{'landscape_type':'Lake'} if kind=='landscape' else {'resources':None},'observations':[{'fields':fields}]}
        def upload(tiles):
            return c.post(f'/api/worlds/{w}/imports',data={'kind':'scan_json'},files={'file':('s.json',json.dumps({'schema_version':1,'metadata':{},'tiles':tiles}))})
        assert upload([tile(0,'village',{'occupied':True}),tile(250,'village',{'occupied':False}),tile(500,'village',{'occupied':True})]).status_code==201
        assert upload([tile(500,'landscape',{})]).status_code==201
        result=c.get(f'/api/worlds/{w}/village-overview')
        assert result.status_code==200
        assert {t['x'] for t in result.json()}=={0,500}
        assert next(t for t in result.json() if t['x']==500)['terrain']['status']=='conflict'
        assert c.get(f'/api/worlds/{w}/tiles?min_x=250&max_x=250&min_y=0&max_y=0').json()[0]['terrain']['value']['fields']['occupied'] is False
        assert upload([tile(250,'village',{'occupied':True})]).status_code==201
        assert {t['x'] for t in c.get(f'/api/worlds/{w}/village-overview').json()}=={0,250,500}


def test_render_tiles_preserve_visual_fields_and_conflicts_without_details(tmp_path):
    with TestClient(create_app(tmp_path/'db')) as c:
        w=c.post('/api/worlds',json={'name':'display','season':'1','min_x':0,'max_x':2,'min_y':0,'max_y':0}).json()['id']
        url=f'/api/worlds/{w}/imports'
        sql="INSERT INTO `x_world` VALUES (1,0,0,1,5,'village',10,'player',11,'ally',420,NULL,FALSE,NULL,NULL,NULL);"
        assert c.post(url,data={'kind':'map_sql'},files={'file':('map.sql',sql)}).status_code==201
        def upload(crop):
            tiles=[{'x':0,'y':0,'kind':'village','static':{'resources':None},'observations':[{'fields':{'occupied':True,'village':{'population':50},'private_detail':'kept'}}]},
                   {'x':1,'y':0,'kind':'oasis','static':{'resources':{'Lumber':25,'Clay':0,'Iron':0,'Crop':crop}},'observations':[{'fields':{'occupied':False,'private_detail':'kept'}}]},
                   {'x':2,'y':0,'kind':'landscape','static':{'landscape_type':'Lake'},'observations':[]}]
            return c.post(url,data={'kind':'scan_json'},files={'file':('scan.json',json.dumps({'schema_version':1,'metadata':{},'tiles':tiles}))})
        assert upload(0).status_code==201
        params={'min_x':0,'max_x':2,'min_y':0,'max_y':0}
        display=c.get(f'/api/worlds/{w}/tiles',params={**params,'render':'true'}).json()
        detail=c.get(f'/api/worlds/{w}/tiles',params=params).json()
        assert display[0]['village']['value']=={'population':420,'alliance_name':'ally'}
        assert display[0]['terrain']['value']['fields']['village']['population']==50
        assert display[1]['terrain']['value']['static']['resources']['Lumber']==25
        assert display[2]['terrain']['value']['static']['landscape_type']=='Lake'
        assert 'observation' not in display[1]['terrain'] and 'observed_at' not in display[1]['terrain']
        assert detail[1]['terrain']['observation']['fields']['private_detail']=='kept'
        assert upload(25).status_code==201
        display=c.get(f'/api/worlds/{w}/tiles',params={**params,'render':'true'}).json()
        assert display[1]['terrain']=={'status':'conflict'}
        assert len(c.get(f'/api/worlds/{w}/tiles',params=params).json()[1]['terrain']['candidates'])==2
