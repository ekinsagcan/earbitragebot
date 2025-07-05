import Foundation
import SwiftUI
import Combine

@MainActor
class ArbitrageViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var opportunities: [ArbitrageOpportunity] = []
    @Published var isLoading = false
    @Published var isConnected = false
    @Published var errorMessage: String?
    @Published var lastUpdated: String?
    @Published var selectedOpportunity: ArbitrageOpportunity?
    
    // Filtering
    @Published var selectedRiskLevels: Set<RiskLevel> = []
    @Published var selectedCategories: Set<CoinCategory> = []
    @Published var minProfitThreshold: Double = 0.5
    @Published var minVolumeThreshold: Double = 10000
    @Published var selectedExchanges: Set<String> = []
    
    // Metadata
    @Published var totalFound = 0
    @Published var averageProfit: Double = 0
    @Published var maxProfit: Double = 0
    @Published var isPremiumData = false
    
    // MARK: - Private Properties
    private let apiService = APIService.shared
    private var refreshTimer: Timer?
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Computed Properties
    var filteredOpportunities: [ArbitrageOpportunity] {
        opportunities.filter { opportunity in
            // Risk level filter
            if !selectedRiskLevels.isEmpty && !selectedRiskLevels.contains(opportunity.riskLevel) {
                return false
            }
            
            // Category filter
            if !selectedCategories.isEmpty && !selectedCategories.contains(opportunity.category) {
                return false
            }
            
            // Profit threshold filter
            if opportunity.profitPercent < minProfitThreshold {
                return false
            }
            
            // Volume threshold filter
            if opportunity.volume24h < minVolumeThreshold {
                return false
            }
            
            // Exchange filter
            if !selectedExchanges.isEmpty {
                let hasSelectedExchange = selectedExchanges.contains(opportunity.exchange1) || 
                                         selectedExchanges.contains(opportunity.exchange2)
                if !hasSelectedExchange {
                    return false
                }
            }
            
            return true
        }
    }
    
    // MARK: - Initialization
    init() {
        setupAutoRefresh()
        setupFiltersObserver()
    }
    
    deinit {
        refreshTimer?.invalidate()
    }
    
    // MARK: - Public Methods
    func loadOpportunities() async {
        await fetchOpportunities()
    }
    
    func refreshOpportunities() async {
        await fetchOpportunities(forceRefresh: true)
    }
    
    func toggleRiskFilter(_ risk: RiskLevel) {
        if selectedRiskLevels.contains(risk) {
            selectedRiskLevels.remove(risk)
        } else {
            selectedRiskLevels.insert(risk)
        }
        applyFilters()
    }
    
    func toggleCategoryFilter(_ category: CoinCategory) {
        if selectedCategories.contains(category) {
            selectedCategories.remove(category)
        } else {
            selectedCategories.insert(category)
        }
        applyFilters()
    }
    
    func clearAllFilters() {
        selectedRiskLevels.removeAll()
        selectedCategories.removeAll()
        selectedExchanges.removeAll()
        minProfitThreshold = 0.5
        minVolumeThreshold = 10000
        applyFilters()
    }
    
    func loadPremiumPreview() async {
        do {
            isLoading = true
            let response = await apiService.fetchPremiumPreview()
            
            switch response {
            case .success(let data):
                processArbitrageData(data)
                isConnected = true
                errorMessage = nil
                
            case .failure(let error):
                handleError(error)
            }
        } catch {
            handleError(error)
        }
        
        isLoading = false
    }
    
    // MARK: - Private Methods
    private func fetchOpportunities(forceRefresh: Bool = false) async {
        do {
            isLoading = true
            
            // Build filter parameters
            let filters = buildFilterParameters()
            
            let response = await apiService.fetchArbitrageOpportunities(
                filters: filters,
                forceRefresh: forceRefresh
            )
            
            switch response {
            case .success(let data):
                processArbitrageData(data)
                isConnected = true
                errorMessage = nil
                updateLastUpdatedTime()
                
            case .failure(let error):
                handleError(error)
            }
        } catch {
            handleError(error)
        }
        
        isLoading = false
    }
    
    private func processArbitrageData(_ data: ArbitrageData) {
        opportunities = data.opportunities
        totalFound = data.metadata.totalFound
        isPremiumData = data.metadata.isPremium
        
        // Calculate statistics
        if !opportunities.isEmpty {
            averageProfit = opportunities.map(\.profitPercent).reduce(0, +) / Double(opportunities.count)
            maxProfit = opportunities.map(\.profitPercent).max() ?? 0
        } else {
            averageProfit = 0
            maxProfit = 0
        }
        
        // Apply current filters
        applyFilters()
    }
    
    private func buildFilterParameters() -> [String: Any] {
        var parameters: [String: Any] = [:]
        
        if !selectedRiskLevels.isEmpty {
            let riskLevels = selectedRiskLevels.map(\.rawValue)
            if riskLevels.count < RiskLevel.allCases.count - 1 { // Exclude 'unknown'
                if riskLevels.contains("high") {
                    parameters["max_risk"] = "high"
                } else if riskLevels.contains("medium") {
                    parameters["max_risk"] = "medium"
                } else if riskLevels.contains("low") {
                    parameters["max_risk"] = "low"
                }
            }
        }
        
        if !selectedCategories.isEmpty {
            parameters["categories"] = selectedCategories.map(\.rawValue).joined(separator: ",")
        }
        
        if !selectedExchanges.isEmpty {
            parameters["exchanges"] = Array(selectedExchanges).joined(separator: ",")
        }
        
        if minProfitThreshold > 0.5 {
            parameters["min_profit"] = minProfitThreshold
        }
        
        if minVolumeThreshold > 10000 {
            parameters["min_volume"] = minVolumeThreshold
        }
        
        return parameters
    }
    
    private func applyFilters() {
        // This is handled by the computed property filteredOpportunities
        // We could add local filtering here if needed for performance
    }
    
    private func handleError(_ error: Error) {
        isConnected = false
        
        if let apiError = error as? APIError {
            switch apiError {
            case .networkError:
                errorMessage = "Network connection error. Please check your internet connection."
            case .invalidResponse:
                errorMessage = "Invalid response from server. Please try again."
            case .serverError(let message):
                errorMessage = "Server error: \(message)"
            case .unauthorized:
                errorMessage = "Authentication required. Please log in again."
            case .forbidden:
                errorMessage = "Access denied. Please check your subscription status."
            case .notFound:
                errorMessage = "Resource not found."
            case .decodingError:
                errorMessage = "Data parsing error. Please try again."
            case .unknown(let message):
                errorMessage = "Unknown error: \(message)"
            }
        } else {
            errorMessage = "An unexpected error occurred: \(error.localizedDescription)"
        }
    }
    
    private func updateLastUpdatedTime() {
        let formatter = DateFormatter()
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        lastUpdated = formatter.string(from: Date())
    }
    
    private func setupAutoRefresh() {
        // Auto-refresh every 30 seconds when app is active
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { _ in
            Task {
                await self.fetchOpportunities()
            }
        }
    }
    
    private func setupFiltersObserver() {
        // Observe filter changes and apply them
        Publishers.CombineLatest4(
            $selectedRiskLevels,
            $selectedCategories,
            $minProfitThreshold,
            $minVolumeThreshold
        )
        .debounce(for: .milliseconds(300), scheduler: DispatchQueue.main)
        .sink { [weak self] _, _, _, _ in
            self?.applyFilters()
        }
        .store(in: &cancellables)
    }
}

