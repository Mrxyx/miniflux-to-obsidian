"""Miniflux API 操作"""

import logging
import requests


class MinifluxClient:
    """Miniflux API 客户端"""

    def __init__(self, host, api_key):
        self.host = host.rstrip('/')
        self.headers = {
            "X-Auth-Token": api_key,
            "Content-Type": "application/json"
        }

    def get_starred_entries(self, limit=50):
        """获取加星文章"""
        try:
            logging.info(f"正在获取加星文章 (limit={limit})...")
            resp = requests.get(
                f"{self.host}/v1/entries?starred=true&limit={limit}",
                headers=self.headers,
                timeout=30
            )
            resp.raise_for_status()
            entries = resp.json().get('entries', [])
            logging.info(f"找到 {len(entries)} 篇加星文章")
            return entries
        except requests.RequestException as e:
            logging.error(f"获取文章失败: {e}")
            return None

    def unstar_entry(self, entry_id):
        """取消文章收藏"""
        try:
            requests.put(
                f"{self.host}/v1/entries/{entry_id}/bookmark",
                headers=self.headers,
                timeout=10
            )
            return True
        except Exception as e:
            logging.warning(f"⚠️ 取消收藏失败 (id={entry_id}): {e}")
            return False

    def unstar_entries(self, entries):
        """批量取消文章收藏"""
        if not entries:
            return
        logging.info(f"正在取消 {len(entries)} 篇文章的收藏...")
        for entry in entries:
            self.unstar_entry(entry['id'])
        logging.info("✅ 收藏已取消")

    def get_entries(self, limit=50, status="unread", after_entry_id=None):
        """获取文章列表"""
        try:
            params = {"status": status, "limit": limit, "order": "id", "direction": "asc"}
            if after_entry_id:
                params["after_entry_id"] = after_entry_id
            resp = requests.get(
                f"{self.host}/v1/entries",
                headers=self.headers,
                params=params,
                timeout=30
            )
            resp.raise_for_status()
            return resp.json().get('entries', [])
        except requests.RequestException as e:
            logging.error(f"获取文章失败: {e}")
            return None

    def update_entry_content(self, entry_id, content):
        """更新文章内容"""
        try:
            resp = requests.put(
                f"{self.host}/v1/entries/{entry_id}",
                headers=self.headers,
                json={"content": content},
                timeout=30
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            logging.error(f"更新文章内容失败 (id={entry_id}): {e}")
            return False
