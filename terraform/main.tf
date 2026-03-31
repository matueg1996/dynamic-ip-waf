# Configuración de infraestructura en AWS.
variable "region" { default = "us-east-1" }
variable "instance_type" { default = "t3.micro" }
variable "ami_id" { default = "ami-0c02fb55956c7d316" }
variable "github_repo" { default = "https://github.com/matueg1996/dynamic-ip-waf.git" }

provider "aws" {
  region = var.region
}

resource "aws_instance" "ip_manager" {
  ami           = var.ami_id
  instance_type = var.instance_type
  vpc_security_group_ids = [aws_security_group.allow_api.id]

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              amazon-linux-extras install docker -y
              service docker start
              usermod -a -G docker ec2-user

              curl -L https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
              chmod +x /usr/local/bin/docker-compose

              cd /home/ec2-user
              git clone ${var.github_repo}
              cd dynamic-ip-waf/docker
              docker-compose up -d
              EOF
}

resource "aws_api_gateway_rest_api" "api" {
  name = "ip-manager-api"
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "method" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "integration" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.method.http_method

  type = "HTTP_PROXY"
  integration_http_method = "ANY"
  uri = "http://${aws_instance.ip_manager.public_ip}:8000/{proxy}"
}

resource "aws_api_gateway_deployment" "deploy" {
  depends_on = [aws_api_gateway_integration.integration]
  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = "prod"
}

resource "aws_api_gateway_api_key" "key" {
  name = "ip-manager-key"
}

resource "aws_api_gateway_usage_plan" "plan" {
  name = "ip-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.api.id
    stage  = aws_api_gateway_deployment.deploy.stage_name
  }
}

resource "aws_api_gateway_usage_plan_key" "attach" {
  key_id        = aws_api_gateway_api_key.key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.plan.id
}

resource "aws_security_group" "allow_api" {
  name        = "allow_api_traffic"
  description = "Permite trafico al puerto 8000 para el IP Manager"

  ingress {
    description      = "API Port"
    from_port        = 8000
    to_port          = 8000
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
  }

  ingress {
    description      = "SSH"
    from_port        = 22
    to_port          = 22
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
  }
}
