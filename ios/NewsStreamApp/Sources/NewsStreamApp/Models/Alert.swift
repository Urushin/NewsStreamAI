import Foundation

public struct CitationInfo: Codable, Hashable, Sendable {
    public let quote: String
    public let source: String?
    public let url: String?
    
    public init(quote: String, source: String? = nil, url: String? = nil) {
        self.quote = quote
        self.source = source
        self.url = url
    }
}

public struct AlertSource: Codable, Identifiable, Hashable, Sendable {
    public var id: String { url }
    public let name: String
    public let domain: String
    public let url: String
    public let tier: Int
    
    public init(name: String, domain: String, url: String, tier: Int = 2) {
        self.name = name
        self.domain = domain
        self.url = url
        self.tier = tier
    }
}

public struct AlertPayload: Codable, Identifiable, Hashable, Sendable {
    public var id: String { alert_id }
    
    public let alert_id: String
    public let cluster_id: String
    public let timestamp: String
    public let push_title: String
    public let bullet_points: [String]
    public let sources: [AlertSource]
    public let velocity_score: Double
    public let relevance_score: Double
    public let hybrid_score: Double
    public let reliability_label: String
    public let category: String
    public let context_explainer: String?
    public let community_sentiment: String?
    public let original_title: String?
    public let was_clickbait_enhanced: Bool?
    public let image_url: String?
    public let detailed_story: String?
    public let citations: [String: CitationInfo]?
    
    // 🌍 3D Globe Coordinates
    public let latitude: Double?
    public let longitude: Double?
    public let location_name: String?
    public let country_code: String?
    
    // ⚡ Fast-Track & Buzz
    public let is_fast_track: Bool?
    public let buzz_score: Double?
    public let matched_entities: [String]?
    
    public var isBreaking: Bool {
        (is_fast_track ?? false) || velocity_score >= 0.85 || (buzz_score ?? 0.0) >= 0.75
    }
    
    public init(
        alert_id: String = UUID().uuidString,
        cluster_id: String = UUID().uuidString,
        timestamp: String = ISO8601DateFormatter().string(from: Date()),
        push_title: String,
        bullet_points: [String],
        sources: [AlertSource],
        velocity_score: Double = 1.0,
        relevance_score: Double = 0.8,
        hybrid_score: Double = 0.85,
        reliability_label: String = "FAIT_OBJECTIF_FIABLE",
        category: String = "Général",
        context_explainer: String? = nil,
        community_sentiment: String? = nil,
        original_title: String? = nil,
        was_clickbait_enhanced: Bool? = false,
        image_url: String? = nil,
        detailed_story: String? = nil,
        citations: [String: CitationInfo]? = nil,
        latitude: Double? = nil,
        longitude: Double? = nil,
        location_name: String? = nil,
        country_code: String? = nil,
        is_fast_track: Bool? = false,
        buzz_score: Double? = 0.0,
        matched_entities: [String]? = nil
    ) {
        self.alert_id = alert_id
        self.cluster_id = cluster_id
        self.timestamp = timestamp
        self.push_title = push_title
        self.bullet_points = bullet_points
        self.sources = sources
        self.velocity_score = velocity_score
        self.relevance_score = relevance_score
        self.hybrid_score = hybrid_score
        self.reliability_label = reliability_label
        self.category = category
        self.context_explainer = context_explainer
        self.community_sentiment = community_sentiment
        self.original_title = original_title
        self.was_clickbait_enhanced = was_clickbait_enhanced
        self.image_url = image_url
        self.detailed_story = detailed_story
        self.citations = citations
        self.latitude = latitude
        self.longitude = longitude
        self.location_name = location_name
        self.country_code = country_code
        self.is_fast_track = is_fast_track
        self.buzz_score = buzz_score
        self.matched_entities = matched_entities
    }
    
