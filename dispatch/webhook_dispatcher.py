"""
NewsStreamAI — Multi-Channel Webhook Dispatcher
Delivers formatted alerts to Discord, Slack, and generic webhook endpoints.
"""
import httpx
from typing import Optional
from core.models import AlertPayload
from config.settings import settings
from core.logger import logger

from dispatch.telegram_bot import telegram_dispatcher

class WebhookDispatcher:
    @staticmethod
    async def dispatch_alert(alert: AlertPayload, custom_url: Optional[str] = None) -> bool:
        """Sends rich alert payload to configured endpoints."""
        urls_to_notify = []
        if custom_url:
            urls_to_notify.append(custom_url)
        if settings.GENERIC_WEBHOOK_URL:
            urls_to_notify.append(settings.GENERIC_WEBHOOK_URL)
        if settings.DISCORD_WEBHOOK_URL:
            await WebhookDispatcher._send_discord(settings.DISCORD_WEBHOOK_URL, alert)
        if settings.SLACK_WEBHOOK_URL:
            await WebhookDispatcher._send_slack(settings.SLACK_WEBHOOK_URL, alert)
        if settings.ENABLE_TELEGRAM_NOTIFICATIONS:
            await telegram_dispatcher.send_alert(alert)

        success = True
        for url in urls_to_notify:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, json=alert.dict())
                    if resp.status_code >= 400:
                        logger.warning(f"Webhook response status {resp.status_code} from {url}")
                        success = False
            except Exception as e:
                logger.error(f"Failed to dispatch webhook to {url}: {e}")
                success = False
                
        return success

    @staticmethod
    async def _send_discord(webhook_url: str, alert: AlertPayload):
        """Formats Discord embed."""
        sources_md = "\n".join([f"• [{s.name}]({s.url}) ({s.domain})" for s in alert.sources[:4]])
        bullets_md = "\n".join([f"• {b}" for b in alert.bullet_points])
        
        embed = {
            "title": f"🚨 {alert.push_title}",
            "description": f"**Synthèse Faits Clés :**\n{bullets_md}\n\n**Sources Recoupées :**\n{sources_md}",
            "color": 0xFF3366 if alert.velocity_score > 0.6 else 0x3399FF,
            "fields": [
                {"name": "Vélocité", "value": f"{alert.velocity_score:.2f}/1.0", "inline": True},
                {"name": "Pertinence Profil", "value": f"{alert.relevance_score:.2f}/1.0", "inline": True},
                {"name": "Indice de Fiabilité", "value": alert.reliability_label, "inline": True},
            ],
            "footer": {"text": "NewsStreamAI • Moteur d'Alerting Temps Réel"}
        }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(webhook_url, json={"embeds": [embed]})
        except Exception as e:
            logger.warning(f"Discord dispatch error: {e}")

    @staticmethod
    async def _send_slack(webhook_url: str, alert: AlertPayload):
        """Formats Slack block kit message."""
        bullets_text = "\n".join([f"• {b}" for b in alert.bullet_points])
        sources_text = " | ".join([f"<{s.url}|{s.name}>" for s in alert.sources[:3]])
        
        payload = {
            "text": f"🚨 *{alert.push_title}*",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🚨 {alert.push_title}*\n\n{bullets_text}\n\n*Sources :* {sources_text}"
                    }
                }
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(webhook_url, json=payload)
        except Exception as e:
            logger.warning(f"Slack dispatch error: {e}")

webhook_dispatcher = WebhookDispatcher()
