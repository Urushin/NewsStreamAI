# 🛰️ NewsStreamAI — Moteur d'Agrégation & Alerting Temps Réel par IA

**NewsStreamAI** est une plateforme d'intelligence informationnelle en quasi temps réel (~1 à 3 min de latence) conçue pour surveiller des milliers de flux hétérogènes (RSS, GDELT, Webhooks), regrouper les événements via un clustering sémantique incrémental glissant, détecter l'accélération de couverture multi-sources, et générer des alertes de synthèse ultra-rapides personnalisées selon le profil cognitif de l'utilisateur.

---

## ⚡ Architecture Cible

```text
[Sources: 3600+ Flux RSS / GDELT 2.0 / Webhooks]
                    │
                    ▼ (Ingestion continue asynchrone)
        [1. Parsing & Shield Anti-Biais]
                    │
                    ▼ (Vectorisation & Hashing rapide)
       [2. Sliding Window & Clustering (2-6h)] ─── (Centroïdes dynamiques & Vélocité)
                    │
                    ▼ (Matching Hybride : α * Sim + β * Vélocité)
        [3. Profil Cognitif Utilisateur]
                    │
                    ▼ (Détection de Criticité : ≥ 3 sources / < 20 min)
         [4. Synthèse LLM Multi-Docs]
                    │
                    ▼ (Webhooks / Discord / Slack / SSE)
       [5. Notification Push Immédiate]
```

---

## 🚀 Démarrage Rapide

### 1. Lancer la Simulation Complète (End-to-End)
Pour tester immédiatement l'ensemble du pipeline en accéléré (ingestion multi-sources, regroupement en cluster, montée en vélocité, synthèse LLM et notification push) :

```bash
python3 simulator/run_simulation.py
```

### 2. Démarrer le Serveur API & Streaming SSE
```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

* **Swagger / OpenAPI** : `http://localhost:8000/docs`
* **Flux Live SSE** : `GET http://localhost:8000/api/stream/live`
* **Inspection des Clusters Actifs** : `GET http://localhost:8000/api/clusters/active`
* **Health Check** : `GET http://localhost:8000/api/health`

---

## 📂 Structure du Projet

```text
NewsStreamAI/
├── config/
│   ├── settings.py              # Configuration centrale (seuils, fenêtres, clés)
│   ├── curated_sources.json     # Catalogue de 3600+ sources RSS tierées
│   └── taxonomy.json            # Arborescence hiérarchique thématique
├── core/
│   ├── models.py                # Schémas Pydantic (Article, Cluster, UserProfile, AlertPayload)
│   └── logger.py                # Journalisation structurée
├── ingestion/
│   ├── rss_poller.py            # Poller asynchrone RSS (httpx + bs4, rotation User-Agents)
│   ├── gdelt_stream.py          # Connecteur temps réel GDELT 2.0 API mondial
│   └── source_catalog.py        # Gestionnaire de sources tierées et filtrage
├── vector/
│   ├── embedder.py              # Embeddings asynchrones multi-fournisseurs (Gemini, OpenAI, Mistral, Local)
│   └── memory_index.py          # Calcul de similarité cosinus & centroïdes en temps réel
├── clustering/
│   ├── sliding_window.py        # Fenêtre glissante (2-6h) avec TTL et centroïdes dynamiques
│   └── velocity_tracker.py      # Calcul de vélocité et détection du seuil critique multi-sources
├── reliability/
│   ├── reputation_db.py         # Base de réputation de domaines (Tiers 1/2/3)
│   └── bias_shield.py           # Détection de biais cognitifs & putaclic
├── matching/
│   ├── profile_engine.py        # Moteur de profil cognitif & vectorisation des intérêts
│   └── hybrid_scorer.py         # Score hybride (Relevance + Velocity - Penalties)
├── synthesis/
│   ├── llm_gateway.py           # Passerelle LLM multi-fournisseurs avec fallback automatique
│   └── alert_synthesizer.py     # Synthèse multi-documents (Titre 15 mots + 3-4 bullets + sources)
├── dispatch/
│   ├── webhook_dispatcher.py    # Envoi de webhooks (Discord, Slack, Custom HTTP)
│   └── sse_broadcaster.py       # Diffusion temps réel Server-Sent Events (SSE)
├── learning/
│   └── feedback_loop.py         # Boucle d'apprentissage adaptative sur actions 'read' / 'rejected'
├── api/
│   └── server.py                # Serveur FastAPI pour l'UI, le streaming et les profils
├── worker/
│   └── stream_daemon.py         # Démon d'exécution continue en arrière-plan
└── simulator/
    └── run_simulation.py        # Script de simulation et démonstration complète
```
