from fastapi import APIRouter, Query, HTTPException
from bson import ObjectId

from app.database.mongodb import get_database


router = APIRouter(
    prefix="/organizations",
    tags=["Organizations"]
)


@router.get("/search")
async def search_organizations(
    query: str = Query(..., min_length=1)
):
    db = get_database()

    organizations = await db.organizations.find(
        {
            "name": {
                "$regex": query,
                "$options": "i"
            },
            "is_active": True
        },
        {
            "_id": 1,
            "name": 1,
            "email_suffix": 1
        }
    ).to_list(length=20)

    return {
        "organizations": [
            {
                "id": str(org["_id"]),
                "name": org["name"],
                "email_suffix": org.get("email_suffix")
            }
            for org in organizations
        ]
    }


@router.get("/{organization_id}/departments")
async def get_organization_departments(
    organization_id: str
):
    db = get_database()

    # Check whether the organization ID is valid
    if not ObjectId.is_valid(organization_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid organization ID"
        )

    organization = await db.organizations.find_one(
        {
            "_id": ObjectId(organization_id),
            "is_active": True
        }
    )

    if not organization:
        raise HTTPException(
            status_code=404,
            detail="Organization not found"
        )

    department_ids = organization.get("departments", [])

    object_ids = [
        ObjectId(dept_id)
        if isinstance(dept_id, str)
        else dept_id
        for dept_id in department_ids
        if ObjectId.is_valid(str(dept_id))
    ]

    departments = await db.departments.find(
        {
            "_id": {"$in": object_ids},
            "is_active": True
        },
        {
            "_id": 1,
            "name": 1
        }
    ).to_list(length=100)

    return {
        "organization_id": organization_id,
        "departments": [
            {
                "id": str(dept["_id"]),
                "name": dept["name"]
            }
            for dept in departments
        ]
    }