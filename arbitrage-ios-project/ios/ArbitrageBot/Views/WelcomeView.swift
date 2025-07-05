import SwiftUI

// MARK: - Welcome View
struct WelcomeView: View {
    @EnvironmentObject var authViewModel: AuthViewModel
    @State private var userID: String = ""
    @State private var username: String = ""
    @State private var showingSignUp = false
    
    var body: some View {
        NavigationView {
            ZStack {
                // Background gradient
                LinearGradient(
                    colors: [.blue, .purple],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: 30) {
                        Spacer()
                        
                        // App Logo and Title
                        VStack(spacing: 20) {
                            Image(systemName: "chart.line.uptrend.xyaxis.circle.fill")
                                .font(.system(size: 80))
                                .foregroundColor(.white)
                            
                            VStack(spacing: 8) {
                                Text("CryptoArbitrage Pro")
                                    .font(.largeTitle)
                                    .fontWeight(.bold)
                                    .foregroundColor(.white)
                                
                                Text("Discover profitable trading opportunities")
                                    .font(.headline)
                                    .foregroundColor(.white.opacity(0.9))
                                    .multilineTextAlignment(.center)
                            }
                        }
                        
                        // Features List
                        VStack(spacing: 16) {
                            FeatureRow(
                                icon: "magnifyingglass.circle.fill",
                                title: "Real-time Discovery",
                                description: "Find arbitrage opportunities across 30+ exchanges"
                            )
                            
                            FeatureRow(
                                icon: "shield.checkered",
                                title: "Risk Analysis",
                                description: "Advanced risk scoring and safety recommendations"
                            )
                            
                            FeatureRow(
                                icon: "bell.circle.fill",
                                title: "Smart Alerts",
                                description: "Get notified of high-profit opportunities instantly"
                            )
                        }
                        
                        Spacer()
                        
                        // Authentication Section
                        VStack(spacing: 16) {
                            Button {
                                showingSignUp = true
                            } label: {
                                Text("Get Started")
                                    .font(.headline)
                                    .foregroundColor(.blue)
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(Color.white)
                                    .cornerRadius(12)
                            }
                            
                            Button {
                                Task {
                                    let randomID = authViewModel.generateRandomUserID()
                                    await authViewModel.authenticateWithUserID(randomID)
                                }
                            } label: {
                                Text("Quick Start (Anonymous)")
                                    .font(.subheadline)
                                    .foregroundColor(.white.opacity(0.9))
                            }
                        }
                        
                        Spacer()
                    }
                    .padding(.horizontal, 24)
                }
            }
        }
        .sheet(isPresented: $showingSignUp) {
            SignUpView()
                .environmentObject(authViewModel)
        }
        .alert("Authentication Error", isPresented: $authViewModel.showingError) {
            Button("OK") {
                authViewModel.showingError = false
            }
        } message: {
            Text(authViewModel.errorMessage ?? "Unknown error occurred")
        }
    }
}

// MARK: - Sign Up View
struct SignUpView: View {
    @EnvironmentObject var authViewModel: AuthViewModel
    @Environment(\.dismiss) private var dismiss
    
    @State private var userID: String = ""
    @State private var username: String = ""
    @State private var useRandomID = true
    
    var body: some View {
        NavigationView {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Welcome to CryptoArbitrage Pro")
                            .font(.title2)
                            .fontWeight(.bold)
                        
                        Text("Create your account to start discovering profitable arbitrage opportunities.")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 8)
                }
                
                Section("Account Information") {
                    HStack {
                        Text("Username")
                        TextField("Optional", text: $username)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    Toggle("Generate Random User ID", isOn: $useRandomID)
                        .onChange(of: useRandomID) { newValue in
                            if newValue {
                                userID = String(authViewModel.generateRandomUserID())
                            } else {
                                userID = ""
                            }
                        }
                    
                    if !useRandomID {
                        HStack {
                            Text("User ID")
                            TextField("Enter your ID", text: $userID)
                                .textFieldStyle(.roundedBorder)
                                .keyboardType(.numberPad)
                        }
                    } else {
                        HStack {
                            Text("Generated ID")
                            Text(userID.isEmpty ? String(authViewModel.generateRandomUserID()) : userID)
                                .foregroundColor(.blue)
                                .fontWeight(.medium)
                        }
                    }
                }
                
                Section {
                    Button {
                        Task {
                            let finalUserID = Int(userID) ?? authViewModel.generateRandomUserID()
                            let finalUsername = username.isEmpty ? nil : username
                            
                            await authViewModel.registerWithUserID(finalUserID, username: finalUsername)
                            
                            if authViewModel.isAuthenticated {
                                dismiss()
                            }
                        }
                    } label: {
                        if authViewModel.isLoading {
                            HStack {
                                ProgressView()
                                    .scaleEffect(0.8)
                                Text("Creating Account...")
                            }
                        } else {
                            Text("Create Account")
                                .fontWeight(.semibold)
                        }
                    }
                    .disabled(authViewModel.isLoading)
                }
            }
            .navigationTitle("Sign Up")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
        .onAppear {
            if useRandomID {
                userID = String(authViewModel.generateRandomUserID())
            }
        }
    }
}

