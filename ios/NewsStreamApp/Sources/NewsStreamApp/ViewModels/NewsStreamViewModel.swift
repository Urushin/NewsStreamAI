import SwiftUI
import Combine

public enum AppEngineMode: String, CaseIterable, Identifiable, Sendable {
    case autonomous = "100% Autonome (iPhone)"
    case server = "Serveur Local (PC)"
    
    public var id: String { rawValue }
}

@MainActor
public final class NewsStreamViewModel: ObservableObject {
    // MARK: - Published State
    @Published public var allAlerts: [AlertPayload] = []
    @Published public var multiSourceAlerts: [AlertPayload] = []
    @Published public var singleSourceAlerts: [AlertPayload] = []
    
    // Engine Mode & AI Provider
    @Published public var engineMode: AppEngineMode = .server
    @Published public var selectedLLMProvider: LLMProvider = .groq
    
    // Tracked Content Entities
    @Published public var trackedApps: [String] = []
    @Published public var trackedYouTubeChannels: [[String: String]] = []
    @Published public var trackedRepos: [String] = []
    @Published public var trackedTwitterAccounts: [String] = []
    @Published public var entityWatchlist: [String] = []
    
    // Telemetry & Pipeline
    @Published public var currentPipelineStep: PipelineStepEvent?
    @Published public var pipelineLogs: [String] = []
    @Published public var isConnectedToSSE: Bool = false
    @Published public var connectionStatusMessage: String = "Connexion au flux direct..."
    
    // Source Health
    @Published public var sourceHealthReport: SourceHealthReport?
    @Published public var isHealthLoading: Bool = false
    
    // Actions State
    @Published public var isSimulating: Bool = false
    @Published public var isCatchingUp: Bool = false
    @Published public var isScanning: Bool = false
    @Published public var toastMessage: String?
    @AppStorage("newsstream_content_window_hours") public var contentWindowHours: Int = 24
    
    // Telegram Configuration
    @Published public var telegramConfig: APIClient.TelegramConfig? = nil
    @Published public var isTelegramLoading: Bool = false
    
    // User Profile
    @Published public var userProfile: UserProfile = UserProfile()
    
    // Bookmarks (Signets)
    @Published public var bookmarkedAlerts: [AlertPayload] = []
    
    // Read state persistence
    @Published public var readAlertIds: Set<String> = []
    
    // Card Deck State (1 news = 1 écran)
    @Published public var currentCardIndex: Int = 0
    @Published public var singleCardIndex: Int = 0
    @Published public var hasNewRealtimeAlertPulse: Bool = false
    
    // 🎬 Content Hub (YouTube & Releases)
    @Published public var contentVideos: [YouTubeVideoItem] = []
    @Published public var contentReleases: [ReleaseUpdateItem] = []
    @Published public var isContentLoading: Bool = false
    @Published public var contentError: String?
    
    // 🌍 Globe 3D Events
    @Published public var globeEvents: [GlobeEventItem] = []
    @Published public var globeArcs: [GlobeArcItem] = []
    @Published public var countryDensity: [String: Int] = [:]
    @Published public var isGlobeLoading: Bool = false
    
    public var currentCard: AlertPayload? {
        guard !multiSourceAlerts.isEmpty, currentCardIndex < multiSourceAlerts.count else { return nil }
        return multiSourceAlerts[currentCardIndex]
    }
    
    public var nextCard: AlertPayload? {
        guard currentCardIndex + 1 < multiSourceAlerts.count else { return nil }
        return multiSourceAlerts[currentCardIndex + 1]
    }
    
    public var currentSingleCard: AlertPayload? {
        guard !singleSourceAlerts.isEmpty, singleCardIndex < singleSourceAlerts.count else { return nil }
        return singleSourceAlerts[singleCardIndex]
    }
    
    public var nextSingleCard: AlertPayload? {
        guard singleCardIndex + 1 < singleSourceAlerts.count else { return nil }
        return singleSourceAlerts[singleCardIndex + 1]
    }
    
    @Published public var blockedSources: Set<String> = []
    
    private var streamTask: Task<Void, Never>?
    private let bookmarksKey = "mynews_saved_bookmarks_v1"
    private let profileCacheKey = "mynews_cached_user_profile_v1"
    private let blockedSourcesKey = "mynews_blocked_sources_v1"
    private let readAlertsKey = "mynews_read_alert_ids_v1"
    
    public init() {
        NotificationManager.shared.requestAuthorization()
        loadLocalCache()
        Task {
            await initialize()
        }
    }
    
    private func loadLocalCache() {
        // Load Blocked Sources
        if let bSources = UserDefaults.standard.stringArray(forKey: blockedSourcesKey) {
            self.blockedSources = Set(bSources)
        }
        // Load Read Alerts
        if let rAlerts = UserDefaults.standard.stringArray(forKey: readAlertsKey) {
            self.readAlertIds = Set(rAlerts)
        }
        // Load Bookmarks
        let storedBookmarks = LocalNewsStore.shared.loadBookmarks()
        if !storedBookmarks.isEmpty {
            self.bookmarkedAlerts = storedBookmarks
        } else {
            let bData = UserDefaults.standard.data(forKey: bookmarksKey) ?? UserDefaults.standard.data(forKey: "mizan_saved_bookmarks_v1")
            if let data = bData,
               let saved = try? JSONDecoder().decode([AlertPayload].self, from: data) {
                self.bookmarkedAlerts = saved
                LocalNewsStore.shared.saveBookmarks(saved)
            }
        }
        // Load Cached Profile
        let pData = UserDefaults.standard.data(forKey: profileCacheKey) ?? UserDefaults.standard.data(forKey: "mizan_cached_user_profile_v1")
        if let data = pData,
           let cached = try? JSONDecoder().decode(UserProfile.self, from: data) {
            self.userProfile = cached
        }
        // Load Engine Mode
        if let modeStr = UserDefaults.standard.string(forKey: "newsstream_engine_mode"),
           let mode = AppEngineMode(rawValue: modeStr) {
            self.engineMode = mode
        }
        // Load LLM Provider
        if let provStr = UserDefaults.standard.string(forKey: "newsstream_selected_llm"),
           let prov = LLMProvider(rawValue: provStr) {
            self.selectedLLMProvider = prov
        }
        // Load Local News Cache (Instant Offline Startup)
        let cachedAlerts = LocalNewsStore.shared.loadAlerts()
        if !cachedAlerts.isEmpty {
            self.allAlerts = cachedAlerts
            self.recomputeStreams()
        }
        // Load Cached Watchlist
        if let cachedList = UserDefaults.standard.stringArray(forKey: "newsstream_entity_watchlist_cache") {
            self.entityWatchlist = cachedList
        }
        // Load Local Telegram Config
        if let localToken = UserDefaults.standard.string(forKey: "newsstream_telegram_token"), !localToken.isEmpty,
           let localChat = UserDefaults.standard.string(forKey: "newsstream_telegram_chat_id"), !localChat.isEmpty {
            let enabled = UserDefaults.standard.bool(forKey: "newsstream_telegram_enabled")
            self.telegramConfig = APIClient.TelegramConfig(
                configured: true,
                bot_token: localToken.count > 10 ? "\(localToken.prefix(6))...\(localToken.suffix(4))" : localToken,
                raw_token: localToken,
                chat_id: localChat,
                enabled: enabled
            )
        }
    }
    
