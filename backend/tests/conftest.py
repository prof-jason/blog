import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def static_dir(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "index.html").write_text("<html><body>Prompt Generator</body></html>")
    return out


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "data" / "app.db"


@pytest.fixture
def client(db_path, static_dir):
    with TestClient(create_app(db_path=db_path, static_dir=static_dir, warm_up_count=0)) as test_client:
        yield test_client