// MARK: - Feature Row Component
struct FeatureRow: View {
    let icon: String
    let title: String
    let description: String
    
    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.white)
                .frame(width: 40)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                
                Text(description)
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.8))
            }
            
            Spacer()
        }
        .padding()
        .background(Color.white.opacity(0.1))
        .cornerRadius(12)
    }
}

// MARK: - Profile View
struct ProfileView: View {
    @EnvironmentObject var authViewModel: AuthViewModel
    @EnvironmentObject var subscriptionManager: SubscriptionManager
    @State private var showingPremiumUpgrade = false
    @State private var showingSettings = false
    
    var body: some View {
        NavigationView {
            List {
                // User Info Section
                Section {
                    HStack {
                        Circle()
                            .fill(LinearGradient(colors: [.blue, .purple], startPoint: .topLeading, endPoint: .bottomTrailing))
                            .frame(width: 60, height: 60)
                            .overlay {
                                Text(authViewModel.currentUser?.displayName.prefix(1).uppercased() ?? "U")
                                    .font(.title2)
                                    .fontWeight(.bold)
                                    .foregroundColor(.white)
                            }
                        
                        VStack(alignment: .leading, spacing: 4) {
                            Text(authViewModel.currentUser?.displayName ?? "Unknown User")
                                .font(.headline)
                                .fontWeight(.semibold)
                            
                            Text("ID: \(authViewModel.currentUser?.id ?? 0)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            
                            // Subscription Status
                            HStack(spacing: 4) {
                                Circle()
                                    .fill(subscriptionManager.subscriptionStatus.color)
                                    .frame(width: 8, height: 8)
                                
                                Text(subscriptionManager.subscriptionStatus.displayName)
                                    .font(.caption)
                                    .fontWeight(.medium)
                                    .foregroundColor(subscriptionManager.subscriptionStatus.color)
                            }
                        }
                        
                        Spacer()
                    }
                    .padding(.vertical, 8)
                }
                
                // Subscription Section
                if !subscriptionManager.isPremium {
                    Section {
                        Button {
                            showingPremiumUpgrade = true
                        } label: {
                            HStack {
                                Image(systemName: "star.fill")
                                    .foregroundColor(.yellow)
                                
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Upgrade to Premium")
                                        .fontWeight(.semibold)
                                    
                                    Text("Unlock unlimited opportunities and advanced features")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                                
                                Spacer()
                                
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .foregroundColor(.primary)
                    }
                } else {
                    Section("Premium Subscription") {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Premium Active")
                                .font(.headline)
                                .foregroundColor(.blue)
                            
                            if let endDate = subscriptionManager.subscriptionEndDate {
                                Text("Expires: \(endDate, style: .date)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
                
                // App Features Section
                Section("Features") {
                    NavigationLink {
                        // EmptyView() // Would link to detailed features
                    } label: {
                        Label("Market Overview", systemImage: "chart.bar.fill")
                    }
                    
                    NavigationLink {
                        // EmptyView() // Would link to notifications settings
                    } label: {
                        Label("Notifications", systemImage: "bell.fill")
                    }
                    
                    NavigationLink {
                        // EmptyView() // Would link to export features
                    } label: {
                        Label("Export Data", systemImage: "square.and.arrow.up")
                    }
                }
                
                // Support Section
                Section("Support") {
                    Link(destination: URL(string: "mailto:support@cryptoarbitragepro.com")!) {
                        Label("Contact Support", systemImage: "envelope.fill")
                    }
                    
                    Link(destination: URL(string: "https://cryptoarbitragepro.com/privacy")!) {
                        Label("Privacy Policy", systemImage: "hand.raised.fill")
                    }
                    
                    Link(destination: URL(string: "https://cryptoarbitragepro.com/terms")!) {
                        Label("Terms of Service", systemImage: "doc.text.fill")
                    }
                }
                
                // Account Section
                Section("Account") {
                    Button {
                        authViewModel.signOut()
                    } label: {
                        Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                            .foregroundColor(.red)
                    }
                }
            }
            .navigationTitle("Profile")
        }
        .sheet(isPresented: $showingPremiumUpgrade) {
            PremiumUpgradeView()
                .environmentObject(subscriptionManager)
        }
    }
}

// MARK: - Premium Upgrade View
struct PremiumUpgradeView: View {
    @EnvironmentObject var subscriptionManager: SubscriptionManager
    @Environment(\.dismiss) private var dismiss
    @State private var selectedPlan: SubscriptionPlan?
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    // Header
                    VStack(spacing: 16) {
                        Image(systemName: "star.fill")
                            .font(.system(size: 60))
                            .foregroundColor(.yellow)
                        
                        Text("Upgrade to Premium")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                        
                        Text("Unlock the full potential of crypto arbitrage")
                            .font(.headline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top)
                    
                    // Features
                    VStack(spacing: 12) {
                        ForEach(SubscriptionManager.premiumFeatures, id: \.title) { feature in
                            PremiumFeatureRow(feature: feature)
                        }
                    }
                    
                    // Subscription Plans
                    VStack(spacing: 12) {
                        ForEach(SubscriptionManager.subscriptionPlans, id: \.id) { plan in
                            SubscriptionPlanCard(
                                plan: plan,
                                isSelected: selectedPlan?.id == plan.id
                            ) {
                                selectedPlan = plan
                            }
                        }
                    }
                    
                    // Purchase Button
                    if let selectedPlan = selectedPlan {
                        Button {
                            Task {
                                await subscriptionManager.purchaseSubscription(selectedPlan)
                                if subscriptionManager.isPremium {
                                    dismiss()
                                }
                            }
                        } label: {
                            if subscriptionManager.isLoading {
                                HStack {
                                    ProgressView()
                                        .scaleEffect(0.8)
                                    Text("Processing...")
                                }
                            } else {
                                Text("Subscribe for \(selectedPlan.formattedPrice)")
                                    .fontWeight(.semibold)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                        .disabled(subscriptionManager.isLoading)
                    }
                    
                    // Restore Purchases
                    Button {
                        Task {
                            await subscriptionManager.restorePurchases()
                        }
                    } label: {
                        Text("Restore Purchases")
                            .font(.subheadline)
                            .foregroundColor(.blue)
                    }
                }
                .padding()
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close") {
                        dismiss()
                    }
                }
            }
        }
        .onAppear {
            if selectedPlan == nil {
                selectedPlan = SubscriptionManager.subscriptionPlans.first { $0.isPopular } ?? SubscriptionManager.subscriptionPlans.first
            }
        }
    }
}

// MARK: - Supporting Components
struct PremiumFeatureRow: View {
    let feature: PremiumFeature
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: feature.icon)
                .font(.title3)
                .foregroundColor(.blue)
                .frame(width: 24)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(feature.title)
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Text(feature.description)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct SubscriptionPlanCard: View {
    let plan: SubscriptionPlan
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 12) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(plan.name)
                                .font(.headline)
                                .fontWeight(.bold)
                            
                            if plan.isPopular {
                                Text("POPULAR")
                                    .font(.caption)
                                    .fontWeight(.bold)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 2)
                                    .background(Color.orange)
                                    .foregroundColor(.white)
                                    .cornerRadius(4)
                            }
                        }
                        
                        Text(plan.description)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                    
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(plan.formattedPrice)
                            .font(.title2)
                            .fontWeight(.bold)
                        
                        Text(plan.pricePerMonth)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(plan.features, id: \.self) { feature in
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                                .font(.caption)
                            
                            Text(feature)
                                .font(.caption)
                                .foregroundColor(.secondary)
                            
                            Spacer()
                        }
                    }
                }
            }
            .padding()
            .background(isSelected ? Color.blue.opacity(0.1) : Color(.systemGray6))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
            )
            .cornerRadius(12)
        }
        .buttonStyle(PlainButtonStyle())
    }
}

