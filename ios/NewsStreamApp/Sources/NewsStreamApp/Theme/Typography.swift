import SwiftUI

#if canImport(UIKit)
import UIKit
#endif

@MainActor
public struct AppTypography {
    public static func editorialHeadline(size: CGFloat = 20) -> Font {
        ThemeManager.shared.headlineFont(size: size)
    }
    
    public static func editorialSubhead(size: CGFloat = 16) -> Font {
        ThemeManager.shared.subheadFont(size: size)
    }
    
    public static func editorialBody(size: CGFloat = 15) -> Font {
        ThemeManager.shared.bodyFont(size: size)
    }
    
    public static func meta(size: CGFloat = 12) -> Font {
        .system(size: size, weight: .medium, design: .default)
    }
    
    public static func mono(size: CGFloat = 11) -> Font {
        .system(size: size, weight: .semibold, design: .monospaced)
    }
}

public enum HapticImpactStyle: Sendable {
    case light, medium, heavy, soft, rigid
}

public enum HapticNotificationType: Sendable {
    case success, warning, error
}

@MainActor
public final class HapticsManager: Sendable {
    public static let shared = HapticsManager()
    private init() {}
    
    public func impact(_ style: HapticImpactStyle = .medium) {
        #if os(iOS)
        let uiStyle: UIImpactFeedbackGenerator.FeedbackStyle
        switch style {
        case .light: uiStyle = .light
        case .medium: uiStyle = .medium
        case .heavy: uiStyle = .heavy
        case .soft: uiStyle = .soft
        case .rigid: uiStyle = .rigid
        }
        let generator = UIImpactFeedbackGenerator(style: uiStyle)
        generator.prepare()
        generator.impactOccurred()
        #endif
    }
    
    public func notification(_ type: HapticNotificationType) {
        #if os(iOS)
        let uiType: UINotificationFeedbackGenerator.FeedbackType
        switch type {
        case .success: uiType = .success
        case .warning: uiType = .warning
        case .error: uiType = .error
        }
        let generator = UINotificationFeedbackGenerator()
        generator.prepare()
        generator.notificationOccurred(uiType)
        #endif
    }
}
