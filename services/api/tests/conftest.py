import os
import json
import pytest
from unittest.mock import MagicMock
import sys
from fastapi.testclient import TestClient


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")  # Define a session-scoped monkeypatch
def session_monkeypatch(request):
    mpatch = pytest.MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(autouse=True)
def mock_fs(monkeypatch):
    monkeypatch.setattr(os, "makedirs", lambda *args, **kwargs: None)
    # mock open to do nothing
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: MagicMock())


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    # Safer defaults for tests
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "ES_HOST", "http://elasticsearch:9200"
    )  # Keep this for settings, but it will be mocked
    monkeypatch.setenv("ES_PRIVATE_INDEX", "private_user_memory")
    monkeypatch.setenv("ES_PUBLIC_INDEX", "public_medical_kb")
    monkeypatch.setenv("ES_PLACES_INDEX", "providers_places")
    # ML thresholds sensible for tests
    monkeypatch.setenv("RISK_LABELS", "urgent_care,see_doctor,self_care,info_only")
    monkeypatch.setenv("RISK_THRESHOLDS", "urgent_care:0.65,see_doctor:0.55")
    monkeypatch.setenv("RISK_MODEL_ID", "__stub__")


@pytest.fixture()
def fake_embed(monkeypatch):
    """Deterministic embed stub: returns tiny 3-dim vectors based on keywords.
    - symptom-ish: [1,0,0]
    - appointment-ish: [0,1,0]
    - meds-ish: [0,0,1]
    - else: [0,0,0]
    """
    from app.tools import embeddings as emb_mod

    def _vec(text: str):
        t = text.lower()
        if any(k in t for k in ["fever", "חום", "pain", "headache"]):
            return [1.0, 0.0, 0.0]
        if any(k in t for k in ["book", "appointment", "lab", "קבע", "תור"]):
            return [0.0, 1.0, 0.0]
        if any(
            k in t for k in ["pill", "med", "refill", "ibuprofen", "warfarin", "תרופה"]
        ):
            return [0.0, 0.0, 1.0]
        return [0.0, 0.0, 0.0]

    def _embed(texts):
        if isinstance(texts, str):
            texts = [texts]
        return [_vec(t) for t in texts]

    monkeypatch.setattr(emb_mod, "embed", _embed)
    return _embed


class _FakeES:
    def __init__(self):
        self.calls = []
        self.handlers = []  # list of (predicate, response)
        self.indices = self._Indices()

    class _Indices:
        def create(self, index, body):
            pass

        def exists(self, index):
            return True  # Assume index exists for tests

    def info(self):
        return {"cluster_name": "test_cluster"}

    def add_handler(self, predicate, response):
        self.handlers.append((predicate, response))

    def search(self, index: str, body: dict, **kwargs):
        self.calls.append((index, json.loads(json.dumps(body))))
        for pred, resp in self.handlers:
            try:
                if pred(index, body):
                    return resp
            except Exception:
                continue
        # default empty
        return {"hits": {"hits": []}}

    def index(self, index: str, id: str, document: dict):
        self.calls.append(("index", index, id, document))


@pytest.fixture()  # Changed scope to function, removed autouse=True
def fake_es(session_monkeypatch):
    fake = _FakeES()

    # Patch the Elasticsearch class itself
    session_monkeypatch.setattr(
        "app.tools.es_client.Elasticsearch", lambda *args, **kwargs: fake
    )

    import app.tools.es_client

    app.tools.es_client._es_client = None

    return fake


@pytest.fixture()
def fake_pipe(monkeypatch):
    """Mock the zero-shot classifier pipeline.
    Provide .run(scores=...) to set desired label probs.
    """
    scores = {"urgent_care": 0.0, "see_doctor": 0.0, "self_care": 0.0, "info_only": 1.0}

    class _P:
        def __call__(
            self, text, candidate_labels, hypothesis_template, multi_label=True
        ):
            # Preserve provided label order
            labels = list(candidate_labels)
            return {
                "labels": labels,
                "scores": [scores.get(label, 0.0) for label in labels],
            }

    p = _P()

    from app.graph.nodes import risk_ml

    def set_scores(**kw):
        scores.update(kw)

    monkeypatch.setattr(risk_ml, "_PIPE", p)
    monkeypatch.setattr(risk_ml, "_get_pipe", lambda: p)
    p.run = set_scores
    return p


@pytest.fixture()
def client(monkeypatch, fake_es, fake_embed):
    # Avoid real index bootstrap at startup
    import app.tools.es_client as es_client

    monkeypatch.setattr(es_client, "ensure_indices", lambda: None)
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sample_docs():
    def hits(docs):
        return {"hits": {"hits": [{"_source": d} for d in docs]}}

    fever_doc = {
        "title": "Fever Home Care",
        "section": "general",
        "language": "en",
        "jurisdiction": "generic",
        "source_url": "file://fever.md",
        "updated_on": "2025-01-01T00:00:00Z",
        "text": "Hydrate; rest; consider acetaminophen",
    }
    ibu_warn = {
        "title": "Ibuprofen",
        "section": "warnings",
        "language": "en",
        "jurisdiction": "generic",
        "source_url": "file://ibuprofen.md",
        "updated_on": "2025-01-01T00:00:00Z",
        "text": "Do not combine with warfarin",
    }
    warf_inter = {
        "title": "Warfarin",
        "section": "interactions",
        "language": "en",
        "jurisdiction": "generic",
        "source_url": "file://warfarin.md",
        "updated_on": "2025-01-01T00:00:00Z",
        "text": "Increased bleeding risk with NSAIDs like ibuprofen",
    }
    return hits, fever_doc, ibu_warn, warf_inter
