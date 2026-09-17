import SwiftUI

extension Notification.Name {
    static let mizanSavedChanged = Notification.Name("mizan.saved.changed")
}

@MainActor
private func publishSavedState(_ event: V2Event, saved: Bool) {
    var cached = LocalNewsStore.shared.loadV2Saved().filter { $0.eventId != event.eventId }
    if saved { cached.insert(event, at: 0) }
    LocalNewsStore.shared.saveV2Saved(cached)
    NotificationCenter.default.post(name: .mizanSavedChanged, object: event.eventId, userInfo: ["saved": saved])
}

func cleanMarkdownKey(_ text: String) -> LocalizedStringKey {
    var s = text.trimmingCharacters(in: .whitespacesAndNewlines)
    s = s.replacingOccurrences(of: "^[•\\-\\s]+", with: "", options: .regularExpression)
    s = s.replacingOccurrences(of: "^\\*\\*(?:Faits confirmés|Recoupement éditorial|Recoupement editorial|Suivi éditorial|suivi editorial|Couverture source)\\*\\*\\s*:\\s*", with: "", options: [.regularExpression, .caseInsensitive])
    s = s.replacingOccurrences(of: "\\b(?:Faits confirmés|Recoupement éditorial|Recoupement editorial|Suivi éditorial|suivi editorial|Couverture source)\\b\\s*:?\\s*", with: "", options: [.regularExpression, .caseInsensitive])
    s = s.replacingOccurrences(of: "\\*+(?:Politico|rss_[a-zA-Z0-9_]+|Bloomberg|The Guardian)\\*+\\s*:?\\s*", with: "", options: [.regularExpression, .caseInsensitive])
    s = s.replacingOccurrences(of: "\\brss_[a-zA-Z0-9_]+\\b", with: "", options: .regularExpression)
    s = s.replacingOccurrences(of: "^\\*([A-Za-z0-9_\\-\\s]+)\\*\\*", with: "**$1**", options: .regularExpression)

    let asteriskCount = s.filter { $0 == "*" }.count
    if asteriskCount % 2 != 0 {
        s += "*"
    }
    return LocalizedStringKey(s)
}

public struct V2EventFeedView: View {
    public var isActive: Bool
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var events: [V2Event] = []
    @State private var pendingEvents: [V2Event] = []
    @State private var savedEventIds: Set<String> = []
    @State private var likedEventIds: Set<String> = []
    @State private var likingIds: Set<String> = []
    @State private var savingIds: Set<String> = []
    @State private var seenIds: Set<String> = []
    @State private var rejectedIds: Set<String> = []
    @State private var isLoading = true
    @State private var isRefreshing = false
    @State private var errorMessage: String?
    @State private var lastUpdated: Date?
    @State private var selectedEvent: V2Event?
    @State private var whyEvent: V2Event?
    @State private var showingSearch = false
    @State private var showingAskFlux = false
    @State private var selectedFilter = "Pour vous"
    @State private var nextOffset: Int?
    @State private var hasMore = false
    @State private var loadingMore = false
    @AppStorage("mizan_feed_view_mode") private var viewMode: String = "deck"
    @AppStorage("mizan_compact_feed") private var compact = false
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    public init(viewModel: NewsStreamViewModel? = nil, isActive: Bool = true) {
        self.viewModel = viewModel ?? NewsStreamViewModel()
        self.isActive = isActive
    }

    private var visibleEvents: [V2Event] {
        let visible = events.filter { !rejectedIds.contains($0.eventId) }
        switch selectedFilter {
        case "Récents": return visible.sorted { ($0.publishedAt ?? "") > ($1.publishedAt ?? "") }
        case "Multi-sources": return visible.filter { $0.sources.count > 1 }
        default: return visible
        }
    }