    private func saveReadAlertIds() {
        UserDefaults.standard.set(Array(readAlertIds), forKey: readAlertsKey)
    }
    
    public func isSourceBlocked(name: String) -> Bool {
        blockedSources.contains(name.lowercased().trimmingCharacters(in: .whitespaces))
    }
    
    public func toggleBlockSource(name: String) {
        let key = name.lowercased().trimmingCharacters(in: .whitespaces)
        if blockedSources.contains(key) {
            blockedSources.remove(key)
            showToast("✅ Source réactivée : \(name)")
        } else {
            blockedSources.insert(key)
            showToast("🚫 Source bloquée : \(name)")
        }
        UserDefaults.standard.set(Array(blockedSources), forKey: blockedSourcesKey)
        HapticsManager.shared.impact(.medium)
        recomputeStreams()
    }
    
    public func toggleBookmark(alert: AlertPayload) {
        HapticsManager.shared.impact(.light)
        if let idx = bookmarkedAlerts.firstIndex(where: { $0.alert_id == alert.alert_id || $0.cluster_id == alert.cluster_id }) {
            bookmarkedAlerts.remove(at: idx)
            showToast("🔖 Retiré des signets")
        } else {
            bookmarkedAlerts.insert(alert, at: 0)
            showToast("🔖 Ajouté aux signets")
        }
        saveBookmarks()
    }
    
    public func isBookmarked(alert: AlertPayload) -> Bool {
        bookmarkedAlerts.contains(where: { $0.alert_id == alert.alert_id || $0.cluster_id == alert.cluster_id })
    }
    
    private func saveBookmarks() {
        LocalNewsStore.shared.saveBookmarks(bookmarkedAlerts)
        if let data = try? JSONEncoder().encode(bookmarkedAlerts) {
            UserDefaults.standard.set(data, forKey: bookmarksKey)
        }
    }
    
    public func initialize() async {
        startLiveSSEStream()
        async let profileTask: () = loadUserProfile()
        async let alertsTask: () = loadAlertsHistory()
        async let healthTask: () = loadSourceHealth()
        async let watchlistTask: () = loadEntityWatchlist()
        async let telegramTask: () = loadTelegramSettings()
        _ = await (profileTask, alertsTask, healthTask, watchlistTask, telegramTask)
    }
    
    // MARK: - Alerts Management & Filtering
    public func loadAlertsHistory() async {
        do {
            async let multiTask = APIClient.shared.fetchMultiAlerts()
            async let singleTask = APIClient.shared.fetchSingleAlerts()
            let (multi, single) = try await (multiTask, singleTask)
            self.allAlerts = multi + single
            LocalNewsStore.shared.saveAlerts(self.allAlerts)
            self.recomputeStreams()
            if self.currentCardIndex >= self.multiSourceAlerts.count && !self.multiSourceAlerts.isEmpty {
                self.currentCardIndex = min(self.currentCardIndex, self.multiSourceAlerts.count - 1)
            }
        } catch {
            print("Failed to fetch alerts history: \(error)")
        }
    }
    
    public func refreshFeed() async {
        HapticsManager.shared.impact(.medium)
        showToast("🔄 Actualisation des alertes...")
        await loadAlertsHistory()
        showToast("✅ Flux synchronisé (\(multiSourceAlerts.count) actualités)")
    }
    
    public func likeCurrentCard() async {
        guard let card = currentCard else { return }
        readAlertIds.insert(card.alert_id)
        saveReadAlertIds()
        HapticsManager.shared.impact(.medium)
        showToast("👍 Intérêt enregistré pour \(card.category)")
        withAnimation(.spring()) {
            currentCardIndex += 1
        }
        do {
            try await APIClient.shared.submitFeedback(
                clusterId: card.cluster_id,
                title: card.push_title,
                feedbackType: "interested"
            )
            await loadUserProfile()
        } catch {
            print("Like feedback error: \(error)")
        }
    }
    
    public func dislikeCurrentCard() async {
        guard let card = currentCard else { return }
        readAlertIds.insert(card.alert_id)
        saveReadAlertIds()
        HapticsManager.shared.impact(.light)
        showToast("👎 Sujet atténué")
        withAnimation(.spring()) {
            currentCardIndex += 1
        }
        do {
            try await APIClient.shared.submitFeedback(
                clusterId: card.cluster_id,
                title: card.push_title,
                feedbackType: "rejected"
            )
            await loadUserProfile()
        } catch {
            print("Dislike feedback error: \(error)")
        }
    }
    
    public func skipCurrentCard() {
        if let card = currentCard {
            readAlertIds.insert(card.alert_id)
            saveReadAlertIds()
        }
        HapticsManager.shared.impact(.light)
        withAnimation(.spring()) {
            currentCardIndex += 1
        }
    }
    
