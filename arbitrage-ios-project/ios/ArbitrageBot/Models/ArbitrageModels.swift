import Foundation
import SwiftUI

// MARK: - Arbitrage Opportunity
struct ArbitrageOpportunity: Identifiable, Codable, Hashable {
    let id = UUID()
    let symbol: String
    let exchange1: String
    let exchange2: String
    let price1: Double
    let price2: Double
    let profitPercent: Double
    let volume24h: Double
    let timestamp: Date
    let buyExchangeTier: String
    let sellExchangeTier: String
    let totalExchanges: Int
    let riskLevel: RiskLevel
    let riskData: RiskData
    let opportunityScore: Double
    let category: CoinCategory
    
    // Computed properties
    var profitAmount: Double {
        price2 - price1
    }
    
    var displaySymbol: String {
        symbol.replacingOccurrences(of: "USDT", with: "/USDT")
    }
    
    var riskColor: Color {
        riskLevel.color
    }
    
    var categoryColor: Color {
        category.color
    }
    
    var confidenceScore: Int {
        riskData.confidence
    }
    
    private enum CodingKeys: String, CodingKey {
        case symbol, exchange1, exchange2, price1, price2
        case profitPercent = "profit_percent"
        case volume24h = "volume_24h"
        case timestamp
        case buyExchangeTier = "buy_exchange_tier"
        case sellExchangeTier = "sell_exchange_tier"
        case totalExchanges = "total_exchanges"
        case riskLevel = "risk_level"
        case riskData = "risk_data"
        case opportunityScore = "opportunity_score"
        case category
    }
}

// MARK: - Risk Level
enum RiskLevel: String, Codable, CaseIterable {
    case low = "low"
    case medium = "medium"
    case high = "high"
    case unknown = "unknown"
    
    var displayName: String {
        switch self {
        case .low: return "Low Risk"
        case .medium: return "Medium Risk"
        case .high: return "High Risk"
        case .unknown: return "Unknown"
        }
    }
    
    var color: Color {
        switch self {
        case .low: return .green
        case .medium: return .orange
        case .high: return .red
        case .unknown: return .gray
        }
    }
    
    var icon: String {
        switch self {
        case .low: return "shield.checkered"
        case .medium: return "exclamationmark.triangle"
        case .high: return "exclamationmark.octagon"
        case .unknown: return "questionmark.circle"
        }
    }
}

// MARK: - Risk Data
struct RiskData: Codable, Hashable {
    let score: Int
    let factors: [String]
    let confidence: Int
    
    var primaryFactor: String {
        factors.first ?? "unknown"
    }
    
    var riskDescription: String {
        if factors.isEmpty {
            return "Risk analysis unavailable"
        }
        
        let mainFactors = factors.prefix(2).joined(separator: ", ")
        return "Main risks: \(mainFactors)"
    }
}

// MARK: - Coin Category
enum CoinCategory: String, Codable, CaseIterable {
    case layer1 = "layer1"
    case layer2 = "layer2"
    case defi = "defi"
    case exchange = "exchange"
    case meme = "meme"
    case payment = "payment"
    case other = "other"
    
    var displayName: String {
        switch self {
        case .layer1: return "Layer 1"
        case .layer2: return "Layer 2"
        case .defi: return "DeFi"
        case .exchange: return "Exchange"
        case .meme: return "Meme"
        case .payment: return "Payment"
        case .other: return "Other"
        }
    }
    
    var color: Color {
        switch self {
        case .layer1: return .blue
        case .layer2: return .purple
        case .defi: return .green
        case .exchange: return .orange
        case .meme: return .pink
        case .payment: return .cyan
        case .other: return .gray
        }
    }
    
    var icon: String {
        switch self {
        case .layer1: return "cube"
        case .layer2: return "square.stack"
        case .defi: return "chart.line.uptrend.xyaxis"
        case .exchange: return "building.2"
        case .meme: return "face.smiling"
        case .payment: return "creditcard"
        case .other: return "questionmark.circle"
        }
    }
}

// MARK: - Exchange Tier
enum ExchangeTier: String, Codable, CaseIterable {
    case tier1 = "tier_1"
    case tier2 = "tier_2"
    case tier3 = "tier_3"
    
    var displayName: String {
        switch self {
        case .tier1: return "Tier 1"
        case .tier2: return "Tier 2"
        case .tier3: return "Tier 3"
        }
    }
    
    var color: Color {
        switch self {
        case .tier1: return .green
        case .tier2: return .orange
        case .tier3: return .red
        }
    }
    
    var trustLevel: String {
        switch self {
        case .tier1: return "High Trust"
        case .tier2: return "Medium Trust"
        case .tier3: return "Lower Trust"
        }
    }
}

// MARK: - Symbol Price Data
struct SymbolPriceData: Identifiable, Codable, Hashable {
    let id = UUID()
    let exchange: String
    let price: Double
    let volume24h: Double
    let change24h: Double
    let tier: String
    let timestamp: String
    
