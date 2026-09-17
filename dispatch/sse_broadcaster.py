"""
NewsStreamAI — Server-Sent Events (SSE) Broadcaster
Broadcasts real-time alert events, live pipeline telemetry steps, and granular ingestion logs using proper ServerSentEvent encoding.
"""
import asyncio
import json
from typing import List, AsyncGenerator, Dict, Any, Optional
from sse_starlette.sse import ServerSentEvent
from core.models import AlertPayload
from core.logger import logger

class SSEBroadcaster:
    def __init__(self):
        self.subscribers: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Registers a new SSE listener queue."""
        q = asyncio.Queue(maxsize=500)
        self.subscribers.append(q)
        logger.info(f"📡 New SSE subscriber connected. Total active listeners: {len(self.subscribers)}")
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Unregisters an SSE listener queue."""
        if q in self.subscribers:
            self.subscribers.remove(q)
            logger.info(f"🔌 SSE subscriber disconnected. Remaining: {len(self.subscribers)}")

    def _enqueue(self, queue: asyncio.Queue, item: ServerSentEvent):
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            if item.event in {"pipeline_step", "pipeline_log"}:
                return
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            try:
                queue.put_nowait(ServerSentEvent(event="resync", data="{}"))
                queue.put_nowait(item)
            except asyncio.QueueFull:
                pass

    async def broadcast_event(self, event_type: str, payload: Any):
        """Pushes a typed ServerSentEvent object to all active subscribers."""
        if not self.subscribers:
            return
            
        if isinstance(payload, str):
            json_str = payload
        else:
            json_str = json.dumps(payload, default=str, ensure_ascii=False)
            
        sse_item = ServerSentEvent(data=json_str, event=event_type)
        
        for q in tuple(self.subscribers):
            self._enqueue(q, sse_item)

    async def broadcast_v2_event(self, event_type: str, event_id: str, payload: Any):
        """Emit a V2 update with a durable event identifier for reconnect-aware clients."""
        if not self.subscribers:
            return
        data = json.dumps(payload, default=str, ensure_ascii=False)
        item = ServerSentEvent(data=data, event=event_type, id=f"v2:{event_id}")
        for queue in tuple(self.subscribers):
            self._enqueue(queue, item)

    async def broadcast_alert(self, alert: AlertPayload):
        """Pushes an alert payload with event type 'alert'."""
        await self.broadcast_event("alert", alert.model_dump(mode="json"))

    async def broadcast_pipeline_step(
        self,
        step_id: str,
        step_title: str,
        details: str,
        progress_pct: int,
        news_count: int = 0,
        summaries_count: int = 0,
        status: str = "running",
        task_label: str = "Traitement en cours",
        elapsed_seconds: float = 0.0
    ):
        """Broadcasts live pipeline progress telemetry with news and summary counters."""
        payload = {
            "step_id": step_id,
            "step_title": step_title,
            "details": details,
            "progress": progress_pct,
            "progress_pct": progress_pct,
            "news_count": news_count,
            "summaries_count": summaries_count,
            "status": status,
            "task_label": task_label,
            "elapsed_seconds": round(elapsed_seconds, 1)
        }
        await self.broadcast_event("pipeline_step", payload)

    async def broadcast_pipeline_log(
        self,
        log_line: str,
        progress_pct: Optional[int] = None,
        news_count: Optional[int] = None,
        source_name: Optional[str] = None,
        summaries_count: Optional[int] = None
    ):
        """Broadcasts a live log line from the ingestion/clustering/synthesis engines."""
        payload = {
            "log": log_line,
            "progress": progress_pct,
            "news_count": news_count,
            "source": source_name,
            "summaries_count": summaries_count
        }
        await self.broadcast_event("pipeline_log", payload)

    async def event_generator(self, q: asyncio.Queue) -> AsyncGenerator[ServerSentEvent, None]:
        """Async generator yielding ServerSentEvent instances directly to EventSourceResponse."""
        try:
            yield ServerSentEvent(event="connected", data=json.dumps({"status": "connected"}))
            while True:
                msg = await q.get()
                yield msg
        finally:
            self.unsubscribe(q)

sse_broadcaster = SSEBroadcaster()
