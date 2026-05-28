# 🌱 Breathe ESG - Backend API

This is the **decoupled Django REST Framework (DRF) backend** for the **Breathe ESG Carbon Credits Analysis Platform**.  
It manages **multi-tenant architecture**, handles **complex CSV data uploads** (Utility, SAP, Travel), processes **asynchronous tasks**, and serves data to the **React/Vite frontend**.

## 🚀 Tech Stack

- **Framework:** Django 6.0.5 & Django REST Framework (DRF)
- **Language:** Python 3.14.3
- **Database:** PostgreSQL
- **Server:** Gunicorn + Uvicorn (ASGI for async support)
- **Static Files:** WhiteNoise
- **Deployment:** Render

## 🛠️ Local Development Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Sanjeevkumar-cs/Carbon-credits-analysis-backend.git
   cd backend
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up local database & run migrations:**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Run the local development server:**
   ```bash
   python manage.py runserver
   ```

## 📊 Generating Test Data

To test file upload models (**Utility Bills, SAP Procurement, Corporate Travel**), generate realistic messy CSVs locally:

```bash
cd scripts
python generate_sap_data.py
python generate_utility_data.py
python generate_travel_data.py
```

Upload the resulting `.csv` files via the **DRF Browsable API** or the **React frontend**.  
⚠️ _Do not run generators on the production server._

---

## ☁️ Render Production Deployment

This project is configured for **automated deployment on Render**.

### 1. Build Script (`build.sh`)

The repository includes a `build.sh` script that handles:

- Dependency installation
- Static file collection
- Database migrations
- Intelligent Superuser creation

```bash
#!/bin/bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Smart Superuser Creation
if [ "$CREATE_SUPERUSER" = "True" ]; then
    python manage.py shell -c "
import os
from django.contrib.auth.models import User
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if username and email and password:
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f'Superuser {username} created.')
    else:
        print('Superuser already exists.')
else:
    print('Missing environment variables for superuser creation.')
"
fi
```

### 2. Render Dashboard Configuration

- **Build Command:**

  ```bash
  bash build.sh
  ```

- **Start Command:**

  ```bash
  python -m gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker --env DJANGO_SETTINGS_MODULE=config.deployment_settings
  ```

- **Environment Variables:**
  - `SECRET_KEY`: Secure random string
  - `DJANGO_SETTINGS_MODULE`: `config.deployment_settings`
  - `CREATE_SUPERUSER`: `True` _(set to False after first deployment)_
  - `DJANGO_SUPERUSER_USERNAME`: `admin`
  - `DJANGO_SUPERUSER_EMAIL`: `admin@example.com`
  - `DJANGO_SUPERUSER_PASSWORD`: `[Your secure password]`

---

## ⚠️ Developer Notes & Lessons Learned

### 1. The "Silent Crash" (Windows vs. Linux Line Endings)

- **Bug:** Render build reported success but failed to install packages.
- **Cause:** `build.sh` created on Windows with `CRLF` endings.
- **Fix:** Save with **LF** endings. In VS Code → _Change End of Line Sequence_ → _LF_.

### 2. Automated Superuser Creation Loops

- **Bug:** `createsuperuser --noinput` crashed builds on redeploy.
- **Cause:** Tried to recreate existing user.
- **Fix:** Added existence check with `User.objects.filter(username=username).exists()`.

### 3. Server Error 500 on Data Submission

- **Bug:** Submitting records with blank optional fields caused 500 errors.
- **Cause:** PostgreSQL rejected empty fields without `null=True, blank=True`.
- **Fix:** Ensure optional fields include `null=True, blank=True`.

### 4. API Root "404 Not Found"

- **Bug:** Visiting base Render URL returned 404.
- **Reality:** Normal for decoupled API.
- **Fix:** Navigate to `/api/` or `/admin/`. Optionally add a custom JSON welcome view at root.

---

## ✅ Summary

This backend is designed for **scalable ESG carbon credit analysis**, with robust handling of **multi-tenant data**, **messy CSV uploads**, and **secure deployment** on Render.  
It is production-ready, with lessons learned baked into the architecture for **smooth deployments** and **error-free API operations**.

