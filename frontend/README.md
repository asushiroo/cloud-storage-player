# Frontend

这是 Cloud Storage Player 的独立前端目录。

## 技术栈

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- Axios

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

更详细的架构说明见：

- `frontend/AGENTS.md`
- `docs/frontend-vue-architecture.md`
