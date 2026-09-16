# 参与 WordTower

欢迎提交问题报告和 Pull Request。功能改动请说明使用场景；界面问题请附复现步骤、浏览器版本和截图，避免包含个人信息或密钥。

## 本地开发

按 [README](README.md#本地启动) 启动前后端。数据库结构变动通过 Alembic 迁移提交；大模型相关单元测试使用 mock，不需要消耗真实额度。

提交前运行：

```bash
cd frontend
npm ci
npm run type-check
npm run test:unit -- --run
npm run build-only
```

```bash
cd backend
uv sync --frozen
ECNU_API_KEY=test-key-not-used-by-unit-tests uv run --frozen python -m unittest discover -s app/test -p 'test_*.py'
```

请保持改动聚焦，并补充能验证行为的测试。修改重试或限流时，尤其注意重复提交、网络断开和用户输入保留。

## Pull Request

说明解决的问题、最终行为和验证方式。PR 会自动运行前后端检查；合并到 `main` 后，GitHub Actions 构建镜像并部署。

项目原创代码采用 [MIT](LICENSE) 许可。引入第三方代码或素材时，请保留原作者署名、许可文本和来源链接，更新 [第三方说明](THIRD_PARTY_NOTICES.md)。
