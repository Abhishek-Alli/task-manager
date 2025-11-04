# -*- coding: utf-8 -*-
import streamlit as st

# Configure page for wide layout - FORCE SIDEBAR EXPANDED
st.set_page_config(
    page_title="SRJ Strips Task Manager",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None  # Hide default Streamlit menu
)

import psycopg2
from psycopg2.extras import DictCursor
import bcrypt
from datetime import datetime, date
import os
import uuid
import pandas as pd
import random
from streamlit_option_menu import option_menu

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='hrms_db',
        user='postgres',
        password='Abhi122103',
        port=5432
    )

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if users table exists and has all required columns
    cur.execute('''
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='users'
    ''')
    existing_columns = [row[0] for row in cur.fetchall()]
    
    required_columns = ['username', 'password', 'employee_id', 'first_name', 'last_name', 'department', 'designation', 'is_admin', 'is_director']
    
    # Only drop and recreate if table doesn't exist or is missing required columns
    if not existing_columns or not all(col in existing_columns for col in required_columns):
        # Drop only if table exists and needs update
        if existing_columns:
            cur.execute('DROP TABLE IF EXISTS users CASCADE')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                    employee_id TEXT UNIQUE NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    designation TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_director BOOLEAN DEFAULT FALSE
                )
            ''')
        
    # Check if tasks table exists
    cur.execute('''
        SELECT table_name FROM information_schema.tables 
        WHERE table_name='tasks'
    ''')
    tasks_exists = cur.fetchone()
    
    # Check if old tasks table exists and has complete column (legacy migration check)
    if tasks_exists:
        cur.execute('''
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='tasks' AND column_name='complete'
        ''')
        has_complete = cur.fetchone()
    
        # Drop and recreate only if old schema detected
        if has_complete:
            cur.execute('DROP TABLE IF EXISTS task_assignments CASCADE')
            cur.execute('DROP TABLE IF EXISTS task_attachments CASCADE')
            cur.execute('DROP TABLE IF EXISTS tasks CASCADE')
    
    # Create tables if they don't exist
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            "desc" TEXT,
            priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'due', 'completed')),
            due_date DATE,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Junction table for many-to-many relationship (group tasks)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS task_assignments (
            id SERIAL PRIMARY KEY,
            task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
            username TEXT REFERENCES users(username) ON DELETE CASCADE,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(task_id, username)
        )
    ''')
    
    # File attachments table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS task_attachments (
            id SERIAL PRIMARY KEY,
            task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_by TEXT REFERENCES users(username) ON DELETE SET NULL
        )
    ''')
    
    # Departments table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Designations table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS designations (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default departments if not exists
    default_departments = ['IT', 'HR', 'Finance', 'Operations', 'Sales', 'Marketing', 'Administration']
    for dept in default_departments:
        cur.execute('INSERT INTO departments (name) VALUES (%s) ON CONFLICT (name) DO NOTHING', (dept,))
    
    # Insert default designations if not exists
    default_designations = ['Manager', 'Senior Manager', 'Executive', 'Senior Executive', 'Associate', 'Senior Associate', 'Administrator']
    for desg in default_designations:
        cur.execute('INSERT INTO designations (name) VALUES (%s) ON CONFLICT (name) DO NOTHING', (desg,))
    
    # Notice Board table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS notices (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_by TEXT REFERENCES users(username) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # Notice attachments table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS notice_attachments (
            id SERIAL PRIMARY KEY,
            notice_id INTEGER REFERENCES notices(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_by TEXT REFERENCES users(username) ON DELETE SET NULL
        )
    ''')
    
    # Check if old chats table exists without chat_id
    cur.execute('''
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='chats' AND column_name='chat_id'
    ''')
    has_chat_id = cur.fetchone()
    
    # Migrate to new schema if needed
    if not has_chat_id:
        cur.execute('DROP TABLE IF EXISTS chats CASCADE')
        cur.execute('DROP TABLE IF EXISTS chat_participants CASCADE')
        cur.execute('DROP TABLE IF EXISTS chat_conversations CASCADE')
    
    # Chat conversations table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat_conversations (
            id SERIAL PRIMARY KEY,
            chat_name TEXT,
            chat_type TEXT NOT NULL CHECK (chat_type IN ('individual', 'group', 'all')),
            created_by TEXT REFERENCES users(username) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            join_link TEXT UNIQUE
        )
    ''')
    
    # Chat participants table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat_participants (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER REFERENCES chat_conversations(id) ON DELETE CASCADE,
            username TEXT REFERENCES users(username) ON DELETE CASCADE,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, username)
        )
    ''')
    
    # Chats table for team communication (messages)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER REFERENCES chat_conversations(id) ON DELETE CASCADE,
            sender_username TEXT REFERENCES users(username) ON DELETE SET NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Chat attachments table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat_attachments (
            id SERIAL PRIMARY KEY,
            chat_message_id INTEGER REFERENCES chats(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_by TEXT REFERENCES users(username) ON DELETE SET NULL
        )
    ''')
    
    # Create uploads directory if it doesn't exist
    uploads_dir = "uploads"
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    # Create chat attachments directory
    chat_uploads_dir = os.path.join("uploads", "chat_attachments")
    if not os.path.exists(chat_uploads_dir):
        os.makedirs(chat_uploads_dir)
    
    # Clear old test messages to avoid rendering issues (only on first run)
    # cur.execute('DELETE FROM chats')
    # cur.execute('DELETE FROM chat_attachments')
    
    cur.execute('SELECT * FROM users WHERE username=%s', ('admin',))
    if not cur.fetchone():
        hashed_pw = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute('''
            INSERT INTO users (username, password, employee_id, first_name, last_name, department, designation, is_admin, is_director) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, FALSE)
        ''', ('admin', hashed_pw, '000000000001', 'Admin', 'User', 'Administration', 'Administrator'))
    
    # Create default "ALL" chat conversation
    cur.execute('SELECT * FROM chat_conversations WHERE chat_type=%s', ('all',))
    if not cur.fetchone():
        cur.execute('''
            INSERT INTO chat_conversations (chat_name, chat_type, created_by)
            VALUES (%s, %s, %s)
            RETURNING id
        ''', ('General Chat (All Users)', 'all', 'admin'))
        all_chat_id = cur.fetchone()[0]
        
        # Add all existing users to "ALL" chat
        cur.execute('SELECT username FROM users')
        all_users = cur.fetchall()
        for user_row in all_users:
            cur.execute('''
                INSERT INTO chat_participants (chat_id, username)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            ''', (all_chat_id, user_row[0]))
    
    conn.commit()
    cur.close()
    conn.close()

# Initialize database only once
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

# Theme initialization
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'

# Inject custom CSS for premium UI
st.markdown("""
<style>
    /* Beautiful Gradient Background - Modern Dark Theme */
    .stApp {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 25%, #1e3a8a 50%, #1e40af 75%, #0f172a 100%) !important;
        background-size: 400% 400% !important;
        animation: gradientShift 15s ease infinite !important;
        min-height: 100vh;
        position: relative;
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Add floating shapes animation */
    .stApp::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: 
            radial-gradient(circle at 20% 50%, rgba(255,255,255,0.15) 0%, transparent 50%),
            radial-gradient(circle at 80% 80%, rgba(255,255,255,0.15) 0%, transparent 50%),
            radial-gradient(circle at 50% 20%, rgba(255,255,255,0.08) 0%, transparent 50%);
        animation: float 20s ease-in-out infinite;
        z-index: 0;
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0px) rotate(0deg); opacity: 1; }
        50% { transform: translateY(-20px) rotate(180deg); opacity: 0.8; }
    }
    
    /* Main content should be above animation */
    .main {
        position: relative;
        z-index: 1;
    }
    
    .main .block-container {
        padding: 2rem 3rem 4rem 3rem;
        max-width: 100% !important;
        width: 100% !important;
        background: transparent !important;
        border-radius: 0 !important;
        border: none !important;
    }
    
    /* Full width layout */
    .main > div {
        max-width: 100% !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    
    /* Hide Streamlit's default header completely */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    /* Hide Streamlit's footer */
    footer {
        visibility: hidden !important;
    }
    
    /* Title styling - Bright colors for contrast on dark background */
    h1 {
        color: #14b8a6 !important;
        font-weight: 900;
        font-size: 3rem;
        letter-spacing: -0.02em;
        margin-bottom: 0.25rem;
        text-shadow: 0 2px 12px rgba(20, 184, 166, 0.6), 0 0 20px rgba(20, 184, 166, 0.3);
    }
    
    h2 {
        color: #ffffff !important;
        font-weight: 700;
        font-size: 2rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
    }
    
    h3 {
        color: #06b6d4 !important;
        font-weight: 700;
        font-size: 1.5rem;
        margin-top: 1.5rem;
        text-shadow: 0 2px 8px rgba(6, 182, 212, 0.4);
    }
    
    /* Text styling - Light text on dark background for contrast */
    p, span, div, label {
        color: #f1f5f9 !important;
        font-size: 1rem;
        line-height: 1.6;
    }
    
    /* Buttons - Glassmorphism style */
    .stButton > button {
        background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.3) 100%) !important;
        backdrop-filter: blur(10px) !important;
        color: #ffffff !important;
        border: 1.5px solid rgba(255,255,255,0.4) !important;
        border-radius: 12px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 16px rgba(255,255,255,0.2) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 24px rgba(255,255,255,0.3) !important;
        background: linear-gradient(135deg, rgba(255,255,255,0.3) 0%, rgba(255,255,255,0.4) 100%) !important;
        border-color: rgba(255,255,255,0.6) !important;
    }
    
    /* Input fields - Glassmorphism style */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select {
        border-radius: 12px !important;
        border: 2px solid rgba(255, 255, 255, 0.4) !important;
        padding: 0.75rem 1rem !important;
        background-color: rgba(255, 255, 255, 0.12) !important;
        backdrop-filter: blur(12px) !important;
        color: #ffffff !important;
        font-size: 0.95rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > select:focus {
        border-color: rgba(255, 255, 255, 0.8) !important;
        box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.25) !important;
        outline: none !important;
        background-color: rgba(255, 255, 255, 0.18) !important;
    }
    
    /* Input labels - Bright white for contrast */
    .stTextInput > label,
    .stTextArea > label,
    .stSelectbox > label {
        color: #ffffff !important;
        font-weight: 600 !important;
        text-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        border-bottom: 2px solid rgba(20, 184, 166, 0.3);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        font-size: 0.95rem;
        color: #94a3b8 !important;
        background: transparent;
    }
    
    .stTabs [aria-selected="true"] {
        color: #14b8a6 !important;
        background: rgba(20, 184, 166, 0.1) !important;
        border-bottom: 2px solid #14b8a6;
    }
    
    /* Metrics - Modern Teal */
    [data-testid="stMetricValue"] {
        font-size: 2.5rem;
        font-weight: 800;
        color: #14b8a6 !important;
        letter-spacing: -0.02em;
    }
    
    [data-testid="stMetricLabel"] {
        color: #e2e8f0 !important;
        font-weight: 500;
        font-size: 0.9rem;
        text-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    }
    
    /* Alerts */
    .stSuccess {
        background: rgba(34, 197, 94, 0.1) !important;
        border-left: 4px solid #22c55e !important;
        border-radius: 8px !important;
        color: #86efac !important;
    }
    
    .stInfo {
        background: rgba(59, 130, 246, 0.1) !important;
        border-left: 4px solid #3b82f6 !important;
        border-radius: 8px !important;
        color: #93c5fd !important;
    }
    
    .stWarning {
        background: rgba(245, 158, 11, 0.1) !important;
        border-left: 4px solid #d4af37 !important;
        border-radius: 8px !important;
        color: #fbbf24 !important;
    }
    
    .stError {
        background: rgba(239, 68, 68, 0.1) !important;
        border-left: 4px solid #ef4444 !important;
        border-radius: 8px !important;
        color: #fca5a5 !important;
    }
    
    /* Tables */
    table {
        border-collapse: separate;
        border-spacing: 0;
        border-radius: 10px;
        overflow: hidden;
        background: rgba(0, 0, 0, 0.5) !important;
        border: 1px solid rgba(20, 184, 166, 0.3) !important;
    }
    
    table th {
        background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        padding: 0.875rem 1rem !important;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
    }
    
    table td {
        color: #f1f5f9 !important;
        padding: 0.875rem 1rem !important;
        border-bottom: 1px solid rgba(20, 184, 166, 0.2) !important;
        background: rgba(15, 23, 42, 0.5) !important;
    }
    
    table tr:hover {
        background: rgba(20, 184, 166, 0.08) !important;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        font-weight: 600;
        background: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(20, 184, 166, 0.4) !important;
        border-radius: 8px;
        padding: 1rem;
        color: #14b8a6 !important;
        font-size: 1rem;
        text-shadow: 0 1px 4px rgba(20, 184, 166, 0.4);
    }
    
    .streamlit-expanderContent {
        background: rgba(15, 23, 42, 0.9) !important;
        border-radius: 0 0 8px 8px;
        padding: 1.5rem;
        border: 1px solid rgba(20, 184, 166, 0.3);
        border-top: none;
        color: #f1f5f9 !important;
    }
    
    /* Dividers */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(20, 184, 166, 0.5), transparent);
        margin: 2rem 0;
    }
    
    /* Sidebar - Old dark theme (overridden by modern light theme below) */
    /* Removed to avoid conflicts with modern sidebar */
    
    /* Dataframe */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.5);
        border: 1px solid rgba(20, 184, 166, 0.3);
        background: rgba(0, 0, 0, 0.5) !important;
    }
    
    /* File uploader */
    .stFileUploader > div {
        background: rgba(0, 0, 0, 0.8);
        border: 2px dashed rgba(20, 184, 166, 0.3);
        border-radius: 10px;
        padding: 2rem;
    }
    
    .stFileUploader > div:hover {
        border-color: #14b8a6;
        background: rgba(0, 0, 0, 1);
    }
    
    /* Checkboxes & Radios - Light text for contrast */
    .stCheckbox label, .stRadio label {
        color: #f1f5f9 !important;
        font-weight: 500;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    }
    
    /* Select boxes - Teal accent for visibility */
    .stSelectbox label {
        color: #14b8a6 !important;
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
        text-shadow: 0 1px 4px rgba(20, 184, 166, 0.4);
    }
    
    /* Glassmorphism Login Card Design */
    .login-card {
        background: rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(20px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
        border: 2px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 24px !important;
        padding: 1.5rem !important;
        margin: 0.25rem !important;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37),
                    0 0 0 1px rgba(255, 255, 255, 0.1) inset !important;
        transition: all 0.3s ease !important;
        position: relative;
        overflow: hidden;
    }
    
    .login-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
    }
    
    .login-card:hover {
        background: rgba(255, 255, 255, 0.15) !important;
        box-shadow: 0 12px 48px 0 rgba(31, 38, 135, 0.5),
                    0 0 0 1px rgba(255, 255, 255, 0.2) inset !important;
        transform: translateY(-5px) !important;
    }
    
    .login-icon {
        font-size: 2.5rem !important;
        text-align: center;
        margin-bottom: 0.5rem !important;
        animation: pulse 2s infinite;
        filter: drop-shadow(0 4px 8px rgba(0,0,0,0.2));
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    .login-title {
        text-align: center;
        font-size: 1.3rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        margin-bottom: 0.3rem !important;
        text-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
    }
    
    .login-subtitle {
        text-align: center;
        color: rgba(255, 255, 255, 0.9) !important;
        font-size: 0.85rem !important;
        margin-bottom: 0.5rem !important;
        font-weight: 400 !important;
    }
    
    /* Clean column spacing */
    [data-testid="column"] {
        padding: 0.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Premium header - Fixed position at top with modern dark theme
st.markdown("""
<div style="position: fixed; top: 0; left: 0; right: 0; width: 100%; text-align: center; padding: 1.5rem 0; background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #1e3a8a 100%); border-bottom: 2px solid #14b8a6; z-index: 1001; border-radius: 0; margin: 0; box-shadow: 0 4px 12px rgba(20, 184, 166, 0.3);">
    <h1 style="margin: 0; padding: 0; color: #ffffff !important; font-size: 2rem !important; font-weight: 700; text-shadow: 0 2px 8px rgba(20, 184, 166, 0.5);">SRJ Strips Task Manager</h1>
</div>
<div style="height: 10px; margin-top: 0;"></div>
""", unsafe_allow_html=True)

# Initialize user session state
if 'user' not in st.session_state:
    st.session_state['user'] = None

# Add hamburger menu CSS
st.markdown("""
<style>
    /* Custom hamburger menu button */
    .hamburger-menu {
        position: fixed;
        top: 1rem;
        left: 1rem;
        z-index: 1002;
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 5px;
        width: 40px;
        height: 40px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        cursor: pointer;
        gap: 4px;
    }
    
    .hamburger-line {
        width: 20px;
        height: 2px;
        background: #ffffff;
        border-radius: 2px;
        transition: all 0.3s ease;
    }
    
    .hamburger-menu:hover {
        background: rgba(255, 255, 255, 0.2);
    }
</style>
""", unsafe_allow_html=True)


def signup():
    # Personal Information
    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First Name *")
        last_name = st.text_input("Last Name *")
        employee_id = st.text_input("Employee ID * (12 digits)", help="Enter exactly 12 numeric digits")
    with col2:
        new_username = st.text_input("Username *")
        new_password = st.text_input("Password *", type="password")
        confirm_password = st.text_input("Confirm Password *", type="password")
    
    # Professional Information
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    # Get departments from database
    cur.execute('SELECT name FROM departments ORDER BY name')
    departments_list = [row['name'] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    col3, col4 = st.columns(2)
    with col3:
        if departments_list:
            department = st.selectbox("Department *", departments_list)
        else:
            department = st.text_input("Department *", help="No departments available. Please contact admin.")
    with col4:
        # Fixed designation dropdown with HOD, SUB-HOD, EMPLOYEE
        designation = st.selectbox("Designation *", ['HOD', 'SUB-HOD', 'EMPLOYEE'], help="Select your designation")
    
    if st.button("Register"):
        # Validation
        if new_username == "admin":
            st.warning("You cannot register as 'admin'.")
            return
        
        if not all([first_name, last_name, employee_id, new_username, new_password, confirm_password, department, designation]):
            st.warning("Please fill all required fields (*).")
            return
        
        # Validate employee_id: must be exactly 12 digits
        if not employee_id.isdigit():
            st.error("Employee ID must contain only numbers.")
            return
        
        if len(employee_id) != 12:
            st.error("Employee ID must be exactly 12 digits.")
            return
        
        if new_password != confirm_password:
            st.error("Passwords do not match.")
            return
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if username already exists
        cur.execute('SELECT * FROM users WHERE username=%s', (new_username,))
        if cur.fetchone():
            st.error("Username already exists.")
            cur.close()
            conn.close()
            return
        
        # Check if employee_id already exists
        cur.execute('SELECT * FROM users WHERE employee_id=%s', (employee_id,))
        if cur.fetchone():
            st.error("Employee ID already exists.")
            cur.close()
            conn.close()
            return
        
        # Create new user
        try:
            hashed_new_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Insert user
            cur.execute(
                'INSERT INTO users (username, password, employee_id, first_name, last_name, department, designation, is_admin) VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)',
                (new_username, hashed_new_pw, employee_id, first_name, last_name, department, designation)
            )
            
            # Commit the transaction
            conn.commit()
            
            # Verify the user was created
            cur.execute('SELECT username, employee_id, first_name, last_name FROM users WHERE username=%s', (new_username,))
            verify_user = cur.fetchone()
            
            if verify_user:
                st.success(f"Registration successful! User '{new_username}' created. Please log in.")
            else:
                st.error("Registration failed. User was not created in database.")
            
            cur.close()
            conn.close()
            
        except Exception as e:
            conn.rollback()
            st.error(f"Registration error: {str(e)}")
            cur.close()
            conn.close()
            return

def director_login():
    username = st.text_input("Director Username", key="director_user")
    password = st.text_input("Director Password", type="password", key="director_pass")
    
    if st.button("Director Login"):
        if not username or not password:
            st.warning("Please enter both username and password.")
            return
        
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=DictCursor)
            cur.execute('SELECT * FROM users WHERE username=%s AND is_director=TRUE', (username,))
            user = cur.fetchone()
            
            if not user:
                st.error("Invalid director credentials or user is not a director.")
                cur.close()
                conn.close()
                return
            
            # Get stored password hash
            stored_password_hash = user['password']
            
            # Ensure stored password is in bytes format for bcrypt
            if isinstance(stored_password_hash, str):
                stored_password_bytes = stored_password_hash.encode('utf-8')
            else:
                stored_password_bytes = stored_password_hash
            
            # Verify password
            if bcrypt.checkpw(password.encode('utf-8'), stored_password_bytes):
                st.session_state['user'] = {
                    'username': user['username'],
                    'is_admin': user.get('is_admin', False),
                    'is_director': True,
                    'designation': user.get('designation', '')
                }
                cur.close()
                conn.close()
                st.success("Director login successful!")
                st.rerun()
            else:
                st.error("Invalid director credentials.")
                cur.close()
                conn.close()
        except Exception as e:
            st.error(f"Director login error: {str(e)}")
            try:
                cur.close()
                conn.close()
            except:
                pass

def login():
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    
    # Debug info (remove in production)
    with st.expander("Debug Info (for testing)", expanded=False):
        if username:
            try:
                conn = get_db_connection()
                cur = conn.cursor(cursor_factory=DictCursor)
                cur.execute('SELECT username, employee_id, first_name, last_name FROM users WHERE username=%s', (username,))
                user_info = cur.fetchone()
                if user_info:
                    st.write(f"User found: {user_info}")
                else:
                    st.write("User not found in database")
                cur.close()
                conn.close()
            except Exception as e:
                st.write(f"Error: {str(e)}")
    
    if st.button("Login"):
        if not username or not password:
            st.warning("Please enter both username and password.")
            return
        
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=DictCursor)
            cur.execute('SELECT * FROM users WHERE username=%s', (username,))
            user = cur.fetchone()
            
            if not user:
                st.error("Invalid username or password.")
                cur.close()
                conn.close()
                return
            
            # Get stored password hash
            stored_password_hash = user['password']
            
            # Ensure stored password is in bytes format for bcrypt
            if isinstance(stored_password_hash, str):
                stored_password_bytes = stored_password_hash.encode('utf-8')
            else:
                stored_password_bytes = stored_password_hash
            
            # Verify password
            if bcrypt.checkpw(password.encode('utf-8'), stored_password_bytes):
                st.session_state['user'] = {
                    'username': user['username'],
                    'is_admin': user.get('is_admin', False),
                    'is_director': user.get('is_director', False),
                    'designation': user.get('designation', '')
                }
                cur.close()
                conn.close()
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password.")
                cur.close()
                conn.close()
        except Exception as e:
            st.error(f"Login error: {str(e)}")
            try:
                cur.close()
                conn.close()
            except:
                pass

def task_page():
    user = st.session_state['user']
    is_admin = user.get('is_admin', False)
    is_director = user.get('is_director', False)
    
    # Determine user role display
    if is_admin:
        role = "Admin"
    elif is_director:
        role = "Director"
    else:
        role = "User"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    # Get user's department to check if HR
    cur.execute('SELECT department FROM users WHERE username=%s', (user['username'],))
    user_dept = cur.fetchone()
    user_department = user_dept['department'] if user_dept else None
    is_hr = user_department and user_department.upper() == 'HR'
    can_add_notices = is_admin or is_hr or is_director
    
    # Initialize session state for page selection if not exists
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "📋 Tasks"
    
    # Modern sidebar styling - CRITICAL: Force sidebar to be visible
    st.markdown("""
    <style>
        /* IMPORTANT: Remove any CSS that might hide sidebar */
        section[data-testid="stSidebar"],
        div[data-testid="stSidebar"],
        aside[data-testid="stSidebar"] {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            width: 300px !important;
            min-width: 300px !important;
            max-width: 300px !important;
            transform: translateX(0) !important;
            margin-left: 0 !important;
        }
        
        /* Sidebar styling - Modern Dark Theme */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
            border-right: 2px solid #14b8a6 !important;
            box-shadow: 2px 0 12px rgba(20, 184, 166, 0.3) !important;
            display: block !important;
            visibility: visible !important;
            width: 280px !important;
            min-width: 280px !important;
            max-width: 280px !important;
            opacity: 1 !important;
            z-index: 999 !important;
            position: relative !important;
            left: 0 !important;
            transform: translateX(0) !important;
        }
        
        /* Sidebar content styling - Light text on dark background */
        section[data-testid="stSidebar"] * {
            color: #e2e8f0 !important;
        }
        
        /* Main content area should leave space for sidebar */
        .main .block-container {
            margin-left: 280px !important;
            padding-left: 2rem !important;
        }
        
        /* Sidebar headings - Light text on dark background */
        section[data-testid="stSidebar"] h3 {
            color: #14b8a6 !important;
            font-weight: 600 !important;
            font-size: 1.1rem !important;
            margin-bottom: 0.75rem !important;
        }
        
        /* Sidebar dividers - Teal accent */
        section[data-testid="stSidebar"] hr {
            border-color: rgba(20, 184, 166, 0.4) !important;
            margin: 1rem 0 !important;
        }
        
        /* Ensure sidebar button is visible (default Streamlit button) */
        button[kind="header"] {
            display: block !important;
            visibility: visible !important;
        }
        
        /* Force sidebar to show even if hidden */
        section[data-testid="stSidebar"][style*="display: none"] {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
        }
        
        /* FORCE SIDEBAR EXPANDED - JavaScript fallback */
    </style>
    <script>
        // CRITICAL: Force sidebar to be visible and expanded immediately
        (function() {
            function forceSidebar() {
                // Find sidebar by multiple selectors
                const selectors = [
                    'section[data-testid="stSidebar"]',
                    'div[data-testid="stSidebar"]',
                    'aside[data-testid="stSidebar"]',
                    '[class*="sidebar"]'
                ];
                
                let sidebar = null;
                for (const selector of selectors) {
                    sidebar = document.querySelector(selector);
                    if (sidebar) break;
                }
                
                if (sidebar) {
                    sidebar.style.display = 'block';
                    sidebar.style.visibility = 'visible';
                    sidebar.style.opacity = '1';
                    sidebar.style.width = '300px';
                    sidebar.style.minWidth = '300px';
                    sidebar.style.maxWidth = '300px';
                    sidebar.style.transform = 'translateX(0)';
                    sidebar.style.marginLeft = '0';
                    sidebar.setAttribute('aria-expanded', 'true');
                    sidebar.removeAttribute('aria-hidden');
                }
                
                // Force expand sidebar button
                const sidebarButton = document.querySelector('button[kind="header"]');
                if (sidebarButton) {
                    if (sidebarButton.getAttribute('aria-expanded') === 'false' || 
                        sidebarButton.getAttribute('aria-expanded') === null) {
                        sidebarButton.click();
                        setTimeout(() => sidebarButton.click(), 100);
                    }
                    sidebarButton.setAttribute('aria-expanded', 'true');
                }
            }
            
            // Run immediately and on load
            forceSidebar();
            window.addEventListener('load', forceSidebar);
            window.addEventListener('DOMContentLoaded', forceSidebar);
            
            // Run every 500ms for first 3 seconds to ensure sidebar stays visible
            let attempts = 0;
            const interval = setInterval(function() {
                forceSidebar();
                attempts++;
                if (attempts >= 6) clearInterval(interval);
            }, 500);
        })();
    </script>
    <style>
        
        /* Ensure sidebar is always visible and expanded */
        section[data-testid="stSidebar"][aria-expanded="false"],
        section[data-testid="stSidebar"][aria-expanded="true"] {
            display: block !important;
            visibility: visible !important;
        }
        
        /* Force sidebar to be visible */
        .css-1d391kg {
            display: block !important;
            visibility: visible !important;
        }
        
        /* Show sidebar toggle button */
        button[data-testid="baseButton-header"],
        button[kind="header"] {
            display: block !important;
            visibility: visible !important;
        }
        
        /* Ensure sidebar content is visible */
        .css-1cypcdb {
            display: block !important;
            visibility: visible !important;
        }
        
        /* Sidebar menu items */
        .st-emotion-cache-1d391kg {
            padding: 0 !important;
        }
        
        /* Modern sidebar container */
        .sidebar-container {
            padding: 1.5rem 1rem;
        }
        
        /* User profile section in sidebar */
        .sidebar-user-profile {
            padding: 1.5rem 1rem;
            border-bottom: 1px solid #e0e0e0;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%);
            border-radius: 12px;
            color: white;
            margin: -1rem -1rem 1.5rem -1rem;
        }
        
        .sidebar-user-name {
            font-weight: 600;
            font-size: 1.1rem;
            margin-bottom: 0.25rem;
        }
        
        .sidebar-user-role {
            font-size: 0.85rem;
            opacity: 0.9;
        }
        .company-heading {
            text-align: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid #262730;
        }
        .company-heading .heading-title {
            color: #14b8a6;
            font-size: 2.5rem;
            font-weight: 700;
            margin: 0;
            padding: 0;
            text-shadow: 0 2px 8px rgba(20, 184, 166, 0.3);
            background: linear-gradient(135deg, #14b8a6 0%, #06b6d4 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1.2;
        }
        .company-heading .tagline {
            color: #FFFFFF;
            font-size: 1rem;
            margin-top: 0.5rem;
            margin-bottom: 0.25rem;
            font-weight: 400;
            opacity: 0.9;
        }
        .company-heading .subtitle {
            color: #B0B0B0;
            font-size: 0.85rem;
            margin-top: 0;
            margin-bottom: 0;
            font-weight: 300;
        }
        button[kind="primary"] {
            background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%) !important;
            border: 2px solid #14b8a6 !important;
            color: white !important;
            font-weight: 600 !important;
            box-shadow: 0 2px 8px rgba(20, 184, 166, 0.3) !important;
            transition: all 0.3s ease !important;
        }
        button[kind="primary"]:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(20, 184, 166, 0.4) !important;
        }
        button[kind="secondary"] {
            background: rgba(255, 255, 255, 0.1) !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            color: #E0E0E0 !important;
            font-weight: 500 !important;
            transition: all 0.3s ease !important;
        }
        button[kind="secondary"]:hover {
            background: rgba(255, 255, 255, 0.15) !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
            border-color: rgba(255, 255, 255, 0.3) !important;
        }
        .header-nav-bar {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #1e3a8a 100%);
            padding: 1.5rem 2rem;
            border-bottom: 3px solid #14b8a6;
            margin-bottom: 2rem;
            border-radius: 0.75rem;
            box-shadow: 0 4px 12px rgba(20, 184, 166, 0.3), 0 1px 3px rgba(0,0,0,0.2);
        }
        .header-top-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.25rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #262730;
        }
        .user-info {
            color: #FAFAFA;
            font-size: 1.1rem;
            font-weight: 500;
        }
        .main-content-wrapper {
            padding: 0 1rem;
            margin-top: 1rem;
        }
        
        /* Option menu custom styling */
        div[data-baseweb="menu"] {
            background: transparent !important;
        }
        
        /* Menu item styling */
        .st-emotion-cache-6qob1r {
            background: transparent !important;
        }
        
        /* Remove default button styling from option menu */
        button[kind="header"] {
            background: transparent !important;
        }
        
        /* Ensure option menu is visible */
        .css-1d391kg {
            padding: 1rem !important;
        }
        
        /* Option menu container visibility */
        div.streamlit-option-menu {
            display: block !important;
            visibility: visible !important;
        }
        
        /* Menu links visibility */
        .st-emotion-cache-1y4p8pa {
            display: block !important;
        }
        
        a[data-testid="stOptionMenu"] {
            display: block !important;
            visibility: visible !important;
        }
        
        /* Additional modern styling for sidebar */
        .css-1d391kg {
            padding-top: 1rem !important;
        }
        
        /* Smooth transitions */
        * {
            transition: background-color 0.3s ease, color 0.3s ease, transform 0.3s ease !important;
        }
        .logout-btn {
            background: linear-gradient(135deg, #FF4444 0%, #CC0000 100%);
            border: none;
            color: white;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .logout-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(255, 68, 68, 0.4);
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Get menu items based on user role (without emojis - professional look)
    if is_admin or is_director:
        menu_options = ["Tasks", "Users Management", "Departments & Designations", "Notice Board", "Chat"]
        menu_icons = ["clipboard-check", "people", "building", "megaphone", "chat-dots"]
        if is_admin:
            menu_options.append("Admin Dashboard")
            menu_icons.append("speedometer2")
    else:
        menu_options = ["Tasks", "Notice Board", "Chat"]
        menu_icons = ["clipboard-check", "megaphone", "chat-dots"]
    
    # Initialize selected variable
    selected = None
    
    # Sidebar navigation with modern design
    # Force sidebar to be visible
    with st.sidebar:
        # Navigation menu - Professional design (at top)
        # Removed "Navigation" heading as requested
        
        # Get current selection index
        current_index = 0
        menu_to_page_map = {
            "Tasks": "📋 Tasks",
            "Users Management": "👥 Users Management",
            "Departments & Designations": "🏢 Departments & Designations",
            "Notice Board": "📢 Notice Board",
            "Chat": "💬 Chat",
            "Admin Dashboard": "📊 Admin Dashboard"
        }
        if st.session_state.current_page in menu_to_page_map.values():
            for idx, opt in enumerate(menu_options):
                if menu_to_page_map.get(opt) == st.session_state.current_page:
                    current_index = idx
                    break
        
        # Display navigation as radio buttons - No label, professional styling
        if len(menu_options) > 0:
            selected = st.radio(
                "",
                menu_options,
                index=current_index,
                label_visibility="collapsed",
                key="nav_menu_radio"
            )
        else:
            st.error("No menu options available!")
            selected = "Tasks"
        
        # Professional radio button styling - High contrast colors
        st.markdown("""
        <style>
            /* Radio button container */
            div[data-testid="stRadio"] {
                display: block !important;
                visibility: visible !important;
                opacity: 1 !important;
                width: 100% !important;
            }
            
            div[data-testid="stRadio"] > div {
                gap: 0.5rem !important;
                display: flex !important;
                flex-direction: column !important;
            }
            
            /* Radio button labels - Dark theme with good contrast */
            div[data-testid="stRadio"] label {
                padding: 0.875rem 1.125rem !important;
                margin: 0.4rem 0 !important;
                border-radius: 8px !important;
                background-color: rgba(30, 41, 59, 0.8) !important;
                border: 1px solid rgba(20, 184, 166, 0.3) !important;
                transition: all 0.3s ease !important;
                cursor: pointer !important;
                font-size: 15px !important;
                font-weight: 500 !important;
                color: #e2e8f0 !important;
                display: block !important;
                visibility: visible !important;
                width: 100% !important;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3) !important;
            }
            
            div[data-testid="stRadio"] label:hover {
                background-color: rgba(20, 184, 166, 0.2) !important;
                border-color: #14b8a6 !important;
                transform: translateX(3px) !important;
                box-shadow: 0 2px 6px rgba(20, 184, 166, 0.4) !important;
                color: #14b8a6 !important;
            }
            
            /* Selected radio button - High contrast */
            div[data-testid="stRadio"] input[type="radio"]:checked + label {
                background-color: #14b8a6 !important;
                color: #ffffff !important;
                border-color: #14b8a6 !important;
                font-weight: 600 !important;
                box-shadow: 0 3px 10px rgba(20, 184, 166, 0.5) !important;
            }
            
            /* Radio button inputs */
            div[data-testid="stRadio"] input[type="radio"] {
                display: block !important;
                visibility: visible !important;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # User profile section - Get user details
        first_name = user.get("first_name", "")
        last_name = user.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip() or user.get("username", "User")
        initials = ""
        if first_name:
            initials += first_name[0].upper()
        if last_name:
            initials += last_name[0].upper()
        if not initials:
            initials = user.get("username", "U")[0].upper()
        
        # Logout button
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---", unsafe_allow_html=True)
        if st.button("🚪 Logout", key="sidebar_logout_btn", width='stretch', type="secondary"):
            st.session_state['user'] = None
            st.session_state['current_page'] = "📋 Tasks"
            st.rerun()
        
        # Style logout button
        st.markdown("""
        <style>
            button[key="sidebar_logout_btn"] {
                background: linear-gradient(135deg, #FF4444 0%, #CC0000 100%) !important;
                color: white !important;
                font-weight: 600 !important;
                border: none !important;
                border-radius: 10px !important;
                padding: 0.75rem !important;
                margin-top: 1rem !important;
                box-shadow: 0 2px 8px rgba(255, 68, 68, 0.3) !important;
                transition: all 0.3s ease !important;
            }
            button[key="sidebar_logout_btn"]:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 4px 12px rgba(255, 68, 68, 0.4) !important;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # User profile card at bottom of sidebar
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="sidebar-user-profile" style="padding: 1.5rem; background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%); 
                    border-radius: 12px; color: white; margin-top: 1rem; box-shadow: 0 4px 12px rgba(20, 184, 166, 0.3);">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div style="width: 50px; height: 50px; border-radius: 50%; background: rgba(255, 255, 255, 0.2); 
                            display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 1.3rem;">
                    {initials}
                </div>
                <div>
                    <div class="sidebar-user-name" style="font-weight: 600; font-size: 1.1rem; margin-bottom: 0.25rem;">{full_name}</div>
                    <div class="sidebar-user-role" style="font-size: 0.85rem; opacity: 0.9;">{role}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Map selected menu to page name (with emojis for internal mapping)
    menu_to_page = {
        "Tasks": "📋 Tasks",
        "Users Management": "👥 Users Management",
        "Departments & Designations": "🏢 Departments & Designations",
        "Notice Board": "📢 Notice Board",
        "Chat": "💬 Chat",
        "Admin Dashboard": "📊 Admin Dashboard"
    }
    
    # Update current page based on selection
    if selected and selected in menu_to_page:
        if st.session_state.current_page != menu_to_page[selected]:
            st.session_state.current_page = menu_to_page[selected]
            st.rerun()
    else:
        # Default to Tasks if nothing selected
        if st.session_state.current_page not in menu_to_page.values():
            st.session_state.current_page = "📋 Tasks"
    
    # Main content wrapper for proper layout
    st.markdown('<div class="main-content-wrapper">', unsafe_allow_html=True)
    
    # Set selected page
    selected_page = st.session_state.current_page
    
    # Display selected page
    if selected_page == "📋 Tasks":
        show_tasks_page(conn, cur, user, is_admin)
    elif selected_page == "👥 Users Management":
        if is_admin or is_director:
            show_users_management(conn, cur)
    elif selected_page == "🏢 Departments & Designations":
        if is_admin or is_director:
            show_departments_designations(conn, cur)
    elif selected_page == "📢 Notice Board":
        show_notice_board(conn, cur, user, can_add_notices)
    elif selected_page == "💬 Chat":
        show_chat_box(conn, cur, user)
    elif selected_page == "📊 Admin Dashboard" and is_admin:
        show_admin_dashboard(conn, cur)
    
    # Close main content wrapper
    st.markdown('</div>', unsafe_allow_html=True)
    
    cur.close()
    conn.close()
    
    # Old tab-based navigation code (commented out for now)
    # if is_admin or is_director:
    #     if is_admin:
    #         tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📋 Tasks", "👥 Users Management", "🏢 Departments & Designations", "📢 Notice Board", "💬 Chat", "📊 Admin Dashboard"])
    #     else:
    #         tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Tasks", "👥 Users Management", "🏢 Departments & Designations", "📢 Notice Board", "💬 Chat"])
    #     
    #     with tab1:
    #         show_tasks_page(conn, cur, user, is_admin)
    #     
    #     with tab2:
    #         show_users_management(conn, cur)
    #     
    #     with tab3:
    #         show_departments_designations(conn, cur)
    #     
    #     with tab4:
    #         show_notice_board(conn, cur, user, can_add_notices)
    #     
    #     if is_admin:
    #         with tab5:
    #             show_chat_box(conn, cur, user)
    #         with tab6:
    #             show_admin_dashboard(conn, cur)
    #     else:
    #         with tab5:
    #             show_chat_box(conn, cur, user)
    #     
    #     cur.close()
    #     conn.close()
    # else:
    #     # Regular users tabs
    #     tab1, tab2, tab3 = st.tabs(["📋 Tasks", "📢 Notice Board", "💬 Chat"])
    #     
    #     with tab1:
    #         show_tasks_page(conn, cur, user, is_admin)
    #     
    #     with tab2:
    #         show_notice_board(conn, cur, user, can_add_notices)
    #     
    #     with tab3:
    #         show_chat_box(conn, cur, user)
    #     
    #     cur.close()
    #     conn.close()

def show_chat_box(conn, cur, user):
    st.markdown("""
    <style>
    /* Telegram-like Chat Styles */
    .telegram-message-own {
        display: flex;
        justify-content: flex-end;
        margin: 12px 0;
        padding: 0 16px;
    }
    .telegram-message-own-content {
        background: linear-gradient(135deg, #14b8a6 0%, #06b6d4 100%);
        color: #ffffff;
        padding: 8px 12px;
        border-radius: 12px 12px 4px 12px;
        max-width: 65%;
        word-wrap: break-word;
        font-size: 14px;
        line-height: 1.4;
        position: relative;
    }
    .telegram-message-other {
        display: flex;
        justify-content: flex-start;
        margin: 12px 0;
        padding: 0 16px;
        align-items: flex-start;
    }
    .telegram-message-other-content {
        background: rgba(20, 184, 166, 0.2);
        border: 1px solid rgba(20, 184, 166, 0.3);
        color: #e2e8f0;
        padding: 8px 12px;
        border-radius: 12px 12px 12px 4px;
        max-width: 65%;
        word-wrap: break-word;
        font-size: 14px;
        line-height: 1.4;
    }
    .telegram-message-time {
        font-size: 11px;
        opacity: 0.7;
        margin-top: 4px;
        text-align: right;
        font-weight: normal;
    }
    .telegram-message-sender {
        font-weight: 600;
        font-size: 14px;
        margin-bottom: 4px;
        color: #14b8a6;
    }
    .telegram-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: linear-gradient(135deg, #14b8a6 0%, #06b6d4 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 14px;
        color: #ffffff;
        margin-right: 8px;
        flex-shrink: 0;
    }
    .telegram-header {
        background: rgba(0, 0, 0, 0.95);
        border-bottom: 1px solid rgba(20, 184, 166, 0.3);
        padding: 12px 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .telegram-header-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #14b8a6 0%, #06b6d4 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 16px;
        color: #ffffff;
    }
    .telegram-chat-info h4 {
        margin: 0;
        color: #ffffff;
        font-size: 16px;
        font-weight: 600;
    }
    .telegram-chat-info p {
        margin: 0;
        color: #94a3b8;
        font-size: 13px;
    }
    .stChatMessage {
        padding: 0 !important;
    }
    [data-testid="stChatMessage"] {
        padding: 0 !important;
    }
    
    /* Hide any subheaders in chat section */
    section[data-testid="stMain"] h2,
    section[data-testid="stMain"] h3 {
        display: none !important;
    }
    
    /* Chat container wrapper - Unified height */
    .chat-wrapper {
        display: flex !important;
        flex-direction: column !important;
        height: calc(100vh - 250px) !important;
        max-height: 80vh !important;
        position: relative;
    }
    
    /* Ensure main chat column has proper structure */
    div[data-testid="column"]:has(.chat-wrapper) {
        display: flex !important;
        flex-direction: column !important;
        height: calc(100vh - 150px) !important;
    }
    
    /* Scrollable messages container - Only messages scroll */
    .chat-messages-container {
        flex: 1 1 auto !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        padding: 15px 10px !important;
        margin-bottom: 0 !important;
        min-height: 200px !important;
        max-height: none !important;
        scroll-behavior: smooth !important;
        -webkit-overflow-scrolling: touch !important;
    }
    
    /* Scrollbar styling for messages container */
    .chat-messages-container::-webkit-scrollbar {
        width: 8px;
    }
    
    .chat-messages-container::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.1);
        border-radius: 10px;
    }
    
    .chat-messages-container::-webkit-scrollbar-thumb {
        background: rgba(20, 184, 166, 0.5);
        border-radius: 10px;
    }
    
    .chat-messages-container::-webkit-scrollbar-thumb:hover {
        background: rgba(20, 184, 166, 0.7);
    }
    
    /* Chat input form - Fixed at bottom */
    .chat-input-form {
        position: relative !important;
        background: rgba(0, 0, 0, 0.95) !important;
        padding: 1rem !important;
        z-index: 100 !important;
        border-top: 1px solid rgba(20, 184, 166, 0.3) !important;
        margin-top: auto !important;
        flex-shrink: 0 !important;
        width: 100% !important;
    }
    
    /* Chat sidebar expanders - Glass morphism effect */
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.25) 100%) !important;
        backdrop-filter: blur(15px) saturate(150%) !important;
        -webkit-backdrop-filter: blur(15px) saturate(150%) !important;
        border: 1.5px solid rgba(255,255,255,0.4) !important;
        border-radius: 12px !important;
        padding: 1rem 1.5rem !important;
        color: #1a1a1a !important;
        font-weight: 600 !important;
        margin-bottom: 0.5rem !important;
        transition: all 0.3s ease !important;
    }
    
    .streamlit-expanderHeader:hover {
        background: linear-gradient(135deg, rgba(255,255,255,0.25) 0%, rgba(255,255,255,0.35) 100%) !important;
        border-color: rgba(255,255,255,0.6) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(255,255,255,0.2) !important;
    }
    
    .streamlit-expanderContent {
        background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.15) 100%) !important;
        backdrop-filter: blur(15px) saturate(150%) !important;
        -webkit-backdrop-filter: blur(15px) saturate(150%) !important;
        border: 1.5px solid rgba(255,255,255,0.3) !important;
        border-top: none !important;
        border-radius: 0 0 12px 12px !important;
        padding: 1.5rem !important;
        margin-top: -0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* All chat sidebar buttons - Glass morphism */
    div[data-testid="column"] button {
        background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.25) 100%) !important;
        backdrop-filter: blur(15px) saturate(150%) !important;
        -webkit-backdrop-filter: blur(15px) saturate(150%) !important;
        border: 1.5px solid rgba(255,255,255,0.4) !important;
        border-radius: 12px !important;
        color: #1a1a1a !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
        margin-bottom: 0.5rem !important;
    }
    
    div[data-testid="column"] button:hover {
        background: linear-gradient(135deg, rgba(255,255,255,0.25) 0%, rgba(255,255,255,0.35) 100%) !important;
        border-color: rgba(255,255,255,0.6) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(255,255,255,0.2) !important;
    }
    
    /* Prevent overall page overflow - Only apply to chat page */
    div[data-testid="column"]:has(.chat-wrapper) + div[data-testid="column"],
    div[data-testid="column"]:has(.chat-wrapper) {
        max-height: 90vh !important;
    }
    
    /* Prevent main section overflow */
    section[data-testid="stMain"] {
        overflow-y: auto !important;
    }
    </style>
    <script>
    // Auto-scroll to bottom when page loads or messages change
    function scrollToBottom() {
        const container = document.querySelector('.chat-messages-container');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }
    
    // Run on load
    window.addEventListener('load', function() {
        setTimeout(scrollToBottom, 500);
    });
    
    // Run after DOM updates
    setTimeout(scrollToBottom, 1000);
    
    // Use MutationObserver to detect new messages
    const observer = new MutationObserver(function(mutations) {
        scrollToBottom();
    });
    
    // Start observing when container is available
    setTimeout(function() {
        const container = document.querySelector('.chat-messages-container');
        if (container) {
            observer.observe(container, { childList: true, subtree: true });
            scrollToBottom();
        }
    }, 1000);
    </script>
    """, unsafe_allow_html=True)
    
    # Get current chat from session state or default to "ALL"
    if 'current_chat_id' not in st.session_state:
        cur.execute('SELECT id FROM chat_conversations WHERE chat_type=%s', ('all',))
        all_chat = cur.fetchone()
        st.session_state.current_chat_id = all_chat['id'] if all_chat else None
    
    # Get all chats user is part of
    cur.execute('''
        SELECT cc.* FROM chat_conversations cc
        INNER JOIN chat_participants cp ON cc.id = cp.chat_id
        WHERE cp.username = %s
        ORDER BY cc.chat_type, cc.created_at DESC
    ''', (user['username'],))
    user_chats = cur.fetchall()
    
    # Chat selection and creation in main content (using columns)
    col_chat_list, col_chat_main = st.columns([3, 7])
    
    with col_chat_list:
        # Side box with all options - No headline
        # User name at top
        first_name = user.get("first_name", "")
        last_name = user.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip() or user.get("username", "User")
        
        st.markdown(f"""
        <div style="padding: 1rem; background: rgba(20, 184, 166, 0.1); border-radius: 8px; margin-bottom: 1rem;">
            <h4 style="margin: 0; color: #14b8a6; font-weight: 600;">{full_name}</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Create one-on-one chat
        with st.expander("👤 Start New Chat", expanded=False):
            # Get all users for one-on-one selection
            cur.execute('SELECT username FROM users WHERE username != %s ORDER BY username', (user['username'],))
            all_users_list = [row['username'] for row in cur.fetchall()]
            
            with st.form("create_individual_chat"):
                selected_user = st.selectbox("Select User to Chat With", options=all_users_list)
                create_individual = st.form_submit_button("Start Chat")
                
                if create_individual and selected_user:
                    # Check if chat already exists
                    cur.execute('''
                        SELECT cc.id FROM chat_conversations cc
                        INNER JOIN chat_participants cp1 ON cc.id = cp1.chat_id
                        INNER JOIN chat_participants cp2 ON cc.id = cp2.chat_id
                        WHERE cc.chat_type = 'individual'
                        AND cp1.username = %s AND cp2.username = %s
                        LIMIT 1
                    ''', (user['username'], selected_user))
                    existing_chat = cur.fetchone()
                    
                    if existing_chat:
                        st.session_state.current_chat_id = existing_chat['id']
                        st.rerun()
                    else:
                        # Create new individual chat
                        cur.execute('''
                            INSERT INTO chat_conversations (chat_type, created_by)
                            VALUES (%s, %s)
                            RETURNING id
                        ''', ('individual', user['username']))
                        new_chat_id = cur.fetchone()[0]
                        
                        # Add both users
                        cur.execute('INSERT INTO chat_participants (chat_id, username) VALUES (%s, %s)', (new_chat_id, user['username']))
                        cur.execute('INSERT INTO chat_participants (chat_id, username) VALUES (%s, %s)', (new_chat_id, selected_user))
                        
                        conn.commit()
                        st.session_state.current_chat_id = new_chat_id
                        st.success("Chat created!")
                        st.rerun()
        
        # Create new group chat
        with st.expander("➕ Create Group Chat", expanded=False):
            # Get all users for group selection
            cur.execute('SELECT username FROM users WHERE username != %s ORDER BY username', (user['username'],))
            all_users_for_group = [row['username'] for row in cur.fetchall()]
            
            with st.form("create_group"):
                group_name = st.text_input("Group Name")
                selected_users = st.multiselect("Select Users", options=all_users_for_group)
                create_group = st.form_submit_button("Create")
                
                if create_group and group_name:
                    # Create new group chat
                    join_link = f"GRP_{uuid.uuid4().hex[:12].upper()}"
                    cur.execute('''
                        INSERT INTO chat_conversations (chat_name, chat_type, created_by, join_link)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    ''', (group_name, 'group', user['username'], join_link))
                    new_chat_id = cur.fetchone()[0]
                    
                    # Add creator and selected users
                    cur.execute('INSERT INTO chat_participants (chat_id, username) VALUES (%s, %s)', (new_chat_id, user['username']))
                    for selected_user in selected_users:
                        cur.execute('INSERT INTO chat_participants (chat_id, username) VALUES (%s, %s) ON CONFLICT DO NOTHING', (new_chat_id, selected_user))
                    
                    conn.commit()
                    st.session_state.current_chat_id = new_chat_id
                    st.success("Group created!")
                    st.rerun()
        
        # Join group by link
        with st.expander("🔗 Join Group by Link", expanded=False):
            with st.form("join_group"):
                join_link = st.text_input("Enter Join Link")
                join_btn = st.form_submit_button("Join")
                
                if join_btn and join_link:
                    cur.execute('SELECT id FROM chat_conversations WHERE join_link=%s', (join_link,))
                    target_chat = cur.fetchone()
                    if target_chat:
                        cur.execute('INSERT INTO chat_participants (chat_id, username) VALUES (%s, %s) ON CONFLICT DO NOTHING', 
                                   (target_chat['id'], user['username']))
                        conn.commit()
                        st.success("Joined group!")
                        st.rerun()
                    else:
                        st.error("Invalid join link")
        
        # List of chats
        st.markdown("---")
        if user_chats:
            for chat in user_chats:
                chat_label = chat['chat_name'] if chat['chat_name'] else f"Chat #{chat['id']}"
                if chat['chat_type'] == 'individual':
                    # For individual chats, show other participant's name
                    cur.execute('''
                        SELECT u.username FROM chat_participants cp
                        JOIN users u ON cp.username = u.username
                        WHERE cp.chat_id = %s AND cp.username != %s
                        LIMIT 1
                    ''', (chat['id'], user['username']))
                    other_user = cur.fetchone()
                    if other_user:
                        chat_label = other_user['username']
                
                if st.button(f"📩 {chat_label}", key=f"chat_btn_{chat['id']}"):
                    st.session_state.current_chat_id = chat['id']
                    st.rerun()
    
    with col_chat_main:
        # Main chat area
        current_chat_id = st.session_state.get('current_chat_id')
        if current_chat_id:
            # Get chat info
            cur.execute('SELECT * FROM chat_conversations WHERE id=%s', (current_chat_id,))
            current_chat = cur.fetchone()
            
            if current_chat:
                chat_name = current_chat['chat_name'] if current_chat['chat_name'] else f"Chat #{current_chat_id}"
                
                # Get messages for current chat
                cur.execute('''
                    SELECT c.*, u.first_name, u.last_name, u.department, u.designation
                    FROM chats c
                    LEFT JOIN users u ON c.sender_username = u.username
                    WHERE c.chat_id = %s
                    ORDER BY c.created_at DESC
                    LIMIT 100
                ''', (current_chat_id,))
                messages = cur.fetchall()
                messages.reverse()
                
                # Chat header
                # Get chat participants for display
                cur.execute('''
                    SELECT u.username, u.first_name, u.last_name FROM chat_participants cp
                    JOIN users u ON cp.username = u.username
                    WHERE cp.chat_id = %s AND cp.username != %s
                ''', (current_chat_id, user['username']))
                participants = cur.fetchall()
                
                if current_chat['chat_type'] == 'individual' and participants:
                    display_name = f"{participants[0]['first_name']} {participants[0]['last_name']}" if participants[0]['first_name'] else participants[0]['username']
                    avatar_initials = ''.join([n[0].upper() for n in display_name.split()[:2]])
                elif current_chat['chat_type'] == 'group':
                    display_name = chat_name
                    avatar_initials = ''.join([w[0].upper() for w in chat_name.split()[:2]])
                else:
                    display_name = "General Chat"
                    avatar_initials = "GC"
                
                # User name at top with three dots menu
                first_name = user.get("first_name", "")
                last_name = user.get("last_name", "")
                user_full_name = f"{first_name} {last_name}".strip() or user.get("username", "User")
                
                # Three dots menu key
                menu_key = f"chat_menu_{current_chat_id}"
                
                # Check if menu is open
                if f'{menu_key}_open' not in st.session_state:
                    st.session_state[f'{menu_key}_open'] = False
                
                # Initialize clear chat dialog state
                if f'clear_chat_dialog_{current_chat_id}' not in st.session_state:
                    st.session_state[f'clear_chat_dialog_{current_chat_id}'] = False
                
                # Header with three dots menu - Using columns
                col_header_left, col_header_right = st.columns([9, 1])
                with col_header_left:
                    st.markdown(f"""
                    <div style="padding: 1rem; background: rgba(0, 0, 0, 0.95); border-bottom: 1px solid rgba(20, 184, 166, 0.3); position: sticky; top: 0; z-index: 100;">
                        <h4 style="margin: 0; color: #ffffff; font-weight: 600;">{user_full_name}</h4>
                        <p style="margin: 0.25rem 0 0 0; color: #94a3b8; font-size: 13px;">{display_name}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_header_right:
                    # Three dots menu button
                    if st.button("⋮", key=f"three_dots_{current_chat_id}", help="More options"):
                        st.session_state[f'{menu_key}_open'] = not st.session_state.get(f'{menu_key}_open', False)
                
                # Three dots menu dropdown - Show below button
                if st.session_state.get(f'{menu_key}_open', False):
                    st.markdown(f"""
                    <div style="background: #ffffff; border: 1px solid #dee2e6; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); padding: 0.5rem 0; margin-top: -10px; margin-bottom: 10px;">
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Clear Chat", key=f"clear_chat_btn_{current_chat_id}", use_container_width=True):
                        st.session_state[f'clear_chat_dialog_{current_chat_id}'] = True
                        st.session_state[f'{menu_key}_open'] = False
                        st.rerun()
                
                # Clear Chat Dialog
                if st.session_state.get(f'clear_chat_dialog_{current_chat_id}', False):
                    st.markdown("---")
                    st.warning("⚠️ Clear Chat")
                    delete_option = st.radio(
                        "Delete messages:",
                        ["Delete from everyone", "Delete from me"],
                        key=f"delete_option_{current_chat_id}"
                    )
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Confirm", key=f"confirm_delete_{current_chat_id}", type="primary"):
                            if delete_option == "Delete from everyone":
                                # Get all message IDs before deletion to delete files
                                cur.execute('SELECT id FROM chats WHERE chat_id = %s', (current_chat_id,))
                                message_ids = [row[0] for row in cur.fetchall()]
                                
                                # Delete associated attachments and files
                                for msg_id in message_ids:
                                    cur.execute('SELECT file_path FROM chat_attachments WHERE chat_message_id = %s', (msg_id,))
                                    attachments = cur.fetchall()
                                    for att in attachments:
                                        file_path = att[0]
                                        if os.path.exists(file_path):
                                            try:
                                                os.remove(file_path)
                                            except Exception as e:
                                                pass  # File already deleted or permission issue
                                
                                # Delete all messages from this chat (attachments will be deleted via CASCADE)
                                cur.execute('DELETE FROM chats WHERE chat_id = %s', (current_chat_id,))
                                conn.commit()
                                st.success("All messages deleted from everyone!")
                                st.session_state[f'clear_chat_dialog_{current_chat_id}'] = False
                                st.rerun()
                            else:  # Delete from me
                                # Get message IDs for user's messages to delete files
                                cur.execute('SELECT id FROM chats WHERE chat_id = %s AND sender_username = %s', 
                                          (current_chat_id, user['username']))
                                message_ids = [row[0] for row in cur.fetchall()]
                                
                                # Delete associated attachments and files
                                for msg_id in message_ids:
                                    cur.execute('SELECT file_path FROM chat_attachments WHERE chat_message_id = %s', (msg_id,))
                                    attachments = cur.fetchall()
                                    for att in attachments:
                                        file_path = att[0]
                                        if os.path.exists(file_path):
                                            try:
                                                os.remove(file_path)
                                            except Exception as e:
                                                pass  # File already deleted or permission issue
                                
                                # Delete only messages sent by current user (attachments will be deleted via CASCADE)
                                cur.execute('DELETE FROM chats WHERE chat_id = %s AND sender_username = %s', 
                                          (current_chat_id, user['username']))
                                conn.commit()
                                st.success("Your messages deleted!")
                                st.session_state[f'clear_chat_dialog_{current_chat_id}'] = False
                                st.rerun()
                    with col2:
                        if st.button("Cancel", key=f"cancel_delete_{current_chat_id}"):
                            st.session_state[f'clear_chat_dialog_{current_chat_id}'] = False
                            st.rerun()
                
                # Show join link if it's a group chat (inside scrollable area)
                join_link_html = ""
                if current_chat['join_link']:
                    join_link_html = f"<div style='padding: 10px 20px; background: rgba(20, 184, 166, 0.1); border-left: 3px solid #14b8a6; color: #14b8a6; margin-bottom: 10px;'>🔗 Join Link: <code>{current_chat['join_link']}</code></div>"
                
                # Chat wrapper for proper structure
                st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
                
                # Scrollable messages container - Fixed position
                st.markdown(f'<div class="chat-messages-container">{join_link_html}', unsafe_allow_html=True)
                
                # Display messages in Telegram-like style
                if messages:
                    for msg in messages:
                        # Get attachments for this message
                        cur.execute('''
                            SELECT * FROM chat_attachments
                            WHERE chat_message_id = %s
                        ''', (msg['id'],))
                        attachments = cur.fetchall()
                        
                        is_own_message = msg['sender_username'] == user['username']
                        sender_name = f"{msg['first_name']} {msg['last_name']}" if msg['first_name'] else msg['sender_username']
                        timestamp = msg['created_at'].strftime('%H:%M') if msg['created_at'] else 'N/A'
                        
                        if is_own_message:
                            # Right-aligned message (own) - Telegram style
                            st.markdown(f'''
                            <div class="telegram-message-own">
                                <div class="telegram-message-own-content">
                                    {msg['message'] or ''}
                                    <div class="telegram-message-time">{timestamp} ✓</div>
                                </div>
                            </div>
                            ''', unsafe_allow_html=True)
                            
                            # Display attachments separately below message
                            if attachments:
                                for att in attachments:
                                    if att['file_type'] == 'image':
                                        st.image(att['file_path'], width=250)
                                    elif att['file_type'] == 'audio':
                                        if os.path.exists(att['file_path']):
                                            with open(att['file_path'], "rb") as audio_file:
                                                st.audio(audio_file, format='audio/mpeg')
                                    elif att['file_type'] == 'pdf':
                                        if os.path.exists(att['file_path']):
                                            with open(att['file_path'], "rb") as pdf_file:
                                                st.download_button(
                                                    label=f"📄 {att['filename']}",
                                                    data=pdf_file,
                                                    file_name=att['filename'],
                                                    key=f"own_pdf_{msg['id']}_{att['id']}"
                                                )
                                    else:
                                        if os.path.exists(att['file_path']):
                                            with open(att['file_path'], "rb") as other_file:
                                                st.download_button(
                                                    label=f"📎 {att['filename']}",
                                                    data=other_file,
                                                    file_name=att['filename'],
                                                    key=f"own_file_{msg['id']}_{att['id']}"
                                                )
                        else:
                            # Left-aligned message (others) with avatar
                            sender_initials = ''.join([n[0].upper() for n in sender_name.split()[:2]]) if sender_name else 'U'
                            
                            st.markdown(f'''
                            <div class="telegram-message-other">
                                <div class="telegram-avatar">{sender_initials}</div>
                                <div class="telegram-message-other-content">
                                    <div class="telegram-message-sender">{sender_name}</div>
                                    {msg['message'] or ''}
                                    <div class="telegram-message-time">{timestamp}</div>
                                </div>
                            </div>
                            ''', unsafe_allow_html=True)
                            
                            # Display attachments separately below message
                            if attachments:
                                for att in attachments:
                                    if att['file_type'] == 'image':
                                        st.image(att['file_path'], width=250)
                                    elif att['file_type'] == 'audio':
                                        if os.path.exists(att['file_path']):
                                            with open(att['file_path'], "rb") as audio_file:
                                                st.audio(audio_file, format='audio/mpeg')
                                    elif att['file_type'] == 'pdf':
                                        if os.path.exists(att['file_path']):
                                            with open(att['file_path'], "rb") as pdf_file:
                                                st.download_button(
                                                    label=f"📄 {att['filename']}",
                                                    data=pdf_file,
                                                    file_name=att['filename'],
                                                    key=f"other_pdf_{msg['id']}_{att['id']}"
                                                )
                                    else:
                                        if os.path.exists(att['file_path']):
                                            with open(att['file_path'], "rb") as other_file:
                                                st.download_button(
                                                    label=f"📎 {att['filename']}",
                                                    data=other_file,
                                                    file_name=att['filename'],
                                                    key=f"other_file_{msg['id']}_{att['id']}"
                                                )
                else:
                    st.info("No messages yet. Start the conversation!")
                
                # Close scrollable messages container
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Message input - Fixed at bottom (inside wrapper)
                # File uploaders outside form
                with st.expander("➕ Attach", expanded=False):
                    uploaded_attachments = st.file_uploader(
                        "📎 Upload files (Images, PDFs, Audio, Documents, etc.)",
                        type=['png', 'jpg', 'jpeg', 'pdf', 'mp3', 'wav', 'ogg', 'm4a', 'doc', 'docx', 'xlsx', 'xls', 'txt'],
                        accept_multiple_files=True,
                        key=f"chat_upload_{current_chat_id}"
                    )
                    
                    # Camera input only shows when explicitly requested
                    if st.button("📷 Take a photo", key=f"camera_btn_{current_chat_id}"):
                        st.session_state[f'show_camera_{current_chat_id}'] = True
                    
                    if st.session_state.get(f'show_camera_{current_chat_id}', False):
                        uploaded_camera = st.camera_input("📷 Camera", key=f"chat_camera_{current_chat_id}", label_visibility="collapsed")
                        if uploaded_camera:
                            st.session_state[f'show_camera_{current_chat_id}'] = False
                    else:
                        uploaded_camera = None
                
                st.markdown('<div class="chat-input-form">', unsafe_allow_html=True)
                with st.form("chat_form", clear_on_submit=True):
                    col1, col2 = st.columns([10, 2])
                    with col1:
                        chat_message = st.text_input("Type your message...", key="chat_input", placeholder="Type a message", label_visibility="collapsed")
                    with col2:
                        submitted = st.form_submit_button("📤 Send")
                    
                    # Combine all uploads
                    uploaded_files = []
                    if uploaded_attachments:
                        uploaded_files.extend(uploaded_attachments)
                    if uploaded_camera:
                        uploaded_files.append(uploaded_camera)
                    
                    if submitted and (chat_message or uploaded_files):
                        # Create message
                        cur.execute('''
                            INSERT INTO chats (chat_id, sender_username, message)
                            VALUES (%s, %s, %s)
                            RETURNING id
                        ''', (current_chat_id, user['username'], chat_message or ""))
                        message_id = cur.fetchone()[0]
                        
                        # Handle file uploads
                        if uploaded_files:
                            chat_uploads_dir = os.path.join("uploads", "chat_attachments")
                            if not os.path.exists(chat_uploads_dir):
                                os.makedirs(chat_uploads_dir)
                            
                            for uploaded_file in uploaded_files:
                                # Generate unique filename
                                if hasattr(uploaded_file, 'name') and uploaded_file.name:
                                    file_extension = os.path.splitext(uploaded_file.name)[1]
                                    filename = uploaded_file.name
                                else:
                                    # Voice recorder or other files without name
                                    file_extension = '.wav'
                                    filename = 'voice_recording.wav'
                                
                                unique_filename = f"{uuid.uuid4()}{file_extension}"
                                file_path = os.path.join(chat_uploads_dir, unique_filename)
                                
                                # Save file
                                with open(file_path, "wb") as f:
                                    f.write(uploaded_file.getbuffer())
                                
                                # Determine file type
                                file_type = 'other'
                                if file_extension.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                                    file_type = 'image'
                                elif file_extension.lower() == '.pdf':
                                    file_type = 'pdf'
                                elif file_extension.lower() in ['.mp3', '.wav', '.ogg', '.m4a']:
                                    file_type = 'audio'
                                elif file_extension.lower() in ['.doc', '.docx']:
                                    file_type = 'document'
                                elif file_extension.lower() in ['.xlsx', '.xls']:
                                    file_type = 'excel'
                                
                                # Get file size
                                file_size = uploaded_file.size if hasattr(uploaded_file, 'size') else os.path.getsize(file_path)
                                
                                # Save to database
                                cur.execute('''
                                    INSERT INTO chat_attachments (chat_message_id, filename, file_path, file_type, file_size, uploaded_by)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                ''', (message_id, filename, file_path, file_type, file_size, user['username']))
                        
                        conn.commit()
                        st.rerun()
                    elif submitted:
                        st.warning("Please enter a message or attach a file.")
                st.markdown('</div>', unsafe_allow_html=True)  # Close chat-input-form
                st.markdown('</div>', unsafe_allow_html=True)  # Close chat-wrapper
            else:
                st.info("Chat not found.")
        else:
            st.info("Select or create a chat to start messaging.")

def show_users_management(conn, cur):
    st.header("👥 Users Management")
    
    # Director creation section
    with st.expander("➕ Create Director Account", expanded=False):
        with st.form("Create Director"):
            st.markdown("**Create a new director account:**")
            dir_username = st.text_input("Director Username *", key="dir_username")
            dir_password = st.text_input("Director Password *", type="password", key="dir_password")
            dir_first_name = st.text_input("First Name *", key="dir_first")
            dir_last_name = st.text_input("Last Name *", key="dir_last")
            
            if st.form_submit_button("Create Director"):
                if not all([dir_username, dir_password, dir_first_name, dir_last_name]):
                    st.warning("Please fill all required fields.")
                else:
                    try:
                        # Check if username exists
                        cur.execute('SELECT * FROM users WHERE username=%s', (dir_username,))
                        if cur.fetchone():
                            st.error("Username already exists.")
                        else:
                            # Generate a random employee ID for director (12 digits)
                            dir_employee_id = f"DIR{random.randint(100000000, 999999999)}"
                            
                            hashed_pw = bcrypt.hashpw(dir_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                            # Directors have "All Departments" as their department and "DIRECTOR" as designation
                            cur.execute('''
                                INSERT INTO users (username, password, employee_id, first_name, last_name, department, designation, is_admin, is_director)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, TRUE)
                            ''', (dir_username, hashed_pw, dir_employee_id, dir_first_name, dir_last_name, "All Departments", "DIRECTOR"))
                            conn.commit()
                            st.success(f"Director '{dir_username}' created successfully with Employee ID: {dir_employee_id}!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error creating director: {str(e)}")
    
    # Get all users
    cur.execute('''
        SELECT username, employee_id, first_name, last_name, department, designation, is_admin, is_director
        FROM users 
        ORDER BY is_admin DESC, is_director DESC, first_name, last_name
    ''')
    all_users = cur.fetchall()
    
    st.metric("Total Users", len(all_users))
    
    # Search and filter
    search_term = st.text_input("🔍 Search by name, username, employee ID, or department", key="user_search")
    
    # Filter users
    filtered_users = []
    for u in all_users:
        search_text = f"{u['first_name']} {u['last_name']} {u['username']} {u['employee_id']} {u['department']}".lower()
        if not search_term or search_term.lower() in search_text:
            filtered_users.append(u)
    
    if not filtered_users:
        st.info("No users found.")
    else:
        # Create DataFrame for table view
        users_data = []
        for u in filtered_users:
            # Get task count for this user
            cur.execute('''
                SELECT COUNT(*) as task_count 
                FROM task_assignments 
                WHERE username = %s
            ''', (u['username'],))
            task_count = cur.fetchone()['task_count']
            
            # Determine role
            if u.get('is_admin', False):
                role = "Admin"
            elif u.get('is_director', False):
                role = "Director"
            else:
                role = "Employee"
            
            users_data.append({
                "Role": role,
                "Full Name": f"{u['first_name']} {u['last_name']}",
                "Username": u['username'],
                "Employee ID": u['employee_id'],
                "Department": u['department'],
                "Designation": u['designation'],
                "Total Tasks": task_count,
                "Is Director": "Yes" if u.get('is_director', False) else "No"
            })
        
        # Display table
        st.markdown("### 📊 All Employees Overview")
        
        # Display dataframe with delete button column
        df_users = pd.DataFrame(users_data)
        with st.expander("📋 View as DataFrame", expanded=True):
            # Add CSS for simple delete button styling
            st.markdown("""
            <style>
                /* Simple delete button with border - style buttons in delete column */
                div[data-testid="stExpander"] .stButton > button {
                    background: transparent !important;
                    border: 1px solid #14b8a6 !important;
                    color: #14b8a6 !important;
                    border-radius: 4px !important;
                    padding: 0.25rem 0.5rem !important;
                    font-weight: 500 !important;
                    box-shadow: none !important;
                    transition: all 0.2s ease !important;
                }
                
                div[data-testid="stExpander"] .stButton > button:hover {
                    background: rgba(20, 184, 166, 0.1) !important;
                    border-color: #14b8a6 !important;
                    color: #14b8a6 !important;
                }
            </style>
            """, unsafe_allow_html=True)
            # Create custom table with delete button column
            # Table header
            col_headers = st.columns([1, 2, 1.5, 1.5, 2, 1.5, 1, 1, 1.5])
            headers = ["Role", "Full Name", "Username", "Employee ID", "Department", "Designation", "Total Tasks", "Is Director", "Delete"]
            for idx, header in enumerate(headers):
                with col_headers[idx]:
                    st.markdown(f"**{header}**")
            
            st.divider()
            
            # Table rows with delete buttons
            for idx, u in enumerate(filtered_users):
                # Get task count for this user
                cur.execute('''
                    SELECT COUNT(*) as task_count 
                    FROM task_assignments 
                    WHERE username = %s
                ''', (u['username'],))
                task_count = cur.fetchone()['task_count']
                
                # Determine role
                if u.get('is_admin', False):
                    role = "Admin"
                elif u.get('is_director', False):
                    role = "Director"
                else:
                    role = "Employee"
                
                # Create row columns
                col_row = st.columns([1, 2, 1.5, 1.5, 2, 1.5, 1, 1, 1.5])
                
                with col_row[0]:
                    st.write(role)
                with col_row[1]:
                    st.write(f"{u['first_name']} {u['last_name']}")
                with col_row[2]:
                    st.write(u['username'])
                with col_row[3]:
                    st.write(u['employee_id'])
                with col_row[4]:
                    st.write(u['department'])
                with col_row[5]:
                    st.write(u['designation'])
                with col_row[6]:
                    st.write(task_count)
                with col_row[7]:
                    st.write("Yes" if u.get('is_director', False) else "No")
                with col_row[8]:
                    # Delete button column
                    if u.get('is_admin', False):
                        st.info("Admin")
                    else:
                        current_username = st.session_state.get('user', {}).get('username')
                        if current_username == u['username']:
                            st.warning("You")
                        else:
                            if st.button("🗑️ Delete", key=f"df_delete_{u['username']}", use_container_width=True):
                                try:
                                    cur.execute('DELETE FROM users WHERE username=%s', (u['username'],))
                                    conn.commit()
                                    st.success(f"User '{u['username']}' deleted successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting user: {str(e)}")
                
                st.divider()
        
        st.markdown("---")
        st.subheader("Detailed View")
        
        # Search input for detailed view
        detailed_search = st.text_input("🔍 Search Employee by Name or Employee ID", key="detailed_search", placeholder="Enter employee name or ID to view details")
        
        # Filter users for detailed view based on search
        detailed_users = []
        if detailed_search:
            search_lower = detailed_search.lower().strip()
            for u in filtered_users:
                full_name = f"{u['first_name']} {u['last_name']}".lower()
                employee_id = u['employee_id'].lower()
                username = u['username'].lower()
                
                if (search_lower in full_name or 
                    search_lower in employee_id or 
                    search_lower in username):
                    detailed_users.append(u)
        else:
            # If no search, show all users
            detailed_users = filtered_users
        
        if detailed_search and not detailed_users:
            st.warning(f"No employee found matching '{detailed_search}'. Please check the name or Employee ID.")
        
        for u in detailed_users:
            with st.container():
                # User header
                if u.get('is_admin', False):
                    role_badge = "👑 Admin"
                elif u.get('is_director', False):
                    role_badge = "🎯 Director"
                else:
                    role_badge = "👤 Employee"
                
                st.markdown(f"### {role_badge} - {u['first_name']} {u['last_name']}")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.markdown(f"**Username:** {u['username']}")
                    st.markdown(f"**Employee ID:** {u['employee_id']}")
                with col2:
                    st.markdown(f"**Department:** {u['department']}")
                    st.markdown(f"**Designation:** {u['designation']}")
                with col3:
                    # Get task count for this user
                    cur.execute('''
                        SELECT COUNT(*) as task_count 
                        FROM task_assignments 
                        WHERE username = %s
                    ''', (u['username'],))
                    task_count = cur.fetchone()['task_count']
                    st.metric("Total Tasks", task_count)
                with col4:
                    # Director status toggle
                    is_current_director = u.get('is_director', False)
                    make_director = st.checkbox("Make Director", value=is_current_director, key=f"director_{u['username']}")
                    if make_director != is_current_director:
                        try:
                            cur.execute('UPDATE users SET is_director=%s WHERE username=%s', (make_director, u['username']))
                            conn.commit()
                            st.success(f"Director status updated for {u['username']}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating director status: {str(e)}")
                    
                    # Delete user button
                    if u.get('is_admin', False):
                        st.warning("Cannot delete admin account")
                    else:
                        if st.button("🗑️ Delete User", key=f"delete_user_{u['username']}"):
                            try:
                                # Check current user (prevent deleting yourself)
                                current_username = st.session_state.get('user', {}).get('username')
                                if current_username == u['username']:
                                    st.error("You cannot delete your own account!")
                                else:
                                    # Delete user (CASCADE will handle task_assignments)
                                    cur.execute('DELETE FROM users WHERE username=%s', (u['username'],))
                                    conn.commit()
                                    st.success(f"User '{u['username']}' deleted successfully!")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting user: {str(e)}")
                
                # Show user's tasks
                cur.execute('''
                    SELECT t.* FROM tasks t
                    INNER JOIN task_assignments ta ON t.id = ta.task_id
                    WHERE ta.username = %s
                    ORDER BY 
                        CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
                        t.created_at DESC
                ''', (u['username'],))
                user_tasks = cur.fetchall()
                
                # Show user's tasks in a better format
                if user_tasks:
                    st.markdown(f"### 📋 Tasks Assigned ({len(user_tasks)} task(s))")
                    
                    # Create a table for tasks
                    tasks_data = []
                    for task in user_tasks:
                        # Priority icons
                        priority_colors = {
                            'urgent': '🔴',
                            'high': '🟠',
                            'medium': '🟡',
                            'low': '🟢'
                        }
                        priority_icon = priority_colors.get(task['priority'], '⚪')
                        
                        # Status icons
                        status_badges = {
                            'pending': '⏳',
                            'due': '⏰',
                            'completed': '✅'
                        }
                        status_icon = status_badges.get(task['status'], '📋')
                        
                        tasks_data.append({
                            "Task ID": task['id'],
                            "Title": task['title'],
                            "Description": task['desc'] or 'N/A',
                            "Priority": f"{priority_icon} {task['priority'].upper()}",
                            "Status": f"{status_icon} {task['status'].upper()}",
                            "Due Date": task['due_date'].strftime('%Y-%m-%d') if task['due_date'] else 'Not set',
                            "Created": task['created_at'].strftime('%Y-%m-%d') if task['created_at'] else 'N/A'
                        })
                    
                    df_tasks = pd.DataFrame(tasks_data)
                    st.dataframe(df_tasks, width='stretch', hide_index=True, use_container_width=True)
                    
                    # Also show expandable view
                    with st.expander(f"📋 View Detailed Task Information", expanded=False):
                        for task in user_tasks:
                            # Priority icons
                            priority_colors = {
                                'urgent': '🔴',
                                'high': '🟠',
                                'medium': '🟡',
                                'low': '🟢'
                            }
                            priority_icon = priority_colors.get(task['priority'], '⚪')
                            
                            # Status icons
                            status_badges = {
                                'pending': '⏳',
                                'due': '⏰',
                                'completed': '✅'
                            }
                            status_icon = status_badges.get(task['status'], '📋')
                            
                            st.markdown(f"""
                            **{task['title']}**  
                            {task['desc'] or ''}  
                            {priority_icon} Priority: {task['priority'].upper()} | {status_icon} Status: {task['status'].upper()}  
                            📅 Due: {task['due_date'].strftime('%Y-%m-%d') if task['due_date'] else 'Not set'}
                            📅 Created: {task['created_at'].strftime('%Y-%m-%d %H:%M') if task['created_at'] else 'N/A'}
                            """)
                            st.divider()
                else:
                    st.info("No tasks assigned to this user.")
                
                st.divider()

def show_departments_designations(conn, cur):
    st.header("🏢 Departments & Designations Management")
    
    dept_tab, desg_tab = st.tabs(["Departments", "Designations"])
    
    with dept_tab:
        st.subheader("📁 Departments")
        
        # Get all departments
        cur.execute('SELECT id, name, created_at FROM departments ORDER BY name')
        departments = cur.fetchall()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.metric("Total Departments", len(departments))
        
        # Add new department
        with st.form("Add Department"):
            new_dept = st.text_input("Department Name *", key="new_dept")
            if st.form_submit_button("Add Department"):
                if new_dept:
                    try:
                        cur.execute('INSERT INTO departments (name) VALUES (%s)', (new_dept.strip(),))
                        conn.commit()
                        st.success(f"Department '{new_dept}' added successfully!")
                        st.rerun()
                    except Exception as e:
                        if 'unique' in str(e).lower():
                            st.error(f"Department '{new_dept}' already exists!")
                        else:
                            st.error(f"Error: {str(e)}")
                else:
                    st.warning("Please enter a department name.")
        
        # List departments
        if departments:
            st.markdown("### Existing Departments")
            for dept in departments:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"• **{dept['name']}**")
                with col2:
                    if st.button("🗑️ Delete", key=f"del_dept_{dept['id']}"):
                        try:
                            # Check if any users have this department
                            cur.execute('SELECT COUNT(*) as count FROM users WHERE department=%s', (dept['name'],))
                            user_count = cur.fetchone()['count']
                            if user_count > 0:
                                st.error(f"Cannot delete! {user_count} user(s) assigned to this department.")
                            else:
                                cur.execute('DELETE FROM departments WHERE id=%s', (dept['id'],))
                                conn.commit()
                                st.success(f"Department '{dept['name']}' deleted!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
    
    with desg_tab:
        st.subheader("💼 Designations")
        
        # Get all designations
        cur.execute('SELECT id, name, created_at FROM designations ORDER BY name')
        designations = cur.fetchall()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.metric("Total Designations", len(designations))
        
        # Add new designation
        with st.form("Add Designation"):
            new_desg = st.text_input("Designation Name *", key="new_desg")
            if st.form_submit_button("Add Designation"):
                if new_desg:
                    try:
                        cur.execute('INSERT INTO designations (name) VALUES (%s)', (new_desg.strip(),))
                        conn.commit()
                        st.success(f"Designation '{new_desg}' added successfully!")
                        st.rerun()
                    except Exception as e:
                        if 'unique' in str(e).lower():
                            st.error(f"Designation '{new_desg}' already exists!")
                        else:
                            st.error(f"Error: {str(e)}")
                else:
                    st.warning("Please enter a designation name.")
        
        # List designations
        if designations:
            st.markdown("### Existing Designations")
            for desg in designations:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"• **{desg['name']}**")
                with col2:
                    if st.button("🗑️ Delete", key=f"del_desg_{desg['id']}"):
                        try:
                            # Check if any users have this designation
                            cur.execute('SELECT COUNT(*) as count FROM users WHERE designation=%s', (desg['name'],))
                            user_count = cur.fetchone()['count']
                            if user_count > 0:
                                st.error(f"Cannot delete! {user_count} user(s) assigned to this designation.")
                            else:
                                cur.execute('DELETE FROM designations WHERE id=%s', (desg['id'],))
                                conn.commit()
                                st.success(f"Designation '{desg['name']}' deleted!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

def show_notice_board(conn, cur, user, can_add_notices):
    st.header("📢 Notice Board")
    
    # Add/Edit Notice section (only for Admin and HR)
    if can_add_notices:
        with st.expander("➕ Add New Notice/Update", expanded=False):
            with st.form("Add Notice"):
                notice_title = st.text_input("Notice Title *")
                notice_content = st.text_area("Notice Content/Details *", height=200)
                is_active_notice = st.checkbox("Active", value=True, help="Only active notices are displayed")
                
                # File attachments for notices (images/PDFs for special occasions)
                notice_files = st.file_uploader(
                    "Attach Images or PDFs (Optional)",
                    type=['png', 'jpg', 'jpeg', 'pdf', 'gif'],
                    accept_multiple_files=True,
                    help="Upload images or PDFs for special wishes or occasions"
                )
                
                submitted = st.form_submit_button("Publish Notice")
                if submitted:
                    if notice_title and notice_content:
                        try:
                            # Create notice
                            cur.execute('''
                                INSERT INTO notices (title, content, created_by, is_active)
                                VALUES (%s, %s, %s, %s) RETURNING id
                            ''', (notice_title.strip(), notice_content.strip(), user['username'], is_active_notice))
                            notice_id = cur.fetchone()['id']
                            
                            # Save attached files
                            if notice_files:
                                uploads_dir = "uploads/notices"
                                if not os.path.exists(uploads_dir):
                                    os.makedirs(uploads_dir)
                                
                                for uploaded_file in notice_files:
                                    # Generate unique filename
                                    file_extension = os.path.splitext(uploaded_file.name)[1]
                                    unique_filename = f"{uuid.uuid4()}{file_extension}"
                                    file_path = os.path.join(uploads_dir, unique_filename)
                                    
                                    # Save file to filesystem
                                    with open(file_path, "wb") as f:
                                        f.write(uploaded_file.getbuffer())
                                    
                                    # Determine file type
                                    if file_extension.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                                        file_type = 'image'
                                    elif file_extension.lower() == '.pdf':
                                        file_type = 'pdf'
                                    else:
                                        file_type = 'other'
                                    
                                    # Save file metadata to database
                                    cur.execute('''
                                        INSERT INTO notice_attachments (notice_id, filename, file_path, file_type, file_size, uploaded_by)
                                        VALUES (%s, %s, %s, %s, %s, %s)
                                    ''', (notice_id, uploaded_file.name, file_path, file_type, uploaded_file.size, user['username']))
                            
                            conn.commit()
                            st.success(f"Notice '{notice_title}' published successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error publishing notice: {str(e)}")
                    else:
                        st.warning("Please fill both title and content.")
    
    # Display all active notices
    st.subheader("📌 Active Notices & Updates")
    
    # Get all notices (admin/HR can see all, others see only active)
    if can_add_notices:
        cur.execute('''
            SELECT n.*, u.first_name, u.last_name, u.department
            FROM notices n
            LEFT JOIN users u ON n.created_by = u.username
            ORDER BY n.created_at DESC
        ''')
    else:
        cur.execute('''
            SELECT n.*, u.first_name, u.last_name, u.department
            FROM notices n
            LEFT JOIN users u ON n.created_by = u.username
            WHERE n.is_active = TRUE
            ORDER BY n.created_at DESC
        ''')
    
    notices = cur.fetchall()
    
    if not notices:
        st.info("No notices available at the moment.")
    else:
        for notice in notices:
            # Notice styling
            if notice['is_active']:
                notice_status = "🟢 Active"
                notice_color = "success"
            else:
                notice_status = "🔴 Inactive"
                notice_color = "warning"
            
            created_by_text = f"{notice['first_name']} {notice['last_name']}" if notice['first_name'] else notice['created_by'] or 'Unknown'
            department_text = f" ({notice['department']})" if notice['department'] else ""
            created_date = notice['created_at'].strftime('%Y-%m-%d %H:%M') if isinstance(notice['created_at'], datetime) else str(notice['created_at'])[:16]
            
            with st.container():
                # Get attachments for this notice
                cur.execute('''
                    SELECT id, filename, file_path, file_type, file_size
                    FROM notice_attachments
                    WHERE notice_id=%s
                    ORDER BY uploaded_at
                ''', (notice['id'],))
                attachments = cur.fetchall()
                
                # Notice card with better contrast
                border_color = "#4CAF50" if notice['is_active'] else "#ff9800"
                bg_color = "#ffffff"
                text_color = "#000000"
                title_color = "#1a5f1a"
                
                st.markdown(f"""
                <div style="border-left: 5px solid {border_color}; padding: 20px; margin: 15px 0; background-color: {bg_color}; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h3 style="color: {title_color}; margin-top: 0;">{notice['title']}</h3>
                    <p style="white-space: pre-wrap; color: {text_color}; font-size: 1em; line-height: 1.6;">{notice['content']}</p>
                    <p style="color: #555; font-size: 0.85em; margin-top: 10px; border-top: 1px solid #eee; padding-top: 10px;">
                        📅 Posted: {created_date} | 👤 By: {created_by_text}{department_text} | {notice_status}
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # Display attachments (images/PDFs) - outside the markdown div
                if attachments and len(attachments) > 0:
                    st.markdown("---")
                    st.markdown("### 🎉 Special Attachments (Wishes/Occasions)")
                    for att in attachments:
                        if att['file_type'] == 'image':
                            # Display image with better styling
                            file_path = att['file_path']
                            # Check if path exists
                            if os.path.exists(file_path):
                                try:
                                    st.markdown(f"**🖼️ Image: {att['filename']}**")
                                    # Display image
                                    st.image(file_path, caption=f"{att['filename']} - Wish/Occasion Image", width='stretch', clamp=True)
                                    st.markdown("---")
                                except Exception as e:
                                    st.warning(f"⚠️ Could not display image: {att['filename']} - {str(e)}")
                                    # Show download button as fallback
                                    try:
                                        with open(file_path, "rb") as file:
                                            file_data = file.read()
                                        st.download_button(
                                            label=f"📥 Download Image: {att['filename']}",
                                            data=file_data,
                                            file_name=att['filename'],
                                            key=f"notice_att_dl_{att['id']}",
                                            mime="image/jpeg"
                                        )
                                    except Exception as e2:
                                        st.error(f"Error loading file: {str(e2)}")
                            else:
                                st.warning(f"⚠️ Image file not found at path: {file_path}")
                                st.info(f"Debug: File path = {file_path}, File type = {att['file_type']}, Filename = {att['filename']}")
                        elif att['file_type'] == 'pdf':
                            # Show download link for PDFs
                            if os.path.exists(att['file_path']):
                                with open(att['file_path'], "rb") as file:
                                    file_data = file.read()
                                st.download_button(
                                    label=f"📄 Download PDF: {att['filename']}",
                                    data=file_data,
                                    file_name=att['filename'],
                                    key=f"notice_att_{att['id']}",
                                    mime="application/pdf"
                                )
                            else:
                                st.warning(f"⚠️ PDF file not found: {att['filename']}")
                        else:
                            # Other file types
                            if os.path.exists(att['file_path']):
                                with open(att['file_path'], "rb") as file:
                                    file_data = file.read()
                                st.download_button(
                                    label=f"📎 Download {att['filename']}",
                                    data=file_data,
                                    file_name=att['filename'],
                                    key=f"notice_att_{att['id']}",
                                    mime=att['file_type']
                                )
                            else:
                                st.warning(f"⚠️ File not found: {att['filename']} at {att['file_path']}")
                else:
                    # Debug: Show if no attachments found (for admin/HR only)
                    if can_add_notices:
                        pass  # Don't show anything if no attachments
                
                # Edit/Delete buttons for Admin and HR
                if can_add_notices:
                    col1, col2, col3 = st.columns([1, 1, 8])
                    
                    with col1:
                        if st.button("✏️ Edit", key=f"edit_notice_{notice['id']}"):
                            # Edit notice logic (using session state)
                            st.session_state[f"editing_notice_{notice['id']}"] = True
                            st.session_state[f"notice_{notice['id']}_title"] = notice['title']
                            st.session_state[f"notice_{notice['id']}_content"] = notice['content']
                            st.session_state[f"notice_{notice['id']}_active"] = notice['is_active']
                            st.rerun()
                    
                    with col2:
                        if st.button("🗑️ Delete", key=f"del_notice_{notice['id']}"):
                            try:
                                cur.execute('DELETE FROM notices WHERE id=%s', (notice['id'],))
                                conn.commit()
                                st.success("Notice deleted successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting notice: {str(e)}")
                    
                    # Show edit form if editing
                    if st.session_state.get(f"editing_notice_{notice['id']}", False):
                        with st.form(f"Edit Notice {notice['id']}"):
                            edit_title = st.text_input("Title", value=st.session_state.get(f"notice_{notice['id']}_title", ""))
                            edit_content = st.text_area("Content", value=st.session_state.get(f"notice_{notice['id']}_content", ""), height=150)
                            edit_active = st.checkbox("Active", value=st.session_state.get(f"notice_{notice['id']}_active", True))
                            
                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.form_submit_button("💾 Save Changes"):
                                    try:
                                        cur.execute('''
                                            UPDATE notices 
                                            SET title=%s, content=%s, is_active=%s, updated_at=CURRENT_TIMESTAMP
                                            WHERE id=%s
                                        ''', (edit_title.strip(), edit_content.strip(), edit_active, notice['id']))
                                        conn.commit()
                                        st.session_state[f"editing_notice_{notice['id']}"] = False
                                        st.success("Notice updated successfully!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error updating notice: {str(e)}")
                            
                            with col_cancel:
                                if st.form_submit_button("❌ Cancel"):
                                    st.session_state[f"editing_notice_{notice['id']}"] = False
                                    st.rerun()
                
                st.divider()

def show_admin_dashboard(conn, cur):
    st.header("📊 Admin Dashboard - Complete Data View")
    
    # Two sections: Directors Login Details and Tasks Details
    tab1, tab2 = st.tabs(["🎯 Directors Login Details", "📋 All Tasks Details"])
    
    with tab1:
        st.subheader("🎯 Directors Login Details")
        
        # Get all directors
        cur.execute('''
            SELECT username, password, employee_id, first_name, last_name, department, designation, is_director
            FROM users 
            WHERE is_director = TRUE
            ORDER BY first_name, last_name
        ''')
        directors = cur.fetchall()
        
        if not directors:
            st.info("No directors found in the system.")
        else:
            st.metric("Total Directors", len(directors))
            
            # Create table data
            directors_data = []
            for dir_user in directors:
                directors_data.append({
                    "Username": dir_user['username'],
                    "Password Hash": dir_user['password'][:50] + "..." if len(dir_user['password']) > 50 else dir_user['password'],
                    "Employee ID": dir_user['employee_id'],
                    "First Name": dir_user['first_name'],
                    "Last Name": dir_user['last_name'],
                    "Department": dir_user['department'],
                    "Designation": dir_user['designation']
                })
            
            # Display in table format
            df_directors = pd.DataFrame(directors_data)
            st.dataframe(df_directors, width='stretch', hide_index=True, height=600)
            
            # Export option
            csv_directors = df_directors.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Directors Data (CSV)",
                data=csv_directors,
                file_name=f"directors_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with tab2:
        st.subheader("📋 All Tasks Details")
        
        # Get all tasks with assigned users and attachments
        cur.execute('''
            SELECT 
                t.id, t.title, t.desc, t.priority, t.status, 
                t.created_at, t.due_date, t.completed_at
            FROM tasks t
            ORDER BY 
                CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
                t.created_at DESC
        ''')
        all_tasks = cur.fetchall()
        
        if not all_tasks:
            st.info("No tasks found in the system.")
        else:
            st.metric("Total Tasks", len(all_tasks))
            
            # Create table data with assigned users
            tasks_data = []
            for task in all_tasks:
                # Get assigned users for this task
                cur.execute('''
                    SELECT username, assigned_at 
                    FROM task_assignments 
                    WHERE task_id = %s
                    ORDER BY assigned_at
                ''', (task['id'],))
                assigned_users_data = cur.fetchall()
                assigned_users = ", ".join([f"{row['username']}" for row in assigned_users_data])
                
                # Get attachments count
                cur.execute('SELECT COUNT(*) as count FROM task_attachments WHERE task_id = %s', (task['id'],))
                attachments_count = cur.fetchone()['count']
                
                # Format dates
                created_date = task['created_at'].strftime('%Y-%m-%d %H:%M') if task['created_at'] else 'N/A'
                due_date = task['due_date'].strftime('%Y-%m-%d') if task['due_date'] else 'Not set'
                completed_date = task['completed_at'].strftime('%Y-%m-%d %H:%M') if task['completed_at'] else 'Not completed'
                
                tasks_data.append({
                    "Task ID": task['id'],
                    "Title": task['title'],
                    "Description": task['desc'] or 'No description',
                    "Priority": task['priority'].upper(),
                    "Status": task['status'].upper(),
                    "Assigned To": assigned_users or 'Unassigned',
                    "Created At": created_date,
                    "Due Date": due_date,
                    "Completed At": completed_date,
                    "Attachments": attachments_count
                })
            
            # Display in table format
            df_tasks = pd.DataFrame(tasks_data)
            st.dataframe(df_tasks, width='stretch', hide_index=True, height=600)
            
            # Export option
            csv_tasks = df_tasks.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Tasks Data (CSV)",
                data=csv_tasks,
                file_name=f"tasks_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

def show_tasks_page(conn, cur, user, is_admin):
    
    # Get all users for multi-select with their designations and departments
    cur.execute('SELECT username, designation, department FROM users ORDER BY username')
    all_users_data = cur.fetchall()
    all_users = [row['username'] for row in all_users_data]
    
    # Get current user's designation and department
    user_designation = user.get('designation', '')
    
    # Get current user's department from database
    cur.execute('SELECT department FROM users WHERE username=%s', (user['username'],))
    user_dept_result = cur.fetchone()
    user_department = user_dept_result['department'] if user_dept_result else None
    
    with st.form("Add task"):
        title = st.text_input("Task Title *")
        desc = st.text_area("Task Description")
        
        col1, col2 = st.columns(2)
        with col1:
            priority = st.selectbox("Priority *", ['low', 'medium', 'high', 'urgent'], index=1)
        with col2:
            status = st.selectbox("Status *", ['pending', 'due', 'completed'], index=0)
        
        due_date = st.date_input("Due Date (Optional)", value=None)
        
        # File upload
        uploaded_files = st.file_uploader(
            "Attach Documents (Images, PDFs, Excel, etc.)",
            type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls', 'doc', 'docx', 'txt', 'csv'],
            accept_multiple_files=True
        )
        
        is_director = user.get('is_director', False)
        
        # Determine assignable users based on role
        if is_admin or is_director:
            if is_director:
                assigned_users = st.multiselect("Assign to users * (Directors, HODs, SUB-HODs, Employees)", all_users, default=[user['username']])
            else:
                assigned_users = st.multiselect("Assign to users * (select multiple for group tasks)", all_users)
        elif user_designation == 'HOD':
            # HOD can only assign to SUB-HOD and EMPLOYEE in their own department
            assignable_users = [row['username'] for row in all_users_data 
                              if row['designation'] in ['SUB-HOD', 'EMPLOYEE'] 
                              and row['department'] == user_department]
            assigned_users = st.multiselect(f"Assign to users * (SUB-HOD and EMPLOYEE in {user_department} only)", assignable_users)
        else:
            assigned_users = [user['username']]
        
        submitted = st.form_submit_button("Add Task")
        if submitted and title and assigned_users:
            # Set completed_at if status is completed
            completed_at_value = datetime.now() if status == 'completed' else None
            
            # Create task
            cur.execute(
                'INSERT INTO tasks (title, "desc", priority, status, due_date, completed_at) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                (title, desc, priority, status, due_date, completed_at_value)
            )
            task_id = cur.fetchone()['id']
            
            # Assign task to selected users
            for username in assigned_users:
                cur.execute(
                    'INSERT INTO task_assignments (task_id, username) VALUES (%s, %s)',
                    (task_id, username)
                )
            
            # Save uploaded files
            if uploaded_files:
                uploads_dir = "uploads"
                if not os.path.exists(uploads_dir):
                    os.makedirs(uploads_dir)
                
                for uploaded_file in uploaded_files:
                    # Generate unique filename
                    file_extension = os.path.splitext(uploaded_file.name)[1]
                    unique_filename = f"{uuid.uuid4()}{file_extension}"
                    file_path = os.path.join(uploads_dir, unique_filename)
                    
                    # Save file to filesystem
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Determine file type
                    file_type = uploaded_file.type if hasattr(uploaded_file, 'type') else 'application/octet-stream'
                    if file_extension.lower() in ['.jpg', '.jpeg', '.png']:
                        file_type = 'image'
                    elif file_extension.lower() == '.pdf':
                        file_type = 'pdf'
                    elif file_extension.lower() in ['.xlsx', '.xls']:
                        file_type = 'excel'
                    elif file_extension.lower() in ['.doc', '.docx']:
                        file_type = 'document'
                    
                    # Save file metadata to database
                    cur.execute('''
                        INSERT INTO task_attachments (task_id, filename, file_path, file_type, file_size, uploaded_by)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (task_id, uploaded_file.name, file_path, file_type, uploaded_file.size, user['username']))
            
            conn.commit()
            st.success("Task added!")
        elif submitted:
            if not title:
                st.error("Please provide a task title.")
            if not assigned_users:
                st.error("Please assign task to at least one user.")
    
    # Bulk Task Import Section (Admin/Director only)
    is_director = user.get('is_director', False)
    if is_admin or is_director:
        st.markdown("---")
        with st.expander("📥 Bulk Import Tasks from Excel/CSV", expanded=False):
            st.markdown("**Import multiple tasks from Excel or CSV file**")
            
            # Expected CSV/Excel format
            st.info("""
            **Expected format for Excel/CSV:**
            - Column 1: **Title** (required)
            - Column 2: **Description** (optional)
            - Column 3: **Priority** - low/medium/high/urgent (optional, defaults to medium)
            - Column 4: **Status** - pending/due/completed (optional, defaults to pending)
            - Column 5: **Due Date** - YYYY-MM-DD format (optional)
            - Column 6: **Assigned To** - username(s), comma-separated for multiple (required)
            """)
            
            bulk_file = st.file_uploader(
                "Upload Excel or CSV file",
                type=['xlsx', 'xls', 'csv'],
                key="bulk_import_file"
            )
            
            if bulk_file:
                try:
                    # Read file based on extension
                    if bulk_file.name.endswith('.csv'):
                        df = pd.read_csv(bulk_file)
                    else:
                        df = pd.read_excel(bulk_file)
                    
                    # Display preview
                    st.markdown("**Preview of uploaded data:**")
                    st.dataframe(df.head(10), width='stretch')
                    
                    if st.button("Import All Tasks", key="bulk_import_btn"):
                        success_count = 0
                        error_count = 0
                        errors = []
                        
                        for idx, row in df.iterrows():
                            try:
                                # Parse row data (handle missing columns)
                                task_title = str(row.iloc[0]) if len(row) > 0 else None
                                task_desc = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else None
                                task_priority = str(row.iloc[2]).lower() if len(row) > 2 and pd.notna(row.iloc[2]) else 'medium'
                                task_status = str(row.iloc[3]).lower() if len(row) > 3 and pd.notna(row.iloc[3]) else 'pending'
                                task_due_date = pd.to_datetime(row.iloc[4]).date() if len(row) > 4 and pd.notna(row.iloc[4]) else None
                                assigned_str = str(row.iloc[5]) if len(row) > 5 else None
                                
                                # Validation
                                if not task_title or task_title.lower() in ['nan', 'none', '']:
                                    error_count += 1
                                    errors.append(f"Row {idx+2}: Missing title")
                                    continue
                                
                                if not assigned_str or assigned_str.lower() in ['nan', 'none', '']:
                                    error_count += 1
                                    errors.append(f"Row {idx+2}: Missing assigned users")
                                    continue
                                
                                # Split assigned users by comma
                                assigned_usernames = [u.strip() for u in assigned_str.split(',')]
                                
                                # Validate users exist
                                cur.execute('SELECT username FROM users WHERE username = ANY(%s)', (assigned_usernames,))
                                valid_users = [row['username'] for row in cur.fetchall()]
                                
                                if not valid_users:
                                    error_count += 1
                                    errors.append(f"Row {idx+2}: No valid users found")
                                    continue
                                
                                # Validate priority and status
                                if task_priority not in ['low', 'medium', 'high', 'urgent']:
                                    task_priority = 'medium'
                                
                                if task_status not in ['pending', 'due', 'completed']:
                                    task_status = 'pending'
                                
                                # Create task
                                completed_at_value = datetime.now() if task_status == 'completed' else None
                                
                                cur.execute(
                                    'INSERT INTO tasks (title, "desc", priority, status, due_date, completed_at) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                                    (task_title, task_desc, task_priority, task_status, task_due_date, completed_at_value)
                                )
                                task_id = cur.fetchone()['id']
                                
                                # Assign to users
                                for username in valid_users:
                                    cur.execute(
                                        'INSERT INTO task_assignments (task_id, username) VALUES (%s, %s)',
                                        (task_id, username)
                                    )
                                
                                success_count += 1
                                
                            except Exception as e:
                                error_count += 1
                                errors.append(f"Row {idx+2}: {str(e)}")
                        
                        # Commit all transactions
                        conn.commit()
                        
                        # Display results
                        if success_count > 0:
                            st.success(f"✅ Successfully imported {success_count} task(s)!")
                        if error_count > 0:
                            st.error(f"❌ Failed to import {error_count} task(s)")
                            with st.expander("View Import Errors"):
                                for err in errors:
                                    st.text(err)
                        
                        # Rerun to show new tasks
                        if success_count > 0:
                            st.rerun()
                
                except Exception as e:
                    st.error(f"Error reading file: {str(e)}")
                    st.info("Please check if your file is in the correct format and try again.")
    
    st.header("Task List")
    
    # Filter options
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        filter_priority = st.selectbox("Filter by Priority", ['All', 'low', 'medium', 'high', 'urgent'], key='filter_priority')
    with filter_col2:
        filter_status = st.selectbox("Filter by Status", ['All', 'pending', 'due', 'completed'], key='filter_status')
    
    # Build query based on user role
    is_director = user.get('is_director', False)
    if is_admin or is_director:
        query = '''
            SELECT t.* FROM tasks t
            ORDER BY 
                CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
                t.created_at DESC
        '''
        params = ()
    else:
        # Use subquery to avoid DISTINCT + ORDER BY issue
        query = '''
            SELECT t.* FROM tasks t
            WHERE t.id IN (
                SELECT DISTINCT task_id FROM task_assignments WHERE username = %s
            )
            ORDER BY 
                CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
                t.created_at DESC
        '''
        params = (user['username'],)
    
    cur.execute(query, params)
    tasks = cur.fetchall()
    
    # Apply filters
    filtered_tasks = []
    for t in tasks:
        if filter_priority != 'All' and t['priority'] != filter_priority:
            continue
        if filter_status != 'All' and t['status'] != filter_status:
            continue
        filtered_tasks.append(t)
    
    if not filtered_tasks:
        st.info("No tasks found.")
    else:
        for t in filtered_tasks:
            # Get assigned users with assigned_at dates for this task
            cur.execute('SELECT username, assigned_at FROM task_assignments WHERE task_id=%s ORDER BY assigned_at', (t['id'],))
            assigned_data = cur.fetchall()
            assigned_users = [row['username'] for row in assigned_data]
            
            # Priority color coding
            priority_colors = {
                'urgent': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }
            priority_icon = priority_colors.get(t['priority'], '⚪')
            
            # Status styling
            status_badges = {
                'pending': '⏳',
                'due': '⏰',
                'completed': '✅'
            }
            status_icon = status_badges.get(t['status'], '📋')
            
            with st.container():
                col1, col2, col3, col4 = st.columns([0.2, 0.4, 0.25, 0.15])
                
                with col1:
                    priority_display = st.selectbox(
                        f"Priority",
                        ['low', 'medium', 'high', 'urgent'],
                        index=['low', 'medium', 'high', 'urgent'].index(t['priority']),
                        key=f"priority_{t['id']}"
                    )
                    if priority_display != t['priority']:
                        cur.execute("UPDATE tasks SET priority=%s WHERE id=%s", (priority_display, t['id']))
                        conn.commit()
                        st.rerun()
                    
                    status_display = st.selectbox(
                        f"Status",
                        ['pending', 'due', 'completed'],
                        index=['pending', 'due', 'completed'].index(t['status']),
                        key=f"status_{t['id']}"
                    )
                    if status_display != t['status']:
                        # Auto-set completed_at when status changes to completed
                        if status_display == 'completed' and not t['completed_at']:
                            cur.execute("UPDATE tasks SET status=%s, completed_at=%s WHERE id=%s", 
                                      (status_display, datetime.now(), t['id']))
                        elif status_display != 'completed':
                            cur.execute("UPDATE tasks SET status=%s, completed_at=NULL WHERE id=%s", 
                                      (status_display, t['id']))
                        else:
                            cur.execute("UPDATE tasks SET status=%s WHERE id=%s", (status_display, t['id']))
                        conn.commit()
                        st.rerun()
                
                with col2:
                    assigned_text = ", ".join(assigned_users) if len(assigned_users) > 0 else "Unassigned"
                    
                    # Format dates
                    due_date_text = ""
                    if t['due_date']:
                        due_date_text = f"  \n📅 **Due Date:** {t['due_date'].strftime('%Y-%m-%d')}"
                    
                    completed_at_text = ""
                    if t['completed_at']:
                        completed_at_text = f"  \n✅ **Completed:** {t['completed_at'].strftime('%Y-%m-%d %H:%M')}"
                    
                    # Show assigned users with assigned dates
                    assigned_details = []
                    for row in assigned_data:
                        assigned_date = row['assigned_at'].strftime('%Y-%m-%d') if row['assigned_at'] else 'N/A'
                        assigned_details.append(f"{row['username']} (Assigned: {assigned_date})")
                    
                    assigned_info = "  \n".join(assigned_details) if assigned_details else "Unassigned"
                    
                    st.markdown(f"**{t['title']}**  \n{t['desc'] or ''}  \n👥 *Assigned to: {assigned_info}*{due_date_text}{completed_at_text}")
                    
                    # Display attached files
                    cur.execute('''
                        SELECT id, filename, file_path, file_type, file_size, uploaded_at, uploaded_by
                        FROM task_attachments
                        WHERE task_id=%s
                        ORDER BY uploaded_at DESC
                    ''', (t['id'],))
                    attachments = cur.fetchall()
                    
                    if attachments:
                        st.markdown("**📎 Attachments:**")
                        for att in attachments:
                            # File size formatting
                            file_size_kb = att['file_size'] / 1024 if att['file_size'] else 0
                            file_size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{file_size_kb/1024:.1f} MB"
                            
                            # File type icon
                            file_icons = {
                                'image': '🖼️',
                                'pdf': '📄',
                                'excel': '📊',
                                'document': '📝'
                            }
                            file_icon = file_icons.get(att['file_type'], '📎')
                            
                            # Read file for download
                            if os.path.exists(att['file_path']):
                                with open(att['file_path'], "rb") as file:
                                    file_data = file.read()
                                
                                col_file1, col_file2 = st.columns([3, 1])
                                with col_file1:
                                    st.markdown(f"{file_icon} {att['filename']} ({file_size_str})")
                                with col_file2:
                                    st.download_button(
                                        label="Download",
                                        data=file_data,
                                        file_name=att['filename'],
                                        key=f"download_{att['id']}",
                                        mime=att['file_type']
                                    )
                            else:
                                st.warning(f"⚠️ File not found: {att['filename']}")
                
                with col3:
                    st.markdown(f"{priority_icon} **{t['priority'].upper()}**  \n{status_icon} **{t['status'].upper()}**")
                    
                    # Show created date
                    if t.get('created_at'):
                        if isinstance(t['created_at'], datetime):
                            created_date = t['created_at'].strftime('%Y-%m-%d %H:%M')
                        else:
                            created_date = str(t['created_at'])[:16]
                        st.markdown(f"📝 Created: {created_date}")
                
                with col4:
                    if st.button("🗑️ Delete", key=f"del_{t['id']}"):
                        cur.execute("DELETE FROM tasks WHERE id=%s", (t['id'],))
                        conn.commit()
                        st.rerun()
                
                st.divider()
    
    # Task Overview Table for Directors and Admins
    is_director = user.get('is_director', False)
    if is_admin or is_director:
        st.markdown("---")
        st.header("📊 Complete Task Overview Table")
        
        # Export filters
        st.subheader("📅 Export Filters")
        filter_exp_col1, filter_exp_col2 = st.columns(2)
        with filter_exp_col1:
            export_filter_type = st.selectbox("Filter Type", ['All Tasks', 'Daily', 'Monthly', 'User Wise'], key='export_filter')
        with filter_exp_col2:
            if export_filter_type == 'Daily':
                export_date = st.date_input("Select Date", value=datetime.now().date(), key='export_daily')
            elif export_filter_type == 'Monthly':
                export_month = st.date_input("Select Month", value=datetime.now().date(), key='export_monthly')
            elif export_filter_type == 'User Wise':
                # Get all users for filter
                cur.execute('SELECT username FROM users ORDER BY username')
                all_users_list = [row[0] for row in cur.fetchall()]
                export_username = st.selectbox("Select User", all_users_list, key='export_user')
        
        # Get all tasks with details
        query = '''
            SELECT t.*, COUNT(DISTINCT ta.username) as assigned_count
            FROM tasks t
            LEFT JOIN task_assignments ta ON t.id = ta.task_id
            WHERE 1=1
        '''
        params = []
        
        # Apply date filters
        if export_filter_type == 'Daily':
            query += ' AND DATE(t.created_at) = %s'
            params.append(export_date)
        elif export_filter_type == 'Monthly':
            query += ' AND DATE_TRUNC(\'month\', t.created_at) = DATE_TRUNC(\'month\', %s::timestamp)'
            params.append(export_month)
        
        # Get users for user-wise filtering
        if export_filter_type == 'User Wise':
            query = '''
                SELECT t.*, COUNT(DISTINCT ta.username) as assigned_count
                FROM tasks t
                INNER JOIN task_assignments ta ON t.id = ta.task_id
                WHERE ta.username = %s
                GROUP BY t.id
            '''
            params = [export_username]
        else:
            query += ' GROUP BY t.id'
        
        query += '''
            ORDER BY 
                CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
                t.created_at DESC
        '''
        
        cur.execute(query, params)
        all_tasks_overview = cur.fetchall()
        
        if all_tasks_overview:
            # Create detailed data for table
            table_data = []
            for task in all_tasks_overview:
                # Get assigned users with their designations
                cur.execute('''
                    SELECT u.username, u.designation, u.department, ta.assigned_at
                    FROM task_assignments ta
                    JOIN users u ON ta.username = u.username
                    WHERE ta.task_id = %s
                    ORDER BY ta.assigned_at
                ''', (task['id'],))
                assigned_users = cur.fetchall()
                
                # Get attachments count
                cur.execute('SELECT COUNT(*) as count FROM task_attachments WHERE task_id = %s', (task['id'],))
                attachments_count = cur.fetchone()['count']
                
                # Format assigned users
                assigned_info = []
                for u in assigned_users:
                    assigned_info.append(f"{u['username']} ({u['designation']})")
                
                # Format dates
                created_date = task['created_at'].strftime('%Y-%m-%d %H:%M') if task['created_at'] else 'N/A'
                due_date = task['due_date'].strftime('%Y-%m-%d') if task['due_date'] else 'Not set'
                completed_date = task['completed_at'].strftime('%Y-%m-%d %H:%M') if task['completed_at'] else 'Not completed'
                
                table_data.append({
                    "ID": task['id'],
                    "Title": task['title'],
                    "Description": (task['desc'][:50] + '...') if task['desc'] and len(task['desc']) > 50 else (task['desc'] or 'No description'),
                    "Priority": task['priority'].upper(),
                    "Status": task['status'].upper(),
                    "Assigned To": ", ".join(assigned_info) if assigned_info else "Unassigned",
                    "Created": created_date,
                    "Due Date": due_date,
                    "Completed": completed_date,
                    "Attachments": attachments_count
                })
            
            # Display in DataFrame
            df_overview = pd.DataFrame(table_data)
            st.dataframe(df_overview, width='stretch', hide_index=True, height=600)
            
            # Export option - CSV format
            # Determine filename based on filter
            filter_suffix = ""
            if export_filter_type == 'Daily':
                filter_suffix = f"_daily_{export_date.strftime('%Y%m%d')}"
            elif export_filter_type == 'Monthly':
                filter_suffix = f"_monthly_{export_month.strftime('%Y%m')}"
            elif export_filter_type == 'User Wise':
                filter_suffix = f"_user_{export_username}"
            
            csv_overview = df_overview.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Task Overview (CSV)",
                data=csv_overview,
                file_name=f"task_overview{filter_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No tasks available for overview.")
    
    # Task Overview Table for HOD
    elif user_designation == 'HOD':
        st.markdown("---")
        st.header("📊 My Department Tasks Overview")
        
        # Get current user's department
        cur.execute('SELECT department FROM users WHERE username=%s', (user['username'],))
        user_dept_result = cur.fetchone()
        user_dept = user_dept_result['department'] if user_dept_result else None
        
        if user_dept:
            # Get tasks assigned to users in HOD's department
            cur.execute('''
                SELECT t.*
                FROM tasks t
                WHERE t.id IN (
                    SELECT DISTINCT ta.task_id
                    FROM task_assignments ta
                    INNER JOIN users u ON ta.username = u.username
                    WHERE u.department = %s
                )
                ORDER BY 
                    CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
                    t.created_at DESC
            ''', (user_dept,))
            dept_tasks = cur.fetchall()
            
            if dept_tasks:
                # Create detailed data for table
                table_data = []
                for task in dept_tasks:
                    # Get assigned users with their designations
                    cur.execute('''
                        SELECT u.username, u.designation, u.department, ta.assigned_at
                        FROM task_assignments ta
                        JOIN users u ON ta.username = u.username
                        WHERE ta.task_id = %s AND u.department = %s
                        ORDER BY ta.assigned_at
                    ''', (task['id'], user_dept))
                    assigned_users = cur.fetchall()
                    
                    # Get attachments count
                    cur.execute('SELECT COUNT(*) as count FROM task_attachments WHERE task_id = %s', (task['id'],))
                    attachments_count = cur.fetchone()['count']
                    
                    # Format assigned users
                    assigned_info = []
                    for u in assigned_users:
                        assigned_info.append(f"{u['username']} ({u['designation']})")
                    
                    # Format dates
                    created_date = task['created_at'].strftime('%Y-%m-%d %H:%M') if task['created_at'] else 'N/A'
                    due_date = task['due_date'].strftime('%Y-%m-%d') if task['due_date'] else 'Not set'
                    completed_date = task['completed_at'].strftime('%Y-%m-%d %H:%M') if task['completed_at'] else 'Not completed'
                    
                    table_data.append({
                        "ID": task['id'],
                        "Title": task['title'],
                        "Description": (task['desc'][:50] + '...') if task['desc'] and len(task['desc']) > 50 else (task['desc'] or 'No description'),
                        "Priority": task['priority'].upper(),
                        "Status": task['status'].upper(),
                        "Assigned To": ", ".join(assigned_info) if assigned_info else "Unassigned",
                        "Created": created_date,
                        "Due Date": due_date,
                        "Completed": completed_date,
                        "Attachments": attachments_count
                    })
                
                # Display in DataFrame
                df_dept = pd.DataFrame(table_data)
                st.dataframe(df_dept, width='stretch', hide_index=True, height=600)
                
                # Export option
                csv_dept = df_dept.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Department Tasks (CSV)",
                    data=csv_dept,
                    file_name=f"dept_tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info(f"No tasks found in {user_dept} department.")

# REMOVED: Duplicate sidebar - navigation is in task_page() function

# Removed debug test section - sidebar is now fixed and visible

if st.session_state['user'] is None:
    st.markdown("---")
    st.markdown("### Please Login")
    # Create tabs for login options
    tab1, tab2 = st.tabs(["Login Options", "Registration"])
    
    with tab1:
        st.write("**Login Form:**")
        # Create side-by-side login cards
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Regular Login:**")
            login()
        
        with col2:
            st.write("**Director Login:**")
            director_login()
    
    with tab2:
        st.write("**Registration Form:**")
        signup()
else:
    task_page()

