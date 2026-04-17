# Resume Analyzer — Cloud Computing Group Project

A serverless resume analysis platform built entirely on AWS using Python CDK.

---

## Architecture Overview

```
User → CloudFront (React SPA)
     → Auth API Gateway  → Lambda → Cognito (OTP email verification)
     → App API Gateway   → Lambda → S3 (presigned upload)
                                  ↓
                               SQS ParseQueue
                                  ↓
                         Parser Lambda → Textract
                                  ↓
                               SQS AnalysisQueue
                                  ↓
                       Analyzer Lambda → Bedrock (Claude 3 Haiku)
                                  ↓
                            SNS ResultsTopic
                           /                \
                  SQS ResultsQueue     SQS NotificationQueue
                         ↓                      ↓
               Results Worker Lambda    Notification Lambda → SES email
                         ↓
                   DynamoDB ResultsTable
                         ↓
              Results API Lambda → Frontend
```

---

## Microservice Assignments

| # | Microservice | Student | Stack | AWS Services |
|---|---|---|---|---|
| 1 | Auth Service | Student 1 | `AuthStack` | Cognito, Lambda, API GW, DynamoDB |
| 2 | Upload Service | Student 1 | `UploadStack` | S3, Lambda, API GW, SQS |
| 3 | Parser Service | Student 2 | `ParserStack` | Lambda, Textract, S3, SQS, DynamoDB |
| 4 | Analyzer Service | Student 2 | `AnalyzerStack` | Lambda, Bedrock, S3, SNS, SQS, DynamoDB |
| 5 | Results Service | Student 3 | `ResultsStack` | Lambda, DynamoDB, API GW, SQS |
| 6 | Notification + Frontend | Student 3 | `FrontendStack` | Lambda, SES, S3, CloudFront |

---

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.12+
- Node.js 18+
- AWS CDK v2 (`npm install -g aws-cdk`)
- Amazon Bedrock: enable **Claude 3 Haiku** model in `us-east-1` via the AWS console
- Amazon SES: verify your sender email address in SES (sandbox mode requires verifying recipients too)

---

## Setup & Deployment

### 1. Backend (CDK)

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Bootstrap CDK (once per account/region)
cdk bootstrap --context account=YOUR_ACCOUNT_ID --context region=us-east-1

# Deploy all stacks in dependency order
cdk deploy --all --context account=YOUR_ACCOUNT_ID --context region=us-east-1
```

After deploy, note the outputs:
- `AuthStack.AuthApiUrl`
- `UploadStack.AppApiUrl`
- `FrontendStack.CloudFrontUrl`
- `FrontendStack.FrontendBucketName`

### 2. Frontend

```bash
cd frontend
npm install

# Create environment file
cp .env.example .env.local
# Edit .env.local with your deployed API URLs

npm run dev          # local development
npm run build        # production build → dist/
```

### 3. Deploy Frontend to S3 + CloudFront

```bash
aws s3 sync frontend/dist/ s3://YOUR_FRONTEND_BUCKET_NAME --delete
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

### 4. SES Configuration

In the AWS console → SES → Verified identities, add and verify:
1. Your sender email (`noreply@yourdomain.com`)
2. Any recipient emails you want to test with (sandbox only)

Set the environment variable before deploying FrontendStack:
```bash
export SES_FROM_ADDRESS=noreply@yourdomain.com
```

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

### App API (`/uploads/*`, `/results/*`) — Bearer `idToken` required

| Method | Path | Description |
|---|---|---|
| POST | `/uploads/presigned-url` | Get S3 presigned URL for direct upload. |
| POST | `/uploads/confirm` | Confirm upload complete → triggers pipeline. |
| GET | `/uploads` | List your uploaded resumes. |
| GET | `/uploads/{uploadId}` | Get upload status (`PENDING`→`PARSING`→`ANALYZING`→`COMPLETE`). |
| GET | `/results` | List analysis results (optional `?uploadId=`). |
| GET | `/results/{resultId}` | Get full analysis report. |

---

## Data Flow

1. **Register** → Cognito creates user, sends 6-digit OTP to email
2. **Verify OTP** → Cognito confirms user
3. **Login** → Cognito returns JWT tokens
4. **Upload Resume** → Frontend gets presigned S3 URL, uploads directly, calls `/confirm`
5. **Parse** → S3 event triggers Parser Lambda → Textract extracts text
6. **Analyze** → Analyzer Lambda calls Bedrock Claude 3 Haiku with resume text
7. **Results** → Results Worker aggregates into DynamoDB; SES email sent
8. **View Report** → Frontend polls `/uploads/{id}` until `COMPLETE`, then loads `/results/{resultId}`

---

## Report Contents (from Bedrock)

- **Resume Score** (0–100)
- **Profile Summary**
- **Top 5 Job Roles** with match %, reason, and 5 target companies each
- **5 Job Search Strategies** tailored to the candidate
- **Skills to Highlight** + **Skills to Develop**
- **Key Achievements**

---

## Project Structure

```
├── backend/
│   ├── app.py                    # CDK app entry
│   ├── cdk.json
│   ├── requirements.txt
│   ├── stacks/
│   │   ├── auth_stack.py         # Student 1
│   │   ├── upload_stack.py       # Student 1
│   │   ├── parser_stack.py       # Student 2
│   │   ├── analyzer_stack.py     # Student 2
│   │   ├── results_stack.py      # Student 3
│   │   └── frontend_stack.py     # Student 3
│   └── lambdas/
│       ├── auth_service/
│       ├── upload_service/
│       ├── parser_service/
│       ├── analyzer_service/
│       ├── results_service/
│       └── notification_service/
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── services/api.js
    │   └── components/
    │       ├── Auth/{Register,VerifyOTP,Login}.jsx
    │       ├── Resume/ResumeUpload.jsx
    │       └── Report/ReportView.jsx
    ├── package.json
    └── .env.example
```

---

## Destroy Resources

```bash
cd backend
cdk destroy --all --context account=YOUR_ACCOUNT_ID --context region=us-east-1
```

> All DynamoDB tables and S3 buckets use `RemovalPolicy.DESTROY` for easy cleanup in dev/class environments.
