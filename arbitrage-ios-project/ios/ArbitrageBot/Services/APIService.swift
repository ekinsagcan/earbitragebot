import Foundation
import Combine

// MARK: - API Error Types
enum APIError: Error, LocalizedError {
    case networkError
    case invalidResponse
    case serverError(String)
    case unauthorized
    case forbidden
    case notFound
    case decodingError
    case unknown(String)
    
    var errorDescription: String? {
        switch self {
        case .networkError:
            return "Network connection error"
        case .invalidResponse:
            return "Invalid response from server"
        case .serverError(let message):
            return "Server error: \(message)"
        case .unauthorized:
            return "Authentication required"
        case .forbidden:
            return "Access forbidden"
        case .notFound:
            return "Resource not found"
        case .decodingError:
            return "Data parsing error"
        case .unknown(let message):
            return "Unknown error: \(message)"
        }
    }
}

// MARK: - API Service
class APIService: ObservableObject {
    static let shared = APIService()
    
    // MARK: - Configuration
    private let baseURL: String
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder
    
    // MARK: - Authentication
    @Published var authToken: String?
    @Published var isAuthenticated = false
    
    // MARK: - Initialization
    private init() {
        // Configure base URL - in production, this would come from configuration
        #if DEBUG
        self.baseURL = "http://localhost:8000"
        #else
        self.baseURL = "https://your-api-domain.com"
        #endif
        
        // Configure URLSession
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30.0
        config.timeoutIntervalForResource = 60.0
        self.session = URLSession(configuration: config)
        
        // Configure JSON handling
        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601
        
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
        
        // Load saved auth token
        loadAuthToken()
    }
    
    // MARK: - Initialization Methods
    func initialize() async {
        // Perform any necessary initialization
        await validateAuthToken()
    }
    
