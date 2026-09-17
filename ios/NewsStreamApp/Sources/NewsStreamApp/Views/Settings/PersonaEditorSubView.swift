import SwiftUI

public struct PersonaEditorSubView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var personaMarkdownText: String = ""
    @State private var isSaving: Bool = false
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        Form {
            Section(
                header: Text("Description & Persona (.md)"),
                footer: Text("Décrivez précisément qui vous êtes, votre métier, vos sujets de veille, votre horizon d'investissement ou vos thèmes de prédilection. Le modèle vectoriel Mizan analyse ce texte intégral pour calibrer vos flux.")
            ) {
                TextEditor(text: $personaMarkdownText)
                    .font(AppTypography.mono(size: 11.5))
                    .frame(minHeight: 220)
                    .padding(6)
                    .background(Color.paperBorder.opacity(0.12))
                    .cornerRadius(8)
            }
            
            Section {
                Button(action: {
                    isSaving = true
                    Task {
                        await viewModel.updateBioMarkdown(text: personaMarkdownText)
                        isSaving = false
                        HapticsManager.shared.notification(.success)
                    }
                }) {
                    HStack {
                        Spacer()
                        if isSaving {
                            ProgressView()
                                .padding(.trailing, 6)
                        } else {
                            Image(systemName: "sparkles")
                        }
                        Text("Analyser & Synchroniser mon Profil avec l'IA")
                            .fontWeight(.semibold)
                        Spacer()
                    }
                    .font(AppTypography.meta(size: 13.5))
                    .foregroundColor(.blue)
                    .padding(.vertical, 4)
                }
            }
        }
        .background(Color.paperBackground)
        .navigationTitle("Persona Markdown")
        .inlineNavigationBar()
        .onAppear {
            if let md = viewModel.userProfile.bio_markdown, !md.isEmpty {
                personaMarkdownText = md
            }
        }
        .onChange(of: viewModel.userProfile.bio_markdown) {
            if let md = viewModel.userProfile.bio_markdown, !md.isEmpty {
                personaMarkdownText = md
            }
        }
    }
}
