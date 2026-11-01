# 校园留言前端

Vue 3 + Vue Router + Vite，使用原生表单和少量共享组件，直接调用现有 FastAPI 接口。

## 运行

要求 Node.js 22.12+ 或 24 LTS。先在项目根目录启动原有后端：

```powershell
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

在另一个终端运行：

```powershell
cd frontend
npm ci
npm run dev
```

访问 http://127.0.0.1:5173 。`/api` 默认代理到 `http://127.0.0.1:8000`，后端无需新增 CORS 配置。需要更换后端地址时，将本目录 `.env.example` 复制为 `.env.local`，修改 `VITE_API_PROXY_TARGET` 并重启 Vite。

## 分层

```text
src/
  api/          HTTP 请求、响应解包、业务接口
  assets/       公共样式
  components/   分页、留言卡片、标注与审核表单
  composables/  列表加载和分页状态
  layouts/      页面布局、导航和退出入口
  router/       路由、登录检查和管理员页面限制
  stores/       当前用户与登录状态
  utils/        凭证存取、时间和中文标签
  views/        登录、注册、留言、分类、审核及统计页面
  App.vue       根组件
  main.js       应用入口
```

页面调用 `api` 层，不直接拼接 URL 或解析响应。`api/request.js` 统一处理后端 `{code, message, data}`、HTTP 错误、超时和登录失效，包括 HTTP 200 中的业务错误。权限最终由后端校验。

## 当前功能

- 登录、注册、退出；凭证保存在 `sessionStorage`，刷新后通过 `/auth/me` 校验恢复，关闭标签页后清除。
- 发布留言；我的留言和公共留言切换、关键词查询及清空、分页、刷新、删除确认。查询或切换范围时回到第一页，翻页保留关键词。发布成功后清空正文及搜索条件并返回我的留言，失败保留输入。
- 管理员在“分类标注”筛选分类并提交人工标注；页面只显示当前有效分类“普通 / 垃圾”，无分类时显示“未分类”。人工标签优先，后端保留原始预测；页面不展示概率、模型名及贡献词。
- 预测正常且达到自动通过阈值的留言发布后直接公开；发布提示区分已自动通过与等待人工审核。管理员在“留言审核”处理剩余待审核留言、通过或填写原因后驳回，列表可查看真实模型概率与贡献词。
- 管理员在“留言统计”查看全部未删除留言总数、正常/垃圾/未分类分布和待审核/通过/驳回数量，支持刷新及失败重试。分类按人工标签优先，其次取成功的模型预测；分类和审核各项合计分别等于总数。
- 列表失败重试、分页越界修正、北京时间显示；正文按纯文本展示。

后端提供标注及审核历史接口，前端暂未提供历史页面。统计页调用管理员接口 `GET /api/v1/statistics`，每次进入页面或点击刷新时重新读取。

## 测试和构建

```powershell
npm test
npm run build
npm run preview
```

`npm test` 使用 Node 内置测试运行器，验证请求契约、登录失效、检索分页、统计加载、分类组件实际渲染及时间显示。分类测试覆盖人工纠正后原始预测、贡献方向与数量、零概率和无特征反馈；旧解释中的 `weight` 不被当作新贡献值。`npm run build` 生成 `dist/`；`preview` 仅供本地检查，也会代理 `/api`。生产部署可参考 `nginx.conf.example`，由 Nginx 托管 `dist/` 并代理 FastAPI。路由使用 hash 模式，刷新不会要求后端提供页面路由。

浏览器联调可使用隔离的内存数据库：在项目根目录运行 `uv run python frontend/tests/serve_backend.py`，然后在前端终端运行：

```powershell
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8001'
npm run dev
```

隔离测试账号为 `student`、`admin`，密码均为 `test-password-123`。仅测试服务提供这些账号；停止服务后测试数据消失，不连接本地 MySQL。正常开发请清除该环境变量或另开终端，使代理恢复到 8000。
