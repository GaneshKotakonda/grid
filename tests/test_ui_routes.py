"""SPA navigation must coexist with the original JSON API paths."""
from fastapi.testclient import TestClient
from src.api import app


def test_frontend_direct_links_serve_html():
    client = TestClient(app)
    for path in ('/operations', '/topology', '/prediction', '/mitigation', '/recovery', '/timeline', '/benchmarks'):
        response = client.get(path, headers={'Accept': 'text/html'})
        assert response.status_code == 200, path
        assert 'text/html' in response.headers['content-type'], path
        assert '<div id="root"></div>' in response.text, path
        assert 'accept' in response.headers.get('vary', '').lower(), path


def test_benchmark_api_keeps_json_contract():
    response = TestClient(app).get('/benchmarks', headers={'Accept': 'application/json'})
    assert response.status_code == 200
    assert response.json()['key_findings']['load_served_gain_pp'] == 4.17
    assert 'accept' in response.headers.get('vary', '').lower()


def test_unknown_files_and_api_paths_stay_404():
    client = TestClient(app)
    for path in ('/missing.js', '/results/missing-run', '/not-a-real-page'):
        assert client.get(path).status_code == 404
