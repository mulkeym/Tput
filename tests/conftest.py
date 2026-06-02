import pytest


@pytest.fixture
def sample_generators():
    """List of generator names for testing."""
    return ["name", "ssn", "email", "mrn", "diagnosis"]
