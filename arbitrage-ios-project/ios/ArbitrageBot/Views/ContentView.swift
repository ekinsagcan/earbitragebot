import SwiftUI

struct ContentView: View {
    @EnvironmentObject var appManager: AppManager
    @EnvironmentObject var authViewModel: AuthViewModel
    @EnvironmentObject var subscriptionManager: SubscriptionManager
    @State private var showingWelcome = false
    
    var body: some View {
        Group {
            if authViewModel.isAuthenticated {
                MainTabView()
            } else {
                WelcomeView()
            }
        }
        .alert("Error", isPresented: $appManager.showingErrorAlert) {
            Button("OK") { }
        } message: {
            Text(appManager.errorMessage)
        }
        .onAppear {
            checkFirstLaunch()
        }
    }
    
    private func checkFirstLaunch() {
        let hasLaunchedBefore = UserDefaults.standard.bool(forKey: "hasLaunchedBefore")
        if !hasLaunchedBefore {
            showingWelcome = true
            UserDefaults.standard.set(true, forKey: "hasLaunchedBefore")
        }
    }
}

// MARK: - Main Tab View
struct MainTabView: View {
    @EnvironmentObject var appManager: AppManager
    @StateObject private var arbitrageViewModel = ArbitrageViewModel()
    @StateObject private var watchlistViewModel = WatchlistViewModel()
    @StateObject private var portfolioViewModel = PortfolioViewModel()
    
    var body: some View {
        TabView(selection: $appManager.currentTab) {
            DiscoverView()
                .environmentObject(arbitrageViewModel)
                .tabItem {
                    Label(MainTab.discover.rawValue, 
                          systemImage: appManager.currentTab == .discover ? 
                          MainTab.discover.selectedIcon : MainTab.discover.icon)
                }
                .tag(MainTab.discover)
            
            WatchlistView()
                .environmentObject(watchlistViewModel)
                .tabItem {
                    Label(MainTab.watchlist.rawValue, 
                          systemImage: appManager.currentTab == .watchlist ? 
                          MainTab.watchlist.selectedIcon : MainTab.watchlist.icon)
                }
                .tag(MainTab.watchlist)
            
            PortfolioView()
                .environmentObject(portfolioViewModel)
                .tabItem {
                    Label(MainTab.portfolio.rawValue, 
                          systemImage: appManager.currentTab == .portfolio ? 
                          MainTab.portfolio.selectedIcon : MainTab.portfolio.icon)
                }
                .tag(MainTab.portfolio)
            
            ProfileView()
                .tabItem {
                    Label(MainTab.profile.rawValue, 
                          systemImage: appManager.currentTab == .profile ? 
                          MainTab.profile.selectedIcon : MainTab.profile.icon)
                }
                .tag(MainTab.profile)
        }
        .accentColor(.blue)
    }
}

// MARK: - Discover View (Main Dashboard)
struct DiscoverView: View {
    @EnvironmentObject var arbitrageViewModel: ArbitrageViewModel
    @EnvironmentObject var subscriptionManager: SubscriptionManager
    @State private var showingFilters = false
    @State private var showingPremiumUpgrade = false
    @State private var refreshing = false
    
    var body: some View {
        NavigationView {
            ZStack {
                // Background gradient
                LinearGradient(
                    colors: [.blue.opacity(0.05), .purple.opacity(0.05)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                ScrollView {
                    LazyVStack(spacing: 16) {
                        // Header Stats
                        headerStatsView
                        
                        // Quick Filters
                        quickFiltersView
                        
                        // Opportunities List
                        opportunitiesListView
                        
                        // Premium Upgrade Prompt (for free users)
                        if !subscriptionManager.isPremium {
                            premiumPromptView
                        }
                    }
                    .padding(.horizontal)
                }
                .refreshable {
                    await refreshData()
                }
            }
            .navigationTitle("Discover")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showingFilters = true
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                            .foregroundColor(.blue)
                    }
                }
                
                ToolbarItem(placement: .navigationBarLeading) {
                    HStack {
                        Circle()
                            .fill(arbitrageViewModel.isConnected ? .green : .red)
                            .frame(width: 8, height: 8)
                        
                        Text(arbitrageViewModel.isConnected ? "Live" : "Offline")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
        .task {
            await arbitrageViewModel.loadOpportunities()
        }
        .sheet(isPresented: $showingFilters) {
            FiltersView()
                .environmentObject(arbitrageViewModel)
        }
        .sheet(isPresented: $showingPremiumUpgrade) {
            PremiumUpgradeView()
                .environmentObject(subscriptionManager)
        }
    }
    
    // MARK: - Header Stats View
    private var headerStatsView: some View {
        VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Total Opportunities")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text("\(arbitrageViewModel.opportunities.count)")
                        .font(.title2)
                        .fontWeight(.bold)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("Avg Profit")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text("\(arbitrageViewModel.averageProfit, specifier: "%.2f")%")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.green)
                }
            }
            
            Divider()
            
            HStack {
                Label("Last Updated", systemImage: "clock")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Text(arbitrageViewModel.lastUpdated ?? "Never")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2, y: 1)
    }
    
