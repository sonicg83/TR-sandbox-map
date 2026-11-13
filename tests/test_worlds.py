from fastapi.testclient import TestClient
from trmap.app import create_app


def test_world_persists_and_rejects_invalid_and_duplicate(tmp_path):
    path = tmp_path / 'test.sqlite3'
    data = {'name': 'test', 'season': 's1', 'min_x': -200, 'max_x': 200, 'min_y': -200, 'max_y': 200, 'wrap': False}
    with TestClient(create_app(path)) as client:
        assert client.post('/api/worlds', json=data).status_code == 201
        assert client.post('/api/worlds', json=data).status_code == 422
        assert client.post('/api/worlds', json={**data, 'name': 'bad', 'min_x': 300}).status_code == 422
        assert client.post('/api/worlds', json={**data, 'name': 'wrap', 'wrap': True}).status_code == 422
    with TestClient(create_app(path)) as client:
        assert len(client.get('/api/worlds').json()) == 1