    public var body: some View {
        NavigationStack {
            ZStack {
                Color.paperBackground.ignoresSafeArea()

                if isLoading && events.isEmpty {
                    feedSkeleton.padding(20)
                } else if visibleEvents.isEmpty {
                    ContentUnavailableView {
                        Label(events.isEmpty ? "Vos news se préparent" : "Aucune actualité ici", systemImage: "sparkles")
                    } description: {
                        Text(events.isEmpty ? "Vos sujets, vos sources, vos news. Actualisez pour retrouver les dernières informations." : "Choisissez un autre filtre pour continuer votre lecture.")
                    } actions: {
                        Button("Actualiser") { Task { await refreshFeed() } }
                            .buttonStyle(.borderedProminent)
                    }
                    .padding(.vertical, 24)
                } else {
                    VStack(spacing: 0) {
                        editorialHeader
                        modeAndFilterBar

                        if viewMode == "deck" {
                            // MARK: - SOLO TWEET DECK MODE (1 news per screen, vertical paging)
                            GeometryReader { geo in
                                ScrollView(.vertical, showsIndicators: false) {
                                    LazyVStack(spacing: 0) {
                                        ForEach(Array(visibleEvents.enumerated()), id: \.element.eventId) { index, event in
                                            V2SoloTweetCardView(
                                                event: event,
                                                isLiked: likedEventIds.contains(event.eventId),
                                                isSaved: savedEventIds.contains(event.eventId),
                                                onOpenDetail: { selectedEvent = event },
                                                onToggleSave: { toggleSave(event) },
                                                onLike: { toggleLike(event) },
                                                onDislike: { reject(event) },
                                                onShowWhy: { whyEvent = event }
                                            )
                                            .frame(width: geo.size.width, height: max(320, geo.size.height))
                                            .onAppear {
                                                recordImpression(event)
                                                if index >= visibleEvents.count - 3 && hasMore && !loadingMore {
                                                    Task { await loadMore() }
                                                }
                                            }
                                        }
                                    }
                                    .scrollTargetLayout()
                                }
                                .scrollTargetBehavior(.paging)
                                .refreshable { await refreshFeed() }
                            }
                        } else {
                            // MARK: - CONTINUOUS FEED / LIST MODE
                            ScrollViewReader { proxy in
                                ScrollView(showsIndicators: false) {
                                    LazyVStack(alignment: .leading, spacing: 20) {
                                        Color.clear.frame(height: 1).id("feed-top")
                                        if let errorMessage {
                                    HStack(alignment: .top, spacing: 10) {
                                        Image(systemName: "wifi.exclamationmark").foregroundStyle(Color.newsAmber)
                                        Text(errorMessage).font(.system(size: 13)).foregroundStyle(.secondary)
                                        Spacer(minLength: 0)
                                        Button("Réessayer") { Task { await refreshFeed() } }
                                            .font(.system(size: 12, weight: .semibold))
                                    }
                                    .padding(14)
                                    .background(Color.paperCard, in: RoundedRectangle(cornerRadius: 16))
                                }
                                if !pendingEvents.isEmpty {
                                    Button {
                                        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.25)) {
                                            events = pendingEvents
                                            pendingEvents = []
                                            proxy.scrollTo("feed-top", anchor: .top)
                                        }
                                        LocalNewsStore.shared.saveV2Events(events)
                                    } label: {
                                        Label("De nouvelles informations vous attendent", systemImage: "arrow.up")
                                            .font(.system(size: 13, weight: .semibold))
                                            .frame(maxWidth: .infinity).padding(14)
                                            .foregroundStyle(.white)
                                            .background(Color.newsPrimary, in: Capsule())
                                    }
                                    .buttonStyle(.plain)
                                }
                                ForEach(Array(visibleEvents.enumerated()), id: \.element.eventId) { index, event in
                                    V2TwitterNewsCardView(
                                        event: event,
                                        isLiked: likedEventIds.contains(event.eventId),
                                        isSaved: savedEventIds.contains(event.eventId),
                                        isFeatured: index == 0 && selectedFilter == "Pour vous",
                                        compact: compact,
                                        onOpenDetail: { selectedEvent = event },
                                        onToggleSave: { toggleSave(event) },
                                        onLike: { toggleLike(event) },
                                        onDislike: { reject(event) },
                                        onShowWhy: { whyEvent = event }
                                    )
                                    .disabled(savingIds.contains(event.eventId))
                                    .onAppear { recordImpression(event) }
                                    .transition(.opacity)
                                }
                                if hasMore {
                                    Button {
                                        Task { await loadMore() }
                                    } label: {
                                        HStack(spacing: 10) {
                                            if loadingMore { ProgressView() }
                                            Text(loadingMore ? "Chargement…" : "Plus de news")
                                            Image(systemName: "arrow.down")
                                        }
                                        .font(.system(size: 14, weight: .semibold))
                                        .frame(maxWidth: .infinity).padding(20)
                                    }
                                    .disabled(loadingMore)
                                } else {
                                    VStack(spacing: 7) {
                                        Image(systemName: "checkmark.circle").foregroundStyle(Color.newsPrimary)
                                        Text("Vous avez parcouru votre sélection.")
                                            .font(.system(size: 13, weight: .medium))
                                        Text("Vos news s'enrichissent au rythme de l'actualité.")
                                            .font(.system(size: 12)).foregroundStyle(.secondary)
                                    }
                                    .frame(maxWidth: .infinity).padding(.vertical, 30)
                                }
                            }
                            .padding(.horizontal, 18)
                            .padding(.bottom, 12)
                        }
                        .refreshable { await refreshFeed() }
                    }
                }
            }
        }
    }
    .safeAreaInset(edge: .top, spacing: 0) {
        if (viewMode == "deck" || events.isEmpty), let errorMessage {
            HStack {
                Label(errorMessage, systemImage: "wifi.exclamationmark")
                    .font(.system(size: 12)).foregroundStyle(.secondary)
                Button("Réessayer") { Task { await refreshFeed() } }.font(.system(size: 12, weight: .semibold))
            }.padding(12).background(Color.paperCard)
        }
        if viewMode == "deck", !pendingEvents.isEmpty {
            Button {
                events = pendingEvents
                pendingEvents = []
                LocalNewsStore.shared.saveV2Events(events)
            } label: {
                Label("De nouvelles informations vous attendent", systemImage: "arrow.up")
                    .font(.system(size: 12, weight: .semibold)).padding(11).frame(maxWidth: .infinity)
            }.background(Color.newsPrimary.opacity(0.08))
        }
    }
    .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    HStack(spacing: 8) {
                        BrandLogoView(size: 28)
                        if viewMode == "deck" && isRefreshing {
                            ProgressView().controlSize(.mini)
                        }
                    }
                }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button { showingAskFlux = true } label: {
                        Image(systemName: "sparkles").font(.system(size: 17))
                    }
                    .accessibilityLabel("Demander au Flux")

                    Button { showingSearch = true } label: {
                        Image(systemName: "magnifyingglass").font(.system(size: 17))
                    }
                    .accessibilityLabel("Rechercher une actualité")

                    Menu {
                        Picker("Affichage", selection: $viewMode) {
                            Label("1 par écran (Solo)", systemImage: "rectangle.portrait").tag("deck")
                            Label("News en continu (Liste)", systemImage: "list.bullet").tag("list")
                        }
                        Toggle("Lecture compacte", isOn: $compact)
                        Button("Actualiser les news", systemImage: "arrow.clockwise") {
                            Task { await refreshFeed() }
                        }
                    } label: {
                        Image(systemName: viewMode == "deck" ? "rectangle.portrait" : "list.bullet")
                            .font(.system(size: 16))
                    }
                    .accessibilityLabel("Mode d'affichage")
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(item: $selectedEvent) { V2EventDetailView(event: $0) }
            .sheet(item: $whyEvent) {
                WhyAmISeeingThisSheet(event: $0).presentationDetents([.medium, .large])
            }
            .sheet(isPresented: $showingSearch) { V2ExploreView() }
            .sheet(isPresented: $showingAskFlux) { AskFluxSheetView(viewModel: viewModel) }
            .task(id: isActive && scenePhase == .active) {
                guard isActive && scenePhase == .active else { return }
                if events.isEmpty { await loadInitialFeed() }
                while !Task.isCancelled {
                    do { try await Task.sleep(for: .seconds(60)) } catch { return }
                    guard !Task.isCancelled else { return }
                    await checkForUpdates()
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .mizanSavedChanged)) { notification in
                guard let id = notification.object as? String,
                      let saved = notification.userInfo?["saved"] as? Bool else { return }
                if saved { savedEventIds.insert(id) } else { savedEventIds.remove(id) }
            }
        }
    }

    private var editorialHeader: some View {
        HStack(spacing: 6) {
            Text(Date.now.formatted(.dateTime.weekday(.wide).day().month(.wide)).uppercased())
                .tracking(1.4)
            Spacer()
            if isRefreshing { ProgressView().controlSize(.mini) }
            else if let lastUpdated {
                Circle().fill(errorMessage == nil ? Color.newsEmerald : Color.newsAmber).frame(width: 5, height: 5)
                Text(lastUpdated, style: .time)
            }
        }
        .font(.system(size: 11, weight: .semibold))
        .foregroundStyle(.secondary)
        .padding(.horizontal, 18)
        .padding(.top, 8)
        .padding(.bottom, 6)
    }

    private var modeAndFilterBar: some View {
        HStack(spacing: 8) {
            filterBar

            Picker("Affichage", selection: $viewMode) {
                Label("Solo", systemImage: "rectangle.portrait").tag("deck")
                Label("Fil", systemImage: "list.bullet").tag("list")
            }
            .pickerStyle(.segmented)
            .frame(width: 135)
        }
        .padding(.horizontal, 16)
        .padding(.bottom, 6)
    }

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(["Pour vous", "Récents", "Multi-sources"], id: \.self) { filter in
                    Button {
                        guard selectedFilter != filter else { return }
                        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.2)) { selectedFilter = filter }
                        Task { await refreshFeed() }
                    } label: {
                        HStack(spacing: 6) {
                            if filter == "Pour vous" { Image(systemName: "sparkles") }
                            Text(filter)
                        }
                        .font(.system(size: 13, weight: .semibold))
                        .padding(.horizontal, 14).padding(.vertical, 8)
                        .foregroundStyle(selectedFilter == filter ? Color.white : Color.secondary)
                        .background(selectedFilter == filter ? Color.newsPrimary : Color.paperCard, in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(selectedFilter == filter ? [.isSelected] : [])
                }
            }
        }
    }

    private var feedSkeleton: some View {
        VStack(alignment: .leading, spacing: 18) {
            Label("Votre sélection se prépare", systemImage: "sparkles")
                .font(.system(size: 13, weight: .medium)).foregroundStyle(.secondary)
            ForEach(0..<3) { _ in
                VStack(alignment: .leading, spacing: 13) {
                    Capsule().fill(Color.secondary.opacity(0.09)).frame(width: 140, height: 12)
                    RoundedRectangle(cornerRadius: 8).fill(Color.secondary.opacity(0.08)).frame(height: 62)
                    Capsule().fill(Color.secondary.opacity(0.07)).frame(height: 10)
                    Capsule().fill(Color.secondary.opacity(0.07)).frame(width: 220, height: 10)
                }
                .padding(20).background(Color.paperCard, in: RoundedRectangle(cornerRadius: 24))
            }
        }
        .accessibilityLabel("Chargement des news")
    }

    private func loadInitialFeed() async {
        let cached = LocalNewsStore.shared.loadV2Events()
        if !cached.isEmpty { events = cached; isLoading = false }
        savedEventIds = Set(LocalNewsStore.shared.loadV2Saved().map(\.eventId))
        await refreshFeed()
        isLoading = false
    }

    private var currentFilterCode: String {
        switch selectedFilter {
        case "Multi-sources": return "multi"
        default: return "all"
        }
    }

    private var currentSortCode: String {
        return selectedFilter == "Récents" ? "recent" : "personalized"
    }

    private func refreshFeed() async {
        guard !isRefreshing else { return }
        isRefreshing = true
        do {
            let page = try await APIClient.shared.fetchV2FeedPage(limit: 30, offset: 0, sort: currentSortCode, filter: currentFilterCode)
            events = page.items
            likedEventIds = Set(page.items.filter { $0.liked == true }.map(\.eventId))
            pendingEvents = []
            nextOffset = page.nextOffset
            hasMore = page.hasMore ?? false
            savedEventIds = Set(page.items.filter { $0.saved == true }.map(\.eventId)).union(savedEventIds)
            LocalNewsStore.shared.saveV2Events(events)
            lastUpdated = Date()
            errorMessage = nil
            if let saved = try? await APIClient.shared.fetchV2Saved() {
                savedEventIds = Set(saved.map(\.eventId))
                LocalNewsStore.shared.saveV2Saved(saved)
            }
        } catch {
            errorMessage = events.isEmpty ? "Le serveur est injoignable. Vérifiez la connexion dans votre profil." : "Connexion interrompue. Votre dernière sélection reste disponible."
        }
        isRefreshing = false
    }

    private func checkForUpdates() async {
        guard !isRefreshing && !loadingMore else { return }
        do {
            let page = try await APIClient.shared.fetchV2FeedPage(limit: 30, offset: 0, sort: currentSortCode, filter: currentFilterCode)
            let known = Set(events.map(\.eventId))
            if page.items.contains(where: { !known.contains($0.eventId) }) {
                pendingEvents = page.items + events.filter { old in !page.items.contains(where: { $0.eventId == old.eventId }) }
            }
            lastUpdated = Date()
            errorMessage = nil
        } catch { errorMessage = "Connexion interrompue. Votre dernière sélection reste disponible." }
    }

    private func loadMore() async {
        guard let nextOffset, !loadingMore else { return }
        loadingMore = true
        do {
            let page = try await APIClient.shared.fetchV2FeedPage(limit: 30, offset: nextOffset, sort: currentSortCode, filter: currentFilterCode)
            let known = Set(events.map(\.eventId))
            events += page.items.filter { !known.contains($0.eventId) }
            savedEventIds.formUnion(page.items.filter { $0.saved == true }.map(\.eventId))
            likedEventIds.formUnion(page.items.filter { $0.liked == true }.map(\.eventId))
            self.nextOffset = page.nextOffset
            hasMore = page.hasMore ?? false
            LocalNewsStore.shared.saveV2Events(events)
            errorMessage = nil
        } catch { errorMessage = "La suite des news n'a pas pu être chargée. Réessayez dans un instant." }
        loadingMore = false
    }

    private func recordImpression(_ event: V2Event) {
        guard isActive, !seenIds.contains(event.eventId) else { return }
        seenIds.insert(event.eventId)
        Task { await APIClient.shared.postV2Interaction(eventId: event.eventId, type: "impression") }
    }

    private func toggleLike(_ event: V2Event) {
        guard !likingIds.contains(event.eventId) else { return }
        likingIds.insert(event.eventId)
        let wasLiked = likedEventIds.contains(event.eventId)
        if wasLiked {
            likedEventIds.remove(event.eventId)
        } else {
            likedEventIds.insert(event.eventId)
            HapticsManager.shared.notification(.success)
        }
        Task {
            let success = await APIClient.shared.postV2Interaction(eventId: event.eventId, type: wasLiked ? "unlike" : "like")
            likingIds.remove(event.eventId)
            if !success {
                if wasLiked { likedEventIds.insert(event.eventId) } else { likedEventIds.remove(event.eventId) }
                errorMessage = "Votre préférence n'a pas pu être enregistrée."
            }
        }
    }

    private func toggleSave(_ event: V2Event) {
        guard !savingIds.contains(event.eventId) else { return }
        let wasSaved = savedEventIds.contains(event.eventId)
        if wasSaved { savedEventIds.remove(event.eventId) } else { savedEventIds.insert(event.eventId) }
        savingIds.insert(event.eventId)
        HapticsManager.shared.impact(.soft)
        Task {
            let success = await APIClient.shared.postV2Interaction(eventId: event.eventId, type: wasSaved ? "unsave" : "save")
            savingIds.remove(event.eventId)
            if success {
                publishSavedState(event, saved: !wasSaved)
            } else {
                if wasSaved { savedEventIds.insert(event.eventId) } else { savedEventIds.remove(event.eventId) }
                errorMessage = "L'enregistrement n'a pas été confirmé. Réessayez lorsque la connexion revient."
            }
        }
    }

    private func reject(_ event: V2Event) {
        Task {
            let success = await APIClient.shared.postV2Interaction(eventId: event.eventId, type: "reject")
            if success {
                withAnimation(reduceMotion ? nil : .easeOut(duration: 0.2)) { _ = rejectedIds.insert(event.eventId) }
            } else { errorMessage = "Votre préférence n'a pas pu être enregistrée." }
        }
    }
}

