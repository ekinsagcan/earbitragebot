# 🚀 CryptoArbitrage Pro - iOS App + Backend API

**Telegram botundan geliştirilmiş modern mobil arbitraj platformu**

## 📱 Proje Özeti

Bu proje, mevcut Telegram arbitraj botunun temel mantığını alarak modern iOS deneyimine uygun şekilde geliştirilmiş kapsamlı bir mobil arbitraj platformudur. Bot.py'deki core logic korunarak, mobile-first yaklaşımla yeniden tasarlanmıştır.

## 🏗️ Mimari

```
arbitrage-ios-project/
├── backend/                 # FastAPI Backend
│   ├── app/
│   │   ├── core/           # Enhanced arbitrage engine
│   │   ├── api/            # REST API endpoints
│   │   ├── database/       # Models & schemas
│   │   └── utils/          # Security & utilities
│   └── requirements.txt
├── ios/                    # SwiftUI iOS App
│   └── ArbitrageBot/
│       ├── App/            # Main app structure
│       ├── Models/         # Data models
│       ├── ViewModels/     # MVVM business logic
│       ├── Views/          # SwiftUI components
│       └── Services/       # API communication
└── README.md
```

## ✨ Ana Özellikler

### 🔍 Gelişmiş Arbitraj Keşfi
- **30+ Borsa Entegrasyonu**: Binance, KuCoin, Gate.io, OKX, Bybit ve daha fazlası
- **Risk Skoru Sistemi**: AI-inspired risk analizi ve güvenlik puanlaması
- **Exchange Tier Classification**: Tier 1/2/3 güvenlik sınıflandırması
- **Real-time Veriler**: Canlı fiyat güncellemeleri ve cache sistemi

### 📊 Smart Analytics
- **Opportunity Scoring**: 0-100 arası fırsat puanlaması
- **Volume Analysis**: 24h volume filtreleme ve analizi
- **Risk Factors**: Detaylı risk faktör analizi
- **Performance Tracking**: API response times ve success rates

### 🎯 Modern Mobil Deneyim
- **SwiftUI Native**: iOS 15+ için optimize edilmiş arayüz
- **Pull-to-Refresh**: Gesture-based data refresh
- **Visual Risk Coding**: Renk bazlı risk gösterimi
- **Interactive Filters**: Tap-to-filter quick actions
- **Haptic Feedback**: Native iOS feedback sistemi

### 💎 Premium Features
- **App Store IAP**: Native subscription management
- **Unlimited Opportunities**: Free tier limiti yok
- **Advanced Analytics**: Detaylı market analizi
- **Real-time Alerts**: Push notification sistemi
- **Portfolio Tracking**: Trade history ve performance

## 🚀 Bot'tan iOS'a Geliştirmeler

### Orijinal Bot Mantığı ✅
```python
# Bot.py'den korunan core features:
- ArbitrageBot.calculate_arbitrage()
- Exchange API entegrasyonları
- Risk filtreleme sistemi
- Premium/Free user ayrımı
- PostgreSQL database
- Volume ve profit thresholds
```

### Mobile Enhancement 🎯
```swift
// iOS'a eklenen modern features:
- MVVM + Clean Architecture
- Real-time SwiftUI updates
- Gesture-based interactions
- Visual risk scoring
- App Store subscriptions
- Native iOS notifications
- Smooth animations
- Dark/Light mode support
```

## 📋 API Endpoints

### Authentication
```
POST /api/v1/auth/login          # Kullanıcı girişi
POST /api/v1/auth/register       # Yeni kullanıcı kaydı
POST /api/v1/auth/refresh        # Token yenileme
```

### Arbitrage
```
GET  /api/v1/arbitrage/opportunities         # Fırsatları getir
GET  /api/v1/arbitrage/opportunities/premium-preview  # Premium önizleme
GET  /api/v1/arbitrage/symbol/{symbol}       # Coin fiyat analizi
GET  /api/v1/arbitrage/markets/overview      # Market genel bakış
GET  /api/v1/arbitrage/filters/options       # Filter seçenekleri
```

## 🛠️ Teknoloji Stack

### Backend
- **Framework**: FastAPI 0.104.1
- **Database**: PostgreSQL (AsyncPG)
- **Authentication**: JWT (python-jose)
- **API Client**: aiohttp (async)
- **Caching**: In-memory + Redis ready
- **Documentation**: Auto-generated Swagger UI

### iOS
- **Language**: Swift 5.0+
- **UI Framework**: SwiftUI + UIKit hybrid
- **Architecture**: MVVM + Clean Architecture
- **Networking**: URLSession + Combine
- **Storage**: UserDefaults + Core Data ready
- **Subscriptions**: StoreKit 2 ready
- **Minimum iOS**: 15.0