    // MARK: - Quick Filters View
    private var quickFiltersView: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                ForEach(RiskLevel.allCases.filter { $0 != .unknown }, id: \.self) { risk in
                    FilterChip(
                        title: risk.displayName,
                        icon: risk.icon,
                        isSelected: arbitrageViewModel.selectedRiskLevels.contains(risk),
                        color: risk.color
                    ) {
                        arbitrageViewModel.toggleRiskFilter(risk)
                    }
                }
                
                ForEach(CoinCategory.allCases.prefix(4), id: \.self) { category in
                    FilterChip(
                        title: category.displayName,
                        icon: category.icon,
                        isSelected: arbitrageViewModel.selectedCategories.contains(category),
                        color: category.color
                    ) {
                        arbitrageViewModel.toggleCategoryFilter(category)
                    }
                }
            }
            .padding(.horizontal)
        }
    }
    
    // MARK: - Opportunities List View
    private var opportunitiesListView: some View {
        LazyVStack(spacing: 12) {
            if arbitrageViewModel.isLoading {
                ForEach(0..<5) { _ in
                    OpportunityCardSkeleton()
                }
            } else if arbitrageViewModel.opportunities.isEmpty {
                EmptyStateView(
                    icon: "magnifyingglass",
                    title: "No Opportunities Found",
                    subtitle: "Try adjusting your filters or check back later"
                )
                .padding(.vertical, 40)
            } else {
                ForEach(Array(arbitrageViewModel.opportunities.enumerated()), id: \.element.id) { index, opportunity in
                    OpportunityCard(
                        opportunity: opportunity,
                        rank: index + 1,
                        isPremium: subscriptionManager.isPremium
                    ) {
                        // Navigate to detail view
                        arbitrageViewModel.selectedOpportunity = opportunity
                    }
                    
                    // Show upgrade prompt after 5th item for free users
                    if !subscriptionManager.isPremium && index == 4 {
                        UpgradePromptCard {
                            showingPremiumUpgrade = true
                        }
                    }
                }
            }
        }
    }
    
    // MARK: - Premium Prompt View
    private var premiumPromptView: some View {
        VStack(spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Unlock Premium Features")
                        .font(.headline)
                        .fontWeight(.semibold)
                    
                    Text("Get unlimited opportunities, advanced analytics, and real-time alerts")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Button("Upgrade") {
                    showingPremiumUpgrade = true
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()
            .background(Color.blue.opacity(0.1))
            .cornerRadius(12)
        }
    }
    
    @MainActor
    private func refreshData() async {
        refreshing = true
        await arbitrageViewModel.refreshOpportunities()
        refreshing = false
    }
}

// MARK: - Filter Chip Component
struct FilterChip: View {
    let title: String
    let icon: String
    let isSelected: Bool
    let color: Color
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.caption)
                
                Text(title)
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                Group {
                    if isSelected {
                        color.opacity(0.2)
                    } else {
                        Color(.systemGray6)
                    }
                }
            )
            .foregroundColor(isSelected ? color : .primary)
            .cornerRadius(16)
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(isSelected ? color : Color.clear, lineWidth: 1)
            )
        }
    }
}

