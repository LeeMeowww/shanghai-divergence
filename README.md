# 沪市背离观察台

在本机浏览器中筛选与上证综指反向的沪市 A 股。React + TypeScript + ECharts / FastAPI / SQLite。

## GitHub Pages 在线版

在线版以静态网页运行，浏览器下载压缩行情快照并完成筛选、详情曲线和 CSV 导出，无需本机 Python 服务。当前快照约 6.7 MB，首次打开需要下载，后续筛选复用内存数据。

- 默认分支 `main` 推送后自动构建并发布。
- GitHub Actions 在工作日北京时间 **18:17** 尝试更新；中国市场休市且快照已最新时跳过采集。
- GitHub 的定时任务可能延迟；界面始终显示实际行情截止日。
- 网页“刷新已发布行情”只读取已部署的数据。需要手动采集时，在仓库 Actions → Publish market dashboard → Run workflow 勾选 refresh。
- 更新失败时工作流失败，不替换现有网站；源码变更发布前先恢复线上更新的数据，防止回退到仓库初始快照。
- 公开仓库连续 60 天没有活动时，GitHub 可能停用定时工作流；可在 Actions 页面重新启用。[GitHub 定时任务说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- 本机版仍由 `start.cmd` 启动，使用 Python 计算；在线版与其通过 288 项计算一致性测试。

Pages 使用 GitHub Actions 作为发布来源（Settings → Pages → Build and deployment → Source → GitHub Actions）。仓库含一份已验证的初始公开行情快照，不含本机 SQLite、账户凭据或运行日志。

在线版构建：

```powershell
python scripts/export_pages.py  # 仅首次从本机 SQLite 导出快照时需要
$env:BUILD_TARGET='pages'
node build.mjs
```

产物为 `dist-pages/`，使用相对资源路径，支持 `/<repository>/` 项目地址。

## 启动

双击 **start.cmd**，浏览器会打开 **http://127.0.0.1:8765**。保留启动窗口；关闭窗口后服务停止。当前电脑已安装项目专用依赖，并附带编译好的网页，无需 Node 即可使用。

首次运行或数据落后时自动采集。服务运行期间，每个交易日北京时间 18:00 检查更新；电脑关闭期间下次启动补齐。按钮可手动重试。首次全市场下载可能需要数分钟至数十分钟，取决于接口响应。

## 使用

1. 等待数据批次就绪，或点击“更新行情”。
2. 选择截止日期（留空表示最新批次）、2—60 个交易日、判定模式和方向。
3. 点击“开始筛选”。切换条件后必须重新筛选，防止把旧结果当作新条件结果。
4. 点击股票名称查看累计涨跌曲线与逐日核对表。搜索、排序和 CSV 导出使用同一个数据批次。
5. 有新批次时点击“使用新批次筛选”；当前结果不会被静默替换。

## 判定口径

- 范围：当前沪市主板与科创板 A 股清单（600/601/603/605/688），包括 ST 股票；不含 B 股、基金、债券、CDR。
- N 个交易日取 N+1 个收盘价，第一天是计算基准日。
- 默认严格模式：每天指数上涨、股票下跌。选择反方向则每天指数下跌、股票上涨；“两个方向”取这两类的并集。指数交替涨跌时不会满足严格模式。
- 累计模式：窗口累计涨跌方向相反；中间可同向。
- 涨跌幅由后复权收盘价计算，表格收盘价为未复权价格；曲线均从基准日 0% 起算。
- 最小涨跌幅阈值作用于**整个区间涨跌幅的绝对值**，两个模式相同。
- 差值单位为百分点，默认按绝对差降序排列。零涨跌不算反向。
- 停牌、无成交、缺失和异常价格排除；不前向填充。指数缺失则拒绝计算。
- 非交易日回退到前一交易日；已有交易日尚未采集时要求更新，不能静默回退。
- 第一版覆盖约最近一年；历史筛选使用当前股票清单，不是完整退市样本回测。背离结果不预测未来收益。

## 数据与失败处理

- AKShare 提供交易日历、上交所股票清单、东方财富指数和个股行情。
- 东方财富接口不稳定时，批次开始前切换到腾讯证券。股票备用适配器使用 AKShare 同一公开接口，一次获取整个窗口的原始价和后复权价，并严格过滤日期；指数可独立使用腾讯备用源。界面记录实际来源。
- 四个采集线程，最多三次退避重试。连续八只失败会停止继续请求，未采集股票计入缺失。
- 每个更新重新取得约一年序列，避免不同复权版本拼接。完整下载后原子保存批次；失败不删除旧批次。
- 股票部分失败时发布可用样本，明确标记数据不完整。所有股票失败或指数不完整则不发布新批次。
- 原始异常保存在 SQLite 的 jobs / errors 中；页面显示简明状态。
- 数据保存在 `data/market.sqlite3`。应用仅绑定 `127.0.0.1`，不上传数据库，不使用付费 API。

## 在另一台电脑安装

安装 Python 3.12（64 位），然后在项目目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

当前 `.deps` 是本机 Python 3.12 的便携依赖；其他 Python 版本请在新复制的源码目录中使用虚拟环境安装，不复制 `.deps`。

## 开发与验证

前端依赖通过 `pnpm-lock.yaml` 锁定。安装 Node 后：

```powershell
pnpm install --frozen-lockfile
node node_modules/typescript/bin/tsc --noEmit
node build.mjs
```

编译入口使用进程内 TypeScript 转换，避免某些 Windows 环境阻止 esbuild 子进程。静态产物位于 `dist/`。

后端测试：

```powershell
# 普通虚拟环境
.\.venv\Scripts\python.exe -m pytest -q
# 本机便携依赖
$env:PYTHONPATH="$PWD\.deps;$PWD"
python -m pytest -q
```

测试数据仅在独立临时 SQLite 数据库使用，生产页面不内置模拟股票。

## 本机接口

| 接口 | 用途 |
|---|---|
| `GET /api/status` | 当前批次、数据覆盖和采集进度 |
| `POST /api/refresh` | 非阻塞启动更新，返回任务编号 |
| `GET /api/screen` | 筛选；参数包括 end、window、mode、direction、board、stock_min、index_min、search、sort、descending、batch_id |
| `GET /api/stocks/{code}/comparison` | 必须指定 batch_id、end；返回图表与每日数值 |
| `GET /api/export` | 必须指定 batch_id；其余筛选参数同 screen；UTF-8 BOM CSV |

`mode`：strict / cumulative；`direction`：down / up / both；`board`：all / main / star。数字涨跌幅参数和返回值均以百分数计，例如 1 代表 1%。

## 常见问题

- **更新失败**：免费公开接口可能断连；查看具体阶段后稍后重试。已有批次仍可筛选。
- **结果为零**：严格模式要求每一天满足指定方向，正常情况下可能没有命中。切换累计模式查看区间背离。
- **数据不完整**：打开排除明细，不要把有效样本数误当全市场数量。
- **打不开网页**：确认启动窗口未关闭，端口 8765 未被其他程序占用。
- **已启动过一次**：直接打开网址，不要同时运行多个采集进程。

参考：[AKShare 股票接口](https://akshare.akfamily.xyz/data/stock/stock.html)、[AKShare 腾讯接口实现](https://github.com/akfamily/akshare/blob/main/akshare/stock_feature/stock_hist_tx.py)。
