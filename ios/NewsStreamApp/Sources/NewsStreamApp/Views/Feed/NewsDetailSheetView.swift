import SwiftUI

public struct CitationDisplayItem: Identifiable, Equatable {
    public var id: String { key }
    public let key: String
    public let quote: String
    public let source: String?
    public let url: String?
}

public struct NewsDetailSheetView: View {
    public let alert: AlertPayload
    @ObservedObject var viewModel: NewsStreamViewModel
    @ObservedObject private var themeManager = ThemeManager.shared
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @State private var selectedCitation: CitationDisplayItem? = nil
    
    public init(alert: AlertPayload, viewModel: NewsStreamViewModel) {
        self.alert = alert
        self.viewModel = viewModel
    }
    
    private var shareURL: URL {
        if let first = alert.sources.first, let u = URL(string: first.url) {
            return u
        }
        return URL(string: "https://mynews.ai")!
    }
    
    private var shareText: String {
        let bullets = alert.bullet_points.map { "• \($0)" }.joined(separator: "\n")
        return "\(alert.push_title)\n\n\(bullets)\n\nSources : \(shareURL)"
    }
    
    private func attributedParagraph(_ text: String) -> AttributedString {
        // Transform [1], [2] into clickable markdown links [1](citation://$1)
        let formatted = text.replacingOccurrences(
            of: "\\[(\\d+)\\]",
            with: "[$1](citation://$1)",
            options: .regularExpression
        )
        return formatted.toMarkdownAttributedString()
    }

    
    private func handleCitationTap(key: String) {
        HapticsManager.shared.impact(.light)
        if let cit = alert.citations?[key] {
            withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                selectedCitation = CitationDisplayItem(
                    key: key,
                    quote: cit.quote,
                    source: cit.source,
                    url: cit.url
                )
            }
        } else if let intKey = Int(key), intKey > 0, intKey <= alert.sources.count {
            let src = alert.sources[intKey - 1]
            withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                selectedCitation = CitationDisplayItem(
                    key: key,
                    quote: "Information sourcée et recoupée dans la couverture éditoriale de \(src.name).",
                    source: src.name,
                    url: src.url
                )
            }
        }
    }
    
    public var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                Color.paperBackground.ignoresSafeArea()
                
                ScrollView(.vertical, showsIndicators: true) {
                    VStack(alignment: .leading, spacing: 20) {
                        // MARK: - 1. Category & Reliability Header
                        HStack(alignment: .center, spacing: 10) {
                            Text(alert.category.uppercased())
                                .font(AppTypography.mono(size: 11))
                                .fontWeight(.bold)
                                .tracking(1.0)
                                .foregroundColor(.secondary)
                            
                            Circle()
                                .fill(Color.paperBorder)
                                .frame(width: 4, height: 4)
                            
                            HStack(spacing: 4) {
                                Image(systemName: alert.isMultiSource ? "checkmark.seal.fill" : "antenna.radiowaves.left.and.right")
                                    .font(.system(size: 11))
                                    .foregroundColor(alert.isMultiSource ? .blue : .purple)
                                
                                Text(alert.isMultiSource ? "\(alert.sources.count) rédactions recoupées" : "Signal 1 source")
                                    .font(AppTypography.mono(size: 10.5))
                                    .fontWeight(.medium)
                                    .foregroundColor(.primary)
                            }
                            
                            Spacer()
                            
                            Text(alert.formattedDate)
                                .font(AppTypography.mono(size: 10))
                                .foregroundColor(.secondary)
                        }
                        .padding(.top, 4)
                        
                        // MARK: - 2. Editorial Headline (Matches card typography style)
                        Text(alert.push_title.toMarkdownAttributedString())
                            .font(AppTypography.editorialHeadline(size: 22))
                            .foregroundColor(.primary)
                            .lineSpacing(3.5)
                            .fixedSize(horizontal: false, vertical: true)
                        
                        // MARK: - 3. Minimal Discreet Reliability Pill
                        HStack(spacing: 6) {
                            Text(alert.reliabilityEmoji)
                                .font(.system(size: 11))
                            Text(alert.reliability_label.replacingOccurrences(of: "_", with: " ").lowercased().capitalized)
                                .font(AppTypography.mono(size: 10.5))
                                .foregroundColor(.secondary)
                            Text("•")
                                .foregroundColor(.secondary.opacity(0.4))
                            Text("Score \(Int(alert.hybrid_score * 100))%")
                                .font(AppTypography.mono(size: 10.5))
                                .foregroundColor(.secondary)
                            Spacer()
                        }
                        .padding(.vertical, 1)
                        
                        // MARK: - 4. Hero Image (if available)
                        if let imgStr = alert.image_url, let imgURL = URL(string: imgStr), !imgStr.isEmpty {
                            AsyncImage(url: imgURL) { phase in
                                switch phase {
                                case .empty:
                                    Rectangle()
                                        .fill(Color.paperBorder.opacity(0.3))
                                        .aspectRatio(16/9, contentMode: .fit)
                                        .cornerRadius(10)
                                case .success(let image):
                                    image
                                        .resizable()
                                        .aspectRatio(contentMode: .fill)
                                        .frame(maxHeight: 220)
                                        .clipped()
                                        .cornerRadius(10)
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 10)
                                                .stroke(Color.paperBorder.opacity(0.5), lineWidth: 0.8)
                                        )
                                case .failure:
                                    EmptyView()
                                @unknown default:
                                    EmptyView()
                                }
                            }
                        }
                        
                        // MARK: - 5. Complete Story with Interactive Citations [1], [2]
                        let story = alert.detailed_story ?? alert.bullet_points.joined(separator: "\n\n")
                        let paragraphs = story.components(separatedBy: "\n\n").filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
                        
                        VStack(alignment: .leading, spacing: 16) {
                            ForEach(Array(paragraphs.enumerated()), id: \.offset) { _, para in
                                Text(attributedParagraph(para.trimmingCharacters(in: .whitespaces)))
                                    .font(.system(size: 16, weight: .regular))
                                    .foregroundColor(Color.primary.opacity(0.92))
                                    .lineSpacing(5)
                                    .fixedSize(horizontal: false, vertical: true)
                                    .tint(.blue)
                            }
                        }
                        .padding(.vertical, 2)
                        
                        // MARK: - 6. Community Sentiment (if available)
                        if let sentiment = alert.community_sentiment, !sentiment.isEmpty {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("RETOUR GÉNÉRAL")
                                    .font(AppTypography.mono(size: 9))
                                    .fontWeight(.bold)
                                    .foregroundColor(.secondary)
                                
                                Text(sentiment.toMarkdownAttributedString())
                                    .font(AppTypography.meta(size: 13))
                                    .italic()
                                    .foregroundColor(.secondary)
                                    .lineSpacing(3)
                            }
                            .padding(12)
                            .background(Color.paperBorder.opacity(0.2))
                            .cornerRadius(8)
                        }
                        
                        // MARK: - 7. Wikipedia-style Citations & Quotes Section
                        if let citations = alert.citations, !citations.isEmpty {
                            VStack(alignment: .leading, spacing: 10) {
                                HStack(spacing: 6) {
                                    Image(systemName: "quote.bubble.fill")
                                        .font(.system(size: 11))
                                        .foregroundColor(.secondary)
                                    Text("EXTRAITS SOURCES & CITATIONS INTERACTIVES (\(citations.count))")
                                        .font(AppTypography.mono(size: 10.5))
                                        .fontWeight(.bold)
                                        .tracking(0.8)
                                        .foregroundColor(.secondary)
                                }
                                
                                let sortedKeys = citations.keys.sorted { (Int($0) ?? 0) < (Int($1) ?? 0) }
                                ForEach(sortedKeys, id: \.self) { key in
                                    if let cit = citations[key] {
                                        Button {
                                            handleCitationTap(key: key)
                                        } label: {
                                            HStack(alignment: .top, spacing: 8) {
                                                Text("[\(key)]")
                                                    .font(AppTypography.mono(size: 11))
                                                    .fontWeight(.bold)
                                                    .foregroundColor(.blue)
                                                
                                                VStack(alignment: .leading, spacing: 3) {
                                                    Text("“\(cit.quote)”".toMarkdownAttributedString())
                                                        .font(.system(size: 13.5, design: .serif))
                                                        .italic()
                                                        .foregroundColor(.primary)
                                                        .lineLimit(2)
                                                        .multilineTextAlignment(.leading)
                                                    
                                                    if let src = cit.source {
                                                        Text(src)
                                                            .font(AppTypography.meta(size: 11))
                                                            .foregroundColor(.secondary)
                                                    }
                                                }
                                                Spacer()
                                                Image(systemName: "hand.tap")
                                                    .font(.system(size: 12))
                                                    .foregroundColor(.secondary.opacity(0.6))
                                            }
                                            .padding(10)
                                            .background(Color.paperCard)
                                            .cornerRadius(8)
                                            .overlay(
                                                RoundedRectangle(cornerRadius: 8)
                                                    .stroke(Color.paperBorder, lineWidth: 0.8)
                                            )
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }
                            }
                            .padding(.top, 4)
                        }
                        
                        // MARK: - 8. Original Sources List
                        VStack(alignment: .leading, spacing: 10) {
                            Text("SOURCES CONSULTÉES (\(alert.sources.count))")
                                .font(AppTypography.mono(size: 10.5))
                                .fontWeight(.bold)
                                .tracking(0.8)
                                .foregroundColor(.secondary)
                            
                            ForEach(alert.sources) { src in
                                Button(action: {
                                    if let u = URL(string: src.url) {
                                        openURL(u)
                                    }
                                }) {
                                    HStack {
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(src.name)
                                                .font(.system(size: 13.5, weight: .semibold))
                                                .foregroundColor(.primary)
                                            Text(src.domain)
                                                .font(AppTypography.mono(size: 10))
                                                .foregroundColor(.secondary)
                                        }
                                        Spacer()
                                        Image(systemName: "arrow.up.right.square")
                                            .font(.system(size: 14))
                                            .foregroundColor(.secondary)
                                    }
                                    .padding(12)
                                    .background(Color.paperCard)
                                    .cornerRadius(8)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 8)
                                            .stroke(Color.paperBorder.opacity(0.8), lineWidth: 0.8)
                                    )
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        
                        // MARK: - 9. Bottom Dismiss Button ("Appuyer pour sortir")
                        Button(action: {
                            dismiss()
                        }) {
                            HStack(spacing: 6) {
                                Image(systemName: "chevron.down")
                                    .font(.system(size: 12, weight: .bold))
                                Text("Retour")
                                    .font(AppTypography.mono(size: 12.5))
                                    .fontWeight(.semibold)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(Color.primary)
                            .foregroundColor(Color.paperBackground)
                            .cornerRadius(10)
                        }
                        .padding(.top, 10)
                        .padding(.bottom, 60)
                    }
                    .padding(.horizontal, 20)
                }
                
                // MARK: - 10. Floating Interactive Citation Bubble
                if let citation = selectedCitation {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("CITATION [\(citation.key)]")
                                .font(AppTypography.mono(size: 10.5))
                                .fontWeight(.bold)
                                .foregroundColor(.blue)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 3)
                                .background(Color.blue.opacity(0.12))
                                .cornerRadius(4)
                            
                            if let src = citation.source {
                                Text("• \(src)")
                                    .font(AppTypography.editorialSubhead(size: 13))
                                    .fontWeight(.medium)
                                    .foregroundColor(.primary)
                            }
                            
                            Spacer()
                            
                            Button {
                                withAnimation(.easeOut(duration: 0.2)) {
                                    selectedCitation = nil
                                }
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.system(size: 18))
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        Text("“\(citation.quote)”")
                            .font(.system(size: 14, weight: .regular, design: .serif))
                            .italic()
                            .foregroundColor(.primary)
                            .lineSpacing(3)
                            .fixedSize(horizontal: false, vertical: true)
                        
                        if let urlStr = citation.url, let u = URL(string: urlStr) {
                            Button {
                                openURL(u)
                            } label: {
                                HStack(spacing: 5) {
                                    Text("Consulter l'article original")
                                        .font(AppTypography.mono(size: 11.5))
                                        .fontWeight(.semibold)
                                    Image(systemName: "arrow.up.right")
                                        .font(.system(size: 11))
                                }
                                .foregroundColor(.blue)
                                .padding(.top, 2)
                            }
                        }
                    }
                    .padding(16)
                    .background(Color.paperCard)
                    .cornerRadius(14)
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(Color.paperBorder, lineWidth: 1.2)
                    )
                    .shadow(color: Color.black.opacity(0.12), radius: 12, x: 0, y: 6)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 20)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .environment(\.openURL, OpenURLAction { url in
                if url.scheme == "citation" {
                    let key = url.host ?? url.path.replacingOccurrences(of: "/", with: "")
                    handleCitationTap(key: key)
                    return .handled
                }
                return .systemAction
            })
            .inlineNavigationBar()
            .toolbar {
                #if os(iOS)
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: {
                        dismiss()
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.down")
                                .font(.system(size: 12, weight: .bold))
                            Text("Retour")
                                .font(AppTypography.mono(size: 12))
                        }
                        .foregroundColor(.primary)
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    HStack(spacing: 14) {
                        Button(action: {
                            viewModel.toggleBookmark(alert: alert)
                        }) {
                            Image(systemName: viewModel.isBookmarked(alert: alert) ? "bookmark.fill" : "bookmark")
                                .font(.system(size: 15))
                                .foregroundColor(viewModel.isBookmarked(alert: alert) ? .blue : .primary)
                        }
                        
                        ShareLink(item: shareURL, subject: Text(alert.push_title), message: Text(shareText)) {
                            Image(systemName: "square.and.arrow.up")
                                .font(.system(size: 15))
                                .foregroundColor(.primary)
                        }
                    }
                }
                #else
                ToolbarItem(placement: .cancellationAction) {
                    Button(action: {
                        dismiss()
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.down")
                                .font(.system(size: 12, weight: .bold))
                            Text("Retour")
                                .font(AppTypography.mono(size: 12))
                        }
                        .foregroundColor(.primary)
                    }
                }
                
                ToolbarItem(placement: .primaryAction) {
                    HStack(spacing: 14) {
                        Button(action: {
                            viewModel.toggleBookmark(alert: alert)
                        }) {
                            Image(systemName: viewModel.isBookmarked(alert: alert) ? "bookmark.fill" : "bookmark")
                                .font(.system(size: 15))
                                .foregroundColor(viewModel.isBookmarked(alert: alert) ? .blue : .primary)
                        }
                        
                        ShareLink(item: shareURL, subject: Text(alert.push_title), message: Text(shareText)) {
                            Image(systemName: "square.and.arrow.up")
                                .font(.system(size: 15))
                                .foregroundColor(.primary)
                        }
                    }
                }
                #endif
            }
        }
    }
}
