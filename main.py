import asyncio
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import Client
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, SessionPasswordNeeded

# পাইথন ৩.১৪+ ইভেন্ট লুপ ফিক্স
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

app = FastAPI()

# ওয়ান-পেজ ওয়েবসাইটের (Blogger) সাথে কানেক্ট করার জন্য CORS ওপেন করা হলো
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# আপনার দেওয়া আসল টেলিগ্রাম এপিআই আইডি ও হ্যাশ এখানে সরাসরি বসানো হলো
API_ID = 35648548
API_HASH = "7cb954d06d962e181fb1717fe1a486a8"

# অ্যাক্টিভ সেশনগুলো সাময়িকভাবে মনে রাখার জন্য মেমোরি
sessions = {}

@app.post("/send_otp")
async def send_otp(phone: str = Form(...)):
    client = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
    await client.connect()
    try:
        code_info = await client.send_code(phone)
        sessions[phone] = {
            "client": client,
            "phone_code_hash": code_info.phone_code_hash
        }
        return {"status": "success", "message": "OTP Sent Successfully!"}
    except Exception as e:
        await client.disconnect()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/verify_otp")
async def verify_otp(phone: str = Form(...), otp: str = Form(...), password: str = Form(None)):
    if phone not in sessions:
        raise HTTPException(status_code=400, detail="Session not found. Please resend OTP.")
    
    client = sessions[phone]["client"]
    phone_code_hash = sessions[phone]["phone_code_hash"]
    
    try:
        if password:
            await client.check_password(password)
        else:
            await client.sign_in(phone, phone_code_hash, otp)
        
        string_session = await client.export_session_string()
        await client.disconnect()
        del sessions[phone]
        
        return {"status": "success", "session": string_session}
        
    except SessionPasswordNeeded:
        return {"status": "2fa_required", "message": "Two-Step Verification Password Required!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str-e)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
