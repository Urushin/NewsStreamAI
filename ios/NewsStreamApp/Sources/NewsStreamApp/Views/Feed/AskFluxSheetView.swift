import SwiftUI

public struct AskFluxSheetView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    
    @State private var queryText: String = ""
    @State private var isLoading: Bool = false
    @State private var currentAnswer: String? = nil
    @State private var currentSources: [APIClient.RAGSource] = []
    
    private let suggestedQueries = [
        "Quels sont les derniers modèles d'IA présentés ?",
        "Y a-t-il de nouveaux leaks sur One Piece ?",
        "Qu'ont tweeté Sam Altman et OpenAI ?",
        "Fais-moi un résumé des tensions géopolitiques"
    ]
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        NavigationStack {
            ZStack {
                Color.paperBackground.ignoresSafeArea()
                
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        // MARK: - Header
                        VStack(alignment: .leading, spacing: 6) {
                            HStack(spacing: 8) {
                                Image(systemName: "sparkles")
                                    .foregroundColor(.orange)
                                    .font(.system(size: 16))
                                Text("INTELLIGENCE COGNITIVE LIVE")
                                    .font(AppTypography.mono(size: 11))
                                    .fontWeight(.bold)
                                    .tracking(0.8)
                                    .foregroundColor(.secondary)
                            }
                            
                            Text("Demander au Flux")
                                .font(AppTypography.editorialHeadline(size: 24))
                                .fontWeight(.bold)
                                .foregroundColor(.primary)
                            
                            Text("Interrogez le flux d'actualités en temps réel. Les réponses sont rigoureusement sourcées et recoupées.")
                                .font(AppTypography.editorialBody(size: 13.5))
                                .foregroundColor(.secondary)
                                .lineSpacing(2)
                        }
                        .padding(.horizontal, 20)
                        .padding(.top, 16)
                        
                        // MARK: - Input Box
                        VStack(spacing: 10) {
                            HStack(alignment: .top, spacing: 10) {
                                Image(systemName: "magnifyingglass")
                                    .foregroundColor(.secondary)
                                    .font(.system(size: 14))
                                    .padding(.top, 4)
                                
                                TextField("Posez votre question sur les événements récents...", text: $queryText, axis: .vertical)
                                    .font(AppTypography.editorialBody(size: 15))
                                    .lineLimit(1...4)
                                    .onSubmit {
                                        submitQuestion()
                                    }
                                
                                if !queryText.isEmpty {
                                    Button(action: {
                                        submitQuestion()
                                    }) {
                                        Image(systemName: "arrow.up.circle.fill")
                                            .font(.system(size: 26))
                                            .foregroundColor(.blue)
                                    }
                                    .disabled(isLoading)
                                }
                            }
                            .padding(14)
                            .background(Color.paperCard)
                            .cornerRadius(14)
                            .overlay(
                                RoundedRectangle(cornerRadius: 14)
                                    .stroke(Color.paperBorder, lineWidth: 1)
                            )
                        }
                        .padding(.horizontal, 20)
                        
                        // MARK: - Suggestions
                        if currentAnswer == nil && !isLoading {
                            VStack(alignment: .leading, spacing: 10) {
                                Text("SUGGESTIONS DU MOMENT")
                                    .font(AppTypography.mono(size: 10))
                                    .fontWeight(.bold)
                                    .foregroundColor(.secondary)
                                    .padding(.horizontal, 20)
                                
                                VStack(spacing: 8) {
                                    ForEach(suggestedQueries, id: \.self) { q in
                                        Button(action: {
                                            queryText = q
                                            submitQuestion()
                                        }) {
                                            HStack(spacing: 10) {
                                                Image(systemName: "arrow.up.right.circle")
                                                    .foregroundColor(.secondary)
                                                    .font(.system(size: 13))
                                                Text(q)
                                                    .font(AppTypography.meta(size: 13))
                                                    .foregroundColor(.primary)
                                                    .multilineTextAlignment(.leading)
                                                Spacer()
                                            }
                                            .padding(.horizontal, 14)
                                            .padding(.vertical, 10)
                                            .background(Color.paperCard.opacity(0.8))
                                            .cornerRadius(10)
                                            .overlay(
                                                RoundedRectangle(cornerRadius: 10)
                                                    .stroke(Color.paperBorder.opacity(0.6), lineWidth: 0.8)
                                            )
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }
                                .padding(.horizontal, 20)
                            }
                        }
                        
                        // MARK: - Loading State
                        if isLoading {
                            VStack(spacing: 14) {
                                ProgressView()
                                    .scaleEffect(1.1)
                                Text("Exploration sémantique du flux et synthèse...")
                                    .font(AppTypography.mono(size: 12))
                                    .foregroundColor(.secondary)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 40)
                        }
                        
                        // MARK: - Answer Card
                        if let answer = currentAnswer, !isLoading {
                            VStack(alignment: .leading, spacing: 14) {
                                HStack {
                                    HStack(spacing: 6) {
                                        Image(systemName: "brain.head.profile")
                                            .foregroundColor(.blue)
                                        Text("SYNTHÈSE DU FLUX")
                                            .font(AppTypography.mono(size: 10.5))
                                            .fontWeight(.bold)
                                            .foregroundColor(.secondary)
                                    }
                                    Spacer()
                                    Button(action: {
                                        UIPasteboard.general.string = answer
                                        viewModel.showToast("📋 Réponse copiée !")
                                    }) {
                                        Image(systemName: "doc.on.doc")
                                            .font(.system(size: 12))
                                            .foregroundColor(.secondary)
                                    }
                                }
                                
                                Text(LocalizedStringKey(answer))
                                    .font(AppTypography.editorialBody(size: 14.5))
                                    .foregroundColor(.primary)
                                    .lineSpacing(4)
                                    .fixedSize(horizontal: false, vertical: true)
                                
                                // Sources citations
                                if !currentSources.isEmpty {
                                    VStack(alignment: .leading, spacing: 8) {
                                        Divider()
                                            .padding(.vertical, 4)
                                        
                                        Text("SOURCES DIRECTES CITÉES")
                                            .font(AppTypography.mono(size: 9.5))
                                            .fontWeight(.bold)
                                            .foregroundColor(.secondary)
                                        
                                        ForEach(currentSources, id: \.url) { src in
                                            Button(action: {
                                                if let u = URL(string: src.url) {
                                                    openURL(u)
                                                }
                                            }) {
                                                HStack(spacing: 6) {
                                                    Image(systemName: "link")
                                                        .font(.system(size: 10))
                                                    Text(src.name)
                                                        .font(AppTypography.mono(size: 11))
                                                        .lineLimit(1)
                                                    Spacer()
                                                    Image(systemName: "arrow.up.right")
                                                        .font(.system(size: 9))
                                                }
                                                .foregroundColor(.blue)
                                                .padding(.vertical, 4)
                                            }
                                        }
                                    }
                                }
                            }
                            .padding(18)
                            .background(Color.paperCard)
                            .cornerRadius(16)
                            .overlay(
                                RoundedRectangle(cornerRadius: 16)
                                    .stroke(Color.paperBorder, lineWidth: 1)
                            )
                            .padding(.horizontal, 20)
                        }
                    }
                    .padding(.bottom, 30)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Fermer") {
                        dismiss()
                    }
                    .font(AppTypography.mono(size: 12))
                }
            }
        }
    }
    
    private func submitQuestion() {
        let q = queryText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return }
        
        isLoading = true
        currentAnswer = nil
        currentSources = []
        HapticsManager.shared.impact(.medium)
        
        Task {
            do {
                let response = try await APIClient.shared.askStream(query: q)
                await MainActor.run {
                    self.currentAnswer = response.answer
                    self.currentSources = response.sources ?? []
                    self.isLoading = false
                }
            } catch {
                // Fallback: local heuristic RAG on active multiSourceAlerts
                let (answer, sources) = performLocalStreamQuery(query: q)
                await MainActor.run {
                    self.currentAnswer = answer
                    self.currentSources = sources
                    self.isLoading = false
                }
            }
        }
    }

    private func performLocalStreamQuery(query: String) -> (String, [APIClient.RAGSource]) {
        let words = query.lowercased()
            .components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { $0.count >= 3 }
        
        var scoredAlerts: [(alert: AlertPayload, score: Int)] = []
        for alert in viewModel.multiSourceAlerts {
            let title = alert.push_title.lowercased()
            let content = alert.bullet_points.joined(separator: " ").lowercased()
            var score = 0
            for w in words {
                if title.contains(w) { score += 3 }
                if content.contains(w) { score += 1 }
            }
            if score > 0 {
                scoredAlerts.append((alert, score))
            }
        }
        
        scoredAlerts.sort { $0.score > $1.score }
        let topMatches = scoredAlerts.prefix(4).map(\.alert)
        
        if topMatches.isEmpty {
            return (
                "Aucune corrélation directe trouvée dans le flux récent pour « \(query) ». Le flux continue de surveiller les sources en direct.",
                []
            )
        }
        
        var answer = "D'après les alertes récentes corroborées par MyNews AI :\n\n"
        var ragSources: [APIClient.RAGSource] = []
        for a in topMatches {
            let bullet = a.bullet_points.first ?? a.push_title
            answer += "• **\(a.push_title)** : \(bullet)\n\n"
            for s in a.sources {
                if !ragSources.contains(where: { $0.url == s.url }) {
                    ragSources.append(APIClient.RAGSource(name: s.name, url: s.url))
                }
            }
        }
        
        return (answer.trimmingCharacters(in: .whitespacesAndNewlines), Array(ragSources.prefix(4)))
    }
}
