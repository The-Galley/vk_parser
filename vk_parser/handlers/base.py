from collections.abc import Sequence
from typing import TypeVar

import orjson
from aio_pika.patterns import Master
from aiohttp.web import Request
from aiohttp.web_exceptions import HTTPBadRequest
from pydantic import BaseModel, ValidationError

from vk_parser.generals.models.pagination import PaginationParams
from vk_parser.storages.parser_request import ParserRequestStorage
from vk_parser.storages.ping import PingStorage

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseHttpMixin:
    @property
    def request(self) -> Request:
        raise NotImplementedError


class DependenciesMixin(BaseHttpMixin):
    @property
    def parser_request_storage(self) -> ParserRequestStorage:
        return self.request.app["parser_request_storage"]

    @property
    def ping_storage(self) -> PingStorage:
        return self.request.app["ping_storage"]

    @property
    def amqp_master(self) -> Master:
        return self.request.app["amqp_master"]


class ListMixin(BaseHttpMixin):
    def _parse(self) -> PaginationParams:
        try:
            return PaginationParams.model_validate(self.request.query)
        except ValidationError:
            raise HTTPBadRequest(reason="Invalid pagination params")


class CreateMixin(BaseHttpMixin):
    async def _parse_json(self, schemas: Sequence[type[BaseModel]]) -> BaseModel:
        result = None
        for schema in schemas:
            result = await self._parse_schema(schema)
            match result:
                case BaseModel():
                    return result
                case orjson.JSONDecodeError():
                    raise HTTPBadRequest(reason="Invalid input params")
        if isinstance(result, ValidationError):
            raise HTTPBadRequest(text=result.json())
        raise HTTPBadRequest(reason="Incorrent input")

    async def _parse_schema(self, schema: type[ModelType]) -> ModelType | Exception:
        try:
            data = await self.request.json(loads=orjson.loads)
            return schema.model_validate(data)
        except (ValidationError, orjson.JSONDecodeError) as e:
            return e
