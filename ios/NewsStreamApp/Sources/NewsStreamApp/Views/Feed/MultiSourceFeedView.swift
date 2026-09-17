import SwiftUI

public struct MultiSourceFeedView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var showingPipelineSheet: Bool = false
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                ScrollView {
                    LazyVStack(spacing: 16) {
                        // Live Pipeline Progress Tracker (if active)
                        if let step = viewModel.currentPipelineStep, step.status != "completed" && step.status != "done" && step.step_id != "completed" {
                            Button(action: {
                                showingPipelineSheet = true
                            }) {
                                HStack(spacing: 12) {
                                    ProgressView()
                                        .tint(.blue)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(step.step_title)
                                            .font(AppTypography.meta(size: 12))
                                            .fontWeight(.bold)
                                            .foregroundColor(.primary)
                                        Text(step.details)
                                            .font(AppTypography.mono(size: 10))
                                            .foregroundColor(.secondary)
                                            .lineLimit(1)
                                    }
                                    Spacer()
                                    Text("\(step.progress_pct)%")
                                        .font(AppTypography.mono(size: 11))
                                        .fontWeight(.bold)
                                        .foregroundColor(.blue)
                                }
                                .padding(12)
                                .background(Color.blue.opacity(0.08))
                                .cornerRadius(12)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12)
                                        .stroke(Color.blue.opacity(0.25), lineWidth: 1)
                                )
                            }
                            .padding(.horizontal, 16)
                        }
                        
                        // Control Action Bar (Simuler / Rattrapage)
                        HStack(spacing: 10) {
                            Button(action: {
                                Task {
                                    await viewModel.triggerSimulation()
                                }
                            }) {
                                HStack(spacing: 6) {
                                    if viewModel.isSimulating {
                                        ProgressView()
                                            .tint(.white)
                                    } else {
                                        Image(systemName: "bolt.fill")
                                    }
                                    Text("Simuler Événements")
                                        .font(AppTypography.meta(size: 12))
                                        .fontWeight(.semibold)
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color.newsPrimary)
                                .foregroundColor(.white)
                                .cornerRadius(10)
                            }
                            .disabled(viewModel.isSimulating)
                            
                            Button(action: {
                                Task {
                                    await viewModel.trigger24hCatchUp()
                                }
                            }) {
                                HStack(spacing: 6) {
                                    if viewModel.isCatchingUp {
                                        ProgressView()
                                            .tint(.primary)
                                    } else {
                                        Image(systemName: "sparkles")
                                    }
                                    Text("Rattrapage 24h")
                                        .font(AppTypography.meta(size: 12))
                                        .fontWeight(.semibold)
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color.paperBorder.opacity(0.6))
                                .foregroundColor(.primary)
                                .cornerRadius(10)
                            }
                            .disabled(viewModel.isCatchingUp)
                        }
                        .padding(.horizontal, 16)
                        
                        // Feed Stream Content
                        if viewModel.multiSourceAlerts.isEmpty {
                            VStack(spacing: 12) {
                                Image(systemName: "dot.radiowaves.left.and.right")
                                    .font(.system(size: 36))
                                    .foregroundColor(.secondary)
                                    .padding(.top, 40)
                                Text("En attente de recoupements multi-sources")
                                    .font(AppTypography.editorialSubhead(size: 16))
                                    .foregroundColor(.primary)
                                Text("Lancez une simulation ou le rattrapage 24h pour observer le pipeline en direct.")
                                    .font(AppTypography.meta(size: 13))
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                                    .padding(.horizontal, 32)
                            }
                            .padding(.vertical, 40)
                        } else {
                            ForEach(viewModel.multiSourceAlerts) { alert in
                                AlertCardView(alert: alert) { isPositive in
                                    Task {
                                        await viewModel.submitFeedback(
                                            clusterId: alert.cluster_id,
                                            title: alert.push_title,
                                            isPositive: isPositive
                                        )
                                    }
                                }
                                .padding(.horizontal, 16)
                            }
                        }
                    }
                    .padding(.vertical, 12)
                }
                .background(Color.paperBackground)
                .refreshable {
                    await viewModel.loadAlertsHistory()
                }
                
                // Toast Notification Overlay
                if let toast = viewModel.toastMessage {
                    Text(toast)
                        .font(AppTypography.meta(size: 12))
                        .fontWeight(.semibold)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.black.opacity(0.85))
                        .foregroundColor(.white)
                        .cornerRadius(20)
                        .shadow(radius: 8)
                        .padding(.bottom, 20)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .navigationTitle("MyNews AI")
            .inlineNavigationBar()
            .toolbar {
                ToolbarItem(placement: .principal) {
                    BrandLogoView(size: 26)
                }
                ToolbarItem(placement: .navigation) {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(viewModel.isConnectedToSSE ? Color.green : Color.orange)
                            .frame(width: 7, height: 7)
                        Text(viewModel.isConnectedToSSE ? "Direct" : "Reconnexion")
                            .font(AppTypography.mono(size: 9))
                            .foregroundColor(.secondary)
                    }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button(action: {
                        showingPipelineSheet = true
                    }) {
                        Image(systemName: "chart.bar.doc.horizontal")
                            .font(.system(size: 13))
                            .foregroundColor(.primary)
                    }
                }
            }
            .sheet(isPresented: $showingPipelineSheet) {
                PipelineTrackerSheet(viewModel: viewModel)
            }
        }
    }
}
