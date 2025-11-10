"""
Meta Self-Building Orchestrator - The ultimate recursive self-improvement system.
This system improves its own self-building capabilities using its own agent infrastructure.
"""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from app.config.settings import get_settings
from app.core.error_handler import safe_execute

# Import the system's own infrastructure to use for self-improvement
from ...discovery.component_scanner import component_scanner, ComponentInfo
from ...registry.dynamic_registry import dynamic_registry
from ...generators.skill_auto_generator import auto_generate_skill
from ...intelligence.audit_logger import audit_logger, AuditEventType
from ..optimization.optimization_engine import optimization_engine

logger = logging.getLogger(__name__)
settings = get_settings()


class MetaImprovementType(Enum):
    """Types of meta-improvements the system can make to itself."""
    ALGORITHM_OPTIMIZATION = "algorithm_optimization"
    PIPELINE_ENHANCEMENT = "pipeline_enhancement"
    DECISION_LOGIC_IMPROVEMENT = "decision_logic_improvement"
    PERFORMANCE_TUNING = "performance_tuning"
    ERROR_HANDLING_ENHANCEMENT = "error_handling_enhancement"
    ARCHITECTURE_EVOLUTION = "architecture_evolution"


class MetaDecisionType(Enum):
    """Types of decisions the meta system makes."""
    SHOULD_IMPROVE = "should_improve"
    IMPROVEMENT_STRATEGY = "improvement_strategy"
    ROLLBACK_DECISION = "rollback_decision"
    DEPLOYMENT_DECISION = "deployment_decision"
    TESTING_STRATEGY = "testing_strategy"


@dataclass
class MetaImprovementProposal:
    """A proposal for improving the self-building system."""
    proposal_id: str
    improvement_type: MetaImprovementType
    target_component: str
    description: str
    proposed_changes: Dict[str, Any]
    expected_benefit: str
    risk_assessment: str
    confidence_score: float
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "proposed"  # proposed, testing, approved, rejected, deployed


