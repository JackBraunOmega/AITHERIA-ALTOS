/**
 * AITHERIA ALTOS - Development Environment Configuration
 * 
 * This Terraform configuration sets up the development environment infrastructure
 * for the AITHERIA ALTOS biotechnology SaaS platform.
 * 
 * It includes:
 * - AWS provider configuration
 * - S3 backend for Terraform state
 * - VPC networking using our custom module
 * - Development environment specific variables
 */

# --- Terraform Settings ---
terraform {
  required_version = ">= 1.0.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # S3 backend configuration for storing Terraform state
  # Note: The S3 bucket must be created manually before running terraform init
  backend "s3" {
    bucket         = "aitheria-altos-terraform-state-dev"
    key            = "dev/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "aitheria-altos-terraform-locks-dev" # For state locking
  }
}

# --- Provider Configuration ---
provider "aws" {
  region = local.region
  
  default_tags {
    tags = {
      Project     = "AITHERIA-ALTOS"
      Environment = "dev"
      ManagedBy   = "terraform"
      Owner       = "platform-team"
    }
  }
}

# --- Local Variables ---
locals {
  region            = "us-west-2"
  environment       = "dev"
  vpc_name          = "aitheria-altos-${local.environment}"
  vpc_cidr          = "10.0.0.0/16"
  availability_zones = ["a", "b", "c"]
  
  # Smaller CIDR blocks for dev environment to reduce costs
  public_subnet_cidrs   = ["10.0.0.0/24", "10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs  = ["10.0.10.0/24", "10.0.11.0/24", "10.0.12.0/24"]
  database_subnet_cidrs = ["10.0.20.0/24", "10.0.21.0/24", "10.0.22.0/24"]
  
  # Use single NAT Gateway in dev to reduce costs
  single_nat_gateway = true
  
  tags = {
    Environment = local.environment
    Project     = "AITHERIA-ALTOS"
    ManagedBy   = "terraform"
  }
}

# --- VPC Module ---
module "vpc" {
  source = "../../modules/vpc"
  
  # Pass variables to the VPC module
  vpc_name              = local.vpc_name
  vpc_cidr              = local.vpc_cidr
  region                = local.region
  availability_zones    = local.availability_zones
  public_subnet_cidrs   = local.public_subnet_cidrs
  private_subnet_cidrs  = local.private_subnet_cidrs
  database_subnet_cidrs = local.database_subnet_cidrs
  
  # Dev-specific configurations
  enable_nat_gateway    = true
  single_nat_gateway    = local.single_nat_gateway
  enable_dns_hostnames  = true
  enable_dns_support    = true
  
  tags = local.tags
}

# --- Outputs ---
output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "The CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "List of IDs of public subnets"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "List of IDs of private subnets"
  value       = module.vpc.private_subnet_ids
}

output "database_subnet_ids" {
  description = "List of IDs of database subnets"
  value       = module.vpc.database_subnet_ids
}

output "nat_public_ips" {
  description = "List of public Elastic IPs created for NAT gateways"
  value       = module.vpc.nat_public_ips
}

output "availability_zones" {
  description = "List of availability zones used"
  value       = module.vpc.availability_zones
}
