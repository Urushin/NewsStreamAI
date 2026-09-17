import SwiftUI

public struct ConsensusBadgeView: View {
    public let sourceCount: Int
    
    public init(sourceCount: Int) {
        self.sourceCount = sourceCount
    }
    
    public var body: some View {
        HStack(spacing: 4) {
            if sourceCount >= 4 {
                Text("🚨")
                Text("\(sourceCount) SOURCES • CONSENSUS MAJEUR")
                    .font(AppTypography.mono(size: 10))
                    .fontWeight(.bold)
            } else if sourceCount == 3 {
                Text("🔥")
                Text("3 SOURCES • CONFIRMÉ")
                    .font(AppTypography.mono(size: 10))
                    .fontWeight(.bold)
            } else if sourceCount == 2 {
                Text("⚡")
                Text("2 SOURCES • RECOUPÉ")
                    .font(AppTypography.mono(size: 10))
                    .fontWeight(.bold)
            } else {
                Text("🟣")
                Text("1 SOURCE ISOLÉE")
                    .font(AppTypography.mono(size: 10))
                    .fontWeight(.bold)
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(badgeBackground)
        .foregroundColor(badgeForeground)
        .cornerRadius(6)
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(badgeBorder, lineWidth: 1)
        )
    }
    
    private var badgeBackground: Color {
        if sourceCount >= 4 {
            return Color.red.opacity(0.15)
        } else if sourceCount == 3 {
            return Color.orange.opacity(0.15)
        } else if sourceCount == 2 {
            return Color.blue.opacity(0.15)
        } else {
            return Color.purple.opacity(0.15)
        }
    }
    
    private var badgeForeground: Color {
        if sourceCount >= 4 {
            return Color.red
        } else if sourceCount == 3 {
            return Color.orange
        } else if sourceCount == 2 {
            return Color.blue
        } else {
            return Color.purple
        }
    }
    
    private var badgeBorder: Color {
        if sourceCount >= 4 {
            return Color.red.opacity(0.4)
        } else if sourceCount == 3 {
            return Color.orange.opacity(0.4)
        } else if sourceCount == 2 {
            return Color.blue.opacity(0.4)
        } else {
            return Color.purple.opacity(0.4)
        }
    }
}
