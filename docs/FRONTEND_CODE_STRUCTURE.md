# 前端代码结构说明（新手友好）

## 这份文档解决什么问题
如果你刚接触这个项目，不知道“代码从哪里进、请求在哪发、页面状态怎么更新”，这份文档就是给你快速上手用的。

## 前端整体技术栈
- React + TypeScript：页面组件与类型约束
- Vite：本地开发与构建
- TanStack Query：请求状态管理（加载/失败/成功）
- react-hook-form + zod：表单状态与输入校验

## 目录结构（重点）

```text
frontend/
├─ src/
│  ├─ main.tsx                  # React 入口，挂载 App 和 QueryClient
│  ├─ App.tsx                   # 主页面（核心交互都在这里）
│  ├─ style.css                 # 页面样式
│  ├─ types.ts                  # 前后端交互的数据类型定义
│  ├─ api/
│  │  └─ dialogApi.ts           # 所有后端请求封装（start/answer/snapshot）
│  └─ utils/
│     ├─ choice.ts              # 工具函数（例如解析 A/B/C/D 选项）
│     └─ choice.test.ts         # 对应单元测试
├─ e2e/
│  └─ app.spec.ts               # Playwright 端到端冒烟测试
├─ index.html                   # Vite HTML 模板（挂载点 #app）
├─ vite.config.ts               # Vite + Vitest 配置
├─ tsconfig.json                # TypeScript 配置
├─ eslint.config.js             # ESLint 配置
└─ package.json                 # 脚本与依赖
```

## 运行时数据流（你最需要理解的）

### 1. 启动入口
1. `main.tsx` 创建 `QueryClient`
2. 用 `<QueryClientProvider>` 包裹 `<App />`
3. 挂载到 `#app`

### 2. 开始诊断（Start Dialog）
1. 用户在 `App.tsx` 填写表单
2. `react-hook-form` 收集输入，`zod` 校验
3. 调用 `startDialog()`（在 `api/dialogApi.ts`）发 `POST /dialogs/start`
4. 成功后保存 `dialogId`、`currentQuestion` 等状态

### 3. 提交回答（Submit Answer）
1. 用户输入答案（或单选 A/B/C/D）
2. 调用 `submitAnswer()` 发 `POST /dialogs/answer`
3. 返回 feedback/score/next question
4. 页面更新结果区与当前状态

### 4. 状态快照（Current State）
1. `useQuery` 调用 `fetchDialogSnapshot()`
2. 请求 `GET /dialogs/{dialog_id}`
3. `state` 显示在右侧 `pre` 区域

## 每个文件该怎么看

### `src/main.tsx`
- 只做“启动与Provider注入”
- 不写业务逻辑

### `src/App.tsx`
- 页面主逻辑中心
- 包含：
  - 表单定义与校验 schema
  - `useMutation`（start / answer）
  - `useQuery`（snapshot）
  - UI 渲染（输入区、结果区、状态区）

### `src/api/dialogApi.ts`
- 只做 HTTP 请求，不做 UI 逻辑
- 好处：后续替换接口或加鉴权改动集中

### `src/types.ts`
- 前后端 JSON 类型契约
- 改接口字段时要同步改这里

### `src/utils/choice.ts`
- 纯函数工具
- 适合写单测，避免把复杂解析写进组件里

## 新手最常见修改场景

### 场景 A：新增一个输入字段
1. 在 `App.tsx` 的 `startSchema` / `StartFormValues` 加字段
2. 在表单 UI 加输入控件
3. 在 `startDialog` payload 里带上该字段
4. 如果后端返回结构变了，同步 `types.ts`

### 场景 B：修改后端地址默认值
- 改 `App.tsx` 中 `backendUrl` 的默认值

### 场景 C：新增一个后端接口
1. 在 `types.ts` 增加请求/响应类型
2. 在 `api/dialogApi.ts` 新增封装函数
3. 在 `App.tsx` 用 `useMutation` 或 `useQuery` 接入

## 代码分层约定（建议遵守）
- `App.tsx`：页面编排 + 状态拼装
- `api/`：网络请求
- `utils/`：纯函数工具
- `types.ts`：类型契约
- 不要在组件中散落 `fetch` 字符串 URL，统一放 `api/`

## 调试入口（定位问题最快）
1. 请求问题：先看 `api/dialogApi.ts`
2. 表单/校验问题：看 `App.tsx` 里的 zod schema
3. 选项渲染问题：看 `utils/choice.ts`
4. 样式问题：看 `style.css`

## 给新同学的上手顺序（30分钟）
1. 先看 `src/main.tsx`（2分钟）
2. 再看 `src/App.tsx`（15分钟）
3. 看 `src/api/dialogApi.ts` + `src/types.ts`（8分钟）
4. 最后看 `utils/choice.ts` 和测试（5分钟）

## 相关文档
- 前端本地开发指南：`docs/FRONTEND_LOCAL_DEV.md`
- 前端现代化计划：`docs/FRONTEND_MODERNIZATION_PLAN.md`
