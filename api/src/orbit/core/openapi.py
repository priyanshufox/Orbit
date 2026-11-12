"""OpenAPI schema with the WebSocket event models added, so the web app gets types for both.

FastAPI only documents models used by HTTP routes; `RoomEvent` (core/events.py) travels over the
WebSocket, so it is merged into `components.schemas` here.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import TypeAdapter

from orbit.core.events import RoomEvent

REF_TEMPLATE = "#/components/schemas/{model}"


def install_openapi(app: FastAPI) -> None:
    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        event_schema = TypeAdapter(RoomEvent).json_schema(
            ref_template=REF_TEMPLATE, by_alias=True, mode="serialization"
        )
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        components.update(event_schema.pop("$defs", {}))
        components["RoomEvent"] = event_schema
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
