# Pack: Production Deployment

**What you're doing:** Putting the backend on **Lightsail** (AWS), the frontend on **Vercel**, and using **GitHub Actions** to build and deploy the backend when you push to `main`. MongoDB, S3, and Clerk stay as-is; you use **separate** prod database, bucket, and Clerk app so dev stays isolated.

**No code changes.** Everything is configured with environment variables.

---

## Before you start

- AWS account (for ECR, S3, Lightsail)
- MongoDB Atlas account (prod cluster or new database)
- Clerk account (prod application)
- Vercel account
- GitHub repo with the Pack code

Pick **one region** (e.g. `us-east-1`) and use it for ECR and Lightsail.

---

## The 10 steps (do in order)

Follow these in order. Write down the two URLs when you get them (Vercel URL in step 4, Lightsail URL in step 5).

---

### Step 1: MongoDB for production

**Goal:** A production database and connection string.

1. In MongoDB Atlas, create a **new database** for production (e.g. `pack_prod`). You can use the same cluster as dev and just add a new database name in the connection string path.
2. Get the **connection string** and put the prod database name in the path (e.g. `...mongodb.net/pack_prod?retryWrites=...`).
3. In Atlas → Network Access, allow access (e.g. `0.0.0.0/0` for now so Lightsail can connect).
4. In Atlas → your cluster → Database → Browse Collections → open the **`documents`** collection (create it if needed) → **Search Indexes** → Create Search Index. Create a **vector** index:
   - **Name:** `vector_index`
   - **Vector path:** `ai_context.embedding`
   - **Dimensions:** 1536
   - **Filter field:** `org_id`
5. Write down the connection string and database name; you’ll need them in Lightsail (step 5).

---

### Step 2: Clerk production app

**Goal:** Production Clerk keys (no domains or webhooks yet).

1. In Clerk, create or switch to a **production** application (separate from the one you use for localhost).
2. Copy the **publishable key** and **secret key**.
3. Don’t add domains or webhooks yet. You’ll add those after you have the Vercel and Lightsail URLs (steps 6 and 7).

---

### Step 3: AWS – ECR, S3, GitHub secrets

**Goal:** A place for your Docker image (ECR), a prod S3 bucket, and GitHub able to push to ECR and deploy to Lightsail.

1. **ECR (Docker image registry)**  
   - In AWS Console → ECR → Create repository.  
   - Name: e.g. `pack-backend`.  
   - Region: same as you’ll use for Lightsail (e.g. `us-east-1`).  
   - Create. Note the **URI** (e.g. `244086559221.dkr.ecr.us-east-1.amazonaws.com/pack-backend`).

2. **S3 bucket for production**  
   - Create a new bucket (e.g. `pack-uploads-prod`). Keep it private.  
   - Permissions → CORS: add a rule that allows your **production** frontend origin (you’ll set this after you have the Vercel URL; for now you can use a placeholder like `https://your-app.vercel.app` and update it later, or add it in step 9). Example CORS:
   ```json
   [{"AllowedHeaders":["*"],"AllowedMethods":["GET","PUT","POST","DELETE"],"AllowedOrigins":["https://your-app.vercel.app"],"ExposeHeaders":[]}]
   ```

3. **IAM user for GitHub Actions**  
   - Create an IAM user that can: push to your ECR repo, deploy to Lightsail, and access the S3 bucket (if needed).  
   - Create **access keys** for that user.  
   - In **GitHub** → your repo → Settings → Secrets and variables → Actions: add secrets **`AWS_ACCESS_KEY_ID`** and **`AWS_SECRET_ACCESS_KEY`** with those keys.

---

### Step 4: Vercel – frontend (get the URL)

**Goal:** Frontend deployed and a **Vercel URL** to use in Clerk and Lightsail.

1. In Vercel, create a new project and connect your GitHub repo.
2. Set **Root Directory** to **`frontend`**.
3. Add environment variables:
   - **`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`** = your **production** Clerk publishable key (from step 2).
   - **`NEXT_PUBLIC_API_URL`** = `https://placeholder.invalid` (temporary so the build works).
