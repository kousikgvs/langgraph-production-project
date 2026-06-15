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
docker tag docker-deployment-frontend my-frontend:v1
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
docker tag my-frontend:v1 <dockerhub-username>/my-frontend:v1
docker tag my-redis:v1 <dockerhub-username>/my-redis:7.4
```

### Push
```bash
docker push <dockerhub-username>/my-frontend:v1
docker push <dockerhub-username>/my-redis:7.4

docker push kousikgvs/my-frontend:v1
docker push kousikgvs/my-redis:7.4
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
$AWS_REGION  = "ap-south-2"
# $AWS_ACCOUNT = (aws sts get-caller-identity --query Account --output text)
$AWS_ACCOUNT = 932566365205
# $ECR_REGISTRY = "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"
$ECR_REGISTRY = "932566365205.dkr.ecr.ap-south-2.amazonaws.com"
```

### Create the repositories (one-time)
```bash
aws ecr create-repository --repository-name my-frontend --region $AWS_REGION
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
docker tag kousikgvs/my-frontend:v1 $ECR_REGISTRY/my-frontend:v1
docker tag kousikgvs/redis:v1 $ECR_REGISTRY/redis:v1
```

### Push
```bash
docker push $ECR_REGISTRY/my-frontend:v1
docker push $ECR_REGISTRY/redis:v1
```

### Verify
```bash
aws ecr list-images --repository-name my-frontend --region $AWS_REGION
aws ecr list-images --repository-name redis    --region $AWS_REGION
```
Or check the AWS Console → **ECR → Repositories**.

### Pull from ECR (on any machine with AWS creds)
```bash
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
docker pull $ECR_REGISTRY/my-frontend:v1
```

> **Required IAM permissions:** `ecr:CreateRepository`, `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`. The managed policy `AmazonEC2ContainerRegistryFullAccess` covers all of these.

Now Creating the Kubernetes Infra for Loadbalancing auto Pod startup.