// MARK: - Opportunity Card
struct OpportunityCard: View {
    let opportunity: ArbitrageOpportunity
    let rank: Int
    let isPremium: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 12) {
                // Header with rank and symbol
                HStack {
                    HStack(spacing: 8) {
                        Text("#\(rank)")
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundColor(.secondary)
                        
                        Text(opportunity.displaySymbol)
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        // Category badge
                        Text(opportunity.category.displayName)
                            .font(.caption2)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(opportunity.categoryColor.opacity(0.2))
                            .foregroundColor(opportunity.categoryColor)
                            .cornerRadius(4)
                    }
                    
                    Spacer()
                    
                    // Profit percentage
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("+\(opportunity.profitPercent, specifier: "%.2f")%")
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(.green)
                        
                        Text("$\(opportunity.profitAmount, specifier: "%.2f")")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                // Exchange info
                HStack {
                    ExchangeInfo(
                        name: opportunity.exchange1.capitalized,
                        price: opportunity.price1,
                        tier: ExchangeTier(rawValue: opportunity.buyExchangeTier) ?? .tier3,
                        type: "Buy"
                    )
                    
                    Image(systemName: "arrow.right")
                        .foregroundColor(.blue)
                        .font(.caption)
                    
                    ExchangeInfo(
                        name: opportunity.exchange2.capitalized,
                        price: opportunity.price2,
                        tier: ExchangeTier(rawValue: opportunity.sellExchangeTier) ?? .tier3,
                        type: "Sell"
                    )
                    
                    Spacer()
                }
                
                // Risk and metadata
                HStack {
                    HStack(spacing: 4) {
                        Image(systemName: opportunity.riskLevel.icon)
                            .foregroundColor(opportunity.riskColor)
                            .font(.caption)
                        
                        Text(opportunity.riskLevel.displayName)
                            .font(.caption)
                            .foregroundColor(opportunity.riskColor)
                    }
                    
                    Spacer()
                    
                    HStack(spacing: 8) {
                        Text("Vol: \(formatVolume(opportunity.volume24h))")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        
                        Text("Score: \(Int(opportunity.opportunityScore))")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(12)
            .shadow(radius: 2, y: 1)
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    private func formatVolume(_ volume: Double) -> String {
        if volume >= 1_000_000 {
            return String(format: "%.1fM", volume / 1_000_000)
        } else if volume >= 1_000 {
            return String(format: "%.1fK", volume / 1_000)
        } else {
            return String(format: "%.0f", volume)
        }
    }
}

// MARK: - Exchange Info Component
struct ExchangeInfo: View {
    let name: String
    let price: Double
    let tier: ExchangeTier
    let type: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                Text(name)
                    .font(.caption)
                    .fontWeight(.medium)
                
                Circle()
                    .fill(tier.color)
                    .frame(width: 6, height: 6)
            }
            
            Text("$\(price, specifier: "%.6f")")
                .font(.caption2)
                .foregroundColor(.secondary)
            
            Text(type)
                .font(.caption2)
                .foregroundColor(type == "Buy" ? .blue : .orange)
        }
    }
}

// MARK: - Skeleton Loading View
struct OpportunityCardSkeleton: View {
    @State private var isAnimating = false
    
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.3))
                    .frame(width: 80, height: 20)
                
                Spacer()
                
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.3))
                    .frame(width: 60, height: 20)
            }
            
            HStack {
                ForEach(0..<3) { _ in
                    VStack(spacing: 4) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.gray.opacity(0.3))
                            .frame(width: 50, height: 12)
                        
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.gray.opacity(0.3))
                            .frame(width: 60, height: 10)
                    }
                }
                Spacer()
            }
            
            HStack {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.3))
                    .frame(width: 70, height: 16)
                
                Spacer()
                
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.3))
                    .frame(width: 100, height: 16)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2, y: 1)
        .opacity(isAnimating ? 0.5 : 1.0)
        .animation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true), value: isAnimating)
        .onAppear {
            isAnimating = true
        }
    }
}

// MARK: - Preview
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
            .environmentObject(AppManager.shared)
            .environmentObject(AuthViewModel())
            .environmentObject(SubscriptionManager())
    }
}