// MARK: - SOLO TWEET CARD VIEW (1 Per Screen Full Height Experience)
public struct V2SoloTweetCardView: View {
    let event: V2Event
    var isLiked: Bool = false
    var isSaved: Bool = false
    var onOpenDetail: () -> Void = {}
    var onToggleSave: () -> Void = {}
    var onLike: () -> Void = {}
    var onDislike: () -> Void = {}
    var onShowWhy: () -> Void = {}

    @ObservedObject private var themeManager = ThemeManager.shared
    @State private var likeScale: CGFloat = 1.0

    private var shareText: String {
        var text = event.displayTitle
        if let summary = event.shortSummary, !summary.isEmpty { text += "\n\n" + summary }
        if let url = event.sources.compactMap(\.articleURL).first { text += "\n\n" + url.absoluteString }
        return text
    }

    public var body: some View {
        VStack {
            Spacer(minLength: 8)

            VStack(alignment: .leading, spacing: 16) {
                // Top: Source Favicon(s), Name(s), Time, Menu
                HStack(spacing: 10) {
                    if event.sources.count > 1 {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(event.sources, id: \.id) { src in
                                    HStack(spacing: 6) {
                                        if let fav = src.faviconURL {
                                            AsyncImage(url: fav) { phase in
                                                if let img = phase.image {
                                                    img.resizable().scaledToFit()
                                                        .frame(width: 20, height: 20)
                                                        .clipShape(Circle())
                                                } else {
                                                    Circle().fill(Color.secondary.opacity(0.15))
                                                        .frame(width: 20, height: 20)
                                                        .overlay(Text(String(src.displayName.prefix(1)).uppercased()).font(themeManager.font(size: 10, weight: .bold)))
                                                }
                                            }
                                        } else {
                                            Circle().fill(Color.secondary.opacity(0.15))
                                                .frame(width: 20, height: 20)
                                                .overlay(Text(String(src.displayName.prefix(1)).uppercased()).font(themeManager.font(size: 10, weight: .bold)))
                                        }
                                        Text(src.displayName)
                                            .font(themeManager.font(size: 13, weight: .bold))
                                            .foregroundColor(.primary)
                                            .lineLimit(1)
                                    }
                                    .padding(.horizontal, 9)
                                    .padding(.vertical, 5)
                                    .background(Color.secondary.opacity(0.08), in: Capsule())
                                }
                                Text("·")
                                    .font(themeManager.font(size: 12))
                                    .foregroundColor(.secondary)
                                Text(event.relativeTimeString)
                                    .font(themeManager.font(size: 12))
                                    .foregroundColor(.secondary)
                                    .fixedSize()
                            }
                        }
                    } else {
                        if let favURL = event.primaryFaviconURL {
                            AsyncImage(url: favURL) { phase in
                                if let img = phase.image {
                                    img.resizable().scaledToFit()
                                        .frame(width: 38, height: 38)
                                        .clipShape(Circle())
                                        .overlay(Circle().stroke(Color.secondary.opacity(0.18), lineWidth: 1))
                                } else {
                                    soloAvatar
                                }
                            }
                        } else {
                            soloAvatar
                        }

                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: 4) {
                                Text(event.sources.first?.displayName ?? "Actualité")
                                    .font(themeManager.font(size: 15, weight: .bold))
                                    .foregroundColor(.primary)
                                    .lineLimit(1)

                                Image(systemName: "newspaper")
                                    .font(.system(size: 12))
                                    .foregroundColor(.secondary)
                            }

                            Text(event.relativeTimeString)
                                .font(themeManager.font(size: 12))
                                .foregroundColor(.secondary)
                        }
                    }

