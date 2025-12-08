# P13: 修复飞书分页bug导致的重复推送问题

## 问题诊断

### 现象
2025-12-06和2025-12-07连续两天推送了相同的GitHub仓库:
- `SIGMME/IWR-Bench`
- `ace-agent/ace`

### 根本原因
**飞书 search API (POST) 分页存在bug，返回重复page_token，导致只能读取前500条记录**

```
飞书表格总记录数: 1003
去重读取到的URL数: 276
差距: 727条记录未被读取! (72.5%)
```

### 技术细节
当前代码使用 POST `/records/search` 接口:
```python
# feishu_storage.py:523
url = f"{self.base_url}/bitable/v1/apps/.../tables/.../records/search"
resp = await client.post(url, headers=..., json={"page_size": 500})
```

飞书search API分页调试结果:
```
Page 1: items=500, has_more=True, token=cGFnZVRva2VuOjUwMA== (pageToken:500)
Page 2: items=500, has_more=True, token=cGFnZVRva2VuOjUwMA== (相同token!)
DUPLICATE TOKEN DETECTED! -> 提前终止
```

而 GET `/records` 接口分页正常:
```
Page 1: items=500, has_more=True, token=recv3igKZFL3T0...
Page 2: items=500, has_more=True, token=recv3lVMQEEfQz... (不同token)
Page 3: items=3, has_more=False
Done! Total items: 1003 (全部读取)
```

---

## 解决方案

**将 `get_existing_urls()` 和 `read_existing_records()` 从 POST search API 改为 GET records API**

---

## 实施步骤

### Step 1: 修改 `get_existing_urls()` 方法

**文件**: `src/storage/feishu_storage.py`
**位置**: 约行510-588

**当前代码** (使用 POST search):
```python
async def get_existing_urls(self) -> set[str]:
    """查询飞书Bitable已存在的所有URL（用于去重）"""
    await self._ensure_access_token()

    existing_urls: set[str] = set()
    page_token = None
    max_pages = 20
    page_count = 0
    seen_tokens: set[str] = set()

    async with httpx.AsyncClient(timeout=10) as client:
        await self._ensure_field_cache(client)
        while True:
            url = f"{self.base_url}/bitable/v1/apps/{self.settings.feishu.bitable_app_token}/tables/{self.settings.feishu.bitable_table_id}/records/search"

            payload = {"page_size": 1000}
            if page_token:
                payload["page_token"] = page_token

            resp = await self._request_with_retry(
                client,
                "POST",
                url,
                headers=self._auth_header(),
                json=payload,
            )
            # ... 其余代码
```

**修改后代码** (使用 GET records):
```python
async def get_existing_urls(self) -> set[str]:
    """查询飞书Bitable已存在的所有URL（用于去重）

    P13修复: 从POST search改为GET records，解决分页token重复bug
    """
    await self._ensure_access_token()

    existing_urls: set[str] = set()
    page_token: Optional[str] = None
    max_pages = 20
    page_count = 0

    async with httpx.AsyncClient(timeout=10) as client:
        await self._ensure_field_cache(client)
        while True:
            # P13修复: 改用 GET records 接口，分页token不会重复
            url = f"{self.base_url}/bitable/v1/apps/{self.settings.feishu.bitable_app_token}/tables/{self.settings.feishu.bitable_table_id}/records"

            params: Dict[str, Any] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            resp = await self._request_with_retry(
                client,
                "GET",
                url,
                headers=self._auth_header(),
                params=params,  # GET请求用params而不是json
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise FeishuAPIError(f"飞书查询失败: {data}")

            items = data.get("data", {}).get("items", [])
            url_field_name = self.FIELD_MAPPING["url"]

            for item in items:
                fields = item.get("fields", {})
                url_obj = fields.get(url_field_name)

                if isinstance(url_obj, dict):
                    url_value = url_obj.get("link")
                    url_key = canonicalize_url(url_value)
                    if url_key:
                        existing_urls.add(url_key)
                elif isinstance(url_obj, str):
                    url_key = canonicalize_url(url_obj)
                    if url_key:
                        existing_urls.add(url_key)

            has_more = data.get("data", {}).get("has_more", False)
            if not has_more:
                break

            page_token = data.get("data", {}).get("page_token")
            if not page_token:
                break

            page_count += 1
            if page_count >= max_pages:
                logger.warning(
                    "飞书去重分页超过上限%d，终止以防卡死，已收集URL:%d",
                    max_pages,
                    len(existing_urls),
                )
                break

    logger.info("飞书已存在URL数量: %d", len(existing_urls))
    return existing_urls
```

### Step 2: 修改 `read_existing_records()` 方法

**文件**: `src/storage/feishu_storage.py`
**位置**: 约行590-698

**修改要点**:
1. 将 `POST .../records/search` 改为 `GET .../records`
2. 将 `json=payload` 改为 `params=params`
3. 移除重复token检测（GET接口不会有此问题）

