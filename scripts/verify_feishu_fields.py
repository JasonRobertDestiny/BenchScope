"""验证飞书新表格的字段是否正确创建"""
import asyncio
import httpx
from src.config import get_settings

# Phase 8要求的25个字段
REQUIRED_FIELDS = {
    # 基础信息组 (5个)
    "标题",
    "URL",
    "来源",
    "摘要",
    "发布日期",
    # Benchmark特征组 (7个)
    "任务领域",
    "评估指标",
    "基准模型",
    "机构",
    "作者",
    "数据集规模",
    "数据集规模描述",
    # GitHub信息组 (3个)
    "GitHub Stars",
    "GitHub URL",
    "许可证",
    # 评分信息组 (8个)
    "活跃度",
    "可复现性",
    "许可合规",
    "新颖性",
    "MGX适配度",
    "总分",
    "优先级",
    "评分依据",
    # 系统信息组 (2个)
    "创建时间",
    "最后修改时间",
}


async def verify_fields():
    """验证飞书表格字段"""
    settings = get_settings()

    async with httpx.AsyncClient(timeout=10) as client:
        # 1. 获取access token
        token_resp = await client.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": settings.feishu.app_id,
                "app_secret": settings.feishu.app_secret,
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["tenant_access_token"]

        # 2. 获取表格字段列表
        fields_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/fields"

        fields_resp = await client.get(
            fields_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        fields_resp.raise_for_status()
        data = fields_resp.json()

        if data.get("code") != 0:
            print(f"❌ 获取字段失败: {data}")
            return False

        # 3. 提取字段名称
        fields = data.get("data", {}).get("items", [])
        field_names = {field["field_name"] for field in fields}

        print(f"\n{'='*80}")
        print(f"飞书表格字段验证报告")
        print(f"{'='*80}\n")
        print(f"表格URL: https://deepwisdom.feishu.cn/base/{settings.feishu.bitable_app_token}?table={settings.feishu.bitable_table_id}")
        print(f"当前字段数: {len(field_names)}/25\n")

        # 4. 检查必需字段
        missing_fields = REQUIRED_FIELDS - field_names
        extra_fields = field_names - REQUIRED_FIELDS

        if not missing_fields:
            print("✅ 所有25个必需字段已创建！\n")
        else:
            print(f"⚠️ 缺少{len(missing_fields)}个必需字段:\n")
            for field in sorted(missing_fields):
                print(f"   ❌ {field}")
            print()

        if extra_fields:
            print(f"ℹ️ 额外字段（{len(extra_fields)}个）:\n")
            for field in sorted(extra_fields):
                print(f"   • {field}")
            print()

        # 5. 分组显示已创建字段
        print("📋 已创建字段分组:\n")

        groups = {
            "基础信息": ["标题", "URL", "来源", "摘要", "发布日期"],
            "Benchmark特征": ["任务领域", "评估指标", "基准模型", "机构", "作者", "数据集规模", "数据集规模描述"],
            "GitHub信息": ["GitHub Stars", "GitHub URL", "许可证"],
            "评分信息": ["活跃度", "可复现性", "许可合规", "新颖性", "MGX适配度", "总分", "优先级", "评分依据"],
            "系统信息": ["创建时间", "最后修改时间"],
        }

        for group_name, group_fields in groups.items():
            created = [f for f in group_fields if f in field_names]
            print(f"  【{group_name}】({len(created)}/{len(group_fields)})")
            for field in group_fields:
                status = "✓" if field in field_names else "✗"
                print(f"    {status} {field}")
            print()

        # 6. 验证关键字段类型
        print("🔍 关键字段类型验证:\n")

        field_types = {field["field_name"]: field["type"] for field in fields}

        type_checks = {
            "任务领域": 3,  # 多选
            "来源": 3,  # 单选
            "优先级": 3,  # 单选
            "总分": 2,  # 数字
            "数据集规模": 2,  # 数字
            "URL": 15,  # 超链接
            "摘要": 1,  # 多行文本
        }

        for field_name, expected_type in type_checks.items():
            if field_name in field_types:
                actual_type = field_types[field_name]
                status = "✓" if actual_type == expected_type else "⚠️"
                print(f"  {status} {field_name}: 类型{actual_type} {'(正确)' if actual_type == expected_type else f'(应为{expected_type})'}")
            else:
                print(f"  ✗ {field_name}: 字段不存在")

        print(f"\n{'='*80}\n")

        return len(missing_fields) == 0


if __name__ == "__main__":
    success = asyncio.run(verify_fields())
    exit(0 if success else 1)