// MARK: - Utility Views
struct EmptyStateView: View {
    let icon: String
    let title: String
    let subtitle: String
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 50))
                .foregroundColor(.secondary)
            
            VStack(spacing: 8) {
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
        }
        .padding()
    }
}

struct UpgradePromptCard: View {
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 12) {
                HStack {
                    Image(systemName: "star.fill")
                        .foregroundColor(.yellow)
                        .font(.title2)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Unlock More Opportunities")
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        Text("Upgrade to Premium for unlimited access")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                    
                    Text("Upgrade")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.blue)
                }
                .padding()
                .background(
                    LinearGradient(
                        colors: [.blue.opacity(0.1), .purple.opacity(0.1)],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.blue.opacity(0.3), lineWidth: 1)
                )
            }
        }
        .buttonStyle(PlainButtonStyle())
    }
}

// MARK: - Placeholder ViewModels
class WatchlistViewModel: ObservableObject {
    @Published var watchedSymbols: [String] = []
}

class PortfolioViewModel: ObservableObject {
    @Published var trades: [Trade] = []
    
    struct Trade {
        let id = UUID()
        let symbol: String
        let type: TradeType
        let amount: Double
        let price: Double
        let date: Date
        
        enum TradeType {
            case buy, sell
        }
    }
}

// MARK: - Placeholder Views
struct WatchlistView: View {
    var body: some View {
        NavigationView {
            Text("Watchlist Coming Soon")
                .navigationTitle("Watchlist")
        }
    }
}

struct PortfolioView: View {
    var body: some View {
        NavigationView {
            Text("Portfolio Tracking Coming Soon")
                .navigationTitle("Portfolio")
        }
    }
}

struct FiltersView: View {
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            Text("Advanced Filters Coming Soon")
                .navigationTitle("Filters")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("Done") {
                            dismiss()
                        }
                    }
                }
        }
    }
}

// MARK: - Previews
struct WelcomeView_Previews: PreviewProvider {
    static var previews: some View {
        WelcomeView()
            .environmentObject(AuthViewModel())
    }
}