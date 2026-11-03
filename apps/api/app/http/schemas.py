"""Wire types shared by response contracts."""

from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer

# Preserve the existing UTC offset spelling (+00:00), including archived timestamps.
WireDatetime = Annotated[
    datetime, PlainSerializer(lambda value: value.isoformat(), return_type=str)
]
