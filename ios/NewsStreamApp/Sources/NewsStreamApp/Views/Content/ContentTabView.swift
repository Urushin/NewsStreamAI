import SwiftUI

public struct ContentTabView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @Environment(\.openURL) private var openURL
    @State private var showingAddSheet = false
    @State private var filter = "Tout"

    public init(viewModel: NewsStreamViewModel) { self.viewModel = viewModel }

    public var body: some View {
        NavigationStack {
            ScrollView(showsIndicators: false) {
                LazyVStack(alignment: .leading, spacing: 22) {
                    VStack(alignment: .leading, spacing: 9) {
                        Text("Au-delà des titres.")
                            .font(.system(size: 34, weight: .regular, design: .serif)).tracking(-1)
                        Text("Les vidéos, les idées et les nouveautés de vos créateurs favoris.")
                            .font(.system(size: 13)).foregroundStyle(.secondary)
                    }.padding(.top, 12)
                    HStack(spacing: 8) {
                        ForEach(["Tout", "Vidéos", "Sorties"], id: \.self) { value in
                            Button { filter = value } label: {
                                Text(value).font(.system(size: 12, weight: .semibold))
                                    .padding(.horizontal, 17).padding(.vertical, 10)
                                    .foregroundStyle(filter == value ? Color.white : Color.secondary)
                                    .background(filter == value ? Color.newsPrimary : Color.paperCard, in: Capsule())
                            }.buttonStyle(.plain)
                        }
                    }
                    if let error = viewModel.contentError {
                        VStack(alignment: .leading, spacing: 10) {
                            Label(error, systemImage: "wifi.exclamationmark")
                                .font(.system(size: 13)).foregroundStyle(.secondary)
                            Button("Réessayer") { Task { await viewModel.loadContentFeed() } }
                                .font(.system(size: 13, weight: .semibold))
                        }.padding(18).background(Color.paperCard, in: RoundedRectangle(cornerRadius: 20))
                    }
                    if viewModel.isContentLoading {
                        ProgressView("Actualisation de vos contenus…").font(.system(size: 13))
                            .frame(maxWidth: .infinity).padding()
                    }
                    if !viewModel.trackedTwitterAccounts.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Vos comptes suivis").font(.system(size: 14, weight: .semibold))
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 8) {
                                    ForEach(viewModel.trackedTwitterAccounts, id: \.self) { account in
                                        Text("@\(account)").font(.system(size: 12, weight: .medium))
                                            .padding(.horizontal, 14).padding(.vertical, 10)
                                            .background(Color.paperCard, in: Capsule())
                                    }
                                }
                            }
                        }
                    }
                    if filter != "Sorties" {
                        sectionHeading("À regarder", count: viewModel.contentVideos.count, icon: "play.rectangle")
                        if viewModel.contentVideos.isEmpty && !viewModel.isContentLoading {
                            emptyPrompt("Vos prochaines découvertes commencent ici.", text: "Ajoutez une chaîne YouTube pour retrouver ses nouvelles vidéos.")
                        }
                        ForEach(viewModel.contentVideos) { video in
                            Button { openSource(video.url) } label: {
                                VStack(alignment: .leading, spacing: 13) {
                                    AsyncImage(url: URL(string: video.thumbnail_url)) { phase in
                                        if case .success(let image) = phase {
                                            image.resizable().scaledToFill().frame(height: 190).frame(maxWidth: .infinity).clipped()
                                        } else {
                                            Color.newsPrimary.opacity(0.08).frame(height: 190)
                                        }
                                    }
                                    .overlay {
                                        Image(systemName: "play.fill").font(.system(size: 19)).foregroundStyle(.white)
                                            .padding(20).background(.black.opacity(0.4), in: Circle())
                                    }
                                    .clipShape(RoundedRectangle(cornerRadius: 18))
                                    Text(video.channel_name).font(.system(size: 11, weight: .semibold)).foregroundStyle(Color.newsPrimary)
                                    Text(video.title).font(.system(size: 19, weight: .semibold))
                                        .foregroundStyle(.primary).multilineTextAlignment(.leading).lineLimit(3)
                                    Label("Regarder sur YouTube", systemImage: "arrow.up.right")
                                        .font(.system(size: 11)).foregroundStyle(.secondary)
                                }.padding(18).background(Color.paperCard, in: RoundedRectangle(cornerRadius: 25))
                            }.buttonStyle(.plain)
                        }
                    }
                    if filter != "Vidéos" {
                        sectionHeading("À découvrir", count: viewModel.contentReleases.count, icon: "sparkles")
                        if viewModel.contentReleases.isEmpty && !viewModel.isContentLoading {
                            emptyPrompt("Gardez une longueur d'avance.", text: "Suivez vos applications et projets pour retrouver leurs dernières sorties.")
                        }
                        ForEach(viewModel.contentReleases) { release in
                            VStack(alignment: .leading, spacing: 14) {
                                HStack(spacing: 12) {
                                    Image(systemName: release.icon_name ?? "cube")
                                        .font(.system(size: 20)).foregroundStyle(Color.newsPrimary)
                                        .frame(width: 45, height: 45)
                                        .background(Color.newsPrimary.opacity(0.08), in: RoundedRectangle(cornerRadius: 13))
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(release.product_name).font(.system(size: 16, weight: .semibold))
                                        Text(release.version).font(.system(size: 11)).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    Text(release.category).font(.system(size: 9, weight: .medium)).foregroundStyle(Color.newsPrimary)
                                        .padding(8).background(Color.newsPrimary.opacity(0.07), in: Capsule())
                                }
                                Text(LocalizedStringKey(release.summary_ai)).font(.system(size: 14)).lineSpacing(4)
                                    .foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                                Button { openSource(release.source_url) } label: {
                                    Label("Voir l'annonce officielle", systemImage: "arrow.up.right")
                                        .font(.system(size: 12, weight: .semibold))
                                }.buttonStyle(.plain)
                            }.padding(19).background(Color.paperCard, in: RoundedRectangle(cornerRadius: 24))
                        }
                    }
                }.padding(.horizontal, 18).padding(.bottom, 20)
            }
            .background(Color.paperBackground)
            .refreshable { await viewModel.loadContentFeed() }
            .navigationTitle("Vidéos & sorties").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingAddSheet = true } label: { Image(systemName: "plus.circle.fill").font(.system(size: 23)) }
                        .accessibilityLabel("Ajouter une chaîne ou un projet")
                }
            }
            .sheet(isPresented: $showingAddSheet) { AddTrackedEntitySheet(viewModel: viewModel) }
            .task { await viewModel.loadContentFeed() }
        }
    }

    private func sectionHeading(_ title: String, count: Int, icon: String) -> some View {
        HStack {
            Label(title, systemImage: icon).font(.system(size: 17, weight: .semibold))
            Spacer()
            Text("\(count)").font(.system(size: 12, weight: .medium)).foregroundStyle(.secondary)
        }
    }

    private func emptyPrompt(_ title: String, text: String) -> some View {
        VStack(alignment: .leading, spacing: 11) {
            Text(title).font(.system(size: 18, weight: .regular, design: .serif))
            Text(text).font(.system(size: 13)).foregroundStyle(.secondary)
            Button("Ajouter à ma bibliothèque") { showingAddSheet = true }
                .font(.system(size: 12, weight: .semibold))
        }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.paperCard, in: RoundedRectangle(cornerRadius: 24))
    }

    private func openSource(_ string: String) {
        guard let url = URL(string: string), ["https", "http"].contains(url.scheme?.lowercased() ?? "") else { return }
        openURL(url)
    }
}