    public func rewindCard() {
        if currentCardIndex > 0 {
            HapticsManager.shared.impact(.light)
            withAnimation(.spring()) {
                currentCardIndex -= 1
            }
        }
    }
    
    public func resetDeck() {
        readAlertIds.removeAll()
        saveReadAlertIds()
        withAnimation {
            currentCardIndex = 0
        }
    }
    
    // MARK: - 🎬 Content Hub (YouTube & Releases)
    public func loadContentFeed() async {
        guard !isContentLoading else { return }
        isContentLoading = true
        contentError = nil
        defer { isContentLoading = false }
        do {
            let res = try await APIClient.shared.fetchContentFeed()
            self.contentVideos = res.videos
            self.contentReleases = res.releases
            
            if let wl = try? await APIClient.shared.fetchWatchlist() {
                self.trackedApps = wl.tracked_apps ?? []
                self.trackedRepos = wl.github_repos
                self.trackedYouTubeChannels = wl.youtube_channels
                self.trackedTwitterAccounts = wl.twitter_accounts ?? []
            }
        } catch {
            contentError = "Vos contenus n’ont pas pu être actualisés. Vérifiez votre connexion et réessayez."
        }
    }
    
    public func searchYouTubeChannels(query: String) async -> [YouTubeSearchResult] {
        let clean = query.trimmingCharacters(in: .whitespaces)
        guard !clean.isEmpty else { return [] }
        do {
            let res = try await APIClient.shared.searchYouTube(query: clean)
            if !res.isEmpty { return res }
        } catch {}
        
        return [
            YouTubeSearchResult(
                id: clean,
                title: clean,
                handle: clean.hasPrefix("@") ? clean : "@\(clean)",
                thumbnail: "https://www.google.com/s2/favicons?domain=youtube.com&sz=128"
            )
        ]
    }
    
    public func searchGitHubRepos(query: String) async -> [GitHubSearchResult] {
        let clean = query.trimmingCharacters(in: .whitespaces)
        guard !clean.isEmpty else { return [] }
        do {
            let res = try await APIClient.shared.searchGitHub(query: clean)
            if !res.isEmpty { return res }
        } catch {}
        
        guard let enc = clean.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let url = URL(string: "https://api.github.com/search/repositories?q=\(enc)&per_page=8&sort=stars") else { return [] }
        var req = URLRequest(url: url)
        req.setValue("MyNewsAI/2.0", forHTTPHeaderField: "User-Agent")
        if let (data, _) = try? await URLSession.shared.data(for: req),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let items = json["items"] as? [[String: Any]] {
            return items.compactMap { item in
                guard let fn = item["full_name"] as? String else { return nil }
                let name = item["name"] as? String ?? fn
                let desc = item["description"] as? String
                let stars = item["stargazers_count"] as? Int
                let owner = item["owner"] as? [String: Any]
                let avatar = owner?["avatar_url"] as? String
                return GitHubSearchResult(
                    full_name: fn,
                    name: name,
                    owner: owner?["login"] as? String,
                    avatar_url: avatar,
                    description: desc,
                    stars: stars
                )
            }
        }
        return []
    }
    
    public func addTrackedEntity(type: String, target: String) async -> Bool {
        do {
            try await APIClient.shared.trackEntity(type: type, target: target)
            await loadContentFeed()
            showToast("✅ Ajouté au suivi : \(target)")
            return true
        } catch {
            showToast("❌ Échec de l'ajout au suivi")
            return false
        }
    }
    
    public func removeTrackedEntity(type: String, target: String) async -> Bool {
        do {
            try await APIClient.shared.untrackEntity(type: type, targetId: target)
            await loadContentFeed()
            showToast("🗑️ Retiré du suivi : \(target)")
            return true
        } catch {
            showToast("❌ Échec de la suppression")
            return false
        }
    }
    
    // MARK: - 🌍 Globe 3D Events
    public func loadGlobeEvents(timeframe: String? = nil, severity: String? = nil, category: String? = nil) async {
        isGlobeLoading = true
        defer { isGlobeLoading = false }
        do {
            let res = try await APIClient.shared.fetchGlobeEvents(timeframe: timeframe, severity: severity, category: category)
            self.globeEvents = res.events
            self.countryDensity = res.country_density
            self.globeArcs = res.arcs ?? []
        } catch {
            print("Failed to fetch globe events: \(error)")
        }
    }
    
    // MARK: - 🧹 Purge Administration
    public func purgeAllAlerts() async {
        do {
            try await APIClient.shared.purgeAlerts()
            self.allAlerts.removeAll()
            self.multiSourceAlerts.removeAll()
            self.singleSourceAlerts.removeAll()
            self.currentCardIndex = 0
            self.singleCardIndex = 0
            self.readAlertIds.removeAll()
            saveReadAlertIds()
            HapticsManager.shared.notification(.warning)
            showToast("🧹 Toutes les news ont été purgées")
        } catch {
            showToast("❌ Erreur lors de la purge")
        }
    }
    
    // MARK: - Single-Source Deck Actions (One-by-One with Like / Dislike)
    public func likeCurrentSingleCard() async {
        guard let card = currentSingleCard else { return }
        HapticsManager.shared.impact(.medium)
        showToast("👍 Intérêt enregistré pour \(card.category)")
        withAnimation(.easeInOut(duration: 0.14)) {
            singleCardIndex += 1
        }
        do {
            try await APIClient.shared.submitFeedback(
                clusterId: card.cluster_id,
                title: card.push_title,
                feedbackType: "interested"
            )
            await loadUserProfile()
        } catch {
            print("Like single feedback error: \(error)")
        }
    }
    
    public func dislikeCurrentSingleCard() async {
        guard let card = currentSingleCard else { return }
        HapticsManager.shared.impact(.light)
        showToast("👎 Signal isolé atténué")
        withAnimation(.easeInOut(duration: 0.14)) {
            singleCardIndex += 1
        }
        do {
            try await APIClient.shared.submitFeedback(
                clusterId: card.cluster_id,
                title: card.push_title,
                feedbackType: "rejected"
            )
            await loadUserProfile()
        } catch {
            print("Dislike single feedback error: \(error)")
        }
    }
    
