from collections.abc import Callable

import pytest
from notifications_python_client.errors import HTTPError


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status_code = status

    def json(self) -> dict:
        return {"errors": [{"error": "Error", "message": "message"}]}


@pytest.fixture
def http_error() -> Callable[[int], HTTPError]:
    return lambda status: HTTPError(response=FakeResponse(status))
