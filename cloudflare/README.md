# yuki23.me 部署

Cloudflare Worker `shanghai-divergence` 提供 `/shanghai-divergence/` 前端和动态 `api/market` 接口。接口实时读取当前已发布行情清单，股票快照按批次缓存；筛选计算在浏览器进行。Python / AKShare 采集仍在 GitHub Actions 后台运行，网站不需要用户电脑在线。

GitHub Actions 在工作日北京时间 18:17、20:17、22:17 尝试更新。交易日历决定是否需要采集；数据已最新则跳过。GitHub 可能延迟执行，因此这些是计划时间，不是完成时间保证。失败不覆盖旧批次。打开的网页每分钟检查新批次并用当前筛选条件重新计算。

构建：`BUILD_TARGET=cloudflare node build.mjs`。部署：`wrangler deploy --config cloudflare/wrangler.json`。

域名路由（控制台配置，仅连接本 Worker）：

- `yuki23.me/shanghai-divergence`
- `yuki23.me/shanghai-divergence/*`

根域名的既有个人网站继续由原 Worker 提供。不要把整个 `yuki23.me/*` 路由绑定到本 Worker。

路由验证：`node scripts/test_cloudflare.mjs`；计算一致性：`python scripts/parity_fixtures.py` 后运行 `node scripts/test_static.mjs`。
