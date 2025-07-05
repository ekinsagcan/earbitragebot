import SwiftUI
import StoreKit

@main
struct ArbitrageBotApp: App {
    @StateObject private var appManager = AppManager.shared
    @StateObject private var authViewModel = AuthViewModel()
    @StateObject private var subscriptionManager = SubscriptionManager()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appManager)
                .environmentObject(authViewModel)
                .environmentObject(subscriptionManager)
                .onAppear {
                    configureApp()
                }
                .task {
                    await initializeApp()
                }
        }
    }
    
    private func configureApp() {
        // Configure app appearance
        configureNavigationBar()
        configureTabBar()
    }
    
    private func configureNavigationBar() {
        let appearance = UINavigationBarAppearance()
        appearance.configureWithTransparentBackground()
        appearance.titleTextAttributes = [
            .foregroundColor: UIColor.label,
            .font: UIFont.systemFont(ofSize: 18, weight: .semibold)
        ]
        
        UINavigationBar.appearance().standardAppearance = appearance
        UINavigationBar.appearance().compactAppearance = appearance
        UINavigationBar.appearance().scrollEdgeAppearance = appearance
    }
    
    private func configureTabBar() {
        let appearance = UITabBarAppearance()
        appearance.configureWithTransparentBackground()
        appearance.backgroundColor = UIColor.systemBackground.withAlphaComponent(0.8)
        
        UITabBar.appearance().standardAppearance = appearance
        UITabBar.appearance().scrollEdgeAppearance = appearance
    }
    
    private func initializeApp() async {
        // Initialize services
        await APIService.shared.initialize()
        await subscriptionManager.loadSubscriptionStatus()
        
        // Check for existing authentication
        if let savedUserID = UserDefaults.standard.object(forKey: "user_id") as? Int {
            await authViewModel.authenticateWithUserID(savedUserID)
        }
    }
}

// MARK: - App Manager
class AppManager: ObservableObject {
    static let shared = AppManager()
    
    @Published var isLoading = true
    @Published var hasNetworkConnection = true
    @Published var currentTab: MainTab = .discover
    @Published var showingErrorAlert = false
    @Published var errorMessage = ""
    
    private init() {
        startNetworkMonitoring()
    }
    
    private func startNetworkMonitoring() {
        // Basic network monitoring
        // In a real app, you'd use Network framework
        Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { _ in
            // Check network connectivity
            self.checkNetworkConnection()
        }
    }
    
    private func checkNetworkConnection() {
        // Simplified network check
        // In production, use proper network monitoring
        hasNetworkConnection = true
    }
    
    func showError(_ message: String) {
        errorMessage = message
        showingErrorAlert = true
    }
}

// MARK: - Main Tab Enum
enum MainTab: String, CaseIterable {
    case discover = "Discover"
    case watchlist = "Watchlist"
    case portfolio = "Portfolio"
    case profile = "Profile"
    
    var icon: String {
        switch self {
        case .discover: return "magnifyingglass.circle"
        case .watchlist: return "star.circle"
        case .portfolio: return "chart.pie"
        case .profile: return "person.circle"
        }
    }
    
    var selectedIcon: String {
        switch self {
        case .discover: return "magnifyingglass.circle.fill"
        case .watchlist: return "star.circle.fill"
        case .portfolio: return "chart.pie.fill"
        case .profile: return "person.circle.fill"
        }
    }
}