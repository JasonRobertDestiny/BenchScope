#!/usr/bin/env python3
"""全面验证Feishu表格、数据模型、存储逻辑的字段对齐"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Set

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from src.config import get_settings
from src.models import ScoredCandidate
from src.storage.feishu_storage import FeishuStorage


def get_model_fields() -> Dict[str, str]:
    """获取ScoredCandidate模型的所有字段及其类型"""
    import inspect
    from dataclasses import fields

    model_fields = {}
    for field in fields(ScoredCandidate):
        field_type = str(field.type)
        model_fields[field.name] = field_type

    return model_fields


async def get_feishu_fields() -> Dict[str, Dict]:
    """获取飞书表格的所有字段配置"""
    settings = get_settings()

    async with httpx.AsyncClient(timeout=30) as client:
        # 获取access token
        token_url = (
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        )
        token_resp = await client.post(
            token_url,
            json={
                "app_id": settings.feishu.app_id,
                "app_secret": settings.feishu.app_secret,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data["tenant_access_token"]

        # 获取表格字段配置
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/fields"
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f'查询失败: {data.get("msg")}')

        fields = data.get("data", {}).get("items", [])

        feishu_fields = {}
        for field in fields:
            field_name = field.get("field_name")
            field_type = field.get("type")
            field_id = field.get("field_id")

            # 获取选项配置（如果是单选/多选字段）
            options = None
            if field_type in [3, 4]:  # 单选(3)或多选(4)
                options = [opt.get("name") for opt in field.get("property", {}).get("options", [])]

            feishu_fields[field_name] = {
                "field_id": field_id,
                "type": field_type,
                "options": options,
            }

        return feishu_fields


def get_storage_mapping() -> Dict[str, str]:
    """获取存储层的字段映射"""
    storage = FeishuStorage()
    return storage.FIELD_MAPPING


async def main():
    print("=" * 80)
    print("BenchScope 字段对齐验证报告")
    print("=" * 80)
    print()

    # 1. 获取模型字段
    model_fields = get_model_fields()
    print(f"【ScoredCandidate模型字段】共{len(model_fields)}个:")
    for idx, (name, type_) in enumerate(sorted(model_fields.items()), 1):
        print(f"  {idx:2d}. {name:30s} {type_}")
    print()

    # 2. 获取飞书字段
    feishu_fields = await get_feishu_fields()
    print("=" * 80)
    print(f"【飞书表格字段】共{len(feishu_fields)}个:")

    # 字段类型映射 (根据飞书API文档)
    field_type_names = {
        1: "文本",
        2: "数字",
        3: "单选",  # 修复：3是单选
        4: "多选",  # 修复：4是多选
        5: "日期",
        7: "复选框",
        11: "人员",
        13: "电话",
        15: "超链接",
        17: "附件",
        18: "单向关联",
        21: "查找引用",
        22: "公式",
        23: "双向关联",
        1001: "创建时间",
        1002: "最后更新时间",
        1003: "创建人",
        1004: "修改人",
        1005: "自动编号",
    }

    for idx, (name, config) in enumerate(sorted(feishu_fields.items()), 1):
        type_name = field_type_names.get(config["type"], f"未知({config['type']})")
        options_info = ""
        if config["options"]:
            options_info = f" - 选项: {', '.join(config['options'])}"
        print(f"  {idx:2d}. {name:30s} [{type_name}]{options_info}")
    print()

    # 3. 获取存储映射
    storage_mapping = get_storage_mapping()
    print("=" * 80)
    print(f"【存储层字段映射】共{len(storage_mapping)}个:")
    for idx, (model_key, feishu_name) in enumerate(sorted(storage_mapping.items()), 1):
        print(f"  {idx:2d}. {model_key:30s} → {feishu_name}")
    print()

    # 4. 差异分析
    print("=" * 80)
    print("【差异分析】")
    print("=" * 80)

    # 4.1 模型字段 vs 存储映射
    model_keys = set(model_fields.keys())
    mapped_keys = set(storage_mapping.keys())

    unmapped_model_fields = model_keys - mapped_keys
    if unmapped_model_fields:
        print(f"\n❌ 模型有但未映射到飞书 ({len(unmapped_model_fields)}个):")
        for field in sorted(unmapped_model_fields):
            field_type = model_fields[field]
            print(f"     - {field:30s} ({field_type})")

    # 4.2 存储映射 vs 飞书字段
    mapped_feishu_names = set(storage_mapping.values())
    actual_feishu_names = set(feishu_fields.keys())

    missing_in_feishu = mapped_feishu_names - actual_feishu_names
    if missing_in_feishu:
        print(f"\n❌ 映射指向的飞书字段不存在 ({len(missing_in_feishu)}个):")
        for name in sorted(missing_in_feishu):
            # 找出哪个模型字段映射到这个不存在的飞书字段
            model_key = [k for k, v in storage_mapping.items() if v == name][0]
            print(f"     - {name:30s} ← {model_key}")

    extra_in_feishu = actual_feishu_names - mapped_feishu_names
    if extra_in_feishu:
        print(f"\n⚠️  飞书有但未被使用 ({len(extra_in_feishu)}个):")
        for name in sorted(extra_in_feishu):
            type_name = field_type_names.get(feishu_fields[name]["type"], "未知")
            print(f"     - {name:30s} [{type_name}]")

    # 4.3 完美对齐的字段
    aligned_fields = mapped_feishu_names & actual_feishu_names
    print(f"\n✅ 完美对齐的字段 ({len(aligned_fields)}个):")
    for name in sorted(aligned_fields):
        model_key = [k for k, v in storage_mapping.items() if v == name][0]
        type_name = field_type_names.get(feishu_fields[name]["type"], "未知")
        model_type = model_fields.get(model_key, "未知")
        print(f"     {name:30s} [{type_name}] ← {model_key} ({model_type})")

    # 5. 数据覆盖率建议
    print()
    print("=" * 80)
    print("【数据覆盖率建议】")
    print("=" * 80)

    # 分析哪些字段可能经常为空
    optional_fields = [
        k for k, v in model_fields.items()
        if "Optional" in v or "None" in v
    ]

    print(f"\n可选字段 ({len(optional_fields)}个) - 可能导致飞书字段为空:")
    for field in sorted(optional_fields):
        if field in storage_mapping:
            feishu_name = storage_mapping[field]
            print(f"  - {field:30s} → {feishu_name}")
        else:
            print(f"  - {field:30s} (未映射)")

    # 6. 总结与建议
    print()
    print("=" * 80)
    print("【总结】")
    print("=" * 80)

    total_issues = len(unmapped_model_fields) + len(missing_in_feishu)
    if total_issues == 0:
        print("\n✅ 所有字段完美对齐！模型、存储映射、飞书表格三者同步。")
    else:
        print(f"\n⚠️  发现{total_issues}个问题需要修复:")
        if unmapped_model_fields:
            print(f"  - {len(unmapped_model_fields)}个模型字段未映射到飞书")
        if missing_in_feishu:
            print(f"  - {len(missing_in_feishu)}个映射指向的飞书字段不存在")

    print()


if __name__ == "__main__":
    asyncio.run(main())
