import Foundation
import SwiftUI

public struct V2FeedResponse: Codable, Sendable {
    public let userId: String
    public let rolloutEnabled: Bool?
    public let items: [V2Event]
    public let nextOffset: Int?
    public let hasMore: Bool?
    
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case rolloutEnabled = "rollout_enabled"
        case nextOffset = "next_offset"
        case hasMore = "has_more"
        case items
    }
}

public struct V2Event: Codable, Identifiable, Sendable, Hashable {
    public let eventId: String
    public let canonicalTitle: String
    public let lifecycle: String?
    public let lastActivityAt: String?
    public var publishedAt: String? = nil
    public let summaryId: String?
    public let headline: String?
    public let shortSummary: String?
    public let freshnessStatus: String?
    public let interestScore: Double?
    public let impactScore: Double?
    public let globalImportanceScore: Double?
    public let discoveryScore: Double?
    public let finalScore: Double?
    public let eligibilityId: String?
    public let sources: [V2Source]
    public let scoreReasons: [V2ScoreReason]?
    public let imageUrl: String?
    public let saved: Bool?
    public let liked: Bool?
    
    public var id: String { eventId }
    
    public var resolvedImageURL: URL? {
        if let imageUrl, !imageUrl.isEmpty, let u = URL(string: imageUrl) {
            return u
        }
        return nil
    }

    public var heroImageURL: URL? { resolvedImageURL }

    public var primaryFaviconURL: URL? {
        sources.first?.faviconURL
    }
    
    public var displayTitle: String {
        let title = headline?.trimmingCharacters(in: .whitespacesAndNewlines)
        if let title, !title.isEmpty { return title }
        return canonicalTitle
    }
    
    public var relativeTimeString: String {
        guard let publishedAt else { return "Date de publication inconnue" }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = formatter.date(from: publishedAt)
        if date == nil {
            formatter.formatOptions = [.withInternetDateTime]
            date = formatter.date(from: publishedAt)
        }
        guard let date else { return "Date de publication inconnue" }
        
        let seconds = -date.timeIntervalSinceNow
        if seconds < 60 { return "À l'instant" }
        let minutes = Int(seconds / 60)
        if minutes < 60 { return "\(minutes) min" }
        let hours = Int(minutes / 60)
        if hours < 24 { return "\(hours) h" }
        let days = Int(hours / 24)
        return "\(days) j"
    }
    
    public var humanCategory: String {
        if let domain = sources.first?.canonicalDomain, !domain.isEmpty {
            return domain.replacingOccurrences(of: "www.", with: "")
        }
        return sources.first?.canonicalName ?? "Actualité"
    }
    
    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case canonicalTitle = "canonical_title"
        case lifecycle
        case lastActivityAt = "last_activity_at"
        case publishedAt = "published_at"
        case summaryId = "summary_id"
        case headline
        case shortSummary = "short_summary"
        case freshnessStatus = "freshness_status"
        case interestScore = "interest_score"
        case impactScore = "impact_score"
        case globalImportanceScore = "global_importance_score"
        case discoveryScore = "discovery_score"
        case finalScore = "final_score"
        case eligibilityId = "eligibility_id"
        case sources
        case scoreReasons = "score_reasons"
        case imageUrl = "image_url"
        case saved
        case liked
    }
}

public struct V2Source: Codable, Identifiable, Sendable, Hashable {
    public let id: String
    public let canonicalName: String
    public let canonicalDomain: String?
    public let url: String?

    public var articleURL: URL? {
        guard let url, let result = URL(string: url), ["https", "http"].contains(result.scheme?.lowercased() ?? "") else { return nil }
        return result
    }

    public var faviconURL: URL? {
        let domain = canonicalDomain ?? (url.flatMap { URL(string: $0)?.host })
        guard let d = domain, !d.isEmpty else { return nil }
        let clean = d.replacingOccurrences(of: "www.", with: "")
        return URL(string: "https://www.google.com/s2/favicons?domain=\(clean)&sz=64")
    }
    