    public func skipCurrentSingleCard() {
        HapticsManager.shared.impact(.light)
        withAnimation(.easeInOut(duration: 0.14)) {
            singleCardIndex += 1
        }
    }
    
    public func rewindSingleCard() {
        if singleCardIndex > 0 {
            HapticsManager.shared.impact(.light)
            withAnimation(.easeInOut(duration: 0.14)) {
                singleCardIndex -= 1
            }
        }
    }
    
    public func resetSingleDeck() {
        withAnimation {
            singleCardIndex = 0
        }
    }
    
    public func handleIncomingAlert(_ alert: AlertPayload) {
        // Ignore if all sources are blocked
        if !alert.sources.isEmpty && alert.sources.allSatisfy({ isSourceBlocked(name: $0.name) }) {
            return
        }
        
        // Prevent duplicate insertion in allAlerts
        if let existingIdx = allAlerts.firstIndex(where: { $0.alert_id == alert.alert_id || $0.cluster_id == alert.cluster_id }) {
            allAlerts[existingIdx] = alert
        } else {
            allAlerts.insert(alert, at: 0)
        }
        LocalNewsStore.shared.saveAlerts(allAlerts)
        
        hasNewRealtimeAlertPulse = true
        showToast("⚡ Nouvelle news : \(alert.push_title.prefix(35))...")
        
        let isAlreadyTracked = multiSourceAlerts.contains(where: { $0.cluster_id == alert.cluster_id || $0.alert_id == alert.alert_id })
        if let idx = multiSourceAlerts.firstIndex(where: { $0.cluster_id == alert.cluster_id || $0.alert_id == alert.alert_id }) {
            multiSourceAlerts.remove(at: idx)
        }
        multiSourceAlerts.insert(alert, at: 0)
        if currentCardIndex > 0 && !isAlreadyTracked {
            currentCardIndex += 1
        }
        HapticsManager.shared.notification(.success)
        
        if alert.isMultiSource {
            // Remove from single-source list if previously captured as isolated signal
            singleSourceAlerts.removeAll(where: { $0.cluster_id == alert.cluster_id || $0.alert_id == alert.alert_id })
        } else {
            if !singleSourceAlerts.contains(where: { $0.cluster_id == alert.cluster_id || $0.push_title == alert.push_title }) {
                singleSourceAlerts.insert(alert, at: 0)
                if singleCardIndex > 0 {
                    singleCardIndex += 1
                }
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 4.0) {
            self.hasNewRealtimeAlertPulse = false
        }
    }
    
    public func recomputeStreams() {
        // Time window filter
        let windowAlerts: [AlertPayload]
        if contentWindowHours > 0 {
            let cutoff = Date().addingTimeInterval(-Double(contentWindowHours) * 3600)
            windowAlerts = allAlerts.filter { alert in
                let d = alert.parsedDate
                return d == Date.distantPast || d >= cutoff
            }
        } else {
            windowAlerts = allAlerts
        }
        
        // Filter out blocked sources
        let filteredAlerts = windowAlerts.filter { alert in
            if alert.sources.isEmpty { return true }
            return !alert.sources.allSatisfy { isSourceBlocked(name: $0.name) }
        }
        
        // 1. Multi-source alerts (>= 2 sources)
        let multi = filteredAlerts.filter { $0.sources.count >= 2 }
            .sorted { $0.parsedDate > $1.parsedDate }
        
        let multiClusterIds = Set(multi.map { $0.cluster_id })
        let multiUrls = Set(multi.flatMap { $0.sources.map { $0.url.lowercased().trimmingCharacters(in: .whitespaces) } })
        let multiTitles = multi.map { $0.push_title.lowercased().trimmingCharacters(in: .whitespaces) }
        
        // 2. Single-source isolated signals (strictly 1 source & strictly NOT in multi-source)
        let single = filteredAlerts.filter { alert in
            guard alert.sources.count <= 1 else { return false }
            guard !multiClusterIds.contains(alert.cluster_id) else { return false }
            
            if let firstSrc = alert.sources.first {
                let u = firstSrc.url.lowercased().trimmingCharacters(in: .whitespaces)
                if !u.isEmpty && multiUrls.contains(u) {
                    return false
                }
            }
            
            let sTitle = alert.push_title.lowercased().trimmingCharacters(in: .whitespaces)
            if !sTitle.isEmpty && multiTitles.contains(where: { $0.count > 10 && ($0.contains(sTitle) || sTitle.contains($0)) }) {
                return false
            }
            
            return true
        }.sorted { $0.parsedDate > $1.parsedDate }
        
        // Unified chronological news stream: multi-source + unique single-source articles
        var unified = multi
        unified.append(contentsOf: single)
        unified.sort { $0.parsedDate > $1.parsedDate }
        
        self.multiSourceAlerts = unified
        self.singleSourceAlerts = single
    }
    
    // MARK: - Live SSE Streaming
    public func startLiveSSEStream() {
        streamTask?.cancel()
        streamTask = Task {
            let stream = SSEStreamManager.shared.startStream()
            for await event in stream {
                if Task.isCancelled { break }
                switch event {
                case .connected:
                    self.isConnectedToSSE = true
                    self.connectionStatusMessage = "Flux direct connecté"
                case .disconnected(let msg):
                    self.isConnectedToSSE = false
                    self.connectionStatusMessage = msg
                case .alert(let alert):
                    self.handleIncomingAlert(alert)
                case .pipelineStep(let step):
                    self.currentPipelineStep = step
                    let isDone = step.step_id == "DONE" || step.step_id == "completed" || step.status == "done" || step.status == "error" || step.progress_pct >= 100
                    if isDone {
                        Task {
                            await self.loadAlertsHistory()
                            try? await Task.sleep(nanoseconds: 1_000_000_000)
                            self.isScanning = false
                            self.isCatchingUp = false
                            self.isSimulating = false
                        }
                    } else {
                        self.isScanning = true
                    }
                case .pipelineLog(let log):
                    self.pipelineLogs.insert(log, at: 0)
                    if self.pipelineLogs.count > 100 {
                        self.pipelineLogs.removeLast()
                    }
                }
            }
        }
    }
    
    // MARK: - Actions
    public func triggerSimulation() async {
        isSimulating = true
        isScanning = true
        showToast("⚡ Simulation de flux d'événements...")
        HapticsManager.shared.impact(.heavy)
        
        if engineMode == .autonomous {
            let startTime = CFAbsoluteTimeGetCurrent()
            let testSimArticles: [RawArticle] = SimulationScenarios.shared.getRotatingBatch()
            
            let totalCount = testSimArticles.count
            pipelineLogs.insert("⚡ Ingestion : Détection de \(totalCount) dépêches simulées...", at: 0)
            
            // Step 1: Ingestion
            currentPipelineStep = PipelineStepEvent(
                step_id: "ingestion",
                step_title: "Collecte & Ingestion Locale",
                details: "Réception de \(totalCount) dépêches fraîches simulées...",
                progress_pct: 25,
                news_count: totalCount,
                summaries_count: 0,
                status: "running",
                task_label: "Simulation Événements",
                elapsed_seconds: CFAbsoluteTimeGetCurrent() - startTime
            )
            try? await Task.sleep(nanoseconds: 500_000_000)
            
            // Step 2: Vectorization
            pipelineLogs.insert("🧬 Vectorisation : Calcul des empreintes sémantiques locales...", at: 0)
            currentPipelineStep = PipelineStepEvent(
                step_id: "vectorization",
                step_title: "Vectorisation Sémantique",
                details: "Analyse lexicale et normalisation de \(totalCount) dépêches...",
                progress_pct: 50,
                news_count: totalCount,
                summaries_count: 0,
                status: "running",
                task_label: "Simulation Événements",
                elapsed_seconds: CFAbsoluteTimeGetCurrent() - startTime
            )
            try? await Task.sleep(nanoseconds: 400_000_000)
            
            // Step 3: Clustering
            pipelineLogs.insert("📊 Clustering : Détection des recoupements thématiques...", at: 0)
            currentPipelineStep = PipelineStepEvent(
                step_id: "clustering",
                step_title: "Clustering & Recoupement",
                details: "Projection des articles et regroupement par similarité Jaccard...",
                progress_pct: 70,
                news_count: totalCount,
                summaries_count: 0,
                status: "running",
                task_label: "Simulation Événements",
                elapsed_seconds: CFAbsoluteTimeGetCurrent() - startTime
            )
            let clusters = LocalClusterEngine.shared.cluster(articles: testSimArticles)
            let multiCount = clusters.filter { $0.isMultiSource }.count
            pipelineLogs.insert("📊 \(clusters.count) clusters identifiés (\(multiCount) multi-sources).", at: 0)
            try? await Task.sleep(nanoseconds: 400_000_000)
            
            // Step 4: Synthesis
            var summariesGenerated = 0
            var newAlerts: [AlertPayload] = []
            for (idx, cl) in clusters.enumerated() {
                let pct = 75 + Int(Double(idx + 1) / Double(clusters.count) * 20)
                pipelineLogs.insert("✍️ Synthèse IA (\(selectedLLMProvider.rawValue)) : '\(cl.mainTitle.prefix(40))...'", at: 0)
                currentPipelineStep = PipelineStepEvent(
                    step_id: "synthesis",
                    step_title: "Génération IA Cognitive",
                    details: "Synthèse : '\(cl.mainTitle.prefix(45))...'",
                    progress_pct: pct,
                    news_count: totalCount,
                    summaries_count: summariesGenerated,
                    status: "running",
                    task_label: "Simulation Événements",
                    elapsed_seconds: CFAbsoluteTimeGetCurrent() - startTime
                )
                let alert = await DirectLLMClient.shared.synthesizeCluster(
                    cluster: cl,
                    language: userProfile.preferred_language,
                    provider: selectedLLMProvider
                )
                newAlerts.append(alert)
                summariesGenerated += 1
                pipelineLogs.insert("✨ Alerte générée : \(alert.push_title.prefix(45))...", at: 0)
                try? await Task.sleep(nanoseconds: 300_000_000)
            }
            
            // Insert and persist
            for a in newAlerts {
                if !allAlerts.contains(where: { $0.id == a.id }) {
                    allAlerts.insert(a, at: 0)
                }
            }
            LocalNewsStore.shared.saveAlerts(allAlerts)
            recomputeStreams()
            
            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            pipelineLogs.insert("🎉 Simulation locale terminée en \(String(format: "%.1f", elapsed))s ! \(totalCount) news • \(summariesGenerated) résumés.", at: 0)
            currentPipelineStep = PipelineStepEvent(
                step_id: "completed",
                step_title: "Diffusion Terminée",
                details: "✨ Simulation réussie ! \(totalCount) dépêches analysées, \(summariesGenerated) actualités résumées.",
                progress_pct: 100,
                news_count: totalCount,
                summaries_count: summariesGenerated,
                status: "done",
                task_label: "Simulation Événements",
                elapsed_seconds: elapsed
            )
            showToast("✅ Simulation locale : \(summariesGenerated) actualités créées !")
            isScanning = false
            isSimulating = false
        } else {
            pipelineLogs.insert("🖥️ Envoi commande simulation au serveur...", at: 0)
            do {
                try await APIClient.shared.triggerSimulation()
                pipelineLogs.insert("✅ Simulation déclenchée sur serveur — suivi en direct via SSE.", at: 0)
            } catch {
                showToast("❌ Erreur serveur PC : vérifiez la connexion ou basculez en mode autonome.")
                pipelineLogs.insert("❌ Échec appel serveur : \(error.localizedDescription)", at: 0)
                isScanning = false
            }
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            isSimulating = false
        }
    }
    
    public func trigger24hCatchUp() async {
        isCatchingUp = true
        isScanning = true
        HapticsManager.shared.impact(.heavy)
        
        if engineMode == .autonomous {
            showToast("🌌 Scan autonome de \(CuratedSources.feeds.count) flux en cours...")
            pipelineLogs.insert("🚀 Lancement du rattrapage 24h autonome (\(CuratedSources.feeds.count) flux)", at: 0)
            
            let articles = await AutonomousFeedEngine.shared.fetch24hCatchUp { done, total, msg in
                Task { @MainActor in
                    self.currentPipelineStep = PipelineStepEvent(
                        step_id: "ingestion",
                        step_title: "Collecte Autonome RSS",
                        details: msg,
                        progress_pct: Int(Double(done) / Double(max(1, total)) * 70),
                        news_count: done,
                        summaries_count: 0,
                        task_label: "Rattrapage 24h Autonome"
                    )
                    if done % 4 == 0 || done == total {
                        self.pipelineLogs.insert("📡 [\(done)/\(total)] \(msg)", at: 0)
                        if self.pipelineLogs.count > 100 { self.pipelineLogs.removeLast() }
                    }
                }
            }
            
            pipelineLogs.insert("📊 Ingestion terminée : \(articles.count) articles captés en 24h", at: 0)
            
            self.currentPipelineStep = PipelineStepEvent(
                step_id: "clustering",
                step_title: "Clustering Sémantique On-Device",
                details: "Regroupement lexical de \(articles.count) dépêches...",
                progress_pct: 75,
                news_count: articles.count,
                summaries_count: 0,
                task_label: "Rattrapage 24h Autonome"
            )
            pipelineLogs.insert("🧬 Clustering Jaccard en cours sur \(articles.count) articles...", at: 0)
            
            let clusters = LocalClusterEngine.shared.cluster(articles: articles)
            let multiCount = clusters.filter { $0.isMultiSource }.count
            pipelineLogs.insert("📊 \(clusters.count) clusters formés (\(multiCount) multi-sources)", at: 0)
            
            self.currentPipelineStep = PipelineStepEvent(
                step_id: "synthesis",
                step_title: "Synthèse IA (\(selectedLLMProvider.rawValue))",
                details: "Génération Slow-News...",
                progress_pct: 80,
                news_count: articles.count,
                summaries_count: 0,
                task_label: "Rattrapage 24h Autonome"
            )
            pipelineLogs.insert("✍️ Synthèse IA via \(selectedLLMProvider.rawValue)...", at: 0)
            
            var generatedAlerts: [AlertPayload] = []
            let sortedClusters = clusters.sorted {
                if $0.isMultiSource != $1.isMultiSource {
                    return $0.isMultiSource && !$1.isMultiSource
                }
                return $0.sourcesCount > $1.sourcesCount
            }
            let toProcess = Array(sortedClusters.prefix(15))
            for (idx, c) in toProcess.enumerated() {
                let alert = await DirectLLMClient.shared.synthesizeCluster(
                    cluster: c,
                    language: userProfile.preferred_language,
                    provider: selectedLLMProvider
                )
                generatedAlerts.append(alert)
                
                let pct = 80 + Int(Double(idx + 1) / Double(max(1, toProcess.count)) * 18)
                self.currentPipelineStep = PipelineStepEvent(
                    step_id: "synthesis",
                    step_title: "Synthèse IA (\(selectedLLMProvider.rawValue))",
                    details: "Résumé \(idx + 1)/\(toProcess.count) : '\(c.mainTitle.prefix(45))...'",
                    progress_pct: pct,
                    news_count: articles.count,
                    summaries_count: idx + 1,
                    task_label: "Rattrapage 24h Autonome"
                )
                pipelineLogs.insert("✨ [\(idx+1)/\(toProcess.count)] Synthèse : \(alert.push_title.prefix(50))...", at: 0)
                if pipelineLogs.count > 100 { pipelineLogs.removeLast() }
            }
            
            if !generatedAlerts.isEmpty {
                for alert in generatedAlerts {
                    if !self.allAlerts.contains(where: { $0.id == alert.id }) {
                        self.allAlerts.insert(alert, at: 0)
                    }
                }
                LocalNewsStore.shared.saveAlerts(self.allAlerts)
                self.recomputeStreams()
                showToast("✅ Rattrapage autonome : \(generatedAlerts.count) dépêches synthétisées !")
                pipelineLogs.insert("🎉 Terminé ! \(generatedAlerts.count) résumés générés, \(articles.count) news analysées.", at: 0)
            } else {
                showToast("✨ Toutes les actualités 24h sont synchronisées.")
                pipelineLogs.insert("✨ Aucune nouvelle dépêche à synthétiser.", at: 0)
            }
            
            self.currentPipelineStep = PipelineStepEvent(
                step_id: "completed",
                step_title: "Rattrapage 24h Terminé",
                details: "\(generatedAlerts.count) dépêches générées en autonomie.",
                progress_pct: 100,
                status: "done",
                task_label: "Rattrapage 24h Autonome"
            )
            self.isScanning = false
            self.isCatchingUp = false
        } else {
            showToast("🌌 Scan & Rattrapage 24h sur serveur PC...")
            pipelineLogs.insert("🖥️ Envoi commande deep-scan-24h au serveur...", at: 0)
            do {
                try await APIClient.shared.trigger24hCatchUp()
                pipelineLogs.insert("✅ Commande envoyée — suivi via SSE en direct.", at: 0)
                
                // Safety watchdog: auto-release busy state if no completion received within 60s
                Task {
                    try? await Task.sleep(nanoseconds: 60_000_000_000)
                    if self.isCatchingUp {
                        await MainActor.run {
                            self.isCatchingUp = false
                            self.isScanning = false
                            Task { await self.loadAlertsHistory() }
                        }
                    }
                }
            } catch {
                showToast("❌ Erreur serveur PC : vérifiez l'IP ou basculez en mode autonome.")
                pipelineLogs.insert("❌ Erreur connexion serveur : \(error.localizedDescription)", at: 0)
                self.isScanning = false
                self.isCatchingUp = false
            }
        }
    }
    
    public func submitFeedback(clusterId: String, title: String, isPositive: Bool) async {
        HapticsManager.shared.impact(.light)
        showToast(isPositive ? "👍 Marqué comme pertinent" : "👎 Marqué comme bruit")
        do {
            try await APIClient.shared.submitFeedback(
                clusterId: clusterId,
                title: title,
                feedbackType: isPositive ? "read" : "rejected"
            )
        } catch {
            print("Feedback submission failed: \(error)")
        }
    }
    
    // MARK: - Health & Profile
    public func loadSourceHealth() async {
        isHealthLoading = true
        do {
            let report = try await APIClient.shared.fetchSourcesHealth()
            self.sourceHealthReport = report
        } catch {
            print("Health fetch error: \(error)")
        }
        isHealthLoading = false
    }
    
    public func loadUserProfile() async {
        do {
            let profile = try await APIClient.shared.fetchUserProfile()
            self.userProfile = profile
            if let data = try? JSONEncoder().encode(profile) {
                UserDefaults.standard.set(data, forKey: profileCacheKey)
            }
        } catch {
            if let pData = UserDefaults.standard.data(forKey: profileCacheKey),
               let cached = try? JSONDecoder().decode(UserProfile.self, from: pData) {
                self.userProfile = cached
            } else {
                let lang = Locale.current.language.languageCode?.identifier ?? "fr"
                self.userProfile.preferred_language = lang
            }
        }
    }
    
    public func saveUserProfile() async {
        if let data = try? JSONEncoder().encode(userProfile) {
            UserDefaults.standard.set(data, forKey: profileCacheKey)
        }
        do {
            try await APIClient.shared.saveUserProfile(userProfile)
            showToast("⚙️ Profil & Intérêts enregistrés")
            HapticsManager.shared.notification(.success)
        } catch {
            showToast("💾 Sauvegardé localement (Serveur inaccessible)")
        }
    }
    
    public func updateBioMarkdown(text: String) async {
        userProfile.bio_markdown = text
        await saveUserProfile()
    }
    
    // MARK: - Interest & Rejection Management
    public func addInterest(topic: String, weight: Double = 0.85) {
        let clean = topic.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return }
        userProfile.interests[clean] = weight
        HapticsManager.shared.impact(.light)
    }
    
