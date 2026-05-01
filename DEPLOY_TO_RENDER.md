# Deploying Premium Pet Clinic to Render.com

This guide walks you through getting the app live on the internet using
**Render.com** (free tier) + **PostgreSQL** (free tier).

---

## What you need

- A free [GitHub](https://github.com) account
- A free [Render](https://render.com) account

---

## Step 1 — Push the project to GitHub

1. Go to https://github.com/new and create a **new repository** (e.g. `PremiumPetClinic`).  
   ✅ Set it to **Private** so your clinic data stays yours.

2. Open a terminal / command prompt inside this folder and run:

```bash
git init
git add .
git commit -m "Initial cloud version"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/PremiumPetClinic.git
git push -u origin main
```

> Replace `YOUR_USERNAME` with your actual GitHub username.

---

## Step 2 — Create the app on Render

### Option A — Automatic (recommended)

Render can read the `render.yaml` file you already have and set everything up
in one click.

1. Log in to https://dashboard.render.com
2. Click **New → Blueprint**
3. Connect your GitHub account and select the `PremiumPetClinic` repository
4. Render reads `render.yaml` and shows you two resources to create:
   - **Web Service** — `premium-pet-clinic`
   - **PostgreSQL Database** — `premium-pet-clinic-db`
5. Click **Apply** — Render builds and deploys everything automatically.

### Option B — Manual (if Blueprint doesn't work)

#### 2a. Create the database first

1. Dashboard → **New → PostgreSQL**
2. Name: `premium-pet-clinic-db`
3. Plan: **Free**
4. Click **Create Database**
5. Copy the **Internal Database URL** from the database's info page.

#### 2b. Create the web service

1. Dashboard → **New → Web Service**
2. Connect the `PremiumPetClinic` GitHub repository
3. Fill in:
   | Field | Value |
   |-------|-------|
   | **Name** | `premium-pet-clinic` |
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |
   | **Plan** | Free |

4. Add **Environment Variables**:
   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | *(paste the Internal Database URL from 2a)* |
   | `VETAPP_SECRET_KEY` | *(any long random string, e.g. `my-super-secret-key-2024`)* |
   | `VETAPP_ADMIN_USER` | `Admin` |
   | `VETAPP_ADMIN_PASS` | `1234` *(change after first login!)* |
   | `VETAPP_TITLE` | `Premium Pet Clinic` |

5. Click **Create Web Service**

---

## Step 3 — Wait for the build

Render will:
1. Install Python packages (~1–2 min)
2. Start the app — on first boot it automatically **creates all database tables**
3. Seed default configuration data (vets, rooms, services, roles)

When the status shows **Live**, click the URL at the top of the service page.

---

## Step 4 — Log in

```
Username: Admin
Password: 1234
```

⚠️ **Change the password immediately** in Settings → Users after first login.

---

## Seed demo data (optional)

If you want 10 demo owners / pets / bookings pre-loaded, run a one-time command
from the Render dashboard:

1. Go to your Web Service → **Shell** tab
2. Run:
```bash
python app.py --seed
```

---

## Environment variables reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | **(required)** | PostgreSQL connection string |
| `VETAPP_SECRET_KEY` | `elite-vet-secret-key-change-me` | Flask session secret — **change this!** |
| `VETAPP_ADMIN_USER` | `Admin` | Default admin username |
| `VETAPP_ADMIN_PASS` | `1234` | Default admin password |
| `VETAPP_TITLE` | `Premium Pet Clinic` | App name shown in the UI |
| `PORT` | `5000` | Injected automatically by Render |

---

## Updating the app

Whenever you make changes, just push to GitHub:

```bash
git add .
git commit -m "Your change description"
git push
```

Render automatically re-deploys within a minute.

---

## Free tier limits

| Resource | Free limit |
|----------|-----------|
| Web service | Spins down after 15 min of inactivity (cold start ~30 sec) |
| PostgreSQL | 1 GB storage, 97 days, then needs upgrade or recreation |

For a production clinic, upgrade to Render's **Starter** plan (~$7/month) to
keep the service always-on and the database permanent.
