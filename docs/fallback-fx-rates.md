# Bundled FX fallback

LaunchGuard includes a small, dated FX fallback table for offline development and incident testing. Fallback values are not live market data and trigger a visible compliance warning.

| Pair | Rate | As of |
|---|---:|---|
| EUR/USD | 1.0800 | 2026-01-02 |
| USD/EUR | 0.9259 | 2026-01-02 |
| GBP/USD | 1.2700 | 2026-01-02 |
| USD/GBP | 0.7874 | 2026-01-02 |
| CNY/USD | 0.1390 | 2026-01-02 |
| USD/CNY | 7.1942 | 2026-01-02 |

Live production approval should refresh fallback-derived pricing before delivery.
