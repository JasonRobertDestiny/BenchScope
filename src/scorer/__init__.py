"""评分器导出

Phase 9注意: BackendBenchmarkScorer已废弃，后端专项评分已集成到LLM Scorer中
"""

from src.scorer.llm_scorer import LLMScorer

__all__ = ["LLMScorer"]
