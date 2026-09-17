import Foundation

public enum LLMProvider: String, CaseIterable, Identifiable, Sendable {
    case mistral = "Mistral AI (Small - Rapide)"
    case groq = "Groq (Llama 3.3 70B - Ultra Rapide)"
    case openai = "OpenAI (GPT-4o mini)"
    case gemini = "Google Gemini (2.0 Flash)"
    case claude = "Claude (Haiku 3.5 - Anthropic)"
    case deepseek = "DeepSeek (Chat V3)"
    case offline = "Heuristique Hors-ligne (Zéro Clé)"
    
    public var id: String { rawValue }
    
    public var keychainKey: String {
        switch self {
        case .mistral: return "newsstream_api_key_mistral"
        case .groq: return "newsstream_api_key_groq"
        case .openai: return "newsstream_api_key_openai"
        case .gemini: return "newsstream_api_key_gemini"
        case .claude: return "newsstream_api_key_claude"
        case .deepseek: return "newsstream_api_key_deepseek"
        case .offline: return ""
        }
    }
    
    public var shortName: String {
        switch self {
        case .mistral: return "Mistral AI"
        case .groq: return "Groq"
        case .openai: return "OpenAI"
        case .gemini: return "Gemini"
        case .claude: return "Claude"
        case .deepseek: return "DeepSeek"
        case .offline: return "Hors-ligne"
        }
    }
}

