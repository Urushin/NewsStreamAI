import Foundation

public struct FeedHealthItem: Codable, Identifiable, Hashable, Sendable {
    public var id: String { name }
    public let name: String
    public let feed_url: String?
    public let success_count: Int?
    public let failure_count: Int?
    public let consecutive_failures: Int?
    public let avg_latency_ms: Double?
    public let total_items_fetched: Int?
    public let quarantined_until: Double?
    public let last_status: String?
    public let last_seen_at: String?
    public let last_error: String?
    
    // Media Transparency & Ownership
    public let owner: String?
    public let orientation: String?
    public let funding: String?
    public let country: String?
    public let profile_description: String?
    
    public var isOk: Bool {
        last_status == "ok"
    }
    
    public var isQuarantined: Bool {
        guard let until = quarantined_until else { return false }
        return Date().timeIntervalSince1970 < until
    }
}

public struct SourceHealthReport: Codable, Sendable {
    public let total_tracked: Int
    public let ok_count: Int
    public let error_count: Int
    public let quarantined_count: Int
    public let health_percentage: Double
    public let sources: [FeedHealthItem]
}
