"""Task-local classification of explicit runtime cleanup faults."""
from evaluation.broker import BrokerError
from evaluation.contract import InfrastructureError


class RuntimeClient:
    def __init__(self, client):
        self.client = client

    def __getattr__(self, name):
        return getattr(self.client, name)

    def call(self, request, **kwargs):
        try:
            return self.client.call(request, **kwargs)
        except BrokerError as exc:
            if exc.status == 500 and exc.error == 'RuntimeCleanupError':
                raise InfrastructureError('Black-box runtime cleanup failed: ' + exc.detail) from exc
            raise
