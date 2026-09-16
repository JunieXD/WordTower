# WordTower Frontend

Vue 3 + TypeScript 的像素风单词闯塔界面，使用 Vite、Pinia、Tailwind CSS 和 GSAP。

```bash
npm ci
npm run dev
```

本地默认请求 `http://localhost:8000`；生产默认使用同源 `/api`。可通过 `VITE_API_BASE_URL` 覆盖。

```bash
npm run type-check
npm run test:unit -- --run
npm run build-only
```

`src/utils/reliableRequest.ts` 仅用于后端支持幂等重放的操作。它合并重复请求、保留重试标识，并通过 `RequestRecoveryNotice` 显示网络确认及限流倒计时。普通查询仍使用 `request.ts`。

详见 [项目主页](../README.md)、[频率保护](../docs/traffic-protection.md) 和 [贡献指南](../CONTRIBUTING.md)。
