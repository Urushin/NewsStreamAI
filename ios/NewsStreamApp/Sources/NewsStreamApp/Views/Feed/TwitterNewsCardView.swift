import SwiftUI

public struct TwitterNewsCardView: View {
    public let alert: AlertPayload
    @ObservedObject var viewModel: NewsStreamViewModel
    public var isBackgroundCard: Bool = false
    public var onTap: (() -> Void)? = nil
    @Environment(\.openURL) private var openURL
    @ObservedObject private var themeManager = ThemeManager.shared
    
    public init(
        alert: AlertPayload,
        viewModel: NewsStreamViewModel,
        isBackgroundCard: Bool = false,
        onTap: (() -> Void)? = nil
    ) {
        self.alert = alert
        self.viewModel = viewModel
        self.isBackgroundCard = isBackgroundCard
        self.onTap = onTap
    }
    
    private var shareURL: URL {
        if let first = alert.sources.first, let u = URL(string: first.url) {
            return u
        }
        return URL(string: "https://mynews.ai")!
    }
    
    private var shareSubject: String {
        "\(alert.push_title) — MyNews AI"
    }
    
    private var shareMessage: String {
        let bullets = alert.bullet_points.prefix(3).map { "• \($0)" }.joined(separator: "\n")
        return "\(alert.push_title)\n\n\(bullets)\n\nSource(s): \(shareURL)"
    }
    
    private var resolvedImageURL: URL? {
        if let imgStr = alert.image_url, !imgStr.isEmpty, let u = URL(string: imgStr) {
            return u
        }
        let cat = alert.category.lowercased()
        let fallbackStr: String
        if cat.contains("tech") || cat.contains("ia") || cat.contains("science") {
            fallbackStr = "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80"
        } else if cat.contains("politique") || cat.contains("monde") || cat.contains("géo") {
            fallbackStr = "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=800&q=80"
        } else if cat.contains("jeu") || cat.contains("gaming") || cat.contains("esport") {
            fallbackStr = "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=800&q=80"
        } else if cat.contains("manga") || cat.contains("anime") || cat.contains("culture") {
            fallbackStr = "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=800&q=80"
        } else if cat.contains("éco") || cat.contains("finance") || cat.contains("marché") {
            fallbackStr = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=80"
        } else if cat.contains("climat") || cat.contains("planète") || cat.contains("énergie") {
            fallbackStr = "https://images.unsplash.com/photo-1509391365360-2e959784a276?w=800&q=80"
        } else {
            fallbackStr = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&q=80"
        }
        return URL(string: fallbackStr)
    }
    
    private var matchedWatchlistEntity: String? {
        let titleLower = alert.push_title.lowercased()
        let contentLower = alert.bullet_points.joined(separator: " ").lowercased()
        for entity in viewModel.entityWatchlist {
            let ent = entity.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            if !ent.isEmpty && (titleLower.contains(ent) || contentLower.contains(ent)) {
                return entity
            }
        }
        return nil
    }