public final class DirectLLMClient: Sendable {
    public static let shared = DirectLLMClient()
    private let session: URLSession
    
    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 12.0
        config.timeoutIntervalForResource = 15.0
        self.session = URLSession(configuration: config)
    }
    
    public func synthesizeCluster(
        cluster: LocalCluster,
        language: String = "fr",
        provider: LLMProvider
    ) async -> AlertPayload {
        let apiKey = KeychainHelper.shared.getString(forKey: provider.keychainKey) ?? ""
        
        // If no API key or offline mode requested, run heuristic engine
        if provider == .offline || apiKey.trimmingCharacters(in: .whitespaces).isEmpty {
            return fallbackHeuristicSynthesis(cluster: cluster)
        }
        
        do {
            switch provider {
            case .mistral:
                return try await callMistral(cluster: cluster, apiKey: apiKey, language: language)
            case .groq:
                return try await callGroq(cluster: cluster, apiKey: apiKey, language: language)
            case .openai:
                return try await callOpenAI(cluster: cluster, apiKey: apiKey, language: language)
            case .gemini:
                return try await callGemini(cluster: cluster, apiKey: apiKey, language: language)
            case .claude:
                return try await callClaude(cluster: cluster, apiKey: apiKey, language: language)
            case .deepseek:
                return try await callDeepSeek(cluster: cluster, apiKey: apiKey, language: language)
            case .offline:
                return fallbackHeuristicSynthesis(cluster: cluster)
            }
        } catch {
            return fallbackHeuristicSynthesis(cluster: cluster)
        }
    }
    
    // MARK: - Groq API (Sub-500ms response)
    private func callGroq(cluster: LocalCluster, apiKey: String, language: String) async throws -> AlertPayload {
        guard let url = URL(string: "https://api.groq.com/openai/v1/chat/completions") else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let promptText = buildPromptText(cluster: cluster, language: language)
        let body: [String: Any] = [
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.2,
            "response_format": ["type": "json_object"],
            "messages": [
                [
                    "role": "system",
                    "content": "Tu es un synthétiseur de presse d'investigation Slow-News. Tu réponds STRICTEMENT en JSON : {\"title\": \"Titre sobre\", \"bullets\": [\"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\"], \"impact\": \"critique\"|\"majeur\"|\"modéré\"}"
                ],
                [
                    "role": "user",
                    "content": promptText
                ]
            ]
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        
        return try parseLLMResponse(data: data, cluster: cluster)
    }
    
    // MARK: - OpenAI API
    private func callOpenAI(cluster: LocalCluster, apiKey: String, language: String) async throws -> AlertPayload {
        guard let url = URL(string: "https://api.openai.com/v1/chat/completions") else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let promptText = buildPromptText(cluster: cluster, language: language)
        let body: [String: Any] = [
            "model": "gpt-4o-mini",
            "temperature": 0.2,
            "response_format": ["type": "json_object"],
            "messages": [
                [
                    "role": "system",
                    "content": "Tu es un synthétiseur de presse d'investigation Slow-News. Tu réponds STRICTEMENT en JSON : {\"title\": \"Titre sobre\", \"bullets\": [\"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\"], \"impact\": \"critique\"|\"majeur\"|\"modéré\"}"
                ],
                [
                    "role": "user",
                    "content": promptText
                ]
            ]
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        
        return try parseLLMResponse(data: data, cluster: cluster)
    }
    
    // MARK: - Gemini API
    private func callGemini(cluster: LocalCluster, apiKey: String, language: String) async throws -> AlertPayload {
        let urlStr = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=\(apiKey)"
        guard let url = URL(string: urlStr) else { throw URLError(.badURL) }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let promptText = buildPromptText(cluster: cluster, language: language)
        let body: [String: Any] = [
            "contents": [
                ["parts": [["text": "Réponds STRICTEMENT en JSON pur : {\"title\": \"...\", \"bullets\": [\"...\", \"...\", \"...\"], \"impact\": \"...\"}\n\n\(promptText)"]]]
            ]
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let cands = json["candidates"] as? [[String: Any]],
           let content = cands.first?["content"] as? [String: Any],
           let parts = content["parts"] as? [[String: Any]],
           let text = parts.first?["text"] as? String {
            return parseRawJSONText(text, cluster: cluster)
        }
        
        throw URLError(.cannotParseResponse)
    }
    
    // MARK: - Mistral API (OpenAI-compatible)
    private func callMistral(cluster: LocalCluster, apiKey: String, language: String) async throws -> AlertPayload {
        guard let url = URL(string: "https://api.mistral.ai/v1/chat/completions") else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let promptText = buildPromptText(cluster: cluster, language: language)
        let body: [String: Any] = [
            "model": "mistral-small-latest",
            "temperature": 0.15,
            "response_format": ["type": "json_object"],
            "messages": [
                [
                    "role": "system",
                    "content": "Tu es un synthétiseur de presse d'investigation Slow-News. Tu réponds STRICTEMENT en JSON : {\"title\": \"Titre sobre\", \"bullets\": [\"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\"], \"impact\": \"critique\"|\"majeur\"|\"modéré\"}"
                ],
                [
                    "role": "user",
                    "content": promptText
                ]
            ]
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        
        return try parseLLMResponse(data: data, cluster: cluster)
    }
    
    // MARK: - Claude / Anthropic API
    private func callClaude(cluster: LocalCluster, apiKey: String, language: String) async throws -> AlertPayload {
        guard let url = URL(string: "https://api.anthropic.com/v1/messages") else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let promptText = buildPromptText(cluster: cluster, language: language)
        let body: [String: Any] = [
            "model": "claude-3-5-haiku-latest",
            "max_tokens": 600,
            "system": "Tu es un synthétiseur de presse d'investigation Slow-News. Tu réponds STRICTEMENT en JSON : {\"title\": \"Titre sobre\", \"bullets\": [\"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\"], \"impact\": \"critique\"|\"majeur\"|\"modéré\"}",
            "messages": [
                [
                    "role": "user",
                    "content": promptText
                ]
            ]
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        
        // Anthropic response: {"content": [{"type": "text", "text": "..."}], ...}
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let content = json["content"] as? [[String: Any]],
           let text = content.first?["text"] as? String {
            return parseRawJSONText(text, cluster: cluster)
        }
        
        throw URLError(.cannotParseResponse)
    }
    
    // MARK: - DeepSeek API (OpenAI-compatible)
    private func callDeepSeek(cluster: LocalCluster, apiKey: String, language: String) async throws -> AlertPayload {
        guard let url = URL(string: "https://api.deepseek.com/v1/chat/completions") else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let promptText = buildPromptText(cluster: cluster, language: language)
        let body: [String: Any] = [
            "model": "deepseek-chat",
            "temperature": 0.2,
            "response_format": ["type": "json_object"],
            "messages": [
                [
                    "role": "system",
                    "content": "Tu es un synthétiseur de presse d'investigation Slow-News. Tu réponds STRICTEMENT en JSON : {\"title\": \"Titre sobre\", \"bullets\": [\"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\", \"1 phrase avec mots en **gras**\"], \"impact\": \"critique\"|\"majeur\"|\"modéré\"}"
                ],
                [
                    "role": "user",
                    "content": promptText
                ]
            ]
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        
        return try parseLLMResponse(data: data, cluster: cluster)
    }
    
    private func buildPromptText(cluster: LocalCluster, language: String) -> String {
        var text = "Articles recoupés :\n"
        for a in cluster.articles.prefix(4) {
            text += "- [\(a.sourceName)] \(a.title) : \(a.content.prefix(300))\n"
        }
        text += """
        
        CONSIGNES STRICTES DE RÉDACTION EN FRANÇAIS :
        1. "title" : Titre direct, informatif et AFFIRMATIF en Français (ZÉRO point d'interrogation, zéro question, interdiction de copier à l'identique un titre source). Conserve les noms officiels d'œuvres, d'animes, de jeux ou d'entreprises entre guillemets.
        2. "bullets" : Exactement 3 puces factuelles et concises d'une phrase avec des éléments clés en **gras**.
        3. "detailed_story" : Récit d'investigation complet et approfondi en 2 paragraphes (150-250 mots) en Français détaillant les faits, les chiffres et les perspectives.
        
        Réponds STRICTEMENT au format JSON :
        {"title": "Titre affirmatif direct", "bullets": ["...", "...", "..."], "detailed_story": "Paragraphe 1...\\n\\nParagraphe 2...", "impact": "critique"|"majeur"|"modéré"}
        """
        return text
    }
    
    private func parseLLMResponse(data: Data, cluster: LocalCluster) throws -> AlertPayload {
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let choices = json["choices"] as? [[String: Any]],
              let msg = choices.first?["message"] as? [String: Any],
              let content = msg["content"] as? String else {
            throw URLError(.cannotParseResponse)
        }
        return parseRawJSONText(content, cluster: cluster)
    }
    
    private func sanitizeTitle(_ raw: String) -> String {
        var t = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        t = t.replacingOccurrences(of: "?", with: "")
        if t.lowercased().hasPrefix("pourquoi ") {
            t = "Les raisons de " + t.dropFirst(9)
        } else if t.lowercased().hasPrefix("comment ") {
            t = "Analyse de " + t.dropFirst(8)
        }
        return t.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    private func parseRawJSONText(_ text: String, cluster: LocalCluster) -> AlertPayload {
        var clean = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if clean.hasPrefix("```json") {
            clean = clean.replacingOccurrences(of: "```json", with: "").replacingOccurrences(of: "```", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
        }
        
        var title = sanitizeTitle(cluster.mainTitle)
        var bullets: [String] = []
        var detailedStory: String? = nil
        
        if let d = clean.data(using: .utf8),
           let obj = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
            if let t = obj["title"] as? String, !t.isEmpty { title = sanitizeTitle(t) }
            if let b = obj["bullets"] as? [String], !b.isEmpty { bullets = b }
            if let s = obj["detailed_story"] as? String, !s.isEmpty { detailedStory = s }
        }
        
        if bullets.isEmpty {
            bullets = [
                "Dépêche confirmée par **\(cluster.sourcesCount) source\(cluster.sourcesCount > 1 ? "s" : "")** indépendantes.",
                "Synthèse établie sur l'événement : **\(title)**.",
                "Développements suivis en direct par la rédaction."
            ]
        }
        
        if detailedStory == nil || detailedStory?.count ?? 0 < 50 {
            let p1 = cluster.articles.first?.content ?? title
            detailedStory = "\(p1)\n\nCette information fait l'objet d'un recoupement continu auprès des rédactions spécialisées."
        }
        
        // Deduplicate sources by domain/source name
        var seenSources = Set<String>()
        var alertSources: [AlertSource] = []
        for a in cluster.articles {
            let key = (a.domain.isEmpty ? a.sourceName : a.domain).lowercased()
            if !seenSources.contains(key) {
                seenSources.insert(key)
                alertSources.append(AlertSource(name: a.sourceName, domain: a.domain, url: a.url, tier: 1))
            }
        }
        
        return AlertPayload(
            alert_id: cluster.id,
            cluster_id: cluster.id,
            timestamp: ISO8601DateFormatter().string(from: Date()),
            push_title: title,
            bullet_points: bullets,
            sources: alertSources,
            velocity_score: cluster.isMultiSource ? 1.0 : 0.5,
            relevance_score: 0.85,
            hybrid_score: cluster.isMultiSource ? 0.80 : 0.60,
            reliability_label: cluster.isMultiSource ? "RECOUPÉ_MULTI_SOURCES" : "SOURCE_UNIQUE",
            category: cluster.category,
            context_explainer: nil,
            community_sentiment: nil,
            original_title: cluster.mainTitle,
            was_clickbait_enhanced: false,
            image_url: cluster.bestImageUrl,
            detailed_story: detailedStory,
            citations: nil
        )
    }
    
    // MARK: - Offline / Heuristic Synthesis
    public func fallbackHeuristicSynthesis(cluster: LocalCluster) -> AlertPayload {
        let title = sanitizeTitle(cluster.mainTitle)
        var bullets: [String] = []
        
        let first = cluster.articles.first?.content ?? title
        let parts = first.components(separatedBy: CharacterSet(charactersIn: ".!?\n"))
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { $0.count > 20 }
        
        if let p1 = parts.first {
            bullets.append(boldify(p1))
        } else {
            bullets.append("Événement majeur rapporté par **\(cluster.sourcesCount) rédaction\(cluster.sourcesCount > 1 ? "s" : "")**.")
        }
        
        if parts.count > 1 {
            bullets.append(boldify(parts[1]))
        } else if let secondArt = cluster.articles.dropFirst().first {
            bullets.append(boldify(secondArt.title))
        }
        
        if cluster.isMultiSource {
            let names = Set(cluster.articles.map { $0.sourceName }).joined(separator: ", ")
            bullets.append("Information recoupée de manière concordante entre **\(names)**.")
        } else {
            bullets.append("Détection continue active pour suivre les développements à venir.")
        }
        
        // Deduplicate sources by domain/source name
        var seenSources = Set<String>()
        var alertSources: [AlertSource] = []
        for a in cluster.articles {
            let key = (a.domain.isEmpty ? a.sourceName : a.domain).lowercased()
            if !seenSources.contains(key) {
                seenSources.insert(key)
                alertSources.append(AlertSource(name: a.sourceName, domain: a.domain, url: a.url, tier: 1))
            }
        }
        
        let detailedStory = "\(first)\n\nAnalyse factuelle et données complémentaires suivies en temps réel."
        
        return AlertPayload(
            alert_id: cluster.id,
            cluster_id: cluster.id,
            timestamp: ISO8601DateFormatter().string(from: Date()),
            push_title: title,
            bullet_points: bullets,
            sources: alertSources,
            velocity_score: cluster.isMultiSource ? 1.0 : 0.5,
            relevance_score: 0.82,
            hybrid_score: cluster.isMultiSource ? 0.78 : 0.58,
            reliability_label: cluster.isMultiSource ? "RECOUPÉ_MULTI_SOURCES" : "SOURCE_UNIQUE",
            category: cluster.category,
            context_explainer: nil,
            community_sentiment: nil,
            original_title: cluster.mainTitle,
            was_clickbait_enhanced: false,
            image_url: cluster.bestImageUrl,
            detailed_story: detailedStory,
            citations: nil
        )
    }
    
    private func boldify(_ text: String) -> String {
        var str = text
        if str.count > 120 {
            str = String(str.prefix(120)) + "..."
        }
        // Bold first proper noun or numbers
        if !str.contains("**") {
            let regex = try? NSRegularExpression(pattern: "([A-ZÀ-Ÿ][a-zà-ÿ]+|\\d+[%M€$]*)", options: [])
            if let match = regex?.firstMatch(in: str, options: [], range: NSRange(location: 0, length: str.utf16.count)) {
                if let r = Range(match.range, in: str) {
                    let word = str[r]
                    str.replaceSubrange(r, with: "**\(word)**")
                }
            }
        }
        return str
    }
}