4. Deploy (e.g. push to `main` or trigger deploy in Vercel).
5. **Write down the Vercel URL** (e.g. `https://pack-xxx.vercel.app`). You’ll use it in steps 5, 6, and 9.

---

### Step 5: Lightsail – backend (get the URL)

**Goal:** Backend running in Lightsail and a **Lightsail URL** to use in Vercel and Clerk.

1. In AWS Console, open **Lightsail** and set the region to the **same region as your ECR repo** (e.g. Virginia / us-east-1).

2. **Create a Container Service**  
   - Containers → Create container service.  
   - Choose a size (e.g. Nano or Micro).  
   - Name: e.g. `pack-backend`.  
   - Create.

3. **Let Lightsail use ECR**  
   - Your image is in ECR (private). Lightsail needs permission to pull it.  
   - In Lightsail, find the option to **enable ECR** / link your AWS account (e.g. under your service or “Account and resource access”).  
   - Follow the prompts so Lightsail can pull from your ECR repo.  
   - [AWS doc: Grant Lightsail access to ECR](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-service-ecr-private-repo-access.html)

4. **Create a deployment**  
   - On your container service → Create deployment (or Deployments → Create).  
   - **Container name:** e.g. `pack-backend`.  
   - **Image:** Your full ECR image URI with tag, e.g. `244086559221.dkr.ecr.us-east-1.amazonaws.com/pack-backend:latest`.  
   - **Port:** `8000`.  
   - **Public endpoint:** Turn it on. Container: `pack-backend`, port: `8000`, health check path: `/health`.  
   - **Environment variables:** Add every variable from the **Lightsail env** table in the Reference section below. Use **production** values: prod MongoDB URI and DB name, prod S3 bucket, prod Clerk secret key, OpenAI key, AWS access key and secret for S3, and **`FRONTEND_URL`** = your **Vercel URL from step 4**.  
   - Do **not** add `CLERK_WEBHOOK_SECRET` yet (you add it in step 8).  
   - Save / deploy. Lightsail will pull the image from ECR and start the container (your image must already be in ECR – you built and pushed it earlier).

5. When the deployment is running, find the **public URL** of the service (e.g. on the service page under Endpoint or Public domain).  
6. **Write down the Lightsail URL** (e.g. `https://pack-backend-xxx.us-east-1.cs.amazonlightsail.com`). You’ll use it in steps 7, 8, and 9.

---

### Step 6: Clerk – add your frontend domain

**Goal:** Clerk allows your production frontend URL.

1. In your **production** Clerk application → Domains (or Settings).
2. Add your **Vercel URL** (from step 4) as an allowed redirect and sign-in/sign-up origin.

---

### Step 7: Clerk – add webhook

**Goal:** Clerk can notify your backend when org/user events happen.

1. In your production Clerk app → **Webhooks** → Add endpoint.
2. **Endpoint URL:** `https://<your-lightsail-url>/api/webhooks/clerk` (use the Lightsail URL from step 5; no trailing slash).
3. Subscribe to the events your backend handles (see `backend/app/api/webhooks.py` for which events you use).
4. Create the webhook and copy the **signing secret** (starts with `whsec_...`). You’ll add it to Lightsail in step 8.

---

### Step 8: Lightsail – add webhook secret

**Goal:** Backend can verify Clerk webhooks.

1. In Lightsail, open your container service and edit the deployment (or container config).
2. Add environment variable: **`CLERK_WEBHOOK_SECRET`** = the signing secret you copied in step 7.
3. Save and create a **new deployment** so the running container restarts with the new env.

---

### Step 9: Vercel – point to the real backend

**Goal:** Frontend calls your Lightsail backend instead of the placeholder.

1. In Vercel → your project → Settings → Environment Variables.
2. Set **`NEXT_PUBLIC_API_URL`** = your **Lightsail URL** (from step 5). Remove the placeholder.
3. Redeploy (e.g. trigger redeploy in Vercel or push a small change).

---

### Step 10: Done

