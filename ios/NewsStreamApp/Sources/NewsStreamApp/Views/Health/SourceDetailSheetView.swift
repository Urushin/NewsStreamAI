import SwiftUI

public struct SourceDetailSheetView: View {
    @Environment(\.dismiss) private var dismiss
    public let item: FeedHealthItem
    public let isBlocked: Bool
    public let onToggleBlock: () -> Void
    
    public init(
        item: FeedHealthItem,
        isBlocked: Bool,
        onToggleBlock: @escaping () -> Void
    ) {
        self.item = item
        self.isBlocked = isBlocked
        self.onToggleBlock = onToggleBlock
    }
    
    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // MARK: - Header & Badges
                    VStack(spacing: 12) {
                        ZStack {
                            Circle()
                                .fill(Color.paperBorder.opacity(0.4))
                                .frame(width: 64, height: 64)
                            
                            Image(systemName: isBlocked ? "eye.slash.fill" : "newspaper.fill")
                                .font(.system(size: 28))
                                .foregroundColor(isBlocked ? .red : .primary)
                        }
                        
                        VStack(spacing: 6) {
                            Text(item.name)
                                .font(AppTypography.editorialHeadline(size: 24))
                                .multilineTextAlignment(.center)
                                .foregroundColor(.primary)
                            
                            if let country = item.country {
                                Text(country)
                                    .font(AppTypography.meta(size: 13))
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        // Status Pills
                        HStack(spacing: 8) {
                            if isBlocked {
                                StatusBadge(text: "SOURCE BLOQUÉE", color: .red)
                            } else if item.isQuarantined {
                                StatusBadge(text: "EN QUARANTAINE", color: .orange)
                            } else if item.isOk {
                                StatusBadge(text: "OPÉRATIONNEL (OK)", color: .green)
                            } else {
                                StatusBadge(text: "INCIDENT TECHNIQUE", color: .red)
                            }
                            
                            if let orientation = item.orientation {
                                StatusBadge(text: orientation.uppercased(), color: .blue)
                            }
                        }
                    }
                    .padding(.top, 10)
                    
                    // MARK: - Fiche Propriété & Actionnariat
                    if (item.owner?.isEmpty == false) || (item.funding?.isEmpty == false) || (item.profile_description?.isEmpty == false) {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack(spacing: 6) {
                                Image(systemName: "building.columns.fill")
                                    .font(.system(size: 14))
                                    .foregroundColor(.secondary)
                                Text("PROPRIÉTAIRE & ACTIONNARIAT")
                                    .font(AppTypography.mono(size: 11))
                                    .foregroundColor(.secondary)
                            }
                            
                            VStack(alignment: .leading, spacing: 8) {
                                if let owner = item.owner, !owner.isEmpty {
                                    HStack(alignment: .firstTextBaseline) {
                                        Text("Actionnaire :")
                                            .font(AppTypography.meta(size: 13))
                                            .foregroundColor(.secondary)
                                            .frame(width: 95, alignment: .leading)
                                        
                                        Text(owner)
                                            .font(AppTypography.editorialSubhead(size: 14))
                                            .fontWeight(.bold)
                                            .foregroundColor(.primary)
                                    }
                                }
                                
                                if let funding = item.funding, !funding.isEmpty {
                                    HStack(alignment: .firstTextBaseline) {
                                        Text("Modèle :")
                                            .font(AppTypography.meta(size: 13))
                                            .foregroundColor(.secondary)
                                            .frame(width: 95, alignment: .leading)
                                        
                                        Text(funding)
                                            .font(AppTypography.meta(size: 13))
                                            .foregroundColor(.primary)
                                    }
                                }
                                
                                if let desc = item.profile_description, !desc.isEmpty {
                                    Text(desc)
                                        .font(AppTypography.editorialBody(size: 13.5))
                                        .foregroundColor(.secondary)
                                        .padding(.top, 4)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                            .padding(14)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.paperCard)
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(Color.paperBorder, lineWidth: 1)
                            )
                        }
                        .padding(.horizontal, 16)
                    }
                    
                    // MARK: - Ligne Éditoriale & Positionnement
                    if let orientation = item.orientation {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack(spacing: 6) {
                                Image(systemName: "safari.fill")
                                    .font(.system(size: 14))
                                    .foregroundColor(.secondary)
                                Text("LIGNE ÉDITORIALE")
                                    .font(AppTypography.mono(size: 11))
                                    .foregroundColor(.secondary)
                            }
                            
                            VStack(alignment: .leading, spacing: 6) {
                                Text(orientation)
                                    .font(AppTypography.editorialSubhead(size: 15))
                                    .foregroundColor(.primary)
                                
                                Text("Analyse algorithmique de réputation et historique des dépêches Mizan/MyNews AI.")
                                    .font(AppTypography.meta(size: 12))
                                    .foregroundColor(.secondary)
                            }
                            .padding(14)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.paperCard)
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(Color.paperBorder, lineWidth: 1)
                            )
                        }
                        .padding(.horizontal, 16)
                    }
                    
                    // MARK: - Télémétrie du Flux
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(spacing: 6) {
                            Image(systemName: "chart.xyaxis.line")
                                .font(.system(size: 14))
                                .foregroundColor(.secondary)
                            Text("TÉLÉMÉTRIE DU FLUX")
                                .font(AppTypography.mono(size: 11))
                                .foregroundColor(.secondary)
                        }
                        
                        VStack(spacing: 10) {
                            TelemetryRow(title: "Latence moyenne", value: "\(Int(item.avg_latency_ms ?? 0)) ms")
                            Divider().background(Color.paperBorder)
                            TelemetryRow(title: "Articles traités", value: "\(item.total_items_fetched ?? 0)")
                            Divider().background(Color.paperBorder)
                            TelemetryRow(title: "Échecs consécutifs", value: "\(item.consecutive_failures ?? 0)")
                            
                            if let lastSeen = item.last_seen_at {
                                Divider().background(Color.paperBorder)
                                TelemetryRow(title: "Dernière synchro", value: String(lastSeen.prefix(19).replacingOccurrences(of: "T", with: " ")))
                            }
                            
                            if let error = item.last_error {
                                Divider().background(Color.paperBorder)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Dernière anomalie :")
                                        .font(AppTypography.mono(size: 10.5))
                                        .foregroundColor(.red)
                                    Text(error)
                                        .font(AppTypography.mono(size: 11))
                                        .foregroundColor(.red.opacity(0.85))
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                        .padding(14)
                        .background(Color.paperCard)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.paperBorder, lineWidth: 1)
                        )
                    }
                    .padding(.horizontal, 16)
                    
                    // MARK: - Mute / Block Action
                    Button {
                        HapticsManager.shared.impact(.medium)
                        onToggleBlock()
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: isBlocked ? "checkmark.circle.fill" : "nosign")
                                .font(.system(size: 15))
                            Text(isBlocked ? "Débloquer et réactiver ce flux" : "Mettre en sourdine / Bloquer ce média")
                                .font(AppTypography.editorialSubhead(size: 14))
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .foregroundColor(isBlocked ? .green : .red)
                        .background(isBlocked ? Color.green.opacity(0.12) : Color.red.opacity(0.1))
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(isBlocked ? Color.green.opacity(0.3) : Color.red.opacity(0.3), lineWidth: 1)
                        )
                    }
                    .buttonStyle(.plain)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 24)
                }
            }
            .background(Color.paperBackground.ignoresSafeArea())
            .navigationTitle("Fiche Source")
            .inlineNavigationBar()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Fermer") {
                        dismiss()
                    }
                    .font(AppTypography.editorialSubhead(size: 14))
                    .foregroundColor(.primary)
                }
            }
        }
    }
}

private struct StatusBadge: View {
    let text: String
    let color: Color
    
    var body: some View {
        Text(text)
            .font(AppTypography.mono(size: 9))
            .fontWeight(.bold)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.12))
            .foregroundColor(color)
            .cornerRadius(6)
    }
}

private struct TelemetryRow: View {
    let title: String
    let value: String
    
    var body: some View {
        HStack {
            Text(title)
                .font(AppTypography.meta(size: 13))
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(AppTypography.mono(size: 12.5))
                .foregroundColor(.primary)
        }
    }
}
