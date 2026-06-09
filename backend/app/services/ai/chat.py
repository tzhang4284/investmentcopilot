"""Streaming AI analyst chat: SSE agentic loop with tool use."""

from __future__ import annotations

import json
from typing import AsyncIterator

import anyio
from sqlalchemy.orm import Session

from .client import MODEL_DEEP, get_client
from .tools import TOOLS, dispatch

MAX_ITERATIONS = 8

SYSTEM_PROMPT = """You are the senior analyst at a one-person hedge fund. The user is the Portfolio Manager (PM); you work for them.

Your job: rigorous, institutional-quality equity analysis grounded in the PM's actual portfolio and live data from your tools.

Operating principles:
- Always ground claims in data. Use get_portfolio before commenting on the PM's positioning, get_fundamentals/get_comps before valuation judgments, get_insider_activity for insider questions, search_filings for disclosure questions.
- Think like a buy-side analyst: what's the variant view, what's priced in, what would change the thesis. Distinguish facts (from tools) from judgment (yours), and say which is which.
- Be direct and quantitative. Use specific numbers from tool results. Flag stale or missing data honestly rather than guessing.
- When the PM asks for a recommendation, give one — with a clear bull case, bear case, and what you'd want to see before sizing up. You advise; the PM decides.
- Keep responses tight. Tables for comparisons, short paragraphs for argument. No filler, no disclaimers about not being a financial advisor — the PM knows.
"""


def _sse(event: dict) -> dict:
    return {"event": "message", "data": json.dumps(event)}


async def stream_chat(db: Session, messages: list[dict]) -> AsyncIterator[dict]:
    """Run the agentic loop, yielding SSE-ready dicts.

    Event types: text {delta}, tool_call {name, input}, tool_result {name, is_error},
    done {}, error {message}.
    """
    client = get_client()
    history = list(messages)

    try:
        for _ in range(MAX_ITERATIONS):
            send_stream, receive_stream = anyio.create_memory_object_stream(max_buffer_size=64)

            def run_turn(send=send_stream):
                # Blocking SDK streaming in a worker thread; deltas forwarded via memory stream.
                try:
                    with client.messages.stream(
                        model=MODEL_DEEP,
                        max_tokens=4096,
                        thinking={"type": "adaptive"},
                        system=[
                            {
                                "type": "text",
                                "text": SYSTEM_PROMPT,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                        tools=TOOLS,
                        messages=history,
                    ) as s:
                        for text in s.text_stream:
                            anyio.from_thread.run(send.send, {"type": "text", "delta": text})
                        final = s.get_final_message()
                    anyio.from_thread.run(send.send, {"type": "_final", "message": final})
                except Exception as exc:
                    anyio.from_thread.run(send.send, {"type": "error", "message": str(exc)})
                finally:
                    anyio.from_thread.run(send.aclose)

            final_message = None
            async with anyio.create_task_group() as tg:
                tg.start_soon(anyio.to_thread.run_sync, run_turn)
                async with receive_stream:
                    async for item in receive_stream:
                        if item["type"] == "_final":
                            final_message = item["message"]
                        elif item["type"] == "error":
                            yield _sse(item)
                            return
                        else:
                            yield _sse(item)

            if final_message is None:
                yield _sse({"type": "error", "message": "stream ended unexpectedly"})
                return

            # Serialize assistant content for the next turn.
            assistant_content = [b.model_dump() for b in final_message.content]
            history.append({"role": "assistant", "content": assistant_content})

            if final_message.stop_reason != "tool_use":
                break

            tool_results = []
            for block in final_message.content:
                if block.type != "tool_use":
                    continue
                yield _sse({"type": "tool_call", "name": block.name, "input": block.input})
                result, is_error = await anyio.to_thread.run_sync(
                    dispatch, db, block.name, block.input
                )
                yield _sse({"type": "tool_result", "name": block.name, "is_error": is_error})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        **({"is_error": True} if is_error else {}),
                    }
                )
            history.append({"role": "user", "content": tool_results})

        yield _sse({"type": "done"})
    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})
