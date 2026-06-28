## 1. 系统与运行时工具

| 优先级 | Tool 名称                 | 类型     | 作用                            | 输入             | 输出               | 风险     |
| :-- | :---------------------- | :----- | :---------------------------- | :------------- | :--------------- | :----- |
| MVP | `tool_registry_lookup`  | system | 根据任务检索候选工具                    | task, tags     | tool specs       | low    |
| MVP | `skill_registry_lookup` | system | 检索候选 skills                   | task, domain   | skill specs      | low    |
| MVP | `memory_retrieve`       | memory | 从 memory 中检索相关历史              | query, filters | memory snippets  | low    |
| MVP | `memory_write`          | memory | 写入 evidence/action/reflection | record         | status           | low    |
| MVP | `state_snapshot`        | system | 保存当前任务状态快照                    | state          | snapshot\_id     | low    |
<!-- | P1  | `cost_tracker`          | system | 统计工具调用成本/次数                   | tool calls     | cost report      | low    |
| P1  | `permission_check`      | system | 检查高风险动作是否允许                   | action         | allow/deny       | medium |
| P1  | `task_progress_report`  | system | 输出当前任务进度                      | state          | progress summary | low    | -->

---

## 2. 搜索与网页信息工具

| 优先级 | Tool 名称                  | 类型      | 作用           | 输入                 | 输出                       | 风险     |
| :-- | :----------------------- | :------ | :----------- | :----------------- | :----------------------- | :----- |
| MVP | `web_search`             | search  | 通用联网搜索       | query, recency     | results, urls            | low    |
| MVP | `web_fetch`              | search  | 读取指定网页内容     | url                | markdown/text            | low    |
| MVP | `news_search`            | search  | 搜索新闻与近期事件    | query, date\_range | news results             | low    |
| P1  | `source_quality_check`   | search  | 判断来源质量       | url/source         | quality score            | low    |
| P1  | `citation_extractor`     | search  | 从文本中提取引用 URL | text               | citations                | low    |
| P1  | `search_deduper`         | search  | 去重相似搜索结果     | results            | deduped results          | low    |
<!-- | P2  | `browser_search`         | browser | 使用浏览器执行搜索    | query              | rendered results         | medium |
| P2  | `browser_fetch_rendered` | browser | 读取动态网页       | url                | rendered text/screenshot | medium | -->
- 供应商包括
    - tavily， https://docs.tavily.com/llms.
    - Jina API， https://r.jina.ai/docs，https://s.jina.ai/docs
    - TOKEN 都已经在.env中
---

## 3. 文档读取工具

| 优先级 | Tool 名称                      | 类型       | 作用                       | 输入             | 输出             | 风险     |
| :-- | :--------------------------- | :------- | :----------------------- | :------------- | :------------- | :----- |
| MVP | `list_files`                | document | 读取本地文件的列表 | file\_path     | content        | low    |
| MVP | `file_reader`                | document | 读取本地文本/markdown/json/csv | file\_path     | content        | low    |
| MVP | `pdf_reader`                 | document | 读取 PDF 内容                | file\_path/url | pages/text     | low    |
| MVP | `docx_reader`                | document | 读取 Word 文档               | file\_path     | text/structure | low    |
| MVP | `table_extractor`            | document | 从文档中提取表格                 | file/pdf/page  | tables         | low    |
| P1  | `document_chunker`           | document | 文档切片                     | text, strategy | chunks         | low    |
| P1  | `document_outline_extractor` | document | 提取文档结构                   | text           | outline        | low    |
| P1  | `reference_parser`           | document | 解析参考文献                   | text           | references     | low    |
<!-- | P2  | `ocr_reader`                 | document | OCR 图片/PDF 扫描件           | image/pdf      | text           | medium |
| P2  | `cross_document_compare`     | document | 多文档对比                    | docs           | diff/summary   | low    | -->

---

## 4. 金融研究工具

| 优先级 | Tool 名称                     | 类型      | 作用          | 输入                  | 输出           | 风险         |
| :-- | :-------------------------- | :------ | :---------- | :------------------ | :----------- | :--------- |
| MVP | `stock_quote`               | finance | 获取股价/市值/成交等 | ticker              | quote data   | low        |
| MVP | `company_profile`           | finance | 公司基本信息      | ticker              | profile      | low        |
| MVP | `financial_statement_fetch` | finance | 拉取财务报表      | ticker, period      | financials   | low        |
| MVP | `earnings_calendar`         | finance | 获取财报日期      | ticker              | dates        | low        |
| P1  | `analyst_estimates_fetch`   | finance | 获取分析师预期     | ticker              | estimates    | low/medium |
| P1  | `transcript_search`         | finance | 搜索财报电话会     | ticker, quarter     | transcript   | low        |
| P1  | `filings_search`            | finance | 搜 SEC/公告文件  | ticker, form\_type  | filings      | low        |
| P1  | `filing_reader`             | finance | 读取公告文件      | filing\_url/id      | text         | low        |
| P1  | `peer_comps_fetch`          | finance | 获取可比公司      | ticker/sector       | peers        | low        |
| P1  | `valuation_multiples_fetch` | finance | 获取估值倍数      | tickers             | multiples    | low        |
| P2  | `estimate_revision_tracker` | finance | 跟踪预期修正      | ticker, date\_range | revisions    | medium     |
<!-- | P2  | `segment_revenue_parser`    | finance | 解析分部收入      | filing/transcript   | segment data | medium     | -->
| P2  | `guidance_extractor`        | finance | 提取管理层指引     | transcript/filing   | guidance     | medium     |
| P2  | `sentiment_signal_fetch`    | finance | 新闻/社媒/研报情绪  | ticker              | sentiment    | medium     |

