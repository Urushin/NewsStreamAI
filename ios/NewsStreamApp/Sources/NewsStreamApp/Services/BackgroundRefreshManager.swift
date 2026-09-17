import Foundation
import BackgroundTasks
import UserNotifications

public final class BackgroundRefreshManager: @unchecked Sendable {
    public static let shared = BackgroundRefreshManager()
    public static let taskIdentifier = "com.issam.mynewsai.refresh"
    
    private init() {}
    
    public func registerBackgroundTask() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.taskIdentifier,
            using: nil
        ) { task in
            guard let refreshTask = task as? BGAppRefreshTask else { return }
            self.handleAppRefresh(task: refreshTask)
        }
    }
    
    public func scheduleAppRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: Self.taskIdentifier)
        // Request execution in 20 minutes
        request.earliestBeginDate = Date(timeIntervalSinceNow: 20 * 60)
        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            print("Could not schedule BGAppRefresh: \(error)")
        }
    }
    
    private final class TaskBox: @unchecked Sendable {
        let task: BGAppRefreshTask
        init(_ task: BGAppRefreshTask) { self.task = task }
    }
    
    private func handleAppRefresh(task: BGAppRefreshTask) {
        // Reschedule next background task
        scheduleAppRefresh()
        let box = TaskBox(task)
        
        let work = Task {
            let articles = await AutonomousFeedEngine.shared.fetch24hCatchUp()
            let clusters = LocalClusterEngine.shared.cluster(articles: articles)
            
            var newAlerts: [AlertPayload] = []
            for c in clusters.prefix(10) {
                let alert = await DirectLLMClient.shared.synthesizeCluster(
                    cluster: c,
                    provider: .offline
                )
                newAlerts.append(alert)
            }
            
            if !newAlerts.isEmpty {
                let existing = LocalNewsStore.shared.loadAlerts()
                var combined = newAlerts
                for e in existing where !combined.contains(where: { $0.id == e.id }) {
                    combined.append(e)
                }
                LocalNewsStore.shared.saveAlerts(combined)
                
                // If top alert is multi-source, dispatch local notification
                if let top = newAlerts.first, top.isMultiSource {
                    self.dispatchLocalNotification(title: "🚨 Dépêche Recoupée", body: top.push_title)
                }
            }
            box.task.setTaskCompleted(success: true)
        }
        
        task.expirationHandler = {
            work.cancel()
            box.task.setTaskCompleted(success: false)
        }
    }
    
    private func dispatchLocalNotification(title: String, body: String) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        
        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil // Immediate
        )
        UNUserNotificationCenter.current().add(request)
    }
}
