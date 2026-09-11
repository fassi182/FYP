from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from bson import ObjectId
from datetime import datetime, timedelta, timezone
import random
import smtplib
from app.services.otp_service import send_otp_email
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token
)
from pydantic import BaseModel, EmailStr, Field
from app.database.mongodb import get_database


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


class SendOTPRequest(BaseModel):
    organization_id: str
    department_id: str
    email: EmailStr
class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
class RegisterRequest(BaseModel):
    organization_id: str
    department_id: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
@router.post("/send-otp")
async def send_otp(data: SendOTPRequest):

    db = get_database()

    # 1. Validate organization ID
    if not ObjectId.is_valid(data.organization_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid organization ID"
        )

    # 2. Find organization
    organization = await db.organizations.find_one({
        "_id": ObjectId(data.organization_id),
        "is_active": True
    })

    if not organization:
        raise HTTPException(
            status_code=404,
            detail="Organization not found"
        )

    # 3. Validate department ID
    if not ObjectId.is_valid(data.department_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid department ID"
        )

    # 4. Check department belongs to organization
    department = await db.departments.find_one({
        "_id": ObjectId(data.department_id),
        "is_active": True
    })

    if not department:
        raise HTTPException(
            status_code=404,
            detail="Department not found"
        )

    organization_departments = [
        str(dept_id)
        for dept_id in organization.get("departments", [])
    ]

    if data.department_id not in organization_departments:
        raise HTTPException(
            status_code=400,
            detail="Department does not belong to this organization"
        )

    # 5. Check email suffix
    email = data.email.lower()
    email_suffix = organization.get("email_suffix")
    if not email_suffix:
        raise HTTPException(
            status_code=400,
            detail="This organization does not have an email suffix configured"
        )
    email_suffix = email_suffix.lower()

    if not email.endswith(email_suffix):
        raise HTTPException(
            status_code=400,
            detail=f"Email must use the organization email suffix: {email_suffix}"
        )

    # 6. Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))

    # 7. Save OTP in database
    await db.otp_verifications.insert_one({
        "email": email,
        "otp": otp,
        "organization_id": data.organization_id,
        "department_id": data.department_id,
        "verified": False,
        "created_at": datetime.now(timezone.utc)
    })

    try:
        await send_otp_email(email, otp)
    except (OSError, RuntimeError, smtplib.SMTPException) as error:
        await db.otp_verifications.delete_one({
            "email": email,
            "otp": otp,
            "verified": False
        })
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {
        "message": "OTP sent successfully",
        "email": email
    }
@router.post("/verify-otp")
async def verify_otp(data: VerifyOTPRequest):

    db = get_database()

    email = data.email.lower()

    # Find the OTP record
    otp_record = await db.otp_verifications.find_one({
        "email": email,
        "otp": data.otp
    })

    # OTP not found or incorrect
    if not otp_record:
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP"
        )

    created_at = otp_record.get("created_at")
    if created_at is None:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created_at > timedelta(minutes=10):
        await db.otp_verifications.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(status_code=400, detail="OTP has expired")

    # Check whether already verified
    if otp_record.get("verified", False):
        return {
            "message": "OTP already verified",
            "verified": True
        }

    # Mark OTP as verified
    await db.otp_verifications.update_one(
        {
            "_id": otp_record["_id"]
        },
        {
            "$set": {
                "verified": True
            }
        }
    )

    return {
        "message": "OTP verified successfully",
        "verified": True
    }
@router.post("/register")
async def register_user(data: RegisterRequest):

    db = get_database()

    email = data.email.lower()

    # 1. Validate organization ID
    if not ObjectId.is_valid(data.organization_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid organization ID"
        )

    organization = await db.organizations.find_one({
        "_id": ObjectId(data.organization_id),
        "is_active": True
    })

    if not organization:
        raise HTTPException(
            status_code=404,
            detail="Organization not found"
        )

    # 2. Validate department ID
    if not ObjectId.is_valid(data.department_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid department ID"
        )

    department = await db.departments.find_one({
        "_id": ObjectId(data.department_id),
        "is_active": True
    })

    if not department:
        raise HTTPException(
            status_code=404,
            detail="Department not found"
        )

    # 3. Check department belongs to organization
    organization_departments = [
        str(dept_id)
        for dept_id in organization.get("departments", [])
    ]

    if data.department_id not in organization_departments:
        raise HTTPException(
            status_code=400,
            detail="Department does not belong to this organization"
        )

    # 4. Check email suffix
    email_suffix = organization.get("email_suffix")
    if not email_suffix:
        raise HTTPException(
            status_code=400,
            detail="This organization does not have an email suffix configured"
        )
    email_suffix = email_suffix.lower()

    if not email.endswith(email_suffix):
        raise HTTPException(
            status_code=400,
            detail=f"Email must use the organization email suffix: {email_suffix}"
        )

    # 5. Check OTP verification
    otp_record = await db.otp_verifications.find_one({
        "email": email,
        "verified": True,
        "organization_id": data.organization_id,
        "department_id": data.department_id,
        "consumed": {"$ne": True}
    })

    if not otp_record:
        raise HTTPException(
            status_code=400,
            detail="Email has not been verified"
        )

    # 6. Check whether user already exists
    existing_user = await db.users.find_one({
        "email": email
    })

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    # 7. Create user
    user = {
    "email": email,
    "organization_id": ObjectId(data.organization_id),
    "department_id": ObjectId(data.department_id),
    "password": hash_password(data.password)
}

    result = await db.users.insert_one(user)

    await db.otp_verifications.update_one(
        {"_id": otp_record["_id"]},
        {"$set": {"consumed": True}}
    )

    return {
        "message": "User registered successfully",
        "user_id": str(result.inserted_id),
        "email": email
    }
@router.post("/login")
async def login_user(data: LoginRequest):

    db = get_database()

    email = data.email.lower()

    # 1. Find user
    user = await db.users.find_one({
        "email": email
    })

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # 2. Verify password
    password_valid = verify_password(
        data.password,
        user["password"]
    )

    if not password_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # 3. Generate JWT
    access_token = create_access_token(
        str(user["_id"])
    )

    # 4. Return token
    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user["_id"]),
        "email": user["email"]
    }