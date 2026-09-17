import SwiftUI

public struct BookmarksView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var searchText: String = ""
    @State private var selectedAlertForDetail: AlertPayload? = nil
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    private var filteredBookmarks: [AlertPayload] {
        if searchText.trimmingCharacters(in: .whitespaces).isEmpty {
            return viewModel.bookmarkedAlerts
        }
        return viewModel.bookmarkedAlerts.filter {
            $0.push_title.localizedCaseInsensitiveContains(searchText) ||
            $0.category.localizedCaseInsensitiveContains(searchText) ||
            $0.bullet_points.joined().localizedCaseInsensitiveContains(searchText)
        }
    }
    
    public var body: some View {
        NavigationStack {
            ZStack {
                Color.paperBackground.ignoresSafeArea()
                
                if viewModel.bookmarkedAlerts.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "bookmark")
                            .font(.system(size: 48))
                            .foregroundColor(.secondary.opacity(0.5))
                        
                        Text("Aucun signet")
                            .font(AppTypography.editorialHeadline(size: 20))
                            .foregroundColor(.primary)
                        
                        Text("Touchez l'icône de signet en haut à droite d'une news pour l'enregistrer dans votre archive personnelle.")
                            .font(AppTypography.meta(size: 13))
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                    }
                } else {
                    ScrollView {
                        LazyVStack(spacing: 16) {
                            ForEach(filteredBookmarks) { alert in
                                TwitterNewsCardView(alert: alert, viewModel: viewModel, onTap: {
                                    selectedAlertForDetail = alert
                                })
                                .padding(.horizontal, 16)
                            }
                        }
                        .padding(.vertical, 16)
                    }
                    .searchable(text: $searchText, prompt: "Rechercher dans mes signets...")
                }
            }
            .navigationTitle("Signets (\(viewModel.bookmarkedAlerts.count))")
            .inlineNavigationBar()
            .sheet(item: $selectedAlertForDetail) { alert in
                NewsDetailSheetView(alert: alert, viewModel: viewModel)
            }
        }
    }
}
