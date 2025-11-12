# Azure PostgreSQL Docker Deployment Guide

This guide covers building and deploying the RAG API with Azure PostgreSQL using Docker.

---

## Overview

The Azure-specific Docker setup includes:
- **Dockerfile.azure**: Optimized image using `requirements-azure-core.txt`
- **docker-compose.azure.yml**: Docker Compose configuration for Azure
- **.env.azure.example**: Environment variable template

### Key Features

- ✓ Python 3.10-slim base image (smaller footprint)
- ✓ Only Azure PostgreSQL dependencies installed
- ✓ Conditional imports automatically use Azure PGVector when installed
- ✓ Optimized for Azure PostgreSQL Flexible Server
- ✓ No unnecessary dependencies (unstructured, MongoDB, etc.)

---

## Quick Start

### 1. Prerequisites

**Azure Resources Required:**
- Azure PostgreSQL Flexible Server with pgvector extension enabled
- Connection string or credentials
- Firewall rules configured
- (Optional) Azure OpenAI or OpenAI API key

**Local Requirements:**
- Docker installed
- Docker Compose installed (if using docker-compose)

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.azure.example .env.azure

# Edit with your Azure PostgreSQL credentials
nano .env.azure  # or use your preferred editor
```

**Minimum required variables:**
```env
# Connection string (option 1)
AZURE_POSTGRESQL_DSN=postgresql://user@server:pass@server.postgres.database.azure.com:5432/db?sslmode=require

# OR individual parameters (option 2)
AZURE_DB_HOST=your-server.postgres.database.azure.com
AZURE_DB_PORT=5432
AZURE_DB_NAME=rag_db
AZURE_DB_USER=your_username@your-server
AZURE_DB_PASSWORD=your_password

# Embedding provider
OPENAI_API_KEY=sk-...
```

### 3. Build the Image

```bash
# Build the Azure-specific image
docker build -f Dockerfile.azure -t rag-api-azure:latest .
```

### 4. Run with Docker

```bash
# Run the container
docker run -d \
  --name rag-api-azure \
  -p 8000:8000 \
  --env-file .env.azure \
  rag-api-azure:latest
```

### 5. OR Run with Docker Compose

```bash
# Using docker-compose
docker-compose -f docker-compose.azure.yml up -d

# View logs
docker-compose -f docker-compose.azure.yml logs -f

# Stop
docker-compose -f docker-compose.azure.yml down
```

---

## Image Details

### Base Image
```dockerfile
FROM python:3.10-slim
```

**Why 3.10-slim?**
- Compatible with all dependencies
- Smaller image size (~150MB vs ~900MB for full python:3.10)
- Faster build and deployment times
- Adequate for production workloads

### Installed Dependencies

**System packages:**
- `pandoc` - Document conversion
- `netcat-openbsd` - Health checks

**Python packages:**
From `requirements-azure-core.txt`:
- langchain-azure-postgresql==0.3.0
- langchain-openai==0.3.10
- langchain-core==0.3.79
- sentence_transformers==3.1.1
- fastapi==0.115.12
- All document processing libraries

### Environment Variables

**Set in Dockerfile:**
```dockerfile
ENV PGVECTOR_CREATE_EXTENSION=false
ENV SCARF_NO_ANALYTICS=true
```

**Configurable via .env.azure:**
- Database connection parameters
- API keys
- Application settings
- Logging configuration

---

## Building for Different Architectures

### AMD64 (x86_64) - Default
```bash
docker build -f Dockerfile.azure -t rag-api-azure:latest .
```

### ARM64 (Apple Silicon, ARM servers)
```bash
docker build -f Dockerfile.azure --platform linux/arm64 -t rag-api-azure:arm64 .
```

### Multi-architecture Build
```bash
# Create a builder
docker buildx create --name azure-builder --use

# Build for multiple architectures
docker buildx build -f Dockerfile.azure \
  --platform linux/amd64,linux/arm64 \
  -t rag-api-azure:latest \
  --push \
  .
```

---

## Deployment Scenarios

### 1. Azure Container Instances (ACI)

```bash
# Login to Azure
az login

