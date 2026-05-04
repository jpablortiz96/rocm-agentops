"""Pydantic schemas for AMD benchmark results and evidence packs."""

from typing import List, Optional

from pydantic import BaseModel, Field


class BenchmarkRequestResult(BaseModel):
    request_id: str
    prompt_type: str
    success: bool
    latency_ms: float
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    error: Optional[str] = None


class AmdBenchmarkSummary(BaseModel):
    run_id: str
    timestamp: str
    endpoint_base_url: str
    model: str
    mock_mode: bool
    total_requests: int
    successful_requests: int
    failed_requests: int
    concurrency_levels: List[int]
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    estimated_total_tokens: int
    estimated_tokens_per_second: float
    benchmark_duration_seconds: float
    notes: List[str] = Field(default_factory=list)
    request_results: List[BenchmarkRequestResult] = Field(default_factory=list)
    benchmark_verified: bool = False


class AmdEvidencePack(BaseModel):
    summary: AmdBenchmarkSummary
    amd_claims: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)