                    Spacer()

                    Menu {
                        Button("Pourquoi cette actualité ?", systemImage: "sparkles", action: onShowWhy)
                        Button("Moins de sujets comme celui-ci", systemImage: "hand.thumbsdown", action: onDislike)
                        Button("Ouvrir les détails complets", systemImage: "arrow.up.right", action: onOpenDetail)
                    } label: {
                        Image(systemName: "ellipsis")
                            .font(.system(size: 18))
                            .foregroundColor(.secondary)
                            .frame(width: 36, height: 36)
                            .contentShape(Rectangle())
                    }
                }

                // Tappable main card content
                Button(action: onOpenDetail) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(event.displayTitle)
                            .font(themeManager.headlineFont(size: 21))
                            .lineSpacing(3)
                            .foregroundColor(.primary)
                            .fixedSize(horizontal: false, vertical: true)

                        if let summary = event.shortSummary, !summary.isEmpty {
                            if summary.contains(" • ") {
                                VStack(alignment: .leading, spacing: 6) {
                                    ForEach(summary.components(separatedBy: " • "), id: \.self) { bullet in
                                        HStack(alignment: .top, spacing: 6) {
                                            Text("•")
                                                .foregroundColor(.blue)
                                                .fontWeight(.bold)
                                            Text(cleanMarkdownKey(bullet))
                                                .font(themeManager.bodyFont(size: 14))
                                                .foregroundColor(.primary.opacity(0.9))
                                                .lineSpacing(2.5)
                                                .fixedSize(horizontal: false, vertical: true)
                                        }
                                    }
                                }
                            } else {
                                Text(cleanMarkdownKey(summary))
                                    .font(themeManager.bodyFont(size: 14.5))
                                    .foregroundColor(.primary.opacity(0.85))
                                    .lineSpacing(3.5)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }

                        if let heroURL = event.heroImageURL {
                            AsyncImage(url: heroURL) { phase in
                                switch phase {
                                case .success(let image):
                                    image.resizable()
                                        .scaledToFill()
                                        .frame(maxWidth: .infinity)
                                        .frame(height: 200)
                                        .clipped()
                                        .clipShape(RoundedRectangle(cornerRadius: 16))
                                        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.secondary.opacity(0.12), lineWidth: 1))
                                case .empty:
                                    RoundedRectangle(cornerRadius: 16)
                                        .fill(Color.secondary.opacity(0.08))
                                        .frame(height: 200)
                                default:
                                    EmptyView()
                                }
                            }
                        }

                        if event.sources.count > 1 {
                            HStack(spacing: 6) {
                                Image(systemName: "link.badge.plus")
                                    .font(.system(size: 11, weight: .semibold))
                                Text("Recoupé par \(event.sources.count) sources")
                                    .font(.system(size: 11, weight: .medium))
                            }
                            .foregroundColor(.secondary)
                            .padding(.vertical, 2)
                        }
                    }
                    .multilineTextAlignment(.leading)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)

                // Action Bar
                Divider().padding(.vertical, 2)

                HStack(spacing: 0) {
                    // Like button
                    Button {
                        withAnimation(.spring(response: 0.25, dampingFraction: 0.5)) {
                            likeScale = 1.35
                        }
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
                            withAnimation(.spring(response: 0.25, dampingFraction: 0.6)) {
                                likeScale = 1.0
                            }
                        }
                        onLike()
                    } label: {
                        HStack(spacing: 5) {
                            Image(systemName: isLiked ? "heart.fill" : "heart")
                                .font(.system(size: 18))
                                .scaleEffect(likeScale)
                            Text(isLiked ? "Aimé" : "J'aime")
                                .font(.system(size: 12, weight: isLiked ? .bold : .medium))
                        }
                        .foregroundColor(isLiked ? Color(red: 0.97, green: 0.09, blue: 0.5) : .secondary)
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.plain)

                    // Dislike button
                    Button(action: onDislike) {
                        HStack(spacing: 5) {
                            Image(systemName: "hand.thumbsdown")
                                .font(.system(size: 16))
                            Text("Moins")
                                .font(.system(size: 12, weight: .medium))
                        }
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.plain)

                    // Bookmark button
                    Button(action: onToggleSave) {
                        HStack(spacing: 5) {
                            Image(systemName: isSaved ? "bookmark.fill" : "bookmark")
                                .font(.system(size: 17))
                            Text(isSaved ? "Sauvé" : "Signet")
                                .font(.system(size: 12, weight: isSaved ? .bold : .medium))
                        }
                        .foregroundColor(isSaved ? Color.newsPrimary : .secondary)
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.plain)

                    // Share button
                    ShareLink(item: shareText) {
                        Image(systemName: "square.and.arrow.up")
                            .font(.system(size: 16))
                            .foregroundColor(.secondary)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.plain)

                    // Detail button
                    Button(action: onOpenDetail) {
                        HStack(spacing: 4) {
                            Text("Détails")
                                .font(.system(size: 11, weight: .bold))
                            Image(systemName: "arrow.up.right")
                                .font(.system(size: 9, weight: .bold))
                        }
                        .foregroundColor(.white)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .background(Color.newsPrimary, in: Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(18)
            .background(Color.paperCard, in: RoundedRectangle(cornerRadius: 26))
            .shadow(color: Color.black.opacity(0.06), radius: 14, x: 0, y: 4)
            .padding(.horizontal, 16)

            Spacer(minLength: 8)
        }
    }

    private var soloAvatar: some View {
        ZStack {
            Circle().fill(Color.newsPrimary.opacity(0.12))
            Text(String((event.sources.first?.displayName ?? "M").prefix(1)).uppercased())
                .font(.system(size: 16, weight: .bold, design: .serif))
                .foregroundColor(Color.newsPrimary)
        }
        .frame(width: 38, height: 38)
    }
}

// MARK: - TWITTER NEWS CARD VIEW (Feed List Mode)
public struct V2TwitterNewsCardView: View {
    let event: V2Event
    var isLiked: Bool = false
    let isSaved: Bool
    var isBackground = false
    var isFeatured = false
    var compact = false
    var onOpenDetail: () -> Void = {}
    var onToggleSave: () -> Void = {}
    var onLike: () -> Void = {}
    var onDislike: () -> Void = {}
    var onShowWhy: () -> Void = {}
    @ObservedObject private var themeManager = ThemeManager.shared

    public init(event: V2Event, isLiked: Bool = false, isSaved: Bool = false, isBackground: Bool = false,
                isFeatured: Bool = false, compact: Bool = false,
                onOpenDetail: @escaping () -> Void = {}, onToggleSave: @escaping () -> Void = {},
                onLike: @escaping () -> Void = {}, onDislike: @escaping () -> Void = {},
                onShowWhy: @escaping () -> Void = {}) {
        self.event = event; self.isLiked = isLiked; self.isSaved = isSaved; self.isBackground = isBackground
        self.isFeatured = isFeatured; self.compact = compact
        self.onOpenDetail = onOpenDetail; self.onToggleSave = onToggleSave
        self.onLike = onLike; self.onDislike = onDislike; self.onShowWhy = onShowWhy
    }

