import Foundation
import UserNotifications

public final class NotificationManager: NSObject, @unchecked Sendable, UNUserNotificationCenterDelegate {
    public static let shared = NotificationManager()
    
    private override init() {
        super.init()
        UNUserNotificationCenter.current().delegate = self
    }
    
    public func requestAuthorization() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            if granted {
                print("✅ Notification authorization granted")
            } else if let error = error {
                print("❌ Notification error: \(error.localizedDescription)")
            }
        }
    }
    
    public func dispatchNewsNotification(title: String, bullet: String, sourceCount: Int, category: String?) {
        let content = UNMutableNotificationContent()
        content.title = title
        if let cat = category, !cat.isEmpty {
            content.subtitle = sourceCount >= 2 ? "🔴 Recoupé par \(sourceCount) rédactions • \(cat)" : "📰 \(cat)"
        } else {
            content.subtitle = sourceCount >= 2 ? "🔴 Recoupé par \(sourceCount) rédactions" : "📰 Nouvelle Actualité"
        }
        content.body = bullet.isEmpty ? title : bullet
        content.sound = .default
        
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 0.1, repeats: false)
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: trigger)
        
        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                print("Erreur dispatch notification: \(error.localizedDescription)")
            }
        }
    }
    
    public func dispatchMultiSourceAlertNotification(title: String, bullet: String, sourceCount: Int, category: String?) {
        dispatchNewsNotification(title: title, bullet: bullet, sourceCount: sourceCount, category: category)
    }
    
    // Display in-app banner even when app is active
    public func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }
}
