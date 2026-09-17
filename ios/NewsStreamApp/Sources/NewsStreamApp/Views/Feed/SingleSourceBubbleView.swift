import SwiftUI

public struct SingleSourceBubbleView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var dragOffset: CGSize = .zero
    @State private var isInteracting = false
    @State private var selectedAlertForDetail: AlertPayload? = nil
    
    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }
    
    public var body: some View {
        NavigationStack {
            ZStack {
                Color.paperBackground.ignoresSafeArea()
                
                VStack(spacing: 12) {
                    // MARK: - 1. Top Header: Category Emblem + Counter + Précédent
                    HStack(alignment: .center, spacing: 10) {
                        HStack(spacing: 6) {
                            Image(systemName: "newspaper")
                                .font(.system(size: 13, weight: .bold))
                                .foregroundColor(.primary)
                            
                            Text("Articles Seuls")
                                .font(AppTypography.editorialHeadline(size: 16))
                                .foregroundColor(.primary)
                        }
                        
                        Text("\(viewModel.singleSourceAlerts.count)")
                            .font(AppTypography.mono(size: 10))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.paperBorder.opacity(0.4))
                            .foregroundColor(.primary)
                            .cornerRadius(5)
                        
                        Spacer()
                        
                        // Précédent Button Top Right
                        Button(action: {
                            guard !isInteracting else { return }
                            viewModel.rewindSingleCard()
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
                            .background(viewModel.singleCardIndex > 0 ? Color.paperBorder.opacity(0.6) : Color.paperBorder.opacity(0.15))
                            .foregroundColor(viewModel.singleCardIndex > 0 ? .primary : .secondary.opacity(0.3))
                            .cornerRadius(8)
                        }
                        .disabled(viewModel.singleCardIndex == 0 || isInteracting)
                    }
                    .padding(.horizontal, 18)
                    .padding(.top, 4)
                    
                    // MARK: - 2. Subtitle / Navigation Hints
                    if !viewModel.singleSourceAlerts.isEmpty {
                        HStack {
                            let displayIdx = min(viewModel.singleCardIndex + 1, viewModel.singleSourceAlerts.count)
                            Text("ARTICLE \(displayIdx) SUR \(viewModel.singleSourceAlerts.count)")
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
                    
                    // MARK: - 3. Centered Dynamic Card Bubble & Action Bar
                    if let card = viewModel.currentSingleCard {
                        VStack(spacing: 12) {
                            // Card Display with Dynamic Height
                            ZStack {
                                // Peeking next card
                                if let next = viewModel.nextSingleCard {
                                    TwitterNewsCardView(alert: next, viewModel: viewModel, isBackgroundCard: true)
                                        .scaleEffect(0.96)
                                        .offset(y: 8)
                                        .opacity(0.4)
                                        .allowsHitTesting(false)
                                }
                                
                                // Foreground Active Card
                                TwitterNewsCardView(alert: card, viewModel: viewModel, isBackgroundCard: false, onTap: {
                                    selectedAlertForDetail = card
                                })
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
                                                // Pass to next
                                                isInteracting = true
                                                withAnimation(.easeInOut(duration: 0.14)) {
                                                    dragOffset = CGSize(width: 0, height: -500)
                                                }
                                                Task { @MainActor in
                                                    try? await Task.sleep(nanoseconds: 120_000_000)
                                                    viewModel.skipCurrentSingleCard()
                                                    dragOffset = .zero
                                                    isInteracting = false
                                                }
                                            } else if h > 65 && viewModel.singleCardIndex > 0 {
                                                // Rewind
                                                isInteracting = true
                                                withAnimation(.easeInOut(duration: 0.14)) {
                                                    dragOffset = CGSize(width: 0, height: 500)
                                                }
                                                Task { @MainActor in
                                                    try? await Task.sleep(nanoseconds: 120_000_000)
                                                    viewModel.rewindSingleCard()
                                                    dragOffset = .zero
                                                    isInteracting = false
                                                }
                                            } else if w > 90 {
                                                // Like
                                                isInteracting = true
                                                withAnimation(.easeInOut(duration: 0.14)) {
                                                    dragOffset = CGSize(width: 500, height: h)
                                                }
                                                Task { @MainActor in
                                                    try? await Task.sleep(nanoseconds: 120_000_000)
                                                    await viewModel.likeCurrentSingleCard()
                                                    dragOffset = .zero
                                                    isInteracting = false
                                                }
                                            } else if w < -90 {
                                                // Dislike
                                                isInteracting = true
                                                withAnimation(.easeInOut(duration: 0.14)) {
                                                    dragOffset = CGSize(width: -500, height: h)
                                                }
                                                Task { @MainActor in
                                                    try? await Task.sleep(nanoseconds: 120_000_000)
                                                    await viewModel.dislikeCurrentSingleCard()
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
                                        await viewModel.dislikeCurrentSingleCard()
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
                                        await viewModel.likeCurrentSingleCard()
                                        isInteracting = false
                                    }
                                }) {
                                    HStack(spacing: 6) {
                                        Image(systemName: "hand.thumbsup.fill")
                                            .font(.system(size: 15))
                                            .foregroundColor(.purple)
                                        Text("Intéressé")
                                            .font(AppTypography.mono(size: 11))
                                            .foregroundColor(.purple)
                                    }
                                    .padding(.horizontal, 15)
                                    .padding(.vertical, 7)
                                    .background(Color.purple.opacity(0.08))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 20)
                                            .stroke(Color.purple.opacity(0.25), lineWidth: 0.8)
                                    )
                                    .cornerRadius(20)
                                }
                                .buttonStyle(.plain)
                                .disabled(isInteracting)
                            }
                            .padding(.top, 2)
                        }
                    } else {
                        // Empty state Centered
                        VStack(spacing: 14) {
                            Image(systemName: "newspaper")
                                .font(.system(size: 38))
                                .foregroundColor(.secondary.opacity(0.4))
                            
                            Text("Aucun article seul en attente")
                                .font(AppTypography.editorialHeadline(size: 18))
                                .foregroundColor(.primary)
                            
                            Text("Les articles issus d'une source unique apparaîtront ici dès leur détection par l'algorithme.")
                                .font(AppTypography.meta(size: 12.5))
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 30)
                            
                            HStack(spacing: 12) {
                                if !viewModel.singleSourceAlerts.isEmpty {
                                    Button(action: {
                                        viewModel.resetSingleDeck()
                                    }) {
                                        HStack(spacing: 5) {
                                            Image(systemName: "arrow.counterclockwise")
                                            Text("Relire")
                                        }
                                        .font(AppTypography.mono(size: 11.5))
                                        .padding(.horizontal, 14)
                                        .padding(.vertical, 8)
                                        .background(Color.paperBorder.opacity(0.4))
                                        .foregroundColor(.primary)
                                        .cornerRadius(8)
                                    }
                                }
                                
                                Button(action: {
                                    Task {
                                        await viewModel.loadAlertsHistory()
                                    }
                                }) {
                                    HStack(spacing: 5) {
                                        Image(systemName: "arrow.clockwise")
                                        Text("Actualiser")
                                    }
                                    .font(AppTypography.mono(size: 11.5))
                                    .padding(.horizontal, 14)
                                    .padding(.vertical, 8)
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
                    
                    // MARK: - 4. Pinned Bottom Arrow for Vertical Scroll ("Passer")
                    if viewModel.currentSingleCard != nil {
                        Button(action: {
                            guard !isInteracting else { return }
                            viewModel.skipCurrentSingleCard()
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
            .sheet(item: $selectedAlertForDetail) { alert in
                NewsDetailSheetView(alert: alert, viewModel: viewModel)
            }
        }
    }
}
