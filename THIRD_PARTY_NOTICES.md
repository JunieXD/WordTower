# 第三方代码与素材

项目根目录的 MIT 许可证适用于 WordTower 原创代码。第三方组件、词典与美术素材继续遵循各自的许可，不因本仓库采用 MIT 而改变。

## ECDICT / StarDict

- 来源：[skywind3000/ECDICT](https://github.com/skywind3000/ECDICT)
- 用途：`backend/app/scripts/stardict.py` 词典读写工具，以及开发者单独下载的词典数据。
- 脚本中保留了原作者 skywind 的署名；上游当前发布的许可文本保存在 [docs/licenses/ECDICT-MIT.txt](docs/licenses/ECDICT-MIT.txt)。词典数据不随本仓库分发。

## 前端美术素材

角色动画位于 `frontend/src/assets/character/`，场景背景位于 `frontend/src/assets/background/`。这些为项目使用的第三方开源素材，沿用各自原始许可，不纳入项目 MIT 的重新授权范围。仓库目前未记录其完整来源链接和许可文本；单独提取、再分发素材前应核对原发布页。

## 软件依赖

前后端依赖分别记录在 `frontend/package-lock.json` 和 `backend/uv.lock` 中。各依赖包附带的版权与许可证保持有效。
