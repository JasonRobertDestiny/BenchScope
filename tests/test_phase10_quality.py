"""Phase 10 推送质量优化测试"""

from __future__ import annotations

import pytest

from src.prefilter.rule_filter import (
    _looks_like_algo_paper,
    _looks_like_non_mgx_application,
    _looks_like_technical_report,
)
from src.models import RawCandidate
from src.common import constants


class TestTechnicalReportDetection:
    """技术报告检测测试"""

    def test_qwen3_vl_technical_report(self) -> None:
        """Qwen3-VL Technical Report应被过滤"""
        candidate = RawCandidate(
            title="Qwen3-VL Technical Report",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We present Qwen3-VL, a multimodal language model...",
        )
        assert _looks_like_technical_report(candidate) is True

    def test_benchmark_paper_not_filtered(self) -> None:
        """Benchmark论文不应被过滤"""
        candidate = RawCandidate(
            title="SWE-bench: A Benchmark for Software Engineering",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We introduce SWE-bench, a benchmark dataset for...",
        )
        assert _looks_like_technical_report(candidate) is False


class TestNonMgxApplicationDetection:
    """非MGX应用检测测试"""

    def test_autonomous_driving_filtered(self) -> None:
        """自动驾驶论文应被过滤"""
        candidate = RawCandidate(
            title="Model-Based Policy Adaptation for Autonomous Driving",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We propose a new approach for autonomous driving...",
        )
        assert _looks_like_non_mgx_application(candidate) is True

    def test_code_generation_not_filtered(self) -> None:
        """代码生成论文不应被过滤"""
        candidate = RawCandidate(
            title="CodeGen: An Open Large Language Model for Code",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We present CodeGen, a code generation model...",
        )
        assert _looks_like_non_mgx_application(candidate) is False


class TestAlgoPaperDetection:
    """算法方法论文检测测试"""

    def test_algo_paper_filtered(self) -> None:
        """无Benchmark信号的算法论文应过滤"""
        candidate = RawCandidate(
            title="We present a new architecture for vision transformers",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We propose a novel architecture without evaluation details.",
        )
        assert _looks_like_algo_paper(candidate) is True

    def test_benchmark_method_not_filtered(self) -> None:
        """包含benchmark信号的论文应保留"""
        candidate = RawCandidate(
            title="A new approach evaluated on a benchmark dataset",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We propose a method and evaluate on a benchmark dataset.",
        )
        assert _looks_like_algo_paper(candidate) is False


class TestOtherDomainConstants:
    """Other领域常量测试"""

    def test_other_domain_high_threshold(self) -> None:
        """Other领域相关性门槛应为7.0"""
        assert constants.OTHER_DOMAIN_RELEVANCE_FLOOR == 7.0

    def test_other_domain_max_ratio(self) -> None:
        """Other领域占比上限应为20%"""
        assert constants.OTHER_DOMAIN_MAX_RATIO == 0.20