    var exchangeTier: ExchangeTier {
        ExchangeTier(rawValue: tier) ?? .tier3
    }
    
    var formattedPrice: String {
        price.formatted(.currency(code: "USD"))
    }
    
    var formattedVolume: String {
        if volume24h >= 1_000_000 {
            return String(format: "%.1fM", volume24h / 1_000_000)
        } else if volume24h >= 1_000 {
            return String(format: "%.1fK", volume24h / 1_000)
        } else {
            return String(format: "%.0f", volume24h)
        }
    }
    
    var change24hColor: Color {
        change24h >= 0 ? .green : .red
    }
    
    private enum CodingKeys: String, CodingKey {
        case exchange, price, tier, timestamp
        case volume24h = "volume_24h"
        case change24h = "change_24h"
    }
}

// MARK: - Market Statistics
struct MarketStatistics: Codable {
    let totalOpportunities: Int
    let avgProfit: Double
    let maxProfit: Double
    let riskDistribution: [String: Int]
    let categoryDistribution: [String: Int]
    let topSymbols: [String]
    let message: String?
    
    private enum CodingKeys: String, CodingKey {
        case totalOpportunities = "total_opportunities"
        case avgProfit = "avg_profit"
        case maxProfit = "max_profit"
        case riskDistribution = "risk_distribution"
        case categoryDistribution = "category_distribution"
        case topSymbols = "top_symbols"
        case message
    }
}

// MARK: - API Response Wrapper
struct ArbitrageResponse: Codable {
    let success: Bool
    let data: ArbitrageData?
    let message: String?
}

struct ArbitrageData: Codable {
    let opportunities: [ArbitrageOpportunity]
    let metadata: ResponseMetadata
}

struct ResponseMetadata: Codable {
    let totalFound: Int
    let isPremium: Bool
    let lastUpdated: String
    let userTier: String
    let appliedFilters: [String: AnyCodable]?
    let cacheMetadata: CacheMetadata?
    let performance: PerformanceData?
    let previewMode: Bool?
    let upgradeMessage: String?
    
    private enum CodingKeys: String, CodingKey {
        case totalFound = "total_found"
        case isPremium = "is_premium"
        case lastUpdated = "last_updated"
        case userTier = "user_tier"
        case appliedFilters = "applied_filters"
        case cacheMetadata = "cache_metadata"
        case performance
        case previewMode = "preview_mode"
        case upgradeMessage = "upgrade_message"
    }
}

struct CacheMetadata: Codable {
    let lastUpdate: String
    let exchangeCount: Int
    let symbolCount: Int
    
    private enum CodingKeys: String, CodingKey {
        case lastUpdate = "last_update"
        case exchangeCount = "exchange_count"
        case symbolCount = "symbol_count"
    }
}

struct PerformanceData: Codable {
    let avgResponseTime: Double
    let activeExchanges: Int
    let successRate: Double
    let totalApiRequests: Int
    
    private enum CodingKeys: String, CodingKey {
        case avgResponseTime = "avg_response_time"
        case activeExchanges = "active_exchanges"
        case successRate = "success_rate"
        case totalApiRequests = "total_api_requests"
    }
}

// MARK: - Helper for dynamic JSON values
struct AnyCodable: Codable {
    let value: Any
    
    init<T>(_ value: T?) {
        self.value = value ?? ()
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dictionary = try? container.decode([String: AnyCodable].self) {
            value = dictionary.mapValues { $0.value }
        } else {
            value = ()
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        
        switch value {
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        default:
            try container.encode(())
        }
    }
}

// MARK: - Sample Data (for SwiftUI Previews)
extension ArbitrageOpportunity {
    static let sampleData = ArbitrageOpportunity(
        symbol: "BTCUSDT",
        exchange1: "binance",
        exchange2: "kucoin",
        price1: 43250.50,
        price2: 43512.30,
        profitPercent: 0.61,
        volume24h: 2500000,
        timestamp: Date(),
        buyExchangeTier: "tier_1",
        sellExchangeTier: "tier_2",
        totalExchanges: 8,
        riskLevel: .low,
        riskData: RiskData(score: 2, factors: ["premium_coin"], confidence: 85),
        opportunityScore: 75.5,
        category: .layer1
    )
    
    static let sampleHighRisk = ArbitrageOpportunity(
        symbol: "SHIBAINU",
        exchange1: "mexc",
        exchange2: "lbank",
        price1: 0.00000845,
        price2: 0.00000912,
        profitPercent: 7.93,
        volume24h: 45000,
        timestamp: Date(),
        buyExchangeTier: "tier_3",
        sellExchangeTier: "tier_3",
        totalExchanges: 3,
        riskLevel: .high,
        riskData: RiskData(score: 8, factors: ["high_profit_7.9%", "low_volume_45k", "tier3_exchanges"], confidence: 25),
        opportunityScore: 42.1,
        category: .meme
    )
}