## 🔧 Kurulum ve Çalıştırma

### Backend Setup
```bash
cd backend/
pip install -r requirements.txt

# Environment variables
export DATABASE_URL="postgresql://user:pass@localhost/arbitrage_db"
export SECRET_KEY="your-secret-key"
export DEBUG="True"

# Run server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### iOS Setup
1. Xcode 15+ ile `ios/ArbitrageBot.xcodeproj` açın
2. `APIService.swift`'te backend URL'ini güncelleyin
3. iOS Simulator veya device'da çalıştırın

## 📊 Database Schema

```sql
-- Users table (from original bot)
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    subscription_end DATE,
    is_premium BOOLEAN DEFAULT FALSE,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- App Store Subscriptions (new)
CREATE TABLE app_store_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    transaction_id TEXT UNIQUE NOT NULL,
    product_id TEXT NOT NULL,
    purchase_date TIMESTAMP NOT NULL,
    expires_date TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Arbitrage Data (analytics)
CREATE TABLE arbitrage_data (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    exchange1 TEXT NOT NULL,
    exchange2 TEXT NOT NULL,
    price1 REAL NOT NULL,
    price2 REAL NOT NULL,
    profit_percent REAL NOT NULL,
    volume_24h REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🎯 Önemli Farklar: Bot vs iOS

| Özellik | Telegram Bot | iOS App |
|---------|-------------|---------|
| **Interface** | Text komutları | SwiftUI tap gestures |
| **Data Display** | Simple text lists | Rich visual cards |
| **Refresh** | Manuel /check komutu | Pull-to-refresh + auto |
| **Filtering** | Text parameters | Interactive filter chips |
| **Risk Analysis** | Text warning | Visual color coding |
| **Subscription** | Gumroad lisans | App Store IAP |
| **Notifications** | Telegram messages | iOS push notifications |
| **User Experience** | Command-based | Gesture-based |

## 📈 Risk Scoring Algorithm

```swift
// Enhanced risk scoring (0-10)
func calculateRiskScore(opportunity: ArbitrageOpportunity) -> (RiskLevel, Int) {
    var score = 0
    
    // Profit risk (higher profit = higher risk)
    if profit > 10% { score += 3 }
    else if profit > 5% { score += 2 }
    else if profit > 2% { score += 1 }
    
    // Volume risk (lower volume = higher risk)
    if volume < 50k { score += 3 }
    else if volume < 100k { score += 2 }
    
    // Exchange tier risk
    if both_tier_3 { score += 3 }
    else if one_tier_3 { score += 1 }
    
    // Symbol trust
    if untrusted_symbol { score += 2 }
    else if premium_coin { score -= 1 }
    
    return (getRiskLevel(score), score)
}
```

## 🚀 Deployment

### Backend Deployment (Railway/Heroku)
```bash
# Dockerfile included
docker build -t arbitrage-api .
docker run -p 8000:8000 arbitrage-api
```

### iOS App Store
1. Code signing setup
2. App Store Connect configuration
3. TestFlight beta testing
4. App Store review submission

## 💰 Monetization

### Subscription Plans
- **Free**: 10 opportunities, basic features
- **Premium Monthly ($9.99)**: Unlimited opportunities, real-time alerts
- **Premium Yearly ($99.99)**: All features + priority support

### Revenue Model
- App Store IAP (30% Apple fee)
- Freemium conversion targeting
- Premium features unlocking

## 📱 Screenshots & Demo

<img src="assets/discover-screen.png" width="300">
<img src="assets/opportunity-detail.png" width="300">
<img src="assets/premium-upgrade.png" width="300">

## 🔮 Future Enhancements

### Phase 2 Features
- [ ] Real-time WebSocket updates
- [ ] Portfolio tracking with P&L
- [ ] Advanced charting (TradingView integration)
- [ ] Social features (community insights)
- [ ] AI-powered predictions

### Phase 3 Features
- [ ] Apple Watch companion app
- [ ] Siri Shortcuts integration
- [ ] Widget support (iOS 14+)
- [ ] Apple Intelligence integration
- [ ] Advanced automation (trading signals)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

- **Email**: support@cryptoarbitragepro.com
- **Discord**: [Join our community](https://discord.gg/cryptoarbitrage)
- **Documentation**: [Full API docs](https://api.cryptoarbitragepro.com/docs)

---

**⚡ Built with ❤️ - From Telegram Bot to Modern iOS App**

> Bu proje, mevcut Telegram botunun başarılı mantığını koruyarak modern mobil deneyim standartlarına taşıyan kapsamlı bir dönüşüm örneğidir. Bot.py'deki proven logic + iOS native experience = CryptoArbitrage Pro 🚀