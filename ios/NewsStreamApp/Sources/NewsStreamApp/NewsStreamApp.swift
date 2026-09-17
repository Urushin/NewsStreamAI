import SwiftUI

public struct NewsStreamAppView: View {
    public init() {}
    
    public var body: some View {
        RootTabView()
    }
}

#if os(iOS)
@main
struct MyNewsAIApp: App {
    @Environment(\.scenePhase) private var scenePhase
    
    init() {
        BackgroundRefreshManager.shared.registerBackgroundTask()
    }
    
    var body: some Scene {
        WindowGroup {
            NewsStreamAppView()
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .background {
                BackgroundRefreshManager.shared.scheduleAppRefresh()
            }
        }
    }
}
#endif
