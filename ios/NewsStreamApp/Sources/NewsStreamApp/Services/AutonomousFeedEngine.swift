import Foundation

public struct RawArticle: Identifiable, Sendable {
    public let id: String
    public let title: String
    public let url: String
    public let content: String
    public let sourceName: String
    public let domain: String
    public let category: String
    public let publishedAt: Date
    public let imageUrl: String?
    
    public init(
        id: String = UUID().uuidString,
        title: String,
        url: String,
        content: String,
        sourceName: String,
        domain: String,
        category: String,
        publishedAt: Date,
        imageUrl: String? = nil
    ) {
        self.id = id
        self.title = title
        self.url = url
        self.content = content
        self.sourceName = sourceName
        self.domain = domain
        self.category = category
        self.publishedAt = publishedAt
        self.imageUrl = imageUrl
    }
}

public final class AutonomousFeedEngine: Sendable {
    public static let shared = AutonomousFeedEngine()
    private let session: URLSession
    
    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10.0
        config.timeoutIntervalForResource = 15.0
        self.session = URLSession(configuration: config)
    }
    
    public func fetch24hCatchUp(
        progress: (@Sendable (Int, Int, String) -> Void)? = nil
    ) async -> [RawArticle] {
        let feeds = CuratedSources.feeds
        let cutoff = Date().addingTimeInterval(-86400) // 24 hours
        var allArticles: [RawArticle] = []
        var completed = 0
        
        await withTaskGroup(of: [RawArticle].self) { group in
            for feed in feeds {
                group.addTask {
                    let items = await self.fetchFeed(feed: feed, since: cutoff)
                    return items
                }
            }
            
            for await items in group {
                completed += 1
                allArticles.append(contentsOf: items)
                progress?(completed, feeds.count, "Flux analysé (\(completed)/\(feeds.count))")
            }
        }
        
        // Deduplicate by URL and normalized title
        var seen = Set<String>()
        var deduped: [RawArticle] = []
        for a in allArticles {
            let key = a.title.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
            if !seen.contains(key) && !seen.contains(a.url) {
                seen.insert(key)
                seen.insert(a.url)
                deduped.append(a)
            }
        }
        
        deduped.sort(keyPath: \.publishedAt, ascending: false)
        return deduped
    }
    
    private func fetchFeed(feed: VettedFeed, since: Date) async -> [RawArticle] {
        guard let url = URL(string: feed.url) else { return [] }
        var request = URLRequest(url: url)
        request.setValue("MyNewsAI/2.0 (Autonomous Mobile Engine; iOS)", forHTTPHeaderField: "User-Agent")
        
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
                return []
            }
            let parser = NativeRSSParser(data: data, source: feed)
            let items = parser.parse()
            return items.filter { $0.publishedAt >= since }
        } catch {
            return []
        }
    }
}

// MARK: - Native Fast XML Parser
private final class NativeRSSParser: NSObject, XMLParserDelegate {
    private let data: Data
    private let source: VettedFeed
    private var articles: [RawArticle] = []
    
    private var currentElement: String = ""
    private var currentTitle: String = ""
    private var currentLink: String = ""
    private var currentDesc: String = ""
    private var currentPubDateStr: String = ""
    private var currentImageUrl: String? = nil
    private var isInItem: Bool = false
    
    init(data: Data, source: VettedFeed) {
        self.data = data
        self.source = source
    }
    
    func parse() -> [RawArticle] {
        let parser = XMLParser(data: data)
        parser.delegate = self
        parser.parse()
        return articles
    }
    
    func parser(_ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?, qualifiedName qName: String?, attributes attributeDict: [String : String] = [:]) {
        currentElement = elementName.lowercased()
        if currentElement == "item" || currentElement == "entry" {
            isInItem = true
            currentTitle = ""
            currentLink = ""
            currentDesc = ""
            currentPubDateStr = ""
            currentImageUrl = nil
        }
        
        if isInItem {
            if currentElement == "enclosure", let url = attributeDict["url"], let type = attributeDict["type"], type.hasPrefix("image") {
                currentImageUrl = url
            } else if currentElement == "media:content", let url = attributeDict["url"] {
                currentImageUrl = url
            } else if currentElement == "media:thumbnail", let url = attributeDict["url"] {
                currentImageUrl = url
            } else if currentElement == "link", let href = attributeDict["href"], currentLink.isEmpty {
                currentLink = href
            }
        }
    }
    
