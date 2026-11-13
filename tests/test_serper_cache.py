from unittest.mock import Mock

import pytest

from app.services.serper import SerperClient, SerperError


def response(organic):
    return Mock(status_code=200, json=lambda: {"organic": organic})


def test_cache_survives_new_client_and_normalizes_query(tmp_path, monkeypatch):
    post = Mock(return_value=response([{"link": "https://example.org", "title": "Source", "snippet": "Text"}]))
    monkeypatch.setattr("app.services.serper.requests.post", post)
    path = tmp_path / "internet.sqlite3"
    first = SerperClient("key", cache_path=path).search("Example   query")
    second = SerperClient("key", cache_path=path).search("example query")
    assert not first["cache_hit"] and second["cache_hit"]
    assert first["organic"] == second["organic"]
    assert post.call_count == 1
    SerperClient("key", cache_path=path).search("example query", num=5)
    SerperClient("key", cache_path=path).search("example query", language="en")
    assert post.call_count == 3


def test_empty_results_and_quote_fallback_are_cached(tmp_path, monkeypatch):
    post = Mock(return_value=response([]))
    monkeypatch.setattr("app.services.serper.requests.post", post)
    client = SerperClient("key", cache_path=tmp_path / "cache.sqlite3")
    assert client.search('"example query"')["organic"] == []
    assert client.search('"example query"')["cache_hit"]
    assert post.call_count == 2


def test_api_errors_are_not_cached(tmp_path, monkeypatch):
    post = Mock(side_effect=[Mock(status_code=429), response([])])
    monkeypatch.setattr("app.services.serper.requests.post", post)
    client = SerperClient("key", cache_path=tmp_path / "cache.sqlite3")
    with pytest.raises(SerperError):
        client.search("example")
    assert not client.search("example")["cache_hit"]
    assert post.call_count == 2


def test_unwritable_cache_does_not_break_search(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.serper.requests.post", Mock(return_value=response([])))
    client = SerperClient("key", cache_path=tmp_path)
    assert client.search("example")["organic"] == []