- Clerk has your domain and webhook; Lightsail has the webhook secret; Vercel has the real API URL.
- **Ongoing deploys:** Push to `main` → GitHub Actions builds the backend image, pushes to ECR, and deploys to Lightsail; Vercel deploys the frontend automatically.

---

## Reference: env vars and commands

Use these when you need the exact variable names or commands.

---

### Lightsail environment variables (steps 5 and 8)

Set these in the Lightsail container deployment. All values are **production**.

| Variable | Example / notes |
|----------|------------------|
| `MONGODB_URI` | Prod connection string with DB in path (e.g. `.../pack_prod?retryWrites=...`) |
| `DATABASE_NAME` | e.g. `pack_prod` |
| `CLERK_SECRET_KEY` | Prod Clerk secret key |
| `CLERK_WEBHOOK_SECRET` | Add in step 8: `whsec_...` from Clerk webhook |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Prod Clerk publishable key (same as Vercel) |
| `NEXT_PUBLIC_CLERK_FRONTEND_API` | If your app uses it |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `AWS_ACCESS_KEY_ID` | IAM user key (S3 access) |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret |
| `AWS_S3_BUCKET_NAME` | Prod bucket (e.g. `pack-uploads-prod`) |
| `AWS_REGION` | e.g. `us-east-1` |
| `FRONTEND_URL` | Vercel URL (e.g. `https://pack-xxx.vercel.app`) for CORS |

Optional: `VECTOR_SEARCH_SCORE_THRESHOLD`, `MAX_CONTENT_LENGTH`, `CHECKPOINT_TTL_DAYS`, `DEBUG=false`.

**Note:** When you modify a deployment in Lightsail, the UI often does **not** show existing environment variables—you have to re-add them. Use the table above as your checklist and keep your real values in a secure place (e.g. password manager or private doc) so you can paste them in when creating or editing a deployment.

---

### Vercel environment variables (steps 4 and 9)

| Variable | When | Value |
|----------|------|--------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Step 4 | Prod Clerk publishable key |
| `NEXT_PUBLIC_API_URL` | Step 4 | `https://placeholder.invalid` (temporary) |
| `NEXT_PUBLIC_API_URL` | Step 9 | Lightsail URL (replace placeholder) |

---

### Build and push Docker image to ECR (manual)

If you need to build and push the image yourself (from repo root):

```bash
# Set these (same region as Lightsail)
export AWS_ACCOUNT_ID=244086559221
export AWS_REGION=us-east-1
export ECR_REPO=pack-backend

# 1. Log in to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# 2. Build (use linux/amd64 so the image runs on Lightsail; required on Apple Silicon)
docker build --platform linux/amd64 -t pack-backend:latest ./backend

# 3. Tag for ECR (quote full image name so :latest is preserved)
docker tag pack-backend:latest "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest"

# 4. Push
docker push "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest"
```

---

### After step 10: how you deploy

- **Backend:** Push to `main` → GitHub Actions builds the image, pushes to ECR, and deploys to Lightsail.
- **Frontend:** Push to `main` → Vercel builds and deploys.

**Manual Lightsail deploy** (if you need to trigger a deploy without pushing code):

```bash
aws lightsail create-container-service-deployment \
  --service-name pack-backend \
  --containers '{"pack-backend":{"image":"244086559221.dkr.ecr.us-east-1.amazonaws.com/pack-backend:latest","ports":{"8000":"HTTP"}}}' \
  --public-endpoint '{"containerName":"pack-backend","containerPort":8000,"healthCheck":{"path":"/health"}}'
```

(Replace account ID, region, repo name, and service name if yours are different.)

---

### Dev vs production (reminder)

| Resource | Dev | Production |
|----------|-----|------------|
| MongoDB | e.g. `pack` | e.g. `pack_prod` (new DB or cluster) |
| S3 | Dev bucket | e.g. `pack-uploads-prod` |
| Clerk | Dev app (localhost) | Prod app (Vercel URL, webhook) |

All of this is done with different env vars; no code changes.
