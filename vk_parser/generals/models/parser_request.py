from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from vk_parser.generals.enums import ParserTypes, RequestStatus


class SimpleVkInputData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parser_type: Literal[ParserTypes.VK_SIMPLE_DOWNLOAD]
    group_url: HttpUrl
    max_age: int


class ParsePostsVkInputData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parser_type: Literal[ParserTypes.VK_DOWNLOAD_AND_PARSED_POSTS]
    group_url: HttpUrl
    posted_up_to: datetime
    max_age: int


class UserStat(BaseModel):
    vk_id: int
    count: int


class ResultData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message: str
    user_stat: Sequence[UserStat]


class DetailParserRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    status: RequestStatus
    input_data: ParsePostsVkInputData | SimpleVkInputData = Field(
        ...,
        discriminator="parser_type",
    )
    result_data: ResultData | None
    finished_at: datetime | None
    error_message: str | None

    @property
    def parser_type(self) -> ParserTypes:
        return self.input_data.parser_type


class ParserRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    status: RequestStatus
    finished_at: datetime | None
    error_message: str | None
