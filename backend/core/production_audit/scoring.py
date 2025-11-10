"""Scoring engine for production readiness audit."""

from typing import Dict, List

from .models import AuditResult, Gap, GapSeverity, ProductionReadinessReport, RoadmapItem


class ScoringEngine:
    """Engine for calculating weighted scores and generating reports."""
    
    def __init__(self):
        """Initialize scoring engine."""
        pass
    
    def calculate_overall_score(self, audit_results: List[AuditResult]) -> float:
        """Calculate weighted overall score from all audit results.
        
        Args:
            audit_results: List of AuditResult from all audit modules.
            
        Returns:
            Overall score between 0 and 100.
        """
        if not audit_results:
            return 0.0
        
        # Calculate weighted sum
        weighted_sum = sum(
            result.score * result.weight 
            for result in audit_results
        )
        
        # Calculate total weight (should be 1.0, but handle edge cases)
        total_weight = sum(result.weight for result in audit_results)
        
        if total_weight == 0:
            return 0.0
        
        return weighted_sum / total_weight
    
    def calculate_category_scores(
        self, 
        audit_results: List[AuditResult]
    ) -> Dict[str, float]:
        """Extract category scores from audit results.
        
        Args:
            audit_results: List of AuditResult from all audit modules.
            
        Returns:
            Dictionary mapping category names to scores.
        """
        return {
            result.category: result.score 
            for result in audit_results
        }
    
    def aggregate_gaps(
        self, 
        audit_results: List[AuditResult]
    ) -> Dict[str, List[Gap]]:
        """Aggregate gaps by category.
        
        Args:
            audit_results: List of AuditResult from all audit modules.
            
        Returns:
            Dictionary mapping category names to lists of gaps.
        """
        gaps_by_category = {}
        
        for result in audit_results:
            if result.gaps:
                gaps_by_category[result.category] = result.gaps
        
        return gaps_by_category
    
    def count_gaps_by_severity(
        self, 
        gaps_by_category: Dict[str, List[Gap]]
    ) -> Dict[str, int]:
        """Count gaps by severity level.
        
        Args:
            gaps_by_category: Dictionary of gaps organized by category.
            
        Returns:
            Dictionary with counts for each severity level.
        """
        counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "total": 0,
        }
        
        for gaps in gaps_by_category.values():
            for gap in gaps:
                counts[gap.severity.value] += 1
                counts["total"] += 1
        
        return counts
    
    def generate_roadmap(
        self, 
        gaps_by_category: Dict[str, List[Gap]]
    ) -> List[RoadmapItem]:
        """Generate prioritized roadmap from identified gaps.
        
        Args:
            gaps_by_category: Dictionary of gaps organized by category.
            
        Returns:
            List of RoadmapItem sorted by priority.
        """
        roadmap_items = []
        priority = 1
        
        # Priority order: CRITICAL -> HIGH -> MEDIUM -> LOW
        severity_order = [
            GapSeverity.CRITICAL,
            GapSeverity.HIGH,
            GapSeverity.MEDIUM,
            GapSeverity.LOW,
        ]
        
        for severity in severity_order:
            for category, gaps in gaps_by_category.items():
                for gap in gaps:
                    if gap.severity == severity:
                        roadmap_items.append(
                            RoadmapItem(
                                priority=priority,
                                title=gap.description,
                                description=gap.recommendation,
                                estimated_effort=gap.estimated_effort,
                                dependencies=gap.dependencies,
                                category=category,
                            )
                        )
                        priority += 1
        
        return roadmap_items
    
    def aggregate_recommendations(
        self, 
        audit_results: List[AuditResult]
    ) -> List[str]:
        """Aggregate all recommendations from audit results.
        
        Args:
            audit_results: List of AuditResult from all audit modules.
            
        Returns:
            List of unique recommendations.
        """
        recommendations = []
        seen = set()
        
        for result in audit_results:
            for rec in result.recommendations:
                if rec not in seen:
                    recommendations.append(rec)
                    seen.add(rec)
        
        return recommendations
    
    def generate_report(
        self, 
        audit_results: List[AuditResult]
    ) -> ProductionReadinessReport:
        """Generate complete production readiness report.
        
        Args:
            audit_results: List of AuditResult from all audit modules.
            
        Returns:
            Complete ProductionReadinessReport.
        """
        # Calculate scores
        overall_score = self.calculate_overall_score(audit_results)
        category_scores = self.calculate_category_scores(audit_results)
        
        # Aggregate gaps
        gaps_by_category = self.aggregate_gaps(audit_results)
        gap_counts = self.count_gaps_by_severity(gaps_by_category)
        
        # Generate roadmap and recommendations
        roadmap = self.generate_roadmap(gaps_by_category)
        recommendations = self.aggregate_recommendations(audit_results)
        
        return ProductionReadinessReport(
            overall_score=overall_score,
            category_scores=category_scores,
            total_gaps=gap_counts["total"],
            critical_gaps=gap_counts["critical"],
            high_gaps=gap_counts["high"],
            medium_gaps=gap_counts["medium"],
            low_gaps=gap_counts["low"],
            gaps_by_category=gaps_by_category,
            recommendations=recommendations,
            roadmap=roadmap,
        )
