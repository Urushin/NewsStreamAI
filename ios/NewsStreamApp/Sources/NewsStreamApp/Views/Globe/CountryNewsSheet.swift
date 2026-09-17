import SwiftUI

public struct CountryNewsSheet: View {
    public let countryCode: String
    public let countryName: String
    public let alerts: [AlertPayload]
    @ObservedObject var viewModel: NewsStreamViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var selectedAlertForDetail: AlertPayload? = nil
    
    public init(
        countryCode: String,
        countryName: String,
        alerts: [AlertPayload],
        viewModel: NewsStreamViewModel
    ) {
        self.countryCode = countryCode
        self.countryName = countryName
        self.alerts = alerts
        self.viewModel = viewModel
    }
    
    public var body: some View {
        NavigationStack {
            ZStack {
                Color.paperBackground.ignoresSafeArea()
                
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        // Header info
                        HStack(spacing: 12) {
                            Text(countryFlag(countryCode))
                                .font(.system(size: 34))
                            
                            VStack(alignment: .leading, spacing: 2) {
                                Text(countryName)
                                    .font(AppTypography.editorialHeadline(size: 20))
                                    .foregroundColor(.primary)
                                
                                Text("\(alerts.count) actualité\(alerts.count > 1 ? "s" : "") recoupée\(alerts.count > 1 ? "s" : "")")
                                    .font(AppTypography.mono(size: 11))
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                        }
                        .padding(.horizontal, 20)
                        .padding(.top, 10)
                        
                        Divider()
                            .padding(.horizontal, 20)
                        
                        if alerts.isEmpty {
                            VStack(spacing: 10) {
                                Image(systemName: "globe.europe.africa")
                                    .font(.system(size: 36))
                                    .foregroundColor(.secondary.opacity(0.4))
                                Text("Aucune dépêche récente dans cette région.")
                                    .font(AppTypography.meta(size: 13))
                                    .foregroundColor(.secondary)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 40)
                        } else {
                            LazyVStack(spacing: 14) {
                                ForEach(alerts) { alert in
                                    TwitterNewsCardView(alert: alert, viewModel: viewModel, onTap: {
                                        selectedAlertForDetail = alert
                                    })
                                    .padding(.horizontal, 16)
                                }
                            }
                        }
                    }
                    .padding(.vertical, 16)
                }
            }
            .navigationTitle("Actualités Régionales")
            .inlineNavigationBar()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Fermer") {
                        dismiss()
                    }
                }
            }
            .sheet(item: $selectedAlertForDetail) { alert in
                NewsDetailSheetView(alert: alert, viewModel: viewModel)
            }
        }
    }
    
    private func countryFlag(_ code: String) -> String {
        let base : UInt32 = 127397
        var s = ""
        for v in code.uppercased().unicodeScalars {
            s.unicodeScalars.append(UnicodeScalar(base + v.value)!)
        }
        return s.isEmpty ? "🌍" : s
    }
}
