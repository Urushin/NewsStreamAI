import Foundation

public final class LocalNewsStore: @unchecked Sendable {
    public static let shared = LocalNewsStore()
    private let fileManager = FileManager.default
    
    private var appSupportURL: URL {
        let urls = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask)
        let dir = urls[0].appendingPathComponent("NewsStreamAI", isDirectory: true)
        if !fileManager.fileExists(atPath: dir.path) {
            try? fileManager.createDirectory(at: dir, withIntermediateDirectories: true)
        }
        return dir
    }
    
    private var alertsFileURL: URL {
        appSupportURL.appendingPathComponent("cached_alerts.json")
    }
    
    private var bookmarksFileURL: URL {
        appSupportURL.appendingPathComponent("bookmarks.json")
    }
    
    private var v2EventsFileURL: URL {
        appSupportURL.appendingPathComponent("cached_v2_events.json")
    }
    
    private var v2SavedFileURL: URL {
        appSupportURL.appendingPathComponent("cached_v2_saved.json")
    }
    
    private init() {}
    
    // MARK: - Legacy V1 Support
    public func saveAlerts(_ alerts: [AlertPayload]) {
        do {
            let data = try JSONEncoder().encode(alerts)
            try data.write(to: alertsFileURL, options: .atomic)
        } catch {
            print("Failed to save local alerts: \(error)")
        }
    }
    
    public func loadAlerts() -> [AlertPayload] {
        guard fileManager.fileExists(atPath: alertsFileURL.path) else { return [] }
        do {
            let data = try Data(contentsOf: alertsFileURL)
            return try JSONDecoder().decode([AlertPayload].self, from: data)
        } catch {
            return []
        }
    }
    
    public func saveBookmarks(_ bookmarks: [AlertPayload]) {
        do {
            let data = try JSONEncoder().encode(bookmarks)
            try data.write(to: bookmarksFileURL, options: .atomic)
        } catch {
            print("Failed to save local bookmarks: \(error)")
        }
    }
    
    public func loadBookmarks() -> [AlertPayload] {
        guard fileManager.fileExists(atPath: bookmarksFileURL.path) else { return [] }
        do {
            let data = try Data(contentsOf: bookmarksFileURL)
            return try JSONDecoder().decode([AlertPayload].self, from: data)
        } catch {
            return []
        }
    }
    
    // MARK: - V2 Event Storage
    public func saveV2Events(_ events: [V2Event]) {
        do {
            let data = try JSONEncoder().encode(events)
            try data.write(to: v2EventsFileURL, options: .atomic)
        } catch {
            print("Failed to save local v2 events: \(error)")
        }
    }
    
    public func loadV2Events() -> [V2Event] {
        guard fileManager.fileExists(atPath: v2EventsFileURL.path) else { return [] }
        do {
            let data = try Data(contentsOf: v2EventsFileURL)
            return try JSONDecoder().decode([V2Event].self, from: data)
        } catch {
            return []
        }
    }
    
    public func saveV2Saved(_ events: [V2Event]) {
        do {
            let data = try JSONEncoder().encode(events)
            try data.write(to: v2SavedFileURL, options: .atomic)
        } catch {
            print("Failed to save local v2 saved events: \(error)")
        }
    }
    
    public func loadV2Saved() -> [V2Event] {
        guard fileManager.fileExists(atPath: v2SavedFileURL.path) else { return [] }
        do {
            let data = try Data(contentsOf: v2SavedFileURL)
            return try JSONDecoder().decode([V2Event].self, from: data)
        } catch {
            return []
        }
    }
}