    private var shareText: String {
        var text = event.displayTitle
        if let summary = event.shortSummary, !summary.isEmpty { text += "\n\n" + summary }
        if let url = event.sources.compactMap(\.articleURL).first { text += "\n\n" + url.absoluteString }
        return text
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: compact ? 12 : 17) {
            if isFeatured && !compact {
                Label("À LA UNE", systemImage: "sparkles")
                    .font(.system(size: 9, weight: .bold)).tracking(1.5)
                    .foregroundStyle(Color.newsPrimary)
            }
            HStack(spacing: 8) {
                if event.sources.count > 1 {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(event.sources, id: \.id) { src in
                                HStack(spacing: 6) {
                                    if let fav = src.faviconURL {
                                        AsyncImage(url: fav) { phase in
                                            if let img = phase.image {
                                                img.resizable().scaledToFit()
                                                    .frame(width: 18, height: 18)
                                                    .clipShape(Circle())
                                            } else {
                                                Circle().fill(Color.secondary.opacity(0.15))
                                                    .frame(width: 18, height: 18)
                                                    .overlay(
                                                        Text(String(src.displayName.prefix(1)).uppercased())
                                                            .font(themeManager.font(size: 9, weight: .bold))
                                                    )
                                            }
                                        }
                                    } else {
                                        Circle().fill(Color.secondary.opacity(0.15))
                                            .frame(width: 18, height: 18)
                                            .overlay(
                                                Text(String(src.displayName.prefix(1)).uppercased())
                                                    .font(themeManager.font(size: 9, weight: .bold))
                                            )
                                    }
                                    Text(src.displayName)
                                        .font(themeManager.font(size: 13, weight: .bold))
                                        .foregroundStyle(.primary)
                                        .lineLimit(1)
                                }
                                .padding(.horizontal, 9)
                                .padding(.vertical, 5)
                                .background(Color.secondary.opacity(0.08), in: Capsule())
                            }
                            Text("·")
                                .font(themeManager.font(size: 12))
                                .foregroundStyle(.secondary)
                            Text(event.relativeTimeString)
                                .font(themeManager.font(size: 11))
                                .foregroundStyle(.secondary)
                                .fixedSize()
                        }
                    }
                } else {
                    if let favURL = event.primaryFaviconURL {
                        AsyncImage(url: favURL) { phase in
                            if let img = phase.image {
                                img.resizable().scaledToFit()
                                    .frame(width: 36, height: 36)
                                    .clipShape(Circle())
                                    .overlay(Circle().stroke(Color.secondary.opacity(0.15), lineWidth: 1))
                            } else {
                                fallbackAvatar
                            }
                        }
                    } else {
                        fallbackAvatar
                    }

                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 4) {
                            Text(event.sources.first?.displayName ?? "Actualité")
                                .font(themeManager.font(size: 13, weight: .bold)).lineLimit(1)
                        }
                        Text(event.relativeTimeString)
                            .font(themeManager.font(size: 11)).foregroundStyle(.secondary)
                    }
                }
                Spacer(minLength: 2)
                Menu {
                    Button("Pourquoi cette actualité ?", systemImage: "sparkles", action: onShowWhy)
                    Button("Moins de sujets comme celui-ci", systemImage: "hand.thumbsdown", action: onDislike)
                } label: {
                    Image(systemName: "ellipsis").font(.system(size: 18)).foregroundStyle(.secondary)
                        .frame(width: 36, height: 36).contentShape(Rectangle())
                }
                .accessibilityLabel("Options de cette actualité")
            }
            Button(action: onOpenDetail) {
                VStack(alignment: .leading, spacing: 12) {
                    Text(event.displayTitle)
                        .font(themeManager.font(size: compact ? 19 : (isFeatured ? 28 : 22), weight: isFeatured && !compact ? .regular : .semibold))
                        .tracking(-0.5).foregroundStyle(.primary)
                        .lineSpacing(2).fixedSize(horizontal: false, vertical: true)
                    if let summary = event.shortSummary, !summary.isEmpty {
                        if summary.contains(" • ") {
                            VStack(alignment: .leading, spacing: 5) {
                                ForEach(summary.components(separatedBy: " • "), id: \.self) { bullet in
                                    HStack(alignment: .top, spacing: 5) {
                                        Text("•")
                                            .foregroundColor(.blue)
                                            .fontWeight(.bold)
                                        Text(cleanMarkdownKey(bullet))
                                            .font(themeManager.font(size: 13.5, weight: .regular))
                                            .foregroundStyle(.secondary)
                                            .lineSpacing(2)
                                            .lineLimit(nil)
                                            .fixedSize(horizontal: false, vertical: true)
                                    }
                                }
                            }
                        } else {
                            Text(cleanMarkdownKey(summary))
                                .font(themeManager.font(size: 14, weight: .regular)).foregroundStyle(.secondary)
                                .lineSpacing(4)
                                .lineLimit(nil)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    if !compact, let url = event.heroImageURL {
                        AsyncImage(url: url) { phase in
                            if case .success(let image) = phase {
                                image.resizable().scaledToFill()
                                    .frame(maxWidth: .infinity).frame(height: isFeatured ? 215 : 178)
                                    .clipped().clipShape(RoundedRectangle(cornerRadius: 17))
                            } else if case .empty = phase {
                                RoundedRectangle(cornerRadius: 17).fill(Color.newsPrimary.opacity(0.04))
                                    .frame(height: isFeatured ? 215 : 178)
                            }
                        }
                    }
                }
                .multilineTextAlignment(.leading)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            HStack(spacing: 8) {
                Button(action: onOpenDetail) {
                    Image(systemName: "newspaper")
                        .font(.system(size: 16))
                        .foregroundStyle(Color.newsPrimary)
                        .frame(width: 36, height: 36)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Voir les détails")

                Spacer()

                Button(action: onDislike) {
                    Image(systemName: "hand.thumbsdown")
                        .font(.system(size: 16))
                        .foregroundStyle(Color.secondary)
                        .frame(width: 36, height: 36)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Moins de sujets similaires")

                Button(action: onLike) {
                    Image(systemName: isLiked ? "heart.fill" : "heart")
                        .font(.system(size: 17))
                        .foregroundStyle(isLiked ? Color(red: 0.97, green: 0.09, blue: 0.5) : Color.secondary)
                        .frame(width: 36, height: 36)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(isLiked ? "Aimé" : "Aimer")

                Button(action: onToggleSave) {
                    Image(systemName: isSaved ? "bookmark.fill" : "bookmark")
                        .font(.system(size: 17)).foregroundStyle(isSaved ? Color.newsPrimary : Color.secondary)
                        .frame(width: 36, height: 36)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(isSaved ? "Retirer des enregistrements" : "Enregistrer pour plus tard")

                ShareLink(item: shareText) {
                    Image(systemName: "square.and.arrow.up").font(.system(size: 16))
                        .foregroundStyle(.secondary).frame(width: 36, height: 36)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Partager cette actualité")
            }
        }
        .padding(compact ? 18 : 21)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.paperCard, in: RoundedRectangle(cornerRadius: 26))
        .opacity(isBackground ? 0.35 : 1)
    }

    private var fallbackAvatar: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 11).fill(Color.newsPrimary.opacity(0.08))
            Text(String((event.sources.first?.displayName ?? "M").prefix(1)).uppercased())
                .font(.system(size: 17, weight: .bold, design: .serif)).foregroundStyle(Color.newsPrimary)
        }
        .frame(width: 36, height: 36)
    }
}

// MARK: - COMPATIBILITY WRAPPER FOR V2 EVENT CARD
public struct V2EventCardView: View {
    let event: V2Event
    var isSaved: Bool
    var onToggleSave: (() -> Void)?
    var onReject: (() -> Void)?
    var onOpenDetail: () -> Void
    @State private var localSaved: Bool
    @State private var liked: Bool
    @State private var busy = false
    @State private var showingWhy = false
    @State private var actionError: String?

    public init(event: V2Event, isSaved: Bool = false,
                onToggleSave: (() -> Void)? = nil, onReject: (() -> Void)? = nil,
                onOpenDetail: @escaping () -> Void = {}) {
        self.event = event; self.isSaved = isSaved
        self.onToggleSave = onToggleSave; self.onReject = onReject; self.onOpenDetail = onOpenDetail
        _localSaved = State(initialValue: event.saved ?? isSaved)
        _liked = State(initialValue: event.liked ?? false)
    }

    public var body: some View {
        V2TwitterNewsCardView(
            event: event, isLiked: liked, isSaved: onToggleSave == nil ? localSaved : isSaved,
            onOpenDetail: onOpenDetail,
            onToggleSave: {
                if let onToggleSave { onToggleSave() }
                else { perform(type: localSaved ? "unsave" : "save") }
            },
            onLike: { perform(type: liked ? "unlike" : "like") },
            onDislike: {
                if let onReject { onReject() } else { perform(type: "reject") }
            },
            onShowWhy: { showingWhy = true }
        )
        .disabled(busy)
        .sheet(isPresented: $showingWhy) {
            WhyAmISeeingThisSheet(event: event).presentationDetents([.medium, .large])
        }
        .alert("Action non enregistrée", isPresented: Binding(get: { actionError != nil }, set: { if !$0 { actionError = nil } })) {
            Button("Fermer", role: .cancel) { actionError = nil }
        } message: { Text(actionError ?? "") }
        .onReceive(NotificationCenter.default.publisher(for: .mizanSavedChanged)) { notification in
            if notification.object as? String == event.eventId, let saved = notification.userInfo?["saved"] as? Bool { localSaved = saved }
        }
    }

    private func perform(type: String) {
        guard !busy else { return }
        busy = true
        Task {
            let success = await APIClient.shared.postV2Interaction(eventId: event.eventId, type: type)
            busy = false
            if success {
                if type == "save" || type == "unsave" {
                    localSaved = type == "save"
                    publishSavedState(event, saved: localSaved)
                } else if type == "like" || type == "unlike" { liked = type == "like" }
                HapticsManager.shared.notification(.success)
            } else { actionError = "La connexion au serveur n'a pas permis de confirmer votre choix. Réessayez." }
        }
    }
}

// MARK: - 3. WHY AM I SEEING THIS SHEET
public struct WhyAmISeeingThisSheet: View {
    let event: V2Event
    @Environment(\.dismiss) private var dismiss

    public var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 14) {
                Text("Cet événement a été sélectionné pour ton flux :")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                if let reasons = event.scoreReasons, !reasons.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(Array(reasons.enumerated()), id: \.offset) { _, reason in
                            HStack(alignment: .top, spacing: 10) {
                                Image(systemName: "sparkles")
                                    .font(.system(size: 13))
                                    .foregroundColor(.blue)
                                    .padding(.top, 2)

                                Text(reason.humanExplanation)
                                    .font(.system(size: 14, weight: .medium))
                                    .foregroundColor(.primary)
                            }
                        }
                    }
                    .padding()
                    .background(Color(uiColor: .secondarySystemBackground))
                    .cornerRadius(12)
                } else {
                    Text("Recommandé selon l'activité de l'information mondiale.")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }
            .padding()
            .navigationTitle("Pourquoi cette actualité ?")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Fermer") { dismiss() }
                }
            }
        }
    }
}

