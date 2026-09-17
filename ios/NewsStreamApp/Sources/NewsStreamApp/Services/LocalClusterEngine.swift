import Foundation

public struct LocalCluster: Identifiable, Sendable {
    public let id: String
    public let mainTitle: String
    public let category: String
    public let articles: [RawArticle]
    public let sourcesCount: Int
    public let bestImageUrl: String?
    
    public var isMultiSource: Bool {
        sourcesCount >= 2
    }
}

public final class LocalClusterEngine: Sendable {
    public static let shared = LocalClusterEngine()
    private init() {}
    
    private let stopwords: Set<String> = [
        "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "ce", "cet", "cette", "ces",
        "dans", "sur", "avec", "pour", "par", "qui", "que", "quoi", "dont", "où", "est", "sont",
        "a", "ont", "et", "ou", "mais", "donc", "or", "ni", "car", "ne", "pas", "plus", "au", "aux",
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
        "from", "up", "about", "into", "over", "after", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would", "should", "could"
    ]
    
    public func cluster(articles: [RawArticle]) -> [LocalCluster] {
        var clusters: [LocalCluster] = []
        var assigned = Set<String>()
        
        for i in 0..<articles.count {
            let base = articles[i]
            if assigned.contains(base.id) { continue }
            
            var matched: [RawArticle] = [base]
            assigned.insert(base.id)
            let baseTokens = tokenize(base.title)
            
            for j in (i+1)..<articles.count {
                let candidate = articles[j]
                if assigned.contains(candidate.id) { continue }
                
                let candidateTokens = tokenize(candidate.title)
                let score = jaccardSimilarity(baseTokens, candidateTokens)
                
                if score >= 0.38 {
                    matched.append(candidate)
                    assigned.insert(candidate.id)
                }
            }
            
            let bestImg = matched.first(where: { $0.imageUrl != nil })?.imageUrl
            let distinctSources = Set(matched.map { $0.sourceName }).count
            
            clusters.append(LocalCluster(
                id: UUID().uuidString,
                mainTitle: base.title,
                category: base.category,
                articles: matched,
                sourcesCount: distinctSources,
                bestImageUrl: bestImg
            ))
        }
        
        return clusters
    }
    
    private func tokenize(_ text: String) -> Set<String> {
        let clean = text.lowercased()
            .components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { $0.count >= 3 && !stopwords.contains($0) }
        return Set(clean)
    }
    
    private func jaccardSimilarity(_ a: Set<String>, _ b: Set<String>) -> Double {
        guard !a.isEmpty && !b.isEmpty else { return 0.0 }
        let intersection = a.intersection(b).count
        let union = a.union(b).count
        return Double(intersection) / Double(union)
    }
}
