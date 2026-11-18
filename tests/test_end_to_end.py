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



def test_import_plan_and_restart(tmp_path):
    path=tmp_path/'data.sqlite'
    with TestClient(create_app(path)) as c:
        world=c.post('/api/worlds',json={'name':'人工样例','season':'一','min_x':-5,'max_x':5,'min_y':-5,'max_y':5}).json()['id']
        sql="INSERT INTO `x_world` VALUES (1,1,1,1,5,'村庄',10,'玩家',11,'联盟',42,NULL,FALSE,NULL,NULL,NULL);"
        url=f'/api/worlds/{world}/imports'
        assert c.post(url,data={'kind':'map_sql'},files={'file':('map.sql',sql)}).status_code==201
        scan={'village':[{'x':1,'y':1,'available':False,'Lumber':3,'Clay':3,'Iron':3,'Crop':9}],'oasis':[],'landscape':[]}
        assert c.post(url,data={'kind':'scan_json'},files={'file':('scan.json',json.dumps(scan_document(scan)))}).status_code==201
        plan=c.post(f'/api/worlds/{world}/plans',json={'name':'计划'}).json()['id']
        marker={'id':'m','type':'marker','x':1,'y':1,'label':'集合','color':'#b1513e','note':'人工测试'}
        assert c.put(f'/api/plans/{plan}',json={'name':'计划','items':[marker]}).status_code==200
        assert c.post(url,data={'kind':'map_sql'},files={'file':('bad.sql',sql+'DROP TABLE worlds;')}).status_code==422
    with TestClient(create_app(path)) as c:
        tile=c.get(f'/api/worlds/{world}/tiles?min_x=1&max_x=1&min_y=1&max_y=1').json()[0]
        assert tile['village']['value']['village_name']=='村庄'
        assert tile['terrain']['value']['Crop']==9
        assert c.get(f'/api/plans/{plan}').json()['items']==[marker]
        assert len(c.get(f'/api/worlds/{world}/imports').json())==2
