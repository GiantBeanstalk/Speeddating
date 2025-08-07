"""
Hypothesis strategies for API testing.

Provides strategies for generating API requests, responses,
and testing HTTP endpoints with various scenarios.
"""

from hypothesis import strategies as st
from fastapi import status


# HTTP method strategies
http_method_strategy = st.sampled_from([
    "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"
])

# HTTP status code strategies
success_status_strategy = st.sampled_from([
    status.HTTP_200_OK,
    status.HTTP_201_CREATED,
    status.HTTP_202_ACCEPTED,
    status.HTTP_204_NO_CONTENT,
])

client_error_status_strategy = st.sampled_from([
    status.HTTP_400_BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_ENTITY,
    status.HTTP_429_TOO_MANY_REQUESTS,
])

server_error_status_strategy = st.sampled_from([
    status.HTTP_500_INTERNAL_SERVER_ERROR,
    status.HTTP_502_BAD_GATEWAY,
    status.HTTP_503_SERVICE_UNAVAILABLE,
])

# Header strategies
header_name_strategy = st.from_regex(
    r"^[a-zA-Z0-9][a-zA-Z0-9\-_]*[a-zA-Z0-9]$",
    fullmatch=True
)

header_value_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        max_codepoint=127
    ),
    min_size=1,
    max_size=200
)

headers_strategy = st.dictionaries(
    keys=header_name_strategy,
    values=header_value_strategy,
    min_size=0,
    max_size=10
)

# Content-Type strategies
content_type_strategy = st.sampled_from([
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "text/plain",
    "text/html",
    "application/xml",
])

# Query parameter strategies
query_param_value_strategy = st.one_of(
    st.text(min_size=0, max_size=100),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans().map(str),
)

query_params_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))),
    values=query_param_value_strategy,
    min_size=0,
    max_size=10
)

# JSON payload strategies
json_primitive_strategy = st.one_of(
    st.none(),
    st.booleans(), 
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text()
)

json_object_strategy = st.recursive(
    json_primitive_strategy,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=10),
        st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=children,
            min_size=0,
            max_size=10
        )
    ),
    max_leaves=20
)

# Request strategies
@st.composite
def api_request_strategy(draw,
                        method: str = None,
                        path: str = None):
    """Generate API request data."""
    return {
        "method": method or draw(http_method_strategy),
        "path": path or draw(st.text(min_size=1, max_size=100)),
        "headers": draw(headers_strategy),
        "query_params": draw(query_params_strategy),
        "json_payload": draw(st.one_of(st.none(), json_object_strategy)),
    }

# Response strategies  
@st.composite
def api_response_strategy(draw,
                         status_code: int = None):
    """Generate API response data."""
    return {
        "status_code": status_code or draw(success_status_strategy),
        "headers": draw(headers_strategy),
        "json_data": draw(st.one_of(st.none(), json_object_strategy)),
        "text_data": draw(st.one_of(st.none(), st.text())),
    }

@st.composite
def error_response_strategy(draw,
                           status_code: int = None):
    """Generate error response data."""
    error_status = status_code or draw(client_error_status_strategy)
    
    return {
        "status_code": error_status,
        "headers": draw(headers_strategy),
        "detail": draw(st.text(min_size=1, max_size=200)),
        "error_code": draw(st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N")))),
        "correlation_id": draw(st.uuids().map(str)),
    }

# Authentication strategies
auth_token_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127),
    min_size=20,
    max_size=200
)

bearer_token_strategy = auth_token_strategy.map(lambda t: f"Bearer {t}")

# User agent strategies
user_agent_strategy = st.sampled_from([
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "TestClient/1.0 (pytest)",
    "curl/7.68.0",
    "PostmanRuntime/7.28.4",
])

# IP address strategies (for rate limiting tests)
ip_address_strategy = st.ip_addresses(v=4).map(str)

# Rate limiting test strategies
@st.composite
def rate_limit_scenario_strategy(draw):
    """Generate rate limiting test scenarios."""
    return {
        "ip_address": draw(ip_address_strategy),
        "user_agent": draw(user_agent_strategy),
        "requests_per_minute": draw(st.integers(min_value=1, max_value=1000)),
        "burst_size": draw(st.integers(min_value=1, max_value=50)),
    }

# Pagination strategies
@st.composite
def pagination_params_strategy(draw):
    """Generate pagination parameters."""
    return {
        "page": draw(st.integers(min_value=1, max_value=100)),
        "page_size": draw(st.integers(min_value=1, max_value=100)),
        "offset": draw(st.integers(min_value=0, max_value=1000)),
        "limit": draw(st.integers(min_value=1, max_value=100)),
    }

# Sorting strategies
sort_field_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127),
    min_size=1,
    max_size=50
)

sort_direction_strategy = st.sampled_from(["asc", "desc", "ASC", "DESC"])

@st.composite
def sorting_params_strategy(draw):
    """Generate sorting parameters."""
    return {
        "sort_by": draw(sort_field_strategy),
        "sort_order": draw(sort_direction_strategy),
        "sort": draw(st.text(min_size=1, max_size=100)),  # Combined sort param
    }

# Filter strategies
@st.composite
def filter_params_strategy(draw):
    """Generate filtering parameters."""
    return {
        "search": draw(st.text(min_size=0, max_size=100)),
        "category": draw(st.text(min_size=1, max_size=50)),
        "status": draw(st.sampled_from(["active", "inactive", "pending", "completed"])),
        "date_from": draw(st.dates().map(str)),
        "date_to": draw(st.dates().map(str)),
        "min_age": draw(st.integers(min_value=18, max_value=100)),
        "max_age": draw(st.integers(min_value=18, max_value=100)),
    }

# Complete API test scenario
@st.composite 
def api_test_scenario_strategy(draw):
    """Generate complete API test scenario."""
    return {
        "request": draw(api_request_strategy()),
        "expected_response": draw(api_response_strategy()),
        "auth_token": draw(st.one_of(st.none(), bearer_token_strategy)),
        "rate_limit": draw(rate_limit_scenario_strategy()),
        "pagination": draw(pagination_params_strategy()),
        "sorting": draw(sorting_params_strategy()),
        "filters": draw(filter_params_strategy()),
    }