    public func updateInterestWeight(topic: String, weight: Double) {
        userProfile.interests[topic] = weight
    }
    
    public func removeInterest(topic: String) {
        userProfile.interests.removeValue(forKey: topic)
        HapticsManager.shared.impact(.light)
    }
    
    public func addRejectionRule(keyword: String) {
        let clean = keyword.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !clean.isEmpty, !userProfile.rejection_rules.contains(clean) else { return }
        userProfile.rejection_rules.append(clean)
        HapticsManager.shared.impact(.light)
    }
    
    public func removeRejectionRule(keyword: String) {
        userProfile.rejection_rules.removeAll(where: { $0 == keyword })
        HapticsManager.shared.impact(.light)
    }
    
    // MARK: - 🎯 Named Entity Watchlist & Fast-Track
    public func loadEntityWatchlist() async {
        do {
            let list = try await APIClient.shared.fetchEntityWatchlist()
            await MainActor.run {
                self.entityWatchlist = list
                UserDefaults.standard.set(list, forKey: "newsstream_entity_watchlist_cache")
            }
        } catch {
            print("Watchlist fetch error (using local cache if available): \(error)")
        }
    }
    
    public func addWatchlistEntity(_ entity: String) async {
        let clean = entity.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty && !entityWatchlist.contains(where: { $0.caseInsensitiveCompare(clean) == .orderedSame }) else { return }
        HapticsManager.shared.impact(.light)
        entityWatchlist.append(clean)
        UserDefaults.standard.set(entityWatchlist, forKey: "newsstream_entity_watchlist_cache")
        showToast("🎯 Ajouté à la Watchlist : \(clean)")
        do {
            try await APIClient.shared.updateEntityWatchlist(watchlist: entityWatchlist)
        } catch {
            print("Server offline, saved watchlist locally: \(error)")
        }
    }
    
