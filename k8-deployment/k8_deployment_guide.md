Application Deployment Commands (EKS + ECR)

This deploys the full three-tier stack to EKS using the manifests in this folder:

- frontend  -> Streamlit UI, exposed publicly via a LoadBalancer Service (:8501)
- backend   -> FastAPI service, reads REDIS_URL (:8000)
- redis     -> in-cluster cache used by the backend (:6379)

Manifests:
- 00-namespace.yaml ............... langgraph-app namespace
- 02-redis.yaml .................. Redis Deployment, PVC, ClusterIP Service
- 03-backend.yaml ............... FastAPI Deployment + Service
- 04-frontend.yaml ............. Streamlit Deployment + LoadBalancer Service
- 01-backend-secret.example.yaml   template for the GROQ_API_KEY secret

"""
# 1. Confirm the cluster exists and is ACTIVE
aws eks describe-cluster --name $CLUSTER_NAME --region $AWS_REGION --query "cluster.status" --output text

# 2. Refresh kubeconfig so the endpoint matches the real cluster
aws eks update-kubeconfig --name $CLUSTER_NAME --region $AWS_REGION

# 3. Confirm you can reach it
kubectl get nodes
"""

1) Set variables

$AWS_REGION = "ap-south-2"
$AWS_ACCOUNT_ID = "932566365205"
$CLUSTER_NAME = "kousik_cluster"
$IMAGE_TAG = "v1"
$ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
$NAMESPACE = "langgraph-app"


ClusterIAMRole: EKS - Cluster

NodeIAMRole: EC2

ClusterIAMRole: AmazonEKSClusterPolicy

NodeIAMRole: 

AmazonEKSWorkerNodePolicy, AmazonEC2ContainerRegistryPullOnly, 
AmazonEKS_CNI_Policy

ClusterIAMRole: 

AmazonEKSBlockStoragePolicy
AmazonEKSBlockStoragePolicyV2
AmazonEKSClusterPolicy
AmazonEKSComputePolicy
AmazonEKSLoadBalancingPolicy
AmazonEKSNetworkingPolicy


2) Verify AWS identity and cluster access - Before this first Create the Cluster - while creating a cluster_name dont use "_" underscore.

aws sts get-caller-identity
aws eks update-kubeconfig --name $CLUSTER_NAME --region $AWS_REGION
kubectl get nodes

3) Create ECR repos if missing (one per image)

aws ecr create-repository --repository-name frontend --region $AWS_REGION
aws ecr create-repository --repository-name backend  --region $AWS_REGION
aws ecr create-repository --repository-name redis    --region $AWS_REGION

If AlreadyExistsException appears, continue.

4) Login Docker to ECR

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

5) Build, tag, push images

The frontend and backend Dockerfiles COPY the whole project, so build from the
project root with -f:

docker build -t "${ECR_REGISTRY}/frontend:${IMAGE_TAG}" -f frontend/Dockerfile .
docker build -t "${ECR_REGISTRY}/backend:${IMAGE_TAG}"  -f backend/Dockerfile .
docker push "${ECR_REGISTRY}/frontend:${IMAGE_TAG}"
docker push "${ECR_REGISTRY}/backend:${IMAGE_TAG}"

Redis is the public image; mirror it to ECR only if you need a private copy:

docker pull redis:7-alpine
docker tag redis:7-alpine "${ECR_REGISTRY}/redis:${IMAGE_TAG}"
docker push "${ECR_REGISTRY}/redis:${IMAGE_TAG}"

6) Confirm image tags exist in ECR

aws ecr describe-images --region $AWS_REGION --repository-name frontend --query "imageDetails[].imageTags" --output json
aws ecr describe-images --region $AWS_REGION --repository-name backend  --query "imageDetails[].imageTags" --output json

7) Point the manifests at your ECR images

In 03-backend.yaml and 04-frontend.yaml set image: to your repos, e.g.
${ECR_REGISTRY}/backend:v1 and ${ECR_REGISTRY}/frontend:v1.

8) Storage for the Redis PVC (StorageClass)

The redis Deployment uses a PersistentVolumeClaim. Without a default StorageClass
that can provision EBS volumes, that PVC stays Pending and the redis pod never
starts. How you provide this depends on the cluster type:

--- EKS AUTO MODE (recommended / what this cluster uses) ---

Auto Mode manages the storage driver for you, but ships NO default StorageClass.
The manifest 01-storageclass.yaml in this folder creates one (auto-ebs) using the
Auto Mode provisioner ebs.csi.eks.amazonaws.com, and it is applied automatically
by "kubectl apply -k ." in step 10. You do NOT need the EBS CSI add-on below.

If you ever need to apply it on its own:

kubectl apply -f 01-storageclass.yaml
kubectl get storageclass        # auto-ebs should show (default)

--- STANDARD (NON-AUTO-MODE) CLUSTER ONLY ---

A manually-created standard cluster does NOT include the EBS CSI driver by
default. Install it as an add-on (skip this entirely on Auto Mode):

8a) Ensure an OIDC provider exists:

eksctl utils associate-iam-oidc-provider --cluster $CLUSTER_NAME --region $AWS_REGION --approve

8b) Create the IRSA role (or use the console "Create recommended role" on the
    add-on screen, which avoids the underscore-in-cluster-name CloudFormation error):

eksctl create iamserviceaccount --name ebs-csi-controller-sa --namespace kube-system --cluster $CLUSTER_NAME --region $AWS_REGION --role-name AmazonEKS_EBS_CSI_DriverRole --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy --approve --role-only

