from __future__ import annotations

from typing import TypeAlias

from pydantic import StrictBool, StrictFloat, StrictInt, StrictStr

PropertyValue: TypeAlias = bool | int | float | str
# Keep integer/float ahead of bool so schema-driven clients preserve enum-like
# numeric values such as InitialSwitchSetting=1 instead of coercing them to true.
StrictPropertyValue: TypeAlias = StrictInt | StrictFloat | StrictBool | StrictStr