- 可以参考目前已经有的
<!-- ---

## 5. 学术与论文复刻工具

| 优先级 | Tool 名称                      | 类型            | 作用                     | 输入                | 输出                    | 风险     |
| :-- | :--------------------------- | :------------ | :--------------------- | :---------------- | :-------------------- | :----- |
| MVP | `paper_pdf_reader`           | academic      | 读取论文 PDF               | file/url          | structured paper text | low    |
| MVP | `paper_section_extractor`    | academic      | 抽取摘要/方法/实验等            | paper text        | sections              | low    |
| MVP | `paper_claim_extractor`      | academic      | 提取核心贡献和实验 claim        | paper text        | claims                | low    |
| MVP | `github_search`              | academic/code | 搜相关代码仓库                | paper title/query | repos                 | low    |
| P1  | `citation_graph_search`      | academic      | 查引用/被引                 | paper title/doi   | citation graph        | low    |
| P1  | `dataset_finder`             | academic      | 查找论文使用数据集              | paper text/query  | dataset links         | medium |
| P1  | `benchmark_info_fetch`       | academic      | 获取 benchmark 信息        | benchmark name    | metrics/setup         | medium |
| P1  | `prompt_extractor`           | academic      | 从论文 appendix 提取 prompt | paper text        | prompts               | low    |
| P2  | `equation_extractor`         | academic      | 提取公式和变量解释              | paper text        | equations             | medium |
| P2  | `method_to_pseudocode`       | academic      | 方法转伪代码                 | method section    | pseudocode            | medium |
| P2  | `experiment_table_extractor` | academic      | 提取实验表格                 | paper pages       | tables/metrics        | medium | -->

---

## 6. 代码与实验工具

| 优先级 | Tool 名称                | 类型        | 作用          | 输入                  | 输出                      | 风险     |
| :-- | :--------------------- | :-------- | :---------- | :------------------ | :---------------------- | :----- |
| MVP | `python_exec_sandbox`  | code      | 安全执行 Python | code/files          | stdout/stderr/artifacts | medium |
| MVP | `shell_exec_sandbox`   | code      | 执行 shell 命令 | command             | stdout/stderr/status    | high   |
| MVP | `code_reader`          | code      | 读取代码文件      | path                | code                    | low    |
| MVP | `code_search`          | code      | 搜索项目代码      | query/path          | matches                 | low    |
| MVP | `code_writer`          | code      | 写入/修改代码     | path, content/diff  | status                  | high   |
<!-- | P1  | `unit_test_runner`     | code      | 运行单元测试      | test command        | results                 | medium |
| P1  | `lint_runner`          | code      | 静态检查        | path                | lint report             | low    |
| P1  | `log_analyzer`         | code      | 分析运行日志      | logs                | issues/summary          | low    |
| P1  | `dependency_inspector` | code      | 检查依赖        | env/files           | dependencies            | low    |
| P1  | `repo_clone`           | code      | 克隆仓库        | repo\_url           | local path              | medium |
| P2  | `notebook_runner`      | code      | 执行 notebook | ipynb               | outputs                 | medium |
| P2  | `experiment_runner`    | code      | 运行实验配置      | config              | metrics/logs            | high   |
| P2  | `metric_evaluator`     | code/eval | 计算指标        | predictions, labels | metric score            | low    |
| P2  | `diff_generator`       | code      | 生成代码 diff   | old,new             | diff                    | low    |
| P2  | `patch_apply`          | code      | 应用补丁        | diff                | status                  | high   | -->

- 沙盒环境供应商
    - E2B: https://github.com/e2b-dev/e2b

---

## 7. 数据分析工具

| 优先级 | Tool 名称                         | 类型   | 作用        | 输入               | 输出                   | 风险     |
| :-- | :------------------------------ | :--- | :-------- | :--------------- | :------------------- | :----- |
| MVP | `csv_reader`                    | data | 读取 CSV    | path             | dataframe summary    | low    |
| MVP | `dataframe_profiler`            | data | 数据概览      | dataframe/path   | schema/stats/missing | low    |
| MVP | `calculator`                    | data | 数值计算      | expression/data  | result               | low    |
| P1  | `chart_generator`               | data | 生成图表      | data, chart spec | image/file           | low    |
| P1  | `statistical_test`              | data | 统计检验      | data, test\_type | pvalue/result        | low    |
| P1  | `regression_runner`             | data | 回归分析      | data, formula    | results              | low    |
| P1  | `time_series_analyzer`          | data | 时间序列分析    | data             | trend/seasonality    | low    |
| P2  | `data_cleaner`                  | data | 缺失/异常处理   | data, strategy   | cleaned data         | medium |
| P2  | `feature_engineering_assistant` | data | 特征生成建议/执行 | data, goal       | features             | medium |
---