    public func removeWatchlistEntity(_ entity: String) async {
        HapticsManager.shared.impact(.light)
        entityWatchlist.removeAll { $0 == entity }
        UserDefaults.standard.set(entityWatchlist, forKey: "newsstream_entity_watchlist_cache")
        showToast("Retiré de la Watchlist : \(entity)")
        do {
            try await APIClient.shared.updateEntityWatchlist(watchlist: entityWatchlist)
        } catch {
            print("Server offline, saved watchlist locally: \(error)")
        }
    }
    
    // MARK: - 📱 Telegram Configuration & Dispatch
    public func loadTelegramSettings() async {
        isTelegramLoading = true
        do {
            let config = try await APIClient.shared.fetchTelegramSettings()
            await MainActor.run {
                self.telegramConfig = config
                if let raw = config.raw_token, !raw.isEmpty {
                    UserDefaults.standard.set(raw, forKey: "newsstream_telegram_token")
                }
                if !config.chat_id.isEmpty {
                    UserDefaults.standard.set(config.chat_id, forKey: "newsstream_telegram_chat_id")
                }
                UserDefaults.standard.set(config.enabled, forKey: "newsstream_telegram_enabled")
                self.isTelegramLoading = false
            }
        } catch {
            await MainActor.run {
                if let localToken = UserDefaults.standard.string(forKey: "newsstream_telegram_token"), !localToken.isEmpty,
                   let localChat = UserDefaults.standard.string(forKey: "newsstream_telegram_chat_id"), !localChat.isEmpty {
                    let enabled = UserDefaults.standard.bool(forKey: "newsstream_telegram_enabled")
                    self.telegramConfig = APIClient.TelegramConfig(
                        configured: true,
                        bot_token: localToken.count > 10 ? "\(localToken.prefix(6))...\(localToken.suffix(4))" : localToken,
                        raw_token: localToken,
                        chat_id: localChat,
                        enabled: enabled
                    )
                }
                self.isTelegramLoading = false
            }
        }
    }

