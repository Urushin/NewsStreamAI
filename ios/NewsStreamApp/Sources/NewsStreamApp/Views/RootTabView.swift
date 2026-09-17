import SwiftUI

public struct RootTabView: View {
    @StateObject private var viewModel = NewsStreamViewModel()
    @StateObject private var themeManager = ThemeManager.shared
    @AppStorage("mynews_selected_tab_v2") private var selectedTab = 0
    @State private var visitedTabs: Set<Int> = [0]
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Namespace private var navigationAnimation

    public init() {}

    public var body: some View {
        ZStack {
            V2EventFeedView(viewModel: viewModel, isActive: selectedTab == 0)
                .opacity(selectedTab == 0 ? 1 : 0)
                .allowsHitTesting(selectedTab == 0)
                .accessibilityHidden(selectedTab != 0)
            if visitedTabs.contains(2) {
                GlobeMapView(viewModel: viewModel)
                    .opacity(selectedTab == 2 ? 1 : 0)
                    .allowsHitTesting(selectedTab == 2)
                    .accessibilityHidden(selectedTab != 2)
                    .ignoresSafeArea()
            }
            if selectedTab == 3 {
                MizanLibraryView(viewModel: viewModel)
            }
            if selectedTab == 4 {
                ProfileSettingsView(viewModel: viewModel)
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            HStack(spacing: 2) {
                tabButton(tag: 0, title: "News", icon: "text.alignleft")
                tabButton(tag: 2, title: "Globe", icon: "globe.europe.africa")
                tabButton(tag: 3, title: "Bibliothèque", icon: "square.stack")
                tabButton(tag: 4, title: "Profil", icon: "person.crop.circle")
            }
            .padding(7)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 28))
            .shadow(color: Color.black.opacity(0.08), radius: 20, x: 0, y: 7)
            .padding(.horizontal, 16)
            .padding(.vertical, 7)
        }
        .background(Color.paperBackground.ignoresSafeArea())
        .tint(Color.newsPrimary)
        .preferredColorScheme(themeManager.selectedColorScheme)
        .onAppear {
            if let initial = ProcessInfo.processInfo.environment["MYNEWS_INITIAL_TAB"].flatMap(Int.init) {
                selectedTab = initial
            }
            if selectedTab == 1 { selectedTab = 3 }
            if ![0, 2, 3, 4].contains(selectedTab) { selectedTab = 0 }
            visitedTabs.insert(selectedTab)
        }
    }

    private func tabButton(tag: Int, title: String, icon: String) -> some View {
        Button {
            HapticsManager.shared.impact(.soft)
            visitedTabs.insert(tag)
            withAnimation(reduceMotion ? nil : .spring(response: 0.32, dampingFraction: 0.85)) {
                selectedTab = tag
            }
        } label: {
            VStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 19, weight: selectedTab == tag ? .semibold : .regular))
                Text(title).font(.system(size: 10, weight: .semibold))
            }
            .foregroundStyle(selectedTab == tag ? Color.newsPrimary : Color.secondary)
            .frame(maxWidth: .infinity)
            .frame(height: 49)
            .background {
                if selectedTab == tag {
                    RoundedRectangle(cornerRadius: 21)
                        .fill(Color.newsPrimary.opacity(0.1))
                        .matchedGeometryEffect(id: "tab", in: navigationAnimation)
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selectedTab == tag ? [.isSelected] : [])
    }
}

private struct MizanLibraryView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var section = 0

    var body: some View {
        VStack(spacing: 0) {
            Picker("Bibliothèque", selection: $section) {
                Text("Enregistrés").tag(0)
                Text("Vidéos & sorties").tag(1)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 20)
            .padding(.top, 12)
            .padding(.bottom, 8)
            if section == 0 { V2SavedView() }
            else { ContentTabView(viewModel: viewModel) }
        }
        .background(Color.paperBackground)
    }
}
