import Foundation

public enum SSEEvent: Sendable {
    case alert(AlertPayload)
    case pipelineStep(PipelineStepEvent)
    case pipelineLog(String)
    case connected
    case disconnected(String)
}

public final class SSEStreamManager: @unchecked Sendable {
    public static let shared = SSEStreamManager()
    
    private var isRunning = false
    private var currentTask: Task<Void, Never>?
    private var activeSession: URLSession?
    private let decoder = JSONDecoder()
    
    private init() {}
    
    public func startStream() -> AsyncStream<SSEEvent> {
        AsyncStream { continuation in
            self.currentTask?.cancel()
            self.isRunning = true
            
            self.currentTask = Task {
                var retryDelay: UInt64 = 1_000_000_000 // 1 sec
                
                while self.isRunning && !Task.isCancelled {
                    var hostsToTry = [APIClient.shared.baseURLString]
                    for candidate in APIClient.shared.candidateHosts where candidate != APIClient.shared.baseURLString {
                        hostsToTry.append(candidate)
                    }
                    
                    var connectedSuccessfully = false
                    
                    for host in hostsToTry {
                        if Task.isCancelled || !self.isRunning { break }
                        
                        guard let url = URL(string: "\(host)/api/stream/live") else {
                            continue
                        }
                        
                        var request = URLRequest(url: url)
                        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                        request.timeoutInterval = 86400 // Keep alive
                        
                        let sseSessionConfig = URLSessionConfiguration.default
                        sseSessionConfig.timeoutIntervalForRequest = 86400
                        sseSessionConfig.timeoutIntervalForResource = 86400
                        sseSessionConfig.waitsForConnectivity = false
                        let sseSession = URLSession(configuration: sseSessionConfig)
                        self.activeSession = sseSession
                        
                        do {
                            defer {
                                sseSession.invalidateAndCancel()
                            }
                            
                            let (bytes, response) = try await sseSession.bytes(for: request)
                            guard let httpRes = response as? HTTPURLResponse, (200...299).contains(httpRes.statusCode) else {
                                continue
                            }
                            
                            connectedSuccessfully = true
                            if APIClient.shared.baseURLString != host {
                                APIClient.shared.baseURLString = host
                            }
                            continuation.yield(.connected)
                            retryDelay = 1_000_000_000
                            
                            var currentEventName: String?
                            var dataBuffer = ""
                            
                            for try await line in bytes.lines {
                                if Task.isCancelled || !self.isRunning { break }
                                
                                let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                                
                                if trimmed.isEmpty {
                                    if let eventType = currentEventName, !dataBuffer.isEmpty {
                                        self.processEvent(type: eventType, rawData: dataBuffer, continuation: continuation)
                                    }
                                    currentEventName = nil
                                    dataBuffer = ""
                                    continue
                                }
                                
                                if trimmed.hasPrefix("event:") {
                                    currentEventName = trimmed.replacingOccurrences(of: "event:", with: "").trimmingCharacters(in: .whitespaces)
                                } else if trimmed.hasPrefix("data:") {
                                    let payload = trimmed.replacingOccurrences(of: "data:", with: "").trimmingCharacters(in: .whitespaces)
                                    if dataBuffer.isEmpty {
                                        dataBuffer = payload
                                    } else {
                                        dataBuffer += "\n" + payload
                                    }
                                }
                            }
                            
                            break
                        } catch {
                            continue
                        }
                    }
                    
                    if !connectedSuccessfully && !Task.isCancelled && self.isRunning {
                        continuation.yield(.disconnected("Reconnexion au flux direct..."))
                        try? await Task.sleep(nanoseconds: retryDelay)
                        retryDelay = min(retryDelay * 2, 6_000_000_000)
                    }
                }
            }
            
            continuation.onTermination = { [weak self] _ in
                self?.stopStream()
            }
        }
    }
    
    private func processEvent(type: String, rawData: String, continuation: AsyncStream<SSEEvent>.Continuation) {
        guard let data = rawData.data(using: .utf8) else { return }
        
        switch type {
        case "alert":
            if let alert = try? decoder.decode(AlertPayload.self, from: data) {
                // Notification locale immédiate avec le titre de la news uniquement si multi-source
                if alert.isMultiSource {
                    NotificationManager.shared.dispatchNewsNotification(
                        title: alert.push_title,
                        bullet: alert.bullet_points.first ?? "",
                        sourceCount: alert.sources.count,
                        category: alert.category
                    )
                }
                continuation.yield(.alert(alert))
            }
        case "pipeline_step":
            do {
                let step = try decoder.decode(PipelineStepEvent.self, from: data)
                continuation.yield(.pipelineStep(step))
            } catch {
                print("⚠️ SSE PipelineStep decoding error: \(error)")
            }
        case "pipeline_log":
            if let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let logMsg = dict["log"] as? String {
                continuation.yield(.pipelineLog(logMsg))
            } else {
                continuation.yield(.pipelineLog(rawData))
            }
        default:
            break
        }
    }
    
    public func stopStream() {
        isRunning = false
        currentTask?.cancel()
        currentTask = nil
        activeSession?.invalidateAndCancel()
        activeSession = nil
    }
}