    func parser(_ parser: XMLParser, foundCharacters string: String) {
        guard isInItem else { return }
        switch currentElement {
        case "title":
            currentTitle += string
        case "link":
            currentLink += string
        case "description", "content", "content:encoded", "summary":
            currentDesc += string
        case "pubdate", "published", "dc:date", "updated":
            currentPubDateStr += string
        default:
            break
        }
    }
    
    func parser(_ parser: XMLParser, foundCDATA CDATABlock: Data) {
        guard isInItem, let str = String(data: CDATABlock, encoding: .utf8) ?? String(data: CDATABlock, encoding: .isoLatin1) else { return }
        switch currentElement {
        case "title":
            currentTitle += str
        case "link":
            currentLink += str
        case "description", "content", "content:encoded", "summary":
            currentDesc += str
        case "pubdate", "published", "dc:date", "updated":
            currentPubDateStr += str
        default:
            break
        }
    }
    
    func parser(_ parser: XMLParser, didEndElement elementName: String, namespaceURI: String?, qualifiedName qName: String?) {
        let el = elementName.lowercased()
        if el == "item" || el == "entry" {
            isInItem = false
            let cleanTitle = currentTitle.trimmingCharacters(in: .whitespacesAndNewlines)
                .replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            let cleanLink = currentLink.trimmingCharacters(in: .whitespacesAndNewlines)
            let cleanDesc = currentDesc.trimmingCharacters(in: .whitespacesAndNewlines)
                .replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            
            // Extract image from HTML description if still nil
            var finalImg = currentImageUrl
            if finalImg == nil, let imgMatch = currentDesc.range(of: "<img[^>]+src=[\"']([^\"']+)[\"']", options: .regularExpression) {
                let sub = String(currentDesc[imgMatch])
                if let srcRange = sub.range(of: "src=[\"']([^\"']+)[\"']", options: .regularExpression) {
                    let val = String(sub[srcRange]).replacingOccurrences(of: "src=\"", with: "").replacingOccurrences(of: "src='", with: "").dropLast()
                    if val.hasPrefix("http") {
                        finalImg = String(val)
                    }
                }
            }
            
            let date = parseDate(currentPubDateStr)
            if !cleanTitle.isEmpty && cleanTitle.count > 10 {
                articles.append(RawArticle(
                    title: cleanTitle,
                    url: cleanLink.isEmpty ? UUID().uuidString : cleanLink,
                    content: cleanDesc.isEmpty ? cleanTitle : cleanDesc,
                    sourceName: source.name,
                    domain: source.domain,
                    category: source.category,
                    publishedAt: date,
                    imageUrl: finalImg
                ))
            }
        }
    }
    
    private func parseDate(_ str: String) -> Date {
        let trimmed = str.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return Date() }
        
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        
        let formats = [
            "EEE, dd MMM yyyy HH:mm:ss Z",
            "EEE, dd MMM yyyy HH:mm:ss zzz",
            "EEE, dd MMM yyyy HH:mm:ss z",
            "dd MMM yyyy HH:mm:ss Z",
            "dd MMM yyyy HH:mm:ss zzz",
            "yyyy-MM-dd'T'HH:mm:ssZ",
            "yyyy-MM-dd'T'HH:mm:ss.SSSZ",
            "yyyy-MM-dd'T'HH:mm:ss'Z'",
            "yyyy-MM-dd'T'HH:mm:ssZZZZZ",
            "yyyy-MM-dd HH:mm:ss"
        ]
        for f in formats {
            df.dateFormat = f
            if let d = df.date(from: trimmed) { return d }
        }
        if let d = ISO8601DateFormatter().date(from: trimmed) {
            return d
        }
        return Date()
    }
}

private extension Array {
    mutating func sort<T: Comparable>(keyPath: KeyPath<Element, T>, ascending: Bool = true) {
        self.sort { a, b in
            ascending ? a[keyPath: keyPath] < b[keyPath: keyPath] : a[keyPath: keyPath] > b[keyPath: keyPath]
        }
    }
}
