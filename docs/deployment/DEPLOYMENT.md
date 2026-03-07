Deployment Guide
Overview
This guide covers deploying the AI Creator Automation application to production environments.
Architecture
plain
Copy
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Flutter Web   │────▶│  FastAPI        │────▶│  PostgreSQL     │
│   (Frontend)    │     │  (Backend)      │     │  (Database)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Redis          │
                        │  (Cache/Queue)  │
                        └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Celery Workers │
                        │  (Task Queue)   │
                        └─────────────────┘
Prerequisites
Docker & Docker Compose
Kubernetes cluster (optional)
Domain name
SSL certificate
Cloud provider account (AWS/GCP/Azure)
Environment Setup
1. Clone Repository
bash
Copy
git clone https://github.com/your-org/ai-creator-automation.git
cd ai-creator-automation
2. Configure Environment Variables
bash
Copy
cp backend/.env.example backend/.env
# Edit backend/.env with your production values
3. Configure Firebase
Create a Firebase project
Enable Authentication (Email/Password, Google, Apple)
Download service account key
Set environment variables
4. Configure Stripe
Create Stripe account
Set up subscription plans
Configure webhook endpoint
Add API keys to environment
Docker Deployment
Development
bash
Copy
cd backend
docker-compose up -d
Production
bash
Copy
cd backend
docker-compose -f docker-compose.prod.yml up -d
Kubernetes Deployment
1. Build Images
bash
Copy
# Backend
docker build -t your-registry/ai-creator-backend:latest backend/
docker push your-registry/ai-creator-backend:latest
2. Apply Manifests
bash
Copy
kubectl apply -f infrastructure/kubernetes/
3. Configure Ingress
bash
Copy
kubectl apply -f infrastructure/kubernetes/ingress.yaml
Cloud Deployment
AWS Deployment
ECS/Fargate
Create ECS cluster
Define task definitions
Create services
Configure ALB
bash
Copy
# Using AWS CLI
aws ecs create-cluster --cluster-name ai-creator
aws ecs register-task-definition --cli-input-json file://task-definition.json
aws ecs create-service --cluster ai-creator --service-name backend --task-definition ai-creator-backend
EKS
bash
Copy
# Create EKS cluster
eksctl create cluster --name ai-creator --region us-east-1

# Deploy application
kubectl apply -f infrastructure/kubernetes/
Google Cloud Platform
Cloud Run
bash
Copy
# Deploy backend
gcloud run deploy ai-creator-backend \
  --source backend/ \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
GKE
bash
Copy
# Create GKE cluster
gcloud container clusters create ai-creator \
  --zone us-central1-a \
  --num-nodes 3

# Deploy application
kubectl apply -f infrastructure/kubernetes/
SSL/TLS Configuration
Using Let's Encrypt
bash
Copy
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create cluster issuer
kubectl apply -f infrastructure/kubernetes/cluster-issuer.yaml
Using Custom Certificate
bash
Copy
# Create TLS secret
kubectl create secret tls ai-creator-tls \
  --cert=path/to/cert.pem \
  --key=path/to/key.pem
Monitoring & Logging
Prometheus & Grafana
bash
Copy
# Install Prometheus
kubectl apply -f infrastructure/monitoring/prometheus.yaml

# Install Grafana
kubectl apply -f infrastructure/monitoring/grafana.yaml
Sentry
Add to environment:
env
Copy
SENTRY_DSN=https://your-sentry-dsn
Backup & Recovery
Database Backup
bash
Copy
# Automated backup script
#!/bin/bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
aws s3 cp backup_$(date +%Y%m%d).sql s3://ai-creator-backups/
Disaster Recovery
Regular database backups
Multi-region deployment
Failover configuration
Scaling
Horizontal Scaling
bash
Copy
# Scale backend replicas
kubectl scale deployment backend --replicas=5

# Scale Celery workers
kubectl scale deployment celery-worker --replicas=10
Vertical Scaling
Update resource limits in Kubernetes manifests:
yaml
Copy
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
Security
Network Policies
yaml
Copy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-network-policy
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
Secrets Management
bash
Copy
# Create secrets
kubectl create secret generic backend-secrets \
  --from-env-file=backend/.env
CI/CD Pipeline
GitHub Actions
yaml
Copy
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build and push
        run: |
          docker build -t $REGISTRY/ai-creator:$GITHUB_SHA backend/
          docker push $REGISTRY/ai-creator:$GITHUB_SHA
      
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/backend backend=$REGISTRY/ai-creator:$GITHUB_SHA
Troubleshooting
Common Issues
Database Connection Failed
Check DATABASE_URL
Verify network connectivity
Check firewall rules
Celery Tasks Not Running
Check Redis connection
Verify worker logs
Check task routing
Video Generation Fails
Check AI service credentials
Verify FFmpeg installation
Check storage permissions
Debug Commands
bash
Copy
# Check pod logs
kubectl logs -f deployment/backend

# Exec into container
kubectl exec -it deployment/backend -- /bin/bash

# Check service status
kubectl get services

# Check ingress
kubectl get ingress
Maintenance
Regular Tasks
Update dependencies
Rotate secrets
Clean up old videos
Monitor resource usage
Review logs
Updates
bash
Copy
# Rolling update
kubectl set image deployment/backend backend=ai-creator:v2.0.0

# Rollback
kubectl rollout undo deployment/backend
Support
For deployment support, contact:
Email: devops@aicreator.app
Slack: #deployment-support
