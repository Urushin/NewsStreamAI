import SwiftUI

public struct TelegramSettingsSubView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var tokenInput: String = ""
    @State private var chatIdInput: String = ""
    @State private var notificationsEnabled: Bool = true
    @State private var isTokenVisible: Bool = false
    @State private var isSaving: Bool = false
    @State private var isTesting: Bool = false
    @State private var testResult: (success: Bool, message: String)? = nil
    @State private var showingTutorial: Bool = false
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        Form {
            // MARK: - 1. Status & Overview
            Section {
                HStack(spacing: 12) {
                    ZStack {
                        Circle()
                            .fill(isConfigured ? Color.blue : Color.secondary.opacity(0.2))
                            .frame(width: 44, height: 44)
                        Image(systemName: "paperplane.fill")
                            .font(.system(size: 20))
                            .foregroundColor(.white)
                    }
                    
                    VStack(alignment: .leading, spacing: 3) {
                        Text(isConfigured ? "Telegram Connecté" : "Non Configuré")
                            .font(AppTypography.editorialHeadline(size: 15))
                            .fontWeight(.bold)
                            .foregroundColor(.primary)
                        
                        Text(isConfigured
                             ? "Les alertes Fast-Track sont acheminées en direct sur votre compte."
                             : "Associez votre bot pour recevoir les flashs info instantanés.")
                            .font(AppTypography.meta(size: 11.5))
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.vertical, 4)
            }
            
            // MARK: - 2. Guide Pas-à-Pas (Tutorial)
            Section(header: Text("Tutoriel de Connexion")) {
                DisclosureGroup(
                    isExpanded: $showingTutorial,
                    content: {
                        VStack(alignment: .leading, spacing: 14) {
                            stepRow(
                                number: "1",
                                title: "Créer votre Bot via @BotFather",
                                detail: "Ouvrez Telegram et recherchez @BotFather. Envoyez /newbot, donnez un nom à votre bot (ex: Mon Actu AI) puis un identifiant finissant par 'bot' (ex: mon_actu_stream_bot)."
                            )
                            
                            stepRow(
                                number: "2",
                                title: "Copier le Token d'accès",
                                detail: "BotFather vous fournit un token API HTTP (ex: 7123456789:AAFbx...). Copiez-le et collez-le dans le champ 'Bot Token' ci-dessous."
                            )
                            
                            stepRow(
                                number: "3",
                                title: "Démarrer la discussion",
                                detail: "Crucial : ouvrez la conversation avec votre tout nouveau bot sur Telegram et cliquez sur 'Démarrer' (/start) pour l'autoriser à vous envoyer des messages."
                            )
                            
                            stepRow(
                                number: "4",
                                title: "Obtenir votre Chat ID",
                                detail: "Recherchez @userinfobot sur Telegram et lancez-le. Il vous répond instantanément votre Id numérique (ex: 987654321). Copiez ce numéro dans le champ 'Chat ID'."
                            )
                        }
                        .padding(.vertical, 8)
                    },
                    label: {
                        HStack(spacing: 8) {
                            Image(systemName: "questionmark.circle.fill")
                                .foregroundColor(.blue)
                            Text("Comment obtenir mon Token et Chat ID ?")
                                .font(AppTypography.meta(size: 13))
                                .fontWeight(.medium)
                        }
                    }
                )
            }
            
            // MARK: - 3. Credentials Inputs
            Section(
                header: Text("Identifiants Telegram"),
                footer: Text("Ces identifiants sont stockés en toute sécurité dans l'environnement local du serveur.")
            ) {
                // Token Input
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Bot Token API")
                            .font(AppTypography.meta(size: 12))
                            .foregroundColor(.secondary)
                        Spacer()
                        Button(action: { isTokenVisible.toggle() }) {
                            Image(systemName: isTokenVisible ? "eye.slash" : "eye")
                                .font(.system(size: 12))
                                .foregroundColor(.secondary)
                        }
                        .buttonStyle(.plain)
                    }
                    
                    if isTokenVisible {
                        TextField("7123456789:AAFb...", text: $tokenInput)
                            .font(AppTypography.mono(size: 12))
                            .platformAutocapitalizationNone()
                            .disableAutocorrection(true)
                    } else {
                        SecureField("7123456789:AAFb...", text: $tokenInput)
                            .font(AppTypography.mono(size: 12))
                    }
                }
                .padding(.vertical, 2)
                
                // Chat ID Input
                VStack(alignment: .leading, spacing: 4) {
                    Text("Votre Chat ID")
                        .font(AppTypography.meta(size: 12))
                        .foregroundColor(.secondary)
                    
                    TextField("123456789", text: $chatIdInput)
                        .font(AppTypography.mono(size: 12))
                        .platformAutocapitalizationNone()
                        .disableAutocorrection(true)
                }
                .padding(.vertical, 2)
                
                // Notifications Toggle
                Toggle("Activer les notifications instantanées", isOn: $notificationsEnabled)
                    .font(AppTypography.meta(size: 13))
            }
            
            // MARK: - 4. Enregistrer & Actions
            Section {
                Button(action: {
                    saveCredentials()
                }) {
                    HStack {
                        Spacer()
                        if isSaving {
                            ProgressView().scaleEffect(0.8)
                        } else {
                            Image(systemName: "checkmark.circle.fill")
                            Text("Enregistrer les réglages")
                                .font(AppTypography.meta(size: 13.5))
                                .fontWeight(.semibold)
                        }
                        Spacer()
                    }
                }
                .disabled(isSaving || tokenInput.trimmingCharacters(in: .whitespaces).isEmpty || chatIdInput.trimmingCharacters(in: .whitespaces).isEmpty)
                
                Button(action: {
                    testNotification()
                }) {
                    HStack {
                        Image(systemName: "paperplane")
                            .foregroundColor(.blue)
                        Text("Envoyer une alerte de test")
                            .font(AppTypography.meta(size: 13))
                        Spacer()
                        if isTesting {
                            ProgressView().scaleEffect(0.8)
                        }
                    }
                }
                .disabled(isTesting || tokenInput.trimmingCharacters(in: .whitespaces).isEmpty || chatIdInput.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            
            if let result = testResult {
                Section {
                    HStack(spacing: 8) {
                        Image(systemName: result.success ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                            .foregroundColor(result.success ? .green : .red)
                        Text(result.message)
                            .font(AppTypography.meta(size: 12))
                            .foregroundColor(result.success ? .green : .red)
                    }
                }
            }
        }
        .background(Color.paperBackground)
        .navigationTitle("Configuration Telegram")
        .inlineNavigationBar()
        .onAppear {
            loadInitialSettings()
        }
    }
    
    private var isConfigured: Bool {
        viewModel.telegramConfig?.configured == true || (!tokenInput.isEmpty && !chatIdInput.isEmpty)
    }
    
    private func stepRow(number: String, title: String, detail: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            ZStack {
                Circle()
                    .fill(Color.blue.opacity(0.15))
                    .frame(width: 22, height: 22)
                Text(number)
                    .font(AppTypography.mono(size: 11))
                    .fontWeight(.bold)
                    .foregroundColor(.blue)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(AppTypography.meta(size: 12.5))
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
                Text(detail)
                    .font(AppTypography.meta(size: 11.5))
                    .foregroundColor(.secondary)
                    .lineSpacing(2)
            }
        }
    }
    
    private func loadInitialSettings() {
        if let config = viewModel.telegramConfig {
            tokenInput = config.raw_token ?? config.bot_token
            chatIdInput = config.chat_id
            notificationsEnabled = config.enabled
        } else {
            Task {
                await viewModel.loadTelegramSettings()
                if let config = viewModel.telegramConfig {
                    tokenInput = config.raw_token ?? config.bot_token
                    chatIdInput = config.chat_id
                    notificationsEnabled = config.enabled
                }
            }
        }
    }
    
    private func saveCredentials() {
        isSaving = true
        testResult = nil
        Task {
            let success = await viewModel.saveTelegramSettings(
                token: tokenInput,
                chatId: chatIdInput,
                enabled: notificationsEnabled
            )
            isSaving = false
            if success {
                testResult = (true, "Configuration enregistrée sur le serveur !")
            } else {
                testResult = (false, "Erreur lors de l'enregistrement.")
            }
        }
    }
    
    private func testNotification() {
        isTesting = true
        testResult = nil
        Task {
            let (ok, msg) = await viewModel.testTelegramAlert(token: tokenInput, chatId: chatIdInput)
            isTesting = false
            testResult = (ok, msg)
        }
    }
}