    public func saveTelegramSettings(token: String, chatId: String, enabled: Bool = true) async -> Bool {
        isTelegramLoading = true
        let cleanToken = token.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanChatId = chatId.trimmingCharacters(in: .whitespacesAndNewlines)
        
        UserDefaults.standard.set(cleanToken, forKey: "newsstream_telegram_token")
        UserDefaults.standard.set(cleanChatId, forKey: "newsstream_telegram_chat_id")
        UserDefaults.standard.set(enabled, forKey: "newsstream_telegram_enabled")
        
        self.telegramConfig = APIClient.TelegramConfig(
            configured: !cleanToken.isEmpty && !cleanChatId.isEmpty,
            bot_token: cleanToken.count > 10 ? "\(cleanToken.prefix(6))...\(cleanToken.suffix(4))" : cleanToken,
            raw_token: cleanToken,
            chat_id: cleanChatId,
            enabled: enabled
        )
        
        do {
            try await APIClient.shared.saveTelegramSettings(token: cleanToken, chatId: cleanChatId, enabled: enabled)
            await loadTelegramSettings()
            showToast("💾 Paramètres Telegram enregistrés !")
            self.isTelegramLoading = false
            return true
        } catch {
            self.isTelegramLoading = false
            showToast("💾 Paramètres enregistrés localement (serveur hors-ligne)")
            return true
        }
    }

