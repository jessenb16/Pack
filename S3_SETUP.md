# AWS S3 Setup Guide for Pack

This guide will help you set up AWS S3 for storing family documents and thumbnails securely using signed URLs.

## Step 1: Create an AWS Account (if needed)

1. Go to https://aws.amazon.com/
2. Click "Create an AWS Account"
3. Complete the signup process

## Step 2: Create an S3 Bucket

1. Log in to AWS Console: https://console.aws.amazon.com/
2. Search for "S3" in the top search bar
3. Click "Create bucket"
4. Configure:
   - **Bucket name**: `pack-family-archive` (must be globally unique)
   - **AWS Region**: `us-east-1` (or your preferred region)
   - **Object Ownership**: ACLs disabled (recommended)
   - **Block Public Access**: ✅ **KEEP ALL CHECKED** (bucket should be private!)
   - **Bucket Versioning**: Disable (unless you need it)
   - **Default encryption**: Enable (SSE-S3 is fine)
5. Click "Create bucket"

> **Important**: Keep the bucket **private**! We use signed URLs for secure access, so public access is not needed.

## Step 3: Configure CORS (for direct uploads if needed)

1. Open your bucket
2. Go to "Permissions" tab
3. Scroll to "Cross-origin resource sharing (CORS)"
4. Add this configuration:

```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
        "AllowedOrigins": ["http://localhost:3000", "https://yourdomain.com"],
        "ExposeHeaders": []
    }
]
```

## Step 4: Create IAM User for API Access

1. Search for "IAM" in AWS Console
2. Click "Users" → "Create user"
3. User name: `pack-s3-user`
4. Click "Next"
5. Select "Attach policies directly"
6. Click "Create policy"
7. Switch to "JSON" tab and paste:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::YOUR-BUCKET-NAME",
                "arn:aws:s3:::YOUR-BUCKET-NAME/*"
            ]
        }
    ]
}
```

Replace `YOUR-BUCKET-NAME` with your actual bucket name.

8. Name the policy: `PackS3Access`
9. Click "Create policy"
10. Go back to user creation, refresh policies, search for "PackS3Access", select it
11. Click "Next" → "Create user"

## Step 5: Create Access Keys

1. Click on the user you just created
2. Go to "Security credentials" tab
3. Scroll to "Access keys"
4. Click "Create access key"
5. Select "Application running outside AWS"
6. Click "Next" → "Create access key"
7. **Important**: Copy both:
   - Access key ID
   - Secret access key (shown only once - save it!)

## Step 6: Update Environment Variables

Add these to your `backend/.env` file:

```env
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_S3_BUCKET_NAME=pack-family-archive
AWS_REGION=us-east-1
```

Replace with your actual values.

## How Signed URLs Work

Pack uses **signed URLs** for secure file access:

- ✅ **Bucket stays private** - no public access needed
- ✅ **URLs expire after 1 hour** - automatic security
- ✅ **Only authenticated users** can get signed URLs
- ✅ **Files are not publicly accessible** - even with the URL pattern

When a user requests documents, the backend:
1. Retrieves S3 keys from MongoDB
2. Generates time-limited signed URLs (1 hour expiration)
3. Returns signed URLs to the frontend
4. Frontend uses these URLs to display images

## Security Notes

- **Never commit** your `.env` file to git
- The IAM user only has S3 permissions (principle of least privilege)
- Consider using AWS Secrets Manager for production
- Signed URLs expire after 1 hour for security

## Cost Optimization

- **S3 Free Tier**: 5GB storage, 20,000 GET requests, 2,000 PUT requests per month
- **After free tier**: ~$0.023/GB storage, $0.0004 per 1,000 requests
- Monitor usage in AWS Billing Dashboard
- Consider lifecycle policies to archive old files to Glacier (cheaper)

## Testing

After setup, test by uploading a document through your app. The files should be:
- Stored in S3 at: `families/{org_id}/originals/{filename}` and `families/{org_id}/thumbnails/{filename}`
- Accessible via signed URLs that expire after 1 hour
- Not publicly accessible (bucket remains private)