// MARK: - Opportunity Detail Methods
extension ArbitrageViewModel {
    func getOpportunityDetail(_ opportunity: ArbitrageOpportunity) -> OpportunityDetailData {
        return OpportunityDetailData(
            opportunity: opportunity,
            riskAnalysis: analyzeRisk(opportunity),
            tradingSteps: generateTradingSteps(opportunity),
            similarOpportunities: findSimilarOpportunities(opportunity)
        )
    }
    
    private func analyzeRisk(_ opportunity: ArbitrageOpportunity) -> RiskAnalysis {
        return RiskAnalysis(
            overallScore: opportunity.riskData.score,
            factors: opportunity.riskData.factors,
            confidence: opportunity.riskData.confidence,
            recommendation: generateRiskRecommendation(opportunity)
        )
    }
    
    private func generateRiskRecommendation(_ opportunity: ArbitrageOpportunity) -> String {
        switch opportunity.riskLevel {
        case .low:
            return "Low risk opportunity with high confidence. Suitable for conservative traders."
        case .medium:
            return "Moderate risk with balanced potential. Consider your risk tolerance."
        case .high:
            return "High risk opportunity. Only suitable for experienced traders willing to accept significant risk."
        case .unknown:
            return "Risk level unclear. Proceed with extreme caution."
        }
    }
    
    private func generateTradingSteps(_ opportunity: ArbitrageOpportunity) -> [TradingStep] {
        return [
            TradingStep(
                step: 1,
                action: "Buy \(opportunity.displaySymbol)",
                exchange: opportunity.exchange1.capitalized,
                price: opportunity.price1,
                details: "Purchase at the lower price on \(opportunity.exchange1.capitalized)"
            ),
            TradingStep(
                step: 2,
                action: "Transfer (if needed)",
                exchange: "Network",
                price: 0,
                details: "Transfer funds to \(opportunity.exchange2.capitalized) if holding on different exchanges"
            ),
            TradingStep(
                step: 3,
                action: "Sell \(opportunity.displaySymbol)",
                exchange: opportunity.exchange2.capitalized,
                price: opportunity.price2,
                details: "Sell at the higher price on \(opportunity.exchange2.capitalized)"
            )
        ]
    }
    
    private func findSimilarOpportunities(_ opportunity: ArbitrageOpportunity) -> [ArbitrageOpportunity] {
        return opportunities.filter { other in
            other.id != opportunity.id &&
            (other.category == opportunity.category ||
             other.exchange1 == opportunity.exchange1 ||
             other.exchange2 == opportunity.exchange2)
        }.prefix(3).map { $0 }
    }
}

// MARK: - Supporting Data Structures
struct OpportunityDetailData {
    let opportunity: ArbitrageOpportunity
    let riskAnalysis: RiskAnalysis
    let tradingSteps: [TradingStep]
    let similarOpportunities: [ArbitrageOpportunity]
}

struct RiskAnalysis {
    let overallScore: Int
    let factors: [String]
    let confidence: Int
    let recommendation: String
}

struct TradingStep {
    let step: Int
    let action: String
    let exchange: String
    let price: Double
    let details: String
}