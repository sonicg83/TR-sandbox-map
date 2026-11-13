# TRMap 初版实施计划

> **给执行代理：** 按任务执行；使用 `superpowers:executing-plans` 或用户明确选择的子代理工作流。复选框用于记录进度。

**目标：** 在本机运行可导入服务器地图数据、查看 TravianZ 风格地图并保存个人标注的单人 Web 沙盘。

**架构：** FastAPI 提供仅监听本机的服务及静态页面；SQLite 保存服务器档案、不可变导入批次、地块观察和沙盘方案。浏览器使用原生 JavaScript 与 Canvas 绘制视口内地块，通过 JSON API 查询和编辑；服务器观察与个人标注分表保存。

**技术栈：** Python ≥ 3.14（现有项目要求）、FastAPI、Uvicorn、SQLite、pytest、原生 HTML/CSS/JavaScript、Canvas；使用 `uv` 管理 Python 环境。依赖版本在实施时锁定并验证 Python 3.14 兼容性。

**设计：** [初版设计](../specs/2026-11-13-initial-sandbox-design.md)。

## 全局约束

- 用户提供的 `map.sql` 只解析数据，绝不执行 SQL；不调用游戏服务器。
- 未知、空置和失败不能混同；观察时间未知不能用导入时间替代；冲突保留并显式展示。
- 原始数据、凭据和生成文件不提交；测试使用人工构造样例。`other_projects/` 只读参考。
- 地图视觉参照 TravianZ；代码和素材使用前核对具体许可和归属，不能确定时使用自制占位并明确显示限制。
- 服务器档案必须包含世界/赛季和坐标范围；边界环绕只在经验证的服务器上手动启用。
- 不覆盖现有工作区及暂存文件。涉及提交时只提交本任务文件，不自动提交用户暂存文件。

## 重点核验

1. SQL 中含转义引号、逗号、空值及非 ASCII 字符时不能错列，也不能执行语句（任务 2）。
2. 扫描 JSON 同坐标跨类别、重复项或超界坐标必须报错，整批不落库（任务 3）。
3. 观察时间缺失、来源冲突或后导入旧数据不能静默覆盖真实信息（任务 4）。
4. 未确认完整性的快照缺少村庄时不能判为空地或消失（任务 4）。
5. 拖动、缩放和边界处点选必须对应同一坐标；未知素材不能误作已知地貌（任务 6）。

## 文件结构

- `pyproject.toml`, `uv.lock`, `main.py`：依赖、启动服务。
- `trmap/app.py`, `trmap/db.py`, `trmap/models.py`：API、SQLite 初始化和共享类型。
- `trmap/imports/sql.py`, `trmap/imports/scan.py`, `trmap/imports/service.py`：纯解析、验证和事务导入。
- `trmap/observations.py`：按字段解析观察、冲突与缺失。
- `trmap/sandbox.py`：服务器档案和沙盘方案持久化。
- `trmap/static/index.html`, `app.js`, `map.js`, `styles.css`：本地页面、交互、渲染及样式。
- `tests/`：人工样例、解析、持久化、合并、API 及地图坐标测试。
- `docs/asset-provenance.md`：素材和视觉映射的来源、许可及未知项。

## 任务 1：本地服务与档案存储

**文件：** 修改 `pyproject.toml`, `main.py`, `README.md`；创建 `trmap/app.py`, `trmap/db.py`, `trmap/models.py`, `trmap/sandbox.py`, `tests/test_worlds.py`。

**接口：** `create_app(database_path: Path) -> FastAPI`；`create_world(connection, name, season, min_x, max_x, min_y, max_y, wrap) -> int`。`POST /api/worlds` 新建，`GET /api/worlds` 列出；重复名称与赛季组合、空名称、反向范围返回 422。

- [ ] 编写 API 测试：创建档案后重新打开数据库仍可读取；非法范围和重复档案不创建记录。
- [ ] 运行 `uv run pytest tests/test_worlds.py -v`，确认实现前测试失败。
- [ ] 配置依赖、SQLite 初始化及上述接口；默认数据库放在被忽略的 `data/` 下；本地服务器默认监听 `127.0.0.1`。
- [ ] 重跑测试，确认全部通过；README 写明本地启动方式和数据路径。

## 任务 2：安全解析每日地图数据

**文件：** 创建 `trmap/imports/sql.py`, `tests/test_sql_import.py`, `tests/fixtures/map.sql`。

**接口：** `parse_map_sql(text: str) -> list[dict]`；返回坐标、村庄 ID、名称、玩家 ID/名称、联盟 ID/名称、人口和部落代码，保留 NULL 为 `None`；只接受已验证的 `INSERT INTO x_world VALUES (...)` 记录格式。

- [ ] 用人工样例测试带逗号、转义引号、中文、NULL 的记录，以及不完整值列表和混入 `DROP TABLE` 的输入；非法输入抛出明确错误，不返回部分结果。
- [ ] 运行 `uv run pytest tests/test_sql_import.py -v`，确认测试先失败。
- [ ] 实现不执行 SQL 的词法解析；对当前样例格式和未支持格式分别成功或拒绝。不要将缺失人口转成零。
- [ ] 重跑测试；以只读方式对本地参考样本验证记录数、首尾坐标和特殊字符解析，不提交真实数据。

## 任务 3：扫描导入与批次事务

**文件：** 创建 `trmap/imports/scan.py`, `trmap/imports/service.py`, `tests/test_scan_import.py`, `tests/test_import_api.py`；修改 `trmap/db.py`, `trmap/app.py`。