    @discardableResult
    public func testTelegramAlert(token: String? = nil, chatId: String? = nil) async -> (Bool, String) {
        HapticsManager.shared.impact(.medium)
        showToast("📱 Envoi du test Telegram...")
        
        let t = token ?? telegramConfig?.raw_token ?? UserDefaults.standard.string(forKey: "newsstream_telegram_token")
        let c = chatId ?? telegramConfig?.chat_id ?? UserDefaults.standard.string(forKey: "newsstream_telegram_chat_id")
        
        // 1. Try server endpoint first
        do {
            try await APIClient.shared.testTelegramNotification(token: t, chatId: c)
            showToast("✅ Notification test Telegram reçue !")
            return (true, "Message test envoyé avec succès via le serveur !")
        } catch {
            // 2. Fallback: direct Telegram Bot API call from device
            guard let botToken = t?.trimmingCharacters(in: .whitespacesAndNewlines), !botToken.isEmpty,
                  let targetChatId = c?.trimmingCharacters(in: .whitespacesAndNewlines), !targetChatId.isEmpty else {
                showToast("❌ Token ou Chat ID manquant")
                return (false, "Token ou Chat ID manquant")
            }
            
            let directResult = await sendTelegramDirect(
                botToken: botToken,
                chatId: targetChatId,
                text: "🚀 *MyNews AI* — Notification de test directe !\n\nVotre bot Telegram est connecté et opérationnel."
            )
            if directResult.0 {
                showToast("✅ Notification test reçue sur Telegram !")
                return (true, "Message test délivré avec succès à Telegram !")
            } else {
                showToast("❌ Échec test : \(directResult.1)")
                return (false, directResult.1)
            }
        }
    }
    
    private func sendTelegramDirect(botToken: String, chatId: String, text: String) async -> (Bool, String) {
        guard let url = URL(string: "https://api.telegram.org/bot\(botToken)/sendMessage") else {
            return (false, "URL Telegram invalide")
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let payload: [String: Any] = [
            "chat_id": chatId,
            "text": text,
            "parse_mode": "Markdown"
        ]
        guard let httpBody = try? JSONSerialization.data(withJSONObject: payload) else {
            return (false, "Erreur sérialisation")
        }
        request.httpBody = httpBody
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            if let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) {
                return (true, "OK")
            } else {
                let errStr = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["description"] as? String ?? "Erreur HTTP \((response as? HTTPURLResponse)?.statusCode ?? 0)"
                return (false, errStr)
            }
        } catch {
            return (false, error.localizedDescription)
        }
    }
    
    // MARK: - ☀️ Morning Briefing & Stream RAG
    public func triggerMorningBriefTelegram() async {
        HapticsManager.shared.impact(.medium)
        showToast("☀️ Synthèse et envoi du Briefing...")
        do {
            try await APIClient.shared.triggerBriefingTelegram()
            showToast("✅ Morning Briefing envoyé sur Telegram !")
        } catch {
            // Direct fallback if server offline
            let token = telegramConfig?.raw_token ?? UserDefaults.standard.string(forKey: "newsstream_telegram_token")
            let chatId = telegramConfig?.chat_id ?? UserDefaults.standard.string(forKey: "newsstream_telegram_chat_id")
            
            if let t = token, !t.isEmpty, let c = chatId, !c.isEmpty, !multiSourceAlerts.isEmpty {
                let topNews = multiSourceAlerts.prefix(5)
                var msg = "☀️ *Morning Briefing — MyNews AI*\n\n"
                for (idx, item) in topNews.enumerated() {
                    msg += "*\(idx + 1). \(item.push_title)*\n"
                    if let firstBullet = item.bullet_points.first {
                        msg += "• \(firstBullet)\n"
                    }
                    msg += "\n"
                }
                let res = await sendTelegramDirect(botToken: t, chatId: c, text: msg)
                if res.0 {
                    showToast("✅ Briefing transmis directement sur Telegram !")
                    return
                }
            }
            showToast("❌ Échec envoi Briefing : vérifiez les réglages Telegram")
        }
    }

    public func askStreamIntelligence(query: String) async -> String {
        do {
            let res = try await APIClient.shared.askStream(query: query)
            return res.answer
        } catch {
            return "Erreur lors de l'interrogation du flux : \(error.localizedDescription)"
        }
    }

    public func recordImplicitFeedback(category: String, dwellSeconds: Double, action: String = "dwell") {
        Task {
            try? await APIClient.shared.submitImplicitFeedback(
                category: category,
                dwellSeconds: dwellSeconds,
                action: action
            )
        }
    }
    
    public func showToast(_ message: String) {
        withAnimation {
            self.toastMessage = message
        }
        Task {
            try? await Task.sleep(nanoseconds: 3_500_000_000)
            if self.toastMessage == message {
                withAnimation {
                    self.toastMessage = nil
                }
            }
        }
    }
}
