# Resume Analyzer — Cloud Computing Group Project

A serverless resume analysis platform built entirely on AWS using Python CDK.

---

## Architecture Overview

```
User → CloudFront (React SPA)
     → Auth API Gateway        → Lambda → Cognito (OTP email verification)
     → Upload API Gateway      → Lambda → S3 (presigned upload)
                                                ↓
                                          SQS ParseQueue
                                                ↓
                                      Parser Lambda → Textract / pypdf
                                                ↓
                                          SQS AnalysisQueue
                                                ↓
                                    Analyzer Lambda → Bedrock (Claude 3 Haiku)
                                                    → Tavily (market research)
                                                ↓
                                         SNS ResultsTopic
                                        /                \
                               SQS ResultsQueue     SQS NotificationQueue
                                      ↓                      ↓
                            Results Worker Lambda    Notification Lambda → SES email
                                      ↓
                                DynamoDB ResultsTable
                                      ↓
     → Results API Gateway    → Results API Lambda → Frontend
     → Jobs API Gateway       → Jobs Lambda → Adzuna (live jobs)
                                           → Tavily (courses)
                                           → Bedrock (tailored resumes)
     → Applications API Gateway → Applications Lambda → DynamoDB ApplicationsTable
```

---

## Microservice Assignments

| # | Microservice | Student | Stack | AWS Services |
|---|---|---|---|---|
| 1 | Auth Service | Student 1 | `AuthStack` | Cognito, Lambda, API GW, DynamoDB |
| 2 | Upload Service | Student 1 | `UploadStack` | S3, Lambda, API GW, SQS |
| 3 | Parser Service | Student 2 | `ParserStack` | Lambda, Textract, S3, SQS, DynamoDB |
| 4 | Analyzer Service | Student 2 | `AnalyzerStack` | Lambda, Bedrock, Tavily, S3, SNS, SQS, DynamoDB |
| 5 | Results Service | Student 3 | `ResultsStack` | Lambda, DynamoDB, API GW, SQS |
| 6 | Notification + Frontend | Student 3 | `FrontendStack` | Lambda, SES, S3, CloudFront |
| 7 | Jobs Service | Student 3 | `JobsStack` | Lambda, API GW, DynamoDB, Bedrock, Adzuna, Tavily |
| 8 | Applications Service | Student 3 | `ApplicationsStack` | Lambda, API GW, DynamoDB |

