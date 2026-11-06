"""The interface every broker integration implements."""

from abc import ABC, abstractmethod

from uninv_backend.models import Account, Broker, Position


class BrokerConnector(ABC):
    """Adapter between one broker's API and uninv's shared models.

    To add a broker, subclass this, translate the broker's responses into `Account` /
    `Position`, and register the instance in `brokers/registry.py`.

    Methods are async because real broker calls are network I/O; the portfolio service
    queries all brokers concurrently.
    """

    @property
    @abstractmethod
    def info(self) -> Broker:
        """Static description of this broker connection."""

    @abstractmethod
    async def get_accounts(self) -> list[Account]:
        """All accounts available through this connection."""

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """All open positions across this connection's accounts."""
