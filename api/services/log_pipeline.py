from __future__ import annotations

import asyncio
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from db.logs import log_event
from services.utils import stream_tokens_from_sse


def schedule_log_event(
    *,
    session: AsyncSession,
    event: dict[str, Any],
    stream_body: str | None = None,
    request_body: dict[str, Any] | None = None,
    log_tasks: set[asyncio.Task],
) -> None:
    async def _persist() -> None:
        if stream_body is not None:
            messages: list[dict[str, Any]] | None = None
            if request_body and isinstance(request_body.get("messages"), list):
                messages = request_body["messages"]
            input_tokens, output_tokens, total_tokens = await asyncio.to_thread(
                stream_tokens_from_sse, stream_body, messages
            )
            event["input_tokens"] = input_tokens
            event["output_tokens"] = output_tokens
            event["total_tokens"] = total_tokens
        await log_event(session, event)

    task = asyncio.create_task(_persist())
    log_tasks.add(task)
    task.add_done_callback(log_tasks.discard)
