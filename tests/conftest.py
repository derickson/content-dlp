import shutil
from pathlib import Path

TEST_DOWNLOAD_DIR = Path(__file__).parent / "test_output"


def pytest_sessionstart(session):
    """Clear test cache once at the start of the test session."""
    if TEST_DOWNLOAD_DIR.exists():
        shutil.rmtree(TEST_DOWNLOAD_DIR)
