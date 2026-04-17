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

### 1. Backend setup

```bash
cd backend

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate.bat

pip install -r requirements.txt

# Bootstrap CDK once per account/region
cdk bootstrap -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

### 2. Deploy all stacks

```bash
cdk deploy --all --require-approval never -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

Note the following values from CDK output:

| CDK Output | Use |
|---|---|
| `ResumeAnalyzerAuth.AuthApiUrl` | `VITE_AUTH_API_URL` in `.env.local` |
| `ResumeAnalyzerUpload.AppApiUrl` | `VITE_APP_API_URL` in `.env.local` |
| `ResumeAnalyzerResults.ResultsApiUrl` | `VITE_RESULTS_API_URL` in `.env.local` |
| `ResumeAnalyzerFrontend.CloudFrontUrl` | `URL` in `.env.local` + update step below |
| `ResumeAnalyzerFrontend.FrontendBucketName` | `FRONTEND_BUCKET_NAME` in `.env.local` |
| `ResumeAnalyzerFrontend.CloudFrontDistributionId` | `DISTRIBUTION_ID` in `.env.local` |

### 3. Update FRONTEND_URL and redeploy

The SES notification email links back to your app. Update the hardcoded URL in `backend/stacks/frontend_stack.py`:

```python
"FRONTEND_URL": "https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net",
```

Then redeploy to apply it:

```bash
cdk deploy ResumeAnalyzerFrontend --require-approval never -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

### 4. Configure frontend environment

```bash
cd ../frontend
cp .env.example .env.local
# Fill in .env.local with the CDK output values from step 2
```

### 5. Build and deploy frontend

```bash
npm install
npm run build

aws s3 sync dist/ s3://YOUR_FRONTEND_BUCKET_NAME --delete --region us-east-1
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*" --region us-east-1
```

### 6. SES configuration

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

### App API (`/uploads/*`, `/results/*`) — Bearer `idToken` required

| Method | Path | Description |
|---|---|---|
| POST | `/uploads/presigned-url` | Get S3 presigned URL for direct upload. |
| POST | `/uploads/confirm` | Confirm upload complete → triggers pipeline. |
| GET | `/uploads` | List your uploaded resumes. |
| GET | `/uploads/{uploadId}` | Get upload status (`PENDING`→`PARSING`→`ANALYZING`→`COMPLETE`). |
| GET | `/uploads/{uploadId}/view-url` | Get presigned URL to view the original resume file. |
| DELETE | `/uploads/{uploadId}` | Delete resume file and upload record. |
| GET | `/results` | List analysis results (optional `?uploadId=`). |
| GET | `/results/{resultId}` | Get full analysis report. |
| DELETE | `/results/{resultId}` | Delete analysis report (upload record reverts to ANALYZING). |

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
│   │   └── frontend_stack.py     
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
cdk destroy --all --force -c account=YOUR_ACCOUNT_ID -c region=us-east-1
```

> All DynamoDB tables and S3 buckets use `RemovalPolicy.DESTROY` for easy cleanup in dev/class environments.