    // MARK: - Authentication Methods
    func authenticate(userID: Int, username: String? = nil) async -> Result<AuthResponse, APIError> {
        let loginData = UserLogin(userID: userID, username: username)
        
        do {
            let data = try encoder.encode(loginData)
            let request = createRequest(
                path: "/api/v1/auth/login",
                method: "POST",
                body: data
            )
            
            let (responseData, response) = try await session.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                switch httpResponse.statusCode {
                case 200...299:
                    let authResponse = try decoder.decode(AuthResponse.self, from: responseData)
                    await MainActor.run {
                        self.authToken = authResponse.accessToken
                        self.isAuthenticated = true
                        self.saveAuthToken(authResponse.accessToken)
                    }
                    return .success(authResponse)
                    
                case 401:
                    return .failure(.unauthorized)
                    
                case 403:
                    return .failure(.forbidden)
                    
                default:
                    return .failure(.serverError("HTTP \(httpResponse.statusCode)"))
                }
            }
            
            return .failure(.invalidResponse)
            
        } catch {
            if error is DecodingError {
                return .failure(.decodingError)
            }
            return .failure(.networkError)
        }
    }
    
    func register(userID: Int, username: String? = nil) async -> Result<AuthResponse, APIError> {
        let registerData = UserRegister(userID: userID, username: username)
        
        do {
            let data = try encoder.encode(registerData)
            let request = createRequest(
                path: "/api/v1/auth/register",
                method: "POST",
                body: data
            )
            
            let (responseData, response) = try await session.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                switch httpResponse.statusCode {
                case 200...299:
                    let authResponse = try decoder.decode(AuthResponse.self, from: responseData)
                    await MainActor.run {
                        self.authToken = authResponse.accessToken
                        self.isAuthenticated = true
                        self.saveAuthToken(authResponse.accessToken)
                    }
                    return .success(authResponse)
                    
                default:
                    return .failure(.serverError("HTTP \(httpResponse.statusCode)"))
                }
            }
            
            return .failure(.invalidResponse)
            
        } catch {
            if error is DecodingError {
                return .failure(.decodingError)
            }
            return .failure(.networkError)
        }
    }
    
    func logout() {
        authToken = nil
        isAuthenticated = false
        removeAuthToken()
    }
    
    // MARK: - Arbitrage API Methods
    func fetchArbitrageOpportunities(
        filters: [String: Any] = [:],
        forceRefresh: Bool = false
    ) async -> Result<ArbitrageData, APIError> {
        
        var queryItems: [URLQueryItem] = []
        
        // Add filter parameters
        for (key, value) in filters {
            if let stringValue = value as? String {
                queryItems.append(URLQueryItem(name: key, value: stringValue))
            } else if let numberValue = value as? Double {
                queryItems.append(URLQueryItem(name: key, value: String(numberValue)))
            } else if let intValue = value as? Int {
                queryItems.append(URLQueryItem(name: key, value: String(intValue)))
            }
        }
        
        let request = createRequest(
            path: "/api/v1/arbitrage/opportunities",
            method: "GET",
            queryItems: queryItems,
            requiresAuth: true
        )
        
        return await performRequest(request, responseType: APIResponseWrapper<ArbitrageData>.self)
    }
    
    func fetchPremiumPreview() async -> Result<ArbitrageData, APIError> {
        let request = createRequest(
            path: "/api/v1/arbitrage/opportunities/premium-preview",
            method: "GET",
            requiresAuth: true
        )
        
        return await performRequest(request, responseType: APIResponseWrapper<ArbitrageData>.self)
    }
    
    func fetchSymbolPrices(symbol: String) async -> Result<SymbolPricesData, APIError> {
        let request = createRequest(
            path: "/api/v1/arbitrage/symbol/\(symbol)",
            method: "GET",
            requiresAuth: true
        )
        
        return await performRequest(request, responseType: APIResponseWrapper<SymbolPricesData>.self)
    }
    
    func fetchMarketOverview() async -> Result<MarketOverviewData, APIError> {
        let request = createRequest(
            path: "/api/v1/arbitrage/markets/overview",
            method: "GET",
            requiresAuth: true
        )
        
        return await performRequest(request, responseType: APIResponseWrapper<MarketOverviewData>.self)
    }
    
    func fetchFilterOptions() async -> Result<FilterOptionsData, APIError> {
        let request = createRequest(
            path: "/api/v1/arbitrage/filters/options",
            method: "GET"
        )
        
        return await performRequest(request, responseType: APIResponseWrapper<FilterOptionsData>.self)
    }
    
    // MARK: - Private Helper Methods
    private func createRequest(
        path: String,
        method: String = "GET",
        body: Data? = nil,
        queryItems: [URLQueryItem]? = nil,
        requiresAuth: Bool = false
    ) -> URLRequest {
        
        var urlComponents = URLComponents(string: baseURL + path)!
        if let queryItems = queryItems {
            urlComponents.queryItems = queryItems
        }
        
        var request = URLRequest(url: urlComponents.url!)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        
        // Add authentication header if required and available
        if requiresAuth, let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        if let body = body {
            request.httpBody = body
        }
        
        return request
    }
    
    private func performRequest<T: Codable>(
        _ request: URLRequest,
        responseType: T.Type
    ) async -> Result<T, APIError> {
        
        do {
            let (data, response) = try await session.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                switch httpResponse.statusCode {
                case 200...299:
                    do {
                        let decodedResponse = try decoder.decode(responseType, from: data)
                        return .success(decodedResponse)
                    } catch {
                        print("Decoding error: \(error)")
                        return .failure(.decodingError)
                    }
                    
                case 401:
                    await MainActor.run {
                        self.authToken = nil
                        self.isAuthenticated = false
                        self.removeAuthToken()
                    }
                    return .failure(.unauthorized)
                    
                case 403:
                    return .failure(.forbidden)
                    
                case 404:
                    return .failure(.notFound)
                    
                default:
                    // Try to parse error message from response
                    if let errorData = try? decoder.decode(ErrorResponse.self, from: data) {
                        return .failure(.serverError(errorData.error))
                    }
                    return .failure(.serverError("HTTP \(httpResponse.statusCode)"))
                }
            }
            
            return .failure(.invalidResponse)
            
        } catch {
            print("Network error: \(error)")
            return .failure(.networkError)
        }
    }
    
    private func validateAuthToken() async {
        guard let token = authToken else {
            isAuthenticated = false
            return
        }
        
        // Test token validity with a simple request
        let request = createRequest(
            path: "/api/v1/arbitrage/opportunities",
            method: "GET",
            requiresAuth: true
        )
        
        do {
            let (_, response) = try await session.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                await MainActor.run {
                    self.isAuthenticated = httpResponse.statusCode != 401
                    if !self.isAuthenticated {
                        self.authToken = nil
                        self.removeAuthToken()
                    }
                }
            }
        } catch {
            await MainActor.run {
                self.isAuthenticated = false
            }
        }
    }
    
    // MARK: - Token Storage
    private func saveAuthToken(_ token: String) {
        UserDefaults.standard.set(token, forKey: "auth_token")
    }
    
    private func loadAuthToken() {
        authToken = UserDefaults.standard.string(forKey: "auth_token")
        isAuthenticated = authToken != nil
    }
    
    private func removeAuthToken() {
        UserDefaults.standard.removeObject(forKey: "auth_token")
    }
}

