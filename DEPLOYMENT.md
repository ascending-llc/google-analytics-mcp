# Google Analytics MCP Server - Deployment Guide

This guide covers deploying the Google Analytics MCP server as a container in Jarvis environments.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Google Cloud Setup](#google-cloud-setup)
- [AWS Setup](#aws-setup)
- [Local Testing](#local-testing)
- [Jarvis Integration](#jarvis-integration)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Deployment Model
- **Target Environment**: Client AWS accounts (EKS cluster)
- **Image Location**: SAAS ECR `897729109735.dkr.ecr.us-east-1.amazonaws.com/jarvis/ga_mcp_server`
- **Authentication**: Google service account credentials via AWS Secrets Manager
- **Port**: 3334 (HTTP transport)
- **Service Name**: `google-analytics-mcp`

### Authentication Flow
```
Google Service Account JSON
  ↓
AWS Secrets Manager (client account)
  ↓
External Secrets Operator
  ↓
Kubernetes Secret
  ↓
Volume Mount → /app/credentials/credentials.json
  ↓
Google Client Libraries (auto-detect via GOOGLE_APPLICATION_CREDENTIALS)
```

---

## Prerequisites

### Required Access
- Google Cloud Console access (to create service account)
- Access to all dealer GA4 properties
- AWS account access (to store credentials in Secrets Manager)
- GitHub repository access (to run CI workflow)

### Tools
- `gcloud` CLI (optional, for GCP management)
- `aws` CLI (for Secrets Manager operations)
- `kubectl` (for Kubernetes troubleshooting)
- Docker (for local testing)

---

## Google Cloud Setup

### 1. Create Google Cloud Project (if needed)

If you don't have a GCP project for managing service accounts:

```bash
gcloud projects create jarvis-analytics-access --name="Jarvis Analytics Access"
gcloud config set project jarvis-analytics-access
```

### 2. Enable Required APIs

```bash
gcloud services enable analyticsdata.googleapis.com
gcloud services enable analyticsadmin.googleapis.com
```

### 3. Create Service Account

```bash
# Create service account
gcloud iam service-accounts create jarvis-analytics-mcp \
  --display-name="Jarvis Google Analytics MCP Server" \
  --description="Service account for Jarvis to query Google Analytics"

# Get service account email
SA_EMAIL=$(gcloud iam service-accounts list \
  --filter="displayName:'Jarvis Google Analytics MCP Server'" \
  --format="value(email)")

echo "Service Account Email: $SA_EMAIL"
```

### 4. Download Service Account Key

```bash
gcloud iam service-accounts keys create ~/jarvis-ga-credentials.json \
  --iam-account=$SA_EMAIL

# Verify the key file
cat ~/jarvis-ga-credentials.json | jq .
```

⚠️ **Security Note**: Store this file securely. It will be uploaded to AWS Secrets Manager and should not be committed to version control.

### 5. Grant GA4 Property Access

#### Option A: Organization-Level Access (Recommended)
If all dealer properties are under a single Google Analytics account:

1. Go to [Google Analytics Admin](https://analytics.google.com/analytics/web/#/admin)
2. Select the parent account
3. Navigate to **Account Access Management**
4. Click **Add users** (+ icon)
5. Enter the service account email: `$SA_EMAIL`
6. Grant **Viewer** role
7. Click **Add**

This grants access to the Rollup property and all individual dealer properties.

#### Option B: Per-Property Access
If properties need individual access grants:

```bash
# Repeat for each property ID
PROPERTY_ID="123456789"

# Note: This requires manual steps in the GA4 UI per property
# 1. Go to Admin → Property → Property Access Management
# 2. Add the service account email with Viewer role
```

### 6. Verify Access

Test that the service account can access properties:

```bash
# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS=~/jarvis-ga-credentials.json

# Test with gcloud
gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS

# Test with Python (requires google-analytics-admin package)
python3 << EOF
from google.analytics.admin_v1beta import AnalyticsAdminServiceClient

client = AnalyticsAdminServiceClient()
accounts = list(client.list_account_summaries())
print(f"Accessible accounts: {len(accounts)}")
for account in accounts:
    print(f"  - {account.account}")
    print(f"    Properties: {len(account.property_summaries)}")
EOF
```

---

## AWS Setup

### 1. Create ECR Repository (One-Time, SAAS Account)

**Account**: `897729109735` (SAAS)
**Region**: `us-east-1`

```bash
# Switch to SAAS AWS profile
export AWS_PROFILE=saas

# Create ECR repository
aws ecr create-repository \
  --repository-name jarvis/ga_mcp_server \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true

# Enable tag immutability (optional)
aws ecr put-lifecycle-policy \
  --repository-name jarvis/ga_mcp_server \
  --lifecycle-policy-text '{
    "rules": [{
      "rulePriority": 1,
      "description": "Keep last 10 images",
      "selection": {
        "tagStatus": "any",
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": { "type": "expire" }
    }]
  }'
```

### 2. Grant Client ECR Pull Access

For each client account that needs to deploy this MCP server:

```bash
CLIENT_ACCOUNT_ID="123456789012"  # Replace with client AWS account ID

# Get current policy
aws ecr get-repository-policy \
  --repository-name jarvis/ga_mcp_server \
  --region us-east-1 > policy.json

# Edit policy.json to add client account pull permissions
# Or set a new policy:
cat > ecr-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPullFromClientAccounts",
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::${CLIENT_ACCOUNT_ID}:root"
        ]
      },
      "Action": [
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ]
    }
  ]
}
EOF

aws ecr set-repository-policy \
  --repository-name jarvis/ga_mcp_server \
  --policy-text file://ecr-policy.json
```

### 3. Store Credentials in AWS Secrets Manager (Per Client)

**Account**: Client AWS account
**Region**: Same as EKS cluster

```bash
# Switch to client AWS profile
export AWS_PROFILE=client-profile

# Store the Google service account JSON in Secrets Manager
aws secretsmanager create-secret \
  --name "jarvis/google-analytics-credentials" \
  --description "Google Analytics service account credentials for Jarvis MCP" \
  --secret-string file://~/jarvis-ga-credentials.json \
  --region us-east-1

# Verify secret was created
aws secretsmanager describe-secret \
  --secret-id "jarvis/google-analytics-credentials" \
  --region us-east-1
```

⚠️ **Security**: The secret is encrypted at rest with AWS KMS. Access is controlled via IAM roles.

### 4. Grant Jarvis IAM Role Access to Secret

This is typically handled by Terraform in `jarvis-deployment`, but for manual setup:

```bash
# Get the Jarvis service account IAM role ARN
JARVIS_ROLE_ARN=$(kubectl get sa jarvis-service-account -n jarvis -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}')

# Update IAM policy to allow access to the secret
aws iam put-role-policy \
  --role-name $(echo $JARVIS_ROLE_ARN | awk -F'/' '{print $NF}') \
  --policy-name GoogleAnalyticsMCPSecretAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:jarvis/google-analytics-credentials*"
    }]
  }'
```

---

## Local Testing

### 1. Build Docker Image

```bash
cd /path/to/google-analytics-mcp

# Build the image
docker build -t ga-mcp-test .
```

### 2. Run Container Locally

```bash
# Run with mounted credentials
docker run -it --rm \
  -v ~/jarvis-ga-credentials.json:/app/credentials/credentials.json:ro \
  -p 3334:3334 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/credentials.json \
  -e ANALYTICS_MCP_HOST=0.0.0.0 \
  -e ANALYTICS_MCP_PORT=3334 \
  ga-mcp-test
```

### 3. Test MCP Endpoint

In another terminal:

```bash
# Test health/info endpoint
curl http://localhost:3334/mcp

# Expected response: JSON with MCP server info
```

### 4. Test with MCP Inspector (Optional)

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Connect to local server
mcp-inspector http://localhost:3334/mcp
```

---

## Jarvis Integration

### 1. Build and Push Image to ECR

Trigger the GitHub Actions workflow:

1. Go to repository **Actions** tab
2. Select **"Build and Push Google Analytics MCP to ECR Registry"**
3. Click **"Run workflow"**
4. Set region: `us-east-1`
5. Optional: Set release version (e.g., `0.1.0`)
6. Click **"Run workflow"**

This will:
- Build multi-arch image (amd64 + arm64)
- Push to `897729109735.dkr.ecr.us-east-1.amazonaws.com/jarvis/ga_mcp_server`
- Tag with `latest`, commit SHA, and optional version

### 2. Update Jarvis Helm Values

In the `jarvis-deployment` repository, edit the client's values file:

**File**: `clients/terraform/clients_values/<client>/<client>_values.yaml`

Add to `mcpConfigs`:

```yaml
mcpConfigs:
  # ... existing MCP servers ...

  - name: google-analytics-mcp
    enabled: true
    replicaCount: 1
    image:
      repository: 897729109735.dkr.ecr.us-east-1.amazonaws.com/jarvis/ga_mcp_server
      tag: latest  # Or specific version like "0.1.0" or commit SHA
      pullPolicy: Always
    service:
      port: 3334
      type: ClusterIP
    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "512Mi"
        cpu: "500m"
```

Add ExternalSecret configuration:

```yaml
googleAnalyticsMcp:
  enabled: true
  credentials:
    refreshInterval: 1h
    secretStoreRef:
      name: secretstore-jarvis
      kind: SecretStore
    targetSecretName: google-analytics-credentials
    remoteRef: jarvis/google-analytics-credentials  # AWS Secrets Manager key
```

### 3. Update Helm Chart Templates

**Note**: These changes are made in `jarvis-deployment/charts/jarvis/templates/`, not this repo.

#### Create ExternalSecret Template
**File**: `charts/jarvis/templates/google_analytics_mcp_externalsecret.yaml`

```yaml
{{- if .Values.googleAnalyticsMcp.enabled }}
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: google-analytics-credentials
  labels:
    {{- include "ascending-jarvis.labels" . | nindent 4 }}
spec:
  refreshInterval: {{ .Values.googleAnalyticsMcp.credentials.refreshInterval | default "1h" }}
  secretStoreRef:
    name: {{ .Values.googleAnalyticsMcp.credentials.secretStoreRef.name | default "secretstore-jarvis" }}
    kind: {{ .Values.googleAnalyticsMcp.credentials.secretStoreRef.kind | default "SecretStore" }}
  target:
    name: {{ .Values.googleAnalyticsMcp.credentials.targetSecretName | default "google-analytics-credentials" }}
    creationPolicy: Owner
  data:
    - secretKey: credentials.json
      remoteRef:
        key: {{ .Values.googleAnalyticsMcp.credentials.remoteRef }}
{{- end }}
```

#### Update MCP Server Template
**File**: `charts/jarvis/templates/mcp_server.yaml`

Add volume mount for Google Analytics MCP:

```yaml
{{- range .Values.mcpConfigs }}
{{- if .enabled }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .name }}
  # ... existing metadata ...
spec:
  # ... existing spec ...
  template:
    spec:
      containers:
        - name: {{ .name }}
          image: "{{ .image.repository }}:{{ .image.tag }}"
          envFrom:
            - secretRef:
                name: jarvis-env
          {{- if eq .name "google-analytics-mcp" }}
          volumeMounts:
            - name: google-analytics-credentials
              mountPath: /app/credentials/credentials.json
              subPath: credentials.json
              readOnly: true
          env:
            - name: GOOGLE_APPLICATION_CREDENTIALS
              value: /app/credentials/credentials.json
          {{- end }}
          # ... rest of container spec ...
      {{- if eq .name "google-analytics-mcp" }}
      volumes:
        - name: google-analytics-credentials
          secret:
            secretName: google-analytics-credentials
            defaultMode: 0400
      {{- end }}
{{- end }}
{{- end }}
```

### 4. Deploy with Terraform

```bash
cd jarvis-deployment/clients/terraform

# Switch to client AWS account
export AWS_PROFILE=client-profile

# Initialize if needed
terraform init -backend-config=clients_values/<client>/backend.hcl

# Plan changes
terraform plan -var-file=clients_values/<client>/<client>.tfvars

# Apply changes
terraform apply -var-file=clients_values/<client>/<client>.tfvars
```

### 5. Verify Deployment

```bash
# Update kubeconfig
aws eks update-kubeconfig --name <cluster-name> --region <region>

# Check pod status
kubectl get pods -l app=google-analytics-mcp -n <namespace>

# Check pod logs
kubectl logs -l app=google-analytics-mcp -n <namespace> --tail=50

# Verify credentials are mounted
kubectl exec -it <pod-name> -n <namespace> -- ls -la /app/credentials/

# Check service
kubectl get svc google-analytics-mcp -n <namespace>

# Test endpoint from within cluster
kubectl run curl-test --image=curlimages/curl -it --rm -- \
  curl http://google-analytics-mcp:3334/mcp
```

### 6. Configure in Jarvis UI

1. Log in to Jarvis
2. Navigate to **Connections** page
3. Enable **Google Analytics MCP** toggle
4. Test with a query:
   ```
   "Show me total sessions from the last 7 days for property 123456789"
   ```

---

## Troubleshooting

### Container Fails to Start

**Check logs**:
```bash
kubectl logs -l app=google-analytics-mcp -n <namespace>
```

**Common issues**:
- Missing credentials file → Verify ExternalSecret created K8s secret
- Invalid JSON in credentials → Validate JSON format in AWS Secrets Manager
- Port conflicts → Ensure port 3334 is available (should be unique per service)

### Authentication Errors

**Symptom**: `google.auth.exceptions.DefaultCredentialsError`

**Check**:
1. Verify GOOGLE_APPLICATION_CREDENTIALS env var is set:
   ```bash
   kubectl exec -it <pod-name> -- env | grep GOOGLE_APPLICATION_CREDENTIALS
   ```

2. Verify credentials file exists and is readable:
   ```bash
   kubectl exec -it <pod-name> -- cat /app/credentials/credentials.json
   ```

3. Verify service account has GA4 property access:
   - Check Google Analytics Admin → Property Access Management
   - Ensure service account email is listed with Viewer role

### Permission Denied Errors

**Symptom**: `403 Forbidden` or `permission denied` when querying GA4

**Resolution**:
1. Verify service account has access to the specific property
2. Check that the property ID is correct (format: `properties/123456789`)
3. Ensure required APIs are enabled in GCP project:
   ```bash
   gcloud services list --enabled | grep analytics
   ```

### External Secrets Operator Issues

**Check ExternalSecret status**:
```bash
kubectl get externalsecret google-analytics-credentials -n <namespace>
kubectl describe externalsecret google-analytics-credentials -n <namespace>
```

**Verify SecretStore**:
```bash
kubectl get secretstore -n <namespace>
kubectl describe secretstore secretstore-jarvis -n <namespace>
```

**Check if K8s secret was created**:
```bash
kubectl get secret google-analytics-credentials -n <namespace>
kubectl describe secret google-analytics-credentials -n <namespace>
```

### ECR Pull Issues

**Symptom**: `ImagePullBackOff` or `ErrImagePull`

**Check**:
1. Verify image exists in ECR:
   ```bash
   aws ecr describe-images \
     --repository-name jarvis/ga_mcp_server \
     --region us-east-1 \
     --profile saas
   ```

2. Verify client account has ECR pull permissions (see AWS Setup step 2)

3. Check pod events:
   ```bash
   kubectl describe pod <pod-name> -n <namespace>
   ```

---

## Use Cases & Example Queries

### Dealer Benchmarking

**Query**: "Compare sessions and form submissions across all dealer properties for the last 30 days"

**Tools Used**:
- `run_report` - Pull session metrics per property
- Aggregation done by LLM across multiple property queries

**Metrics**:
- `sessions`, `totalUsers`
- `eventCount` (filtered for `form_submit` event)
- `sessionDefaultChannelGroup` (traffic source breakdown)

### Vehicle Interest Analysis

**Query**: "Which vehicle models are getting the most engagement this month?"

**Tools Used**:
- `run_report` - Filter by page URL (VDP pages)
- `get_custom_dimensions` - Identify model dimensions

**Metrics**:
- `screenPageViews`
- `averageSessionDuration`
- `bounceRate`
- `eventCount` (for model-specific lead forms)

---

## Support

For issues or questions:
- **Repository**: https://github.com/googleanalytics/google-analytics-mcp
- **Jarvis Deployment**: Contact DevOps team
- **Google Analytics API**: https://developers.google.com/analytics/devguides/reporting/data/v1

---

## Security Considerations

1. **Credentials Storage**: Service account JSON is stored encrypted in AWS Secrets Manager
2. **Access Control**: Only Jarvis service account can read the secret (via IRSA)
3. **Network**: MCP server only accessible within Kubernetes cluster (ClusterIP service)
4. **Least Privilege**: Service account has Viewer role (read-only) on GA4 properties
5. **Credential Rotation**: Update secret in AWS Secrets Manager, External Secrets Operator will auto-sync

---

## Maintenance

### Updating the Image

1. Make code changes
2. Push to GitHub
3. Run GitHub Actions workflow (see Jarvis Integration step 1)
4. Update image tag in Helm values
5. Run Terraform apply

### Rotating Credentials

```bash
# Create new service account key
gcloud iam service-accounts keys create ~/jarvis-ga-credentials-new.json \
  --iam-account=$SA_EMAIL

# Update AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id "jarvis/google-analytics-credentials" \
  --secret-string file://~/jarvis-ga-credentials-new.json

# External Secrets Operator will sync within refreshInterval (default 1h)
# Or force immediate sync:
kubectl annotate externalsecret google-analytics-credentials \
  force-sync=$(date +%s) -n <namespace>

# Delete old key from GCP
gcloud iam service-accounts keys list --iam-account=$SA_EMAIL
gcloud iam service-accounts keys delete <old-key-id> --iam-account=$SA_EMAIL
```
