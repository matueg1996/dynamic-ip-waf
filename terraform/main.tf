provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "ip_manager" {
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "t3.micro"

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              amazon-linux-extras install docker -y
              service docker start
              usermod -a -G docker ec2-user

              curl -L https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
              chmod +x /usr/local/bin/docker-compose

              cd /home/ec2-user
              git clone https://your-repo.git
              cd dynamic-ip-waf

              # Generar archivo .env para la aplicación
              cat <<ENV > .env
              DATABASE_URL=postgresql://admin:password!!-=-@db:5432/ip_manager
              API_KEY=mi-api-key
              WAF_EXPORT_URL=http://api:8000/export
              ENV

              cd docker
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