    public var body: some View {
        Group {
            if isBackgroundCard {
                // MARK: - Ultra-Lightweight Background Preview (Zero Drag Overhead)
                RoundedRectangle(cornerRadius: 16)
                    .fill(Color.paperBackground)
                    .overlay(
                        RoundedRectangle(cornerRadius: 16)
                            .stroke(Color.paperBorder.opacity(0.8), lineWidth: 1)
                    )
            } else {
                // MARK: - Active Foreground Card
                VStack(alignment: .leading, spacing: 11) {
                    // 1. Top Header: Overlapping Source Favicons + Verification + Time + Actions
                    HStack(alignment: .center, spacing: 8) {
                        // Overlapping Source Favicon Badges
                        HStack(spacing: -8) {
                            ForEach(Array(alert.sources.prefix(3).enumerated()), id: \.offset) { index, src in
                                ZStack {
                                    Circle()
                                        .fill(Color.white)
                                        .frame(width: 26, height: 26)
                                    
                                    if !src.domain.isEmpty, let favURL = URL(string: "https://www.google.com/s2/favicons?domain=\(src.domain)&sz=64") {
                                        AsyncImage(url: favURL) { phase in
                                            switch phase {
                                            case .success(let image):
                                                image
                                                    .resizable()
                                                    .aspectRatio(contentMode: .fit)
                                                    .frame(width: 17, height: 17)
                                                    .clipShape(Circle())
                                            default:
                                                Text(String(src.name.prefix(1)).uppercased())
                                                    .font(.system(size: 10.5, weight: .bold, design: .rounded))
                                                    .foregroundColor(.primary)
                                            }
                                        }
                                    } else {
                                        Text(String(src.name.prefix(1)).uppercased())
                                            .font(.system(size: 10.5, weight: .bold, design: .rounded))
                                            .foregroundColor(.primary)
                                    }
                                }
                                .frame(width: 26, height: 26)
                                .overlay(
                                    Circle()
                                        .stroke(Color.paperBackground, lineWidth: 2)
                                )
                                .clipShape(Circle())
                            }
                        }
                        
                        // Consensus info
                        HStack(spacing: 4) {
                            if alert.isMultiSource {
                                Image(systemName: "checkmark.seal.fill")
                                    .font(.system(size: 11.5))
                                    .foregroundColor(.blue)
                                
                                Text("\(alert.sources.count) rédactions")
                                    .font(.system(size: 11.5, weight: .semibold))
                                    .foregroundColor(.primary)
                            } else {
                                Image(systemName: "newspaper")
                                    .font(.system(size: 10.5))
                                    .foregroundColor(.secondary)
                                
                                Text(alert.sources.first?.name ?? "1 source")
                                    .font(.system(size: 11.5, weight: .medium))
                                    .foregroundColor(.primary)
                            }
                            
                            Text("• \(alert.formattedDate)")
                                .font(.system(size: 10.5))
                                .foregroundColor(.secondary)
                        }
                        
                        Spacer()
                        
                        // Bookmark & Native Share
                        HStack(spacing: 12) {
                            Button(action: {
                                viewModel.toggleBookmark(alert: alert)
                            }) {
                                Image(systemName: viewModel.isBookmarked(alert: alert) ? "bookmark.fill" : "bookmark")
                                    .font(.system(size: 14.5))
                                    .foregroundColor(viewModel.isBookmarked(alert: alert) ? .blue : .secondary.opacity(0.8))
                            }
                            .buttonStyle(.plain)
                            
                            ShareLink(item: shareURL, subject: Text(shareSubject), message: Text(shareMessage)) {
                                Image(systemName: "square.and.arrow.up")
                                    .font(.system(size: 13.5))
                                    .foregroundColor(.secondary.opacity(0.8))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    
                    // 2. Synthetic Journalistic Headline & Body (Tapping opens detail sheet)
                    VStack(alignment: .leading, spacing: 10) {
                        if let matched = matchedWatchlistEntity {
                            HStack(spacing: 5) {
                                Image(systemName: "scope")
                                    .font(.system(size: 10, weight: .bold))
                                Text("SUJET SUIVI • \(matched.uppercased())")
                                    .font(.system(size: 10.5, weight: .heavy))
                            }
                            .foregroundColor(.orange)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3.5)
                            .background(Color.orange.opacity(0.14))
                            .cornerRadius(6)
                            .overlay(
                                RoundedRectangle(cornerRadius: 6)
                                    .stroke(Color.orange.opacity(0.4), lineWidth: 1)
                            )
                        }

                        Text(alert.push_title.toMarkdownAttributedString())
                            .font(AppTypography.editorialHeadline(size: 18))
                            .foregroundColor(.primary)
                            .lineSpacing(2.5)
                            .fixedSize(horizontal: false, vertical: true)
                        
                        // 3. Compact Key Points (Uses selected newspaper style, 1 sentence each, Markdown Bold parsed)
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(Array(alert.bullet_points.prefix(3).enumerated()), id: \.offset) { _, point in
                                HStack(alignment: .top, spacing: 7) {
                                    Circle()
                                        .fill(Color.primary.opacity(0.5))
                                        .frame(width: 4.5, height: 4.5)
                                        .padding(.top, 6.5)
                                    
                                    Text(point.toMarkdownAttributedString())
                                        .font(AppTypography.editorialBody(size: 14))
                                        .foregroundColor(.primary.opacity(0.92))
                                        .lineSpacing(2.5)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                        
                        // 4. Media Section (Guaranteed illustration image for EVERY news)
                        if let imgURL = resolvedImageURL {
                            AsyncImage(url: imgURL) { phase in
                                switch phase {
                                case .empty:
                                    Rectangle()
                                        .fill(Color.paperBorder.opacity(0.2))
                                        .aspectRatio(16/9, contentMode: .fit)
                                        .frame(maxHeight: 140)
                                        .cornerRadius(10)
                                case .success(let image):
                                    image
                                        .resizable()
                                        .aspectRatio(contentMode: .fill)
                                        .frame(maxHeight: 140)
                                        .clipped()
                                        .cornerRadius(10)
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 10)
                                                .stroke(Color.paperBorder.opacity(0.5), lineWidth: 0.8)
                                        )
                                case .failure:
                                    Rectangle()
                                        .fill(Color.paperBorder.opacity(0.25))
                                        .aspectRatio(16/9, contentMode: .fit)
                                        .frame(maxHeight: 140)
                                        .cornerRadius(10)
                                        .overlay(
                                            Image(systemName: "newspaper.fill")
                                                .foregroundColor(.secondary.opacity(0.4))
                                        )
                                @unknown default:
                                    EmptyView()
                                }
                            }
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture {
                        onTap?()
                    }
                    
                    // 5. Category Tag & Source Links (Directly clickable, not intercepted)
                    HStack(spacing: 8) {
                        Text(alert.category.uppercased())
                            .font(AppTypography.mono(size: 9))
                            .tracking(0.8)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2.5)
                            .background(Color.paperBorder.opacity(0.35))
                            .cornerRadius(4)
                            .foregroundColor(.secondary)
                        
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 5) {
                                ForEach(alert.sources) { src in
                                    Button(action: {
                                        if let url = URL(string: src.url) {
                                            openURL(url)
                                        }
                                    }) {
                                        HStack(spacing: 3) {
                                            Text(src.name)
                                                .font(AppTypography.mono(size: 10))
                                            Image(systemName: "arrow.up.right")
                                                .font(.system(size: 7))
                                        }
                                        .padding(.horizontal, 7)
                                        .padding(.vertical, 3)
                                        .background(Color.paperBorder.opacity(0.35))
                                        .foregroundColor(.primary)
                                        .cornerRadius(5)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                    }
                }
                .padding(14)
                .background(Color.paperBackground)
                .cornerRadius(16)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.paperBorder, lineWidth: 1)
                )
            }
        }
    }
    
    private func sourceColor(index: Int) -> Color {
        let colors = [
            Color(hex: "#1E293B"),
            Color(hex: "#334155"),
            Color(hex: "#475569"),
            Color(hex: "#0F172A")
        ]
        return colors[index % colors.count]
    }
}
