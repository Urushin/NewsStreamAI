import SwiftUI
#if canImport(UIKit)
import UIKit
import WebKit
#endif

/// The Atlas is shared with the web app so projections, observations and controls
/// stay identical on both surfaces. Article reading remains native.
public struct GlobeMapView: View {
    @ObservedObject var viewModel: NewsStreamViewModel
    @State private var selectedAlert: AlertPayload?
    @State private var selectedV2Event: V2Event?
    @State private var loading = true
    @State private var loadError: String?
    @State private var articleUnavailable = false
    @State private var reloadID = UUID()
    @State private var host = APIClient.shared.baseURLString

    public init(viewModel: NewsStreamViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        NavigationStack {
            ZStack {
                Color(red: 0.04, green: 0.10, blue: 0.16).ignoresSafeArea()
                #if canImport(UIKit)
                if let url = atlasURL {
                    SharedAtlasWebView(url: url, loading: $loading, loadError: $loadError) { alertID in
                        Task { await openArticle(alertID) }
                    }
                    .id(reloadID)
                    .ignoresSafeArea()
                }
                #endif
                if loading && loadError == nil {
                    VStack(spacing: 15) {
                        ProgressView().tint(Color.newsPrimary)
                        Text("Votre fenêtre sur le monde")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .padding(24)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 22))
                }
                if let error = loadError {
                    VStack(spacing: 18) {
                        Image(systemName: "globe.europe.africa")
                            .font(.system(size: 46, weight: .ultraLight))
                            .foregroundStyle(Color.newsPrimary)
                        Text("Retrouvons le monde")
                            .font(.title2.weight(.semibold))
                        Text(error)
                            .font(.subheadline)
                            .multilineTextAlignment(.center)
                            .foregroundStyle(.secondary)
                        Button("Réessayer") {
                            host = APIClient.shared.baseURLString
                            loadError = nil
                            loading = true
                            reloadID = UUID()
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(Color.newsPrimary)
                    }
                    .padding(30)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(red: 0.04, green: 0.10, blue: 0.16))
                }
            }
            .ignoresSafeArea()
            .toolbar(.hidden, for: .navigationBar)
            .sheet(item: $selectedV2Event) { event in
                NavigationStack {
                    V2EventDetailView(event: event)
                        .toolbar {
                            ToolbarItem(placement: .topBarTrailing) {
                                Button("Fermer") { selectedV2Event = nil }
                            }
                        }
                }
            }
            .sheet(item: $selectedAlert) { alert in
                NewsDetailSheetView(alert: alert, viewModel: viewModel)
            }
            .alert("Information indisponible", isPresented: $articleUnavailable) {
                Button("Fermer", role: .cancel) { }
            } message: {
                Text("Cet article n’est plus présent dans les news. Son résumé reste accessible sur le globe.")
            }
            .onAppear {
                if host != APIClient.shared.baseURLString {
                    host = APIClient.shared.baseURLString
                    reloadID = UUID()
                }
                if atlasURL == nil {
                    loading = false
                    loadError = "Vérifiez l’adresse de votre serveur dans le profil."
                }
            }
        }
    }

    private var atlasURL: URL? {
        guard let base = URL(string: host), ["http", "https"].contains(base.scheme?.lowercased() ?? ""), base.host != nil else { return nil }
        return base.appendingPathComponent("static/atlas.html")
    }

    @MainActor
    private func openArticle(_ id: String) async {
        do {
            let detail = try await APIClient.shared.fetchV2Event(eventId: id)
            selectedV2Event = detail.asV2Event
            return
        } catch {
            if let article = viewModel.allAlerts.first(where: { $0.alert_id == id }) {
                selectedAlert = article
                return
            }
            await viewModel.loadAlertsHistory()
            if let article = viewModel.allAlerts.first(where: { $0.alert_id == id }) {
                selectedAlert = article
            } else {
                articleUnavailable = true
            }
        }
    }
}

#if canImport(UIKit)
private struct SharedAtlasWebView: UIViewRepresentable {
    let url: URL
    @Binding var loading: Bool
    @Binding var loadError: String?
    let onArticle: (String) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(context.coordinator, name: "atlasNews")
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.scrollView.contentInset = .zero
        webView.scrollView.verticalScrollIndicatorInsets = .zero
        webView.scrollView.isScrollEnabled = false
        webView.scrollView.bounces = false
        webView.allowsBackForwardNavigationGestures = false
        webView.load(URLRequest(url: url, cachePolicy: .reloadRevalidatingCacheData, timeoutInterval: 20))
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        context.coordinator.parent = self
    }

    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        uiView.stopLoading()
        uiView.configuration.userContentController.removeScriptMessageHandler(forName: "atlasNews")
        uiView.navigationDelegate = nil
        uiView.uiDelegate = nil
    }

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler, WKUIDelegate {
        var parent: SharedAtlasWebView
        init(_ parent: SharedAtlasWebView) { self.parent = parent }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            let origin = message.frameInfo.securityOrigin
            let expectedPort = parent.url.port ?? (parent.url.scheme == "https" ? 443 : 80)
            guard message.frameInfo.isMainFrame,
                  origin.host == parent.url.host,
                  origin.protocol == parent.url.scheme,
                  (origin.port == 0 || origin.port == expectedPort),
                  let body = message.body as? [String: Any],
                  let id = body["alert_id"] as? String, !id.isEmpty, id.count <= 200 else { return }
            parent.onArticle(id)
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.loading = false
            parent.loadError = nil
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            failed(error)
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            failed(error)
        }

        private func failed(_ error: Error) {
            guard (error as NSError).code != NSURLErrorCancelled else { return }
            parent.loading = false
            parent.loadError = "Le globe ne parvient pas à joindre votre serveur. Vérifiez votre connexion et l’adresse configurée dans le profil."
        }

        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            parent.loading = true
            parent.loadError = nil
            webView.reload()
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping @MainActor @Sendable (WKNavigationActionPolicy) -> Void) {
            guard let destination = navigationAction.request.url else { decisionHandler(.cancel); return }
            if destination.scheme == parent.url.scheme && destination.host == parent.url.host && destination.port == parent.url.port && destination.path == parent.url.path {
                decisionHandler(.allow)
            } else {
                if navigationAction.navigationType == .linkActivated, ["https", "http"].contains(destination.scheme ?? "") {
                    UIApplication.shared.open(destination)
                }
                decisionHandler(.cancel)
            }
        }

        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if navigationAction.targetFrame == nil, let destination = navigationAction.request.url, ["https", "http"].contains(destination.scheme ?? "") {
                UIApplication.shared.open(destination)
            }
            return nil
        }
    }
}
#endif