// MARK: - 4. V2 EVENT DETAIL VIEW
public struct V2EventDetailView: View {
    let event: V2Event

    @State private var detail: V2EventDetail?
    @State private var claims: [V2Claim] = []
    @State private var history: V2EventHistoryResponse?
    @State private var isLoading = true
    @State private var isSaved = false
    @State private var isSaving = false
    @State private var loadError: String?
    @State private var selectedEvidence: V2Evidence?
    @State private var startTime = Date()
    @ObservedObject private var themeManager = ThemeManager.shared

    public init(event: V2Event) {
        self.event = event
        _isSaved = State(initialValue: event.saved ?? LocalNewsStore.shared.loadV2Saved().contains(where: { $0.eventId == event.eventId }))
    }

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                if isLoading { ProgressView("Chargement des sources et des faits…").font(.system(size: 12)) }
                if let loadError {
                    Label(loadError, systemImage: "exclamationmark.circle")
                        .font(.system(size: 13)).foregroundStyle(.secondary)
                }
                if let heroURL = event.heroImageURL {
                    AsyncImage(url: heroURL) { phase in
                        switch phase {
                        case .success(let image):
                            image.resizable()
                                .scaledToFill()
                                .frame(maxWidth: .infinity)
                                .frame(height: 210)
                                .clipped()
                                .clipShape(RoundedRectangle(cornerRadius: 16))
                        case .empty:
                            RoundedRectangle(cornerRadius: 16)
                                .fill(Color.secondary.opacity(0.08))
                                .frame(height: 210)
                        default:
                            EmptyView()
                        }
                    }
                }

                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 6) {
                        Text(event.humanCategory.uppercased())
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(.blue)

                        Text("•")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)

                        Text(event.relativeTimeString)
                            .font(.system(size: 12))
                            .foregroundColor(.secondary)

                        Spacer()

                        if event.sources.count >= 2 {
                            Text("\(event.sources.count) sources")
                                .font(.system(size: 11, weight: .semibold))
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(Color.secondary.opacity(0.12))
                                .clipShape(Capsule())
                        }
                    }

                    Text(detail?.summary?.headline ?? event.displayTitle)
                        .font(themeManager.headlineFont(size: 24))
                        .foregroundColor(.primary)
                        .fixedSize(horizontal: false, vertical: true)
                }


                VStack(alignment: .leading, spacing: 14) {
                    let summaryText = detail?.summary?.articleBody ?? detail?.summary?.detailedStory ?? detail?.summary?.detailSummary ?? detail?.summary?.shortSummary ?? event.shortSummary ?? "Analyse de l'événement en cours..."
                    let rawParagraphs = summaryText.contains("\n\n")
                        ? summaryText.components(separatedBy: "\n\n")
                        : (summaryText.contains(" • ") ? summaryText.components(separatedBy: " • ") : summaryText.components(separatedBy: "\n"))
                    let paragraphs = rawParagraphs
                        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: "^[•\\-\\s]+", with: "", options: .regularExpression) }
                        .filter { !$0.isEmpty && !$0.lowercased().hasPrefix("selon les sources") && !$0.lowercased().hasPrefix("confirmation de l'événement") }

                    if !paragraphs.isEmpty {
                        ForEach(Array(paragraphs.enumerated()), id: \.offset) { idx, para in
                            Text(cleanMarkdownKey(para))
                                .font(idx == 0 ? themeManager.bodyFont(size: 16.5) : themeManager.bodyFont(size: 15.5))
                                .foregroundColor(.primary)
                                .lineSpacing(7)
                                .padding(.bottom, idx == 0 ? 6 : 2)
                        }
                    } else {
                        Text(cleanMarkdownKey(summaryText))
                            .font(themeManager.bodyFont(size: 16))
                            .foregroundColor(.primary)
                            .lineSpacing(7)
                    }
                }

                if !claims.isEmpty {
                    DisclosureGroup("Faits & degré de certitude") {
                        VStack(spacing: 12) {
                            ForEach(claims) { claim in claimCard(claim) }
                        }.padding(.top, 12)
                    }.font(.system(size: 16, weight: .semibold))
                }
                if let revisions = history?.revisions, revisions.count > 1 {
                    DisclosureGroup("L'évolution de cette information") {
                        VStack(alignment: .leading, spacing: 15) {
                            ForEach(revisions) { revision in
                                HStack(alignment: .top, spacing: 10) {
                                    Circle().fill(Color.newsPrimary).frame(width: 7, height: 7).padding(.top, 6)
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text("Mise à jour \(revision.revisionNumber)").font(.system(size: 13, weight: .semibold))
                                        if let reason = revision.reason { Text(reason).font(.system(size: 12)).foregroundStyle(.secondary) }
                                    }
                                }
                            }
                        }.padding(.top, 12)
                    }.font(.system(size: 16, weight: .semibold))
                }

                let sourcesList = detail?.sources.isEmpty == false ? (detail?.sources ?? []) : event.sources
                VStack(alignment: .leading, spacing: 10) {
                    Text("SOURCES ORIGINALES (\(sourcesList.count))")
                        .font(themeManager.font(size: 11, weight: .bold))
                        .foregroundColor(.secondary)
                        .tracking(0.5)

                    if sourcesList.isEmpty {
                        Text("Sources en cours de référencement...")
                            .font(.footnote)
                            .foregroundColor(.secondary)
                    } else {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(sourcesList) { source in
                                    if let url = source.articleURL {
                                        Link(destination: url) {
                                            compactSourceChip(source, hasLink: true)
                                        }
                                        .buttonStyle(.plain)
                                        .simultaneousGesture(TapGesture().onEnded {
                                            Task {
                                                await APIClient.shared.postV2Interaction(
                                                    eventId: event.eventId,
                                                    type: "source_click",
                                                    sourceId: source.id
                                                )
                                            }
                                        })
                                    } else {
                                        compactSourceChip(source, hasLink: false)
                                    }
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }
                }
            }
            .padding(16)
        }
        .background(Color.paperBackground)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button {
                    guard !isSaving else { return }
                    isSaving = true
                    let targetSaved = !isSaved
                    Task {
                        let success = await APIClient.shared.postV2Interaction(eventId: event.eventId, type: targetSaved ? "save" : "unsave")
                        isSaving = false
                        if success {
                            isSaved = targetSaved
                            publishSavedState(event, saved: targetSaved)
                        } else { loadError = "L'enregistrement n'a pas pu être confirmé. Réessayez." }
                    }
                } label: {
                    Image(systemName: isSaved ? "bookmark.fill" : "bookmark")
                        .foregroundColor(isSaved ? .blue : .primary)
                }

                ShareLink(item: "\(detail?.summary?.headline ?? event.displayTitle)\n\n\(event.sources.compactMap(\.articleURL).first?.absoluteString ?? "MIZAN")") {
                    Image(systemName: "square.and.arrow.up")
                }
            }
        }
        .sheet(item: $selectedEvidence) { evidence in
            EvidenceDetailSheet(evidence: evidence)
                .presentationDetents([.medium])
        }
        .task {
            startTime = Date()
            await APIClient.shared.postV2Interaction(eventId: event.eventId, type: "open")

            async let detailTask = APIClient.shared.fetchV2Event(eventId: event.eventId)
            async let claimsTask = APIClient.shared.fetchV2Claims(eventId: event.eventId)
            async let historyTask = APIClient.shared.fetchV2History(eventId: event.eventId)

            do {
                detail = try await detailTask
            } catch { loadError = "Le détail n'a pas pu être actualisé. Le résumé reste disponible." }
            do {
                claims = try await claimsTask
            } catch {}
            do {
                history = try await historyTask
            } catch {}

            if let saved = try? await APIClient.shared.fetchV2Saved() { isSaved = saved.contains(where: { $0.eventId == event.eventId }) }
            isLoading = false
        }
        .onDisappear {
            let dwellSeconds = Int(Date().timeIntervalSince(startTime))
            if dwellSeconds >= 1 {
                Task {
                    await APIClient.shared.postV2Interaction(
                        eventId: event.eventId,
                        type: "dwell",
                        duration: dwellSeconds * 1000
                    )
                }
            }
        }
    }

    private func compactSourceChip(_ source: V2Source, hasLink: Bool) -> some View {
        HStack(spacing: 6) {
            if let favURL = source.faviconURL {
                AsyncImage(url: favURL) { phase in
                    if let img = phase.image {
                        img.resizable().scaledToFit().frame(width: 18, height: 18).clipShape(Circle())
                    } else {
                        Circle().fill(Color.secondary.opacity(0.15))
                            .frame(width: 18, height: 18)
                            .overlay(Text(String(source.displayName.prefix(1)).uppercased()).font(themeManager.font(size: 9, weight: .bold)))
                    }
                }
            } else {
                Circle().fill(Color.secondary.opacity(0.15))
                    .frame(width: 18, height: 18)
                    .overlay(Text(String(source.displayName.prefix(1)).uppercased()).font(themeManager.font(size: 9, weight: .bold)))
            }
            Text(source.displayName)
                .font(themeManager.font(size: 13, weight: .semibold))
                .foregroundColor(.primary)
                .lineLimit(1)
            if hasLink {
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(.blue)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Color.secondary.opacity(0.08), in: Capsule())
        .overlay(
            Capsule().stroke(Color.secondary.opacity(0.15), lineWidth: 0.5)
        )
    }

    private func sourceRowContent(_ source: V2Source, hasLink: Bool) -> some View {
        HStack(spacing: 12) {
            if let favURL = source.faviconURL {
                AsyncImage(url: favURL) { phase in
                    if let img = phase.image {
                        img.resizable().scaledToFit().frame(width: 24, height: 24).clipShape(Circle())
                    } else {
                        Image(systemName: "globe").frame(width: 24, height: 24).foregroundStyle(.secondary)
                    }
                }
            } else {
                Image(systemName: "globe").frame(width: 24, height: 24).foregroundStyle(.secondary)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(source.displayName)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(.primary)
                if let domain = source.canonicalDomain {
                    Text(domain)
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }
            }
            Spacer()
            if hasLink {
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(.blue)
            } else {
                Image(systemName: "checkmark.seal")
                    .font(.system(size: 13))
                    .foregroundColor(.secondary)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Color(uiColor: .secondarySystemBackground))
        .cornerRadius(12)
    }

    private func claimCard(_ claim: V2Claim) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: claim.statusIcon)
                    .font(.system(size: 11, weight: .bold))
                Text(claim.humanStatus)
                    .font(.system(size: 11, weight: .bold))
            }
            .foregroundColor(claim.statusColor)

            Text(claim.canonicalText)
                .font(.system(size: 15, weight: .medium))
                .foregroundColor(.primary)

            if !claim.evidence.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(claim.evidence) { ev in
                        Button {
                            selectedEvidence = ev
                            Task {
                                await APIClient.shared.postV2Interaction(
                                    eventId: event.eventId,
                                    type: "source_click",
                                    sourceId: ev.id
                                )
                            }
                        } label: {
                            HStack(alignment: .top, spacing: 6) {
                                Image(systemName: "quote.opening")
                                    .font(.system(size: 10))
                                    .foregroundColor(.secondary)
                                    .padding(.top, 2)

                                VStack(alignment: .leading, spacing: 2) {
                                    Text("\"\(ev.quotedText)\"")
                                        .font(.system(size: 13, design: .serif))
                                        .foregroundColor(.primary.opacity(0.85))
                                        .lineLimit(2)
                                        .multilineTextAlignment(.leading)

                                    HStack(spacing: 4) {
                                        Text(ev.displaySource)
                                            .font(.system(size: 11, weight: .medium))
                                            .foregroundColor(.blue)
                                        Image(systemName: "arrow.up.right")
                                            .font(.system(size: 9))
                                            .foregroundColor(.blue)
                                    }
                                }
                            }
                            .padding(8)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color(uiColor: .tertiarySystemBackground))
                            .cornerRadius(8)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(uiColor: .secondarySystemBackground))
        .cornerRadius(12)
    }
}