# Create resource group (if needed)
az group create --name rag-api-rg --location eastus

# Push image to Azure Container Registry
az acr build --registry <your-acr> --image rag-api-azure:latest -f Dockerfile.azure .

# Deploy to ACI
az container create \
  --resource-group rag-api-rg \
  --name rag-api-azure \
  --image <your-acr>.azurecr.io/rag-api-azure:latest \
  --dns-name-label rag-api-unique \
  --ports 8000 \
  --environment-variables \
    PGVECTOR_CREATE_EXTENSION=false \
  --secure-environment-variables \
    AZURE_POSTGRESQL_DSN='<connection-string>' \
    OPENAI_API_KEY='<api-key>' \
  --cpu 2 \
  --memory 4
```

### 2. Azure Container Apps

```bash
# Create Container Apps environment
az containerapp env create \
  --name rag-api-env \
  --resource-group rag-api-rg \
  --location eastus

# Deploy container app
az containerapp create \
  --name rag-api \
  --resource-group rag-api-rg \
  --environment rag-api-env \
  --image <your-acr>.azurecr.io/rag-api-azure:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 10 \
  --cpu 2 \
  --memory 4Gi \
  --env-vars \
    PGVECTOR_CREATE_EXTENSION=false \
  --secrets \
    db-connection-string='<connection-string>' \
    openai-key='<api-key>'
```

### 3. Azure Kubernetes Service (AKS)

Create `k8s-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-api-azure
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rag-api
  template:
    metadata:
      labels:
        app: rag-api
    spec:
      containers:
      - name: rag-api
        image: <your-acr>.azurecr.io/rag-api-azure:latest
        ports:
        - containerPort: 8000
        env:
        - name: PGVECTOR_CREATE_EXTENSION
          value: "false"
        - name: AZURE_POSTGRESQL_DSN
          valueFrom:
            secretKeyRef:
              name: db-secrets
              key: connection-string
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: openai-key
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 40
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 20
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: rag-api-service
spec:
  selector:
    app: rag-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

Deploy:
```bash
kubectl apply -f k8s-deployment.yaml
```

### 4. Local Development

```bash
# Build and run locally with live reload
docker-compose -f docker-compose.azure.yml up --build

# Or run in detached mode
docker-compose -f docker-compose.azure.yml up -d

# View logs
docker-compose -f docker-compose.azure.yml logs -f rag-api-azure

# Stop
docker-compose -f docker-compose.azure.yml down
```

---

## Testing the Deployment

### Health Check
```bash
curl http://localhost:8000/health
```

### API Documentation
```bash
# Open in browser
http://localhost:8000/docs
```

### Test Upload
```bash
curl -X POST http://localhost:8000/api/documents \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test.pdf"
```

### Test Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this about?"}'
```

---

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker logs rag-api-azure
```

**Common issues:**
1. **Missing environment variables**
   - Verify .env.azure is correctly configured
   - Check all required variables are set

2. **Database connection failure**
   - Verify Azure PostgreSQL firewall rules
   - Check connection string format
   - Ensure SSL is enabled: `?sslmode=require`

3. **Extension not found**
   - Ensure pgvector is enabled in Azure Portal
   - Run: `CREATE EXTENSION IF NOT EXISTS vector;`

### Import Errors

If you see module import errors:
```bash
# Rebuild the image
docker build -f Dockerfile.azure -t rag-api-azure:latest --no-cache .
```

### Connection Timeouts

Azure PostgreSQL requires specific connection settings:
```env
# Ensure SSL is enabled
AZURE_POSTGRESQL_DSN=postgresql://user:pass@host:5432/db?sslmode=require

# Or set individually
DB_SSLMODE=require
```

### Performance Issues

**Increase resources:**
```yaml
# In docker-compose.azure.yml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 4G
```

---

## Image Size Optimization

Current image size: ~800MB-1.2GB (depends on PyTorch inclusion)

### Further Optimization

**Remove PyTorch** (if not using sentence_transformers):
Edit `requirements-azure-core.txt` and remove:
```txt
sentence_transformers==3.1.1
torch>=1.11.0
```

This reduces image to ~300-400MB.