    public var displayName: String {
        if let domain = canonicalDomain, !domain.isEmpty {
            return domain.replacingOccurrences(of: "www.", with: "")
        }
        return canonicalName.replacingOccurrences(of: "rss_", with: "").capitalized
    }
    
    enum CodingKeys: String, CodingKey {
        case id
        case canonicalName = "canonical_name"
        case canonicalDomain = "canonical_domain"
        case url
    }
}

public struct V2ScoreReason: Codable, Sendable, Hashable {
    public let reasonType: String
    public let contribution: Double?
    public let weight: Double?
    public let explanationKey: String?
    
    public var humanExplanation: String {
        switch reasonType {
        case "profile_topic": return "Correspond à tes sujets suivis"
        case "profile_entity": return "Mentionne une entité d'intérêt"
        case "global_importance": return "Importance internationale majeure"
        case "discovery": return "Découverte suggérée"
        case "interaction_reinforcement": return "Basé sur tes lectures récentes"
        default: return "Sélectionné pour toi"
        }
    }
    
    enum CodingKeys: String, CodingKey {
        case reasonType = "reason_type"
        case contribution
        case weight
        case explanationKey = "explanation_key"
    }
}

public struct V2EventDetail: Codable, Sendable {
    public let event: V2EventCore
    public let summary: V2Summary?
    public let sources: [V2Source]
    
    public var asV2Event: V2Event {
        V2Event(
            eventId: event.id,
            canonicalTitle: event.canonicalTitle,
            lifecycle: event.lifecycle,
            lastActivityAt: event.lastActivityAt,
            summaryId: summary?.id,
            headline: summary?.headline,
            shortSummary: summary?.shortSummary,
            freshnessStatus: summary?.freshnessStatus,
            interestScore: nil,
            impactScore: nil,
            globalImportanceScore: nil,
            discoveryScore: nil,
            finalScore: nil,
            eligibilityId: nil,
            sources: sources,
            scoreReasons: nil,
            imageUrl: nil,
            saved: nil,
            liked: nil
        )
    }
}

public struct V2EventCore: Codable, Sendable {
    public let id: String
    public let canonicalTitle: String
    public let lifecycle: String
    public let lastActivityAt: String?
    
    enum CodingKeys: String, CodingKey {
        case id, lifecycle
        case canonicalTitle = "canonical_title"
        case lastActivityAt = "last_activity_at"
    }
}

public struct V2Summary: Codable, Sendable {
    public let id: String?
    public let headline: String
    public let shortSummary: String?
    public let detailSummary: String?
    public let freshnessStatus: String?
    public let versionNumber: Int?
    public let createdAt: String?
    public let articleBody: String?
    public let detailedStory: String?
    
    enum CodingKeys: String, CodingKey {
        case id
        case headline
        case shortSummary = "short_summary"
        case detailSummary = "detail_summary"
        case freshnessStatus = "freshness_status"
        case versionNumber = "version_number"
        case createdAt = "created_at"
        case articleBody = "article_body"
        case detailedStory = "detailed_story"
    }
}

public struct V2ClaimsResponse: Codable, Sendable {
    public let eventId: String
    public let claims: [V2Claim]
    
    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case claims
    }
}

public struct V2Claim: Codable, Identifiable, Sendable {
    public let id: String
    public let canonicalText: String
    public let status: String
    public let statusConfidence: Double?
    public let role: String?
    public let evidence: [V2Evidence]
    
    public var humanStatus: String {
        switch status.lowercased() {
        case "corroborated": return "Confirmé"
        case "uncertain": return "Incertain"
        case "disputed": return "Contesté"
        case "corrected": return "Corrigé"
        case "reported": return "Signalé"
        default: return "En cours d'analyse"
        }
    }
    