**修改后代码**:
```python
async def read_existing_records(self) -> List[dict[str, Any]]:
    """查询飞书已存在的记录，含URL/发布时间/创建时间/来源，用于时间窗去重

    P13修复: 从POST search改为GET records，解决分页token重复bug
    """

    await self._ensure_access_token()

    records: List[dict[str, Any]] = []
    page_token: Optional[str] = None
    url_field = self.FIELD_MAPPING["url"]
    publish_field = self.FIELD_MAPPING["publish_date"]
    max_pages = 20
    page_count = 0

    async with httpx.AsyncClient(timeout=10) as client:
        await self._ensure_field_cache(client)
        while True:
            # P13修复: 改用 GET records 接口
            url = f"{self.base_url}/bitable/v1/apps/{self.settings.feishu.bitable_app_token}/tables/{self.settings.feishu.bitable_table_id}/records"

            params: Dict[str, Any] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            resp = await self._request_with_retry(
                client,
                "GET",
                url,
                headers=self._auth_header(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise FeishuAPIError(f"飞书查询失败: {data}")

            items = data.get("data", {}).get("items", [])

            for item in items:
                fields = item.get("fields", {})
                url_obj = fields.get(url_field)
                publish_raw = fields.get(publish_field)
                created_raw = fields.get("创建时间")

                # URL字段兼容两种格式
                if isinstance(url_obj, dict):
                    url_value = url_obj.get("link")
                elif isinstance(url_obj, str):
                    url_value = url_obj
                else:
                    url_value = None

                url_key = canonicalize_url(url_value)
                publish_date: Optional[datetime] = None
                if isinstance(publish_raw, (int, float)):
                    publish_date = datetime.fromtimestamp(publish_raw / 1000)
                elif isinstance(publish_raw, str) and publish_raw:
                    try:
                        publish_date = datetime.fromisoformat(
                            publish_raw.replace("Z", "+00:00")
                        )
                    except ValueError:
                        logger.debug("无法解析发布时间: %s", publish_raw)

                if publish_date:
                    publish_date = publish_date.replace(tzinfo=None)

                # P12: 解析记录创建时间
                created_at: Optional[datetime] = None
                if isinstance(created_raw, (int, float)):
                    created_at = datetime.fromtimestamp(created_raw / 1000)
                elif isinstance(created_raw, str) and created_raw:
                    try:
                        created_at = datetime.fromisoformat(
                            created_raw.replace("Z", "+00:00")
                        )
                    except ValueError:
                        logger.debug("无法解析创建时间: %s", created_raw)

                if created_at:
                    created_at = created_at.replace(tzinfo=None)

                if url_key:
                    source_field = self.FIELD_MAPPING.get("source", "来源")
                    source_value = fields.get(source_field, "default")
                    record_item: dict[str, Any] = {
                        "url": str(url_value),
                        "url_key": url_key,
                        "publish_date": publish_date,
                        "created_at": created_at,
                        "source": str(source_value),
                    }
                    records.append(record_item)

            has_more = data.get("data", {}).get("has_more", False)
            if not has_more:
                break
            page_token = data.get("data", {}).get("page_token")
            if not page_token:
                break

            page_count += 1
            if page_count >= max_pages:
                logger.warning("读取飞书记录超出分页上限%d，提前停止", max_pages)
                break

    logger.info("飞书历史记录读取完成: %d条", len(records))
    return records
```

### Step 3: 同样修改 `read_brief_records()` 方法

**位置**: 约行701-780

同样的修改模式:
- `POST .../records/search` -> `GET .../records`
- `json=payload` -> `params=params`

---

## 测试验证计划

### 单元测试
```bash
.venv/bin/python -c "
import asyncio
from src.storage import FeishuStorage

async def test():
    storage = FeishuStorage()
    urls = await storage.get_existing_urls()
    print(f'读取URL数量: {len(urls)}')

    # 验证是否包含之前遗漏的记录
    for url in urls:
        if 'IWR-Bench' in url or 'ace-agent' in url:
            print(f'Found: {url}')

asyncio.run(test())
"
```

### 验收标准
- [ ] `get_existing_urls()` 能读取全部1003条记录
- [ ] 不再出现"重复page_token"警告
- [ ] `SIGMME/IWR-Bench` 和 `ace-agent/ace` 能在URL列表中找到
- [ ] 连续运行两次，第二次应该正确去重（0条新增）

---

## 回滚方案

如果GET接口出现问题，可以回退到search接口并增加page_size:
```python
# 临时workaround: 减小page_size避免token冲突
payload = {"page_size": 100}  # 从500降到100
```

---

## 相关文件

- `src/storage/feishu_storage.py` - 需要修改的文件
- `src/main.py` - 调用方，无需修改
- `.claude/specs/benchmark-intelligence-agent/CODEX-P12-DEDUP-FIX.md` - 之前的去重修复（本次修复的前提）
