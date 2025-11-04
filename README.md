# SRJ Strips Task Manager

A comprehensive task management system built with Streamlit and PostgreSQL.

## Features

- 📋 **Task Management** - Create, assign, and track tasks with priorities
- 👥 **User Management** - Manage employees, directors, and admins
- 🏢 **Departments & Designations** - Organize employees by departments
- 📢 **Notice Board** - Share announcements and updates
- 💬 **Chat System** - Real-time communication between team members
- 📊 **Admin Dashboard** - Complete overview of all data

## Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: PostgreSQL
- **Authentication**: bcrypt

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd demo-software
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate virtual environment:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Set up PostgreSQL database:
   - Create a database named `hrms_db`
   - Update database credentials in `task_manager.py` (lines 22-29)

6. Run the application:
```bash
streamlit run task_manager.py
```

## Configuration

### Local Development

For local development, the app will use default database settings. Update `get_db_connection()` function in `task_manager.py` if needed.

### Streamlit Cloud Deployment

1. Go to your app on Streamlit Cloud
2. Click **"Manage app"** (lower right corner)
3. Go to **Settings** → **Secrets**
4. Add these secrets:

```toml
[postgres]
host = "your-database-host.com"
database = "hrms_db"
user = "postgres"
password = "your-database-password"
port = 5432
```

**Note**: You need a cloud PostgreSQL database (e.g., from Supabase, Railway, Neon, or AWS RDS).

### Database Options for Cloud

- **Supabase** (Free tier): https://supabase.com
- **Railway** (Free tier): https://railway.app
- **Neon** (Free tier): https://neon.tech
- **AWS RDS**: https://aws.amazon.com/rds/postgresql

## Default Login

- **Username**: admin
- **Password**: admin

## Project Structure

```
demo-software/
├── task_manager.py      # Main application file
├── requirements.txt     # Python dependencies
├── uploads/            # File uploads directory
│   ├── chat_attachments/
│   └── notices/
└── README.md           # This file
```

## Important Notes

⚠️ **Vercel Hosting**: Vercel does not support Python/Streamlit applications. For hosting Streamlit apps, consider:
- **Streamlit Cloud** (Recommended) - https://streamlit.io/cloud
- **Railway** - https://railway.app
- **Render** - https://render.com
- **Heroku** - https://www.heroku.com

## License

This project is proprietary software for SRJ Strips.

