from fastapi.testclient import TestClient
from trmap.app import create_app


def test_javascript_modules_have_browser_compatible_content_type(tmp_path):
    with TestClient(create_app(tmp_path / 'db.sqlite')) as c:
        response = c.get('/static/app.mjs')
        assert response.status_code == 200
        assert 'javascript' in response.headers['content-type']

def test_map_toolbar_and_landscape_assets_are_served(tmp_path):
    with TestClient(create_app(tmp_path / 'db.sqlite')) as c:
        page = c.get('/').text
        for button in ('zoomIn', 'zoomOut', 'centerOrigin'):
            assert f'id="{button}"' in page
        for asset in ('landscape/Forest', 'landscape/Clay', 'landscape/Hill', 'landscape/Lake', 'oasis/Lumber', 'oasis/Clay', 'oasis/Iron', 'oasis/Crop', 'village/level1', 'village/level2', 'village/level3', 'village/level4'):
            response = c.get(f'/static/assets/{asset}.png')
            assert response.status_code == 200, asset
            assert response.headers['content-type'] == 'image/png'
