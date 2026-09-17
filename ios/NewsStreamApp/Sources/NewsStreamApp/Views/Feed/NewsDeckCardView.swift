import SwiftUI

public struct NewsDeckCardView: View {
    public let alert: AlertPayload
    @Environment(\.openURL) private var openURL
    
    public init(alert: AlertPayload) {
        self.alert = alert
    }
    
    public var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            // Top Metadata Bar: Category + Reliability Badge
            HStack(alignment: .center) {
                HStack(spacing: 6) {
                    Circle()
                        .fill(Color.primary.opacity(0.7))
                        .frame(width: 5, height: 5)
                    Text(alert.category.uppercased())
                        .font(AppTypography.mono(size: 11))
                        .tracking(1.2)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                HStack(spacing: 4) {
                    Text(alert.reliabilityEmoji)
                    Text(alert.reliability_label.replacingOccurrences(of: "_", with: " ").capitalized)
                        .font(AppTypography.mono(size: 10))
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(Color.paperBorder.opacity(0.4))
                .cornerRadius(6)
            }
            
            // 🔥 Breaking / Fast-Track Alert Banner
            if alert.isBreaking {
                HStack(spacing: 6) {
                    Image(systemName: "flame.fill")
                        .foregroundColor(.red)
                    Text((alert.is_fast_track ?? false) ? "FLASH FAST-TRACK" : "BREAKING")
                        .font(AppTypography.mono(size: 11))
                        .fontWeight(.bold)
                        .foregroundColor(.red)
                    if let entities = alert.matched_entities, !entities.isEmpty {
                        Text("• #\(entities[0])")
                            .font(AppTypography.mono(size: 11))
                            .foregroundColor(.red.opacity(0.85))
                    }
                    Spacer()
                    if let buzz = alert.buzz_score, buzz > 0.3 {
                        Text("🔥 \(Int(buzz * 100))% BUZZ")
                            .font(AppTypography.mono(size: 10))
                            .fontWeight(.bold)
                            .foregroundColor(.orange)
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Color.red.opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Color.red.opacity(0.35), lineWidth: 1)
                )
                .cornerRadius(8)
            }
            
            // Editorial Headline (Serif)
            Text(alert.push_title.toMarkdownAttributedString())
                .font(AppTypography.editorialHeadline(size: 24))
                .foregroundColor(.primary)
                .lineSpacing(5)
                .fixedSize(horizontal: false, vertical: true)
            
            // Subtle Hairline Divider
            Rectangle()
                .fill(Color.paperBorder.opacity(0.7))
                .frame(height: 1)
            
            // Bullet Points
            VStack(alignment: .leading, spacing: 14) {
                ForEach(Array(alert.bullet_points.enumerated()), id: \.offset) { _, point in
                    HStack(alignment: .top, spacing: 10) {
                        Circle()
                            .fill(Color.primary.opacity(0.4))
                            .frame(width: 5, height: 5)
                            .padding(.top, 7)
                        
                        Text(point.toMarkdownAttributedString())
                            .font(AppTypography.editorialBody(size: 15))
                            .foregroundColor(.primary.opacity(0.9))
                            .lineSpacing(4)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            
            // Community Sentiment / Synthesis note if present
            if let sentiment = alert.community_sentiment, !sentiment.isEmpty {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "bubble.left.and.bubble.right")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                        .padding(.top, 2)
                    Text(sentiment.toMarkdownAttributedString())
                        .font(AppTypography.meta(size: 12))
                        .foregroundColor(.secondary)
                        .italic()
                        .lineSpacing(2)
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.paperBorder.opacity(0.25))
                .cornerRadius(8)
            }
            
            Spacer(minLength: 10)
            
            // Sources Cluster Section (Tappable links)
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("SOURCES CONVERGENTES (\(alert.sources.count))")
                        .font(AppTypography.mono(size: 10))
                        .foregroundColor(.secondary)
                    Spacer()
                    Text("Toucher pour lire l'article source")
                        .font(AppTypography.mono(size: 9))
                        .foregroundColor(.secondary.opacity(0.8))
                }
                
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(alert.sources) { src in
                            Button(action: {
                                if let url = URL(string: src.url) {
                                    openURL(url)
                                }
                            }) {
                                HStack(spacing: 5) {
                                    Image(systemName: "newspaper.fill")
                                        .font(.system(size: 9))
                                    Text(src.name)
                                        .font(AppTypography.mono(size: 11))
                                    Image(systemName: "arrow.up.right")
                                        .font(.system(size: 8))
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(Color.paperBorder.opacity(0.5))
                                .foregroundColor(.primary)
                                .cornerRadius(8)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            
            // Footer: Timestamp + Velocity / Consensus Score
            HStack {
                HStack(spacing: 4) {
                    Image(systemName: "clock")
                        .font(.system(size: 10))
                    Text(alert.formattedDate)
                        .font(AppTypography.mono(size: 11))
                }
                .foregroundColor(.secondary)
                
                Spacer()
                
                HStack(spacing: 4) {
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.system(size: 10))
                    Text("Consensus \(Int(alert.hybrid_score * 100))%")
                        .font(AppTypography.mono(size: 11))
                }
                .foregroundColor(alert.isMultiSource ? .blue : .secondary)
            }
        }
        .padding(22)
        .background(Color.paperBackground)
        .cornerRadius(20)
        .overlay(
            RoundedRectangle(cornerRadius: 20)
                .stroke(alert.isBreaking ? Color.red.opacity(0.6) : Color.paperBorder, lineWidth: alert.isBreaking ? 2 : 1)
        )
        .shadow(color: alert.isBreaking ? Color.red.opacity(0.12) : Color.black.opacity(0.06), radius: alert.isBreaking ? 20 : 15, x: 0, y: 6)
    }
}