@dataclass
class MetaABTest:
    """A/B test for self-improvement pipelines."""
    test_id: str
    test_name: str
    control_version: str
    test_versions: List[str]
    test_metrics: List[str]
    test_duration: int  # seconds
    results: Dict[str, Dict[str, float]] = field(default_factory=dict)
    winner: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MetaSelfBuildingOrchestrator:
    """
    The ultimate recursive self-improvement system.
    Uses the system's own agent infrastructure to improve itself.
    """
    
    def __init__(self):
        self.improvement_proposals: Dict[str, MetaImprovementProposal] = {}
        self.active_ab_tests: Dict[str, MetaABTest] = {}
        self.improvement_history: List[Dict[str, Any]] = []
        
        # Meta-system configuration
        self.config = {
            "self_analysis_interval": 3600,  # 1 hour
            "improvement_threshold": 0.15,   # 15% improvement needed
            "max_concurrent_tests": 3,
            "test_duration": 86400,          # 24 hours
            "rollback_threshold": -0.05,     # 5% degradation triggers rollback
            "confidence_threshold": 0.8,     # 80% confidence needed for deployment
        }
        
        # Track system performance before improvements
        self.baseline_metrics: Dict[str, float] = {}
        
        # Statistics
        self.stats = {
            "total_improvements_proposed": 0,
            "total_improvements_deployed": 0,
            "total_rollbacks": 0,
            "average_improvement": 0.0,
            "active_tests": 0,
            "last_self_analysis": None
        }
    
    async def initialize(self):
        """Initialize the meta self-building system."""
        
        try:
            # Register meta-building as a sandboxed plugin in its own system
            await self._register_as_plugin()
            
            # Establish baseline metrics
            await self._establish_baseline_metrics()
            
            # Start continuous self-improvement cycle
            asyncio.create_task(self._continuous_self_improvement())
            
            # Start A/B test manager
            asyncio.create_task(self._ab_test_manager())
            
            logger.info("Meta self-building orchestrator initialized - recursive loop active!")
            
        except Exception as e:
            logger.error(f"Failed to initialize meta orchestrator: {e}")
            raise
    
    async def _register_as_plugin(self):
        """Register the meta-building system as a plugin in its own infrastructure."""
        
        try:
            # Create a skill that represents the meta-building decision logic
            meta_skill_code = await self._generate_meta_decision_skill()
            
            if meta_skill_code:
                # Save as a generated skill
                skill_path = "/home/mr/Dokument/filee.tar/happyos/app/skills/generated/meta_decision_engine.py"
                
                with open(skill_path, 'w', encoding='utf-8') as f:
                    f.write(meta_skill_code)
                
                # Register with the system
                component = ComponentInfo(
                    name="meta_decision_engine",
                    type="skills",
                    path=skill_path,
                    module_name="app.skills.generated.meta_decision_engine",
                    last_modified=datetime.now(),
                    metadata={
                        "auto_generated": True,
                        "meta_system": True,
                        "recursive_self_improvement": True,
                        "decision_types": [dt.value for dt in MetaDecisionType]
                    }
                )
                
                # Register and activate
                await dynamic_registry.register_component(component)
                await dynamic_registry.activate_component("meta_decision_engine")
                
                logger.info("Meta-building system registered as plugin - recursive loop established!")
                
        except Exception as e:
            logger.error(f"Error registering meta-building as plugin: {e}")
    
    async def _generate_meta_decision_skill(self) -> Optional[str]:
        """Generate the meta-decision skill code."""
        
        skill_code = '''"""
Meta Decision Engine - Makes decisions about self-improvement.
This skill is part of the recursive self-improvement loop.
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Execute meta-decision logic for self-improvement.
    
    Args:
        request: Decision request (e.g., "should_improve", "improvement_strategy")
        context: Context including metrics, proposals, etc.
        
    Returns:
        Decision result with reasoning
    """
    if context is None:
        context = {}
    
    try:
        decision_type = context.get("decision_type", "should_improve")
        
        if decision_type == "should_improve":
            return await _decide_should_improve(context)
        elif decision_type == "improvement_strategy":
            return await _decide_improvement_strategy(context)
        elif decision_type == "rollback_decision":
            return await _decide_rollback(context)
        elif decision_type == "deployment_decision":
            return await _decide_deployment(context)
        elif decision_type == "testing_strategy":
            return await _decide_testing_strategy(context)
        else:
            return {
                "success": False,
                "error": f"Unknown decision type: {decision_type}",
                "metadata": {"skill_type": "meta_decision"}
            }
            
    except Exception as e:
        logger.error(f"Meta decision error: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {"skill_type": "meta_decision"}
        }

async def _decide_should_improve(context: Dict[str, Any]) -> Dict[str, Any]:
    """Decide if the system should attempt self-improvement."""
    
    current_metrics = context.get("current_metrics", {})
    baseline_metrics = context.get("baseline_metrics", {})
    recent_changes = context.get("recent_changes", [])
    
    # Decision logic
    should_improve = False
    reasoning = []
    
    # Check performance degradation
    for metric, current_value in current_metrics.items():
        baseline_value = baseline_metrics.get(metric, current_value)
        if baseline_value > 0:
            degradation = (baseline_value - current_value) / baseline_value
            if degradation > 0.1:  # 10% degradation
                should_improve = True
                reasoning.append(f"Performance degradation in {metric}: {degradation:.2%}")
    
    # Check if no improvements in a while
    if not recent_changes:
        should_improve = True
        reasoning.append("No recent improvements - time for optimization")
    
    # Check system complexity
    complexity_score = context.get("complexity_score", 0)
    if complexity_score > 0.8:
        should_improve = True
        reasoning.append("System complexity high - needs simplification")
    
    return {
        "success": True,
        "result": {
            "should_improve": should_improve,
            "confidence": 0.85,
            "reasoning": reasoning
        },
        "metadata": {
            "skill_type": "meta_decision",
            "decision_type": "should_improve",
            "timestamp": datetime.now().isoformat()
        }
    }

async def _decide_improvement_strategy(context: Dict[str, Any]) -> Dict[str, Any]:
    """Decide what improvement strategy to use."""
    
    problem_areas = context.get("problem_areas", [])
    available_strategies = context.get("available_strategies", [])
    
    # Strategy selection logic
    selected_strategy = None
    reasoning = []
    
    if "performance" in problem_areas:
        selected_strategy = "algorithm_optimization"
        reasoning.append("Performance issues detected - optimizing algorithms")
    elif "reliability" in problem_areas:
        selected_strategy = "error_handling_enhancement"
        reasoning.append("Reliability issues - enhancing error handling")
    elif "complexity" in problem_areas:
        selected_strategy = "architecture_evolution"
        reasoning.append("Complexity issues - evolving architecture")
    else:
        selected_strategy = "pipeline_enhancement"
        reasoning.append("General improvement - enhancing pipelines")
    
    return {
        "success": True,
        "result": {
            "strategy": selected_strategy,
            "confidence": 0.75,
            "reasoning": reasoning
        },
        "metadata": {
            "skill_type": "meta_decision",
            "decision_type": "improvement_strategy"
        }
    }

async def _decide_rollback(context: Dict[str, Any]) -> Dict[str, Any]:
    """Decide if a change should be rolled back."""
    
    performance_change = context.get("performance_change", 0)
    error_rate_change = context.get("error_rate_change", 0)
    user_satisfaction_change = context.get("user_satisfaction_change", 0)
    
    should_rollback = False
    reasoning = []
    
    # Rollback criteria
    if performance_change < -0.1:  # 10% performance degradation
        should_rollback = True
        reasoning.append(f"Performance degraded by {abs(performance_change):.2%}")
    
    if error_rate_change > 0.05:  # 5% increase in errors
        should_rollback = True
        reasoning.append(f"Error rate increased by {error_rate_change:.2%}")
    
    if user_satisfaction_change < -0.15:  # 15% drop in satisfaction
        should_rollback = True
        reasoning.append(f"User satisfaction dropped by {abs(user_satisfaction_change):.2%}")
    
    return {
        "success": True,
        "result": {
            "should_rollback": should_rollback,
            "confidence": 0.9,
            "reasoning": reasoning
        },
        "metadata": {
            "skill_type": "meta_decision",
            "decision_type": "rollback_decision"
        }
    }

async def _decide_deployment(context: Dict[str, Any]) -> Dict[str, Any]:
    """Decide if an improvement should be deployed."""
    
    test_results = context.get("test_results", {})
    improvement_score = context.get("improvement_score", 0)
    risk_score = context.get("risk_score", 0)
    
    should_deploy = False
    reasoning = []
    
    # Deployment criteria
    if improvement_score > 0.1 and risk_score < 0.3:
        should_deploy = True
        reasoning.append(f"Good improvement ({improvement_score:.2%}) with low risk ({risk_score:.2%})")
    elif improvement_score > 0.2:  # High improvement overrides moderate risk
        should_deploy = True
        reasoning.append(f"High improvement ({improvement_score:.2%}) justifies deployment")
    else:
        reasoning.append(f"Insufficient improvement ({improvement_score:.2%}) or high risk ({risk_score:.2%})")
    
    return {
        "success": True,
        "result": {
            "should_deploy": should_deploy,
            "confidence": 0.8,
            "reasoning": reasoning
        },
        "metadata": {
            "skill_type": "meta_decision",
            "decision_type": "deployment_decision"
        }
    }

async def _decide_testing_strategy(context: Dict[str, Any]) -> Dict[str, Any]:
    """Decide what testing strategy to use."""
    
    change_scope = context.get("change_scope", "small")
    risk_level = context.get("risk_level", "low")
    
    testing_strategy = {
        "test_duration": 3600,  # 1 hour default
        "test_scope": "limited",
        "rollback_triggers": ["performance_degradation", "error_increase"]
    }
    
    reasoning = []
    
    if change_scope == "large" or risk_level == "high":
        testing_strategy["test_duration"] = 86400  # 24 hours
        testing_strategy["test_scope"] = "comprehensive"
        reasoning.append("Large/risky change requires comprehensive testing")
    elif change_scope == "medium":
        testing_strategy["test_duration"] = 7200  # 2 hours
        testing_strategy["test_scope"] = "moderate"
        reasoning.append("Medium change requires moderate testing")
    else:
        reasoning.append("Small change requires limited testing")
    
    return {
        "success": True,
        "result": {
            "testing_strategy": testing_strategy,
            "confidence": 0.85,
            "reasoning": reasoning
        },
        "metadata": {
            "skill_type": "meta_decision",
            "decision_type": "testing_strategy"
        }
    }
'''
        
        return skill_code
    
    async def _establish_baseline_metrics(self):
        """Establish baseline metrics for the self-building system."""
        
        try:
            # Get current system performance
            system_stats = await self._get_system_performance_metrics()
            
            self.baseline_metrics = {
                "skill_generation_time": system_stats.get("avg_skill_generation_time", 0),
                "skill_success_rate": system_stats.get("skill_success_rate", 0),
                "system_response_time": system_stats.get("avg_response_time", 0),
                "error_rate": system_stats.get("error_rate", 0),
                "component_count": system_stats.get("total_components", 0),
                "optimization_success_rate": system_stats.get("optimization_success_rate", 0)
            }
            
            logger.info(f"Baseline metrics established: {self.baseline_metrics}")
            
        except Exception as e:
            logger.error(f"Error establishing baseline metrics: {e}")
    
    async def _get_system_performance_metrics(self) -> Dict[str, float]:
        """Get current system performance metrics."""
        
        try:
            # Get metrics from various system components
            from ...generators.skill_auto_generator import skill_auto_generator
            from ..optimization.optimization_engine import optimization_engine
            
            generator_stats = skill_auto_generator.get_generation_stats()
            optimization_stats = optimization_engine.get_optimization_stats()
            registry_stats = dynamic_registry.get_registry_stats()
            
            return {
                "avg_skill_generation_time": 30.0,  # Would calculate from actual data
                "skill_success_rate": generator_stats.get("success_rate", 0),
                "avg_response_time": 2.5,  # Would measure actual response times
                "error_rate": 0.05,  # Would calculate from error logs
                "total_components": registry_stats.get("total_registered", 0),
                "optimization_success_rate": optimization_stats.get("optimization_success_rate", 0) / 100
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}
    
    async def _continuous_self_improvement(self):
        """Continuous self-improvement cycle."""
        
        while True:
            try:
                await asyncio.sleep(self.config["self_analysis_interval"])
                
                logger.info("Starting self-improvement cycle...")
                
                # Step 1: Analyze current system state
                analysis_result = await self._analyze_system_state()
                
                # Step 2: Use meta-decision skill to decide if improvement is needed
                should_improve = await self._make_meta_decision(
                    MetaDecisionType.SHOULD_IMPROVE,
                    {
                        "current_metrics": analysis_result["current_metrics"],
                        "baseline_metrics": self.baseline_metrics,
                        "recent_changes": self.improvement_history[-10:],
                        "complexity_score": analysis_result.get("complexity_score", 0)
                    }
                )
                
                if should_improve.get("result", {}).get("should_improve", False):
                    # Step 3: Generate improvement proposals
                    proposals = await self._generate_improvement_proposals(analysis_result)
                    
                    # Step 4: Select best proposal using meta-decision
                    if proposals:
                        best_proposal = await self._select_best_proposal(proposals)
                        
                        if best_proposal:
                            # Step 5: Start A/B test for the improvement
                            await self._start_improvement_ab_test(best_proposal)
                
                self.stats["last_self_analysis"] = datetime.now()
                
            except Exception as e:
                logger.error(f"Error in continuous self-improvement: {e}")
    
    async def _analyze_system_state(self) -> Dict[str, Any]:
        """Analyze the current state of the self-building system."""
        
        try:
            # Get current metrics
            current_metrics = await self._get_system_performance_metrics()
            
            # Analyze trends
            trends = await self._analyze_performance_trends()
            
            # Identify problem areas
            problem_areas = await self._identify_problem_areas(current_metrics)
            
            # Calculate complexity score
            complexity_score = await self._calculate_system_complexity()
            
            return {
                "current_metrics": current_metrics,
                "trends": trends,
                "problem_areas": problem_areas,
                "complexity_score": complexity_score,
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing system state: {e}")
            return {}
    
    async def _make_meta_decision(
        self, 
        decision_type: MetaDecisionType, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make a meta-decision using the meta-decision skill."""
        
        try:
            # Use the system's own skill execution infrastructure
            from app.core.skill_executor import execute_skill
            
            # Prepare context for the meta-decision skill
            decision_context = {
                **context,
                "decision_type": decision_type.value
            }
            
            # Execute the meta-decision skill
            result = await safe_execute(
                execute_skill,
                "meta_decision_engine",
                f"Make decision: {decision_type.value}",
                decision_context
            )
            
            if result and result.get("success"):
                logger.info(f"Meta-decision made: {decision_type.value} -> {result.get('result')}")
                return result
            else:
                logger.error(f"Meta-decision failed: {result}")
                return {"success": False, "error": "Decision failed"}
                
        except Exception as e:
            logger.error(f"Error making meta-decision: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_improvement_proposals(self, analysis_result: Dict[str, Any]) -> List[MetaImprovementProposal]:
        """Generate improvement proposals based on system analysis."""
        
        proposals = []
        
        try:
            problem_areas = analysis_result.get("problem_areas", [])
            current_metrics = analysis_result.get("current_metrics", {})
            
            # Generate proposals for each problem area
            for problem in problem_areas:
                if problem == "performance":
                    proposal = await self._create_performance_improvement_proposal(current_metrics)
                elif problem == "reliability":
                    proposal = await self._create_reliability_improvement_proposal(current_metrics)
                elif problem == "complexity":
                    proposal = await self._create_complexity_reduction_proposal(current_metrics)
                else:
                    proposal = await self._create_general_improvement_proposal(problem, current_metrics)
                
                if proposal:
                    proposals.append(proposal)
                    self.improvement_proposals[proposal.proposal_id] = proposal
                    self.stats["total_improvements_proposed"] += 1
            
            logger.info(f"Generated {len(proposals)} improvement proposals")
            return proposals
            
        except Exception as e:
            logger.error(f"Error generating improvement proposals: {e}")
            return []
    
    async def _create_performance_improvement_proposal(self, metrics: Dict[str, Any]) -> Optional[MetaImprovementProposal]:
        """Create a proposal to improve system performance."""
        
        proposal_id = f"perf_improvement_{int(datetime.now().timestamp())}"
        
        # Use the system's own skill generation to create improvement code
        improvement_request = f"""
        Optimize the self-building system's performance. Current metrics show:
        - Skill generation time: {metrics.get('avg_skill_generation_time', 0)}s
        - System response time: {metrics.get('avg_response_time', 0)}s
        
        Create optimizations for faster skill generation and response times.
        """
        
        # Generate improvement code using the system's own generator
        improvement_component = await auto_generate_skill(
            improvement_request,
            context={"improvement_type": "performance", "target": "self_building_system"}
        )
        
        if improvement_component:
            return MetaImprovementProposal(
                proposal_id=proposal_id,
                improvement_type=MetaImprovementType.PERFORMANCE_TUNING,
                target_component="skill_auto_generator",
                description="Optimize skill generation performance",
                proposed_changes={
                    "new_component": improvement_component.name,
                    "optimization_type": "performance",
                    "expected_speedup": "20-30%"
                },
                expected_benefit="Faster skill generation and system response",
                risk_assessment="Low - performance optimization",
                confidence_score=0.8
            )
        
        return None
    
    async def _create_reliability_improvement_proposal(self, metrics: Dict[str, Any]) -> Optional[MetaImprovementProposal]:
        """Create a proposal to improve system reliability."""
        
        proposal_id = f"reliability_improvement_{int(datetime.now().timestamp())}"
        
        return MetaImprovementProposal(
            proposal_id=proposal_id,
            improvement_type=MetaImprovementType.ERROR_HANDLING_ENHANCEMENT,
            target_component="self_healing_orchestrator",
            description="Enhance error handling and recovery mechanisms",
            proposed_changes={
                "enhanced_error_detection": True,
                "improved_rollback_logic": True,
                "better_pattern_recognition": True
            },
            expected_benefit="Higher system reliability and faster error recovery",
            risk_assessment="Medium - changes to error handling",
            confidence_score=0.75
        )
    
    async def _create_complexity_reduction_proposal(self, metrics: Dict[str, Any]) -> Optional[MetaImprovementProposal]:
        """Create a proposal to reduce system complexity."""
        
        proposal_id = f"complexity_reduction_{int(datetime.now().timestamp())}"
        
        return MetaImprovementProposal(
            proposal_id=proposal_id,
            improvement_type=MetaImprovementType.ARCHITECTURE_EVOLUTION,
            target_component="system_architecture",
            description="Simplify system architecture and reduce complexity",
            proposed_changes={
                "consolidate_modules": True,
                "simplify_interfaces": True,
                "reduce_dependencies": True
            },
            expected_benefit="Easier maintenance and better performance",
            risk_assessment="High - architectural changes",
            confidence_score=0.6
        )
    
    async def _create_general_improvement_proposal(self, problem: str, metrics: Dict[str, Any]) -> Optional[MetaImprovementProposal]:
        """Create a general improvement proposal."""
        
        proposal_id = f"general_improvement_{problem}_{int(datetime.now().timestamp())}"
        
        return MetaImprovementProposal(
            proposal_id=proposal_id,
            improvement_type=MetaImprovementType.PIPELINE_ENHANCEMENT,
            target_component="general_system",
            description=f"General improvement for {problem}",
            proposed_changes={"improvement_area": problem},
            expected_benefit=f"Better {problem} handling",
            risk_assessment="Medium - general improvements",
            confidence_score=0.7
        )
    
    async def _select_best_proposal(self, proposals: List[MetaImprovementProposal]) -> Optional[MetaImprovementProposal]:
        """Select the best improvement proposal using meta-decision logic."""
        
        try:
            # Use meta-decision skill to select best proposal
            decision_context = {
                "proposals": [
                    {
                        "id": p.proposal_id,
                        "type": p.improvement_type.value,
                        "confidence": p.confidence_score,
                        "risk": p.risk_assessment,
                        "benefit": p.expected_benefit
                    }
                    for p in proposals
                ],
                "available_strategies": [p.improvement_type.value for p in proposals]
            }
            
            decision_result = await self._make_meta_decision(
                MetaDecisionType.IMPROVEMENT_STRATEGY,
                decision_context
            )
            
            if decision_result.get("success"):
                selected_strategy = decision_result.get("result", {}).get("strategy")
                
                # Find proposal with matching strategy
                for proposal in proposals:
                    if proposal.improvement_type.value == selected_strategy:
                        logger.info(f"Selected improvement proposal: {proposal.proposal_id}")
                        return proposal
            
            # Fallback: select highest confidence proposal
            return max(proposals, key=lambda p: p.confidence_score)
            
        except Exception as e:
            logger.error(f"Error selecting best proposal: {e}")
            return proposals[0] if proposals else None
    
    async def _start_improvement_ab_test(self, proposal: MetaImprovementProposal):
        """Start an A/B test for an improvement proposal."""
        
        try:
            test_id = f"meta_ab_test_{proposal.proposal_id}"
            
            # Create A/B test
            ab_test = MetaABTest(
                test_id=test_id,
                test_name=f"Test {proposal.improvement_type.value}",
                control_version="current_system",
                test_versions=[f"improved_{proposal.proposal_id}"],
                test_metrics=["performance", "reliability", "user_satisfaction"],
                test_duration=self.config["test_duration"],
                started_at=datetime.now()
            )
            
            self.active_ab_tests[test_id] = ab_test
            self.stats["active_tests"] += 1
            
            # Implement the improvement in test environment
            await self._implement_improvement_for_testing(proposal, test_id)
            
            logger.info(f"Started A/B test for improvement: {test_id}")
            
            # Schedule test completion
            asyncio.create_task(self._complete_ab_test(test_id))
            
        except Exception as e:
            logger.error(f"Error starting A/B test: {e}")
    
    async def _implement_improvement_for_testing(self, proposal: MetaImprovementProposal, test_id: str):
        """Implement an improvement in a test environment."""
        
        try:
            # This would implement the actual improvement
            # For now, simulate implementation
            
            logger.info(f"Implementing improvement for testing: {proposal.proposal_id}")
            
            # Mark proposal as testing
            proposal.status = "testing"
            
            # Log the implementation
            await audit_logger.log_event(
                AuditEventType.COMPONENT_REGISTERED,
                component_name=f"meta_improvement_{proposal.proposal_id}",
                details={
                    "improvement_type": proposal.improvement_type.value,
                    "test_id": test_id,
                    "status": "testing"
                }
            )
            
        except Exception as e:
            logger.error(f"Error implementing improvement for testing: {e}")
    
    async def _ab_test_manager(self):
        """Manage active A/B tests."""
        
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                for test_id, ab_test in list(self.active_ab_tests.items()):
                    try:
                        # Collect test metrics
                        await self._collect_ab_test_metrics(test_id)
                        
                        # Check if test should be stopped early
                        if await self._should_stop_test_early(test_id):
                            await self._complete_ab_test(test_id)
                        
                    except Exception as e:
                        logger.error(f"Error managing A/B test {test_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error in A/B test manager: {e}")
    
    async def _collect_ab_test_metrics(self, test_id: str):
        """Collect metrics for an A/B test."""
        
        try:
            ab_test = self.active_ab_tests.get(test_id)
            if not ab_test:
                return
            
            # Get current system metrics
            current_metrics = await self._get_system_performance_metrics()
            
            # Store metrics for control and test versions
            ab_test.results["control"] = {
                "performance": self.baseline_metrics.get("system_response_time", 0),
                "reliability": self.baseline_metrics.get("skill_success_rate", 0),
                "user_satisfaction": 0.8  # Would measure actual satisfaction
            }
            
            ab_test.results["test"] = {
                "performance": current_metrics.get("avg_response_time", 0),
                "reliability": current_metrics.get("skill_success_rate", 0),
                "user_satisfaction": 0.85  # Would measure actual satisfaction
            }
            
        except Exception as e:
            logger.error(f"Error collecting A/B test metrics: {e}")
    
    async def _should_stop_test_early(self, test_id: str) -> bool:
        """Determine if an A/B test should be stopped early."""
        
        try:
            ab_test = self.active_ab_tests.get(test_id)
            if not ab_test or not ab_test.results:
                return False
            
            # Check for significant degradation
            control_perf = ab_test.results.get("control", {}).get("performance", 0)
            test_perf = ab_test.results.get("test", {}).get("performance", 0)
            
            if control_perf > 0:
                performance_change = (test_perf - control_perf) / control_perf
                
                # Stop if performance degraded significantly
                if performance_change > self.config["rollback_threshold"]:
                    logger.warning(f"Stopping A/B test {test_id} due to performance degradation")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking early stop condition: {e}")
            return False
    
    async def _complete_ab_test(self, test_id: str):
        """Complete an A/B test and make deployment decision."""
        
        try:
            ab_test = self.active_ab_tests.get(test_id)
            if not ab_test:
                return
            
            ab_test.completed_at = datetime.now()
            
            # Analyze results using meta-decision
            deployment_decision = await self._make_meta_decision(
                MetaDecisionType.DEPLOYMENT_DECISION,
                {
                    "test_results": ab_test.results,
                    "improvement_score": self._calculate_improvement_score(ab_test.results),
                    "risk_score": 0.3  # Would calculate actual risk
                }
            )
            
            should_deploy = deployment_decision.get("result", {}).get("should_deploy", False)
            
            if should_deploy:
                # Deploy the improvement
                await self._deploy_improvement(test_id)
                logger.info(f"Deployed improvement from A/B test: {test_id}")
            else:
                # Rollback the test
                await self._rollback_improvement(test_id)
                logger.info(f"Rolled back improvement from A/B test: {test_id}")
            
            # Clean up
            del self.active_ab_tests[test_id]
            self.stats["active_tests"] -= 1
            
        except Exception as e:
            logger.error(f"Error completing A/B test: {e}")
    
    def _calculate_improvement_score(self, results: Dict[str, Dict[str, float]]) -> float:
        """Calculate overall improvement score from A/B test results."""
        
        try:
            control = results.get("control", {})
            test = results.get("test", {})
            
            improvements = []
            
            for metric in ["performance", "reliability", "user_satisfaction"]:
                control_value = control.get(metric, 0)
                test_value = test.get(metric, 0)
                
                if control_value > 0:
                    improvement = (test_value - control_value) / control_value
                    improvements.append(improvement)
            
            return sum(improvements) / len(improvements) if improvements else 0
            
        except Exception as e:
            logger.error(f"Error calculating improvement score: {e}")
            return 0
    
    async def _deploy_improvement(self, test_id: str):
        """Deploy an improvement that passed A/B testing."""
        
        try:
            # Find the associated proposal
            proposal = None
            for p in self.improvement_proposals.values():
                if test_id.endswith(p.proposal_id):
                    proposal = p
                    break
            
            if proposal:
                proposal.status = "deployed"
                self.stats["total_improvements_deployed"] += 1
                
                # Record in improvement history
                self.improvement_history.append({
                    "proposal_id": proposal.proposal_id,
                    "improvement_type": proposal.improvement_type.value,
                    "deployed_at": datetime.now(),
                    "test_id": test_id
                })
                
                # Update baseline metrics
                await self._update_baseline_metrics()
                
                logger.info(f"Successfully deployed improvement: {proposal.proposal_id}")
            
        except Exception as e:
            logger.error(f"Error deploying improvement: {e}")
    
    async def _rollback_improvement(self, test_id: str):
        """Rollback an improvement that failed A/B testing."""
        
        try:
            # Find the associated proposal
            proposal = None
            for p in self.improvement_proposals.values():
                if test_id.endswith(p.proposal_id):
                    proposal = p
                    break
            
            if proposal:
                proposal.status = "rejected"
                self.stats["total_rollbacks"] += 1
                
                logger.info(f"Rolled back improvement: {proposal.proposal_id}")
            
        except Exception as e:
            logger.error(f"Error rolling back improvement: {e}")
    
    async def _update_baseline_metrics(self):
        """Update baseline metrics after successful deployment."""
        
        try:
            new_metrics = await self._get_system_performance_metrics()
            
            # Update baseline with improved metrics
            for metric, value in new_metrics.items():
                if metric in self.baseline_metrics:
                    self.baseline_metrics[metric] = value
            
            logger.info("Updated baseline metrics after successful deployment")
            
        except Exception as e:
            logger.error(f"Error updating baseline metrics: {e}")
    
    async def _analyze_performance_trends(self) -> Dict[str, str]:
        """Analyze performance trends over time."""
        
        # This would analyze historical data
        # For now, return simulated trends
        return {
            "skill_generation": "stable",
            "system_response": "improving",
            "error_rate": "stable",
            "optimization_success": "improving"
        }
    
    async def _identify_problem_areas(self, current_metrics: Dict[str, float]) -> List[str]:
        """Identify areas that need improvement."""
        
        problem_areas = []
        
        # Compare with baseline
        for metric, current_value in current_metrics.items():
            baseline_value = self.baseline_metrics.get(metric, current_value)
            
            if baseline_value > 0:
                change = (current_value - baseline_value) / baseline_value
                
                if change < -0.1:  # 10% degradation
                    if "time" in metric or "response" in metric:
                        problem_areas.append("performance")
                    elif "rate" in metric and "error" in metric:
                        problem_areas.append("reliability")
                    elif "success" in metric:
                        problem_areas.append("reliability")
        
        return list(set(problem_areas))
    
    async def _calculate_system_complexity(self) -> float:
        """Calculate system complexity score."""
        
        try:
            # Get system statistics
            registry_stats = dynamic_registry.get_registry_stats()
            
            # Simple complexity calculation
            component_count = registry_stats.get("total_registered", 0)
            dependency_count = len(getattr(dynamic_registry, 'dependency_graph', {}))
            
            # Normalize to 0-1 scale
            complexity_score = min((component_count + dependency_count) / 1000, 1.0)
            
            return complexity_score
            
        except Exception as e:
            logger.error(f"Error calculating system complexity: {e}")
            return 0.5
    
    def get_meta_stats(self) -> Dict[str, Any]:
        """Get meta-building statistics."""
        
        return {
            **self.stats,
            "baseline_metrics": self.baseline_metrics,
            "active_proposals": len([p for p in self.improvement_proposals.values() if p.status == "proposed"]),
            "testing_proposals": len([p for p in self.improvement_proposals.values() if p.status == "testing"]),
            "deployed_improvements": len([p for p in self.improvement_proposals.values() if p.status == "deployed"]),
            "recent_improvements": self.improvement_history[-5:],
            "system_evolution_rate": len(self.improvement_history) / max(1, (datetime.now() - datetime(2024, 1, 1)).days)
        }


# Global meta orchestrator instance
meta_orchestrator = MetaSelfBuildingOrchestrator()


# Convenience functions
async def initialize_meta_self_building():
    """Initialize the meta self-building system."""
    await meta_orchestrator.initialize()


async def trigger_self_improvement():
    """Manually trigger a self-improvement cycle."""
    analysis = await meta_orchestrator._analyze_system_state()
    proposals = await meta_orchestrator._generate_improvement_proposals(analysis)
    
    if proposals:
        best_proposal = await meta_orchestrator._select_best_proposal(proposals)
        if best_proposal:
            await meta_orchestrator._start_improvement_ab_test(best_proposal)
            return {"success": True, "proposal": best_proposal.proposal_id}
    
    return {"success": False, "message": "No improvements needed"}


def get_meta_building_stats() -> Dict[str, Any]:
    """Get meta-building statistics."""
    return meta_orchestrator.get_meta_stats()