import SwiftUI
import Combine

public enum AppTheme: String, CaseIterable, Identifiable, Sendable {
    case system = "Système"
    case light = "Clair"
    case dark = "Sombre"
    
    public var id: String { rawValue }
    
    public var colorScheme: ColorScheme? {
        switch self {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

public enum ThemePalette: String, CaseIterable, Identifiable, Sendable {
    case standard = "Papier Éditorial"
    case sepia = "Sépia d'Archive"
    case nightBlue = "Nuit Bleue"
    case contrastInk = "Encre & Contraste"
    
    public var id: String { rawValue }
    
    public var subtitle: String {
        switch self {
        case .standard: return "Papier clair et bleu MIZAN (#F6F8FB)"
        case .sepia: return "Chaleur de bibliothèque (#F5F0E6)"
        case .nightBlue: return "Bleu marine profond nocturne (#0D1B2A)"
        case .contrastInk: return "Blanc éclatant et encre noire pure"
        }
    }
}

public enum NewspaperStyle: String, CaseIterable, Identifiable, Sendable {
    case editorial = "Éditorial Classique"
    case modern = "Moderne Minimaliste"
    case financial = "Gazette Financière"
    case international = "Presse Diplomatique"
    
    public var id: String { rawValue }
    
    public var subtitle: String {
        switch self {
        case .editorial: return "Serif traditionnel façon Le Monde & New York Times"
        case .modern: return "Sans-serif épuré haute lisibilité"
        case .financial: return "Serif compact dense façon Financial Times"
        case .international: return "Serif classique géométrique type Bodoni"
        }
    }
}

@MainActor
public final class ThemeManager: ObservableObject {
    public static let shared = ThemeManager()
    
    private let themeKey = "mynews_selected_theme_v1"
    private let fontStyleKey = "mynews_selected_font_style_v1"
    private let paletteKey = "mynews_selected_palette_v1"
    
    @Published public var selectedTheme: AppTheme {
        didSet {
            UserDefaults.standard.set(selectedTheme.rawValue, forKey: themeKey)
        }
    }
    
    @Published public var selectedPalette: ThemePalette {
        didSet {
            UserDefaults.standard.set(selectedPalette.rawValue, forKey: paletteKey)
        }
    }
    
    @Published public var selectedNewspaperStyle: NewspaperStyle {
        didSet {
            UserDefaults.standard.set(selectedNewspaperStyle.rawValue, forKey: fontStyleKey)
        }
    }
    
    private init() {
        let savedThemeStr = UserDefaults.standard.string(forKey: themeKey) ?? AppTheme.system.rawValue
        self.selectedTheme = AppTheme(rawValue: savedThemeStr) ?? .system
        
        let savedPaletteStr = UserDefaults.standard.string(forKey: paletteKey) ?? ThemePalette.standard.rawValue
        self.selectedPalette = ThemePalette(rawValue: savedPaletteStr) ?? .standard
        
        let savedFontStr = UserDefaults.standard.string(forKey: fontStyleKey) ?? NewspaperStyle.modern.rawValue
        self.selectedNewspaperStyle = NewspaperStyle(rawValue: savedFontStr) ?? .modern
    }
    
    public var selectedColorScheme: ColorScheme? {
        selectedPalette == .nightBlue ? .dark : selectedTheme.colorScheme
    }
    
    public func headlineFont(size: CGFloat = 20) -> Font {
        switch selectedNewspaperStyle {
        case .editorial:
            return .system(size: size, weight: .bold, design: .serif)
        case .modern:
            return .system(size: size, weight: .bold, design: .default)
        case .financial:
            return .system(size: size, weight: .heavy, design: .serif)
        case .international:
            return .system(size: size, weight: .bold, design: .rounded)
        }
    }
    
    public func subheadFont(size: CGFloat = 16) -> Font {
        switch selectedNewspaperStyle {
        case .editorial:
            return .system(size: size, weight: .semibold, design: .serif)
        case .modern:
            return .system(size: size, weight: .semibold, design: .default)
        case .financial:
            return .system(size: size, weight: .semibold, design: .serif)
        case .international:
            return .system(size: size, weight: .semibold, design: .rounded)
        }
    }
    
    public func bodyFont(size: CGFloat = 15) -> Font {
        switch selectedNewspaperStyle {
        case .editorial:
            return .system(size: size, weight: .regular, design: .serif)
        case .modern:
            return .system(size: size, weight: .regular, design: .default)
        case .financial:
            return .system(size: size, weight: .regular, design: .serif)
        case .international:
            return .system(size: size, weight: .regular, design: .default)
        }
    }
    
    public var fontDesign: Font.Design {
        switch selectedNewspaperStyle {
        case .editorial, .financial:
            return .serif
        case .modern:
            return .default
        case .international:
            return .rounded
        }
    }
    
    public func font(size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: fontDesign)
    }
}
