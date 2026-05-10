# Frontend

这是 Cloud Storage Player 当前主线前端。

## 技术栈

- React
- TypeScript
- Vite
- React Router
- TanStack Query

## 启动

```bash
npm install
npm run dev
```

如果后端地址不是默认值，可创建 `.env.local`：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 构建

```bash
npm run build
```

## 说明

- `third/` 只做参考，不参与这里的运行时。
- 当前前端不兼容原 Vue 版本，已直接切换到新的 React 实现。
- 更详细的约束见 `frontend/AGENTS.md`。
