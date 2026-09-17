"""
NewsStreamAI — Telegram Instant Push Dispatcher
Sends formatted real-time news alerts and fast-track breaking bulletins directly to Telegram.
"""
import html
import re
import httpx
from typing import Optional, List
from core.models import AlertPayload, Article
from config.settings import settings
from core.logger import logger

class TelegramDispatcher:
    def __init__(self):
        pass

    def _get_credentials(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        bot_token = token or settings.TELEGRAM_BOT_TOKEN
        target_chat = chat_id or settings.TELEGRAM_CHAT_ID
        return bot_token.strip(), target_chat.strip()

    async def send_alert(
        self,
        alert: AlertPayload,
        token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> bool:
        """Sends a consolidated multi-source AlertPayload to Telegram."""
        bot_token, target_chat = self._get_credentials(token, chat_id)
        if not bot_token or not target_chat:
            logger.debug("Telegram alert skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
            return False

        # Format HTML Message
        title_esc = html.escape(alert.push_title)
        category_esc = html.escape(alert.category.upper())
        
        # Reliability badge
        reliability_badge = "🟢 Fait Fiable" if "FIABLE" in alert.reliability_label else "🟡 Signal Émergent"
        
        # Bullets
        bullets_html = ""
        for b in alert.bullet_points[:4]:
            b_clean = html.escape(b)
            b_formatted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', b_clean)
            bullets_html += f"• {b_formatted}\n"

        # Sources links
        sources_html = []
        for s in alert.sources[:4]:
            s_name = html.escape(s.name)
            s_url = html.escape(s.url)
            sources_html.append(f'<a href="{s_url}">{s_name}</a>')
        sources_line = " | ".join(sources_html) if sources_html else "Sources directes"

        velocity_pct = int(alert.velocity_score * 100)
        relevance_pct = int(alert.relevance_score * 100)

        message_text = (
            f"🚨 <b>[{category_esc}] {title_esc}</b>\n\n"
            f"<b>Faits Clés :</b>\n{bullets_html}\n"
            f"📰 <b>Sources :</b> {sources_line}\n\n"
            f"⚡ Vélocité: <b>{velocity_pct}%</b> | 🎯 Pertinence: <b>{relevance_pct}%</b> | {reliability_badge}\n"
            f"<i>MyNews AI • Notification Instantanée</i>"
        )

        return await self._send_raw_message(bot_token, target_chat, message_text)

    async def send_fast_track_bulletin(
        self,
        article: Article,
        matched_entity: str,
        token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> bool:
        """Sends an ultra-fast flash bulletin (<500ms) for watchlist hits or breaking signals."""
        bot_token, target_chat = self._get_credentials(token, chat_id)
        if not bot_token or not target_chat:
            logger.debug("Telegram fast-track skipped: credentials missing.")
            return False

        title_esc = html.escape(article.title)
        source_esc = html.escape(article.source_name)
        url_esc = html.escape(article.url)
        entity_esc = html.escape(matched_entity)
        
        snippet = article.content[:200].strip() if article.content else "Dépêche en cours de transmission..."
        snippet_esc = html.escape(snippet)

        is_spoiler = any(w in article.title.lower() for w in ["spoiler", "leak", "raw scan"])
        tag = "⚡ FAST-TRACK SPOILER/LEAK" if is_spoiler else "⚡ FAST-TRACK BREAKING"

        message_text = (
            f"🔥 <b>{tag} : #{entity_esc}</b>\n\n"
            f"<b>{title_esc}</b>\n\n"
            f"📝 <i>{snippet_esc}...</i>\n\n"
            f"🔗 <a href=\"{url_esc}\">Lire la source originale ({source_esc})</a>\n\n"
            f"<i>Match Watchlist : <b>{entity_esc}</b> • Analyse IA en cours</i>"
        )

        return await self._send_raw_message(bot_token, target_chat, message_text)

    async def test_connection(self, token: str, chat_id: str) -> bool:
        """Tests telegram connection with a heartbeat ping."""
        text = "🔔 <b>MyNews AI : Connexion Telegram Établie !</b>\nVous recevrez ici vos alertes en temps réel et alertes Fast-Track."
        return await self._send_raw_message(token, chat_id, text)

    async def _send_raw_message(self, bot_token: str, chat_id: str, text: str) -> bool:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.success(f"📱 Telegram notification sent successfully to chat {chat_id[:4]}***")
                    return True
                else:
                    logger.warning(f"Telegram API returned status {resp.status_code}: {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

telegram_dispatcher = TelegramDispatcher()
