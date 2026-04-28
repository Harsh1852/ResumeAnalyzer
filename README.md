# 🎯 Resume Analyzer — Serverless Cloud Platform

A fully serverless, event-driven resume analysis platform built on AWS using Python CDK. Upload your resume and instantly get an AI-powered report with a score, role recommendations, live job openings, tailored resumes, course recommendations, and a drag-and-drop application tracker.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Resume Analysis** | Upload PDF/DOCX → Textract extracts text → Claude 3 Haiku scores and analyzes |
| **AI Report** | Score (0–100), section-by-section review, top 5 role matches, job strategies |
| **Live Job Openings** | Real Adzuna postings matched to your top roles, refreshable on demand |
| **Tailored Resumes** | AI-rewritten resume for any job — Markdown or LaTeX (default or custom template) |
| **Course Recommendations** | Missing-skill courses sourced via Tavily for each job posting |
| **Application Tracker** | Kanban board to track applications across Wishlist → Applied → Interview → Offer |
| **Email Notifications** | SES email when your analysis completes with a deep-link to the report |
| **PDF Export** | Print-optimized report export via browser print |
| **CI/CD** | GitHub Actions auto-deploys frontend to S3 + CloudFront on every push to `main` |

---

## 🏗️ Architecture

```
User → CloudFront CDN (React SPA)
          │
          ├─ Auth API GW ──────────→ Auth Lambda ─────────→ Cognito User Pool
          │
          ├─ App API GW ───────────→ Upload Lambda ──────→ S3 (presigned upload)
          │                                                       │
          │                                               SQS ParseQueue
          │                                                       │
          │                                           Parser Lambda (Textract)
          │                                                       │
          │                                               SQS AnalysisQueue
          │                                                       │
          │                                    Analyzer Lambda (Bedrock Claude 3 Haiku)
          │                                                       │
          │                                                SNS ResultsTopic
          │                                               /               \
          │                                    SQS ResultsQueue    SQS NotificationQueue
          │                                           │                       │
          │                              Results Worker Lambda    Notification Lambda → SES
          │                                           │
          │                                    DynamoDB ResultsTable
          │                                           │
          ├─ Results API GW ────────→ Results Lambda ─┘
          │
          ├─ Jobs API GW ──────────→ Jobs Lambda ──────→ Adzuna API
          │                              │                Tavily API
          │                              └──────────────→ Bedrock (tailored resumes)
          │                              └──────────────→ DynamoDB (jobs + tailored resumes)
          │
          └─ Applications API GW ──→ Applications Lambda → DynamoDB ApplicationsTable
```

---

## 🧩 Microservice Breakdown

| # | Microservice | Stack | AWS Services Used |
|---|---|---|---|
| 1 | **Auth Service** | `AuthStack` | Cognito, Lambda, API Gateway, DynamoDB |
| 2 | **Upload Service** | `UploadStack` | S3, Lambda, API Gateway, SQS |
| 3 | **Parser Service** | `ParserStack` | Lambda, Textract, S3, SQS, DynamoDB |
| 4 | **Analyzer Service** | `AnalyzerStack` | Lambda, Bedrock (Claude 3 Haiku), S3, SNS, SQS |
| 5 | **Results Service** | `ResultsStack` | Lambda, DynamoDB, API Gateway, SQS |
| 6 | **Notification + Frontend** | `FrontendStack` | Lambda, SES, S3, CloudFront |
| 7 | **Jobs Service** | `JobsStack` | Lambda, DynamoDB, API Gateway, Bedrock, Adzuna, Tavily |
| 8 | **Applications Service** | `ApplicationsStack` | Lambda, DynamoDB, API Gateway |

---

## 🛠️ Prerequisites

