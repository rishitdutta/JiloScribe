from typing import Iterable, Mapping

type JSON = int | bool | float | str | None | Iterable[JSON] | Mapping[str, JSON]
