
from __future__ import annotations

import logging
import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateRecordError, RecordNotFoundError
from app.shared.base_model import Base

logger = logging.getLogger(__name__)


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):

    model_class: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session





    async def get_by_id(self, record_id: uuid.UUID) -> ModelT:
        result = await self.session.get(self.model_class, record_id)
        if result is None:
            raise RecordNotFoundError(
                model=self.model_class.__name__,
                identifier=str(record_id),
            )
        return result

    async def get_by_id_or_none(self, record_id: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model_class, record_id)

    async def get_by_field(self, field_name: str, value: Any) -> ModelT | None:
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
        stmt = select(self.model_class)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model_class)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def exists(self, record_id: uuid.UUID) -> bool:
        pk_column = getattr(self.model_class, "id")
        stmt = select(func.count()).where(pk_column == record_id).limit(1)
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0





    async def create(self, instance: ModelT) -> ModelT:
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
        await self.session.delete(instance)
        await self.session.flush()
        logger.debug(
            "Record deleted",
            extra={"model": self.model_class.__name__, "id": str(instance.id)},
        )

    async def delete_by_id(self, record_id: uuid.UUID) -> None:
        instance = await self.get_by_id(record_id)
        await self.delete(instance)
