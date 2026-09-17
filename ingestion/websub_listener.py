"""
NewsStreamAI — WebSub (PubSubHubbub) Real-Time Push Listener
Receives instantaneous push webhooks from media publisher hubs (e.g. Le Monde, CNN, NYT)
eliminating periodic polling latency.
"""
import re
from typing import Optional, List, Dict, Any, Callable
from urllib.parse import urlparse
from fastapi import APIRouter, Request, Response, HTTPException
import httpx
from core.models import Article
from core.logger import logger
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield
from clustering.deduplicator import URLNormalizer
from ingestion.rss_poller import rss_poller

websub_router = APIRouter(prefix="/api/websub", tags=["WebSub Push"])

class WebSubManager:
    def __init__(self):
        self.subscribed_topics: Dict[str, str] = {} # topic_url -> hub_url
        self.incoming_article_callbacks: List[Callable[[List[Article]], Any]] = []

    def register_callback(self, cb: Callable[[List[Article]], Any]):
        """Registers a callback to be notified when articles are pushed by WebSub hubs."""
        self.incoming_article_callbacks.append(cb)

    async def subscribe_topic(self, hub_url: str, topic_url: str, callback_url: str) -> bool:
        """Sends a subscription request to the publisher's WebSub hub."""
        data = {
            "hub.callback": callback_url,
            "hub.mode": "subscribe",
            "hub.topic": topic_url,
            "hub.lease_seconds": "864000" # 10 days
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(hub_url, data=data)
                if resp.status_code in (202, 204, 200):
                    self.subscribed_topics[topic_url] = hub_url
                    logger.info(f"⚡ WebSub: Subscription requested for topic '{topic_url}' to hub '{hub_url}'")
                    return True
                else:
                    logger.warning(f"WebSub subscribe failed: HTTP {resp.status_code}")
                    return False
        except Exception as e:
            logger.error(f"WebSub subscribe error: {e}")
            return False

websub_manager = WebSubManager()

@websub_router.get("/callback")
async def websub_challenge_verification(
    request: Request
):
    """
    WebSub Hub challenge verification:
    GET query contains hub.mode, hub.topic, hub.challenge, hub.lease_seconds.
    Must return hub.challenge with status 200 to confirm subscription.
    """
    params = request.query_params
    hub_mode = params.get("hub.mode")
    hub_challenge = params.get("hub.challenge")
    hub_topic = params.get("hub.topic")

    if hub_mode in ("subscribe", "unsubscribe") and hub_challenge:
        logger.info(f"✅ WebSub Hub verified challenge for topic '{hub_topic}' (mode: {hub_mode})")
        return Response(content=hub_challenge, media_type="text/plain", status_code=200)

    raise HTTPException(status_code=400, detail="Invalid WebSub challenge request")

@websub_router.post("/callback")
async def websub_push_content(request: Request):
    """
    Receives pushed XML feeds as soon as an article is published by the media outlet.
    Immediately parses items and dispatches them into the processing pipeline.
    """
    body = await request.body()
    xml_text = body.decode("utf-8", errors="replace")

    if not xml_text:
        return Response(status_code=204)

    # Use AsyncRSSPoller's robust XML parser
    items = rss_poller._parse_xml_items(xml_text)
    articles: List[Article] = []

    for item in items:
        link = URLNormalizer.normalize(item.get("link", ""))
        title = item.get("title", "").strip()
        summary = item.get("summary", "").strip()
        img_url = item.get("image_url")

        if not link or not title:
            continue

        domain = (urlparse(link).hostname or "").replace("www.", "").lower()
        reputation_score, tier = SourceReputationDB.evaluate_domain(domain)
        penalty, biases = BiasShield.inspect(title, summary)

        articles.append(Article(
            title=title,
            url=link,
            source_name=domain.split(".")[0].capitalize(),
            domain=domain,
            content=summary,
            category="Dépêche WebSub Push",
            tier=tier,
            reliability_score=round(reputation_score * penalty, 2),
            detected_biases=biases,
            image_url=img_url
        ))

    if articles:
        logger.alert(f"⚡ WebSub: Instantaneously received {len(articles)} pushed articles without polling!")
        for cb in websub_manager.incoming_article_callbacks:
            try:
                res = cb(articles)
                if hasattr(res, "__await__"):
                    await res
            except Exception as e:
                logger.error(f"Error in WebSub callback: {e}")

    return Response(status_code=200, content="OK")