// MARK: - API Response Models
struct APIResponseWrapper<T: Codable>: Codable {
    let success: Bool
    let data: T?
    let message: String?
}

struct AuthResponse: Codable {
    let accessToken: String
    let tokenType: String
    let expiresIn: Int
    
    private enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
    }
}

struct UserLogin: Codable {
    let userID: Int
    let username: String?
    
    private enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case username
    }
    
    init(userID: Int, username: String? = nil) {
        self.userID = userID
        self.username = username
    }
}

struct UserRegister: Codable {
    let userID: Int
    let username: String?
    
    private enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case username
    }
    
    init(userID: Int, username: String? = nil) {
        self.userID = userID
        self.username = username
    }
}

struct ErrorResponse: Codable {
    let success: Bool
    let error: String
    let detail: String?
}

// MARK: - Extended Response Models
struct SymbolPricesData: Codable {
    let symbol: String
    let prices: [SymbolPriceData]
    let statistics: PriceStatistics
    let metadata: ResponseMetadata
}

struct PriceStatistics: Codable {
    let minPrice: Double
    let maxPrice: Double
    let avgPrice: Double
    let spreadPercent: Double
    let exchangeCount: Int
    let totalVolume: Double
    
    private enum CodingKeys: String, CodingKey {
        case minPrice = "min_price"
        case maxPrice = "max_price"
        case avgPrice = "avg_price"
        case spreadPercent = "spread_percent"
        case exchangeCount = "exchange_count"
        case totalVolume = "total_volume"
    }
}

struct MarketOverviewData: Codable {
    let marketStats: MarketStatistics
    let systemStats: SystemStats
    let metadata: ResponseMetadata
    
    private enum CodingKeys: String, CodingKey {
        case marketStats = "market_stats"
        case systemStats = "system_stats"
        case metadata
    }
}

struct SystemStats: Codable {
    let cachePerformance: CachePerformance
    let exchangeHealth: ExchangeHealth
    let performance: PerformanceData
    
    private enum CodingKeys: String, CodingKey {
        case cachePerformance = "cache_performance"
        case exchangeHealth = "exchange_health"
        case performance
    }
}

struct CachePerformance: Codable {
    let hitRate: Double
    let totalRequests: Int
    
    private enum CodingKeys: String, CodingKey {
        case hitRate = "hit_rate"
        case totalRequests = "total_requests"
    }
}

struct ExchangeHealth: Codable {
    let tier1: Int
    let tier2: Int
    let tier3: Int
}

struct FilterOptionsData: Codable {
    let riskLevels: [FilterOption]
    let exchanges: [ExchangeOption]
    let categories: [FilterOption]
    let volumeRanges: [VolumeOption]
    let profitRanges: [ProfitOption]
    
    private enum CodingKeys: String, CodingKey {
        case riskLevels = "risk_levels"
        case exchanges
        case categories
        case volumeRanges = "volume_ranges"
        case profitRanges = "profit_ranges"
    }
}

struct FilterOption: Codable {
    let value: String
    let label: String
    let description: String
}

struct ExchangeOption: Codable {
    let value: String
    let label: String
    let tier: String
}

struct VolumeOption: Codable {
    let value: Double
    let label: String
}

struct ProfitOption: Codable {
    let value: Double
    let label: String
}