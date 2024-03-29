import logging
from asyncio import gather
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ScalarResult, func, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vk_parser.db.models.parser_request import ParserRequest as ParserRequestDb
from vk_parser.db.utils import inject_session
from vk_parser.generals.enums import ParserTypes, RequestStatus
from vk_parser.generals.models.pagination import PaginationResponse
from vk_parser.generals.models.parser_request import (
    DetailParserRequest,
    ParserRequest,
    Result,
)
from vk_parser.storages.base import PaginationMixin

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParserRequestStorage(PaginationMixin):
    session_factory: async_sessionmaker[AsyncSession]

    async def get_pagination(
        self,
        page: int,
        page_size: int,
    ) -> PaginationResponse[ParserRequest]:
        query = select(ParserRequestDb)
        return await self._paginate(
            query=query,
            page=page,
            page_size=page_size,
            model_type=ParserRequest,
        )

    async def admin_pagination(
        self,
        page: int,
        page_size: int,
    ) -> PaginationResponse[DetailParserRequest]:
        query = select(ParserRequestDb).order_by(ParserRequestDb.created_at.desc())
        return await self._paginate(
            query=query,
            page=page,
            page_size=page_size,
            model_type=DetailParserRequest,
        )

    @inject_session
    async def get_detail(
        self,
        session: AsyncSession,
        id_: int,
    ) -> DetailParserRequest | None:
        query = select(ParserRequestDb).filter_by(id=id_)
        obj = (await session.scalars(query)).first()
        return DetailParserRequest.model_validate(obj) if obj else None

    @inject_session
    async def create(
        self,
        session: AsyncSession,
        input_data: Mapping[str, Any],
    ) -> DetailParserRequest | None:
        query = (
            insert(ParserRequestDb)
            .values(
                input_data=input_data,
            )
            .returning(ParserRequestDb)
        )
        try:
            result: ScalarResult[ParserRequestDb] = await session.scalars(query)
            await session.commit()
        except DBAPIError:
            log.warning(
                "Error in creating parser request: %s", input_data, exc_info=True
            )
            return None
        return DetailParserRequest.model_validate(result.one())

    @inject_session
    async def update_status(
        self,
        session: AsyncSession,
        id_: int,
        status: RequestStatus,
    ) -> DetailParserRequest | None:
        query = (
            update(ParserRequestDb)
            .where(ParserRequestDb.id == id_)
            .values(status=status)
            .returning(ParserRequestDb)
        )
        try:
            result = await session.scalars(query)
            await session.commit()
            return DetailParserRequest.model_validate(result.one())
        except DBAPIError as e:
            log.warning("Error updating: %s", e)

        return None

    @inject_session
    async def save_error(
        self,
        session: AsyncSession,
        id_: int,
        finished_at: datetime,
        error_message: str,
    ) -> None:
        query = (
            update(ParserRequestDb)
            .where(ParserRequestDb.id == id_)
            .values(
                finished_at=finished_at,
                status=RequestStatus.FAILED,
                error_message=error_message,
            )
        )
        try:
            await session.execute(query)
            await session.commit()
        except DBAPIError:
            log.warning("Error save error")

    @inject_session
    async def save_empty_result(
        self,
        session: AsyncSession,
        id_: int,
        finished_at: datetime,
        message: str,
    ) -> None:
        query = (
            update(ParserRequestDb)
            .where(ParserRequestDb.id == id_)
            .values(
                finished_at=finished_at,
                status=RequestStatus.EMPTY,
                result_data={
                    "message": message,
                    "user_stat": [],
                },
            )
        )
        try:
            await session.execute(query)
            await session.commit()
        except DBAPIError:
            log.warning("Error save error")

    @inject_session
    async def save_successful_result(
        self,
        session: AsyncSession,
        id_: int,
        result: Result,
        finished_at: datetime,
    ) -> None:
        query = (
            update(ParserRequestDb)
            .where(ParserRequestDb.id == id_)
            .values(
                finished_at=finished_at,
                status=RequestStatus.SUCCESSFUL,
                result_data=result.model_dump(),
            )
        )
        try:
            await session.execute(query)
            await session.commit()
        except DBAPIError:
            log.warning("Error save error")

    @inject_session
    async def stat_by_type(
        self, session: AsyncSession, parser_type: ParserTypes
    ) -> tuple[ParserTypes, Sequence[tuple[RequestStatus, int]]]:
        query = (
            select(ParserRequestDb.status, func.count())
            .group_by(
                ParserRequestDb.status,
            )
            .filter(ParserRequestDb.input_data["parser_type"].astext == parser_type)
        )
        return parser_type, (await session.execute(query)).fetchall()  # type: ignore[return-value]

    async def stat(self) -> Sequence[tuple[ParserTypes, RequestStatus, int]]:
        tasks = [self.stat_by_type(parser_type=pt) for pt in ParserTypes]
        stat = await gather(*tasks)
        output = []
        for pt, res in stat:
            for req_status, count in res:
                output.append((pt, req_status, count))
        return output
