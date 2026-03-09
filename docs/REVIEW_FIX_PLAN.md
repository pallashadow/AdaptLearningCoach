# 修复计划（2026-03-09）

## 目标

基于本次项目扫描结果，修复以下问题并降低回归风险：

1. Follow-up 题错误消耗 `max_round`
2. CORS 配置安全与兼容性问题
3. `/dialogs/answer` 并发下的丢更新风险
4. `kwargs={}` 可变默认参数隐患
5. README 与默认端口不一致

---

## 范围与原则

- 优先修复会影响业务正确性和安全性的项（P1/P2）。
- 保持 API 兼容，避免破坏现有前端调用方式。
- 每个改动配套最小可验证用例（单测或接口级验证步骤）。
- 所有配置改动尽量通过环境变量控制，避免硬编码。

---

## 详细修复方案

### 1) Follow-up 不应占用主轮次（P1）

#### 现状问题

- `ref_node` 在主问题与 follow-up 场景都执行 `current_round + 1`。
- 导致弱答触发补问时，主轮次被提前耗尽，`max_round` 语义失真。

#### 修改方案

- 文件：`lib/agentic/nodes/ref_node.py`
- 将轮次递增规则改为：
  - `is_followup == False`：`current_round += 1`
  - `is_followup == True`：`current_round` 保持不变
- 对“缺失 `user_answer` / 缺失 `current_concept`”早退分支同样应用上述规则，避免补问异常时误增轮次。
- 保持 `sub_qa_history` 继续记录 follow-up 过程，不影响诊断细节追踪。

#### 验收标准

- `max_round=3` 时，即使每轮都触发 follow-up，仍然要回答 3 个主问题后才结束。
- `DialogSnapshot.state.current_round` 与“已完成主问题数量”一致。

---

### 2) CORS 安全与浏览器兼容修复（P1）

#### 现状问题

- 当前配置：`allow_origins=["*"]` + `allow_credentials=True`。
- 该组合不符合浏览器 CORS 规范（携带凭证不能使用 `*`），且存在过宽暴露风险。

#### 修改方案

- 文件：`main.py`
- 新增环境变量：
  - `CORS_ALLOW_ORIGINS`（逗号分隔）
  - `CORS_ALLOW_CREDENTIALS`（`true/false`）
- 默认策略建议：
  - 本地开发默认：`allow_origins=["http://127.0.0.1:5173","http://localhost:5173"]`
  - `allow_credentials=False`
- 若显式配置了 origin 白名单，再按配置启用。
- 当 `allow_credentials=True` 且 origin 含 `*` 时，启动日志输出警告并自动降级为 `False`（或拒绝启动，二选一，建议降级）。

#### 验收标准

- 前端本地可正常调用。
- 浏览器控制台不再出现 CORS 凭证与通配符冲突错误。
- 非白名单源站跨域请求被拒绝。

---

### 3) `/dialogs/answer` 并发写入一致性（P2）

#### 现状问题

- 现在是 `get -> 修改 state -> set`，并发提交时存在后写覆盖先写。
- `qa_history/current_round/feedback` 可能被丢失。

#### 修改方案

- 文件：`lib/api/dialog_store.py`、`main.py`
- 新增存储接口（抽象能力）：
  - `update(dialog_id, updater)`：在存储层原子地读取并更新。
- 实现细节：  - `FirestoreDialogStore`：使用事务（transaction）读写同一文档，冲突自动重试。
- `submit_answer` 改为走 `store.update(...)`，避免应用层分离式读写。
- 如果事务失败，返回 409 或 503（可重试语义），并在响应中给出简短提示。

#### 验收标准

- 人工并发（同一 `dialog_id` 快速双击提交）不会丢失 `qa_history` 项。
- 压测下 `current_round` 单调正确，不出现回退。

---

### 4) 可变默认参数清理（P3）

#### 现状问题

- `call_llm` / `call_llm_stream` 使用 `kwargs={}`。
- 虽当前未触发 bug，但后续维护风险高。

#### 修改方案

- 文件：`lib/llm/litellm_api.py`
- 签名改为 `kwargs: dict | None = None`。
- 函数内 `kwargs = kwargs or {}`。
- 保持调用方无感知变更。

#### 验收标准

- 现有调用路径行为不变。
- 静态检查不再出现 mutable default 参数警告。

---

### 5) 端口文档对齐（P3）

#### 现状问题

- README 示例默认端口为 `8000`，`main.py` 默认端口为 `8001`。

#### 修改方案

- 文件：`README.md`
- 将默认 URL 与示例命令统一为 `8001`，并补充说明可通过 `PORT` 覆盖。

#### 验收标准

- 新用户按 README 直接运行可以成功联通健康检查。

---

## 建议执行顺序

1. 修复 Follow-up 轮次逻辑（正确性最高优先）
2. 修复 CORS 配置（安全与可用性）
3. 上线存储原子更新接口（一致性）
4. 清理可变默认参数（工程质量）
5. 同步 README 端口（文档一致性）

---

## 测试与验证清单

### 单元测试（建议新增）

- `tests/test_ref_node_rounding.py`
  - 覆盖主问题、follow-up、异常早退三种场景的 `current_round` 行为。
- `tests/test_dialog_store_atomic_update.py`
  - 并发更新下 `qa_history` 和 `current_round` 一致性。

### 接口级验证

1. 启动服务并创建 `max_round=3` 对话，构造低分答案触发 follow-up。
2. 确认 follow-up 往返后 `current_round` 不增长，主问题后才增长。
3. 使用两个并发请求同时提交同一 `dialog_id`，确认历史不丢。
4. 从白名单与非白名单 origin 分别发起请求，确认 CORS 行为符合预期。

---

## 风险与回滚

- 风险点：
  - Firestore 事务实现细节可能与当前异步客户端 API 存在差异。
  - 轮次逻辑变更会影响前端“进度显示”的体感，需同步说明“主问题计数”语义。
- 回滚策略：
  - 通过 feature flag（例如 `STRICT_MAIN_ROUND_ONLY`）控制新旧轮次逻辑切换。
  - 原子更新接口保留旧 `get/set` 路径，在事务异常时可临时降级。

---

## 交付物

- 代码改动：
  - `lib/agentic/nodes/ref_node.py`
  - `main.py`
  - `lib/api/dialog_store.py`
  - `lib/llm/litellm_api.py`
  - `README.md`
- 测试改动：
  - 新增针对轮次与并发一致性的测试文件
- 文档改动：
  - 本文档 `docs/REVIEW_FIX_PLAN.md`


