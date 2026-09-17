import SwiftUI

public enum SourceFilterTab: String, CaseIterable, Identifiable {
    case all = "Tous"
    case active = "Actifs"
    case blocked = "Bloqués"
    case errors = "Erreurs"
    
    public var id: String { rawValue }
}

public enum SourceSortOption: String, CaseIterable, Identifiable {
    case name = "Nom (A-Z)"
    case itemsFetched = "News reçues ↓"
    case latency = "Latence ↑"
    
    public var id: String { rawValue }
}

public struct SourceHealthView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var searchText: String = ""
    @State private var selectedTab: SourceFilterTab = .all
    @State private var sortOption: SourceSortOption = .name
    @State private var selectedSourceForDetail: FeedHealthItem? = nil
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var filteredSources: [FeedHealthItem] {
        guard let report = viewModel.sourceHealthReport else { return [] }
        
        let filtered = report.sources.filter { src in
            // Search text match
            let matchesSearch = searchText.isEmpty ||
                src.name.localizedCaseInsensitiveContains(searchText) ||
                (src.owner?.localizedCaseInsensitiveContains(searchText) ?? false) ||
                (src.orientation?.localizedCaseInsensitiveContains(searchText) ?? false)
            guard matchesSearch else { return false }
            
            let isBlocked = viewModel.isSourceBlocked(name: src.name)
            
            // Tab filter
            switch selectedTab {
            case .all:
                return true
            case .active:
                return !isBlocked && src.isOk
            case .blocked:
                return isBlocked
            case .errors:
                return !src.isOk
            }
        }
        
        // Sorting
        switch sortOption {
        case .name:
            return filtered.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        case .itemsFetched:
            return filtered.sorted { ($0.total_items_fetched ?? 0) > ($1.total_items_fetched ?? 0) }
        case .latency:
            return filtered.sorted { ($0.avg_latency_ms ?? 9999) < ($1.avg_latency_ms ?? 9999) }
        }
    }
    
    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    // MARK: - 1. Summary KPIs
                    if let report = viewModel.sourceHealthReport {
                        HStack(spacing: 8) {
                            KPIBox(title: "TOTAL", value: "\(report.total_tracked)", color: .blue)
                            KPIBox(title: "SANTÉ", value: "\(String(format: "%.0f%%", report.health_percentage))", color: .green)
                            KPIBox(title: "BLOQUÉS", value: "\(viewModel.blockedSources.count)", color: .orange)
                            KPIBox(title: "ERREURS", value: "\(report.error_count)", color: .red)
                        }
                        .padding(.horizontal, 16)
                    }
                    
                    // MARK: - 2. Filter Tabs
                    Picker("Filtre", selection: $selectedTab) {
                        ForEach(SourceFilterTab.allCases) { tab in
                            Text(tab.rawValue).tag(tab)
                        }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal, 16)
                    
                    // MARK: - 3. Sort Picker & Count
                    HStack {
                        Text("\(filteredSources.count) flux affichés")
                            .font(AppTypography.mono(size: 11))
                            .foregroundColor(.secondary)
                        Spacer()
                        Menu {
                            Picker("Trier par", selection: $sortOption) {
                                ForEach(SourceSortOption.allCases) { opt in
                                    Text(opt.rawValue).tag(opt)
                                }
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: "arrow.up.arrow.down")
                                    .font(.system(size: 11))
                                Text(sortOption.rawValue)
                                    .font(AppTypography.mono(size: 11))
                            }
                            .foregroundColor(.blue)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.paperBorder.opacity(0.3))
                            .cornerRadius(6)
                        }
                    }
                    .padding(.horizontal, 16)
                    
                    // MARK: - 4. Feed Items List
                    LazyVStack(spacing: 8) {
                        ForEach(filteredSources) { src in
                            FeedHealthRow(
                                item: src,
                                isBlocked: viewModel.isSourceBlocked(name: src.name),
                                onTap: {
                                    HapticsManager.shared.impact(.light)
                                    selectedSourceForDetail = src
                                },
                                onToggleBlock: {
                                    viewModel.toggleBlockSource(name: src.name)
                                }
                            )
                        }
                    }
                    .padding(.horizontal, 16)
                }
                .padding(.vertical, 12)
            }
            .background(Color.paperBackground)
            .navigationTitle("Santé & Gestion des Flux")
            .inlineNavigationBar()
            .searchable(text: $searchText, prompt: "Rechercher une source ou un propriétaire...")
            .refreshable {
                await viewModel.loadSourceHealth()
            }
            .sheet(item: $selectedSourceForDetail) { item in
                SourceDetailSheetView(
                    item: item,
                    isBlocked: viewModel.isSourceBlocked(name: item.name),
                    onToggleBlock: {
                        viewModel.toggleBlockSource(name: item.name)
                    }
                )
            }
        }
    }
}

