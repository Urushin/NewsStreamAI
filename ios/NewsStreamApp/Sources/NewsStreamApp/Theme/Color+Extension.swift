import SwiftUI

#if canImport(UIKit)
import UIKit
#endif

public extension Color {
    // 🏛️ Dynamic Design System Colors based on selected palette & color scheme
    @MainActor
    static var paperBackground: Color {
        #if canImport(UIKit)
        let isDark = (ThemeManager.shared.selectedTheme == .dark) ||
            (ThemeManager.shared.selectedTheme == .system && UITraitCollection.current.userInterfaceStyle == .dark)
        #else
        let isDark = false
        #endif

        switch ThemeManager.shared.selectedPalette {
        case .nightBlue:
            return isDark ? Color(hex: "#09111E") : Color(hex: "#0D1B2A")
        case .sepia:
            return isDark ? Color(hex: "#1A1510") : Color(hex: "#F5F0E6")
        case .contrastInk:
            return isDark ? Color(hex: "#0B1220") : Color(hex: "#FFFEF5")
        case .standard:
            return isDark ? Color(hex: "#0B1220") : Color(hex: "#F6F8FB")
        }
    }
    
    @MainActor
    static var paperCard: Color {
        #if canImport(UIKit)
        let isDark = (ThemeManager.shared.selectedTheme == .dark) ||
            (ThemeManager.shared.selectedTheme == .system && UITraitCollection.current.userInterfaceStyle == .dark)
        #else
        let isDark = false
        #endif

        switch ThemeManager.shared.selectedPalette {
        case .nightBlue:
            return isDark ? Color(hex: "#111D2E") : Color(hex: "#1B2838")
        case .sepia:
            return isDark ? Color(hex: "#241D17") : Color(hex: "#FAF6EC")
        case .contrastInk:
            return isDark ? Color(hex: "#142033") : Color(hex: "#FFFFFF")
        case .standard:
            return isDark ? Color(hex: "#142033") : Color(hex: "#FFFFFF")
        }
    }
    
    @MainActor
    static var paperBorder: Color {
        #if canImport(UIKit)
        let isDark = (ThemeManager.shared.selectedTheme == .dark) ||
            (ThemeManager.shared.selectedTheme == .system && UITraitCollection.current.userInterfaceStyle == .dark)
        #else
        let isDark = false
        #endif

        switch ThemeManager.shared.selectedPalette {
        case .nightBlue:
            return isDark ? Color(hex: "#23354D") : Color(hex: "#2D4059")
        case .sepia:
            return isDark ? Color(hex: "#3D3227") : Color(hex: "#D4C9B0")
        case .contrastInk:
            return isDark ? Color(hex: "#27272A") : Color(hex: "#1A1A1A")
        case .standard:
            return isDark ? Color(hex: "#27272A") : Color(hex: "#E4E4E7")
        }
    }
    
    // Accents
    static let newsPrimary = Color(hex: "#386BFF")
    static let newsAccent = Color(hex: "#7C3AED")
    static let accentBlue = newsPrimary
    static let newsAmber = Color(hex: "#D97706")
    static let newsEmerald = Color(hex: "#059669")
    static let newsRose = Color(hex: "#E11D48")
    
    init(light: Color, dark: Color) {
        #if canImport(UIKit)
        self.init(UIColor { traitCollection in
            traitCollection.userInterfaceStyle == .dark ? UIColor(dark) : UIColor(light)
        })
        #else
        self = light
        #endif
    }
    
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
