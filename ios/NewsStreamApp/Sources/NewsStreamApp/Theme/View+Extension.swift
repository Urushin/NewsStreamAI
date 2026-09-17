import SwiftUI

public extension View {
    @ViewBuilder
    func inlineNavigationBar() -> some View {
        #if os(iOS)
        self.navigationBarTitleDisplayMode(.inline)
        #else
        self
        #endif
    }
    
    @ViewBuilder
    func platformAutocapitalizationNone() -> some View {
        #if os(iOS)
        self.textInputAutocapitalization(.never)
        #else
        self
        #endif
    }
}

public extension String {
    func toMarkdownAttributedString() -> AttributedString {
        var s = self
        // Normalize loose spaces before/after asterisks so markdown parsers treat them as formatting rather than literal
        s = s.replacingOccurrences(of: #"\*\*([^\*\n]+?)\s+\*\*"#, with: "**$1** ", options: .regularExpression)
        s = s.replacingOccurrences(of: #"\*\*\s+([^\*\n]+?)\*\*"#, with: " **$1**", options: .regularExpression)
        s = s.replacingOccurrences(of: #"(?<!\*)\*([^\*\n]+?)\s+\*(?!\*)"#, with: "*$1* ", options: .regularExpression)
        s = s.replacingOccurrences(of: #"(?<!\*)\*\s+([^\*\n]+?)\*(?!\*)"#, with: " *$1*", options: .regularExpression)
        
        if let attr = try? AttributedString(
            markdown: s,
            options: AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        ) {
            return attr
        }
        if let attr = try? AttributedString(markdown: s) {
            return attr
        }
        return AttributedString(self)
    }
}

