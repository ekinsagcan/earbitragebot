import Foundation
import SwiftUI

@MainActor
class AuthViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var isAuthenticated = false
    @Published var currentUser: User?
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var showingError = false
    
    // MARK: - Private Properties
    private let apiService = APIService.shared
    
    // MARK: - User Data
    struct User {
        let id: Int
        let username: String?
        let joinDate: Date
        
        var displayName: String {
            username ?? "User \(id)"
        }
    }
    
    // MARK: - Initialization
    init() {
        // Listen to API service authentication changes
        setupAuthenticationObserver()
    }
    
    // MARK: - Authentication Methods
    func authenticateWithUserID(_ userID: Int, username: String? = nil) async {
        isLoading = true
        errorMessage = nil
        
        let result = await apiService.authenticate(userID: userID, username: username)
        
        switch result {
        case .success(_):
            isAuthenticated = true
            currentUser = User(
                id: userID,
                username: username,
                joinDate: Date()
            )
            saveUserData(userID: userID, username: username)
            
        case .failure(let error):
            handleAuthError(error)
        }
        
        isLoading = false
    }
    
    func registerWithUserID(_ userID: Int, username: String? = nil) async {
        isLoading = true
        errorMessage = nil
        
        let result = await apiService.register(userID: userID, username: username)
        
        switch result {
        case .success(_):
            isAuthenticated = true
            currentUser = User(
                id: userID,
                username: username,
                joinDate: Date()
            )
            saveUserData(userID: userID, username: username)
            
        case .failure(let error):
            handleAuthError(error)
        }
        
        isLoading = false
    }
    
    func signOut() {
        apiService.logout()
        isAuthenticated = false
        currentUser = nil
        clearUserData()
    }
    
    func generateRandomUserID() -> Int {
        return Int.random(in: 100000...999999)
    }
    
    // MARK: - Auto-Authentication
    func checkForExistingAuthentication() async {
        if let savedUserID = UserDefaults.standard.object(forKey: "user_id") as? Int {
            let username = UserDefaults.standard.string(forKey: "username")
            await authenticateWithUserID(savedUserID, username: username)
        }
    }
    
    // MARK: - Private Methods
    private func setupAuthenticationObserver() {
        // This could be expanded to listen to API service changes
        // For now, we manage state directly
    }
    
    private func handleAuthError(_ error: APIError) {
        switch error {
        case .unauthorized:
            errorMessage = "Authentication failed. Please try again."
        case .networkError:
            errorMessage = "Network error. Please check your connection."
        case .serverError(let message):
            errorMessage = "Server error: \(message)"
        default:
            errorMessage = error.localizedDescription
        }
        showingError = true
    }
    
    private func saveUserData(userID: Int, username: String?) {
        UserDefaults.standard.set(userID, forKey: "user_id")
        if let username = username {
            UserDefaults.standard.set(username, forKey: "username")
        }
    }
    
    private func clearUserData() {
        UserDefaults.standard.removeObject(forKey: "user_id")
        UserDefaults.standard.removeObject(forKey: "username")
    }
}

// MARK: - Subscription Manager
@MainActor
class SubscriptionManager: ObservableObject {
    // MARK: - Published Properties
    @Published var isPremium = false
    @Published var subscriptionStatus: SubscriptionStatus = .free
    @Published var subscriptionEndDate: Date?
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    // MARK: - Subscription Status
    enum SubscriptionStatus {
        case free
        case premium
        case expired
        
        var displayName: String {
            switch self {
            case .free: return "Free"
            case .premium: return "Premium"
            case .expired: return "Expired"
            }
        }
        
        var color: Color {
            switch self {
            case .free: return .gray
            case .premium: return .blue
            case .expired: return .red
            }
        }
    }
    
