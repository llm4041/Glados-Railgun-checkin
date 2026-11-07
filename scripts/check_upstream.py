"""检查上游仓库是否有新提交，若有则通过企业微信机器人推送提醒。

去重策略：把「上次已通知的上游提交 SHA」写入 STATE_FILE，
由 GitHub Actions 的 cache 在每次运行之间传递，避免同一提交反复打扰。
"""

import os
import sys
from pathlib import Path

import requests

API = "https://api.github.com"
UPSTREAM = os.environ.get("UPSTREAM_REPO", "Devilstore/Glados-Railgun-checkin")
FORK = os.environ.get("GITHUB_REPOSITORY", "llm4041/Glados-Railgun-checkin")
BRANCH = os.environ.get("UPSTREAM_BRANCH", "master")
TOKEN = (os.environ.get("GITHUB_TOKEN") or "").strip()
WEBHOOK_URL = (os.environ.get("WEBHOOK_URL") or "").strip()

STATE_FILE = Path(".upstream-state/last_sha.txt")
MAX_COMMITS = 5
MAX_CONTENT_LEN = 1800  # 企业微信 text 上限 2048 字节，留出余量


def log(message: str) -> None:
    print(f"[upstream-check] {message}", flush=True)


def api_get(path: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "upstream-check"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    resp = requests.get(API + path, headers=headers, timeout=20)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        raise RuntimeError("GitHub API 触发限流，检查 GITHUB_TOKEN 是否有效")
    resp.raise_for_status()
    return resp.json()


def read_last_sha() -> str:
    try:
        return STATE_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def write_last_sha(sha: str) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(sha + "\n", encoding="utf-8")


def build_message(pending: int) -> str:
    lines = [f"GLaDOS 上游有 {pending} 个新提交（本仓库落后 {pending} 个）", ""]
    try:
        limit = max(1, min(pending, MAX_COMMITS))
        commits = api_get(f"/repos/{UPSTREAM}/commits?sha={BRANCH}&per_page={limit}")
        for item in commits:
            title = item["commit"]["message"].splitlines()[0].strip()
            lines.append(f"- {item['sha'][:7]} {title[:60]}")
        if pending > MAX_COMMITS:
            lines.append(f"- …… 其余 {pending - MAX_COMMITS} 个见仓库")
    except Exception as e:  # noqa: BLE001 - 拿不到列表不影响提醒本身
        log(f"获取提交列表失败，仅发送摘要: {e}")

    lines += [
        "",
        f"对比: https://github.com/{FORK}/compare/{BRANCH}...{UPSTREAM.split('/')[0]}:{BRANCH}",
        "同步: git fetch upstream && git merge upstream/master",
    ]
    content = "\n".join(lines)
    return content[:MAX_CONTENT_LEN]


def send_wecom(content: str) -> bool:
    resp = requests.post(
        WEBHOOK_URL,
        json={"msgtype": "text", "text": {"content": content}},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode") == 0:
        return True
    log(f"企业微信接口返回异常: {data}")
    return False


def main() -> int:
    head_sha = api_get(f"/repos/{UPSTREAM}/branches/{BRANCH}")["commit"]["sha"]
    # 跨仓库对比只接受「同网络内的 owner:branch」写法，不能带仓库名
    upstream_owner = UPSTREAM.split("/")[0]
    compare = api_get(f"/repos/{FORK}/compare/{BRANCH}...{upstream_owner}:{BRANCH}")
    # 注意：此方向下 ahead_by 才是「上游有、本仓库没有」的提交数
    pending = int(compare.get("ahead_by", 0))

    if pending == 0:
        log(f"已与上游同步（{head_sha[:7]}），无需通知")
        write_last_sha(head_sha)
        return 0

    if head_sha == read_last_sha():
        log(f"上游 {head_sha[:7]} 已通知过，跳过")
        return 0

    if not WEBHOOK_URL:
        log(f"上游有 {pending} 个新提交，但未配置 WEBHOOK_URL，跳过企业微信通知")
        return 0

    content = build_message(pending)
    if not send_wecom(content):
        return 1

    write_last_sha(head_sha)
    log(f"已通知企业微信：上游落后 {pending} 个提交（{head_sha[:7]}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 - 定时任务失败需要可见
        log(f"检查失败: {e}")
        sys.exit(1)