---

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.12+
- Node.js 18+
- AWS CDK v2 (`npm install -g aws-cdk`)
- Amazon Bedrock: enable **Claude 3 Haiku** model in `us-east-1` via the AWS console
- Amazon SES: verify your sender email address in SES (sandbox mode requires verifying recipients too)
- **Adzuna API credentials:** Register at [developer.adzuna.com](https://developer.adzuna.com) to get `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`
- **Tavily API key:** Register at [tavily.com](https://tavily.com) to get `TAVILY_API_KEY`

---

## Setup & Deployment

### 1. Backend setup

```bash
cd backend

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate.bat

pip install -r requirements.txt

# Bootstrap CDK once per account/region
cdk bootstrap -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

### 2. Set third-party API keys

Set these environment variables before deploying so CDK injects them into the Lambda functions:

```bash
export ADZUNA_APP_ID=your_adzuna_app_id
export ADZUNA_APP_KEY=your_adzuna_app_key
export TAVILY_API_KEY=your_tavily_api_key
```

### 3. Deploy all stacks

```bash
cdk deploy --all --require-approval never -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

Note the following values from CDK output:

| CDK Output | Use |
|---|---|
| `ResumeAnalyzerAuth.AuthApiUrl` | `VITE_AUTH_API_URL` in `.env.local` |
| `ResumeAnalyzerUpload.AppApiUrl` | `VITE_APP_API_URL` in `.env.local` |
| `ResumeAnalyzerResults.ResultsApiUrl` | `VITE_RESULTS_API_URL` in `.env.local` |
| `ResumeAnalyzerJobs.JobsApiUrl` | `VITE_JOBS_API_URL` in `.env.local` |
| `ResumeAnalyzerApplications.ApplicationsApiUrl` | `VITE_APPLICATIONS_API_URL` in `.env.local` |
| `ResumeAnalyzerFrontend.CloudFrontUrl` | `URL` in `.env.local` + update step below |
| `ResumeAnalyzerFrontend.FrontendBucketName` | `FRONTEND_BUCKET_NAME` in `.env.local` |
| `ResumeAnalyzerFrontend.CloudFrontDistributionId` | `DISTRIBUTION_ID` in `.env.local` |

### 4. Update FRONTEND_URL and redeploy

The SES notification email links back to your app. Update the hardcoded URL in `backend/stacks/frontend_stack.py`:

```python
"FRONTEND_URL": "https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net",
```

Then redeploy to apply it:

```bash
cdk deploy ResumeAnalyzerFrontend --require-approval never -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

### 5. Configure frontend environment

```bash
cd ../frontend
cp .env.example .env.local
# Fill in .env.local with the CDK output values from step 3
```

`.env.local` must contain all five API URLs:

```bash
VITE_AUTH_API_URL=https://...execute-api.us-east-1.amazonaws.com/prod/
VITE_APP_API_URL=https://...execute-api.us-east-1.amazonaws.com/prod/
VITE_RESULTS_API_URL=https://...execute-api.us-east-1.amazonaws.com/prod/
VITE_JOBS_API_URL=https://...execute-api.us-east-1.amazonaws.com/prod/
VITE_APPLICATIONS_API_URL=https://...execute-api.us-east-1.amazonaws.com/prod/
```

### 6. Build and deploy frontend

```bash
npm install
npm run build

aws s3 sync dist/ s3://YOUR_FRONTEND_BUCKET_NAME --delete --region us-east-1
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*" --region us-east-1
```

### 7. SES configuration

In the AWS console → SES → Verified identities, verify:
1. Your sender email (set in `backend/stacks/frontend_stack.py` as `SES_FROM_ADDRESS`)
2. Any recipient emails (required while SES is in sandbox mode)

---

## API Reference

### Auth API (`/auth/*`) — no authentication required

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register new account. Sends OTP to email. |
| POST | `/auth/verify` | Verify 6-digit OTP from Cognito email. |
| POST | `/auth/resend-otp` | Resend verification code. |
| POST | `/auth/login` | Login. Returns `idToken`, `accessToken`, `refreshToken`. |
| POST | `/auth/refresh` | Refresh access token. |
| POST | `/auth/logout` | Global sign out. |
| POST | `/auth/forgot-password` | Send password reset code to email. |
| POST | `/auth/confirm-forgot-password` | Submit reset code + new password. |
| POST | `/auth/change-password` | Change password (requires current password). |
| POST | `/auth/update-email` | Initiate email address change. |
| POST | `/auth/verify-email-change` | Confirm email change with verification code. |
| POST | `/auth/delete-account` | Delete account and all associated data. |

### Upload API (`/uploads/*`) — Bearer `idToken` required

| Method | Path | Description |
|---|---|---|
| POST | `/uploads/presigned-url` | Get S3 presigned URL for direct upload. |
| POST | `/uploads/confirm` | Confirm upload complete → triggers pipeline. |
| GET | `/uploads` | List your uploaded resumes. |
| GET | `/uploads/{uploadId}` | Get upload status (`PENDING`→`PARSING`→`ANALYZING`→`COMPLETE`). |
| GET | `/uploads/{uploadId}/view-url` | Get presigned URL to view the original resume file. |
| DELETE | `/uploads/{uploadId}` | Delete resume file and upload record. |

### Results API (`/results/*`) — Bearer `idToken` required

| Method | Path | Description |
|---|---|---|
| GET | `/results` | List analysis results (optional `?uploadId=`). |
| GET | `/results/{resultId}` | Get full analysis report. |
| DELETE | `/results/{resultId}` | Delete analysis report (upload record reverts to ANALYZING). |

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

## Data Flow

1. **Register** → Cognito creates user, sends 6-digit OTP to email
2. **Verify OTP** → Cognito confirms user
3. **Login** → Cognito returns JWT tokens
4. **Upload Resume** → Frontend gets presigned S3 URL, uploads directly, calls `/confirm`
5. **Parse** → S3 event triggers Parser Lambda → pypdf (PDF) or Textract (image) extracts text
6. **Analyze** → Analyzer Lambda calls Tavily for live market data, then Bedrock Claude 3 Haiku with resume text
7. **Results** → Results Worker aggregates into DynamoDB; SES completion email sent
8. **View Report** → Frontend polls `/uploads/{id}` until `COMPLETE`, then loads `/results/{resultId}`
9. **Find Jobs** → Jobs Lambda searches Adzuna for live listings matching the resume's top roles
10. **Tailored Resume** → Jobs Lambda calls Bedrock to rewrite the resume for a specific job (markdown or LaTeX)
11. **Track Applications** → Kanban board (`/tracker`) stores and updates job application records

---

## Report Contents (from Bedrock + Tavily)

- **Resume Score** (0–100) with honest rubric-based scoring
- **Profile Summary**
- **Resume Section-by-Section Review** (Professional Summary, Work Experience, Skills, Education, Presentation)
- **Critical Improvements** (top 5 actionable fixes)
- **Top 5 Job Roles** with match %, resume gaps, application tips, and 5 target companies each
- **7 Job Search Strategies** tailored to the candidate (informed by real-time Tavily job market data)
- **Skills to Highlight** + **Skills to Develop**
- **Key Achievements**

---

## Project Structure

```
├── backend/
│   ├── app.py                    
│   ├── cdk.json
│   ├── requirements.txt
│   ├── stacks/
│   │   ├── auth_stack.py         
│   │   ├── upload_stack.py       
│   │   ├── parser_stack.py       
│   │   ├── analyzer_stack.py     
│   │   ├── results_stack.py      
│   │   ├── frontend_stack.py     
│   │   ├── jobs_stack.py         
│   │   └── applications_stack.py 
│   └── lambdas/
│       ├── auth_service/
│       ├── upload_service/
│       ├── parser_service/
│       ├── analyzer_service/
│       ├── results_service/
│       ├── notification_service/
│       ├── jobs_service/
│       └── applications_service/
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── services/api.js
    │   └── components/
    │       ├── Auth/{Register,VerifyOTP,Login,ForgotPassword,Profile}.jsx
    │       ├── Resume/ResumeUpload.jsx
    │       ├── Report/{ReportView,RoleDetail,ReportPDF}.jsx
    │       ├── Jobs/{JobDetail,JobsSection,TailoredResumeEditor}.jsx
    │       └── Tracker/{TrackerBoard,ApplicationDetail}.jsx
    ├── package.json
    └── .env.example
```

---

## Destroy Resources

```bash
cd backend
cdk destroy --all --force -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

> All DynamoDB tables and S3 buckets use `RemovalPolicy.DESTROY` for easy cleanup in dev/class environments.