<!-- ## 8. 浏览器与 Computer Use 工具

| 优先级 | Tool 名称                | 类型      | 作用       | 输入              | 输出         | 风险        |
| :-- | :--------------------- | :------ | :------- | :-------------- | :--------- | :-------- |
| P2  | `browser_open`         | browser | 打开网页     | url             | page state | medium    |
| P2  | `browser_click`        | browser | 点击页面元素   | selector/coords | page state | high      |
| P2  | `browser_type`         | browser | 输入文本     | selector, text  | page state | high      |
| P2  | `browser_screenshot`   | browser | 截图       | page            | image      | low       |
| P2  | `browser_extract_text` | browser | 提取当前页面文字 | page            | text       | low       |
| P2  | `browser_download`     | browser | 下载文件     | selector/url    | file path  | medium    |
| P3  | `browser_form_fill`    | browser | 自动填表     | form spec       | status     | high      |
| P3  | `browser_login_flow`   | browser | 登录流程     | credentials ref | session    | very high |

这类工具要做权限控制，默认不要开放高风险动作。 -->

---

## 9. 产物生成工具

| 优先级 | Tool 名称              | 类型       | 作用         | 输入                | 输出               | 风险  |
| :-- | :------------------- | :------- | :--------- | :---------------- | :--------------- | :-- |
| MVP | `markdown_writer`    | artifact | 写 markdown | content,path      | file             | low |
| MVP | `json_writer`        | artifact | 写结构化结果     | json,path         | file             | low |

<!-- | P1  | `docx_writer`        | artifact | 生成 Word    | sections/style    | docx path        | low |
| P1  | `pptx_writer`        | artifact | 生成 PPT     | slides/style      | pptx path        | low |
| P1  | `chart_embedder`     | artifact | 把图表嵌入报告    | chart paths       | document         | low |
| P2  | `pdf_exporter`       | artifact | 导出 PDF     | source file       | pdf path         | low |
| P2  | `report_formatter`   | artifact | 套格式模板      | report, template  | formatted report | low |
| P2  | `citation_formatter` | artifact | 格式化引用      | references, style | bibliography     | low | -->

---

## 10. 验证、合规与质量工具

| 优先级 | Tool 名称                      | 类型      | 作用             | 输入                   | 输出                | 风险     |
| :-- | :--------------------------- | :------ | :------------- | :------------------- | :---------------- | :----- |
| MVP | `citation_checker`           | quality | 检查引用是否存在/可访问   | urls                 | status report     | low    |
| MVP | `claim_evidence_checker`     | quality | 检查 claim 是否有证据 | claims,evidence      | support report    | low    |
| MVP | `coverage_evaluator`         | quality | 评估维度覆盖度        | artifact, criteria   | coverage report   | low    |
| MVP | `conflict_detector`          | quality | 检测证据冲突         | evidence/artifact    | conflicts         | low    |
<!-- | P1  | `compliance_filter`          | quality | 过滤不合规来源/内容     | evidence             | filtered evidence | low    |
| P1  | `hallucination_checker`      | quality | 检查未支持表述        | artifact,evidence    | flags             | medium |
| P1  | `recency_checker`            | quality | 检查时效性          | citations/dates      | recency report    | low    |
| P1  | `source_reliability_scorer`  | quality | 评估来源可靠性        | source               | score             | low    |
| P2  | `assumption_stress_tester`   | quality | 压力测试核心假设       | assumptions,evidence | stress report     | medium |
| P2  | `reproducibility_checker`    | quality | 检查实验可复现性       | code, logs, metrics  | report            | medium |
| P2  | `result_consistency_checker` | quality | 检查报告内部一致性      | artifact             | issues            | low    | -->

---

## 11. 人机协作工具

| 优先级 | Tool 名称                 | 类型    | 作用        | 输入             | 输出              | 风险     |
| :-- | :---------------------- | :---- | :-------- | :------------- | :-------------- | :----- |
| MVP | `ask_human`             | human | 请求用户补充信息  | question       | answer          | low    |
| MVP | `human_approval`        | human | 高风险动作确认   | action summary | approve/deny    | low    |
| P1  | `human_review_payload`  | human | 给用户展示当前状态 | state summary  | review payload  | low    |
| P1  | `human_select_branch`   | human | 用户选择探索分支  | branch options | selected branch | low    |
| P2  | `human_edit_artifact`   | human | 用户修改中间产物  | artifact       | edited artifact | medium |
| P2  | `human_set_constraints` | human | 用户更新约束    | constraints    | updated config  |        |
