import Foundation

// MARK: - YouTube Video Item
public struct YouTubeVideoItem: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let video_id: String
    public let title: String
    public let channel_name: String
    public let channel_handle: String?
    public let channel_id: String
    public let thumbnail_url: String
    public let published_at: String
    public let url: String
    
    public init(
        id: String = UUID().uuidString,
        video_id: String,
        title: String,
        channel_name: String,
        channel_handle: String? = nil,
        channel_id: String,
        thumbnail_url: String,
        published_at: String,
        url: String
    ) {
        self.id = id
        self.video_id = video_id
        self.title = title
        self.channel_name = channel_name
        self.channel_handle = channel_handle
        self.channel_id = channel_id
        self.thumbnail_url = thumbnail_url
        self.published_at = published_at
        self.url = url
    }
}

// MARK: - Release Update Item
public struct ReleaseUpdateItem: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let product_name: String
    public let version: String
    public let title: String
    public let summary_ai: String
    public let source_url: String
    public let published_at: String
    public let category: String
    public let icon_name: String?
    public let artwork_url: String?
    
    public init(
        id: String = UUID().uuidString,
        product_name: String,
        version: String,
        title: String,
        summary_ai: String,
        source_url: String,
        published_at: String,
        category: String = "Outil & Logiciel",
        icon_name: String? = "cube.fill",
        artwork_url: String? = nil
    ) {
        self.id = id
        self.product_name = product_name
        self.version = version
        self.title = title
        self.summary_ai = summary_ai
        self.source_url = source_url
        self.published_at = published_at
        self.category = category
        self.icon_name = icon_name
        self.artwork_url = artwork_url
    }
}

// MARK: - Content Feed Response
public struct ContentFeedResponse: Codable, Sendable {
    public let videos: [YouTubeVideoItem]
    public let releases: [ReleaseUpdateItem]
}

// MARK: - Watchlist Response
public struct WatchlistResponse: Codable, Sendable {
    public let youtube_channels: [[String: String]]
    public let github_repos: [String]
    public let tracked_apps: [String]?
    public let twitter_accounts: [String]?
}

// MARK: - Globe 3D Event & Arc Models (WorldMonitor Engine)
public struct GlobeArcItem: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let from_id: String
    public let from_lat: Double
    public let from_lon: Double
    public let from_name: String?
    public let to_id: String
    public let to_lat: Double
    public let to_lon: Double
    public let to_name: String?
    public let label: String?
}

public struct GlobeEventItem: Codable, Identifiable, Hashable, Sendable {
    public var id: String { alert_id }
    public let alert_id: String
    public let title: String
    public let category: String
    public let reliability_label: String
    public let sources_count: Int
    public let sources_names: [String]?
    public let latitude: Double
    public let longitude: Double
    public let location_name: String?
    public let country_code: String?
    public let severity: String?
    public let status: String?
    public let summary: String?
    public let impact_score: Double?
    public let timestamp: String
    public let detailed_story: String?
    
    public var isCritical: Bool {
        severity?.lowercased() == "critical"
    }
    
    public var isActive: Bool {
        status?.lowercased() == "active"
    }
    
    public var formattedCoords: String {
        let latDir = latitude >= 0 ? "N" : "S"
        let lonDir = longitude >= 0 ? "E" : "O"
        return String(format: "%.2f°%@, %.2f°%@", abs(latitude), latDir, abs(longitude), lonDir)
    }
}

public struct GlobeEventsResponse: Codable, Sendable {
    public let total_events: Int
    public let events: [GlobeEventItem]
    public let country_density: [String: Int]
    public let arcs: [GlobeArcItem]?
}

// MARK: - Live Search Results
public struct YouTubeSearchResult: Identifiable, Codable, Hashable, Sendable {
    public var id: String
    public var title: String
    public var handle: String
    public var thumbnail: String
    
    public init(id: String, title: String, handle: String, thumbnail: String) {
        self.id = id
        self.title = title
        self.handle = handle
        self.thumbnail = thumbnail
    }
}

public struct GitHubSearchResult: Identifiable, Codable, Hashable, Sendable {
    public var id: String { full_name }
    public var full_name: String
    public var name: String
    public var owner: String?
    public var avatar_url: String?
    public var description: String?
    public var stars: Int?
    public var language: String?
    public var url: String?
    
    public init(
        full_name: String,
        name: String,
        owner: String? = nil,
        avatar_url: String? = nil,
        description: String? = nil,
        stars: Int? = nil,
        language: String? = nil,
        url: String? = nil
    ) {
        self.full_name = full_name
        self.name = name
        self.owner = owner
        self.avatar_url = avatar_url
        self.description = description
        self.stars = stars
        self.language = language
        self.url = url
    }
}

