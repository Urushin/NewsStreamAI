import Foundation

public final class APIClient: @unchecked Sendable {
    public static let shared = APIClient()
    
    public var baseURLString: String {
        get {
            #if targetEnvironment(simulator)
            let defaultHost = "http://127.0.0.1:8000"
            #else
            let defaultHost = "http://192.168.1.189:8000"
            #endif

            guard let saved = UserDefaults.standard.string(forKey: "newsstream_api_base_url"), !saved.isEmpty else {
                return defaultHost
            }
            #if targetEnvironment(simulator)
            if saved.contains("100.70.") || saved.contains(".local") || saved.contains("192.168.") {
                UserDefaults.standard.set(defaultHost, forKey: "newsstream_api_base_url")
                return defaultHost
            }
            #endif
            return saved
        }
        set {
            UserDefaults.standard.set(newValue, forKey: "newsstream_api_base_url")
        }
    }
    
    public var candidateHosts: [String] {
        #if targetEnvironment(simulator)
        return [
            "http://127.0.0.1:8000",
            "http://localhost:8000"
        ]
        #else
        return [
            "http://192.168.1.189:8000"
        ]
        #endif
    }
    
    private let session: URLSession
    private let decoder: JSONDecoder
    
    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 8.0
        config.timeoutIntervalForResource = 25.0
        config.waitsForConnectivity = false
        self.session = URLSession(configuration: config)
        self.decoder = JSONDecoder()
    }
    
    private func executeData(path: String, method: String = "GET", body: Data? = nil, customTimeout: TimeInterval? = nil) async throws -> (Data, HTTPURLResponse) {
        var hostsToTry = [baseURLString]
        for candidate in candidateHosts where candidate != baseURLString {
            hostsToTry.append(candidate)
        }
        
        var lastError: Error = URLError(.cannotConnectToHost)
        
        for host in hostsToTry {
            let cleanPath = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            guard let url = URL(string: "\(host)/\(cleanPath)") else {
                continue
            }
            var request = URLRequest(url: url)
            request.httpMethod = method
            request.timeoutInterval = customTimeout ?? 6.0
            if let body = body {
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.httpBody = body
            }
            
            do {
                let (data, response) = try await session.data(for: request)
                if let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) {
                    if host != self.baseURLString {
                        self.baseURLString = host
                    }
                    return (data, httpResponse)
                }
            } catch {
                lastError = error
            }
        }
        
        throw lastError
    }
    
    // MARK: - Multi-Source Alerts (>= 2 Sources)
    public func fetchMultiAlerts() async throws -> [AlertPayload] {
        let (data, _) = try await executeData(path: "api/alerts/multi")
        struct Response: Codable {
            let total: Int?
            let alerts: [AlertPayload]
        }
        let res = try decoder.decode(Response.self, from: data)
        return res.alerts
    }
    
    // MARK: - Single-Source Alerts (1 Source)
    public func fetchSingleAlerts() async throws -> [AlertPayload] {
        let (data, _) = try await executeData(path: "api/alerts/single")
        struct Response: Codable {
            let total: Int?
            let alerts: [AlertPayload]
        }
        let res = try decoder.decode(Response.self, from: data)
        return res.alerts
    }
    
    // MARK: - Legacy History Fallback
    public func fetchAlertsHistory() async throws -> [AlertPayload] {
        let (data, _) = try await executeData(path: "api/alerts/history")
        struct HistoryResponse: Codable {
            let total: Int?
            let alerts: [AlertPayload]
        }
        let res = try decoder.decode(HistoryResponse.self, from: data)
        return res.alerts
    }

    // MARK: - V2 Core Endpoints
    public func fetchV2Feed(limit: Int = 50) async throws -> [V2Event] {
        let (data, _) = try await executeData(path: "api/v2/feed?limit=\(limit)", customTimeout: 90)
        return try decoder.decode(V2FeedResponse.self, from: data).items
    }
    
    public func fetchV2FeedPage(limit: Int = 30, offset: Int = 0, sort: String = "personalized", filter: String = "all") async throws -> V2FeedResponse {
        var path = "api/v2/feed?limit=\(limit)&offset=\(offset)&sort=\(sort)"
        if filter != "all" {
            path += "&filter=\(filter)"
        }
        let (data, _) = try await executeData(path: path, customTimeout: 90)
        return try decoder.decode(V2FeedResponse.self, from: data)
    }

    public func fetchV2Event(eventId: String) async throws -> V2EventDetail {
        let (data, _) = try await executeData(path: "api/v2/events/\(eventId)")
        return try decoder.decode(V2EventDetail.self, from: data)
    }
    
    public func fetchV2Claims(eventId: String) async throws -> [V2Claim] {
        let (data, _) = try await executeData(path: "api/v2/events/\(eventId)/claims")
        return try decoder.decode(V2ClaimsResponse.self, from: data).claims
    }
    
    public func fetchV2History(eventId: String) async throws -> V2EventHistoryResponse {
        let (data, _) = try await executeData(path: "api/v2/events/\(eventId)/history")
        return try decoder.decode(V2EventHistoryResponse.self, from: data)
    }
    
    public func fetchV2Saved(limit: Int = 50) async throws -> [V2Event] {
        let (data, _) = try await executeData(path: "api/v2/saved?limit=\(limit)")
        return try decoder.decode(V2SavedResponse.self, from: data).items
    }
    
    public func searchV2(query: String, limit: Int = 30) async throws -> [V2Event] {
        var components = URLComponents()
        components.queryItems = [URLQueryItem(name: "q", value: query), URLQueryItem(name: "limit", value: String(limit))]
        let (data, _) = try await executeData(path: "api/v2/search?\(components.percentEncodedQuery ?? "")")
        return try decoder.decode(V2SearchResponse.self, from: data).items
    }
    
    public func fetchV2Explore() async throws -> V2ExploreResponse {
        let (data, _) = try await executeData(path: "api/v2/explore")
        return try decoder.decode(V2ExploreResponse.self, from: data)
    }
    
    @discardableResult
    public func postV2Interaction(
        eventId: String,
        type: String,
        duration: Int? = nil,
        sourceId: String? = nil,
        metadata: [String: Any]? = nil
    ) async -> Bool {
        var payload: [String: Any] = [
            "event_id": eventId,
            "interaction_type": type,
            "surface": "ios",
            "client_event_id": UUID().uuidString
        ]
        if let duration { payload["duration_ms"] = duration }
        if let sourceId { payload["source_id"] = sourceId }
        if let metadata { payload["metadata"] = metadata }
        
        do {
            let body = try JSONSerialization.data(withJSONObject: payload)
            _ = try await executeData(path: "api/v2/interactions", method: "POST", body: body)
            return true
        } catch {
            return false
        }
    }
    
    // MARK: - Sources Health
    public func fetchSourcesHealth() async throws -> SourceHealthReport {
        let (data, _) = try await executeData(path: "api/sources/health")
        return try decoder.decode(SourceHealthReport.self, from: data)
    }
    
    // MARK: - User Profile
    public func fetchUserProfile(username: String = "default_user") async throws -> UserProfile {
        let (data, _) = try await executeData(path: "api/profile/\(username)")
        return try decoder.decode(UserProfile.self, from: data)
    }
    
    public func saveUserProfile(_ profile: UserProfile) async throws {
        let body = try JSONEncoder().encode(profile)
        _ = try await executeData(path: "api/profile", method: "POST", body: body)
    }
    
    // MARK: - Trigger Simulation
    public func triggerSimulation() async throws {
        _ = try await executeData(path: "api/simulate-pulse", method: "POST")
    }
    
    // MARK: - Trigger 24H Deep Catch-Up
    public func trigger24hCatchUp() async throws {
        _ = try await executeData(path: "api/stream/deep-scan-24h", method: "POST", customTimeout: 120.0)
    }
    
    // MARK: - Ping / Health Test
    public func pingServer(host: String) async -> (Bool, Double) {
        let clean = host.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: "\(clean)/api/health") else {
            return (false, 0)
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 3.5
        let start = CFAbsoluteTimeGetCurrent()
        do {
            let (_, response) = try await session.data(for: request)
            let elapsedMs = (CFAbsoluteTimeGetCurrent() - start) * 1000.0
            if let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) {
                return (true, elapsedMs)
            }
            return (false, elapsedMs)
        } catch {
            return (false, 0)
        }
    }
    
    // MARK: - Feedback Loop (Interested / Rejected)
    public func submitFeedback(clusterId: String, title: String, feedbackType: String) async throws {
        let payload: [String: String] = [
            "username": "default_user",
            "cluster_id": clusterId,
            "alert_title": title,
            "action": feedbackType
        ]
        let body = try JSONSerialization.data(withJSONObject: payload)
        _ = try? await executeData(path: "api/feedback", method: "POST", body: body)
    }
    
    // MARK: - Administration & Purge
    public func purgeAlerts() async throws {
        _ = try await executeData(path: "api/purge", method: "POST")
    }
    
    // MARK: - 🌍 Globe 3D Events
    public func fetchGlobeEvents(timeframe: String? = nil, severity: String? = nil, category: String? = nil) async throws -> GlobeEventsResponse {
        var queryItems: [String] = []
        if let tf = timeframe, !tf.isEmpty, tf != "all" { queryItems.append("timeframe=\(tf)") }
        if let sev = severity, !sev.isEmpty, sev != "all" { queryItems.append("severity=\(sev)") }
        if let cat = category, !cat.isEmpty, cat != "all" {
            let encodedCat = cat.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? cat
            queryItems.append("category=\(encodedCat)")
        }
        let queryString = queryItems.isEmpty ? "" : "?\(queryItems.joined(separator: "&"))"
        let (data, _) = try await executeData(path: "api/globe/events\(queryString)")
        return try decoder.decode(GlobeEventsResponse.self, from: data)
    }
    
    // MARK: - 🎬 Content Hub (YouTube & Releases)
    public func fetchContentFeed() async throws -> ContentFeedResponse {
        let (data, _) = try await executeData(path: "api/content/feed")
        return try decoder.decode(ContentFeedResponse.self, from: data)
    }
    
    public func fetchWatchlist() async throws -> WatchlistResponse {
        let (data, _) = try await executeData(path: "api/content/watchlist")
        return try decoder.decode(WatchlistResponse.self, from: data)
    }
    
    public func trackEntity(type: String, target: String) async throws {
        let payload: [String: String] = ["type": type, "target": target]
        let body = try JSONSerialization.data(withJSONObject: payload)
        _ = try await executeData(path: "api/content/track", method: "POST", body: body)
    }
    
    public func untrackEntity(type: String, targetId: String) async throws {
        let payload: [String: String] = ["type": type, "target_id": targetId]
        let body = try JSONSerialization.data(withJSONObject: payload)
        _ = try await executeData(path: "api/content/untrack", method: "POST", body: body)
    }
    
    // MARK: - 🔍 Live Search
    public func searchYouTube(query: String) async throws -> [YouTubeSearchResult] {
        let clean = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        let (data, _) = try await executeData(path: "api/youtube/search?q=\(clean)")
        struct SearchResp: Codable { let results: [YouTubeSearchResult] }
        return try decoder.decode(SearchResp.self, from: data).results
    }
    
    public func searchGitHub(query: String) async throws -> [GitHubSearchResult] {
        let clean = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        let (data, _) = try await executeData(path: "api/github/search?q=\(clean)")
        struct SearchResp: Codable { let results: [GitHubSearchResult] }
        return try decoder.decode(SearchResp.self, from: data).results
    }
    
    // MARK: - 🎯 Named Entity Watchlist & Fast-Track
    public func fetchEntityWatchlist() async throws -> [String] {
        let (data, _) = try await executeData(path: "api/user/watchlist")
        struct EntityWatchlistResp: Codable { let status: String; let watchlist: [String] }
        return try decoder.decode(EntityWatchlistResp.self, from: data).watchlist
    }

    public func updateEntityWatchlist(watchlist: [String]) async throws {
        let payload: [String: Any] = [
            "username": "default_user",
            "watchlist": watchlist
        ]
        let body = try JSONSerialization.data(withJSONObject: payload)
        _ = try await executeData(path: "api/user/watchlist", method: "POST", body: body)
    }

    public struct TelegramConfig: Codable, Sendable {
        public let configured: Bool
        public let bot_token: String
        public let raw_token: String?
        public let chat_id: String
        public let enabled: Bool
    }

    public func fetchTelegramSettings() async throws -> TelegramConfig {
        let (data, _) = try await executeData(path: "api/settings/telegram")
        return try decoder.decode(TelegramConfig.self, from: data)
    }

    public func saveTelegramSettings(token: String, chatId: String, enabled: Bool = true) async throws {
        let payload: [String: Any] = [
            "token": token,
            "chat_id": chatId,
            "enabled": enabled
        ]
        let body = try JSONSerialization.data(withJSONObject: payload)
        _ = try await executeData(path: "api/settings/telegram", method: "POST", body: body)
    }

    public func testTelegramNotification(token: String? = nil, chatId: String? = nil) async throws {
        var payload: [String: String] = [:]
        if let t = token, !t.isEmpty { payload["token"] = t }
        if let c = chatId, !c.isEmpty { payload["chat_id"] = c }
        let body = try JSONSerialization.data(withJSONObject: payload)
        _ = try await executeData(path: "api/notifications/test-telegram", method: "POST", body: body)
    }
    
    // MARK: - ☀️ Morning Briefing & Stream RAG
    public struct MorningBriefHighlight: Codable, Hashable, Sendable, Identifiable {
        public var id: String { headline }
        public let topic: String
        public let headline: String
        public let summary: String
        public let sources: String
    }

    public struct MorningBriefingData: Codable, Sendable {
        public let greeting: String
        public let key_highlights: [MorningBriefHighlight]
        public let radar_count: Int?
        public let curated_count: Int?
    }

    public struct TodayBriefingResponse: Codable, Sendable {
        public let status: String
        public let briefing: MorningBriefingData?
        public let message: String?
    }

    public func fetchTodayBriefing() async throws -> MorningBriefingData? {
        let (data, _) = try await executeData(path: "api/briefing/today")
        let res = try decoder.decode(TodayBriefingResponse.self, from: data)
        return res.briefing
    }

    public func triggerBriefingTelegram() async throws {
        _ = try await executeData(path: "api/briefing/trigger-now", method: "POST")
    }

    public struct RAGSource: Codable, Hashable, Sendable {
        public let name: String
        public let url: String
    }

    public struct StreamAskResponse: Codable, Sendable {
        public let status: String
        public let answer: String
        public let sources: [RAGSource]?
    }

    public func askStream(query: String) async throws -> StreamAskResponse {
        let payload = ["query": query]
        let body = try JSONSerialization.data(withJSONObject: payload)
        let (data, _) = try await executeData(path: "api/stream/ask", method: "POST", body: body)
        return try decoder.decode(StreamAskResponse.self, from: data)
    }

    public func submitImplicitFeedback(category: String, dwellSeconds: Double, action: String = "dwell") async throws {
        let payload: [String: Any] = [
            "username": "default_user",
            "category": category,
            "dwell_seconds": dwellSeconds,
            "action": action
        ]
        let body = try JSONSerialization.data(withJSONObject: payload)
        _ = try? await executeData(path: "api/feedback/implicit", method: "POST", body: body)
    }
}
