# Docker Deployment

A Streamlit frontend + Redis backend, runnable as a single container or orchestrated via Docker Compose.

---

## 1. Build & run the frontend from its Dockerfile
```bash
docker build -t streamlit-frontend -f frontend/Dockerfile .
docker run -p 8501:8501 streamlit-frontend
```

### With a custom tag
```bash
docker build -t <your-tag-name> -f frontend/Dockerfile .
docker run -p 8501:8501 <your-tag-name>
```

---

## 2. Run the full stack via Docker Compose
```bash
docker compose up --build
```

Each service in `docker-compose.yml` becomes its **own container** with its **own image**:

| Service              | Image                        | Source                           |
| -------------------- | ---------------------------- | -------------------------------- |
| `streamlit-frontend` | `docker-deployment-frontend` | Built from `frontend/Dockerfile` |
| `redis`              | `redis:7.4`                  | Pulled from Docker Hub           |

They share a Docker network, so the frontend reaches Redis by service name (`REDIS_HOST=redis`).

### Verify the containers
```bash
docker ps   # should show 2 containers
```

Example output:
```text
CONTAINER ID   IMAGE                        COMMAND                  PORTS                    NAMES
7aed1c72f3b6   docker-deployment-frontend   "streamlit run ..."      0.0.0.0:8501->8501/tcp   streamlit-frontend
951b242d122d   6ab0b6e73817                 "docker-entrypoint..."   0.0.0.0:6379->6379/tcp   redis
```

---

## 3. Tag each image separately (no rebuild — just add new tags)

### Frontend image
The locally built image already has a name, so tag it directly:
```bash
docker tag redis:7-alpine redis:v1
docker tag langgraph-production-project-backend langgraph-production-project-backend:v1
docker tag langgraph-production-project-frontend langgraph-production-project-frontend:v1
```

### Redis image
Tagging by short container-image ID can fail because Docker treats unknown IDs as a repo name:
```text
PS> docker tag 6ab0b6e73817 my-redis:v1
Error response from daemon: No such image: 6ab0b6e73817:latest
```

Fix it by pulling the image so the `repo:tag` is registered locally, then tag it:
```bash
# 1. Pull the image
docker pull redis:7.4

# 2. Tag it
docker tag redis:7.4 my-redis:v1
```

### Verify
```bash
docker images
```
Expected (same IMAGE ID, different REPOSITORY:TAG):
```text
IMAGE                              ID             DISK USAGE   EXTRA
docker-deployment-frontend:latest  d7691aed2e6c   785MB        U
my-frontend:v1                     d7691aed2e6c   785MB        U
redis:7.4                          <redis-id>     ~120MB       U
my-redis:v1                        <redis-id>     ~120MB       U
```

> **Note:** `docker tag` only tags **images**, not containers. To rename a running container use `docker rename <old> <new>`.

---

## 4. Push images to Docker Hub

Docker Hub requires images to be named `<dockerhub-username>/<repo>:<tag>`. Re-tag your local images with your username, then push.

### Log in
```bash
docker login
# Enter your Docker Hub username and a Personal Access Token (recommended over password)
```

### Re-tag with your Docker Hub username
Replace `<dockerhub-username>` with yours (e.g. `kousikgvs`):
```bash
$DOCKER_USERNAME = "kousikgvs"
docker tag langgraph-production-project-frontend:v1 $DOCKER_USERNAME/frontend:v1
docker tag redis:v1 $DOCKER_USERNAME/redis:v1
docker tag langgraph-production-project-backend:v1 $DOCKER_USERNAME/backend:v1
```

### Push
```bash
docker push $DOCKER_USERNAME/backend:v1
docker push $DOCKER_USERNAME/redis:v1
docker push $DOCKER_USERNAME/frontend:v1
```

### Verify
- Check https://hub.docker.com/repositories — the repos should appear under your account.
- Pull from anywhere:
  ```bash
  docker pull <dockerhub-username>/my-frontend:v1
  ```

> **Tip:** create a Personal Access Token at https://hub.docker.com/settings/security and use it instead of your password during `docker login`.

---

## 5. Push images to AWS ECR

AWS Elastic Container Registry (ECR) is a private Docker registry hosted on AWS. Unlike Docker Hub, the repository **must exist before you can push** to it.

### Prerequisites
- AWS CLI installed and configured (`aws configure` — needs an access key with ECR permissions)
- Docker logged out of any conflicting registry sessions

