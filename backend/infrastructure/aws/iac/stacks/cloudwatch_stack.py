"""
CloudWatch Stack

Creates CloudWatch metrics, logs, and alarms for monitoring.
"""

from aws_cdk import (
    aws_cloudwatch as cloudwatch,
    aws_logs as logs,
    aws_sns as sns,
    CfnOutput
)
from constructs import Construct

from .base_stack import BaseStack
from ..config.environment_config import EnvironmentConfig


class CloudWatchStack(BaseStack):
    """CloudWatch stack for monitoring and alerting."""
    
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        env_config: EnvironmentConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env_config, **kwargs)
        
        # Create SNS topic for alerts
        self.alert_topic = self._create_alert_topic()
        
        # Create log groups
        self._create_log_groups()
        
        # Create dashboards
        self._create_dashboards()
        
        # Create alarms
        self._create_alarms()
        
        # Create outputs
        self._create_outputs()
    
    def _create_alert_topic(self) -> sns.Topic:
        """Create SNS topic for CloudWatch alarms."""
        
        topic = sns.Topic(
            self,
            "AlertTopic",
            topic_name=self.get_resource_name("alerts"),
            display_name="Infrastructure Recovery Alerts"
        )
        
        return topic
    
    def _create_log_groups(self) -> None:
        """Create CloudWatch log groups."""
        
        # Application log group
        self.app_log_group = logs.LogGroup(
            self,
            "ApplicationLogGroup",
            log_group_name=f"/aws/lambda/{self.get_resource_name('app')}",
            retention=logs.RetentionDays.ONE_MONTH if self.env_config.environment == "dev" else logs.RetentionDays.THREE_MONTHS
        )
        
        # API Gateway log group
        self.api_log_group = logs.LogGroup(
            self,
            "ApiGatewayLogGroup",
            log_group_name=f"/aws/apigateway/{self.get_resource_name('api')}",
            retention=logs.RetentionDays.ONE_WEEK if self.env_config.environment == "dev" else logs.RetentionDays.ONE_MONTH
        )
        
        # Circuit breaker log group
        self.circuit_breaker_log_group = logs.LogGroup(
            self,
            "CircuitBreakerLogGroup",
            log_group_name=f"/aws/lambda/{self.get_resource_name('circuit-breaker')}",
            retention=logs.RetentionDays.ONE_MONTH
        )
    
    def _create_dashboards(self) -> None:
        """Create CloudWatch dashboards."""
        
        self.dashboard = cloudwatch.Dashboard(
            self,
            "InfraRecoveryDashboard",
            dashboard_name=self.get_resource_name("dashboard")
        )
        
        # Add widgets for key metrics
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lambda Function Invocations",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Invocations",
                        statistic="Sum"
                    )
                ]
            ),
            cloudwatch.GraphWidget(
                title="API Gateway Requests",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/ApiGateway",
                        metric_name="Count",
                        statistic="Sum"
                    )
                ]
            )
        )
    
    def _create_alarms(self) -> None:
        """Create CloudWatch alarms."""
        
        # Lambda error rate alarm
        lambda_error_alarm = cloudwatch.Alarm(
            self,
            "LambdaErrorAlarm",
            alarm_name=self.get_resource_name("lambda-errors"),
            alarm_description="Lambda function error rate is too high",
            metric=cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name="Errors",
                statistic="Sum"
            ),
            threshold=10,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        
        lambda_error_alarm.add_alarm_action(
            cloudwatch.SnsAction(self.alert_topic)
        )
        
        # API Gateway 4xx error alarm
        api_4xx_alarm = cloudwatch.Alarm(
            self,
            "Api4xxAlarm",
            alarm_name=self.get_resource_name("api-4xx-errors"),
            alarm_description="API Gateway 4xx error rate is too high",
            metric=cloudwatch.Metric(
                namespace="AWS/ApiGateway",
                metric_name="4XXError",
                statistic="Sum"
            ),
            threshold=50,
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        
        api_4xx_alarm.add_alarm_action(
            cloudwatch.SnsAction(self.alert_topic)
        )
    
    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        
        self.create_output(
            "AlertTopicArn",
            value=self.alert_topic.topic_arn,
            description="SNS topic ARN for alerts"
        )
        
        self.create_output(
            "DashboardUrl",
            value=f"https://console.aws.amazon.com/cloudwatch/home?region={self.env_config.aws_region}#dashboards:name={self.dashboard.dashboard_name}",
            description="CloudWatch dashboard URL"
        )