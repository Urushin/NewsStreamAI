import Foundation

public struct PipelineStepEvent: Codable, Sendable {
    public let step_id: String
    public let step_title: String
    public let details: String
    public let progress_pct: Int
    public let news_count: Int?
    public let summaries_count: Int?
    public let status: String?
    public let task_label: String?
    public let elapsed_seconds: Double?
    
    enum CodingKeys: String, CodingKey {
        case step_id
        case step_title
        case details
        case progress_pct
        case progress
        case news_count
        case summaries_count
        case status
        case task_label
        case elapsed_seconds
    }
    
    public init(
        step_id: String,
        step_title: String,
        details: String,
        progress_pct: Int,
        news_count: Int? = nil,
        summaries_count: Int? = nil,
        status: String? = nil,
        task_label: String? = nil,
        elapsed_seconds: Double? = nil
    ) {
        self.step_id = step_id
        self.step_title = step_title
        self.details = details
        self.progress_pct = progress_pct
        self.news_count = news_count
        self.summaries_count = summaries_count
        self.status = status
        self.task_label = task_label
        self.elapsed_seconds = elapsed_seconds
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.step_id = try container.decode(String.self, forKey: .step_id)
        self.step_title = try container.decode(String.self, forKey: .step_title)
        self.details = try container.decode(String.self, forKey: .details)
        if let p = try? container.decode(Int.self, forKey: .progress_pct) {
            self.progress_pct = p
        } else if let p = try? container.decode(Int.self, forKey: .progress) {
            self.progress_pct = p
        } else {
            self.progress_pct = 0
        }
        self.news_count = try container.decodeIfPresent(Int.self, forKey: .news_count)
        self.summaries_count = try container.decodeIfPresent(Int.self, forKey: .summaries_count)
        self.status = try container.decodeIfPresent(String.self, forKey: .status)
        self.task_label = try container.decodeIfPresent(String.self, forKey: .task_label)
        self.elapsed_seconds = try container.decodeIfPresent(Double.self, forKey: .elapsed_seconds)
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(step_id, forKey: .step_id)
        try container.encode(step_title, forKey: .step_title)
        try container.encode(details, forKey: .details)
        try container.encode(progress_pct, forKey: .progress_pct)
        try container.encode(progress_pct, forKey: .progress)
        try container.encodeIfPresent(news_count, forKey: .news_count)
        try container.encodeIfPresent(summaries_count, forKey: .summaries_count)
        try container.encodeIfPresent(status, forKey: .status)
        try container.encodeIfPresent(task_label, forKey: .task_label)
        try container.encodeIfPresent(elapsed_seconds, forKey: .elapsed_seconds)
    }
    
    public var safeNewsCount: Int { news_count ?? 0 }
    public var safeSummariesCount: Int { summaries_count ?? 0 }
    public var safeStatus: String { status ?? "in_progress" }
    public var safeTaskLabel: String { task_label ?? "Traitement Cognitif" }
    public var safeElapsedSeconds: Double { elapsed_seconds ?? 0.0 }
}

public struct UserProfile: Codable, Sendable {
    public var username: String
    public var display_name: String?
    public var preferred_language: String
    public var min_score_threshold: Double
    public var webhook_url: String?
    public var interests: [String: Double]
    public var rejection_rules: [String]
    public var bio_markdown: String?
    
    public init(
        username: String = "default_user",
        display_name: String? = nil,
        preferred_language: String = Locale.current.language.languageCode?.identifier ?? "fr",
        min_score_threshold: Double = 0.65,
        webhook_url: String? = nil,
        interests: [String: Double] = [:],
        rejection_rules: [String] = [],
        bio_markdown: String? = nil
    ) {
        self.username = username
        self.display_name = display_name
        self.preferred_language = preferred_language
        self.min_score_threshold = min_score_threshold
        self.webhook_url = webhook_url
        self.interests = interests
        self.rejection_rules = rejection_rules
        self.bio_markdown = bio_markdown
    }
}