// MARK: - 5. EVIDENCE DETAIL SHEET
public struct EvidenceDetailSheet: View {
    let evidence: V2Evidence
    @Environment(\.dismiss) private var dismiss

    public var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(evidence.displaySource.uppercased())
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(.blue)

                    Text("Extrait certifié par le système")
                        .font(.headline)
                }

                Text("\"\(evidence.quotedText)\"")
                    .font(.system(size: 16, design: .serif))
                    .foregroundColor(.primary)
                    .lineSpacing(4)
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(uiColor: .secondarySystemBackground))
                    .cornerRadius(12)

                if let url = URL(string: evidence.sourceURLSnapshot) {
                    Link(destination: url) {
                        HStack {
                            Text("Consulter la publication originale")
                            Spacer()
                            Image(systemName: "arrow.up.forward.square")
                        }
                        .font(.system(size: 15, weight: .semibold))
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                }

                Spacer()
            }
            .padding()
            .navigationTitle("Preuve & Source")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Fermer") { dismiss() }
                }
            }
        }
    }
}

// MARK: - 6. V2 EXPLORE VIEW
public struct V2ExploreView: View {
    @State private var searchText = ""
    @State private var searchResults: [V2Event] = []
    @State private var topSources: [V2TopSource] = []
    @State private var recentEvents: [V2Event] = []
    @State private var isSearching = false
    @State private var isLoading = true
    @State private var selectedEvent: V2Event?
    @State private var searchTask: Task<Void, Never>?
    @State private var loadError: String?
    @Environment(\.dismiss) private var dismiss

