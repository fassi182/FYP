from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime, timezone

from app.database.mongodb import get_database
from app.core.security import get_current_user_id


router = APIRouter(
    prefix="/cases",
    tags=["Case Archive"]
)


# ============================================================
# REQUEST MODELS
# ============================================================

class CaseCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    diagnosis: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    images: list[str] = []


class CaseUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    diagnosis: str | None = None
    explanation: str | None = None
    images: list[str] | None = None


class VoteRequest(BaseModel):
    vote: str


# ============================================================
# HELPER FUNCTION
# ============================================================

def case_to_response(case):
    return {
        "id": str(case["_id"]),
        "author_id": str(case["author_id"]),
        "title": case["title"],
        "description": case["description"],
        "diagnosis": case["diagnosis"],
        "explanation": case["explanation"],
        "images": case.get("images", []),
        "status": case.get("status", "pending"),
        "upvotes": case.get("upvotes", 0),
        "downvotes": case.get("downvotes", 0),
        "score": case.get("score", 0),
        "is_promoted_to_learning": case.get(
            "is_promoted_to_learning",
            False
        ),
        "created_at": case.get("created_at"),
        "updated_at": case.get("updated_at")
    }


# ============================================================
# 1. GET ALL VALIDATED CASES
# ============================================================

@router.get("")
async def get_cases(
    user_id: str = Depends(get_current_user_id)
):
    db = get_database()

    cases = await db.case_archive.find(
        {
            "status": "validated"
        }
    ).sort(
        "created_at",
        -1
    ).to_list(length=100)

    return {
        "cases": [
            case_to_response(case)
            for case in cases
        ]
    }


# ============================================================
# 2. GET SINGLE CASE
# ============================================================

@router.get("/{case_id}")
async def get_case(
    case_id: str,
    user_id: str = Depends(get_current_user_id)
):
    db = get_database()

    if not ObjectId.is_valid(case_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid case ID"
        )

    case = await db.case_archive.find_one({
        "_id": ObjectId(case_id)
    })

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    return case_to_response(case)


# ============================================================
# 3. CREATE CASE
# ============================================================

@router.post("")
async def create_case(
    data: CaseCreateRequest,
    user_id: str = Depends(get_current_user_id)
):
    db = get_database()

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID"
        )

    now = datetime.now(timezone.utc)

    case = {
        "author_id": ObjectId(user_id),
        "title": data.title,
        "description": data.description,
        "diagnosis": data.diagnosis,
        "explanation": data.explanation,
        "images": data.images,

        # New cases require validation
        "status": "pending",

        # Voting starts at zero
        "upvotes": 0,
        "downvotes": 0,
        "score": 0,

        # Future Learning module
        "is_promoted_to_learning": False,

        "created_at": now,
        "updated_at": now
    }

    result = await db.case_archive.insert_one(case)

    created_case = await db.case_archive.find_one({
        "_id": result.inserted_id
    })

    return {
        "message": "Case created successfully",
        "case": case_to_response(created_case)
    }


# ============================================================
# 4. UPDATE OWN CASE
# ============================================================

@router.put("/{case_id}")
async def update_case(
    case_id: str,
    data: CaseUpdateRequest,
    user_id: str = Depends(get_current_user_id)
):
    db = get_database()

    if not ObjectId.is_valid(case_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid case ID"
        )

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID"
        )

    case = await db.case_archive.find_one({
        "_id": ObjectId(case_id)
    })

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    # Only the case owner can edit it
    if str(case["author_id"]) != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own cases"
        )

    update_data = {}

    if data.title is not None:
        update_data["title"] = data.title

    if data.description is not None:
        update_data["description"] = data.description

    if data.diagnosis is not None:
        update_data["diagnosis"] = data.diagnosis

    if data.explanation is not None:
        update_data["explanation"] = data.explanation

    if data.images is not None:
        update_data["images"] = data.images

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No case data provided"
        )

    update_data["updated_at"] = datetime.now(timezone.utc)

    await db.case_archive.update_one(
        {
            "_id": ObjectId(case_id)
        },
        {
            "$set": update_data
        }
    )

    updated_case = await db.case_archive.find_one({
        "_id": ObjectId(case_id)
    })

    return {
        "message": "Case updated successfully",
        "case": case_to_response(updated_case)
    }


# ============================================================
# 5. DELETE OWN CASE
# ============================================================

@router.delete("/{case_id}")
async def delete_case(
    case_id: str,
    user_id: str = Depends(get_current_user_id)
):
    db = get_database()

    if not ObjectId.is_valid(case_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid case ID"
        )

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID"
        )

    case = await db.case_archive.find_one({
        "_id": ObjectId(case_id)
    })

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    # Only the owner can delete the case
    if str(case["author_id"]) != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own cases"
        )

    await db.case_archive.delete_one({
        "_id": ObjectId(case_id)
    })

    # Remove related votes
    await db.case_votes.delete_many({
        "case_id": ObjectId(case_id)
    })

    # Remove related saves
    await db.saved_cases.delete_many({
        "case_id": ObjectId(case_id)
    })

    return {
        "message": "Case deleted successfully"
    }


