from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.core.security import get_current_user_id
from app.database.mongodb import get_database


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)
from pydantic import BaseModel
class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    education: str | None = None
    experience: str | None = None
@router.put("/me")
async def update_my_profile(
    data: ProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id)
):
    db = get_database()

    update_data = {}

    if data.name is not None:
        update_data["name"] = data.name

    if data.education is not None:
        update_data["education"] = data.education

    if data.experience is not None:
        update_data["experience"] = data.experience

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No profile data provided"
        )

    result = await db.users.update_one(
        {
            "_id": ObjectId(user_id)
        },
        {
            "$set": update_data
        }
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user = await db.users.find_one({
        "_id": ObjectId(user_id)
    })

    return {
        "message": "Profile updated successfully",
        "user": {
            "user_id": str(user["_id"]),
            "email": user["email"],
            "organization_id": str(user["organization_id"]),
            "department_id": str(user["department_id"]),
            "name": user.get("name"),
            "education": user.get("education"),
            "experience": user.get("experience")
        }
    }

@router.get("/me")
async def get_my_profile(
    user_id: str = Depends(get_current_user_id)
):

    db = get_database()

    user = await db.users.find_one({
        "_id": ObjectId(user_id)
    })

    if not user:
        raise HTTPException(
        status_code=404,
        detail="User not found"
        )

    return {
        "user_id": str(user["_id"]),
        "email": user["email"],
        "organization_id": str(user["organization_id"]),
        "department_id": str(user["department_id"])
    }