    public init() {}

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if let loadError {
                        Label(loadError, systemImage: "wifi.exclamationmark")
                            .font(.system(size: 13)).foregroundStyle(.secondary).padding(.horizontal, 18)
                    }
                    if isLoading && searchText.isEmpty {
                        ProgressView("Exploration des sources…").frame(maxWidth: .infinity).padding()
                    } else if !isLoading && searchText.isEmpty && recentEvents.isEmpty && topSources.isEmpty {
                        ContentUnavailableView("Explorez vos sujets", systemImage: "magnifyingglass", description: Text("Recherchez une actualité, une personne ou une source."))
                    }
                    if !searchText.isEmpty {
                        if isSearching {
                            ProgressView()
                                .padding()
                                .frame(maxWidth: .infinity)
                        } else if searchResults.isEmpty {
                            ContentUnavailableView(
                                "Aucun résultat",
                                systemImage: "magnifyingglass",
                                description: Text("Aucun événement ne correspond à \"\(searchText)\".")
                            )
                            .padding(.top, 40)
                        } else {
                            VStack(alignment: .leading, spacing: 0) {
                                Text("RÉSULTATS")
                                    .font(.system(size: 12, weight: .bold))
                                    .foregroundColor(.secondary)
                                    .padding(.horizontal, 16)
                                    .padding(.bottom, 8)

                                ForEach(searchResults) { event in
                                    V2EventCardView(
                                        event: event,
                                        onOpenDetail: { selectedEvent = event }
                                    )
                                    Color.clear.frame(height: 18)
                                }
                            }
                        }
                    } else {
                        if !topSources.isEmpty {
                            VStack(alignment: .leading, spacing: 10) {
                                Text("SOURCES DU RÉSEAU")
                                    .font(.system(size: 12, weight: .bold))
                                    .foregroundColor(.secondary)
                                    .padding(.horizontal, 16)

                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 10) {
                                        ForEach(topSources) { source in
                                            Button {
                                                searchText = source.displayName
                                                            } label: {
                                                VStack(alignment: .leading, spacing: 2) {
                                                    Text(source.displayName)
                                                        .font(.system(size: 13, weight: .semibold))
                                                        .foregroundColor(.primary)
                                                    Text("\(source.eventCount) événements")
                                                        .font(.system(size: 11))
                                                        .foregroundColor(.secondary)
                                                }
                                                .padding(.horizontal, 12)
                                                .padding(.vertical, 8)
                                                .background(Color(uiColor: .secondarySystemBackground))
                                                .cornerRadius(10)
                                            }
                                            .buttonStyle(.plain)
                                        }
                                    }
                                    .padding(.horizontal, 16)
                                }
                            }
                        }

                        if !recentEvents.isEmpty {
                            VStack(alignment: .leading, spacing: 0) {
                                Text("ACTIVITÉ RÉCENTE DU RÉSEAU")
                                    .font(.system(size: 12, weight: .bold))
                                    .foregroundColor(.secondary)
                                    .padding(.horizontal, 16)
                                    .padding(.bottom, 8)

                                ForEach(recentEvents) { event in
                                    V2EventCardView(
                                        event: event,
                                        onOpenDetail: { selectedEvent = event }
                                    )
                                    Color.clear.frame(height: 18)
                                }
                            }
                        }
                    }
                }
                .padding(.vertical, 12)
            }
            .background(Color.paperBackground)
            .navigationTitle("Explorer")
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Fermer") { dismiss() } } }
            .onDisappear { searchTask?.cancel() }
            .searchable(text: $searchText, prompt: "Rechercher événements, sujets, entités...")
            .onChange(of: searchText) { _, newValue in
                triggerSearch(newValue)
            }
            .navigationDestination(item: $selectedEvent) { event in
                V2EventDetailView(event: event)
            }
            .task {
                await loadExploreData()
            }
            .refreshable {
                await loadExploreData()
            }
        }
    }

    private func triggerSearch(_ query: String) {
        searchTask?.cancel()
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            searchResults = []
            isSearching = false
            return
        }

        isSearching = true
        loadError = nil
        searchResults = []
        searchTask = Task {
            try? await Task.sleep(nanoseconds: 300_000_000)
            if Task.isCancelled { return }
            do {
                let results = try await APIClient.shared.searchV2(query: trimmed)
                if !Task.isCancelled {
                    self.searchResults = results
                    self.isSearching = false
                    self.loadError = nil
                }
            } catch {
                if !Task.isCancelled {
                    self.isSearching = false
                    self.loadError = "La recherche n'a pas pu aboutir. Vérifiez votre connexion puis réessayez."
                }
            }
        }
    }

    private func loadExploreData() async {
        isLoading = true
        do {
            let res = try await APIClient.shared.fetchV2Explore()
            self.topSources = res.topSources
            self.recentEvents = res.recentEvents
            loadError = nil
        } catch { loadError = "Les dernières actualités n'ont pas pu être chargées." }
        isLoading = false
    }
}

// MARK: - 7. V2 SAVED VIEW
public struct V2SavedView: View {
    @State private var savedEvents: [V2Event] = []
    @State private var isLoading = true
    @State private var selectedEvent: V2Event?
    @State private var loadError: String?
    @State private var removingIds: Set<String> = []

    public init() {}

    public var body: some View {
        NavigationStack {
            ZStack {
                Color.paperBackground
                    .ignoresSafeArea()

                if isLoading && savedEvents.isEmpty {
                    ProgressView()
                } else if savedEvents.isEmpty {
                    ContentUnavailableView(
                        "Aucun événement sauvegardé",
                        systemImage: "bookmark",
                        description: Text("Les événements que tu enregistres dans le flux apparaîtront ici.")
                    )
                } else {
                    ScrollView {
                        LazyVStack(spacing: 18) {
                            ForEach(savedEvents) { event in
                                V2EventCardView(
                                    event: event,
                                    isSaved: true,
                                    onToggleSave: {
                                        removeSaved(event)
                                    },
                                    onOpenDetail: {
                                        selectedEvent = event
                                    }
                                )


                            }
                        }
                        .padding(18)
                    }
                    .refreshable {
                        await loadSaved()
                    }
                }
            }
            .navigationTitle("Enregistrés")
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .top, spacing: 0) {
                if let loadError {
                    HStack {
                        Text(loadError).font(.system(size: 12)).foregroundStyle(.secondary)
                        Button("Réessayer") { Task { await loadSaved() } }.font(.system(size: 12, weight: .semibold))
                    }.padding(14).background(Color.paperCard)
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .mizanSavedChanged)) { notification in
                if let id = notification.object as? String, notification.userInfo?["saved"] as? Bool == false {
                    savedEvents.removeAll { $0.eventId == id }
                    LocalNewsStore.shared.saveV2Saved(savedEvents)
                }
            }
            .navigationDestination(item: $selectedEvent) { event in
                V2EventDetailView(event: event)
            }
            .task {
                await loadSaved()
            }
        }
    }

    private func loadSaved() async {
        isLoading = savedEvents.isEmpty
        if savedEvents.isEmpty {
            let cached = LocalNewsStore.shared.loadV2Saved()
            if !cached.isEmpty {
                self.savedEvents = cached
                self.isLoading = false
            }
        }

        do {
            let fetched = try await APIClient.shared.fetchV2Saved()
            withAnimation(.easeInOut(duration: 0.2)) {
                self.savedEvents = fetched
            }
            LocalNewsStore.shared.saveV2Saved(fetched)
            loadError = nil
        } catch { loadError = "Vos enregistrements n'ont pas pu être actualisés." }
        isLoading = false
    }

    private func removeSaved(_ event: V2Event) {
        guard !removingIds.contains(event.eventId) else { return }
        removingIds.insert(event.eventId)
        Task {
            let success = await APIClient.shared.postV2Interaction(eventId: event.eventId, type: "unsave")
            removingIds.remove(event.eventId)
            if success {
                withAnimation(.easeOut(duration: 0.2)) { savedEvents.removeAll { $0.eventId == event.eventId } }
                LocalNewsStore.shared.saveV2Saved(savedEvents)
                publishSavedState(event, saved: false)
            } else { loadError = "Le retrait n'a pas été confirmé. Réessayez." }
        }
    }
}