Set these once per shell to avoid repetition:
```powershell
# $AWS_ACCOUNT = (aws sts get-caller-identity --query Account --output text)
$AWS_REGION  = "ap-south-2"
$AWS_ACCOUNT = 932566365205
$ECR_REPOSITORY = "kousikgvs"
$ECR_REGISTRY = "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"
# $ECR_REGISTRY = "932566365205.dkr.ecr.ap-south-2.amazonaws.com/kousikgvs"
```

### Create the repositories (one-time)
```bash
aws ecr create-repository --repository-name frontend --region $AWS_REGION
aws ecr create-repository --repository-name backend --region $AWS_REGION
aws ecr create-repository --repository-name redis --region $AWS_REGION
```

### Authenticate Docker to ECR
The login token is valid for **12 hours** — re-run when it expires:
```bash
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
```

### Re-tag local images for ECR
ECR images must be named `<account>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>`:
```bash
docker tag $DOCKER_USERNAME/frontend:v1 $ECR_REGISTRY/frontend:v1
docker tag $DOCKER_USERNAME/redis:v1 $ECR_REGISTRY/redis:v1
docker tag $DOCKER_USERNAME/backend:v1 $ECR_REGISTRY/backend:v1
```

### Push
```bash
docker push $ECR_REGISTRY/frontend:v1
docker push $ECR_REGISTRY/redis:v1
docker push $ECR_REGISTRY/backend:v1
```

### Verify
```bash
aws ecr list-images --repository-name frontend --region $AWS_REGION
aws ecr list-images --repository-name redis    --region $AWS_REGION
aws ecr list-images --repository-name backend    --region $AWS_REGION
```
Or check the AWS Console → **ECR → Repositories**.

### Pull from ECR (on any machine with AWS creds)
```bash
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
docker pull $ECR_REGISTRY/frontend:v1
```

> **Required IAM permissions:** `ecr:CreateRepository`, `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`. The managed policy `AmazonEC2ContainerRegistryFullAccess` covers all of these.

Now Creating the Kubernetes Infra for Loadbalancing auto Pod startup.

This guide explains the EKS deployment path in simple beginner language.

Think of the tools like this:

- Kubeflow manages the ML workflow.
- KServe serves the model.
- Helm installs and upgrades the platform components.
- kubectl operates and debugs the running cluster.


## Target Architecture

```text
Kubeflow pipeline or external training job -> model artifact in Amazon S3
                                                |
                                                v
                                         KServe InferenceService on EKS
                                                |
                                                v
                                           Prediction API
```

## Prerequisites

Install these tools first:

- AWS account with permission to create EKS, IAM, S3, and EC2 resources
- AWS CLI v2
- eksctl
- kubectl
- Helm 3
- A trained model file such as `model.joblib`

On Windows, you can install them with `winget`:

```powershell
winget install -e --id Amazon.AWSCLI --accept-source-agreements --accept-package-agreements
winget install -e --id eksctl.eksctl --accept-source-agreements --accept-package-agreements
winget install -e --id Kubernetes.kubectl --accept-source-agreements --accept-package-agreements
winget install -e --id Helm.Helm --version 3.20.0 --accept-source-agreements --accept-package-agreements
```

This guide assumes Helm 3. If you already installed Helm 4, replace it with a Helm 3 release before continuing.

Verify the tools:

```powershell
aws --version
eksctl version
kubectl version --client
helm version
```

Configure AWS credentials:

```powershell
aws configure
```

## If AWS - kubectl Doesnt connect automatically connect using Below Steps after creating the cluster

ClusterIAMRole: EKS - Cluster

NodeIAMRole: EC2

ClusterIAMRole: AmazonEKSClusterPolicy

NodeIAMRole: AmazonEKSWorkerNodePolicy, AmazonEC2ContainerRegistryPullOnly, AmazonEKS_CNI_Policy

Example admin access flow:

```powershell
$CLUSTER_NAME = ""
$AWS_REGION = ""
$ADMIN_ROLE_ARN = ""

aws eks create-access-entry `
  --cluster-name $CLUSTER_NAME `
  --region $AWS_REGION `
  --principal-arn $ADMIN_ROLE_ARN `
  --type STANDARD

aws eks associate-access-policy `
  --cluster-name $CLUSTER_NAME `
  --region $AWS_REGION `
  --principal-arn $ADMIN_ROLE_ARN `
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy `
  --access-scope type=cluster

