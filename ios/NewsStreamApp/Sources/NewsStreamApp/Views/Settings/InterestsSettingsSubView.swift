import SwiftUI

public struct InterestsSettingsSubView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var newInterestText: String = ""
    @State private var newRejectionText: String = ""
    @State private var isSaving: Bool = false
    
    let suggestedPresets = [
        "Intelligence Artificielle",
        "Cybersécurité",
        "Finance & Bourse",
        "Géopolitique",
        "Crypto & Web3",
        "Science & Espace",
        "Climat & Énergie",
        "Jeux Vidéo & Tech",
        "Santé & Biotech",
        "Automobile & Mobilité"
    ]
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        Form {
            // MARK: - Sujets Recommandés
            Section(header: Text("Sujets Recommandés")) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(suggestedPresets, id: \.self) { preset in
                            if viewModel.userProfile.interests[preset] == nil {
                                Button(action: {
                                    viewModel.addInterest(topic: preset, weight: 0.85)
                                    HapticsManager.shared.impact(.light)
                                }) {
                                    HStack(spacing: 4) {
                                        Image(systemName: "plus.circle.fill")
                                            .font(.system(size: 11))
                                        Text(preset)
                                            .font(AppTypography.mono(size: 11))
                                    }
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 6)
                                    .background(Color.paperBorder.opacity(0.4))
                                    .foregroundColor(.primary)
                                    .cornerRadius(12)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
            
            // MARK: - Centres d'intérêt actifs
            Section(
                header: Text("Centres d'intérêt actifs (\(viewModel.userProfile.interests.count))"),
                footer: Text("Vos sujets favoris orientent discrètement la sélection des actualités.")
            ) {
                HStack {
                    TextField("Ajouter un domaine (ex: Semi-conducteurs)", text: $newInterestText)
                        .font(AppTypography.meta(size: 13))
                    
                    Button(action: {
                        guard !newInterestText.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        viewModel.addInterest(topic: newInterestText, weight: 0.85)
                        newInterestText = ""
                        HapticsManager.shared.impact(.light)
                    }) {
                        Text("Ajouter")
                            .font(AppTypography.mono(size: 12))
                            .fontWeight(.bold)
                            .foregroundColor(.blue)
                    }
                    .disabled(newInterestText.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                
                if viewModel.userProfile.interests.isEmpty {
                    Text("Aucun centre d'intérêt défini : toutes les actualités multi-sources sont présentées.")
                        .font(AppTypography.meta(size: 12))
                        .foregroundColor(.secondary)
                        .padding(.vertical, 4)
                } else {
                    ForEach(viewModel.userProfile.interests.sorted(by: { $0.key < $1.key }), id: \.key) { topic, _ in
                        HStack(spacing: 10) {
                            Image(systemName: "sparkle")
                                .foregroundColor(.blue.opacity(0.85))
                                .font(.system(size: 12))
                            Text(topic)
                                .font(AppTypography.meta(size: 14))
                                .fontWeight(.medium)
                            Spacer()
                            Button(action: {
                                viewModel.removeInterest(topic: topic)
                                HapticsManager.shared.impact(.light)
                            }) {
                                Image(systemName: "trash")
                                    .font(.system(size: 12))
                                    .foregroundColor(.red.opacity(0.8))
                                    .padding(.leading, 8)
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            
            // MARK: - Mots-Clés & Thèmes Exclus (Blacklist)
            Section(
                header: Text("Mots-Clés Exclus / Blacklist (\(viewModel.userProfile.rejection_rules.count))"),
                footer: Text("Toutes les news contenant ces mots seront systématiquement écartées par l'algorithme.")
            ) {
                HStack {
                    TextField("Mot-clé à bloquer (ex: people, football)", text: $newRejectionText)
                        .font(AppTypography.meta(size: 13))
                    
                    Button(action: {
                        guard !newRejectionText.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        viewModel.addRejectionRule(keyword: newRejectionText)
                        newRejectionText = ""
                        HapticsManager.shared.impact(.light)
                    }) {
                        Text("Bloquer")
                            .font(AppTypography.mono(size: 12))
                            .fontWeight(.bold)
                            .foregroundColor(.red)
                    }
                    .disabled(newRejectionText.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                
                if viewModel.userProfile.rejection_rules.isEmpty {
                    Text("Aucun mot-clé exclu.")
                        .font(AppTypography.meta(size: 12))
                        .foregroundColor(.secondary)
                } else {
                    ForEach(viewModel.userProfile.rejection_rules, id: \.self) { rule in
                        HStack {
                            Image(systemName: "nosign")
                                .font(.system(size: 11))
                                .foregroundColor(.red)
                            Text(rule)
                                .font(AppTypography.meta(size: 13))
                            Spacer()
                            Button(action: {
                                viewModel.removeRejectionRule(keyword: rule)
                                HapticsManager.shared.impact(.light)
                            }) {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.system(size: 14))
                                    .foregroundColor(.secondary)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            
            // MARK: - Sauvegarde
            Section {
                Button(action: {
                    isSaving = true
                    Task {
                        await viewModel.saveUserProfile()
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
                            Image(systemName: "checkmark.circle.fill")
                        }
                        Text("Enregistrer & Réentraîner l'IA")
                            .fontWeight(.semibold)
                        Spacer()
                    }
                    .font(AppTypography.meta(size: 14))
                    .foregroundColor(.blue)
                }
            }
        }
        .background(Color.paperBackground)
        .navigationTitle("Centres d'intérêt")
        .inlineNavigationBar()
    }
}