- **AWS CLI** configured with admin permissions
- **Python 3.12+**
- **Node.js 20+** and npm
- **AWS CDK v2** — `npm install -g aws-cdk`
- **Amazon Bedrock** — enable **Claude 3 Haiku** (`anthropic.claude-3-haiku-20240307-v1:0`) in `us-east-1` via the console
- **Amazon Textract** — available by default in `us-east-1`
- **Amazon SES** — verify your sender email address (sandbox mode also requires verifying recipient addresses)
- **Adzuna API** — free account at [developer.adzuna.com](https://developer.adzuna.com) for `APP_ID` and `API_KEY`
- **Tavily API** — free account at [app.tavily.com](https://app.tavily.com) for `TAVILY_API_KEY`

---

## 🚀 Setup & Deployment

### 1. Clone the repo

```bash
git clone https://github.com/Harsh1852/CloudProject.git
cd CloudProject
```

### 2. Backend — install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
```

### 3. Bootstrap CDK (once per account/region)

```bash
cdk bootstrap -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

### 4. Set external API keys

Open `backend/stacks/jobs_stack.py` and fill in:

```python
"ADZUNA_APP_ID":  "YOUR_ADZUNA_APP_ID",
"ADZUNA_API_KEY": "YOUR_ADZUNA_API_KEY",
"TAVILY_API_KEY": "YOUR_TAVILY_API_KEY",
```

Open `backend/stacks/frontend_stack.py` and set your SES sender address:

```python
"SES_FROM_ADDRESS": "noreply@yourdomain.com",
"FRONTEND_URL":     "https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net",
```

### 5. Deploy all stacks

```bash
cdk deploy --all --require-approval never -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

Note the CDK outputs:

| CDK Output Key | Used as |
|---|---|
| `ResumeAnalyzerAuth.AuthApiUrl` | `VITE_AUTH_API_URL` |
| `ResumeAnalyzerUpload.AppApiUrl` | `VITE_APP_API_URL` |
| `ResumeAnalyzerResults.ResultsApiUrl` | `VITE_RESULTS_API_URL` |
| `ResumeAnalyzerJobs.JobsApiUrl` | `VITE_JOBS_API_URL` |
| `ResumeAnalyzerApplications.ApplicationsApiUrl` | `VITE_APPLICATIONS_API_URL` |
| `ResumeAnalyzerFrontend.FrontendBucketName` | S3 bucket for frontend deploy |
| `ResumeAnalyzerFrontend.CloudFrontDistributionId` | CloudFront distribution ID |
| `ResumeAnalyzerFrontend.CloudFrontUrl` | Your app's public URL |

### 6. Configure and deploy the frontend

```bash
cd ../frontend
cp .env.example .env.local
# Fill in .env.local with the CDK output values above
npm install
npm run build
aws s3 sync dist/ s3://YOUR_FRONTEND_BUCKET --delete --region us-east-1
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*" --region us-east-1
```

### 7. (Optional) Set up CI/CD

Add these GitHub Actions secrets to your repo:

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user with S3 + CloudFront permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding secret |

After that, every push to `main` that touches `frontend/**` will automatically build and deploy the frontend.

---

## 📡 API Reference

### Auth API — no authentication required

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create account — sends 6-digit OTP to email |
| `POST` | `/auth/verify` | Verify OTP → activates account |
| `POST` | `/auth/resend-otp` | Resend verification code |
| `POST` | `/auth/login` | Login → returns `idToken`, `accessToken`, `refreshToken` |
| `POST` | `/auth/refresh` | Refresh access token |
| `POST` | `/auth/logout` | Global sign-out |

### App API — Bearer `idToken` required

| Method | Path | Description |
|---|---|---|
| `POST` | `/uploads/presigned-url` | Get S3 presigned URL for direct browser upload |
| `POST` | `/uploads/confirm` | Confirm upload complete → triggers analysis pipeline |
| `GET` | `/uploads` | List your uploaded resumes |
| `GET` | `/uploads/{uploadId}` | Poll upload status (`PENDING → PARSING → ANALYZING → COMPLETE`) |
| `GET` | `/uploads/{uploadId}/view-url` | Presigned URL to view original resume file |
| `DELETE` | `/uploads/{uploadId}` | Delete resume + upload record |
| `GET` | `/results` | List analysis results |
| `GET` | `/results/{resultId}` | Full analysis report |
| `DELETE` | `/results/{resultId}` | Delete analysis report |

### Jobs API — Bearer `idToken` required

| Method | Path | Description |
|---|---|---|
| `POST` | `/jobs/search` | Search Adzuna for live jobs matching your top roles |
| `GET` | `/jobs` | List cached jobs for a `resultId` |
| `GET` | `/jobs/{jobId}` | Get a single job posting |
| `GET` | `/jobs/{jobId}/courses` | Get Tavily course recommendations for missing skills |
| `POST` | `/jobs/{jobId}/tailored-resume` | Generate AI-tailored resume (Markdown or LaTeX) |
| `GET` | `/tailored-resumes/{resumeId}` | Get a saved tailored resume |
| `PUT` | `/tailored-resumes/{resumeId}` | Save edits to a tailored resume |

### Applications API — Bearer `idToken` required

| Method | Path | Description |
|---|---|---|
| `POST` | `/applications` | Create application (company, title, status, notes, …) |
| `GET` | `/applications` | List all your applications |
| `GET` | `/applications/{id}` | Get a single application |
| `PUT` | `/applications/{id}` | Update application (status, notes, interview details) |
| `DELETE` | `/applications/{id}` | Delete application |
| `GET` | `/applications/stats` | Aggregate counts by status |

### Jobs API (`/jobs/*`, `/tailored-resumes/*`) — Bearer `idToken` required

| Method | Path | Description |
|---|---|---|
| GET | `/jobs` | List cached jobs for a result (`?resultId=`). |
| POST | `/jobs/search` | Search Adzuna for live jobs matching the resume's top roles. |
| GET | `/jobs/{jobId}` | Get a single job listing. |
| POST | `/jobs/{jobId}/courses` | Fetch Tavily course recommendations for a job role. |
| POST | `/jobs/{jobId}/tailored-resume` | Generate an AI-tailored resume for a specific job. |
| GET | `/tailored-resumes/{resumeId}` | Get a tailored resume (markdown or LaTeX). |
| PUT | `/tailored-resumes/{resumeId}` | Save edits to a tailored resume. |

### Applications API (`/applications/*`) — Bearer `idToken` required

| Method | Path | Description |
|---|---|---|
| GET | `/applications` | List all applications (optional `?status=`). |
| POST | `/applications` | Create a new application record. |
| GET | `/applications/stats` | Aggregate stats: total, by-status counts, response rate, offer rate. |
| GET | `/applications/{id}` | Get a single application. |
| PATCH | `/applications/{id}` | Update application fields (status, notes, next action, etc.). |
| DELETE | `/applications/{id}` | Delete an application. |
| POST | `/applications/{id}/rounds` | Add an interview round to an application. |
| PATCH | `/applications/{id}/rounds/{roundId}` | Update an interview round. |
| DELETE | `/applications/{id}/rounds/{roundId}` | Delete an interview round. |

---

## 🔄 End-to-End Data Flow

```
1.  Register   → Cognito creates user, sends 6-digit OTP
2.  Verify     → Cognito confirms account
3.  Login      → Cognito returns JWT tokens (15 min idToken)
4.  Upload     → Frontend gets presigned S3 URL, uploads directly, calls /confirm
5.  Parse      → S3 event → Parser Lambda → Textract extracts text → SQS
6.  Analyze    → Analyzer Lambda → Bedrock Claude 3 Haiku → SNS fan-out
7.  Results    → Results Worker writes to DynamoDB; Notification Lambda sends SES email
8.  View       → Frontend polls /uploads/{id} until COMPLETE → loads /results/{resultId}
9.  Jobs       → User clicks "Find jobs" → Adzuna live postings cached in DynamoDB
10. Tailor     → User picks a job → Bedrock rewrites resume → editable in-app
11. Track      → User drags application cards across Kanban columns
```

---

## 📊 Report Contents

Generated by Claude 3 Haiku + Tavily real-time job market data:

- **Resume Score** (0–100) with rubric breakdown
- **Profile Summary**
- **Section-by-Section Review** — Professional Summary, Work Experience, Skills, Education, Presentation
- **Critical Improvements** — top 5 actionable fixes
- **Top 5 Role Matches** — match %, resume gaps, application tips, 5 target companies each
- **7 Job Search Strategies** — personalised to the candidate
- **Skills to Highlight** and **Skills to Develop**
- **Key Achievements**

---

## 📁 Project Structure

```
CloudProject/
├── .github/
│   └── workflows/
│       └── deploy-frontend.yml     # CI/CD: auto-deploy on push to main
│
├── backend/
│   ├── app.py                      # CDK app entry point
│   ├── cdk.json
│   ├── requirements.txt
│   ├── stacks/
│   │   ├── auth_stack.py           # Microservice 1 — Cognito auth
│   │   ├── upload_stack.py         # Microservice 2 — S3 upload + SQS trigger
│   │   ├── parser_stack.py         # Microservice 3 — Textract parsing
│   │   ├── analyzer_stack.py       # Microservice 4 — Bedrock analysis
│   │   ├── results_stack.py        # Microservice 5 — Results API
│   │   ├── frontend_stack.py       # Microservice 6 — SES + CloudFront
│   │   ├── jobs_stack.py           # Microservice 7 — Jobs, courses, tailored resumes
│   │   └── applications_stack.py   # Microservice 8 — Application tracker
│   └── lambdas/
│       ├── auth_service/
│       ├── upload_service/
│       ├── parser_service/
│       ├── analyzer_service/
│       ├── results_service/
│       ├── notification_service/
│       ├── jobs_service/
│       └── applications_service/
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    ├── .env.example
    └── src/
        ├── App.jsx                 # Routing
        ├── main.jsx
        ├── services/
        │   └── api.js              # Axios client for all 4 APIs
        └── components/
            ├── Auth/
            │   ├── Login.jsx
            │   ├── Register.jsx
            │   └── VerifyOTP.jsx
            ├── Resume/
            │   └── ResumeUpload.jsx
            ├── Report/
            │   ├── ReportView.jsx  # Full-screen report with PDF export
            │   ├── ReportPDF.jsx   # Print-optimised PDF layout
            │   └── RoleDetail.jsx  # Per-role deep-dive page
            ├── Jobs/
            │   ├── JobsSection.jsx # Jobs panel in report view
            │   └── JobDetail.jsx   # Job page: tailored resume + courses
            └── Tracker/
                ├── TrackerBoard.jsx      # Kanban drag-and-drop board
                ├── ApplicationDetail.jsx
                └── NewApplication.jsx
```

---

## 💣 Tear Down

```bash
cd backend
cdk destroy --all --force -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

> All DynamoDB tables and S3 buckets use `RemovalPolicy.DESTROY` for easy cleanup.

---

## 🛡️ Security Notes

- JWT tokens are stored in `localStorage` — suitable for a class project; use HttpOnly cookies for production
- SES is used in sandbox mode — verify recipient emails or request production access
- Adzuna and Tavily API keys are stored as Lambda environment variables — use AWS Secrets Manager for production
- IAM roles follow least-privilege: each Lambda only has permissions for the resources it owns

---

## 📄 License

MIT — see [LICENSE](LICENSE)
