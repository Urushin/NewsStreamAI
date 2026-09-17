import SwiftUI

public struct ProfileSettingsView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var editingIdentity = false

    public init(viewModel: NewsStreamViewModel) { self.viewModel = viewModel }

    private var displayName: String {
        let name = viewModel.userProfile.display_name?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return name.isEmpty ? "Votre espace" : name
    }

    public var body: some View {
        NavigationStack {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 26) {
                    HStack(alignment: .center, spacing: 18) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 25).fill(Color.newsPrimary)
                            Text(viewModel.userProfile.display_name?.isEmpty == false ? String(displayName.prefix(1)).uppercased() : "M")
                                .font(.system(size: 36, weight: .regular, design: .serif)).foregroundStyle(.white)
                        }
                        .frame(width: 78, height: 78)
                        VStack(alignment: .leading, spacing: 7) {
                            Text(displayName).font(.system(size: 30, weight: .regular, design: .serif))
                            Text("Un regard sur le monde, à votre image.")
                                .font(.system(size: 12)).foregroundStyle(.secondary)
                            Button("Modifier mon profil") { editingIdentity = true }
                                .font(.system(size: 12, weight: .semibold))
                        }
                    }
                    .padding(.vertical, 8)
                    HStack(spacing: 12) {
                        profileMetric("\(viewModel.userProfile.interests.count)", label: "centres d'intérêt")
                        profileMetric("\(viewModel.entityWatchlist.count)", label: "sujets suivis")
                        profileMetric(viewModel.userProfile.preferred_language.uppercased(), label: "langue de lecture")
                    }
                    profileSection("Ce qui vous intéresse") {
                        NavigationLink(destination: InterestsSettingsSubView(viewModel: viewModel)) {
                            ProfileNavRow(icon: "sparkles", iconColor: .newsPrimary, title: "Mes centres d'intérêt", subtitle: "Gérez vos domaines et thématiques favoris")
                        }
                        NavigationLink(destination: PersonaEditorSubView(viewModel: viewModel)) {
                            ProfileNavRow(icon: "person.text.rectangle", iconColor: .purple, title: "Mieux me connaître", subtitle: "Votre contexte, vos projets et vos envies")
                        }
                        NavigationLink(destination: WatchlistSettingsSubView(viewModel: viewModel)) {
                            ProfileNavRow(icon: "scope", iconColor: .orange, title: "Mes sujets suivis", subtitle: "Personnes, entreprises et sujets à ne pas manquer")
                        }
                    }
                    profileSection("Votre expérience") {
                        NavigationLink(destination: AppearanceSettingsSubView()) {
                            ProfileNavRow(icon: "circle.lefthalf.filled", iconColor: .indigo, title: "Apparence", subtitle: "Thème, ambiance et typographie")
                        }
                        NavigationLink(destination: ReadingPreferencesSubView(viewModel: viewModel)) {
                            ProfileNavRow(icon: "textformat.size", iconColor: .pink, title: "Lecture & langue", subtitle: "L'information à votre rythme")
                        }
                        NavigationLink(destination: TelegramSettingsSubView(viewModel: viewModel)) {
                            ProfileNavRow(icon: "bell.badge", iconColor: .newsPrimary, title: "Alertes Telegram", subtitle: viewModel.telegramConfig?.configured == true ? "Votre connexion Telegram est configurée" : "Recevez les informations qui comptent")
                        }
                    }
                    profileSection("Sources & connexion") {
                        NavigationLink(destination: SourceHealthView(viewModel: viewModel)) {
                            ProfileNavRow(icon: "antenna.radiowaves.left.and.right", iconColor: .green, title: "Mes sources", subtitle: "Disponibilité, fiabilité et sources bloquées")
                        }
                        NavigationLink(destination: EngineSettingsSubView(viewModel: viewModel)) {
                            ProfileNavRow(icon: "network", iconColor: .teal, title: "Connexion & intelligence", subtitle: "Serveur, fournisseur IA et mode autonome")
                        }
                        NavigationLink(destination: MaintenanceSettingsSubView(viewModel: viewModel)) {
                            ProfileNavRow(icon: "slider.horizontal.3", iconColor: .secondary, title: "Réglages avancés", subtitle: "Collecte, diagnostics et maintenance")
                        }
                    }
                    BrandLogoView(size: 23).opacity(0.5).frame(maxWidth: .infinity).padding(.vertical, 8)
                }
                .padding(20)
            }
            .background(Color.paperBackground)
            .navigationTitle("Profil")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $editingIdentity) { MizanIdentityEditor(viewModel: viewModel) }
            .overlay(alignment: .bottom) {
                if let toast = viewModel.toastMessage {
                    Text(toast).font(.system(size: 12, weight: .medium))
                        .padding(14).background(.regularMaterial, in: Capsule()).padding()
                }
            }
        }
    }

    private func profileMetric(_ value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(value).font(.system(size: 23, weight: .semibold)).foregroundStyle(Color.newsPrimary)
            Text(label).font(.system(size: 10)).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(15).background(Color.paperCard, in: RoundedRectangle(cornerRadius: 19))
    }

    private func profileSection<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.system(size: 17, weight: .semibold)).padding(.horizontal, 3)
            VStack(spacing: 22, content: content)
                .buttonStyle(.plain)
                .padding(18).frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.paperCard, in: RoundedRectangle(cornerRadius: 23))
        }
    }
}

