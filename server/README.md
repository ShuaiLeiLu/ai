# Cyber Invest Server

FastAPI backend foundation for Cyber Invest.

## Jin10 MCP Market Data

The backend exposes Jin10 MCP data through deployable project APIs under `/api/v1/market-data`.

Required deployment environment:

```env
JIN10_MCP_SERVER_URL=https://mcp.jin10.com/mcp
JIN10_MCP_BEARER_TOKEN=your-bearer-token
JIN10_MCP_PROTOCOL_VERSION=2025-11-25
JIN10_MCP_TIMEOUT=20
```

Available API paths:

- `GET /api/v1/market-data/quote-codes`
- `GET /api/v1/market-data/quotes/{code}`
- `GET /api/v1/market-data/klines/{code}?time=&count=`
- `GET /api/v1/market-data/flash?cursor=`
- `GET /api/v1/market-data/flash/search?keyword=`
- `GET /api/v1/market-data/news?cursor=`
- `GET /api/v1/market-data/news/search?keyword=&cursor=`
- `GET /api/v1/market-data/news/{news_id}`
- `GET /api/v1/market-data/calendar`
