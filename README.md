# Aussie EcoGuard — FIT3184 A2

澳大利亚动物目击管理、物种与数量检索、照片／文字寻宠、邮件订阅和 Lex 助手。
四人分工中 A 负责核心业务和 AI 检索；[10 月 13 日四人执行表](docs/product-and-implementation-plan.md#team-handoff-20261013)列出已有产物、待完成工作和验收交付。详细任务保留在同一文档。

## 最新交付与运行状态

**C 前端部署准备（2026-10-28）：** 已补齐非 root 静态前端容器及独立 Terraform 目录，17/17 项实际本地容器检查、5 项原生 mock 测试通过。真实云端保存计划已生成并下载，同一份计划通过修正后的审阅与 11 个拒绝危险变更的反例检查：仅新增 3 项，零更新、零删除。私有推理 IAM 和原有状态哈希复核未变。镜像尚未发布，HTTPS 前端尚未部署；今天额度页面未加载成功，A$0 额外自付限制下暂停新的付费部署。详见[实际保存计划审核](docs/c-frontend-saved-plan-review-20261028.md)。

**C/B 联调准备（2026-10-27）：** Jerry 已将 C 的 PR #1 合并到团队主分支；尚未看到 B 后续的新版本。当前前端与上游一致，39/39 项本地测试及正式构建通过。只读实查确认个人环境 API、公开注册仍暂停，CORS 仅允许本机地址，JWT 用户池／客户端配置一致；尚无已确认部署的 HTTPS 前端。本轮没有恢复服务或运行媒体测试。GCP 额度页显示 10 月 28 日到期、0 天内到期，下一次在线运行前需重新复核额度与恢复范围。详见[联调准备与连接配置](docs/c-b-preflight-20261027.md)。

**当前云厂商选择：** C 的个人部署路线是 AWS + GCP Cloud Run。作业 Spec 第2页允许自行选择厂商并要求至少两家云，Rubric 第7页明确列举 AWS + GCP；Oracle 不是必选厂商。Oracle 模板和未部署主机的记录属于较早路线。厂商选择符合要求，不等于实际跨云处理或整份作业已经验收通过。

**C 部分个人环境最新记录（2026-10-25）：** AWS 当前60项资源，应用已恢复暂停；GCP私有推理环境13项资源。第3次单图尝试仅一次应用保存计划94c，exit0并通过激活验证；随后源对象不存在检查的 HeadObject 返回254，完整意图账本无业务种子或图片PUT。八项控制在 T0+262.019秒读回暂停，满足原600秒目标。后续10轮、547.989秒观察中，两轮S3桶读取超时，因此连续安全观察和fixture drain仍未通过；最后fallback再次读回全部8项暂停和边界有效。真实跨云图片／Lambda WIF媒体成功次数仍为 **0**。
详见[三次实际尝试、恢复证据与剩余事项](docs/c-runtime-attempt-and-recovery-20261025.md)和[精选状态记录](evidence/c-runtime-attempts-status-20261025.json)。[默认停用源码快照](tools/c-runtime-controller/README.md)保留HeadObject严格JSON错误解析及安全诊断，并更新V15的正常计划证据链；8项fixture与9项启动注入测试属于本地验证，ARMFalse、60个实际pin待绑定，没有新的云端媒体尝试。官方固定2.38.1 formatter已本地重现旧正则的格式兼容问题，但原生失败未保存stderr，不能断言这就是本次唯一根因。随后同一refresh-only保存计划完成一次零资源动作的状态同步，当前serial95；新normal保存计划a927通过0创建/8更新/52不变审核，尚未apply。[checkpoint52源码与证据审核](docs/c-runtime-checkpoint52-review-20261025.md)保留V15的ARMFalse、60个待填pin及未绑定当前证明；pool2三组只读实测不代表540秒连续验收。不得写回旧serial94/85状态。GCP13的41项只读元数据检查通过，没有HTTP推理请求。个人报告尚未定稿，当前不宣称完成百分比。下面的核心交接测试记录来自10月8日。

**核心实现已完成本轮交接；云端运行和访问已暂停，数据与配置保留。**
AWS 的定时任务、队列处理、七个 Lambda 和 API 已停用；媒体桶也拒绝包括旧签名链接在内的数据读写。
`infra/aws/deployment.auto.tfvars` 持久保存 `runtime_enabled=false`，普通 plan 不会默默恢复运行。
恢复服务需要新的授权，并继续遵守 **额外自费 A$0**。

[核心交付与停用记录](docs/core-completion-20261008.md)区分代码检查、真实本机模型和云验收。
本轮唯一自动测试 **259 项全部通过**：后端 130、前端 39、推理与鉴权 72、Oracle 门禁 8、停用检查器 10。
真实本机核心链路 **55/55**；120 秒视频按 0/10/…/110 秒取 12 帧，推理 **203.985 秒**，临时素材和模型进程均已清理。
这些本机检查使用真实缓存模型、内存存储和明确的空 Rekognition fixture，不代表真实双云链路通过。

模型 v3 的独立小样本验证：8 张未见图片的猫狗物种及特征 **8/8**；照片与照片加描述候选检索各 **7/8**；
独立改写文字 **4/4**，无关文字 **0/4 误报**。一个 bulldog 检索未命中仍保留在报告分母。
这是品种／物种语义候选基线，**不是宠物个体身份准确率或所有入侵物种精度验收**。
[模型报告](services/inference/evidence/model-quality-v3-20261008.json)保留原失败和后续验证的边界。

完整成品仍需完成实际双云自动处理、正式应用 Lex 和独立同宠／干扰宠物数据验收。
当前个人路线使用已部署的 AWS ingest 与 GCP 私有推理服务，实际处理结果仍须以运行证据确认。Oracle 未部署不是这条路线的厂商合规缺口；不能把本轮核心交付描述为全作业完成。
此前[续验收失败记录](docs/acceptance-continuation-20261008.md)与[前轮云检查](docs/environment-acceptance-20261008.md)原样保留。

## 核心能力

- 权限、稳定分页、状态与错误契约；标签和数量条件使用 AND。
- checksum 去重、真实图片／视频校验、缩略图、10 秒抽帧、分类和模型写回。
- 浏览器上传签名 600 秒；临时查询从创建起共 900 秒，续签与重试不延长期限。
- 可恢复查询失败保留输入并提供 Retry；最多两次自动短重试。成功、永久失败、取消和过期会清理输入。
- 照片、描述和联合寻宠只比较同版特征；联合查询要求两种输入匹配同一个宠物裁剪，强照片不能盖过矛盾文字。
- 批量标签、人工物种标签抑制、重复删除回执、迟到结果失效、对象及索引一致性。

## 本地启动

```powershell
Set-Location D:\3184a2
.\scripts\bootstrap-local.ps1
.\scripts\dev.ps1 api
# 另一终端
.\scripts\dev.ps1 web
```

前端默认使用真实 Cognito。要进入可见开发模式，在 `apps/web/.env.local` 明确设置
`VITE_DEV_MODE=true`，仅允许 loopback。开发 API 使用内存数据，缺少真实服务会明确报错；
不会模拟 AI、Cognito、SNS 或 Lex 成功。暂停期间云端登录／API／S3 不可用于在线演示。

## 检查与真实本机复现

```powershell
.\scripts\verify.ps1
.\services\inference\.venv\Scripts\python.exe -m pytest services/inference/tests -q
.\.venv\Scripts\python.exe -m unittest discover -s infra/oracle/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s infra/aws/tests -v
.\.venv\Scripts\python.exe scripts/fit_pet_calibration.py --check
```

真实模型离线检查需要已验证的约 2.08 GiB 模型缓存，见[推理配置](services/inference/ENVIRONMENT.md)。
固定 COCO 双猫 PNG 来自[公开文档素材](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/coco_sample.png)，
保存在忽略的 `tmp/model-smoke/coco_sample.png`；脚本验证其 SHA-256，不自动下载或更换样本。
复现输出目录必须全新，避免覆盖失败证据：

```powershell
.\services\inference\.venv\Scripts\python.exe scripts/check_core_local.py `
  --sample tmp/model-smoke/coco_sample.png --output-dir tmp/my-core-run
.\services\inference\.venv\Scripts\python.exe scripts/check_video_local.py `
  --sample tmp/model-smoke/coco_sample.png --output-dir tmp/my-video-run
```

视频检查使用本机已安装的 Scoop FFmpeg/FFprobe。两只本地身份、内存队列及空入口识别 fixture
均在报告显式标注；没有邮件发送、云操作或真实宠物身份结论。
`scripts/evaluate_pet_quality.py` 可验证来源哈希、划分和真实预计算特征，使用生产 Worker 评分，
不会加载模型或把合成向量当作 AI 证据。真实身份基准仍需人工标签和至少 50 个独立保留查询来源。

## 模型与评分冻结

当前 manifest 为 `ecoguard-models-2026-10-08-v3`，SHA-256：
`639595e1e9ffe18cb11ead1c7480ffe7a31bf767f6cbaf6b8375829227a569ae`。
Grounding DINO 提供候选框，SigLIP2 在同一裁剪上统一比较物种，避免跨提示分数覆盖标签；
文字显式小写并按 64 token 处理。图片和文字分别使用仅校准集拟合的单调评分，
各自门槛固定 0.5，联合分数为两者几何均值。分数是候选排序依据，不是身份概率。
40 对公开语义校准数据及拟合器可复算；holdout 未参与拟合或阈值选择。

旧 v2 manifest 按原字节归档在 `config/manifests/`。任务固定 manifest，v3 不接 v2 任务，
异版向量不比较；旧媒体不能自动视为新索引，恢复时需审查重建方案。
视频计数是每物种的帧内最大数量，不是跨帧唯一动物数。

## 云环境与费用

下表区分10月8日历史环境与当前 C 个人 AWS + GCP 环境。当前资源与验收边界见[10月25日实际运行记录](docs/c-runtime-attempt-and-recovery-20261025.md)；[10月24日个人部署交接](docs/c-personal-operations-handover-20261024.md)和[只读检查记录](docs/c-readonly-integration-checkpoint-20261024.md)保留当时状态，不能据其旧资源数或旧表推断当前环境。

| 云 | 当前项目状态 |
|---|---|
| AWS 课程账号 `360493183467` / `default` / us-east-1 | 10月8日历史记录：Cognito、私有 S3、5 张按请求计费 DynamoDB 表、4 个 SQS 工作队列及 DLQ、ECR、7 个 Lambda、HTTP API 保留；运行和访问暂停 |
| AWS 个人账号 `011154879765` / `ecoguard-personal` | 10月25日：us-east-1个人环境60项资源，serial 95；应用暂停，实际跨云图片成功0，见[最新记录](docs/c-runtime-attempt-and-recovery-20261025.md) |
| Google `ecoguard-fit3184-jlii0474` | 10月8日历史记录：IAM/WIF 身份接线，账单未绑定，无计算部署 |
| Google `ecoguard-fit3184-a2-2026` | 个人验证环境13项资源，私有Cloud Run及模型warmup已验证；实际Lambda角色调用尚未验证 |
| Oracle | 较早路线的既有服务器模板；当时未找到可用主机、未部署应用。当前采用AWS + GCP，Oracle不是必选项 |

历史交接中的“59项资源已部署并暂停”保留在10月24日记录；首次保存计划实际应用后成为60项，不能将旧59项状态覆盖到当前serial 95。

课程 API `https://i4zicvj5s2.execute-api.us-east-1.amazonaws.com/api/v1` 当前关闭。
Cognito pool 为 `us-east-1_9nR2hwyVJ`，client 为 `6io5inllom6a5l43038uhbluvi`；
这些是公开配置，不是凭证。AWS LabRole→Google WIF 和令牌验签曾实际通过；
该轮 Oracle 路线没有完成接收端或自动入库验收，正式 Lex 亦待验收；这些历史结果不否定当前 AWS + GCP 路线。SNS 确认及唯一授权测试邮件已实际实收，本轮没有再发邮件。

用户选择保留云端数据和配置，并接受少量存储额度消耗。**暂停不保证账单为零**：
S3、DynamoDB、日志等保留数据仍可能占用额度；队列消息、TTL 和日志保留期仍继续。
10月8日当时的操作边界为“不创建新 VM、负载均衡或 Google 计算，不启动已停止服务器，不处理其他项目”；这不是后来获准的个人GCP私有推理部署的当前资源描述。新的运行或权限变更须按当前具体范围核验，不能重放已消耗的尝试许可。
[停用、检查及恢复说明](infra/aws/SHUTDOWN.md)。密钥、登录缓存、`.env`、原图／向量、Terraform state 均不入 Git。

## 代码与队友接管

| 路径 | 内容 |
|---|---|
| `apps/web` | React / TypeScript 英文界面、Cognito SDK、查询重试与过期恢复 |
| `packages/domain` | 权限、数量、标签、AND 与时间规则 |
| `services/aws` | API、预处理、推理任务、删除、通知、outbox、清理、Lex |
| `services/inference` | DINO / SigLIP2、可终止模型 Worker、服务令牌与 Cognito 验签 |
| `infra/aws` / `infra/gcp` / `infra/oracle` | 原 Terraform 基础设施、IAM/WIF、既有 Oracle 主机模板 |
| `config` / `scripts` | 固定模型与校准、可复算评估、本地和停用检查器 |

B 接管界面与用户体验；C 接管当前 AWS + GCP 身份、ingest 镜像和云部署；D 接管正式 Lex、邮件、独立数据、完整验收、演示与报告。
A 的核心交接详见[最新记录](docs/core-completion-20261008.md)，完整验收与贡献边界仍按[四人计划](docs/product-and-implementation-plan.md)。

[部署流程](docs/deployment-runbook.md) · [22 项验收矩阵](docs/acceptance-matrix.md) ·
[手动 Lex](docs/manual-lex-setup.md) · [Toolkit 配置](docs/aws-agent-toolkit-setup.md)
