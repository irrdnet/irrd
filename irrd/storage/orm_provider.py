import functools

import sqlalchemy.orm as saorm
from asgiref.sync import sync_to_async
from sqlalchemy.exc import SQLAlchemyError

from irrd.storage.database_handler import DatabaseHandler


class ORMSessionProvider:
    """
    This object provides access to a SQLALchemy ORM session,
    to allow access to the database for ORM queries.
    These are mainly used for authentication, the ORM has overhead that
    makes it a poor choice for high performance.
    """

    def __init__(self):
        self.database_handler = DatabaseHandler()
        self.session = self._get_session()

    def _get_session(self):
        return saorm.Session(bind=self.database_handler._connection)

    def close(self):
        """
        Close the connection, discarding changes.
        """
        self.session.close()
        self.database_handler.close()

    def commit_close(self):
        """
        Commit any changes and close the connection.
        Must be called explicitly on each session provider.
        """
        self.session.commit()
        self.database_handler.commit()
        self.close()

    @sync_to_async
    def run(self, target):
        """
        Run the provided callable query, async interface.
        This is just a small async wrapper around the sync version.
        """
        return self.run_sync(target)

    def run_sync(self, target):
        """
        Run the provided callable query, sync interface.
        Target should be a callable, e.g. run_sync(query.all).
        Automatically reconnects once if the connection was lost.
        """
        try:
            return target()
        except saorm.exc.NoResultFound:
            return None
        except SQLAlchemyError:  # pragma: no cover
            self.database_handler.refresh_connection()
            target.__self__.session = self.session = self._get_session()
            return target()


def session_provider_manager(func):
    """
    Decorator intended for async functions to provide an ORMSessionProvider.
    Commits/closes at the end of a successful call.
    """

    @functools.wraps(func)
    async def endpoint_wrapper(*args, **kwargs):
        provider = ORMSessionProvider()
        try:
            response = await func(*args, session_provider=provider, **kwargs)
            provider.commit_close()
        except Exception:  # pragma: no cover
            provider.close()
            raise
        return response

    return endpoint_wrapper


def session_provider_manager_sync(func):
    """
    Decorator for sync functions to provide an ORMSessionProvider.
    Commits/closes at the end of a successful call.
    """

    @functools.wraps(func)
    def endpoint_wrapper(*args, **kwargs):
        provider = ORMSessionProvider()
        try:
            response = func(*args, session_provider=provider, **kwargs)
            provider.commit_close()
        except Exception:  # pragma: no cover
            provider.close()
            raise
        return response

    return endpoint_wrapper