    // MARK: - Premium Features
    static let premiumFeatures = [
        PremiumFeature(
            icon: "infinity",
            title: "Unlimited Opportunities",
            description: "Access to all arbitrage opportunities without limits"
        ),
        PremiumFeature(
            icon: "chart.line.uptrend.xyaxis",
            title: "Advanced Analytics",
            description: "Detailed market analysis and performance tracking"
        ),
        PremiumFeature(
            icon: "bell.badge",
            title: "Real-time Alerts",
            description: "Push notifications for high-profit opportunities"
        ),
        PremiumFeature(
            icon: "chart.pie",
            title: "Portfolio Tracking",
            description: "Track your trades and performance over time"
        ),
        PremiumFeature(
            icon: "star.fill",
            title: "Priority Support",
            description: "Fast customer support and feature requests"
        ),
        PremiumFeature(
            icon: "square.and.arrow.down",
            title: "Data Export",
            description: "Export opportunities and analysis data"
        )
    ]
    
    // MARK: - Subscription Plans
    static let subscriptionPlans = [
        SubscriptionPlan(
            id: "monthly_premium",
            name: "Premium Monthly",
            price: 9.99,
            period: "month",
            description: "Full access to all premium features",
            features: ["Unlimited opportunities", "Real-time alerts", "Portfolio tracking"]
        ),
        SubscriptionPlan(
            id: "yearly_premium",
            name: "Premium Yearly",
            price: 99.99,
            period: "year",
            description: "Best value - 2 months free!",
            features: ["Everything in Monthly", "Priority support", "Advanced analytics"],
            isPopular: true
        )
    ]
    
    // MARK: - Methods
    func loadSubscriptionStatus() async {
        // In a real app, this would check with App Store / backend
        // For now, simulate based on stored data
        isPremium = UserDefaults.standard.bool(forKey: "is_premium")
        
        if let endDateData = UserDefaults.standard.data(forKey: "subscription_end_date"),
           let endDate = try? JSONDecoder().decode(Date.self, from: endDateData) {
            subscriptionEndDate = endDate
            
            if endDate > Date() {
                subscriptionStatus = .premium
                isPremium = true
            } else {
                subscriptionStatus = .expired
                isPremium = false
            }
        } else {
            subscriptionStatus = .free
            isPremium = false
        }
    }
    
    func purchaseSubscription(_ plan: SubscriptionPlan) async {
        isLoading = true
        
        // Simulate purchase process
        // In a real app, this would integrate with StoreKit
        try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
        
        // Simulate successful purchase
        let endDate = Calendar.current.date(byAdding: .month, value: plan.period == "year" ? 12 : 1, to: Date()) ?? Date()
        
        subscriptionEndDate = endDate
        subscriptionStatus = .premium
        isPremium = true
        
        // Save to UserDefaults (in real app, this would be managed by backend)
        UserDefaults.standard.set(true, forKey: "is_premium")
        if let endDateData = try? JSONEncoder().encode(endDate) {
            UserDefaults.standard.set(endDateData, forKey: "subscription_end_date")
        }
        
        isLoading = false
    }
    
    func restorePurchases() async {
        isLoading = true
        
        // Simulate restore process
        try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
        
        // In a real app, this would check with App Store
        await loadSubscriptionStatus()
        
        isLoading = false
    }
    
    func cancelSubscription() {
        // In a real app, this would redirect to App Store subscription management
        isPremium = false
        subscriptionStatus = .free
        subscriptionEndDate = nil
        
        UserDefaults.standard.removeObject(forKey: "is_premium")
        UserDefaults.standard.removeObject(forKey: "subscription_end_date")
    }
}

// MARK: - Supporting Models
struct PremiumFeature {
    let icon: String
    let title: String
    let description: String
}

struct SubscriptionPlan {
    let id: String
    let name: String
    let price: Double
    let period: String
    let description: String
    let features: [String]
    let isPopular: Bool
    
    init(id: String, name: String, price: Double, period: String, description: String, features: [String], isPopular: Bool = false) {
        self.id = id
        self.name = name
        self.price = price
        self.period = period
        self.description = description
        self.features = features
        self.isPopular = isPopular
    }
    
    var formattedPrice: String {
        return String(format: "$%.2f", price)
    }
    
    var pricePerMonth: String {
        let monthlyPrice = period == "year" ? price / 12 : price
        return String(format: "$%.2f/month", monthlyPrice)
    }
}