# ============================================================
# 6. VOTE ON CASE
# ============================================================

@router.post("/{case_id}/vote")
async def vote_case(
    case_id: str,
    data: VoteRequest,
    user_id: str = Depends(get_current_user_id)
):
    db = get_database()

    if not ObjectId.is_valid(case_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid case ID"
        )

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID"
        )

    if data.vote not in ["up", "down"]:
        raise HTTPException(
            status_code=400,
            detail="Vote must be either 'up' or 'down'"
        )

    case = await db.case_archive.find_one({
        "_id": ObjectId(case_id)
    })

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    existing_vote = await db.case_votes.find_one({
        "case_id": ObjectId(case_id),
        "user_id": ObjectId(user_id)
    })

    # --------------------------------------------------------
    # First vote
    # --------------------------------------------------------

    if not existing_vote:

        await db.case_votes.insert_one({
            "case_id": ObjectId(case_id),
            "user_id": ObjectId(user_id),
            "vote": data.vote,
            "created_at": datetime.now(timezone.utc)
        })

        if data.vote == "up":
            await db.case_archive.update_one(
                {"_id": ObjectId(case_id)},
                {
                    "$inc": {
                        "upvotes": 1,
                        "score": 1
                    }
                }
            )

        else:
            await db.case_archive.update_one(
                {"_id": ObjectId(case_id)},
                {
                    "$inc": {
                        "downvotes": 1,
                        "score": -1
                    }
                }
            )

        return {
            "message": "Vote recorded successfully",
            "vote": data.vote
        }

    # --------------------------------------------------------
    # Same vote again → remove vote
    # --------------------------------------------------------

    if existing_vote["vote"] == data.vote:

        await db.case_votes.delete_one({
            "_id": existing_vote["_id"]
        })

        if data.vote == "up":
            await db.case_archive.update_one(
                {"_id": ObjectId(case_id)},
                {
                    "$inc": {
                        "upvotes": -1,
                        "score": -1
                    }
                }
            )

        else:
            await db.case_archive.update_one(
                {"_id": ObjectId(case_id)},
                {
                    "$inc": {
                        "downvotes": -1,
                        "score": 1
                    }
                }
            )

        return {
            "message": "Vote removed successfully"
        }

    # --------------------------------------------------------
    # Change vote
    # --------------------------------------------------------

    old_vote = existing_vote["vote"]

    await db.case_votes.update_one(
        {
            "_id": existing_vote["_id"]
        },
        {
            "$set": {
                "vote": data.vote
            }
        }
    )

    if old_vote == "up" and data.vote == "down":

        await db.case_archive.update_one(
            {"_id": ObjectId(case_id)},
            {
                "$inc": {
                    "upvotes": -1,
                    "downvotes": 1,
                    "score": -2
                }
            }
        )

    elif old_vote == "down" and data.vote == "up":

        await db.case_archive.update_one(
            {"_id": ObjectId(case_id)},
            {
                "$inc": {
                    "downvotes": -1,
                    "upvotes": 1,
                    "score": 2
                }
            }
        )

    return {
        "message": "Vote updated successfully",
        "vote": data.vote
    }


# ============================================================
# 7. SAVE / UNSAVE CASE
# ============================================================

@router.post("/{case_id}/save")
async def save_case(
    case_id: str,
    user_id: str = Depends(get_current_user_id)
):
    db = get_database()

    if not ObjectId.is_valid(case_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid case ID"
        )

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID"
        )

    case = await db.case_archive.find_one({
        "_id": ObjectId(case_id)
    })

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    existing_save = await db.saved_cases.find_one({
        "case_id": ObjectId(case_id),
        "user_id": ObjectId(user_id)
    })

    # Already saved → unsave
    if existing_save:

        await db.saved_cases.delete_one({
            "_id": existing_save["_id"]
        })

        return {
            "message": "Case removed from saved cases",
            "saved": False
        }

    # Not saved → save
    await db.saved_cases.insert_one({
        "case_id": ObjectId(case_id),
        "user_id": ObjectId(user_id),
        "created_at": datetime.now(timezone.utc)
    })

    return {
        "message": "Case saved successfully",
        "saved": True
    }


# ============================================================
# 8. GET MY CASES
# ============================================================

@router.get("/my")
async def get_my_cases(
    user_id: str = Depends(get_current_user_id)
):
    db = get_database()

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID"
        )

    cases = await db.case_archive.find({
        "author_id": ObjectId(user_id)
    }).sort(
        "created_at",
        -1
    ).to_list(length=100)

    return {
        "cases": [
            case_to_response(case)
            for case in cases
        ]
    }