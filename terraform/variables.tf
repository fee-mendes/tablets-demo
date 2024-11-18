variable "unique_identifier" {
  description = "A unique identifier for the table demo deployment. This is commonly your initials or something unique to identify your deployment in AWS console."
  type        = string
}

variable "use_spot_instances" {
  description = "Whether to use spot instances for the instances"
  type        = string
  default     = "no"
  validation {
    condition = var.use_spot_instances == "yes" || var.use_spot_instances == "no"
    error_message = "The value of use_spot_instances must be either 'yes' or 'no'."
  }
}

variable "aws_profile" {
  description = "AWS credentials profile to use for authentication."
  default     = "default"
}

variable "aws_region" {
  description = "AWS region to deploy resources."
  default     = "us-east-2" # Change to your preferred region, or override when applying
}

variable "scylla_instance_type" {
  description = "Instance type for ScyllaDB nodes."
  default     = "i4i.8xlarge"
}

variable "loader_instance_type" {
  description = "Instance type for loader nodes."
  default     = "c7i.8xlarge"
}
