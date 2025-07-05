# 🚀 One-Click Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template)

## Or Manual Deploy:

1. **Fork bu repository**
2. **Railway.app** → "New Project" → "Deploy from GitHub"
3. **Select this repo** → `arbitrage-ios-project`
4. **Root directory**: `/backend`
5. **Environment Variables**:
   ```
   SECRET_KEY=your-super-secret-key-here
   DEBUG=False
   ```
6. **Deploy!** → 2 dakikada hazır ✅

## Test URLs:
```
https://your-app.railway.app/
https://your-app.railway.app/health
https://your-app.railway.app/docs
https://your-app.railway.app/api/v1/arbitrage/opportunities
```

## Mobile Test Commands:
```bash
# Health check
curl https://your-app.railway.app/health

# Get opportunities 
curl https://your-app.railway.app/api/v1/arbitrage/opportunities

# Login test
curl -X POST https://your-app.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123456}'
```