**Use multi-stage build** (advanced):
```dockerfile
FROM python:3.10-slim AS builder
# ... build dependencies ...

FROM python:3.10-slim
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Deploy Azure Image

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2

    - name: Login to Azure Container Registry
      uses: azure/docker-login@v1
      with:
        login-server: ${{ secrets.ACR_LOGIN_SERVER }}
        username: ${{ secrets.ACR_USERNAME }}
        password: ${{ secrets.ACR_PASSWORD }}

    - name: Build and push
      run: |
        docker build -f Dockerfile.azure -t ${{ secrets.ACR_LOGIN_SERVER }}/rag-api-azure:${{ github.sha }} .
        docker push ${{ secrets.ACR_LOGIN_SERVER }}/rag-api-azure:${{ github.sha }}
```

### Azure DevOps Pipeline

```yaml
trigger:
- main

pool:
  vmImage: 'ubuntu-latest'

variables:
  dockerRegistryServiceConnection: 'azure-acr'
  imageRepository: 'rag-api-azure'
  containerRegistry: 'youracr.azurecr.io'
  dockerfilePath: '$(Build.SourcesDirectory)/Dockerfile.azure'
  tag: '$(Build.BuildId)'

stages:
- stage: Build
  displayName: Build and push Docker image
  jobs:
  - job: Build
    displayName: Build
    steps:
    - task: Docker@2
      displayName: Build and push image
      inputs:
        command: buildAndPush
        repository: $(imageRepository)
        dockerfile: $(dockerfilePath)
        containerRegistry: $(dockerRegistryServiceConnection)
        tags: |
          $(tag)
          latest
```

---

## Monitoring

### Container Logs
```bash
# Real-time logs
docker logs -f rag-api-azure

# Last 100 lines
docker logs --tail 100 rag-api-azure
```

### Resource Usage
```bash
# Monitor resources
docker stats rag-api-azure
```

### Azure Monitor Integration

Add to your code:
```python
from opencensus.ext.azure.log_exporter import AzureLogHandler

logger.addHandler(AzureLogHandler(
    connection_string=os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
))
```

---

## Security Best Practices

1. **Never commit secrets**
   - Use .env files (gitignored)
   - Use Azure Key Vault for production

2. **Use minimal base image**
   - We use python:3.10-slim (not full python:3.10)

3. **Run as non-root** (add to Dockerfile):
   ```dockerfile
   RUN useradd -m -u 1000 appuser
   USER appuser
   ```

4. **Scan for vulnerabilities**:
   ```bash
   docker scan rag-api-azure:latest
   ```

5. **Keep dependencies updated**:
   ```bash
   pip list --outdated
   ```

---

## Comparison with Other Dockerfiles

| Feature | Dockerfile | Dockerfile.lite | Dockerfile.azure |
|---------|-----------|----------------|------------------|
| Base Image | python:3.10 | python:3.10-slim | python:3.10-slim |
| Size | ~1.5GB | ~1.2GB | ~800MB-1.2GB |
| Dependencies | All | Lite | Azure-only |
| Vector Stores | All | All | Azure PGVector only |
| OpenCV | ✓ | ✓ | ✗ |
| MongoDB | ✓ | ✓ | ✗ |
| Unstructured | ✓ | ✓ | ✗ |
| Build Time | ~15min | ~10min | ~8min |

---

## Next Steps

1. **Test locally** with docker-compose
2. **Push to Azure Container Registry**
3. **Deploy to your preferred Azure service** (ACI, ACA, or AKS)
4. **Set up monitoring** and alerts
5. **Configure auto-scaling** based on load

---

## Support

- **Dockerfile**: [Dockerfile.azure](Dockerfile.azure)
- **Compose File**: [docker-compose.azure.yml](docker-compose.azure.yml)
- **Environment Template**: [.env.azure.example](.env.azure.example)
- **Installation Guide**: [AZURE_INSTALLATION_SUCCESS.md](AZURE_INSTALLATION_SUCCESS.md)

---

**Created**: 2025-11-12
**Purpose**: Optimized Docker deployment for Azure PostgreSQL RAG API
