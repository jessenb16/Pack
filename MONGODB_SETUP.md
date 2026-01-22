# MongoDB Atlas Setup Guide

## Step 1: Create MongoDB Atlas Account

1. Go to https://www.mongodb.com/cloud/atlas
2. Sign up for a free account (or sign in if you have one)
3. Create a new project (or use existing)

## Step 2: Create a Cluster

1. Click "Build a Database"
2. Choose **FREE (M0)** tier
3. Select a cloud provider and region (choose closest to you)
4. Name your cluster (e.g., "Pack-Cluster")
5. Click "Create"

## Step 3: Create Database User

1. Go to "Database Access" in the left sidebar
2. Click "Add New Database User"
3. Choose "Password" authentication
4. Enter username and password (save these!)
5. Set privileges to "Atlas admin" (or "Read and write to any database")
6. Click "Add User"

## Step 4: Whitelist Your IP

1. Go to "Network Access" in the left sidebar
2. Click "Add IP Address"
3. For development, click "Allow Access from Anywhere" (0.0.0.0/0)
   - **Note**: For production, only allow specific IPs
4. Click "Confirm"

## Step 5: Get Connection String

1. Go to "Database" in the left sidebar
2. Click "Connect" on your cluster
3. Choose "Connect your application"
4. Select "Python" and version "3.6 or later"
5. Copy the connection string
   - It looks like: `mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`

## Step 6: Update Connection String

1. Replace `<username>` with your database username
2. Replace `<password>` with your database password
3. Add database name at the end: `...mongodb.net/pack?retryWrites=true&w=majority`

**Final format:**
```
mongodb+srv://yourusername:yourpassword@cluster0.xxxxx.mongodb.net/pack?retryWrites=true&w=majority
```

## Step 7: Add to Backend .env

Create or update `backend/.env`:

```env
MONGODB_URI=mongodb+srv://yourusername:yourpassword@cluster0.xxxxx.mongodb.net/pack?retryWrites=true&w=majority
DATABASE_NAME=pack
```

## Step 8: Test Connection

Start your backend and check the logs - you should see:
```
MongoDB connection established successfully
```

Or test manually:
```python
from pymongo import MongoClient
client = MongoClient("your_connection_string")
client.admin.command('ping')
print("Connected successfully!")
```

## Next Steps

After MongoDB is set up:
1. Start the backend server
2. The backend will automatically create collections when needed
3. Test by signing up - your user should be synced to MongoDB

## Troubleshooting

**Connection timeout**: Make sure your IP is whitelisted
**Authentication failed**: Check username/password in connection string
**Database not found**: The database will be created automatically on first use

