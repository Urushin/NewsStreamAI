"""
NewsStreamAI — Real-Time Streaming Daemon
Continuous background orchestration: StreamHub Multi-Protocol Ingestion -> Vectorizing -> Sliding Clustering -> Semantic Dedup -> Scorer -> Synthesis -> Dispatch.
Supports real-time pulses, 24h deep scan catch-up, and live visual telemetry with granular logs and news & summary counters.
"""
import time
import asyncio
import json
from pathlib import Path
from typing import List, Dict
from core.models import UserProfile, Article, AlertPayload, AlertSource
from core.logger import logger
from config.settings import settings
from ingestion.stream_hub import stream_hub
from vector.embedder import embedder
from clustering.sliding_window import sliding_engine
from clustering.semantic_dedup import semantic_deduplicator
from matching.hybrid_scorer import HybridScorer
from synthesis.alert_synthesizer import alert_synthesizer
from dispatch.webhook_dispatcher import webhook_dispatcher
from dispatch.sse_broadcaster import sse_broadcaster
from dispatch.telegram_bot import telegram_dispatcher
from matching.watchlist_engine import watchlist_engine

ALERTS_STORE_FILE = Path("data/dispatched_alerts.json")

def persist_daemon_alerts(alerts: List[AlertPayload]):
    try:
        ALERTS_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        raw = [a.model_dump(mode="json") for a in alerts[-120:]]
        with open(ALERTS_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to persist dispatched alerts from daemon: {e}")

class RealTimeStreamDaemon:
    def __init__(self, profiles: List[UserProfile]):
        self.profiles = profiles
        self.running = False
        self.is_busy = False
        self._running_catchup = False
        self._last_user_scan_at: float = 0.0
        self._lock = asyncio.Lock()
        self.dispatched_alerts: List[AlertPayload] = []

    async def start(self):
        self.running = True
        logger.info(f"🚀 NewsStreamAI Daemon started. Monitoring across 8 ingestion protocols for {len(self.profiles)} active user profiles.")
        
        while self.running:
            try:
                # Do not run periodic background tick during catch-up or within 60s after a user scan
                if not self._running_catchup and (time.time() - self._last_user_scan_at > 60.0):
                    await self.tick(manual=False)
            except Exception as e:
                logger.error(f"Error in stream daemon tick: {e}")
                
            await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)

    async def tick(self, manual: bool = False):
        """Polling cycle. Silent during periodic background ticks; broadcasts pipeline UI on manual triggers."""
        if self.is_busy or self._running_catchup:
            logger.info("⏱️ Stream daemon tick skipped: another operation (deep scan / pulse) is currently in progress.")
            return

        if manual:
            self._last_user_scan_at = time.time()

        async with self._lock:
            self.is_busy = True
            start_time = time.time()
            try:
                if manual:
                    # Interactive telemetry only on explicit user request
                    await sse_broadcaster.broadcast_pipeline_step(
                        step_id="ingestion",
                        step_title="Collecte & Ingestion des Flux",
                        details="Interrogation simultanée des flux RSS, Twitter et connecteurs en direct...",
                        progress_pct=15,
                        news_count=0,
                        summaries_count=0,
                        task_label="Scan Réseau Temps Réel",
                        elapsed_seconds=time.time() - start_time
                    )
                    await sse_broadcaster.broadcast_pipeline_log("🌐 Démarrage du scan des flux RSS, Twitter & API...")
                else:
                    logger.debug("⏱️ Ingestion pulse: background silent poll...")
                
                new_articles = await stream_hub.poll_all_sources(active_profiles=self.profiles)
                        
                if not new_articles:
                    logger.info("No new articles in this cycle.")
                    if manual:
                        await sse_broadcaster.broadcast_pipeline_log("✨ Toutes les sources sont à jour. Aucune nouvelle dépêche inédite.")
                        await sse_broadcaster.broadcast_pipeline_step(
                            step_id="completed",
                            step_title="Scan Terminé",
                            details="Toutes les sources sont à jour. Aucune nouvelle dépêche inédite.",
                            progress_pct=100,
                            news_count=0,
                            summaries_count=0,
                            status="done",
                            task_label="Scan Réseau Temps Réel",
                            elapsed_seconds=time.time() - start_time
                        )
                    return

                # Optional rollout step: persist canonical V2 facts before V1
                # performs any RAM clustering or user-facing dispatch.
                from storage_v2.config import v2_canonical_write_enabled
                if v2_canonical_write_enabled():
                    try:
                        from storage_v2.shadow import run_shadow_hook
                        canonical_report = await asyncio.to_thread(
                            run_shadow_hook, articles=new_articles, clusters=(), alerts=(), logger=logger, force=True
                        )
                        if canonical_report is not None:
                            for event_id in canonical_report.event_ids:
                                await sse_broadcaster.broadcast_v2_event(
                                    "v2_event_updated", event_id, {"event_id": event_id, "source": "v2_canonical"}
                                )
                    except Exception as exc:
                        logger.error(f"V2 canonical write hook failed: {type(exc).__name__}: {exc}")

                # Fast-Track evaluation: immediate push bulletin for watchlist hits and breaking signals
                await self._handle_fast_track_evaluation(new_articles)

                await self._process_articles_batch(new_articles, mode_label="Scan Réseau", start_time=start_time)
            except Exception as e:
                logger.error(f"Error in daemon tick execution: {e}")
            finally:
                self.is_busy = False

    async def _handle_fast_track_evaluation(self, articles: List[Article]):
        """Evaluates incoming articles against entity watchlists and triggers instant flash alerts."""
        if not settings.FAST_TRACK_ENABLED or not self.profiles:
            return

        active_profile = self.profiles[0]
        ft_dispatched_count = 0
        max_ft_per_batch = 3

        for a in articles:
            if ft_dispatched_count >= max_ft_per_batch:
                break

            should_ft, matched_entity = watchlist_engine.evaluate_fast_track(a, active_profile)
            if should_ft and matched_entity:
                # Deduplication: do not flood with identical headlines
                title_lower = (a.title or "").lower().strip()
                already_dispatched = any(
                    da.push_title and (
                        title_lower in da.push_title.lower() or
                        (matched_entity.lower() in da.push_title.lower() and da.category == a.category)
                    )
                    for da in self.dispatched_alerts[-20:]
                )
                if already_dispatched:
                    continue

                ft_dispatched_count += 1

                # 1. Instant Telegram bulletin
                try:
                    await telegram_dispatcher.send_fast_track_bulletin(a, matched_entity)
                except Exception as te:
                    logger.warning(f"Telegram fast-track dispatch error: {te}")

                # 2. Instant Fast-track single alert payload (full quality French synthesis)
                try:
                    single_alert = await alert_synthesizer.synthesize_single(
                        a, active_profile, cluster_id=f"ft-{a.id[:8]}", fast_mode=False
                    )
                    single_alert.is_fast_track = True
                    single_alert.matched_entities = a.matched_entities
                    # Ensure prefix is only added once
                    if not single_alert.push_title.startswith("⚡ ["):
                        single_alert.push_title = f"⚡ [{matched_entity}] {single_alert.push_title}"
                    
                    # Broadcast immediately via SSE
                    await sse_broadcaster.broadcast_alert(single_alert)
                    await sse_broadcaster.broadcast_pipeline_log(
                        f"⚡ FAST-TRACK DÉCLENCHÉ : #{matched_entity} sur {a.source_name} !"
                    )
                    self.dispatched_alerts.append(single_alert)
                except Exception as se:
                    logger.warning(f"Fast-track alert synthesis error: {se}")

    async def run_24h_catchup_cycle(self):
        """Deep 24-hour catch-up scan across the entire multi-protocol network."""
        if self._running_catchup:
            logger.warning("🌌 24h catch-up cycle requested while one is already active; skipping duplicate invocation.")
            return

        self._running_catchup = True
        self._last_user_scan_at = time.time()
        try:
            async with self._lock:
                self.is_busy = True
                start_time = time.time()
                try:
                    logger.info("🌌 Starting 24-Hour Deep Catch-Up Cycle...")

                    # ── Step 1 : 24h Ingestion ──
                    await sse_broadcaster.broadcast_pipeline_step(
                        step_id="ingestion",
                        step_title="Rattrapage Global 24 Heures",
                        details="Interrogation ciblée de 100+ flux prioritaires, Twitter, HackerNews, Reddit, arXiv et GDELT...",
                        progress_pct=15,
                        news_count=0,
                        summaries_count=0,
                        task_label="Rattrapage Global 24 Heures",
                        elapsed_seconds=time.time() - start_time
                    )
                    await sse_broadcaster.broadcast_pipeline_log("🌌 Lancement du scan 24h sur les sources prioritaires et connecteurs API...")

                    articles_24h = await stream_hub.poll_24h_deep_scan(active_profiles=self.profiles, max_feeds=100)

                    if not articles_24h:
                        await sse_broadcaster.broadcast_pipeline_log("✨ Toutes les actualités des 24h sont synchronisées.")
                        await sse_broadcaster.broadcast_pipeline_step(
                            step_id="completed",
                            step_title="Rattrapage 24h Terminé",
                            details="Toutes les actualités des 24 dernières heures sont déjà synchronisées.",
                            progress_pct=100,
                            news_count=0,
                            summaries_count=0,
                            status="done",
                            task_label="Rattrapage Global 24 Heures",
                            elapsed_seconds=time.time() - start_time
                        )
                        return

                    await self._process_articles_batch(articles_24h, mode_label="Rattrapage 24h", start_time=start_time)
                except Exception as e:
                    logger.error(f"Error in 24h catchup cycle: {e}")
                    await sse_broadcaster.broadcast_pipeline_log(f"❌ Erreur lors du rattrapage 24h : {e}")
                    await sse_broadcaster.broadcast_pipeline_step(
                        step_id="completed",
                        step_title="Rattrapage 24h Interrompu",
                        details=f"Erreur : {e}",
                        progress_pct=100,
                        status="error",
                        task_label="Rattrapage Global 24 Heures",
                        elapsed_seconds=time.time() - start_time
                    )
                finally:
                    self.is_busy = False
                    self._last_user_scan_at = time.time()
        finally:
            self._running_catchup = False
            self._last_user_scan_at = time.time()

    async def _process_articles_batch(self, articles: List[Article], mode_label: str, start_time: float):
        """Vectorizes, clusters, scores, synthesizes, and dispatches a batch of articles with real-time logs and counters."""
        total_news_found = len(articles)
        summaries_generated = 0

        await sse_broadcaster.broadcast_pipeline_log(
            f"📥 Collecte terminée : {total_news_found} dépêches uniques conservées après pré-déduplication !",
            news_count=total_news_found
        )

        # ── Step 2 : Vectorisation ──
        await sse_broadcaster.broadcast_pipeline_step(
            step_id="vectorization",
            step_title="Vectorisation Sémantique",
            details=f"Calcul des embeddings vectoriels haute dimension pour les {total_news_found} dépêches...",
            progress_pct=50,
            news_count=total_news_found,
            summaries_count=0,
            task_label=mode_label,
            elapsed_seconds=time.time() - start_time
        )
        await sse_broadcaster.broadcast_pipeline_log(f"🧬 Vectorisation : Calcul des embeddings sémantiques pour {total_news_found} textes...")

        texts = [f"{a.title}\n{a.content[:500]}" for a in articles]
        embeddings = await embedder.embed_texts(texts)
        for i, a in enumerate(articles):
            a.embedding = embeddings[i]

        await sse_broadcaster.broadcast_pipeline_log(f"🧬 Vectorisation : {len(embeddings)} vecteurs sémantiques calculés avec succès.")

        # ── Step 3 : Clustering ──
        await sse_broadcaster.broadcast_pipeline_step(
            step_id="clustering",
            step_title="Clustering & Recoupement Multi-Sources",
            details=f"Projection dans l'espace sémantique ({len(sliding_engine.active_clusters)} clusters formés, calcul de vélocité)...",
            progress_pct=70,
            news_count=total_news_found,
            summaries_count=0,
            task_label=mode_label,
            elapsed_seconds=time.time() - start_time
        )
        await sse_broadcaster.broadcast_pipeline_log("📊 Clustering : Projection spatiale et détection des recoupements...")

        new_cluster_count = 0

        for idx, a in enumerate(articles, 1):
            cluster, is_new = sliding_engine.process_article(a)
            if is_new:
                new_cluster_count += 1

            if idx % 100 == 0 or idx == total_news_found:
                await sse_broadcaster.broadcast_pipeline_log(
                    f"📊 Clustering : [{idx}/{total_news_found}] articles traités | {len(sliding_engine.active_clusters)} clusters spatiaux consolidés...",
                    news_count=total_news_found
                )
                await asyncio.sleep(0.01)

        await sse_broadcaster.broadcast_pipeline_log(
            f"📊 Clustering terminé : {len(sliding_engine.active_clusters)} clusters spatiaux consolidés en mémoire.",
            news_count=total_news_found
        )

        # ── Step 4 & 5 : Scoring & Synthèse IA Multi-Sources (Concurrente) ──
        multi_clusters = [
            c for c in sliding_engine.active_clusters.values()
            if (len(c.domains) >= 2 or c.is_critical) and not c.alert_dispatched
        ]

        # 2nd pass: Semantic LLM deduplication on borderline cluster candidates
        if len(multi_clusters) > 1:
            multi_clusters = await semantic_deduplicator.merge_borderline_clusters(multi_clusters, sliding_engine=sliding_engine)

        multi_clusters.sort(key=lambda c: (len(c.domains), len(c.articles)), reverse=True)
        
        # Cap to top 10 most impactful multi-source clusters
        target_clusters = multi_clusters[:10]
        logger.info(f"📊 Active clusters in memory: {len(sliding_engine.active_clusters)} | Multi-source to synthesize: {len(target_clusters)} (from {len(multi_clusters)})")

        active_profile_list = self.profiles if self.profiles else [UserProfile(username="default_user", preferred_language="fr")]
        primary_profile = active_profile_list[0]

        if target_clusters:
            await sse_broadcaster.broadcast_pipeline_log(
                f"🚨 Détection : {len(target_clusters)} sujets majeurs confirmés par au moins 2 sources indépendantes !",
                news_count=total_news_found
            )

            sem = asyncio.Semaphore(3)

            async def _synthesize_cluster_task(cluster_item, c_idx):
                nonlocal summaries_generated
                score, relevance, should_trigger = HybridScorer.evaluate(cluster_item, primary_profile)
                if not (should_trigger or len(cluster_item.domains) >= 2):
                    return None

                async with sem:
                    await sse_broadcaster.broadcast_pipeline_step(
                        step_id="synthesis",
                        step_title="Génération IA Cognitive (LLM)",
                        details=f"Synthèse ({summaries_generated + 1}/{len(target_clusters)}) : '{cluster_item.articles[0].title[:50]}...'",
                        progress_pct=75 + int(20 * (c_idx + 1) / max(1, len(target_clusters))),
                        news_count=total_news_found,
                        summaries_count=summaries_generated,
                        task_label=mode_label,
                        elapsed_seconds=time.time() - start_time
                    )
                    await sse_broadcaster.broadcast_pipeline_log(
                        f"✍️ IA (LLM) : Synthèse multi-sources ({len(cluster_item.domains)} sources) : '{cluster_item.articles[0].title[:45]}...'",
                        news_count=total_news_found,
                        summaries_count=summaries_generated
                    )

                    try:
                        from synthesis.chimera_engine import chimera_engine
                        alert = await chimera_engine.synthesize(cluster_item, primary_profile, score, relevance)
                    except Exception as e:
                        logger.warning(f"Chimera synthesis failed, falling back to AlertSynthesizer: {e}")
                        alert = await alert_synthesizer.synthesize(cluster_item, primary_profile, score, relevance)

                    cluster_item.synthesized_alert = alert
                    cluster_item.alert_dispatched = True
                    self.dispatched_alerts.append(alert)
                    summaries_generated += 1

                    await webhook_dispatcher.dispatch_alert(alert, custom_url=primary_profile.webhook_url)
                    await sse_broadcaster.broadcast_alert(alert)
                    try:
                        from storage_v2.runtime import register_legacy_alert_delivery
                        await asyncio.to_thread(register_legacy_alert_delivery, cluster_item, alert)
                    except Exception as delivery_error:
                        logger.error(f"V2 Delivery registration failed: {type(delivery_error).__name__}: {delivery_error}")

                    extra_info = []
                    if alert.was_clickbait_enhanced:
                        extra_info.append("Titre clarifié")
                    if alert.context_explainer:
                        extra_info.append("Éclairage documenté")
                    if alert.community_sentiment:
                        extra_info.append("Débats résumés")

                    tag_str = f" [{', '.join(extra_info)}]" if extra_info else ""
                    await sse_broadcaster.broadcast_pipeline_log(
                        f"✨ Synthèse diffusée [{len(cluster_item.domains)} sources]{tag_str} : {alert.push_title}",
                        news_count=total_news_found,
                        summaries_count=summaries_generated
                    )
                    return alert

            synth_tasks = [_synthesize_cluster_task(c, idx) for idx, c in enumerate(target_clusters)]
            await asyncio.gather(*synth_tasks, return_exceptions=True)
        else:
            await sse_broadcaster.broadcast_pipeline_log("ℹ️ Aucun cluster n'a encore atteint le seuil de consensus multi-sources (>= 2 sources).")

        # ── Step 5b : Traitement des Signaux Isolés (1 source unique) avec Synthèse Détaillée ──
        single_candidates = [
            c for c in sliding_engine.active_clusters.values()
            if len(c.domains) == 1 and len(c.articles) >= 1 and not c.alert_dispatched
            and len(c.articles[0].title or "") >= 20
        ]
        # Sort by richness of content and freshness
        single_candidates.sort(key=lambda c: (len(c.articles[0].content or ""), c.last_updated_at), reverse=True)
        top_single = single_candidates[:8]
        if top_single:
            await sse_broadcaster.broadcast_pipeline_log(
                f"🟣 Veille ciblée : Synthèse approfondie de {len(top_single)} signaux exclusifs (1 source)...",
                news_count=total_news_found,
                summaries_count=summaries_generated
            )
            sem_single = asyncio.Semaphore(4)

            async def _synth_single_worker(s_cluster):
                async with sem_single:
                    try:
                        single_alert = await alert_synthesizer.synthesize_single(
                            s_cluster.articles[0],
                            primary_profile,
                            cluster_id=s_cluster.id,
                            fast_mode=False
                        )
                        s_cluster.synthesized_alert = single_alert
                        s_cluster.alert_dispatched = True
                        self.dispatched_alerts.append(single_alert)
                        await sse_broadcaster.broadcast_alert(single_alert)
                        try:
                            from storage_v2.runtime import register_legacy_alert_delivery
                            await asyncio.to_thread(register_legacy_alert_delivery, s_cluster, single_alert)
                        except Exception as delivery_error:
                            logger.error(f"V2 Delivery registration failed: {type(delivery_error).__name__}: {delivery_error}")
                    except Exception as e:
                        logger.debug(f"Single signal synthesis error: {e}")

            single_tasks = [_synth_single_worker(sc) for sc in top_single]
            await asyncio.gather(*single_tasks, return_exceptions=True)

        total_elapsed = time.time() - start_time
        await sse_broadcaster.broadcast_pipeline_log(
            f"🎉 Terminé en {total_elapsed:.1f}s ! {total_news_found} news trouvées • {summaries_generated} actualités résumées.",
            news_count=total_news_found,
            summaries_count=summaries_generated
        )

        # ── Step 6 : Completed Telemetry ──
        await sse_broadcaster.broadcast_pipeline_step(
            step_id="completed",
            step_title="Traitement & Diffusion Terminés",
            details=f"✨ {mode_label} terminé avec succès en {total_elapsed:.1f}s ! Nombre de news flux trouvé : {total_news_found} • Nombre d'actu résumé : {summaries_generated}",
            progress_pct=100,
            news_count=total_news_found,
            summaries_count=summaries_generated,
            status="done",
            task_label=mode_label,
            elapsed_seconds=round(total_elapsed, 1)
        )
        persist_daemon_alerts(self.dispatched_alerts)

        # Additive V2 observation only: it is disabled by default and its own
        try:
            from storage_v2.shadow import run_shadow_hook
            shadow_report = await asyncio.to_thread(
                run_shadow_hook,
                articles=articles,
                clusters=tuple(sliding_engine.active_clusters.values()),
                alerts=tuple(self.dispatched_alerts),
                logger=logger,
                force=True,
            )
            if shadow_report is not None:
                for event_id in shadow_report.event_ids:
                    await sse_broadcaster.broadcast_v2_event(
                        "v2_event_updated", event_id, {"event_id": event_id, "source": "v2_shadow"}
                    )
        except Exception as exc:
            logger.error(f"V2 shadow sync failed: {type(exc).__name__}: {exc}")

    def stop(self):
        self.running = False
        logger.info("🛑 Stopping NewsStreamAI Daemon...")

daemon = RealTimeStreamDaemon(profiles=[])
