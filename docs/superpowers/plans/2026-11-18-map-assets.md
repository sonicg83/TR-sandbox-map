# 地图素材与缩放 Implementation Plan

**Goal:** 以原创据点和绿洲素材增强辨识，并提供三级缩放和地图工具栏。
**Architecture:** 纯函数处理人口、资源、缩放与查询分块；Canvas 根据观测状态与当前沙盘方案分层绘制。10% 使用稀疏观测渲染，不遍历整个世界。
**Tech Stack:** JavaScript Canvas、FastAPI、Node test、pytest。
**Spec:** docs/superpowers/specs/2026-11-18-map-assets-design.md

## Global Constraints

- 不复制 TravianZ 图片；保持观察、冲突、未知和沙盘数据分离。
- 保留现有用户变更；不提交真实数据或生成的中间结果。

## Review Focus

- 人口边界 99/100/399/400/999/1000、未知及冲突。
- 绿洲多资源优先顺序、全零和冲突。
- 视口超出 40000 地块时分块，并防止过期请求覆盖新视图。
- 固定缩放边界及指针锚定、归中。
- 无标记、有标记、重复标记的确定性颜色；低缩放下标记和冲突可辨。

### Task 1: 素材与来源

- [ ] 为四种据点和四种绿洲准备原创素材，统一风格并保留透明背景。
- [ ] 记录生成来源、视觉语义和地貌映射未验证；不用图片推断服务器实际建筑。

### Task 2: 绾定数据与视口

**Files:** `trmap/static/map.mjs`, `tests/test_map_geometry.mjs`, `trmap/static/app.mjs`。
- [ ] 为等级边界、绿洲选择、色点、缩放锚点和视口分块编写行为测试，先验证失败。
- [ ] 实现纯函数；将大视野拆成不超过 40000 地块的请求，过期请求不得覆盖新视图。
- [ ] 运行 `node --test tests/test_map_geometry.mjs` 并确认通过。

### Task 3: 分层绘制与控件

**Files:** `trmap/static/app.mjs`, `trmap/static/index.html`, `trmap/static/styles.css`, `tests/test_static.py`。
- [ ] 先测试三个按钮和资源文件可用性。
- [ ] 100%/50% 绘制素材，10% 稀疏绘制村庄色点；图片失败、冲突及未知状态采用明确回退。
- [ ] 工具栏按钮、滚轮分档、以指定锚点缩放、原点归中；保留已有点击、拖动、筛选与沙盘功能。
- [ ] 检查无障碍名称、边界按钮状态及高 DPI。

### Task 4: 验证和文档

- [ ] 更新 README 和素材来源记录；运行 `uv run pytest -q`、`node --test tests/test_map_geometry.mjs`。
- [ ] 本地用合成数据检查三个比例、较大视野、过滤、标记、冲突、归中和拖动；报告未验证项。
