import os
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import Client
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, SessionPasswordNeeded

app = FastAPI()

# ওয়ান-পেজ ওয়েবসাইটের সাথে কানেক্ট করার জন্য CORS ওপেন করা হলো
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# আপনার API ID এবং HASH (my.telegram.org থেকে নিন)
API_ID = int(os.environ.get("API_ID", "আপনার_API_ID"))
API_HASH = os.environ.get("API_HASH", "আপনার_API_HASH")

# অ্যাক্টিভ সেশনগুলো সাময়িকভাবে মনে রাখার জন্য মেমোরি
sessions = {}

@app.post("/send_otp")
async def send_otp(phone: str = Form(...)):
    client = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
    await client.connect()
    try:
        code_info = await client.send_code(phone)
        # ফোন নম্বরকে কি (Key) হিসেবে সেভ রাখা হচ্ছে
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
            # যদি টু-স্টেপ ভেরিফিকেশন পাসওয়ার্ড থাকে
            await client.check_password(password)
        else:
            # সাধারণ ওটিপি সাবমিট
            await client.sign_in(phone, phone_code_hash, otp)
        
        # সেশন সাকসেস হলে স্ট্রিং জেনারেট করা
        string_session = await client.export_session_string()
        await client.disconnect()
        del sessions[phone] # মেমোরি ক্লিয়ার
        
        return {"status": "success", "session": string_session}
        
    except SessionPasswordNeeded:
        return {"status": "2fa_required", "message": "Two-Step Verification Password Required!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)