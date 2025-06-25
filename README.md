# AITHERIA ALTOS

> **Enterprise-grade, cloud-native, AI-powered SaaS platform for the end-to-end biotechnology R&amp;D lifecycle**

[![CI Status](https://github.com/your-org/aitheria-altos/actions/workflows/ci.yml/badge.svg)](../actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

---

## ✨ Key Features

* Unified operating system covering molecular design, biological engineering, lab management and analytics  
* Microservices architecture (FastAPI + RabbitMQ) exposed through a single AWS API Gateway  
* Cloud-native infrastructure on AWS (EKS, RDS, S3, SageMaker, Terraform IaC)  
* Security-by-design – HIPAA &amp; FDA 21 CFR Part 11-ready, RBAC, audit trails  
* Automated CI/CD (GitHub Actions → Amazon ECR → EKS rolling updates)  

---

## 🏗️ High-Level Architecture

### 1. Frontend (Next.js 14)

* React 18 with **SSR** & **ISR**  
* Tailwind CSS + Zustand + TanStack Query  
* Realtime collaboration via Socket.IO  
* D3 / Plotly / Mol★ for scientific visuals  

### 2. API Gateway

* AWS API Gateway (REST)  
* JWT validation, rate-limiting, CORS  
* Routes traffic to internal microservices  

### 3. Microservices (Python 3.11 / FastAPI)

| Service | Purpose |
|---------|---------|
| **AuthService** | OAuth 2.0 / OIDC, SSO, JWT issuance |
| **ProjectService** | Workspaces, projects, Kanban tasks |
| **NucleicAcidService** | DNA/RNA design, plasmid analysis |
| **ProteinService** | Protein engineering, binder design |
| **LIMSService** | Samples, inventory, instruments |
| **BillingService** | Subscriptions, Stripe integration |

Async jobs are dispatched via **RabbitMQ** to worker pods.

### 4. Data & Storage Layer

* PostgreSQL (RDS) – transactional data  
* MongoDB (DocumentDB) – unstructured logs  
* S3 – large scientific files  
* OpenSearch k-NN – vector embeddings  
* Redis (ElastiCache) – caching & sessions  

### 5. AI / MLOps

* SageMaker for training/inference  
* MLflow for experiment tracking  
* NVIDIA Triton servers inside EKS  

### 6. DevOps & Security

* Terraform IaC provisions VPC, EKS, DBs …  
* GitHub Actions pipeline (build → test → scan → push → deploy)  
* RBAC enforced at API Gateway & service level  
* Audit logs streamed to CloudWatch & S3 Glacier  

---

## 📂 Project Structure

```
aitheria-altos/
├── frontend/               # Next.js web application
├── backend/
│   ├── api-gateway/        # OpenAPI specs, AWS SAM templates
│   └── services/           # Individual FastAPI microservices
│       ├── auth/
│       ├── project/
│       ├── nucleic-acid/
│       ├── protein/
│       ├── lims/
│       └── billing/
├── infrastructure/         # Terraform modules & env configs
├── docs/                   # Extended documentation (to be added)
├── .github/                # CI/CD workflows
├── .gitignore
└── README.md               # You are here
```

---

## 🛠️ Local Development Setup

1. **Prerequisites**

   * Node.js 18+ & npm or yarn  
   * Python 3.11+ & `pyenv`/`poetry` (recommended)  
   * Docker & Docker Compose  
   * Terraform 1.7+  
   * AWS CLI configured with test account  
   * Factory Bridge (for pairing with Factory.ai)

2. **Clone & bootstrap**

   ```bash
   git clone https://github.com/your-org/aitheria-altos.git
   cd aitheria-altos
   ```

3. **Frontend**

   ```bash
   cd frontend
   cp .env.example .env.local   # fill in variables
   npm install
   npm run dev                  # http://localhost:3000
   ```

4. **Backend microservices**

   ```bash
   # Example for AuthService
   cd backend/services/auth
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8001
   ```

   Repeat for other services (different ports). A `docker-compose.yml` (coming soon) will spin up the entire stack with RabbitMQ and databases.

---

## 🚀 Deployment (Basic)

1. Configure backend & infra secrets in **GitHub Actions** → **Repository Secrets**.
2. From your workstation:

   ```bash
   cd infrastructure/envs/dev
   terraform init
   terraform apply    # creates VPC, EKS, RDS, … in dev account
   ```

3. Push to `main` → GitHub Actions builds images, runs tests/security scans, pushes to **Amazon ECR**, then performs a rolling deploy to **EKS** via `kubectl apply -k k8s/overlays/dev`.

Production follows the same flow with additional gates (manual approval, model-evaluation).

---

## 📚 Further Documentation

Detailed specs, ADRs, API references, and onboarding guides will live in the [`docs/`](docs/) folder.  
Until then, refer to the original project brief and open issues for clarification.

---

### 🖋️ Contributing

Please read `docs/CONTRIBUTING.md` (coming soon) for coding standards, commit style, and the PR review process. All contributions welcome!

---

© 2025 San Francisco AI Factory – Released under the Apache 2.0 license.
