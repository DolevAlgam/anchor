FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    awscli \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform
RUN curl -fsSL https://releases.hashicorp.com/terraform/1.5.7/terraform_1.5.7_linux_amd64.zip -o terraform.zip \
    && unzip terraform.zip \
    && mv terraform /usr/local/bin/ \
    && rm terraform.zip

# Install Terraformer
RUN curl -fsSL https://github.com/GoogleCloudPlatform/terraformer/releases/download/0.8.24/terraformer-all-linux-amd64 -o /usr/local/bin/terraformer \
    && chmod +x /usr/local/bin/terraformer

# Create working directory
WORKDIR /app

# Create terraform plugin cache directory
RUN mkdir -p /root/.terraform.d/plugins

# Pre-download AWS provider
RUN mkdir -p /root/.terraform.d/plugins/linux_amd64 && \
    curl -fsSL https://releases.hashicorp.com/terraform-provider-aws/5.99.1/terraform-provider-aws_5.99.1_linux_amd64.zip -o /tmp/aws.zip && \
    unzip /tmp/aws.zip -d /root/.terraform.d/plugins/linux_amd64 && \
    rm /tmp/aws.zip

# Set Python path
ENV PYTHONPATH=/app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (moved to end for better caching)
COPY anchor/ ./anchor/

# Run anchor command
ENTRYPOINT ["/bin/bash", "-c", "python -m anchor.cmd.anchor \"$@\"", "--"] 