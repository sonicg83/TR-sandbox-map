from fastapi.testclient import TestClient
from trmap.app import create_app


def test_javascript_modules_have_browser_compatible_content_type(tmp_path):
    with TestClient(create_app(tmp_path / 'db.sqlite')) as c:
        response = c.get('/static/app.mjs')
        assert response.status_code == 200
        assert 'javascript' in response.headers['content-type']
