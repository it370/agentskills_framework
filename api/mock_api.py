from fastapi import APIRouter

router = APIRouter(prefix="/mock", tags=["mock"])


@router.get("/profile")
async def mock_profile():
    """Return a hardcoded candidate profile."""
    return {
        "full_name": "Jordan Example",
        "dob": "1990-05-14",
        "ssn": "123-45-6789",
        "address": "123 Main St, Springfield, USA",
    }


@router.post("/criminal-check")
async def mock_criminal_check(payload: dict):
    """
    Return a deterministic mock criminal check response.
    Echoes input and supplies fixed outputs.
    """
    return {
        "input_received": payload,
        "criminal_status": "clear",
        "risk_score": 12,
        "scoresheet": {"risk": {"final_score": 12}},
    }


@router.post("/education-verify")
async def mock_education(payload: dict):
    """Return a canned education verification result."""
    return {
        "input_received": payload,
        "degree": "B.Sc. Computer Science",
        "grad_year": "2012",
        "is_qualified": True,
    }