aws eks update-kubeconfig --name kousik_cluster_1 --region ap-south-2

when we enter aws configure we give the access_key and secret_access_key right its when we create the role.

now when we create cluster we give cluster_role and node_role 

cluster > access > add a new access for our local role being used.

Open your cluster.
Open the Access tab.
Open Access entries.
Click Create access entry.
Principal ARN:
choose arn:aws:iam::932566365205:role/kousik_role
or choose your IAM user if that is what you use locally
Type:
choose Standard
Save the access entry.
After creating it, attach an access policy.
Choose:
AmazonEKSClusterAdminPolicy

kubectl get nodes
```

If you see `the server has asked for the client to provide credentials`, your kubeconfig may be present, but the IAM principal you are using still does not have cluster access.
In that case, fix the access entry or the role assumption path first.

## Create the EKS Cluster and Worker Nodes

Important:

- `kubectl` does not create the EKS control plane or EC2 worker nodes.
- `eksctl` creates the EKS cluster and managed node groups.
- `kubectl` connects to the cluster after it exists.
- Helm installs software into the cluster. Helm does not create the cluster itself.

Set a cluster name, AWS Region, and node size:

```powershell
$CLUSTER_NAME = ""
$AWS_REGION = ""
$NODE_TYPE = "t3.medium"
```

For this guide, `t3.medium` is the practical minimum for running EKS add-ons plus KServe or Kubeflow components.
If your AWS account or console workflow is restricted to Free Tier-eligible EC2 types, do not keep `t3.medium` selected. That exact combination causes the managed node group to fail with `InvalidParameterCombination`.

Use one of these paths instead:

- Keep `$NODE_TYPE = "t3.medium"` and remove the Free Tier-only restriction.
- Or temporarily switch `$NODE_TYPE` to an x86_64 Free Tier-eligible type such as `t3.micro` after verifying what is available in your Region:

```powershell
aws ec2 describe-instance-types `
  --region $AWS_REGION `
  --filters Name=free-tier-eligible,Values=true `
  --query "InstanceTypes[?contains(ProcessorInfo.SupportedArchitectures, 'x86_64')].InstanceType" `
  --output text
```

Free Tier-sized nodes are only useful for validating that cluster creation works. They are usually too small for Kubeflow, KServe, or other multi-service ML workloads.

Create a new EKS cluster with one managed node group:

```powershell
eksctl create cluster `
       --name $CLUSTER_NAME `
       --region $AWS_REGION `
       --version 1.30 `
       --nodegroup-name linux-nodes `
       --node-type $NODE_TYPE `
       --nodes 2 `
       --nodes-min 2 `
       --nodes-max 4 `
       --managed
```


Confirm that the cluster is ready:

```powershell
aws eks list-clusters --region $AWS_REGION
aws eks update-kubeconfig --region $AWS_REGION --name $CLUSTER_NAME
# Use a human or CI access role that has an EKS access entry. Do not use the EC2 node role here.
kubectl get nodes
kubectl config current-context
kubectl cluster-info
kubectl get nodes -o wide
```

`kubectl` does not detect Amazon EKS automatically. It only reads your local `kubeconfig`.
If no EKS context is configured, `kubectl` falls back to `http://localhost:8080`.
If the EKS context exists but you see `the server has asked for the client to provide credentials`, your current AWS identity does not have access to that cluster yet.

If you need another node group later, create one with `eksctl`:

```powershell
eksctl create nodegroup `
       --cluster $CLUSTER_NAME `
       --region $AWS_REGION `
       --name batch-nodes `
       --node-type t3.large `
       --nodes 2 `
       --nodes-min 1 `
       --nodes-max 4 `
       --managed
```

If you only want to change the node count for an existing node group, scale it:

```powershell
eksctl scale nodegroup `
       --cluster $CLUSTER_NAME `
       --region $AWS_REGION `
       --name linux-nodes `
       --nodes 3
```

## View Nodes, Namespaces, and Pods with kubectl

After the cluster is up, these are the most useful inspection commands:

```powershell
kubectl get nodes
kubectl get nodes -o wide
kubectl get namespaces
kubectl get pods -A
kubectl get pods -n kube-system
kubectl get pods -o wide -A
```

Useful follow-up commands:

```powershell
kubectl describe node <node-name>
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace>
```

Example: view the system pods that EKS created:

```powershell
kubectl get pods -n kube-system
```