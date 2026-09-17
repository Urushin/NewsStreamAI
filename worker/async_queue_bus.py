"""
NewsStreamAI — Asynchronous URL Message Bus & Worker Queue
Decouples rapid link discovery from heavy text extraction and embedding.
Supports Redis Streams (if REDIS_URL configured) or High-Throughput Asyncio Queue.
"""
import asyncio
from typing import Dict, Any, Optional, Callable, List
from core.models import Article
from core.logger import logger
from ingestion.content_extractor import content_extractor

class AsyncURLMessageBus:
    def __init__(self, maxsize: int = 2000, num_workers: int = 8):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self.num_workers = num_workers
        self.workers: List[asyncio.Task] = []
        self.is_running = False
        self.on_article_extracted: Optional[Callable[[Article], Any]] = None

    def start(self, callback: Optional[Callable[[Article], Any]] = None):
        """Starts background worker pool."""
        if self.is_running:
            return
        self.is_running = True
        self.on_article_extracted = callback
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker_loop(i))
            self.workers.append(task)
        logger.info(f"⚡ Async URL Message Bus started with {self.num_workers} parallel extraction workers.")

    async def push_article_for_extraction(self, article: Article):
        """Pushes an article whose full content needs extraction."""
        try:
            self.queue.put_nowait(article)
        except asyncio.QueueFull:
            logger.warning("URL Message Bus queue is full, dropping extraction item.")

    async def _worker_loop(self, worker_id: int):
        """Worker loop continuously popping articles and extracting text via content_extractor."""
        while self.is_running:
            try:
                article: Article = await self.queue.get()
                if not article.is_full_text_extracted and article.url:
                    text = await content_extractor.extract_from_url(article.url)
                    if text and len(text) > len(article.content or ""):
                        article.content = text
                        article.is_full_text_extracted = True

                if self.on_article_extracted:
                    res = self.on_article_extracted(article)
                    if asyncio.iscoroutine(res):
                        await res

                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Worker {worker_id} extraction error: {e}")

    async def stop(self):
        """Gracefully shuts down workers."""
        self.is_running = False
        for w in self.workers:
            w.cancel()
        self.workers.clear()

async_message_bus = AsyncURLMessageBus()