    private enum CodingKeys: String, CodingKey {
        case alert_id, cluster_id, timestamp, push_title, bullet_points, sources
        case velocity_score, relevance_score, hybrid_score, reliability_label, category
        case context_explainer, community_sentiment, original_title, was_clickbait_enhanced
        case image_url, detailed_story, citations
        case latitude, longitude, location_name, country_code
        case is_fast_track, buzz_score, matched_entities
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.alert_id = (try? container.decodeIfPresent(String.self, forKey: .alert_id)) ?? UUID().uuidString
        self.cluster_id = (try? container.decodeIfPresent(String.self, forKey: .cluster_id)) ?? UUID().uuidString
        self.timestamp = (try? container.decodeIfPresent(String.self, forKey: .timestamp)) ?? ISO8601DateFormatter().string(from: Date())
        self.push_title = (try? container.decodeIfPresent(String.self, forKey: .push_title)) ?? ""
        self.bullet_points = (try? container.decodeIfPresent([String].self, forKey: .bullet_points)) ?? []
        self.sources = (try? container.decodeIfPresent([AlertSource].self, forKey: .sources)) ?? []
        self.velocity_score = (try? container.decodeIfPresent(Double.self, forKey: .velocity_score)) ?? 1.0
        self.relevance_score = (try? container.decodeIfPresent(Double.self, forKey: .relevance_score)) ?? 0.8
        self.hybrid_score = (try? container.decodeIfPresent(Double.self, forKey: .hybrid_score)) ?? 0.85
        self.reliability_label = (try? container.decodeIfPresent(String.self, forKey: .reliability_label)) ?? "FAIT_OBJECTIF_FIABLE"
        self.category = (try? container.decodeIfPresent(String.self, forKey: .category)) ?? "Actualités"
        self.context_explainer = try? container.decodeIfPresent(String.self, forKey: .context_explainer)
        self.community_sentiment = try? container.decodeIfPresent(String.self, forKey: .community_sentiment)
        self.original_title = try? container.decodeIfPresent(String.self, forKey: .original_title)
        self.was_clickbait_enhanced = try? container.decodeIfPresent(Bool.self, forKey: .was_clickbait_enhanced)
        self.image_url = try? container.decodeIfPresent(String.self, forKey: .image_url)
        self.detailed_story = try? container.decodeIfPresent(String.self, forKey: .detailed_story)
        self.citations = try? container.decodeIfPresent([String: CitationInfo].self, forKey: .citations)
        self.latitude = try? container.decodeIfPresent(Double.self, forKey: .latitude)
        self.longitude = try? container.decodeIfPresent(Double.self, forKey: .longitude)
        self.location_name = try? container.decodeIfPresent(String.self, forKey: .location_name)
        self.country_code = try? container.decodeIfPresent(String.self, forKey: .country_code)
        self.is_fast_track = try? container.decodeIfPresent(Bool.self, forKey: .is_fast_track)
        self.buzz_score = try? container.decodeIfPresent(Double.self, forKey: .buzz_score)
        self.matched_entities = try? container.decodeIfPresent([String].self, forKey: .matched_entities)
    }
    
    public var parsedDate: Date {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: timestamp) {
            return date
        }
        let fallback = ISO8601DateFormatter()
        if let date = fallback.date(from: timestamp) {
            return date
        }
        return Date.distantPast
    }
    
    public var formattedDate: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: timestamp) {
            let displayFormatter = DateFormatter()
            displayFormatter.timeStyle = .short
            displayFormatter.dateStyle = .none
            return displayFormatter.string(from: date)
        }
        let fallback = ISO8601DateFormatter()
        if let date = fallback.date(from: timestamp) {
            let displayFormatter = DateFormatter()
            displayFormatter.timeStyle = .short
            displayFormatter.dateStyle = .none
            return displayFormatter.string(from: date)
        }
        return ""
    }
    
    public var isMultiSource: Bool {
        sources.count >= 2
    }
    
    public var reliabilityEmoji: String {
        switch reliability_label {
        case "FAIT_OBJECTIF_FIABLE": return "✅"
        case "INFORMATION_PARTIELLE": return "⚠️"
        case "SIGNAL_SOCIAL_TENDANCE": return "🔥"
        case "RUMEUR_NON_CONFIRMEE": return "❌"
        default: return "📌"
        }
    }
}
