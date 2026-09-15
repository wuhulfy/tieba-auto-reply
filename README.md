# Tieba Auto Reply

一个使用 GitHub Actions 低频巡检指定贴吧的 Python 项目。默认目标为 `hifi交易`，候选回复内容为 `bd`，且默认处于预演模式，不会真正发布。

> 请仅在你有权自动回复的范围中使用，并遵守贴吧规则。该项目不会尝试绕过验证码或风控。

## 调度方式

工作流每天有 9 个候选时间，但只有当天绝对日序号 `% 3` 对应的 3 个时间会真正访问贴吧：

| 余数 | 北京时间 |
|---:|---|
| 0 | 06:52、12:37、19:47 |
| 1 | 07:24、13:13、21:33 |
| 2 | 08:41、15:06、22:18 |

使用绝对日序号而不是月内日期，可以避免 31 日到次月 1 日重复同一组。GitHub 的排队可能使实际执行时间延后数分钟。

## GitHub 配置

1. 创建公开仓库并推送本项目。
2. 在 `Settings -> Secrets and variables -> Actions -> Secrets` 新建 `BDUSS`。
3. 在 `Secrets` 新建 `TIEBA_USERNAME`，值为你在帖子中显示的精确昵称（作为兼容后备）。
4. 建议在 `Secrets` 新建 `TIEBA_USER_ID`，填账号的纯数字用户 ID；未设置时程序会尝试自动获取。
5. 在 `Variables` 中可设置 `MAX_REPLIES`、`REPLY_DELAY_MIN` 和 `REPLY_DELAY_MAX`；默认分别为 `20`、`5`、`10`。
6. 在 `Variables` 新建 `DRY_RUN`，首先设为 `true`。
7. 手动运行 workflow，保持 `dry_run=true`。预演会逐帖检查本账号是否已回复，并只列出确认未回复的帖子。
8. 确认结果后，再将仓库变量 `DRY_RUN` 改为 `false`。

`BDUSS` 不能写入文件、代码、Issue 或 Actions 日志。默认只处理当前时间往前 6 小时内创建的主题；更早的帖子不会补回复。

## 本地预演

PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:BDUSS = "你的 BDUSS"
$env:TIEBA_USERNAME = "你的贴吧用户名"
$env:TIEBA_USER_ID = "你的纯数字用户 ID"
$env:DRY_RUN = "true"
python -m src.main
```

手动运行不受三组候选时间限制，但真实回复仍要求当前北京时间在 06:00–23:59 内。

## 去重与停机

- Actions cache 保存已处理的主题 ID。
- 预演模式也会做贴吧端回复检查；检测到已回复时会记录主题 ID，但绝不发布内容。
- 对本地状态中没有的帖子，发布前会通过 HTTPS 手机端帖子接口检查首页和末尾页面中是否已有本账号回复；优先匹配稳定的数字用户 ID，昵称只作为后备。
- 验证码、安全验证、频率提示或登录失效会立即停止当次任务。
- 主题列表明确请求 `sort_type=1` 的发帖时间顺序，并按分页标记继续翻页；去除置顶和重复项后从新到旧处理。
- 默认仅处理发布时间不超过 6 小时的主题，可通过 `MAX_THREAD_AGE_HOURS` 调整。
- `MAX_REPLIES` 可设为任意正整数，默认单次最多回复 20 帖；真实回复之间默认随机等待 5–10 秒。

## 限制

由于GitHub Action定时操作可能存在一定延时/丢失的情况，故更建议手动执行。
贴吧的签到、列表和回复接口不是面向该项目的稳定公开 API，页面或风控改动后可能需要修改。项目中所有贴吧请求均使用 HTTPS。

## 来源说明

会话、`tbs` 和手机端签名思路参考了 MIT 许可的 [wuhulfy/TiebaSignIn](https://github.com/wuhulfy/TiebaSignIn)。本项目重新组织了实现，并将网络端点改为 HTTPS。