public struct KPIBox: View {
    public let title: String
    public let value: String
    public let color: Color
    
    public init(title: String, value: String, color: Color) {
        self.title = title
        self.value = value
        self.color = color
    }
    
    public var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(AppTypography.mono(size: 8.5))
                .foregroundColor(.secondary)
            Text(value)
                .font(AppTypography.mono(size: 14))
                .fontWeight(.bold)
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(9)
        .background(Color.paperCard)
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.paperBorder, lineWidth: 1)
        )
    }
}

public struct FeedHealthRow: View {
    public let item: FeedHealthItem
    public let isBlocked: Bool
    public let onTap: () -> Void
    public let onToggleBlock: () -> Void
    
    public init(
        item: FeedHealthItem,
        isBlocked: Bool,
        onTap: @escaping () -> Void,
        onToggleBlock: @escaping () -> Void
    ) {
        self.item = item
        self.isBlocked = isBlocked
        self.onTap = onTap
        self.onToggleBlock = onToggleBlock
    }
    
    public var body: some View {
        HStack(alignment: .center, spacing: 10) {
            // Source Name, Owner & Status
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(item.name)
                        .font(AppTypography.editorialSubhead(size: 14))
                        .foregroundColor(isBlocked ? .secondary : .primary)
                        .strikethrough(isBlocked)
                        .lineLimit(1)
                    
                    if let owner = item.owner {
                        Text(owner)
                            .font(AppTypography.mono(size: 8))
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1.5)
                            .background(Color.paperBorder.opacity(0.6))
                            .foregroundColor(.secondary)
                            .cornerRadius(3)
                            .lineLimit(1)
                    }
                    
                    if isBlocked {
                        Text("Bloqué")
                            .font(AppTypography.mono(size: 8.5))
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .background(Color.red.opacity(0.15))
                            .foregroundColor(.red)
                            .cornerRadius(4)
                    } else if item.isQuarantined {
                        Text("Quarantaine")
                            .font(AppTypography.mono(size: 8.5))
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .background(Color.orange.opacity(0.15))
                            .foregroundColor(.orange)
                            .cornerRadius(4)
                    }
                }
                
                Text(isBlocked ? "Source mise en sourdine" : (item.last_error ?? item.orientation ?? "Opérationnel"))
                    .font(AppTypography.meta(size: 11))
                    .foregroundColor(isBlocked ? .secondary.opacity(0.6) : .secondary)
                    .lineLimit(1)
            }
            
            Spacer()
            
            // Latency & fetched count
            if !isBlocked {
                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(Int(item.avg_latency_ms ?? 0))ms")
                        .font(AppTypography.mono(size: 10.5))
                        .foregroundColor(.secondary)
                    Text("\(item.total_items_fetched ?? 0) news")
                        .font(AppTypography.mono(size: 9))
                        .foregroundColor(.secondary.opacity(0.7))
                }
                
                Text(item.isOk ? "OK" : "ERR")
                    .font(AppTypography.mono(size: 9.5))
                    .fontWeight(.bold)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(item.isOk ? Color.green.opacity(0.15) : Color.red.opacity(0.15))
                    .foregroundColor(item.isOk ? Color.green : Color.red)
                    .cornerRadius(6)
            }
            
            // Block / Unblock Toggle Button
            Button(action: onToggleBlock) {
                Image(systemName: isBlocked ? "eye.slash.fill" : "nosign")
                    .font(.system(size: 13))
                    .foregroundColor(isBlocked ? .red : .secondary.opacity(0.5))
                    .padding(8)
                    .background(isBlocked ? Color.red.opacity(0.1) : Color.paperBorder.opacity(0.3))
                    .clipShape(Circle())
            }
            .buttonStyle(.plain)
        }
        .contentShape(Rectangle())
        .onTapGesture {
            onTap()
        }
        .padding(11)
        .background(isBlocked ? Color.paperCard.opacity(0.5) : Color.paperCard)
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(isBlocked ? Color.red.opacity(0.2) : Color.paperBorder, lineWidth: 1)
        )
    }
}