    public var statusIcon: String {
        switch status.lowercased() {
        case "corroborated": return "checkmark.seal.fill"
        case "uncertain": return "questionmark.circle.fill"
        case "disputed": return "arrow.triangle.swap"
        case "corrected": return "arrow.counterclockwise.circle.fill"
        default: return "newspaper.fill"
        }
    }
    
    public var statusColor: Color {
        switch status.lowercased() {
        case "corroborated": return .green
        case "uncertain": return .orange
        case "disputed": return .red
        case "corrected": return .blue
        default: return .secondary
        }
    }
    
    enum CodingKeys: String, CodingKey {
        case id, status, evidence, role
        case canonicalText = "canonical_text"
        case statusConfidence = "status_confidence"
    }
}

public struct V2Evidence: Codable, Identifiable, Sendable {
    public let id: String
    public let quotedText: String
    public let sourceURLSnapshot: String
    public let sourceName: String?
    public let sourceDomain: String?
    public let evidenceRole: String?
    public let independenceAssessment: String?
    
    public var displaySource: String {
        if let domain = sourceDomain, !domain.isEmpty {
            return domain.replacingOccurrences(of: "www.", with: "")
        }
        if let name = sourceName, !name.isEmpty {
            return name.replacingOccurrences(of: "rss_", with: "").capitalized
        }
        if let url = URL(string: sourceURLSnapshot), let host = url.host {
            return host.replacingOccurrences(of: "www.", with: "")
        }
        return "Source originale"
    }
    
    enum CodingKeys: String, CodingKey {
        case id
        case quotedText = "quoted_text"
        case sourceURLSnapshot = "source_url_snapshot"
        case sourceName = "source_name"
        case sourceDomain = "source_domain"
        case evidenceRole = "evidence_role"
        case independenceAssessment = "independence_assessment"
    }
}

public struct V2EventHistoryResponse: Codable, Sendable {
    public let eventId: String
    public let revisions: [V2EventRevision]
    public let summaries: [V2EventSummaryRevision]
    
    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case revisions, summaries
    }
}

public struct V2EventRevision: Codable, Identifiable, Sendable {
    public let id: String
    public let revisionNumber: Int
    public let reason: String?
    public let createdAt: String?
    
    enum CodingKeys: String, CodingKey {
        case id, reason
        case revisionNumber = "revision_number"
        case createdAt = "created_at"
    }
}

public struct V2EventSummaryRevision: Codable, Identifiable, Sendable {
    public let id: String
    public let versionNumber: Int
    public let headline: String
    public let shortSummary: String?
    public let createdAt: String?
    
    enum CodingKeys: String, CodingKey {
        case id, headline
        case versionNumber = "version_number"
        case shortSummary = "short_summary"
        case createdAt = "created_at"
    }
}

public struct V2SavedResponse: Codable, Sendable {
    public let userId: String
    public let items: [V2Event]
    
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case items
    }
}

public struct V2SearchResponse: Codable, Sendable {
    public let query: String
    public let items: [V2Event]
}

public struct V2ExploreResponse: Codable, Sendable {
    public let topSources: [V2TopSource]
    public let recentEvents: [V2Event]
    
    enum CodingKeys: String, CodingKey {
        case topSources = "top_sources"
        case recentEvents = "recent_events"
    }
}

public struct V2TopSource: Codable, Identifiable, Sendable {
    public var id: String { canonicalName }
    public let canonicalName: String
    public let canonicalDomain: String?
    public let eventCount: Int
    
    public var displayName: String {
        if let domain = canonicalDomain, !domain.isEmpty {
            return domain.replacingOccurrences(of: "www.", with: "")
        }
        return canonicalName.replacingOccurrences(of: "rss_", with: "").capitalized
    }
    
    enum CodingKeys: String, CodingKey {
        case canonicalName = "canonical_name"
        case canonicalDomain = "canonical_domain"
        case eventCount = "event_count"
    }
}
