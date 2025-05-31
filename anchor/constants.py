"""Constants used throughout the Anchor application."""

# Agent configuration
DEFAULT_MAX_ITERATIONS = 20
DEFAULT_MODEL = "gpt-4"
DEFAULT_MEMORY_ITEMS = 100
DEFAULT_AGENT_SLEEP = 1  # seconds between iterations

# Git configuration
DEFAULT_BRANCH = "anchor/infra"

# AWS configuration
DEFAULT_AWS_REGION = "us-east-1"
# Services that Terraformer will scan for resources
TERRAFORMER_AWS_SERVICES = [
    "cloudwatch",    # CloudWatch metrics, alarms, dashboards
    "ec2_instance",  # EC2 instances
    "ebs",          # Elastic Block Store volumes
    "ecs",          # Elastic Container Service
    "lambda",       # Lambda functions
    "cloudfront",   # CloudFront distributions
    "api_gateway",  # API Gateway APIs
    "s3",          # S3 buckets
    "eks",         # Elastic Kubernetes Service
    "ecr",         # Elastic Container Registry
    "iam",         # IAM roles, policies, users, and groups
]

# Logging configuration
DEFAULT_LOG_LEVEL = "INFO" 