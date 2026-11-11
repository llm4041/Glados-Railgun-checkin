"""企业微信群机器人推送（上游未内置，作为独立补丁，不修改 checkin.py）。

上游 checkin.py 只支持 PushDeer / Server酱。本文件通过包一层 PushService.__init__，
在原有后端基础上追加企业微信后端，其余流程（签到、渲染、退出码）完全复用上游实现。

用法（工作流里把 `python checkin.py` 换成 `python scripts/wecom_notify.py`）：
    WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=... \
    GLADOS_COOKIES='[...]' python scripts/wecom_notify.py

未配置 WECOM_WEBHOOK_URL 时行为与直接运行 checkin.py 完全一致。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

import checkin  # noqa: E402

ENV_WEBHOOK = "WECOM_WEBHOOK_URL"


class WecomBackend(checkin.PushBackend):
    """企业微信群机器人 Webhook 后端"""

    name = "企业微信"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, report) -> bool:
        try:
            resp = requests.post(
                self.webhook_url,
                json={"msgtype": "text", "text": {"content": f"{report.title}\n{self._render(report)}"}},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") == 0:
                return True
            checkin.logger.error(f"{checkin.LogEmoji.ERROR} [{self.name}] 推送失败: 接口返回 {data}")
            return False
        except Exception as e:  # noqa: BLE001 - 推送失败不应影响主流程
            checkin.logger.error(f"{checkin.LogEmoji.ERROR} [{self.name}] 推送失败: {e}")
            return False


_original_init = checkin.PushService.__init__


def _init_with_wecom(self, config=None):
    _original_init(self, config)
    webhook_url = (os.environ.get(ENV_WEBHOOK) or "").strip()
    if not webhook_url:
        checkin.logger.warning(f"{checkin.LogEmoji.WARNING} 环境变量 '{ENV_WEBHOOK}' 未设置。")
        return
    self.backends.append(WecomBackend(webhook_url))


checkin.PushService.__init__ = _init_with_wecom

if __name__ == "__main__":
    checkin.main()