8c) Install the add-on:

aws eks create-addon --cluster-name $CLUSTER_NAME --region $AWS_REGION --addon-name aws-ebs-csi-driver --service-account-role-arn arn:aws:iam::${AWS_ACCOUNT_ID}:role/AmazonEKS_EBS_CSI_DriverRole

8d) Confirm it is active and a default StorageClass exists:

aws eks describe-addon --cluster-name $CLUSTER_NAME --region $AWS_REGION --addon-name aws-ebs-csi-driver --query "addon.status"
kubectl get pods -n kube-system | findstr ebs
kubectl get storageclass

   If a StorageClass exists but none is marked (default), set one:

kubectl patch storageclass gp2 -p '{\"metadata\":{\"annotations\":{\"storageclass.kubernetes.io/is-default-class\":\"true\"}}}'

9) Create the namespace and the backend secret from your gitignored .env

NOTE: the kubectl paths below assume you are INSIDE the k8-deployment folder.
   cd k8-deployment
(If you run from the project root instead, use k8-deployment/00-namespace.yaml,
 --from-env-file=.\.env, and kubectl apply -k k8-deployment.)

cd k8-deployment
kubectl apply -f 00-namespace.yaml
kubectl -n $NAMESPACE create secret generic backend-secrets --from-env-file=..\.env
kubectl apply -k .

10) Apply all manifests

kubectl apply -k .

11) Verify rollout and endpoints

kubectl rollout status deployment/backend  -n $NAMESPACE
kubectl rollout status deployment/frontend -n $NAMESPACE
kubectl get pods -n $NAMESPACE -o wide
kubectl get pvc -n $NAMESPACE
kubectl get endpoints backend -n $NAMESPACE
kubectl get svc frontend -n $NAMESPACE

12) Get the public URL of the frontend

kubectl get svc frontend -n $NAMESPACE -w

When EXTERNAL-IP changes from <pending> to a hostname, open it in a browser
to reach the Streamlit UI.

IMPORTANT (EKS Auto Mode): a plain "type: LoadBalancer" Service does NOT work on
Auto Mode. It falls back to the legacy Classic ELB path, which registers worker
NODES as targets - but Auto Mode nodes are not registered that way, so the ELB
has no healthy backends and the URL just TIMES OUT (even though all pods are
Running and the EXTERNAL-IP resolves).

The fix is already baked into 04-frontend.yaml: it uses Auto Mode's built-in
load balancer controller to create a public NLB that targets pod IPs directly:

  metadata:
    annotations:
      service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
      service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: "ip"
      service.beta.kubernetes.io/aws-load-balancer-healthcheck-path: "/_stcore/health"
      service.beta.kubernetes.io/aws-load-balancer-healthcheck-port: "8501"
  spec:
    type: LoadBalancer
    loadBalancerClass: eks.amazonaws.com/nlb   # <-- the critical line

If you changed an existing frontend Service from the old plain LoadBalancer,
delete and recreate it so the new NLB is provisioned (this gives a NEW hostname;
the old one is dead):

kubectl delete svc frontend -n $NAMESPACE
kubectl apply -k .
kubectl get svc frontend -n $NAMESPACE -w

Confirm Auto Mode accepted it (Events should say "SuccessfullyReconciled" and the
Endpoints line should list pod IPs):

kubectl describe svc frontend -n $NAMESPACE

13) If EXTERNAL-IP stays pending

Check subnet tags in the EKS VPC:

- kubernetes.io/role/elb = 1 (public LB)
- kubernetes.io/role/internal-elb = 1 (internal LB)

Then run:

kubectl describe svc frontend -n $NAMESPACE

14) If the app is not reachable

kubectl get pods -n $NAMESPACE
kubectl describe pod -n $NAMESPACE <pod-name>
kubectl logs -n $NAMESPACE <pod-name>

If the redis pod is Pending and its PVC is Pending, the EBS CSI driver (step 8)
is missing or has no default StorageClass:

kubectl describe pvc redis-data -n $NAMESPACE

If the PVC shows an EMPTY STORAGECLASS column, it was created before the default
StorageClass existed. A PVC's storageClassName is IMMUTABLE, so "kubectl apply -k ."
will NOT fix it - you must delete and recreate the PVC (and its pod):

kubectl delete pvc redis-data -n $NAMESPACE
kubectl delete pod -l app=redis -n $NAMESPACE
kubectl apply -k .

Then confirm it binds and the pod starts:

kubectl get storageclass        # auto-ebs should show (default)
kubectl get pvc -n $NAMESPACE    # redis-data -> Bound
kubectl get pods -n $NAMESPACE   # redis -> Running

Common checks:
- Backend cannot reach Redis: REDIS_URL must be redis://redis:6379/0 so it
  resolves the redis Service.
- Frontend cannot reach backend: BACKEND_URL must be http://backend:8000 and the
  backend Service must have endpoints (kubectl get endpoints backend -n $NAMESPACE).

If pods show ImagePullBackOff, rebuild and push the image again (steps 5 and 6),
update the image if needed, then restart the rollout:

kubectl set image deployment/backend  backend="${ECR_REGISTRY}/backend:${IMAGE_TAG}"   -n $NAMESPACE
kubectl set image deployment/frontend frontend="${ECR_REGISTRY}/frontend:${IMAGE_TAG}" -n $NAMESPACE
kubectl rollout restart deployment/frontend -n $NAMESPACE
kubectl rollout status  deployment/frontend -n $NAMESPACE