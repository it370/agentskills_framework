from typing import Any, Dict, List

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from data.mongo import get_collection


def json_response(payload: Any, status: int = 200) -> JSONResponse:
    """Consistent JSON response wrapper."""

    return JSONResponse(content=payload, status_code=status)

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


@router.get("/wnfe")
async def get_wnfe_list(limit: int = 9):
    """Fetch WNFE records from MongoDB collection `wnfe`.

    Previous mock generation logic has been commented out for reference.
    """

    try:
        collection = get_collection("wnfe")
        # Exclude MongoDB's internal _id field by default
        cursor = collection.find({}, {"_id": 0}).limit(limit)
        result: List[Dict[str, Any]] = list(cursor)
    except Exception as exc:  # pragma: no cover - safety net around DB access
        return json_response(
            {
                "error": "Failed to fetch WNFE records",
                "detail": str(exc),
            },
            status=500,
        )

    # Previous mock-data generation (kept for reference):
    #
    # result = []
    # for i in range(9):
    #     employer_name = WNFE_EMPLOYER_NAMES[i % len(WNFE_EMPLOYER_NAMES)]
    #     candidate_name = WNFE_CANDIDATE_NAMES[i % len(WNFE_CANDIDATE_NAMES)]
    #     position_title = WNFE_POSITION_TITLES[i % len(WNFE_POSITION_TITLES)]
    #     division = WNFE_DIVISIONS[i % len(WNFE_DIVISIONS)]
    #     recent_hire_date = mock_data.random_date(2018, 2023)
    #     original_hire_date = mock_data.random_date(2005, 2017)
    #     employment_status = WNFE_EMPLOYMENT_STATUSES[i % len(WNFE_EMPLOYMENT_STATUSES)]
    #     termination_date = (
    #         mock_data.random_date(2020, 2023)
    #         if employment_status == "Terminated"
    #         else ""
    #     )
    #     source = WNFE_SOURCES[i % len(WNFE_SOURCES)]
    #
    #     result.append({
    #         "employer_name": employer_name,
    #         "candidate_name": candidate_name,
    #         "position_title": position_title,
    #         "division": division,
    #         "recent_hire_date": recent_hire_date,
    #         "original_hire_date": original_hire_date,
    #         "employment_status": employment_status,
    #         "termination_date": termination_date,
    #         "source": source
    #     })

    return json_response(result)


@router.get("/orders/{order_number}")
def get_order_details(order_number: str):

    # Accept any given 8 digit number for mock; lightly validate format.
    if not (order_number.isdigit() and len(order_number) == 8):
        return json_response(
            {"error": "Invalid order number, expected 8 digit numeric string", "order_number": order_number},
            status=400,
        )

    try:
        collection = get_collection("orders")
        # Look up by order_number field; exclude internal _id by default
        doc = collection.find_one({"order_number": order_number}, {"_id": 0})
    except Exception as exc:  # pragma: no cover - safety net around DB access
        return json_response(
            {
                "error": "Failed to fetch order details",
                "detail": str(exc),
                "order_number": order_number,
            },
            status=500,
        )

    if not doc:
        return json_response(
            {
                "error": "Order not found",
                "order_number": order_number,
            },
            status=404,
        )

    # Previous mock-data based result (kept for reference):
    #
    # first_name, last_name = mock_data.random_name()
    # email = mock_data.random_email(first_name, last_name)
    # ssn_id = f"{mock_data.random_8_digit_id()}{mock_data.random_8_digit_id()[0:1]}"
    # birth_date = mock_data.random_date(1960, 2000)
    # address = mock_data.random_address()
    # phone = mock_data.random_phone()
    # employer_company_name = mock_data.random_employer()
    # employer_phone = mock_data.random_phone()
    # start_date, end_date = mock_data.random_employment_period()
    # job_title = mock_data.random_job_title()
    # reason_for_leaving = mock_data.random_reason_for_leaving()
    # job_location_state = mock_data.random.choice(mock_data.STATES) if hasattr(mock_data, "random") else None
    #
    # # If random attribute is not present (defensive), fall back to utility functions
    # if job_location_state is None:
    #     job_location_state = mock_data.STATES[0]
    # job_location_city = mock_data.CITIES[mock_data.STATES.index(job_location_state) % len(mock_data.CITIES)]
    #
    # result = {
    #     "first_name": first_name,
    #     "last_name": last_name,
    #     "ssn_id": ssn_id,
    #     "birth_date": birth_date,
    #     "email": email,
    #     "address": address,
    #     "phone": phone,
    #     "employer_company_name": employer_company_name,
    #     "employer_phone": employer_phone,
    #     "start_date": start_date,
    #     "end_date": end_date,
    #     "job_title": job_title,
    #     "reason_for_leaving": reason_for_leaving,
    #     "job_location_state": job_location_state,
    #     "job_location_city": job_location_city,
    #     "order_number": order_number,
    # }
    #
    # return json_response(result)

    # Ensure order_number is always present in the response payload.
    if "order_number" not in doc:
        doc["order_number"] = order_number

    return json_response(doc)


@router.get("/queues")
def list_queue_orders(queue_name: str = Query(..., description="Queue name to list orders for")):
    
    # load from mongodb / orders collection
    collection = get_collection("orders")
    # cursor = collection.find({"queue_name": queue_name}, {"_id": 0})
    # result: List[Dict[str, Any]] = list(cursor)
    # Query orders for the given queue_name
    orders = collection.find({}, {"_id": 0, "order_number": 1})
    result = [
        {
            "order_id": order.get("order_number"),
            "service_name": queue_name,
        }
        for order in orders
    ]
    return json_response(result)


@router.get("/logbook")
def get_logbook():
    # employer_name = params["employer_name"]
    collection = get_collection("logbook")
    # doc = collection.find_one({"employer_name": employer_name}, {"_id": 0})
    cursor = collection.find({}, {"_id": 0})
    result: List[Dict[str, Any]] = list(cursor)
    return json_response(result)

# router.add_route("GET", "/api/clearstar/orders/{order_number}", get_order_details)
# router.add_route("GET", "/api/clearstar/wnfe", get_wnfe_list)
# router.add_route("GET", "/api/clearstar/queues/{queue_name}", list_queue_orders)
# router.add_route("GET", "/api/clearstar/logbook", get_logbook)