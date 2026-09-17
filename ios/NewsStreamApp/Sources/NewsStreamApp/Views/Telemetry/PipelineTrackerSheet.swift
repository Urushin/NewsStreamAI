import SwiftUI

public struct PipelineTrackerSheet: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @Environment(\.dismiss) private var dismiss
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    private var activeStepIndex: Int {
        guard let stepId = viewModel.currentPipelineStep?.step_id else {
            return viewModel.isScanning ? 0 : -1
        }
        switch stepId {
        case "ingestion": return 0
        case "vectorization": return 1
        case "clustering": return 2
        case "synthesis": return 3
        case "completed", "DONE": return 4
        default: return 0
        }
    }
    
    public var body: some View {
        NavigationStack {
            ZStack {
                Color.paperBackground.ignoresSafeArea()
                
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        
                        // MARK: - 1. Top Card (Task Label, Status Badge & KPI Counters)
                        VStack(alignment: .leading, spacing: 14) {
                            HStack(alignment: .center, spacing: 12) {
                                ZStack {
                                    RoundedRectangle(cornerRadius: 10)
                                        .fill(Color.blue.opacity(0.12))
                                        .frame(width: 38, height: 38)
                                    Image(systemName: "cpu")
                                        .font(.system(size: 18, weight: .bold))
                                        .foregroundColor(.blue)
                                }
                                
                                VStack(alignment: .leading, spacing: 3) {
                                    HStack(spacing: 8) {
                                        Text(viewModel.currentPipelineStep?.safeTaskLabel ?? "Traitement Cognitif en Direct")
                                            .font(AppTypography.editorialSubhead(size: 15))
                                            .fontWeight(.bold)
                                            .foregroundColor(.primary)
                                        
                                        if viewModel.isScanning || viewModel.isSimulating || viewModel.isCatchingUp {
                                            HStack(spacing: 4) {
                                                ProgressView()
                                                    .scaleEffect(0.6)
                                                Text("EN COURS")
                                                    .font(AppTypography.mono(size: 9))
                                                    .fontWeight(.bold)
                                                    .foregroundColor(.orange)
                                            }
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 2.5)
                                            .background(Color.orange.opacity(0.12))
                                            .cornerRadius(6)
                                        } else {
                                            Text(viewModel.currentPipelineStep?.safeStatus == "done" ? "TERMINÉ" : "EN VEILLE")
                                                .font(AppTypography.mono(size: 9))
                                                .fontWeight(.bold)
                                                .padding(.horizontal, 6)
                                                .padding(.vertical, 2.5)
                                                .background(Color.green.opacity(0.12))
                                                .foregroundColor(.green)
                                                .cornerRadius(6)
                                        }
                                    }
                                    
                                    Text(viewModel.currentPipelineStep?.details ?? "Pipeline prêt pour l'analyse des flux.")
                                        .font(AppTypography.meta(size: 11.5))
                                        .foregroundColor(.secondary)
                                        .lineLimit(2)
                                }
                                
                                Spacer()
                            }
                            
                            // Live Dual KPI Counters & Stopwatch
                            HStack(spacing: 10) {
                                // Timer
                                HStack(spacing: 4) {
                                    Image(systemName: "clock")
                                        .font(.system(size: 10))
                                        .foregroundColor(.secondary)
                                    Text("Temps :")
                                        .font(AppTypography.mono(size: 10))
                                        .foregroundColor(.secondary)
                                    Text(String(format: "%.1fs", viewModel.currentPipelineStep?.safeElapsedSeconds ?? 0.0))
                                        .font(AppTypography.mono(size: 10))
                                        .fontWeight(.bold)
                                        .foregroundColor(.primary)
                                }
                                .padding(.horizontal, 8)
                                .padding(.vertical, 5)
                                .background(Color.paperBorder.opacity(0.3))
                                .cornerRadius(8)
                                
                                // News Found Counter
                                HStack(spacing: 4) {
                                    Image(systemName: "newspaper")
                                        .font(.system(size: 10))
                                        .foregroundColor(.blue)
                                    Text("News trouvées :")
                                        .font(AppTypography.mono(size: 10))
                                        .foregroundColor(.secondary)
                                    Text("\(viewModel.currentPipelineStep?.safeNewsCount ?? 0)")
                                        .font(AppTypography.mono(size: 10))
                                        .fontWeight(.bold)
                                        .foregroundColor(.blue)
                                }
                                .padding(.horizontal, 8)
                                .padding(.vertical, 5)
                                .background(Color.blue.opacity(0.08))
                                .cornerRadius(8)
                                
                                // Summaries Count
                                HStack(spacing: 4) {
                                    Image(systemName: "sparkles")
                                        .font(.system(size: 10))
                                        .foregroundColor(.purple)
                                    Text("Résumés :")
                                        .font(AppTypography.mono(size: 10))
                                        .foregroundColor(.secondary)
                                    Text("\(viewModel.currentPipelineStep?.safeSummariesCount ?? 0)")
                                        .font(AppTypography.mono(size: 10))
                                        .fontWeight(.bold)
                                        .foregroundColor(.purple)
                                }
                                .padding(.horizontal, 8)
                                .padding(.vertical, 5)
                                .background(Color.purple.opacity(0.08))
                                .cornerRadius(8)
                            }
                            
                            // Progress Bar
                            VStack(spacing: 4) {
                                ProgressView(value: Double(max(3, viewModel.currentPipelineStep?.progress_pct ?? (viewModel.isScanning ? 20 : 100))), total: 100)
                                    .tint(.blue)
                                
                                HStack {
                                    Text(viewModel.currentPipelineStep?.step_title ?? (viewModel.isScanning ? "Traitement..." : "Prêt"))
                                        .font(AppTypography.mono(size: 9.5))
                                        .foregroundColor(.secondary)
                                    Spacer()
                                    Text("\(viewModel.currentPipelineStep?.progress_pct ?? (viewModel.isScanning ? 20 : 100))%")
                                        .font(AppTypography.mono(size: 9.5))
                                        .fontWeight(.bold)
                                        .foregroundColor(.primary)
                                }
                            }
                        }
                        .padding(16)
                        .background(Color.white)
                        .cornerRadius(14)
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .stroke(Color.paperBorder, lineWidth: 1)
                        )
                        
                        // MARK: - 2. 5 Pipeline Stages Visual Stepper (Exact Web Interface)
                        VStack(alignment: .leading, spacing: 10) {
                            Text("ÉTAPES DU PIPELINE COGNITIF")
                                .font(AppTypography.mono(size: 10.5))
                                .fontWeight(.bold)
                                .tracking(0.8)
                                .foregroundColor(.secondary)
                            
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 8) {
                                    stepBadge(idx: 0, title: "1. Collecte", sub: "Scan des 807 flux", icon: "antenna.radiowaves.left.and.right")
                                    stepBadge(idx: 1, title: "2. Vecteurs", sub: "Embeddings 384d", icon: "waveform")
                                    stepBadge(idx: 2, title: "3. Clusters", sub: "Recoupements", icon: "square.3.layers.3d")
                                    stepBadge(idx: 3, title: "4. Synthèse IA", sub: "Génération LLM", icon: "sparkles")
                                    stepBadge(idx: 4, title: "5. Diffusion", sub: "Diffusion SSE", icon: "paperplane")
                                }
                            }
                        }
                        
                        // MARK: - 3. Quick Action Buttons
                        HStack(spacing: 12) {
                            Button(action: {
                                Task {
                                    await viewModel.triggerSimulation()
                                }
                            }) {
                                HStack(spacing: 6) {
                                    if viewModel.isSimulating {
                                        ProgressView().scaleEffect(0.7).tint(.white)
                                    } else {
                                        Image(systemName: "bolt.fill")
                                            .font(.system(size: 11))
                                    }
                                    Text(viewModel.isSimulating ? "Simulation..." : "Simuler Événements")
                                        .font(AppTypography.mono(size: 11))
                                        .fontWeight(.semibold)
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color.blue.opacity(viewModel.isSimulating ? 0.6 : 1.0))
                                .foregroundColor(.white)
                                .cornerRadius(8)
                            }
                            .disabled(viewModel.isSimulating || viewModel.isScanning)
                            
                            Button(action: {
                                Task {
                                    await viewModel.trigger24hCatchUp()
                                }
                            }) {
                                HStack(spacing: 6) {
                                    if viewModel.isCatchingUp {
                                        ProgressView().scaleEffect(0.7)
                                    } else {
                                        Image(systemName: "arrow.clockwise")
                                            .font(.system(size: 11))
                                    }
                                    Text(viewModel.isCatchingUp ? "Scan 24h..." : "Rattrapage 24h")
                                        .font(AppTypography.mono(size: 11))
                                        .fontWeight(.semibold)
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color.paperBorder.opacity(viewModel.isCatchingUp ? 0.6 : 0.4))
                                .foregroundColor(.primary)
                                .cornerRadius(8)
                            }
                            .disabled(viewModel.isCatchingUp || viewModel.isScanning)
                        }
                        
                        // MARK: - 4. Live Console Logs (Terminal Theme)
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                HStack(spacing: 6) {
                                    Image(systemName: "terminal")
                                        .font(.system(size: 11))
                                        .foregroundColor(.green)
                                    Text("CONSOLE DE TÉLÉMÉTRIE EN DIRECT")
                                        .font(AppTypography.mono(size: 10.5))
                                        .fontWeight(.bold)
                                        .foregroundColor(.secondary)
                                }
                                
                                Spacer()
                                
                                HStack(spacing: 4) {
                                    Circle()
                                        .fill(viewModel.isConnectedToSSE ? Color.green : Color.orange)
                                        .frame(width: 6, height: 6)
                                    Text(viewModel.isConnectedToSSE ? "Flux actif" : "Connexion...")
                                        .font(AppTypography.mono(size: 9))
                                        .foregroundColor(.secondary)
                                }
                            }
                            
                            VStack(alignment: .leading, spacing: 6) {
                                if viewModel.pipelineLogs.isEmpty {
                                    Text("> Console prête. Cliquez sur 'Simuler Événements' ou 'Rattrapage 24h' pour observer les étapes du pipeline.")
                                        .font(AppTypography.mono(size: 10.5))
                                        .foregroundColor(.secondary.opacity(0.7))
                                        .padding(.vertical, 10)
                                } else {
                                    ForEach(Array(viewModel.pipelineLogs.prefix(40).enumerated()), id: \.offset) { _, log in
                                        Text(log)
                                            .font(AppTypography.mono(size: 10))
                                            .foregroundColor(Color(hex: "#22C55E"))
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                            .lineSpacing(1.5)
                                    }
                                }
                            }
                            .padding(12)
                            .frame(maxWidth: .infinity, minHeight: 180, alignment: .topLeading)
                            .background(Color(hex: "#0F172A"))
                            .cornerRadius(10)
                            .overlay(
                                RoundedRectangle(cornerRadius: 10)
                                    .stroke(Color.paperBorder.opacity(0.3), lineWidth: 1)
                            )
                        }
                    }
                    .padding(16)
                }
            }
            .navigationTitle("Télémétrie Pipeline IA")
            .inlineNavigationBar()
            .toolbar {
                #if os(iOS)
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Fermer") {
                        dismiss()
                    }
                    .font(AppTypography.mono(size: 12))
                }
                #else
                ToolbarItem(placement: .confirmationAction) {
                    Button("Fermer") {
                        dismiss()
                    }
                    .font(AppTypography.mono(size: 12))
                }
                #endif
            }
        }
    }
    
    @ViewBuilder
    private func stepBadge(idx: Int, title: String, sub: String, icon: String) -> some View {
        let isDone = activeStepIndex > idx
        let isActive = activeStepIndex == idx
        
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Image(systemName: icon)
                    .font(.system(size: 10))
                    .foregroundColor(isActive ? .blue : (isDone ? .green : .secondary))
                Text(title)
                    .font(AppTypography.mono(size: 10))
                    .fontWeight(.bold)
                    .foregroundColor(isActive ? .primary : (isDone ? .primary : .secondary))
                Spacer()
                if isActive {
                    ProgressView()
                        .scaleEffect(0.5)
                } else if isDone {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 10))
                        .foregroundColor(.green)
                }
            }
            
            Text(sub)
                .font(AppTypography.mono(size: 8.5))
                .foregroundColor(.secondary)
        }
        .padding(10)
        .frame(width: 125, height: 58)
        .background(isActive ? Color.blue.opacity(0.08) : (isDone ? Color.green.opacity(0.05) : Color.white))
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(isActive ? Color.blue : (isDone ? Color.green.opacity(0.4) : Color.paperBorder), lineWidth: 1)
        )
    }
}
