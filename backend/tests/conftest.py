import os
import sys
from pathlib import Path
import pytest

# Add backend directory to sys.path so 'app' imports work
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.ingestion.catalogue_loader import catalogue_loader
from app.ingestion.policy_loader import policy_loader
from app.retrieval.semantic_search import local_vector_index

@pytest.fixture(autouse=True)
def setup_test_fixtures():
    """Ensures test fixtures are loaded for unit test assertions."""
    # Force loading isolated synthetic fixtures for tests
    catalogue_loader.load_default_catalogue(force_fixtures=True)
    policy_loader.load_default_policy(force_fixtures=True)
    local_vector_index.build_index(force_rebuild=True)
    yield
