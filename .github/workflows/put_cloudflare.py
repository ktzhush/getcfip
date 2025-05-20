import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Union, Optional

class CloudflareKVClient:
    def __init__(self):
        load_dotenv()
        self.account_id = os.getenv("CF_ACCOUNT_ID")
        self.namespace_id = os.getenv("CF_NAMESPACE_ID")
        self.api_token = os.getenv("CF_API_KEY")
        self.email = os.getenv("CF_AUTH_EMAIL")
        self.v_file ="./BestCF/bestcfv4.txt"
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/storage/kv/namespaces/{self.namespace_id}"
        self._validate_credentials()

    def _validate_credentials(self):
        """验证必要凭证"""
        if not all([self.account_id, self.namespace_id, self.api_token]):
            raise ValueError("❌ 缺少必要的环境变量: CF_ACCOUNT_ID, CF_NAMESPACE_ID 或 CF_API_KEY")

    def _load_large_ips(self, v_file: str) -> str:
        """内存友好的实现"""
        seen = set()
        with open(v_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    seen.add(line)
        return '\n'.join(seen)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """发送API请求的通用方法"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "X-Auth-Key": self.api_token,
            "X-Auth-Email": self.email
        }
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"API请求失败: {str(e)}"
            if hasattr(e, 'response') and e.response:
                error_details = e.response.json().get('errors', [{}])[0]
                error_msg += f" | 状态码: {e.response.status_code} | 错误: {error_details.get('message', '未知错误')}"
            raise SystemExit(error_msg)

    def update_single_key(self, key: str, value: str, expiration_ttl: Optional[int] = None) -> Dict:
        """
        更新单个KV键值
        :param key: 键名
        :param value: 值
        :param expiration_ttl: 过期时间（秒）
        :return: API响应
        """
        endpoint = f"/values/{key}"
        params = {}
        if expiration_ttl:
            params["expiration_ttl"] = expiration_ttl
        return self._make_request("PUT", endpoint, data=value, params=params)

    def bulk_update_keys(self, kv_pairs: List[Dict], expiration_ttl: Optional[int] = None) -> Dict:
        """
        批量更新KV键值（最多10,000个）
        :param kv_pairs: 键值对列表，格式: [{"key": "k1", "value": "v1"}, ...]
        :param expiration_ttl: 统一过期时间（秒）
        :return: API响应
        """
        if len(kv_pairs) > 10000:
            raise ValueError("单次批量操作不能超过10,000个键值对")
        elif len(kv_pairs) < 2:
            raise ValueError("KEY值为1，不能进行批量更新，请使用单个键值对更新。")
        payload = kv_pairs
        if expiration_ttl:
            for item in payload:
                item["expiration_ttl"] = expiration_ttl
        return self._make_request("PUT", "/bulk", json=payload)

    def load_keys_from_file(self, file_path: Union[str, Path]) -> List[Dict]:
        """
        从文件加载键值对（示例：每行作为一个值，自动生成键）
        :param file_path: 文件路径
        :return: 格式化的键值对列表
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
            return [{"key": f"item_{idx}", "value": line} for idx, line in enumerate(lines, 1)]

def load_large_ips(path: str) -> str:
    """内存友好的实现"""
    seen = set()
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                seen.add(line)
    return '\n'.join(seen)

if __name__ == "__main__":
    try:
        client = CloudflareKVClient()

        # 加载IP文件
        ip_file = os.getenv("IP_FILE_PATH")
        if not ip_file:
            raise ValueError("未设置环境变量 IP_FILE_PATH")
        ip_data = client._load_large_ips(ip_file)

        # 单键更新
        print("正在更新单键...")
        single_result = client.update_single_key(
            key="ip_list",
            value=ip_data,
            expiration_ttl=None  # 永不过期
        )
        print(f"✅ 单键更新成功: {json.dumps(single_result, indent=2)}")

    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")
        exit(1)