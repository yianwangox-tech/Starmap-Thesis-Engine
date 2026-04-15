# StarMap System

StarMap System 是一个面向学术研究场景的文献整理与分析网站，用来帮助用户从论文导入、相似度匹配、主题聚类、引用追踪到 BibTeX 导出，形成一套可视化的研究工作流。它特别适合论文选题、文献综述、研究脉络梳理，以及与 Zotero、Overleaf/LaTeX 配合使用的场景。

## 1. 系统定位

这个网站的核心目标，是把“找文献、筛文献、读文献、组织文献、导出引用”这些分散步骤集中到一个界面中完成。

用户可以：

- 创建多个研究项目，分别维护不同课题的文献池
- 导入本地 PDF，并自动抽取论文元数据与文本信息
- 根据目标论文题目、摘要、关键词和当前研究内容，计算相关论文的匹配度
- 通过可视化图谱观察文献分布、主题结构和引用关系
- 同步 Zotero 文库，减少手动搬运文献的工作量
- 生成标准 BibTeX，便于复制到 Overleaf 或其他 LaTeX 环境中使用

## 2. 主要功能

### 2.1 账号与项目管理

- 支持注册、登录与会话保持
- 每个账号可以创建多个项目
- 每个项目有独立的研究目标信息：
  - `Target Title`
  - `Target Abstract`
  - `Target Keywords`
  - `Target Current Content`

这些信息会作为后续论文匹配和推荐的参考基准。

### 2.2 PDF 导入与回滚

- 支持将本地 PDF 直接拖拽到工作区中
- 系统会解析 PDF 内容，并尝试提取论文标题、摘要、作者、年份等信息
- 导入完成后自动合并到当前项目的论文列表中
- 支持 `Rollback Latest Import`，用于撤销最近一次导入，避免误操作造成污染

### 2.3 相关论文匹配

系统会根据以下信号综合计算论文与当前项目的匹配度：

- 标题
- 摘要
- 当前研究内容
- 引用数量辅助权重（可选）

每篇论文都会显示一个相似度分数，帮助用户快速判断其与当前研究主题的相关程度。

### 2.4 论文详情面板

点击某篇论文后，可以查看更完整的信息，包括：

- 标题、作者、年份、引用数
- 摘要
- 匹配原因说明
- 各个信号对最终得分的贡献占比
- 阅读状态
- 个人笔记

在详情面板中，用户还可以直接执行以下操作：

- `Sync to Zotero`
- `Generate BibTeX`
- `Cited By`
- `References`
- `Read the Paper`
- `See Paper Info`

### 2.5 BibTeX 生成与引用键

系统支持自动生成 BibTeX，用于在 Overleaf 或 LaTeX 中直接使用。

功能特点：

- 自动生成 `citation_key`
- 采用 `AuthorYearTitle` 格式
- 会清洗特殊字符，避免 LaTeX 报错
- 多作者在 BibTeX 的 `author` 字段中使用 `and` 连接，符合 BibTeX 标准
- 同一账号跨项目时，会自动避免 `citation_key` 重名

例如：

```bibtex
@article{Zhang2024Large,
  author = {San Zhang and Li Wei},
  title = {The Large Language Models for Finance},
  year = {2024},
  journal = {Journal of Testing}
}
```

### 2.6 Zotero 集成

系统支持与 Zotero 协同工作，包括：

- 检测 Zotero API 是否可达
- 预览 Zotero 文库内容
- 将当前项目中的论文同步到 Zotero
- 从 Zotero 中拉取尚未匹配到当前项目的论文
- 同步 Zotero 附件 PDF 内容，用于提升文本相似度计算效果

如果用户已登录，系统可以通过后端读取 `.env` 中配置的 Zotero 凭证，而不要求用户每次在前端重新输入。

### 2.7 OpenAlex 学术数据支持

系统会结合 OpenAlex 获取和补全学术元数据，例如：

- 论文标题
- 作者
- 出版年份
- DOI
- 期刊或会议名称
- 引用数
- 被引论文列表
- 参考文献列表

这使得用户不仅能管理本地导入的 PDF，也能围绕论文进一步展开引用网络探索。

