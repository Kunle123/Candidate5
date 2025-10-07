"""
CV Quality Metrics Tracker
===========================
Tracks quality metrics over time for monitoring and analysis.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class CVQualityMetrics:
    """Tracks and stores CV quality metrics for monitoring."""
    
    def __init__(self, storage_path: str = "/tmp/cv_quality_metrics.jsonl"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log_generation(
        self,
        session_id: str,
        quality_report: Dict[str, Any],
        generation_time_seconds: float,
        model: str,
        profile_size: str,
        was_auto_corrected: bool = False
    ):
        """
        Log a CV generation event with quality metrics.
        
        Args:
            session_id: Session ID (anonymized for privacy)
            quality_report: Quality report dict from CVQualityValidator
            generation_time_seconds: Time taken to generate CV
            model: Model used (e.g., "gpt-4o")
            profile_size: Profile size category (small/medium/large/very_large)
            was_auto_corrected: Whether auto-correction was applied
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id_hash": hash(session_id) % 10000,  # Anonymized
            "model": model,
            "profile_size": profile_size,
            "generation_time_s": round(generation_time_seconds, 2),
            "was_auto_corrected": was_auto_corrected,
            "passed": quality_report.get("passed", False),
            "error_count": len(quality_report.get("errors", [])),
            "warning_count": len(quality_report.get("warnings", [])),
            "metrics": quality_report.get("metrics", {})
        }
        
        try:
            with open(self.storage_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
            logger.debug(f"[METRICS] Logged CV generation: passed={entry['passed']}, profile_size={profile_size}")
        except Exception as e:
            logger.error(f"[METRICS] Failed to log metrics: {e}")
    
    def get_recent_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent metrics entries."""
        if not self.storage_path.exists():
            return []
        
        try:
            with open(self.storage_path, "r") as f:
                lines = f.readlines()
                recent_lines = lines[-limit:]
                return [json.loads(line) for line in recent_lines]
        except Exception as e:
            logger.error(f"[METRICS] Failed to read metrics: {e}")
            return []
    
    def get_summary_stats(self, limit: int = 100) -> Dict[str, Any]:
        """Get summary statistics from recent generations."""
        metrics = self.get_recent_metrics(limit)
        
        if not metrics:
            return {"error": "No metrics available"}
        
        total = len(metrics)
        passed = sum(1 for m in metrics if m.get("passed", False))
        auto_corrected = sum(1 for m in metrics if m.get("was_auto_corrected", False))
        
        # Calculate average metrics
        avg_role_completeness = sum(
            m.get("metrics", {}).get("role_completeness_pct", 0) 
            for m in metrics
        ) / total if total > 0 else 0
        
        avg_bullets = sum(
            m.get("metrics", {}).get("avg_bullets_per_role", 0)
            for m in metrics
        ) / total if total > 0 else 0
        
        avg_gen_time = sum(m.get("generation_time_s", 0) for m in metrics) / total if total > 0 else 0
        
        # Group by profile size
        by_size = {}
        for m in metrics:
            size = m.get("profile_size", "unknown")
            if size not in by_size:
                by_size[size] = {"total": 0, "passed": 0}
            by_size[size]["total"] += 1
            if m.get("passed", False):
                by_size[size]["passed"] += 1
        
        # Calculate pass rates by size
        for size_data in by_size.values():
            size_data["pass_rate_pct"] = round(
                (size_data["passed"] / size_data["total"] * 100) if size_data["total"] > 0 else 0,
                1
            )
        
        return {
            "total_generations": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate_pct": round((passed / total * 100) if total > 0 else 0, 1),
            "auto_corrected_count": auto_corrected,
            "auto_correction_rate_pct": round((auto_corrected / total * 100) if total > 0 else 0, 1),
            "avg_role_completeness_pct": round(avg_role_completeness, 1),
            "avg_bullets_per_role": round(avg_bullets, 1),
            "avg_generation_time_s": round(avg_gen_time, 1),
            "by_profile_size": by_size,
            "last_updated": datetime.utcnow().isoformat()
        }


# Global instance
_metrics_tracker = None


def get_metrics_tracker() -> CVQualityMetrics:
    """Get or create the global metrics tracker."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = CVQualityMetrics()
    return _metrics_tracker

