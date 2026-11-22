"""Official PostgresSaver with a closed, validated JSON serializer; no pickle/import hooks."""

import base64
import json
import time
from contextlib import contextmanager
from datetime import datetime
from uuid import UUID

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from pydantic import BaseModel

from app.modules.evidence import schemas as evidence_schemas
from app.modules.investigation import live_schemas, resolution, resolution_schemas, schemas

MODELS = {
    f"{value.__module__}.{value.__name__}": value
    for module in (schemas, evidence_schemas, resolution, resolution_schemas, live_schemas)
    for value in vars(module).values()
    if isinstance(value, type)
    and issubclass(value, BaseModel)
    and value.__module__ == module.__name__
}


class SafeCheckpointSerializer:
    """Tagged containers prevent user dictionaries from masquerading as type markers."""

    def dumps_typed(self, value):
        def encode(v):
            if v is None or isinstance(v, str | int | float | bool):
                return ["value", v]
            if isinstance(v, UUID):
                return ["uuid", str(v)]
            if isinstance(v, datetime):
                return ["datetime", v.isoformat()]
            if isinstance(v, bytes):
                return ["bytes", base64.b64encode(v).decode("ascii")]
            if isinstance(v, BaseModel):
                key = f"{type(v).__module__}.{type(v).__name__}"
                if key not in MODELS:
                    raise ValueError("Unregistered checkpoint model")
                return ["model", key, v.model_dump_json()]
            if isinstance(v, dict):
                return ["dict", [[encode(k), encode(item)] for k, item in v.items()]]
            if isinstance(v, list | tuple | set):
                return [type(v).__name__, [encode(item) for item in v]]
            raise ValueError("Unsupported checkpoint type")

        return "safe-json-v1", json.dumps(encode(value), allow_nan=False).encode("utf-8")

    def loads_typed(self, data):
        kind, payload = data
        if kind != "safe-json-v1" or len(payload) > 4_000_000:
            raise ValueError("Unsupported checkpoint encoding")

        def decode(v):
            tag = v[0]
            if tag == "value":
                return v[1]
            if tag == "uuid":
                return UUID(v[1])
            if tag == "datetime":
                return datetime.fromisoformat(v[1])
            if tag == "bytes":
                return base64.b64decode(v[1], validate=True)
            if tag == "model" and v[1] in MODELS:
                return MODELS[v[1]].model_validate_json(v[2])
            if tag == "dict":
                return {decode(k): decode(item) for k, item in v[1]}
            if tag in ("list", "tuple", "set"):
                return {"list": list, "tuple": tuple, "set": set}[tag](
                    decode(item) for item in v[1]
                )
            raise ValueError("Unknown checkpoint type")

        return decode(json.loads(payload))


@contextmanager
def checkpoint_connection(engine):
    # raw_connection preserves test/host connect_args including an isolated search_path.
    connection = engine.raw_connection()
    driver = connection.driver_connection
    old_factory, old_autocommit = driver.row_factory, driver.autocommit
    try:
        driver.autocommit = True
        driver.row_factory = dict_row
        yield driver, PostgresSaver(driver, serde=SafeCheckpointSerializer())
    finally:
        if not driver.closed:
            driver.row_factory = old_factory
            driver.autocommit = old_autocommit
        connection.close()


def setup_checkpoints(engine):
    """Supported SDK lifecycle, serialized per schema; concurrent-index DDL needs autocommit."""
    with checkpoint_connection(engine) as (connection, saver):
        key = connection.execute("SELECT current_schema() AS name").fetchone()["name"]
        deadline = time.monotonic() + 30
        while not connection.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired",
            (f"ied-checkpoint-setup:{key}",),
        ).fetchone()["acquired"]:
            # Never block inside an advisory-lock SELECT: the SDK's concurrent
            # index migration could wait for that very query's virtual transaction.
            if time.monotonic() >= deadline:
                raise TimeoutError("Checkpoint setup is busy")
            time.sleep(0.05)
        try:
            saver.setup()
        finally:
            connection.execute(
                "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                (f"ied-checkpoint-setup:{key}",),
            )
