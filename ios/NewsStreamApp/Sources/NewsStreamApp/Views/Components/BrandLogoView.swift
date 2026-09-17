import SwiftUI

public struct BrandLogoView: View {
    public var size: CGFloat = 32

    public init(size: CGFloat = 32) { self.size = size }

    public var body: some View {
        HStack(spacing: 9) {
            Image(systemName: "asterisk")
                .font(.system(size: size * 0.82, weight: .heavy))
                .foregroundStyle(Color.newsPrimary)
                .rotationEffect(.degrees(15))
            Text("MIZAN")
                .font(.system(size: size * 0.72, weight: .black, design: .default))
                .tracking(-0.8)
                .foregroundStyle(Color.primary)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Mizan")
    }
}
