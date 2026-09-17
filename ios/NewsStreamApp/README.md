# 📱 NewsStreamAI — Application Mobile iOS Native (SwiftUI)

Application mobile iOS native développée en **SwiftUI (iOS 17+)** pour le kiosque d'actualités haute précision **NewsStreamAI / Mizan**.

---

## 🌟 Fonctionnalités Clés

1. **🏛️ Design Slow-News Paper / Zinc** :
   * Fond ivoire `#FDFCF8` / Thème sombre feutré `#09090B`.
   * Typographie éditoriale Serif (`New York`) et Sans-serif (`SF Pro`).
   * Badges de consensus dynamiques (🚨 4+ sources, 🔥 3 sources, ⚡ 2 sources, 🟣 1 source).

2. **⚡ Streaming Server-Sent Events (SSE) en Direct** :
   * Connexion `AsyncStream` sur `/api/stream/live` avec reconnexion automatique exponentielle.
   * Réception en temps réel des alertes de consensus et des étapes de télémétrie IA.

3. **🛡️ Isolation Stricte Multi-Sources vs Signaux Isolés (1 Source)** :
   * **Onglet "Fil Confirmé"** : Affiche uniquement les événements recoupés (≥ 2 sources indépendantes), avec badges anti-clickbait, éclairage éditorial et sentiment communautaire.
   * **Onglet "Signaux Isolés"** : Bulle dédiée aux dépêches à source unique, strictement exclusives et traduites dans la langue de l'appareil.

4. **🌍 Unification Linguistique Universelle** :
   * Détection automatique de la langue locale de l'appareil (`Locale.current`).
   * Toutes les alertes et dépêches étrangères sont traduites et synthétisées.

5. **🩺 Télémétrie & Santé des 720 Flux** :
   * Tableau de bord en temps réel des latences (ms), statuts opérationnels et auto-quarantaine des flux RSS.

6. **📲 Intégration Native iOS** :
   * Vibrations haptiques physiques (`UIImpactFeedbackGenerator`).
   * Gestuelle Pull-to-Refresh native.
   * Liens directs vers les sources médias d'origine.

---

## 🚀 Comment Lancer l'Application sur Xcode / Simulateur

### 1. Démarrer le Backend NewsStreamAI
Dans un terminal :
```bash
cd "/Users/issam/Documents/Projets perso/NewsStreamAI"
./start_newsstream.sh
```
*(Le backend tourne sur `http://localhost:8000`).*

### 2. Ouvrir le Projet dans Xcode
Dans un second terminal :
```bash
open -a Xcode "/Users/issam/Documents/Projets perso/NewsStreamAI/ios/NewsStreamApp"
```
Ou double-cliquez sur `Package.swift`.

### 3. Exécuter
* Choisissez un simulateur (ex: **iPhone 16 Pro** ou **iPhone 15**).
* Appuyez sur **`⌘ + R`** (Run).

---

## 📁 Structure du Code

```text
ios/NewsStreamApp/
├── Package.swift               # Définition SPM & Dépendances
├── Sources/NewsStreamApp/
│   ├── NewsStreamApp.swift     # Point d'entrée SwiftUI
│   ├── Theme/                  # Couleurs Paper (#FDFCF8), Typographie & Haptics
│   ├── Models/                 # AlertPayload, SourceHealth, PipelineStep, UserProfile
│   ├── Services/               # APIClient (REST) & SSEStreamManager (Temps Réel)
│   ├── ViewModels/             # NewsStreamViewModel (@MainActor ObservableObject)
│   └── Views/
│       ├── RootTabView.swift   # Navigation principale (TabBar 4 onglets)
│       ├── Feed/               # Fil Confirmé & Bulle Signaux Isolés
│       ├── Components/         # AlertCardView & ConsensusBadgeView
│       ├── Health/             # Moniteur de santé des 720 sources
│       ├── Telemetry/          # Sheet de suivi live du pipeline IA
│       └── Settings/           # Configuration IP Serveur & Langue de Restitution
└── Tests/                      # Tests unitaires & Décodage JSON
```
