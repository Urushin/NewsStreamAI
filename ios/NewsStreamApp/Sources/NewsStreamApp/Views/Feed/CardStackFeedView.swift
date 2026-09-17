import SwiftUI

public struct CardStackFeedView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var dragOffset: CGSize = .zero
    @State private var isInteracting = false
    @State private var showingPipelineSheet = false
    @State private var selectedAlertForDetail: AlertPayload? = nil
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        NavigationStack {
            ZStack {
                Color.paperBackground.ignoresSafeArea()
                
                VStack(spacing: 12) {
                    // MARK: - 1. Clean Top Header: Logo only (No text) + Status + Précédent Top Right
                    HStack(alignment: .center, spacing: 10) {
                        // Minimalist Emblem Logo Only
                        ZStack {
                            RoundedRectangle(cornerRadius: 7)
                                .fill(Color.primary)
                                .frame(width: 28, height: 28)
                            Image(systemName: "scale.3d")
                                .font(.system(size: 14, weight: .bold))
                                .foregroundColor(Color.paperBackground)
                        }
                        
                        // Live SSE Status + Realtime Pulse
                        HStack(spacing: 4) {
                            Circle()
                                .fill(viewModel.hasNewRealtimeAlertPulse ? Color.blue : (viewModel.isConnectedToSSE ? Color.green : Color.orange))
                                .frame(width: 6, height: 6)
                                .scaleEffect(viewModel.hasNewRealtimeAlertPulse ? 1.35 : 1.0)
                            Text(viewModel.hasNewRealtimeAlertPulse ? "Nouveau" : (viewModel.isConnectedToSSE ? "Direct" : "Connexion..."))
                                .font(AppTypography.mono(size: 9.5))
                                .foregroundColor(viewModel.hasNewRealtimeAlertPulse ? .blue : .secondary)
                        }
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(Color.paperBorder.opacity(0.3))
                        .cornerRadius(8)
                        
                        Spacer()
                        
                        // Actualiser (Refresh) Button
                        Button(action: {
                            Task {
                                await viewModel.refreshFeed()
                            }
                        }) {
                            Image(systemName: "arrow.clockwise")
                                .font(.system(size: 11.5))
                                .foregroundColor(.secondary)
                                .padding(6)
                                .background(Color.paperBorder.opacity(0.25))
                                .clipShape(Circle())
                        }
                        
                        // Telemetry Sheet Button
                        Button(action: {
                            showingPipelineSheet = true
                        }) {
                            Image(systemName: "chart.bar.doc.horizontal")
                                .font(.system(size: 11.5))
                                .foregroundColor(.secondary)
                                .padding(6)
                                .background(Color.paperBorder.opacity(0.25))
                                .clipShape(Circle())
                        }
                        
                        // Real "Précédent" Button Top Right
                        Button(action: {
                            guard !isInteracting else { return }
                            viewModel.rewindCard()
                        }) {
                            HStack(spacing: 3) {
                                Image(systemName: "arrow.uturn.backward")
                                    .font(.system(size: 10, weight: .semibold))
                                Text("Précédent")
                                    .font(AppTypography.mono(size: 10.5))
                                    .fontWeight(.medium)
                            }
                            .padding(.horizontal, 9)
                            .padding(.vertical, 5)
                            .background(viewModel.currentCardIndex > 0 ? Color.paperBorder.opacity(0.6) : Color.paperBorder.opacity(0.15))
                            .foregroundColor(viewModel.currentCardIndex > 0 ? .primary : .secondary.opacity(0.3))
                            .cornerRadius(8)
                        }
                        .disabled(viewModel.currentCardIndex == 0 || isInteracting)
                    }
                    .padding(.horizontal, 18)
                    .padding(.top, 2)
                    
                    // MARK: - 2. Live Scan Progress Banner (if active)
                    if viewModel.isScanning || viewModel.isCatchingUp || viewModel.isSimulating {
                        VStack(alignment: .leading, spacing: 5) {
                            HStack {
                                HStack(spacing: 6) {
                                    ProgressView()
                                        .scaleEffect(0.65)
                                    Text(viewModel.currentPipelineStep?.step_title ?? "Scan & Traitement IA en cours...")
                                        .font(AppTypography.mono(size: 10.5))
                                        .fontWeight(.semibold)
                                        .foregroundColor(.primary)
                                }
                                Spacer()
                                Text("\(viewModel.currentPipelineStep?.progress_pct ?? 0)%")
                                    .font(AppTypography.mono(size: 10.5))
                                    .foregroundColor(.blue)
                            }
                            
                            ProgressView(value: Double(max(5, viewModel.currentPipelineStep?.progress_pct ?? 0)), total: 100.0)
                                .tint(.blue)
                            
                            if let details = viewModel.currentPipelineStep?.details, !details.isEmpty {
                                Text(details)
                                    .font(AppTypography.mono(size: 9))
                                    .foregroundColor(.secondary)
                                    .lineLimit(1)
                            }
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .background(Color.paperBorder.opacity(0.35))
                        .cornerRadius(10)
                        .padding(.horizontal, 18)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    }
                    
                    // MARK: - 3. Card Deck Counter
                    if !viewModel.multiSourceAlerts.isEmpty {
                        HStack {
                            let displayIdx = min(viewModel.currentCardIndex + 1, viewModel.multiSourceAlerts.count)
                            Text("NEWS \(displayIdx) SUR \(viewModel.multiSourceAlerts.count)")
                                .font(AppTypography.mono(size: 9.5))
                                .foregroundColor(.secondary)
                            Spacer()
                            Text("↕ Défiler • ↔ Voter")
                                .font(AppTypography.mono(size: 8.5))
                                .foregroundColor(.secondary.opacity(0.7))
                        }
                        .padding(.horizontal, 20)
                    }
                    
                    Spacer(minLength: 4)
                    
                    // MARK: - 4. Centered Dynamic Card Bubble & Action Bar
                    if let card = viewModel.currentCard {
                        VStack(spacing: 12) {
                            // Card Display with Dynamic Height
                            ZStack {
                                // Next card peeking from behind
                                if let next = viewModel.nextCard {
                                    TwitterNewsCardView(alert: next, viewModel: viewModel, isBackgroundCard: true)
                                        .scaleEffect(0.96)
                                        .offset(y: 8)
                                        .opacity(0.4)
                                        .allowsHitTesting(false)
                                }
                                
                                // Top Active Card with Fluid Gestures
                                ZStack {
                                    TwitterNewsCardView(alert: card, viewModel: viewModel, isBackgroundCard: false, onTap: {
                                        selectedAlertForDetail = card
                                    })
                                    
                                    // Satisfying Dynamic Swipe Stamps
                                    if dragOffset.width > 30 {
                                        VStack {
                                            HStack {
                                                HStack(spacing: 5) {
                                                    Image(systemName: "hand.thumbsup.fill")
                                                    Text("PERTINENT")
                                                        .font(AppTypography.mono(size: 13))
                                                        .fontWeight(.bold)
                                                }
                                                .foregroundColor(.green)
                                                .padding(.horizontal, 14)
                                                .padding(.vertical, 8)
                                                .background(Color.green.opacity(0.12))
                                                .overlay(
                                                    RoundedRectangle(cornerRadius: 10)
                                                        .stroke(Color.green, lineWidth: 2)
                                                )
                                                .cornerRadius(10)
                                                .rotationEffect(.degrees(-12))
                                                .opacity(Double(min(1.0, (dragOffset.width - 30) / 60.0)))
                                                Spacer()
                                            }
                                            Spacer()
                                        }
                                        .padding(20)
                                    } else if dragOffset.width < -30 {
                                        VStack {
                                            HStack {
                                                Spacer()
                                                HStack(spacing: 5) {
                                                    Text("IGNORÉ")
                                                        .font(AppTypography.mono(size: 13))
                                                        .fontWeight(.bold)
                                                    Image(systemName: "hand.thumbsdown.fill")
                                                }
                                                .foregroundColor(.red)
                                                .padding(.horizontal, 14)
                                                .padding(.vertical, 8)
                                                .background(Color.red.opacity(0.12))
                                                .overlay(
                                                    RoundedRectangle(cornerRadius: 10)
                                                        .stroke(Color.red, lineWidth: 2)
                                                )
                                                .cornerRadius(10)
                                                .rotationEffect(.degrees(12))
                                                .opacity(Double(min(1.0, (-dragOffset.width - 30) / 60.0)))
                                            }
                                            Spacer()
                                        }
                                        .padding(20)
                                    }
                                }
                                .offset(dragOffset)
                                .rotationEffect(.degrees(Double(dragOffset.width / 35)))
                                .gesture(
                                    DragGesture()
                                        .onChanged { gesture in
                                            guard !isInteracting else { return }
                                            dragOffset = gesture.translation
                                        }
                                        .onEnded { gesture in
                                            guard !isInteracting else { return }
                                            let w = gesture.translation.width
                                            let h = gesture.translation.height
                                            
                                            if h < -65 {
                                                // Swipe Up = Pass to next news
                                                isInteracting = true
                                                withAnimation(.easeInOut(duration: 0.14)) {
                                                    dragOffset = CGSize(width: 0, height: -500)
                                                }
                                                Task { @MainActor in
                                                    try? await Task.sleep(nanoseconds: 120_000_000)
                                                    viewModel.skipCurrentCard()
                                                    dragOffset = .zero
                                                    isInteracting = false
                                                }
                                            } else if h > 65 && viewModel.currentCardIndex > 0 {
                                                // Swipe Down = Rewind to previous news
                                                isInteracting = true
                                                withAnimation(.easeInOut(duration: 0.14)) {
                                                    dragOffset = CGSize(width: 0, height: 500)
                                                }
                                                Task { @MainActor in
                                                    try? await Task.sleep(nanoseconds: 120_000_000)
                                                    viewModel.rewindCard()
                                                    dragOffset = .zero
                                                    isInteracting = false
                                                }
                                            } else if w > 90 {
                                                // Swipe Right = Like
                                                isInteracting = true
                                                withAnimation(.easeInOut(duration: 0.14)) {
                                                    dragOffset = CGSize(width: 500, height: h)
                                                }
                                                Task { @MainActor in
                                                    try? await Task.sleep(nanoseconds: 120_000_000)
                                                    await viewModel.likeCurrentCard()
                                                    dragOffset = .zero
                                                    isInteracting = false
                                                }
                                            } else if w < -90 {
                                                // Swipe Left = Dislike
                                                isInteracting = true
                                                withAnimation(.easeInOut(duration: 0.14)) {
                                                    dragOffset = CGSize(width: -500, height: h)
                                                }
                                                Task { @MainActor in
                                                    try? await Task.sleep(nanoseconds: 120_000_000)
                                                    await viewModel.dislikeCurrentCard()
                                                    dragOffset = .zero
                                                    isInteracting = false
                                                }
                                            } else {
                                                withAnimation(.spring(response: 0.25, dampingFraction: 0.8)) {
                                                    dragOffset = .zero
                                                }
                                            }
                                        }
                                )
                            }
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.horizontal, 14)
                            
                            // Like & Dislike Buttons adapted directly to Card
                            HStack(spacing: 40) {
                                // 👎 Dislike Button
                                Button(action: {
                                    guard !isInteracting else { return }
                                    isInteracting = true
                                    Task {
                                        await viewModel.dislikeCurrentCard()
                                        isInteracting = false
                                    }
                                }) {
                                    HStack(spacing: 6) {
                                        Image(systemName: "hand.thumbsdown.fill")
                                            .font(.system(size: 15))
                                            .foregroundColor(.red.opacity(0.85))
                                        Text("Moins")
                                            .font(AppTypography.mono(size: 11))
                                            .foregroundColor(.secondary)
                                    }
                                    .padding(.horizontal, 15)
                                    .padding(.vertical, 7)
                                    .background(Color.paperBorder.opacity(0.35))
                                    .cornerRadius(20)
                                }
                                .buttonStyle(.plain)
                                .disabled(isInteracting)
                                
                                // 👍 Like Button
                                Button(action: {
                                    guard !isInteracting else { return }
                                    isInteracting = true
                                    Task {
                                        await viewModel.likeCurrentCard()
                                        isInteracting = false
                                    }
                                }) {
                                    HStack(spacing: 6) {
                                        Image(systemName: "hand.thumbsup.fill")
                                            .font(.system(size: 15))
                                            .foregroundColor(.blue)
                                        Text("Pertinent")
                                            .font(AppTypography.mono(size: 11))
                                            .foregroundColor(.blue)
                                    }
                                    .padding(.horizontal, 15)
                                    .padding(.vertical, 7)
                                    .background(Color.blue.opacity(0.08))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 20)
                                             .stroke(Color.blue.opacity(0.25), lineWidth: 0.8)
                                    )
                                    .cornerRadius(20)
                                }
                                .buttonStyle(.plain)
                                .disabled(isInteracting)
                            }
                            .padding(.top, 2)
                        }
                    } else {
                        // Empty Deck State Centered
                        VStack(spacing: 14) {
                            Image(systemName: "newspaper")
                                .font(.system(size: 40))
                                .foregroundColor(.secondary.opacity(0.5))
                            
                            Text("Vous êtes à jour")
                                .font(AppTypography.editorialHeadline(size: 20))
                                .foregroundColor(.primary)
                            
                            Text("Aucune nouvelle actualité en attente. Plus de 1 000 flux sont surveillés en continu.")
                                .font(AppTypography.meta(size: 12.5))
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 30)
                            
                            HStack(spacing: 12) {
                                Button(action: {
                                    viewModel.resetDeck()
                                }) {
                                    HStack(spacing: 5) {
                                        Image(systemName: "arrow.counterclockwise")
                                        Text("Relire")
                                    }
                                    .font(AppTypography.mono(size: 11.5))
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 9)
                                    .background(Color.paperBorder.opacity(0.4))
                                    .foregroundColor(.primary)
                                    .cornerRadius(8)
                                }
                            }
                            .padding(.top, 6)
                        }
                        .padding(24)
                        .background(Color.paperBackground)
                        .cornerRadius(16)
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(Color.paperBorder, lineWidth: 1)
                        )
                        .padding(.horizontal, 16)
                    }
                    
                    Spacer(minLength: 4)
                    
                    // MARK: - 5. Pinned Bottom Arrow for Vertical Scroll ("Passer")
                    if viewModel.currentCard != nil {
                        Button(action: {
                            guard !isInteracting else { return }
                            viewModel.skipCurrentCard()
                        }) {
                            VStack(spacing: 2) {
                                Image(systemName: "chevron.up")
                                    .font(.system(size: 16, weight: .bold))
                                    .foregroundColor(.secondary.opacity(0.85))
                                Text("Passer")
                                    .font(AppTypography.mono(size: 9.5))
                                    .foregroundColor(.secondary.opacity(0.75))
                            }
                            .padding(.horizontal, 20)
                            .padding(.vertical, 6)
                        }
                        .buttonStyle(.plain)
                        .disabled(isInteracting)
                        .padding(.bottom, 6)
                    }
                }
            }
            #if os(iOS)
            .navigationBarHidden(true)
            #endif
            .sheet(isPresented: $showingPipelineSheet) {
                PipelineTrackerSheet(viewModel: viewModel)
            }
            .sheet(item: $selectedAlertForDetail) { alert in
                NewsDetailSheetView(alert: alert, viewModel: viewModel)
            }
            .overlay(alignment: .top) {
                if let toast = viewModel.toastMessage {
                    Text(toast)
                        .font(AppTypography.mono(size: 11.5))
                        .padding(.horizontal, 14)
                        .padding(.vertical, 7)
                        .background(Color.primary)
                        .foregroundColor(Color.paperBackground)
                        .cornerRadius(18)
                        .shadow(radius: 6)
                        .padding(.top, 10)
                        .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
        }
    }
}
