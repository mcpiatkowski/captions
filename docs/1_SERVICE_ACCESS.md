# AWS Service Access Guide

## Required AWS Services
- Amazon S3 (storage)
- Amazon Transcribe (speech-to-text)
- Amazon Translate (text translation)
- IAM (identity and access management)

## 1. Set Up AWS Account
If you don't have an AWS account:
1. Go to [AWS Console](https://aws.amazon.com/)
2. Click "Create an AWS Account"
3. Follow the registration process

## 2. Install and Configure AWS CLI

### Installation
```bash
# macOS (with Homebrew)
brew install awscli

# Linux (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install -y awscli

# Windows
# Download and run the installer from: https://aws.amazon.com/cli/
```

### Configuration
```bash
aws configure
```
You'll be prompted to enter:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., us-east-1)
- Default output format (json recommended)

## 3. Verify AWS CLI Configuration
```bash
aws sts get-caller-identity
```
This should return your account ID, user ID, and ARN.

## 4. Verify S3 Access
```bash
# List all buckets
aws s3 ls

# Create a test bucket (replace with unique name)
aws s3 mb s3://transcript-test-bucket-$(date +%s)

# Remove test bucket
aws s3 rb s3://transcript-test-bucket-[timestamp]
```

## 5. Verify Transcribe Access
```bash
# List available transcription jobs
aws transcribe list-transcription-jobs

# Check available language models
aws transcribe list-language-models
```

## 6. Verify Translate Access
```bash
# List available languages for translation
aws translate list-languages

# Test translation with a sample text
aws translate translate-text \
  --text "This is a test sentence." \
  --source-language-code "en" \
  --target-language-code "pl"
```

## 7. Create IAM Policy for Transcription and Translation

If you don't have sufficient permissions, create a policy and attach it to your user:

1. Create a policy file named `transcription-translation-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "transcribe:*",
        "translate:*",
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "s3:CreateBucket",
        "s3:ListAllMyBuckets"
      ],
      "Resource": "*"
    }
  ]
}
```

2. Create the policy:
```bash
aws iam create-policy \
  --policy-name TranscriptionTranslationPolicy \
  --policy-document file://transcription-translation-policy.json
```

3. Attach policy to your user (replace USERNAME with your AWS username):
```bash
aws iam attach-user-policy \
  --user-name USERNAME \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/TranscriptionTranslationPolicy
```
(Replace ACCOUNT_ID with your AWS account ID from step 3)

## 8. Troubleshooting Access Issues

### "Access Denied" Errors
- Verify credentials are correct in `~/.aws/credentials`
- Check if your user has the required permissions
- Ensure bucket policies allow access

### Region Issues
- Make sure you're using the correct region with `--region` flag or in AWS configuration
- Some services may not be available in all regions

### Service Quotas
- Check service limits: `aws service-quotas list-service-quotas --service-code transcribe`
- Request increase if needed through AWS console

## 9. Cost Management
- Set up AWS Budget alerts to monitor spending
- Use AWS Cost Explorer to analyze service costs
- Remember that S3 storage, Transcribe API, and Translate API calls all incur charges
- Consider using batch processing for Translate to reduce costs

## 10. Security Best Practices
- Use IAM roles instead of access keys when possible
- Follow the principle of least privilege for permissions
- Use MFA for AWS account access
- Regularly rotate access keys