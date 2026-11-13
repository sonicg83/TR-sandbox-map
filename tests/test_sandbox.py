from fastapi.testclient import TestClient
from trmap.app import create_app


def test_plan_persists_and_checks_bounds(tmp_path):
    path = tmp_path / 'db.sqlite'
    with TestClient(create_app(path)) as c:
        w = c.post('/api/worlds', json={'name':'s','season':'1','min_x':-2,'max_x':2,'min_y':-2,'max_y':2}).json()['id']
        p = c.post(f'/api/worlds/{w}/plans', json={'name':'plan'}).json()['id']
        marker = {'id':'one','type':'marker','x':1,'y':1,'label':'A','color':'#ff0000','note':''}
        assert c.put(f'/api/plans/{p}', json={'name':'plan','items':[marker]}).status_code == 200
        assert c.put(f'/api/plans/{p}', json={'name':'plan','items':[{**marker,'x':99}]}).status_code == 422
    with TestClient(create_app(path)) as c:
        assert c.get(f'/api/plans/{p}').json()['items'] == [marker]
