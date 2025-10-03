import uuid
from typing import Annotated, Optional

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from aiori_agent.utils import get_model_name


HOSTNAME_REGEX = r"^([a-zA-Z0-9-]{1,63})(\.[a-zA-Z-][a-zA-Z0-9-]{0,62})*$"
DOMAIN_NAME_REGEX = r"^([a-zA-Z0-9-]{1,63})(\.[a-zA-Z0-9-]{1,63})+$"

Hostname = Annotated[str, Field(pattern=HOSTNAME_REGEX, json_schema_extra={ 'format': 'hostname',  })]
Domain = Annotated[str, Field(pattern=DOMAIN_NAME_REGEX, json_schema_extra={ 'format': 'domain',  })]

class MeasurementQuery(BaseModel):
    id: SkipJsonSchema[Optional[uuid.UUID]] = Field(default_factory=uuid.uuid4)
    # id: Annotated[SkipJsonSchema[str], Field(default_factory=lambda: uuid.uuid4().hex)]
    # type: Optional[str] = Field(default_factory=get_model_name)

    # @computed_field
    # @property
    @classmethod
    def model_type(cls) -> str:
        return get_model_name(cls)