private struct MizanIdentityEditor: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var displayName = ""
    @State private var saving = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Votre prénom ou nom d'affichage", text: $displayName)
                        .textContentType(.name).autocorrectionDisabled()
                } header: { Text("Comment vous appeler ?") }
                footer: { Text("Ce nom personnalise votre profil sur iOS et sur le web.") }
                Section {
                    NavigationLink("Votre contexte et vos préférences") { PersonaEditorSubView(viewModel: viewModel) }
                }
            }
            .scrollContentBackground(.hidden).background(Color.paperBackground)
            .navigationTitle("Mon profil").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annuler") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(saving ? "Enregistrement…" : "Enregistrer") {
                        saving = true
                        Task {
                            viewModel.userProfile.display_name = displayName.trimmingCharacters(in: .whitespacesAndNewlines)
                            await viewModel.saveUserProfile()
                            saving = false
                            dismiss()
                        }
                    }.disabled(saving)
                }
            }
            .onAppear { displayName = viewModel.userProfile.display_name ?? "" }
        }
    }
}

// MARK: - Navigation Row Component
struct ProfileNavRow: View {
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String
    
    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 7)
                    .fill(iconColor.opacity(0.12))
                    .frame(width: 32, height: 32)
                Image(systemName: icon)
                    .foregroundColor(iconColor)
                    .font(.system(size: 14))
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(AppTypography.meta(size: 14))
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                Text(subtitle)
                    .font(AppTypography.meta(size: 11))
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}