**接口：** `parse_scan_json(text: str) -> list[dict]` 解析 `village/oasis/landscape`；`POST /api/worlds/{id}/imports` 接受 `kind`（`map_sql` 或 `scan_json`）、文件、可选用户确认的观察时间和覆盖范围，以及 `complete_snapshot`（默认 false）；返回批次 ID、成功、跳过、冲突和错误数量。未知时间和范围均可为空。

- [ ] 测试三种类别、资源值、未知时间、相同输入重复导入、跨类别同坐标、同类别重复、无效类型和超界；错误批次不能留下部分观察。重复文件默认拒绝并返回既有批次 ID，不产生重复观察。
- [ ] 运行 `uv run pytest tests/test_scan_import.py tests/test_import_api.py -v`，确认先失败。
- [ ] 实现两种导入的共享事务、文件摘要、服务器归属、观察时间与导入时间分离；SQL 和 JSON 都只能写入明确选中的档案。若导入文件本身无法验证服务器身份，要求用户确认归属并标记为用户声明。
- [ ] 重跑测试；在界面任务前提供 `GET /api/worlds/{id}/imports` 供批次时间和状态展示。

## 任务 4：观察合并与查询

**文件：** 创建 `trmap/observations.py`, `tests/test_observations.py`；修改 `trmap/app.py`, `trmap/db.py`。

**接口：** `resolve_tile(connection, world_id: int, x: int, y: int) -> dict`；`GET /api/worlds/{id}/tiles?min_x=&max_x=&min_y=&max_y=` 返回视口内地块及字段级来源、时间、状态和冲突，限制请求范围。

- [ ] 测试按坐标关联两来源；同类、时间可信的较新观察获选；较旧文件后导入不覆盖；无时间或不可比冲突返回候选值与 `conflict`；JSON 未出现坐标返回 `unknown`；未确认完整快照缺失村庄不生成消失事件。
- [ ] 运行 `uv run pytest tests/test_observations.py -v`，确认先失败。
- [ ] 实现观察解析：不同领域字段分别取自身来源，不能相互覆盖；可信时间相同时值冲突也返回 `conflict`；批次不可变。完整快照缺席仅记录未出现，不推断原因。
- [ ] 测试不同服务器档案的相同坐标严格隔离；重跑全部观察测试与 API 测试。

## 任务 5：本地沙盘方案

**文件：** 修改 `trmap/sandbox.py`, `trmap/app.py`, `trmap/db.py`；创建 `tests/test_sandbox.py`。

**接口：** `POST/GET /api/worlds/{id}/plans`；`GET/PUT /api/plans/{id}`。方案包含名称和 `items` 数组：标记为 `{id,type:"marker",x,y,label,color,note}`，路线为 `{id,type:"arrow",from:{x,y},to:{x,y},label,color,note}`。

- [ ] 测试创建、编辑和删除标记及路线、跨档案隔离、非法坐标拒绝、重启后恢复；导入新批次不改变方案。
- [ ] 运行 `uv run pytest tests/test_sandbox.py -v`，确认先失败。
- [ ] 在独立方案表中实现上述接口，单次 PUT 原子保存整个方案；校验类型、坐标和文本大小。
- [ ] 重跑测试，确认通过。

## 任务 6：TravianZ 风格地图与交互

**文件：** 创建 `trmap/static/index.html`, `app.js`, `map.js`, `styles.css`, `tests/test_map_geometry.mjs`, `docs/asset-provenance.md`；修改 `trmap/app.py`。

**接口：** `worldToScreen(x, y, view)` 与 `screenToWorld(px, py, view)` 为互逆映射；前端通过任务 1、3、4、5 的 API 管理档案、导入、视口与方案。地图只请求当前视口，并在视图改变时刷新。

- [ ] 编写 Node 内置测试：中心坐标、四象限、负坐标、拖动及多级缩放后的映射往返一致；边界和环绕只按档案配置处理。
- [ ] 运行 `node --test tests/test_map_geometry.mjs`，确认实现前失败。
- [ ] 调研 TravianZ 地块排列和图片依赖并填写素材来源、许可和映射表；在许可与映射明确前使用自制图形占位。实现菱形地图、视口裁剪、未知状态和地块点击；说明尚不能还原的地块。
- [ ] 实现档案创建、导入表单和结果、地块详情、坐标跳转、玩家/联盟/村庄搜索、联盟及类型筛选、方案标记和箭头编辑。数据时间未知及冲突必须可见；用户输入按文本处理。
- [ ] 重跑几何测试；以本地服务使用人工样例实际验证拖动、缩放、搜索、筛选、导入和重启恢复。记录参考视觉对照及未验证的映射。

## 任务 7：端到端验收与文档

**文件：** 修改 `README.md`, `docs/asset-provenance.md`；创建 `tests/test_end_to_end.py`。

- [ ] 编写覆盖创建档案、导入两份样例、查询关联地块、保存方案、再次导入和重启恢复的端到端测试；验证 SQL 中危险语句不会执行。
- [ ] 运行 `uv run pytest -v` 和 `node --test tests/test_map_geometry.mjs`，全部通过；实际浏览器复核首版用户流程。
- [ ] 更新 README 的安装、启动、文件导入、时间与覆盖范围填写、备份、限制与许可说明；确认只监听本机，不包含凭据或真实样本。
- [ ] 执行 `git diff --check`、检查仓库状态和目标文件，记录测试结果与未完成的视觉映射；保留用户现有暂存内容。
