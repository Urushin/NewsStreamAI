import SwiftUI

public struct AddTrackedEntitySheet: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @Environment(\.dismiss) private var dismiss
    
    @State private var selectedTab: Int = 0 // 0: Apps & Outils, 1: YouTube, 2: GitHub Repos
    @State private var inputQuery: String = ""
    @State private var isSubmitting: Bool = false
    @State private var isSearching: Bool = false
    @State private var statusMessage: String? = nil
    
    @State private var ytResults: [YouTubeSearchResult] = []
    @State private var ghResults: [GitHubSearchResult] = []
    @State private var searchTask: Task<Void, Never>? = nil
    
    private let popularApps = [
        "Instagram",
        "X",
        "Notion",
        "Google Gemini",
        "ChatGPT",
        "Figma",
        "Claude",
        "Slack",
        "WhatsApp",
        "Linear"
    ]
    
    private let popularTwitterAccounts = [
        "OpenAI",
        "sama",
        "elonmusk",
        "ylecun",
        "AnthropicAI",
        "karpathy",
        "MistralAI",
        "dr_cintas",
        "shanks_leaks"
    ]
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        NavigationStack {
            Form {
                // MARK: - 1. Type Selector
                Section(header: Text("Type d'élément à suivre")) {
                    Picker("Type", selection: $selectedTab) {
                        Label("Apps", systemImage: "app.badge").tag(0)
                        Label("YouTube", systemImage: "play.rectangle.fill").tag(1)
                        Label("GitHub", systemImage: "chevron.left.forwardslash.chevron.right").tag(2)
                        Label("Twitter/X", systemImage: "bubble.left.and.bubble.right.fill").tag(3)
                    }
                    .pickerStyle(.segmented)
                    .padding(.vertical, 4)
                    .onChange(of: selectedTab) {
                        inputQuery = ""
                        ytResults = []
                        ghResults = []
                        statusMessage = nil
                    }
                }
                
                // MARK: - 2. Search Field
                Section(
                    header: Text(sectionHeaderTitle),
                    footer: Text(sectionFooterDescription)
                ) {
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.secondary)
                            .font(.system(size: 13))
                        
                        TextField(textFieldPlaceholder, text: $inputQuery)
                            .font(AppTypography.mono(size: 14))
                            .platformAutocapitalizationNone()
                            .disableAutocorrection(true)
                            .onChange(of: inputQuery) { _, newVal in
                                performLiveSearch(query: newVal)
                            }
                        
                        if !inputQuery.isEmpty {
                            Button(action: {
                                inputQuery = ""
                                ytResults = []
                                ghResults = []
                            }) {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundColor(.secondary)
                                    .font(.system(size: 13))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    
                    if isSearching {
                        HStack {
                            Spacer()
                            ProgressView()
                                .scaleEffect(0.8)
                            Text("Recherche en direct...")
                                .font(AppTypography.meta(size: 11.5))
                                .foregroundColor(.secondary)
                            Spacer()
                        }
                        .padding(.vertical, 4)
                    }
                    
                    if let msg = statusMessage {
                        Text(msg)
                            .font(AppTypography.meta(size: 12))
                            .foregroundColor(msg.contains("✅") ? .green : .red)
                    }
                }
                
                // MARK: - 3. Live Results & Tracked Lists (YouTube & GitHub)
                if selectedTab == 1 {
                    if !ytResults.isEmpty {
                        Section(header: Text("Chaînes Détectées")) {
                            ForEach(ytResults) { ch in
                                Button(action: {
                                    addYouTubeChannel(ch)
                                }) {
                                    HStack(spacing: 12) {
                                        AsyncImage(url: URL(string: ch.thumbnail)) { phase in
                                            switch phase {
                                            case .success(let img):
                                                img
                                                    .resizable()
                                                    .aspectRatio(contentMode: .fill)
                                                    .frame(width: 34, height: 34)
                                                    .clipShape(Circle())
                                            default:
                                                Circle()
                                                    .fill(Color.red.opacity(0.15))
                                                    .frame(width: 34, height: 34)
                                                    .overlay(
                                                        Image(systemName: "play.rectangle.fill")
                                                            .foregroundColor(.red)
                                                            .font(.system(size: 14))
                                                    )
                                            }
                                        }
                                        
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(ch.title)
                                                .font(AppTypography.meta(size: 13.5))
                                                .fontWeight(.medium)
                                                .foregroundColor(.primary)
                                            Text(ch.handle)
                                                .font(AppTypography.mono(size: 11))
                                                .foregroundColor(.secondary)
                                        }
                                        
                                        Spacer()
                                        
                                        Image(systemName: "plus.circle.fill")
                                            .foregroundColor(.blue)
                                            .font(.system(size: 16))
                                    }
                                    .padding(.vertical, 3)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    
                    Section(header: Text("Chaînes Suivies (\(viewModel.trackedYouTubeChannels.count))")) {
                        if viewModel.trackedYouTubeChannels.isEmpty {
                            Text("Aucune chaîne YouTube suivie pour l'instant.")
                                .font(AppTypography.meta(size: 12))
                                .foregroundColor(.secondary)
                        } else {
                            ForEach(viewModel.trackedYouTubeChannels.indices, id: \.self) { idx in
                                let ch = viewModel.trackedYouTubeChannels[idx]
                                HStack {
                                    Image(systemName: "play.rectangle.fill")
                                        .foregroundColor(.red)
                                        .font(.system(size: 14))
                                    
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(ch["name"] ?? ch["handle"] ?? "Inconnu")
                                            .font(AppTypography.meta(size: 13.5))
                                            .fontWeight(.medium)
                                        if let h = ch["handle"] {
                                            Text(h)
                                                .font(AppTypography.mono(size: 11))
                                                .foregroundColor(.secondary)
                                        }
                                    }
                                    
                                    Spacer()
                                    
                                    Button(action: {
                                        Task {
                                            if let target = ch["id"] ?? ch["handle"] {
                                                _ = await viewModel.removeTrackedEntity(type: "youtube", target: target)
                                            }
                                        }
                                    }) {
                                        Image(systemName: "trash")
                                            .font(.system(size: 13))
                                            .foregroundColor(.red.opacity(0.85))
                                            .padding(6)
                                            .background(Color.red.opacity(0.08))
                                            .clipShape(Circle())
                                    }
                                    .buttonStyle(.plain)
                                }
                                .padding(.vertical, 2)
                            }
                        }
                    }
                } else if selectedTab == 2 {
                    if !ghResults.isEmpty {
                        Section(header: Text("Dépôts Détectés")) {
                            ForEach(ghResults) { repo in
                                Button(action: {
                                    addGitHubRepo(repo)
                                }) {
                                    HStack(spacing: 12) {
                                        if let av = repo.avatar_url, let avURL = URL(string: av) {
                                            AsyncImage(url: avURL) { phase in
                                                switch phase {
                                                case .success(let img):
                                                    img
                                                        .resizable()
                                                        .aspectRatio(contentMode: .fill)
                                                        .frame(width: 32, height: 32)
                                                        .cornerRadius(6)
                                                default:
                                                    RoundedRectangle(cornerRadius: 6)
                                                        .fill(Color.paperBorder.opacity(0.3))
                                                        .frame(width: 32, height: 32)
                                                }
                                            }
                                        } else {
                                            RoundedRectangle(cornerRadius: 6)
                                                .fill(Color.paperBorder.opacity(0.3))
                                                .frame(width: 32, height: 32)
                                                .overlay(
                                                    Image(systemName: "chevron.left.forwardslash.chevron.right")
                                                        .font(.system(size: 12))
                                                )
                                        }
                                        
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(repo.full_name)
                                                .font(AppTypography.mono(size: 13))
                                                .fontWeight(.semibold)
                                                .foregroundColor(.primary)
                                            
                                            if let desc = repo.description, !desc.isEmpty {
                                                Text(desc)
                                                    .font(AppTypography.meta(size: 11))
                                                    .foregroundColor(.secondary)
                                                    .lineLimit(1)
                                            }
                                            
                                            if let stars = repo.stars {
                                                HStack(spacing: 3) {
                                                    Image(systemName: "star.fill")
                                                        .font(.system(size: 9))
                                                        .foregroundColor(.orange)
                                                    Text("\(stars) stars")
                                                        .font(AppTypography.mono(size: 9.5))
                                                        .foregroundColor(.secondary)
                                                }
                                            }
                                        }
                                        
                                        Spacer()
                                        
                                        Image(systemName: "plus.circle.fill")
                                            .foregroundColor(.blue)
                                            .font(.system(size: 16))
                                    }
                                    .padding(.vertical, 3)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    
                    Section(header: Text("Dépôts Suivis (\(viewModel.trackedRepos.count))")) {
                        if viewModel.trackedRepos.isEmpty {
                            Text("Aucun dépôt GitHub suivi pour l'instant.")
                                .font(AppTypography.meta(size: 12))
                                .foregroundColor(.secondary)
                        } else {
                            ForEach(viewModel.trackedRepos, id: \.self) { repo in
                                HStack {
                                    Image(systemName: "chevron.left.forwardslash.chevron.right")
                                        .foregroundColor(.purple)
                                        .font(.system(size: 14))
                                    
                                    Text(repo)
                                        .font(AppTypography.mono(size: 13.5))
                                        .fontWeight(.medium)
                                    
                                    Spacer()
                                    
                                    Button(action: {
                                        Task {
                                            _ = await viewModel.removeTrackedEntity(type: "github", target: repo)
                                        }
                                    }) {
                                        Image(systemName: "trash")
                                            .font(.system(size: 13))
                                            .foregroundColor(.red.opacity(0.85))
                                            .padding(6)
                                            .background(Color.red.opacity(0.08))
                                            .clipShape(Circle())
                                    }
                                    .buttonStyle(.plain)
                                }
                                .padding(.vertical, 2)
                            }
                        }
                    }
                }
                
                // MARK: - 4. Tab 0: Suggestions 1-Tap & Currently Tracked Apps
                if selectedTab == 0 {
                    Section(header: Text("Suggestions Rapides (1-Tap pour Ajouter)")) {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(popularApps, id: \.self) { app in
                                    let isTracked = viewModel.trackedApps.contains(where: { $0.lowercased() == app.lowercased() })
                                    Button(action: {
                                        Task {
                                            if !isTracked {
                                                _ = await viewModel.addTrackedEntity(type: "app", target: app)
                                            }
                                        }
                                    }) {
                                        HStack(spacing: 5) {
                                            Image(systemName: isTracked ? "checkmark.circle.fill" : "plus.circle")
                                                .font(.system(size: 11))
                                                .foregroundColor(isTracked ? .green : .primary)
                                            Text(app)
                                                .font(AppTypography.mono(size: 11.5))
                                                .fontWeight(.medium)
                                        }
                                        .padding(.horizontal, 11)
                                        .padding(.vertical, 7)
                                        .background(isTracked ? Color.green.opacity(0.12) : Color.paperBorder.opacity(0.35))
                                        .foregroundColor(.primary)
                                        .cornerRadius(8)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .padding(.vertical, 3)
                        }
                    }
                    
                    // Direct submission if typed manually
                    if !inputQuery.trimmingCharacters(in: .whitespaces).isEmpty {
                        Button(action: {
                            submitManualEntity()
                        }) {
                            HStack {
                                Spacer()
                                if isSubmitting {
                                    ProgressView().scaleEffect(0.85)
                                } else {
                                    Text("Ajouter \"\(inputQuery)\" au suivi")
                                        .font(AppTypography.meta(size: 14))
                                        .fontWeight(.semibold)
                                }
                                Spacer()
                            }
                        }
                    }
                    
                    // List of Currently Tracked Apps with Direct Delete
                    Section(header: Text("Applications & Outils Suivis (\(viewModel.trackedApps.count))")) {
                        if viewModel.trackedApps.isEmpty {
                            Text("Aucune application suivie pour l'instant.")
                                .font(AppTypography.meta(size: 12))
                                .foregroundColor(.secondary)
                        } else {
                            ForEach(viewModel.trackedApps, id: \.self) { app in
                                HStack {
                                    Image(systemName: "app.badge.fill")
                                        .foregroundColor(.blue)
                                        .font(.system(size: 14))
                                    
                                    Text(app)
                                        .font(AppTypography.meta(size: 13.5))
                                        .fontWeight(.medium)
                                    
                                    Spacer()
                                    
                                    Button(action: {
                                        Task {
                                            _ = await viewModel.removeTrackedEntity(type: "app", target: app)
                                        }
                                    }) {
                                        Image(systemName: "trash")
                                            .font(.system(size: 13))
                                            .foregroundColor(.red.opacity(0.85))
                                            .padding(6)
                                            .background(Color.red.opacity(0.08))
                                            .clipShape(Circle())
                                    }
                                    .buttonStyle(.plain)
                                }
                                .padding(.vertical, 2)
                            }
                        }
                    }
                }
                
                // MARK: - 5. Tab 3: Twitter / X Accounts
                if selectedTab == 3 {
                    Section(header: Text("Suggestions Rapides (1-Tap)")) {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(popularTwitterAccounts, id: \.self) { acc in
                                    let handle = acc.replacingOccurrences(of: "@", with: "")
                                    let isTracked = viewModel.trackedTwitterAccounts.contains(where: { $0.lowercased() == handle.lowercased() })
                                    Button(action: {
                                        Task {
                                            if !isTracked {
                                                _ = await viewModel.addTrackedEntity(type: "twitter", target: handle)
                                            }
                                        }
                                    }) {
                                        HStack(spacing: 5) {
                                            Image(systemName: isTracked ? "checkmark.circle.fill" : "plus.circle")
                                                .font(.system(size: 11))
                                                .foregroundColor(isTracked ? .green : .primary)
                                            Text("@\(handle)")
                                                .font(AppTypography.mono(size: 11.5))
                                                .fontWeight(.medium)
                                        }
                                        .padding(.horizontal, 11)
                                        .padding(.vertical, 7)
                                        .background(isTracked ? Color.green.opacity(0.12) : Color.paperBorder.opacity(0.35))
                                        .foregroundColor(.primary)
                                        .cornerRadius(8)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .padding(.vertical, 3)
                        }
                    }
                    
                    if !inputQuery.trimmingCharacters(in: .whitespaces).isEmpty {
                        Button(action: {
                            submitManualEntity()
                        }) {
                            HStack {
                                Image(systemName: "plus.circle.fill")
                                    .foregroundColor(.blue)
                                Text("Ajouter \"@\(inputQuery.replacingOccurrences(of: "@", with: ""))\"")
                                    .font(AppTypography.mono(size: 13.5))
                                    .fontWeight(.semibold)
                                Spacer()
                                if isSubmitting {
                                    ProgressView().scaleEffect(0.8)
                                }
                            }
                        }
                        .disabled(isSubmitting)
                    }
                    
                    Section(header: Text("Comptes Surveillés (\(viewModel.trackedTwitterAccounts.count))")) {
                        if viewModel.trackedTwitterAccounts.isEmpty {
                            Text("Aucun compte Twitter/X suivi pour l'instant.")
                                .font(AppTypography.meta(size: 12))
                                .foregroundColor(.secondary)
                        } else {
                            ForEach(viewModel.trackedTwitterAccounts, id: \.self) { acc in
                                HStack {
                                    Image(systemName: "at")
                                        .foregroundColor(.blue)
                                        .font(.system(size: 14))
                                    
                                    Text(acc)
                                        .font(AppTypography.mono(size: 13.5))
                                        .fontWeight(.medium)
                                    
                                    Spacer()
                                    
                                    Button(action: {
                                        Task {
                                            _ = await viewModel.removeTrackedEntity(type: "twitter", target: acc)
                                        }
                                    }) {
                                        Image(systemName: "trash")
                                            .font(.system(size: 13))
                                            .foregroundColor(.red.opacity(0.85))
                                            .padding(6)
                                            .background(Color.red.opacity(0.08))
                                            .clipShape(Circle())
                                    }
                                    .buttonStyle(.plain)
                                }
                                .padding(.vertical, 2)
                            }
                        }
                    }
                }
            }
            .background(Color.paperBackground)
            .navigationTitle("Nouveau Suivi")
            .inlineNavigationBar()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Fermer") {
                        dismiss()
                    }
                }
            }
            .task {
                await viewModel.loadContentFeed()
            }
        }
    }
    
    private var sectionHeaderTitle: String {
        switch selectedTab {
        case 0: return "Rechercher une Application"
        case 1: return "Recherche Instantanée YouTube"
        case 2: return "Recherche Instantanée GitHub"
        default: return "Compte Twitter / X à Suivre"
        }
    }
    
    private var sectionFooterDescription: String {
        switch selectedTab {
        case 0:
            return "Saisissez n'importe quelle application (Instagram, Notion, X, Gemini, Figma...) pour recevoir ses releases avec synthèse IA."
        case 1:
            return "Recherche en direct : tapez le nom d'un créateur (ex: Marques, Lex, Underscore) ou un @handle."
        case 2:
            return "Recherche en direct : tapez le nom du projet open-source (ex: vllm, uv, swift, llama)."
        default:
            return "Les tweets de ces comptes sont filtrés par IA pour ne retenir que les annonces critiques et signaux à fort impact."
        }
    }
    
    private var textFieldPlaceholder: String {
        switch selectedTab {
        case 0: return "Nom de l'application..."
        case 1: return "Nom ou @handle de la chaîne..."
        case 2: return "Nom du dépôt (ex: astral-sh/uv)..."
        default: return "Handle Twitter (ex: @sama, @OpenAI)..."
        }
    }
    
    private func performLiveSearch(query: String) {
        searchTask?.cancel()
        let clean = query.trimmingCharacters(in: .whitespaces)
        guard clean.count >= 2 else {
            ytResults = []
            ghResults = []
            isSearching = false
            return
        }
        
        searchTask = Task {
            try? await Task.sleep(nanoseconds: 280_000_000)
            guard !Task.isCancelled else { return }
            
            await MainActor.run {
                isSearching = true
            }
            
            if selectedTab == 1 {
                let res = await viewModel.searchYouTubeChannels(query: clean)
                guard !Task.isCancelled else { return }
                await MainActor.run {
                    self.ytResults = res
                    self.isSearching = false
                }
            } else if selectedTab == 2 {
                let res = await viewModel.searchGitHubRepos(query: clean)
                guard !Task.isCancelled else { return }
                await MainActor.run {
                    self.ghResults = res
                    self.isSearching = false
                }
            } else {
                await MainActor.run {
                    self.isSearching = false
                }
            }
        }
    }
    
    private func addYouTubeChannel(_ ch: YouTubeSearchResult) {
        Task {
            isSubmitting = true
            let success = await viewModel.addTrackedEntity(type: "youtube", target: ch.id)
            isSubmitting = false
            if success {
                statusMessage = "✅ Chaîne \"\(ch.title)\" ajoutée !"
                try? await Task.sleep(nanoseconds: 600_000_000)
                dismiss()
            } else {
                statusMessage = "❌ Échec de l'ajout"
            }
        }
    }
    
    private func addGitHubRepo(_ repo: GitHubSearchResult) {
        Task {
            isSubmitting = true
            let success = await viewModel.addTrackedEntity(type: "github", target: repo.full_name)
            isSubmitting = false
            if success {
                statusMessage = "✅ Dépôt \"\(repo.full_name)\" ajouté !"
                try? await Task.sleep(nanoseconds: 600_000_000)
                dismiss()
            } else {
                statusMessage = "❌ Échec de l'ajout"
            }
        }
    }
    
    private func submitManualEntity() {
        let clean = inputQuery.trimmingCharacters(in: .whitespaces)
        guard !clean.isEmpty else { return }
        isSubmitting = true
        statusMessage = nil
        
        Task {
            let typeStr = selectedTab == 0 ? "app" : (selectedTab == 1 ? "youtube" : (selectedTab == 2 ? "github" : "twitter"))
            let targetClean = selectedTab == 3 ? clean.replacingOccurrences(of: "@", with: "") : clean
            let success = await viewModel.addTrackedEntity(type: typeStr, target: targetClean)
            isSubmitting = false
            if success {
                statusMessage = "✅ Ajouté avec succès !"
                inputQuery = ""
                try? await Task.sleep(nanoseconds: 600_000_000)
                if selectedTab != 0 && selectedTab != 3 {
                    dismiss()
                }
            } else {
                statusMessage = "❌ Impossible de trouver cet élément."
            }
        }
    }
}