// MARK: - Subpage 1: Watchlist & Fast-Track
public struct WatchlistSettingsSubView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var newEntityInput: String = ""
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        Form {
            Section(
                header: Text("Ajouter une entité"),
                footer: Text("Les entités de la watchlist déclenchent une alerte push prioritaire dès détection dans les flux mondiaux.")
            ) {
                HStack {
                    TextField("Ex: One Piece, Sam Altman, GPT-5...", text: $newEntityInput)
                        .autocorrectionDisabled()
                        .font(AppTypography.meta(size: 13))
                    
                    Button(action: {
                        let textToAdd = newEntityInput.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !textToAdd.isEmpty else { return }
                        newEntityInput = ""
                        Task {
                            await viewModel.addWatchlistEntity(textToAdd)
                        }
                    }) {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(.blue)
                            .font(.system(size: 20))
                    }
                    .disabled(newEntityInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                
                // Quick Suggestions
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        let suggestions = ["OpenAI", "Elon Musk", "One Piece", "Claude 3.5", "Sam Altman", "NVIDIA", "Jujutsu Kaisen", "Mistral AI", "Dragon Ball"]
                        ForEach(suggestions, id: \.self) { sug in
                            if !viewModel.entityWatchlist.contains(where: { $0.caseInsensitiveCompare(sug) == .orderedSame }) {
                                Button(action: {
                                    Task {
                                        await viewModel.addWatchlistEntity(sug)
                                    }
                                }) {
                                    HStack(spacing: 3) {
                                        Image(systemName: "plus")
                                            .font(.system(size: 9, weight: .bold))
                                        Text(sug)
                                            .font(AppTypography.meta(size: 11))
                                    }
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(Color.orange.opacity(0.12))
                                    .foregroundColor(.orange)
                                    .cornerRadius(8)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
            
            Section(header: Text("Entités sous surveillance (\(viewModel.entityWatchlist.count))")) {
                if viewModel.entityWatchlist.isEmpty {
                    Text("Aucune entité surveillée pour le moment.")
                        .foregroundColor(.secondary)
                        .font(AppTypography.meta(size: 12))
                } else {
                    ForEach(viewModel.entityWatchlist, id: \.self) { entity in
                        HStack {
                            Image(systemName: "tag.fill")
                                .foregroundColor(.orange.opacity(0.85))
                                .font(.system(size: 11))
                            Text(entity)
                                .font(AppTypography.meta(size: 13))
                            Spacer()
                            Button(action: {
                                Task {
                                    await viewModel.removeWatchlistEntity(entity)
                                }
                            }) {
                                Image(systemName: "trash")
                                    .foregroundColor(.red.opacity(0.7))
                                    .font(.system(size: 13))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
        .background(Color.paperBackground)
        .navigationTitle("Watchlist Fast-Track")
        .inlineNavigationBar()
    }
}

// MARK: - Subpage 2: Moteur & Autonomie
public struct EngineSettingsSubView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var serverURL: String = APIClient.shared.baseURLString
    @State private var apiKeyInput: String = ""
    @State private var isApiKeyVisible: Bool = false
    @State private var pingLatency: Double? = nil
    @State private var isServerOnline: Bool? = nil
    @State private var isTestingPing: Bool = false
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        Form {
            Section(
                header: Text("Mode Moteur"),
                footer: Text(viewModel.engineMode == .autonomous
                    ? "Mode Autonome : l'iPhone interroge directement les flux d'actualités et synthétise les dépêches sans dépendre du serveur PC."
                    : "Mode Serveur : l'application communique avec le serveur local hébergé sur votre Mac.")
            ) {
                Picker("Mode Moteur", selection: $viewModel.engineMode) {
                    ForEach(AppEngineMode.allCases) { mode in
                        Text(mode.rawValue).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.vertical, 2)
            }
            
            if viewModel.engineMode == .autonomous {
                Section(header: Text("Moteur d'Analyse IA")) {
                    Picker("Fournisseur IA", selection: $viewModel.selectedLLMProvider) {
                        ForEach(LLMProvider.allCases) { prov in
                            Text(prov.rawValue).tag(prov)
                        }
                    }
                    .onChange(of: viewModel.selectedLLMProvider) {
                        loadApiKeyForCurrentProvider()
                    }
                    
                    if viewModel.selectedLLMProvider != .offline {
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text("Clé API \(viewModel.selectedLLMProvider.shortName)")
                                    .font(AppTypography.meta(size: 12))
                                    .foregroundColor(.secondary)
                                Spacer()
                                Button(action: {
                                    isApiKeyVisible.toggle()
                                }) {
                                    Image(systemName: isApiKeyVisible ? "eye.slash" : "eye")
                                        .font(.system(size: 12))
                                        .foregroundColor(.secondary)
                                }
                                .buttonStyle(.plain)
                            }
                            
                            HStack {
                                if isApiKeyVisible {
                                    TextField("Clé API...", text: $apiKeyInput)
                                        .font(AppTypography.mono(size: 12))
                                        .textFieldStyle(.roundedBorder)
                                        .platformAutocapitalizationNone()
                                        .disableAutocorrection(true)
                                } else {
                                    SecureField("Clé API...", text: $apiKeyInput)
                                        .font(AppTypography.mono(size: 12))
                                        .textFieldStyle(.roundedBorder)
                                }
                                
                                Button("Enregistrer") {
                                    KeychainHelper.shared.setString(apiKeyInput, forKey: viewModel.selectedLLMProvider.keychainKey)
                                    viewModel.showToast("🔐 Clé API enregistrée dans le Keychain")
                                }
                                .font(AppTypography.meta(size: 11))
                                .buttonStyle(.bordered)
                            }
                        }
                        .padding(.vertical, 2)
                    }
                    
                    HStack(spacing: 8) {
                        Image(systemName: "bolt.badge.clock.fill")
                            .foregroundColor(.green)
                            .font(.system(size: 13))
                        Text("Tâche de fond iOS : Active (BGAppRefresh)")
                            .font(AppTypography.meta(size: 12))
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 2)
                }
            } else {
                Section(header: Text("Serveur PC Backend")) {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("URL Serveur")
                                .font(AppTypography.meta(size: 12))
                                .foregroundColor(.secondary)
                            Spacer()
                            if let online = isServerOnline {
                                HStack(spacing: 4) {
                                    Circle()
                                        .fill(online ? Color.green : Color.red)
                                        .frame(width: 7, height: 7)
                                    Text(online ? "En ligne (\(Int(pingLatency ?? 0)) ms)" : "Inaccessible")
                                        .font(AppTypography.mono(size: 10))
                                        .foregroundColor(online ? .green : .red)
                                }
                            }
                        }
                        
                        HStack {
                            TextField("http://192.168.1.189:8000", text: $serverURL)
                                .font(AppTypography.mono(size: 12))
                                .textFieldStyle(.roundedBorder)
                                .platformAutocapitalizationNone()
                                .disableAutocorrection(true)
                                .onChange(of: serverURL) { _, val in
                                    APIClient.shared.baseURLString = val
                                }
                            
                            Button(action: {
                                testServerPing()
                            }) {
                                if isTestingPing {
                                    ProgressView().scaleEffect(0.7)
                                } else {
                                    Text("Tester")
                                        .font(AppTypography.mono(size: 11.5))
                                }
                            }
                            .buttonStyle(.bordered)
                            .disabled(isTestingPing)
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
            
            Section(header: Text("Scan & Synchronisation")) {
                Button(action: {
                    Task {
                        await viewModel.trigger24hCatchUp()
                    }
                }) {
                    HStack {
                        Image(systemName: "clock.arrow.circlepath")
                            .foregroundColor(.orange)
                        Text(viewModel.engineMode == .autonomous ? "Lancer Rattrapage 24h Autonome" : "Lancer Scan 24h Serveur")
                            .font(AppTypography.meta(size: 13))
                            .fontWeight(.medium)
                        Spacer()
                        if viewModel.isCatchingUp {
                            ProgressView().scaleEffect(0.8)
                        }
                    }
                }
                .disabled(viewModel.isCatchingUp)
            }
        }
        .background(Color.paperBackground)
        .navigationTitle("Moteur & Autonomie")
        .inlineNavigationBar()
        .onAppear {
            loadApiKeyForCurrentProvider()
        }
    }
    
    private func testServerPing() {
        isTestingPing = true
        Task {
            let (online, ms) = await APIClient.shared.pingServer(host: serverURL)
            await MainActor.run {
                self.isServerOnline = online
                self.pingLatency = ms
                self.isTestingPing = false
                if online {
                    viewModel.showToast("🟢 Serveur connecté (\(Int(ms)) ms)")
                } else {
                    viewModel.showToast("🔴 Serveur injoignable : vérifiez l'IP")
                }
            }
        }
    }
    
    private func loadApiKeyForCurrentProvider() {
        apiKeyInput = KeychainHelper.shared.getString(forKey: viewModel.selectedLLMProvider.keychainKey) ?? ""
    }
}

// MARK: - Subpage 3: Apparence & Typographie
public struct AppearanceSettingsSubView: View {
    @ObservedObject private var themeManager = ThemeManager.shared
    
    public init() {}
    
    public var body: some View {
        Form {
            Section(header: Text("Mode d'affichage")) {
                Picker("Thème", selection: $themeManager.selectedTheme) {
                    ForEach(AppTheme.allCases) { theme in
                        Text(theme.rawValue).tag(theme)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.vertical, 2)
            }
            
            Section(
                header: Text("Palette Visuelle"),
                footer: Text("Personnalisez l'atmosphère de lecture avec nos teintes d'encre et de papier noble.")
            ) {
                Picker("Palette", selection: $themeManager.selectedPalette) {
                    ForEach(ThemePalette.allCases) { pal in
                        VStack(alignment: .leading) {
                            Text(pal.rawValue)
                            Text(pal.subtitle)
                                .font(.system(size: 10))
                                .foregroundColor(.secondary)
                        }
                        .tag(pal)
                    }
                }
            }
            
            Section(
                header: Text("Style de Journal"),
                footer: Text("Sélectionnez la typographie éditoriale pour les grands titres et le corps des dépêches.")
            ) {
                Picker("Style Typographique", selection: $themeManager.selectedNewspaperStyle) {
                    ForEach(NewspaperStyle.allCases) { style in
                        VStack(alignment: .leading) {
                            Text(style.rawValue)
                            Text(style.subtitle)
                                .font(.system(size: 10))
                                .foregroundColor(.secondary)
                        }
                        .tag(style)
                    }
                }
            }
        }
        .background(Color.paperBackground)
        .navigationTitle("Apparence")
        .inlineNavigationBar()
    }
}

// MARK: - Subpage 4: Préférences de Lecture
public struct ReadingPreferencesSubView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    
    public static let availableLanguages = [
        ("fr", "🇫🇷 Français"),
        ("en", "🇬🇧 English"),
        ("es", "🇪🇸 Español"),
        ("de", "🇩🇪 Deutsch"),
        ("it", "🇮🇹 Italiano"),
        ("pt", "🇵🇹 Português"),
        ("nl", "🇳🇱 Nederlands"),
        ("ru", "🇷🇺 Русский"),
        ("ar", "🇸🇦 العربية"),
        ("zh", "🇨🇳 中文"),
        ("ja", "🇯🇵 日本語")
    ]
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        Form {
            Section(
                header: Text("Langue de Synthèse"),
                footer: Text("Toutes les dépêches internationales (japonaises, anglaises, arabes...) seront automatiquement traduites et synthétisées dans cette langue.")
            ) {
                Picker("Langue", selection: $viewModel.userProfile.preferred_language) {
                    ForEach(Self.availableLanguages, id: \.0) { code, name in
                        Text(name).tag(code)
                    }
                }
                .onChange(of: viewModel.userProfile.preferred_language) {
                    Task {
                        await viewModel.saveUserProfile()
                    }
                }
            }
            
            Section(
                header: Text("Fenêtre Temporelle"),
                footer: Text("Filtre les actualités pour n'afficher que les événements publiés dans cette plage.")
            ) {
                Picker("Afficher les news des", selection: $viewModel.contentWindowHours) {
                    Text("1 heure").tag(1)
                    Text("6 heures").tag(6)
                    Text("12 heures").tag(12)
                    Text("24 heures").tag(24)
                    Text("48 heures").tag(48)
                    Text("3 jours").tag(72)
                    Text("7 jours").tag(168)
                    Text("Tout afficher").tag(0)
                }
                .onChange(of: viewModel.contentWindowHours) { _, _ in
                    viewModel.recomputeStreams()
                }
            }
        }
        .background(Color.paperBackground)
        .navigationTitle("Préférences de Lecture")
        .inlineNavigationBar()
    }
}

// MARK: - Subpage 5: Administration & Maintenance
public struct MaintenanceSettingsSubView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var serverURL: String = APIClient.shared.baseURLString
    @State private var showingPurgeConfirmation: Bool = false
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        Form {
            Section(header: Text("Génération & Ingestion")) {
                Button(action: {
                    Task {
                        await viewModel.triggerSimulation()
                    }
                }) {
                    HStack {
                        Image(systemName: "bolt.fill")
                            .foregroundColor(.blue)
                        Text("Simuler News Immédiates")
                            .font(AppTypography.meta(size: 13))
                        Spacer()
                        if viewModel.isSimulating {
                            ProgressView().scaleEffect(0.8)
                        }
                    }
                }
                .disabled(viewModel.isSimulating)
                
                Button(action: {
                    Task {
                        await viewModel.trigger24hCatchUp()
                    }
                }) {
                    HStack {
                        Image(systemName: "clock.arrow.circlepath")
                            .foregroundColor(.orange)
                        Text("Lancer Scan 24h Exhaustif")
                            .font(AppTypography.meta(size: 13))
                        Spacer()
                        if viewModel.isCatchingUp {
                            ProgressView().scaleEffect(0.8)
                        }
                    }
                }
                .disabled(viewModel.isCatchingUp)
            }
            
            Section(header: Text("Configuration Serveur Backend")) {
                HStack {
                    Text("Serveur")
                        .font(AppTypography.meta(size: 12))
                        .foregroundColor(.secondary)
                    TextField("URL Backend", text: $serverURL)
                        .font(AppTypography.mono(size: 12))
                        .textFieldStyle(.roundedBorder)
                        .platformAutocapitalizationNone()
                        .disableAutocorrection(true)
                    Button("OK") {
                        let clean = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
                        if !clean.isEmpty {
                            APIClient.shared.baseURLString = clean
                            viewModel.showToast("🌐 URL Serveur mise à jour")
                        }
                    }
                    .font(AppTypography.meta(size: 11))
                    .buttonStyle(.bordered)
                }
            }
            
            Section(header: Text("Zone de Danger")) {
                Button(role: .destructive, action: {
                    showingPurgeConfirmation = true
                }) {
                    HStack {
                        Image(systemName: "trash.fill")
                            .foregroundColor(.red)
                        Text("Purger toutes les actualités")
                            .font(AppTypography.meta(size: 13.5))
                            .fontWeight(.medium)
                            .foregroundColor(.red)
                    }
                }
            }
        }
        .background(Color.paperBackground)
        .navigationTitle("Système & Maintenance")
        .inlineNavigationBar()
        .alert("Purger toutes les news ?", isPresented: $showingPurgeConfirmation) {
            Button("Annuler", role: .cancel) { }
            Button("Purger définitivement", role: .destructive) {
                Task {
                    await viewModel.purgeAllAlerts()
                }
            }
        } message: {
            Text("Cette action efface l'historique complet des alertes et réinitialise tous les clusters sur le serveur et l'appareil.")
        }
    }
}
