"""
app/repositories/base.py
=========================
Generic async CRUD base repository for SQLAlchemy 2.0.

Design decisions:
- `BaseRepository[ModelT]` is a generic class parameterised on the ORM model
  type. Concrete repositories inherit and get all standard CRUD operations for
  free, overriding only where domain-specific logic is needed.
- All methods are `async` and accept an `AsyncSession` that is always injected
  from outside (never created inside the repository). This makes repositories
  fully testable with a mock/test session.
- `get_by_id` raises `RecordNotFoundError` (domain exception) rather than
  returning `None`, keeping the service layer free of None-checks.
  A separate `get_by_id_or_none` is provided when callers legitimately
  need to handle absence without an exception.
- `list_all` supports `limit`/`offset` for pagination and an optional
  `order_by` clause. Concrete repos override this with domain-specific filters.
- `bulk_create` uses `session.add_all` + a single flush for efficiency —
  avoids N individual INSERT round-trips when persisting Stage 12 batch writes.
- Repositories NEVER commit — that is the responsibility of the session
  dependency (`get_async_session`) in the API layer, or the caller for
  background tasks using `get_db_context`.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateRecordError, RecordNotFoundError
from app.models.base import Base

logger = logging.getLogger(__name__)

# Generic type variable bound to any SQLAlchemy model
ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic async CRUD repository for a single SQLAlchemy ORM model.

    Subclasses must define `model_class` as a class attribute pointing to
    the concrete ORM model they manage.

    Type parameter:
        ModelT: The SQLAlchemy ORM model class (must inherit from `Base`).

    Example::

        class ClaimRepository(BaseRepository[VerifiedClaim]):
            model_class = VerifiedClaim
    """

    model_class: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialise the repository with an async database session.

        The session is provided by FastAPI's DI system (`get_async_session`)
        and is shared across all repositories within a single request.

        Args:
            session: An active SQLAlchemy `AsyncSession`.
        """
        self.session = session

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_by_id(self, record_id: uuid.UUID) -> ModelT:
        """
        Fetch a single record by its UUID primary key.

        Args:
            record_id: UUID of the record to fetch.

        Returns:
            The ORM model instance.

        Raises:
            RecordNotFoundError: If no record with the given ID exists.
        """
        result = await self.session.get(self.model_class, record_id)
        if result is None:
            raise RecordNotFoundError(
                model=self.model_class.__name__,
                identifier=str(record_id),
            )
        return result

    async def get_by_id_or_none(self, record_id: uuid.UUID) -> ModelT | None:
        """
        Fetch a single record by UUID, returning None if not found.

        Use this when absence of a record is a valid, expected condition
        (e.g. cache-miss checks). Use `get_by_id` when absence is an error.

        Args:
            record_id: UUID of the record to fetch.

        Returns:
            The ORM model instance, or None.
        """
        return await self.session.get(self.model_class, record_id)

    async def get_by_field(self, field_name: str, value: Any) -> ModelT | None:
        """
        Fetch the first record where `field_name` equals `value`.

        Args:
            field_name: Name of the model attribute to filter on.
            value:      Value to match.

        Returns:
            The first matching ORM instance, or None.

        Raises:
            AttributeError: If `field_name` is not a valid column on the model.
        """
        column = getattr(self.model_class, field_name)
        stmt = select(self.model_class).where(column == value).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        order_by: Any = None,
    ) -> list[ModelT]:
        """
        Return a paginated list of all records.

        Args:
            limit:    Maximum number of records to return (default 20).
            offset:   Number of records to skip (default 0).
            order_by: Optional SQLAlchemy column expression for ordering.
                      Example: `VerifiedClaim.created_at.desc()`

        Returns:
            List of ORM model instances.
        """
        stmt = select(self.model_class)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """
        Return the total number of records in the table.

        Returns:
            Integer count of all rows.
        """
        stmt = select(func.count()).select_from(self.model_class)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def exists(self, record_id: uuid.UUID) -> bool:
        """
        Check whether a record with the given UUID exists.

        More efficient than `get_by_id_or_none` for existence checks
        because it issues a COUNT(*) with LIMIT 1.

        Args:
            record_id: UUID to check.

        Returns:
            True if the record exists, False otherwise.
        """
        pk_column = getattr(self.model_class, "id")
        stmt = select(func.count()).where(pk_column == record_id).limit(1)
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def create(self, instance: ModelT) -> ModelT:
        """
        Persist a new ORM model instance to the database.

        The instance must be fully constructed before calling this method.
        This method adds the instance to the session and flushes (but does
        NOT commit — the session dependency handles that).

        Args:
            instance: A new, unsaved ORM model instance.

        Returns:
            The persisted instance (with server-generated fields populated
            after the flush, e.g. `created_at`).

        Raises:
            DuplicateRecordError: On UNIQUE constraint violation.
        """
        try:
            self.session.add(instance)
            await self.session.flush()
            await self.session.refresh(instance)
            logger.debug(
                "Record created",
                extra={"model": self.model_class.__name__, "id": str(instance.id)},
            )
            return instance
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateRecordError(
                model=self.model_class.__name__,
                field="unique_constraint",
                value=str(exc.orig),
            ) from exc

    async def bulk_create(self, instances: list[ModelT]) -> list[ModelT]:
        """
        Persist multiple new ORM instances in a single flush.

        Uses `session.add_all` for efficiency — one round-trip instead of N.
        Particularly important for Stage 12 (Persistence) which writes
        search queries and retrieved articles in bulk.

        Args:
            instances: List of new, unsaved ORM model instances.

        Returns:
            The list of persisted instances with server-generated fields populated.

        Raises:
            DuplicateRecordError: On UNIQUE constraint violation in any row.
        """
        if not instances:
            return []
        try:
            self.session.add_all(instances)
            await self.session.flush()
            for instance in instances:
                await self.session.refresh(instance)
            logger.debug(
                "Bulk records created",
                extra={"model": self.model_class.__name__, "count": len(instances)},
            )
            return instances
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateRecordError(
                model=self.model_class.__name__,
                field="unique_constraint",
                value=str(exc.orig),
            ) from exc

    async def update(self, instance: ModelT, **fields: Any) -> ModelT:
        """
        Update specified fields on an existing ORM model instance.

        Mutates the instance in-place, flushes the changes, and refreshes
        the instance to pick up any server-side `onupdate` values (e.g. `updated_at`).

        Args:
            instance: An existing, tracked ORM model instance.
            **fields: Column-name → new-value pairs to update.

        Returns:
            The updated and refreshed instance.

        Example::

            claim = await claim_repo.get_by_id(claim_id)
            updated = await claim_repo.update(claim, status=ClaimStatus.COMPLETED)
        """
        for field, value in fields.items():
            if not hasattr(instance, field):
                raise AttributeError(
                    f"{self.model_class.__name__} has no attribute {field!r}"
                )
            setattr(instance, field, value)

        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        logger.debug(
            "Record updated",
            extra={
                "model": self.model_class.__name__,
                "id": str(instance.id),
                "fields": list(fields.keys()),
            },
        )
        return instance

    async def delete(self, instance: ModelT) -> None:
        """
        Delete an ORM model instance from the database.

        Args:
            instance: The tracked ORM instance to delete.
        """
        await self.session.delete(instance)
        await self.session.flush()
        logger.debug(
            "Record deleted",
            extra={"model": self.model_class.__name__, "id": str(instance.id)},
        )

    async def delete_by_id(self, record_id: uuid.UUID) -> None:
        """
        Fetch and delete a record by UUID.

        Args:
            record_id: UUID of the record to delete.

        Raises:
            RecordNotFoundError: If no record with the given ID exists.
        """
        instance = await self.get_by_id(record_id)
        await self.delete(instance)
