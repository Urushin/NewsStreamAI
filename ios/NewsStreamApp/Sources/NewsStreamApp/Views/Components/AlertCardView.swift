import SwiftUI

public struct AlertCardView: View {
    public let alert: AlertPayload
    public let onFeedback: (Bool) -> Void
    
    @State private var isExplainerExpanded: Bool = true
    
    public init(alert: AlertPayload, onFeedback: @escaping (Bool) -> Void) {
        self.alert = alert
        self.onFeedback = onFeedback
    }
    
    public var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            // Header: Badges & Timestamp
            HStack(alignment: .center, spacing: 6) {
                ConsensusBadgeView(sourceCount: alert.sources.count)
                
                if alert.was_clickbait_enhanced == true {
                    HStack(spacing: 3) {
                        Image(systemName: "wand.and.stars")
                        Text("Titre clarifié")
                    }
                    .font(AppTypography.mono(size: 10))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 4)
                    .background(Color.blue.opacity(0.12))
                    .foregroundColor(.blue)
                    .cornerRadius(6)
                }
                
                Spacer()
                
                Text(alert.formattedDate)
                    .font(AppTypography.mono(size: 11))
                    .foregroundColor(.secondary)
            }
            
            if alert.isBreaking {
                HStack(spacing: 5) {
                    Image(systemName: "flame.fill")
                        .foregroundColor(.red)
                        .font(.system(size: 10))
                    Text((alert.is_fast_track ?? false) ? "FLASH FAST-TRACK" : "BREAKING")
                        .font(AppTypography.mono(size: 10))
                        .fontWeight(.bold)
                        .foregroundColor(.red)
                    if let entities = alert.matched_entities, !entities.isEmpty {
                        Text("• #\(entities[0])")
                            .font(AppTypography.mono(size: 10))
                            .foregroundColor(.red.opacity(0.85))
                    }
                    Spacer()
                    if let buzz = alert.buzz_score, buzz > 0.3 {
                        Text("🔥 \(Int(buzz * 100))% BUZZ")
                            .font(AppTypography.mono(size: 9))
                            .fontWeight(.bold)
                            .foregroundColor(.orange)
                    }
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.red.opacity(0.08))
                .cornerRadius(6)
            }
            
            // Headline (Editorial Serif)
            Text(alert.push_title.toMarkdownAttributedString())
                .font(AppTypography.editorialHeadline(size: 19))
                .foregroundColor(.primary)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
            
            // Context Explainer (Pour comprendre / Éclairage éditorial)
            if let explainer = alert.context_explainer, !explainer.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 5) {
                        Image(systemName: "lightbulb.fill")
                            .foregroundColor(.purple)
                            .font(.system(size: 12))
                        Text("Éclairage éditorial")
                            .font(AppTypography.meta(size: 12))
                            .fontWeight(.bold)
                            .foregroundColor(.purple)
                    }
                    Text(explainer.toMarkdownAttributedString())
                        .font(AppTypography.meta(size: 13))
                        .foregroundColor(.primary.opacity(0.85))
                        .lineSpacing(2)
                }
                .padding(12)
                .background(Color.purple.opacity(0.08))
                .cornerRadius(10)
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(Color.purple.opacity(0.2), lineWidth: 1)
                )
            }
            
            // Bullet points
            VStack(alignment: .leading, spacing: 8) {
                ForEach(alert.bullet_points, id: \.self) { bullet in
                    HStack(alignment: .top, spacing: 8) {
                        Circle()
                            .fill(Color.blue)
                            .frame(width: 5, height: 5)
                            .padding(.top, 6)
                        Text(bullet.toMarkdownAttributedString())
                            .font(AppTypography.editorialBody(size: 14))
                            .foregroundColor(.primary.opacity(0.9))
                            .lineSpacing(3)
                    }
                }
            }
            
            // Community Sentiment / Debates
            if let sentiment = alert.community_sentiment, !sentiment.isEmpty {
                VStack(alignment: .leading, spacing: 5) {
                    HStack(spacing: 5) {
                        Image(systemName: "bubble.left.and.bubble.right.fill")
                            .foregroundColor(.orange)
                            .font(.system(size: 11))
                        Text("Débats & Sentiment Communautaire")
                            .font(AppTypography.meta(size: 11))
                            .fontWeight(.bold)
                            .foregroundColor(.orange)
                    }
                    Text(sentiment.toMarkdownAttributedString())
                        .font(AppTypography.meta(size: 12))
                        .foregroundColor(.primary.opacity(0.85))
                }
                .padding(10)
                .background(Color.orange.opacity(0.08))
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Color.orange.opacity(0.2), lineWidth: 1)
                )
            }
            
            Divider()
                .padding(.vertical, 2)
            
            // Sources & Feedback Action Buttons
            HStack(alignment: .center, spacing: 8) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(alert.sources) { src in
                            if let url = URL(string: src.url) {
                                Link(destination: url) {
                                    HStack(spacing: 4) {
                                        Image(systemName: "arrow.up.right")
                                            .font(.system(size: 8))
                                        Text(src.name)
                                            .font(AppTypography.meta(size: 11))
                                    }
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(Color.paperBorder.opacity(0.5))
                                    .foregroundColor(.secondary)
                                    .cornerRadius(6)
                                }
                            }
                        }
                    }
                }
                
                Spacer()
                
                // Feedback Buttons
                HStack(spacing: 8) {
                    Button(action: {
                        onFeedback(true)
                    }) {
                        Image(systemName: "hand.thumbsup")
                            .font(.system(size: 13))
                            .padding(7)
                            .background(Color.paperBorder.opacity(0.4))
                            .foregroundColor(.secondary)
                            .clipShape(Circle())
                    }
                    
                    Button(action: {
                        onFeedback(false)
                    }) {
                        Image(systemName: "hand.thumbsdown")
                            .font(.system(size: 13))
                            .padding(7)
                            .background(Color.paperBorder.opacity(0.4))
                            .foregroundColor(.secondary)
                            .clipShape(Circle())
                    }
                }
            }
        }
        .padding(16)
        .background(Color.paperCard)
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(alert.isBreaking ? Color.red.opacity(0.5) : Color.paperBorder, lineWidth: alert.isBreaking ? 1.5 : 1)
        )
        .shadow(color: alert.isBreaking ? Color.red.opacity(0.08) : Color.black.opacity(0.04), radius: 6, x: 0, y: 2)
    }
}