### 2.8 LLM 能力支持

系统可以接入外部大模型 API，用于增强检索与表达能力。当前设计支持通过后端代理访问大模型服务，并通过 `.env` 管理密钥。

LLM 相关用途包括：

- 语义增强搜索
- 主题聚类命名优化
- 某些元数据补全与文本处理任务

如果未启用相关开关，系统仍可使用本地规则与传统检索逻辑运行。

### 2.9 项目级设置开关

每个项目都可以单独配置以下开关：

- `Use LLM-assisted search`
  - 用于增强搜索和长列表筛选
- `Enable Background Precompute`
  - 在进入项目时预加载部分结果，换取后续更流畅的交互体验
- `Use LLM Theme Naming`
  - 用更清晰的自然语言为主题聚类命名
- `Use citation-count quality assist`
  - 在相似度排序中引入压缩后的引用数量权重

其中，`Background Precompute` 开启时，页面顶部会显示预加载提示，说明正在预计算哪些内容、预计耗时，以及可能带来的暂时卡顿。

### 2.10 文献可视化

系统提供多种图谱模式来帮助用户理解文献结构：

- `Orbital (Uni-directional)`
  - 以中心论文为核心，观察相关论文的分层分布
- `Network (Bi-directional)`
  - 展示论文之间更丰富的关系网络
- `Citation Graph`
  - 聚焦论文间的引用关系

此外，还支持：

- `Paper Status Overview`
- `Auto Cluster Themes`
- `Sync Zotero`
- `View Repository`

这些功能共同构成一个围绕研究问题展开的“文献地图”。

### 2.11 文献综述草稿辅助

系统支持基于核心论文和用户笔记生成 `Literature Review Draft`，帮助用户更快整理研究思路。这个功能更像是一个写作辅助入口，适合在完成初步筛选后，用于生成结构化综述草稿。

## 3. 典型使用流程

一个常见的使用流程如下：

1. 注册并登录账号
2. 创建一个新的研究项目
3. 填写目标题目、摘要、关键词与当前研究内容
4. 导入本地 PDF，或从 Zotero 拉取相关论文
5. 查看系统生成的相关论文列表与相似度分数
6. 在详情面板中阅读摘要、记录笔记、调整状态
7. 使用 `Cited By` 和 `References` 扩展文献池
8. 使用可视化图谱观察主题和引用结构
9. 为目标论文生成 BibTeX 并复制到 Overleaf / LaTeX

## 4. 技术与配置说明

### 4.1 前端

- 单页网页应用
- 主要界面定义在 `frontend/index.html`
- 使用 ECharts 实现图谱可视化
- 使用 PDF.js 处理 PDF 阅读与解析相关能力

### 4.2 后端

- 使用 FastAPI 提供 API
- 主要逻辑位于 `backend/main.py`
- 使用 SQLite 保存用户、项目、会话和设置

### 4.3 配置方式

系统支持通过项目根目录的 `.env` 管理运行配置，常见变量包括：

- `STARMAP_LLM_PROVIDER`
- `STARMAP_LLM_API_KEY`
- `STARMAP_OPENALEX_API_KEY`
- `STARMAP_CONTACT_EMAIL`
- `STARMAP_ZOTERO_USER_ID`
- `STARMAP_ZOTERO_API_KEY`
- `STARMAP_ZOTERO_COLLECTION_KEY`

这类配置主要由后端读取，避免浏览器直接接触敏感密钥。

## 5. 适用场景

这个网站尤其适合以下场景：

- 论文开题前的文献摸底
- 系统性整理某一研究主题的核心论文
- 跟踪一篇论文的引用与被引脉络
- 将 Zotero 文库与研究项目联动
- 为 Overleaf 写作准备 BibTeX
- 生成和维护文献综述草稿

## 6. 总结

StarMap System 本质上是一个“研究项目驱动”的文献管理与分析平台。它不是单纯的 PDF 阅读器，也不是单纯的文献库，而是把文献导入、相关性分析、引用追踪、可视化探索、Zotero 协同和 BibTeX 导出整合到同一个研究工作流中，帮助用户更系统地组织学术材料并推进写作。
