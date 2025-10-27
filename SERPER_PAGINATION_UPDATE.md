# Serper API Pagination and Danish Defaults Update

## Summary

Updated the Serper API integration to properly handle pagination (to get up to 100 results) and added Danish language/country defaults with UI controls.

## Changes Made

### 1. ✅ Fixed Serper Pagination (backend/core/search_engines/serper.py)

**Problem**: The code tried to get 100 results in a single request with `"num": max_results`, but Serper API only returns **10 results per page maximum**.

**Solution**: Implemented proper pagination that iterates through pages:
```python
# For max_results=100, fetch 10 pages
pages_needed = (max_results + 10 - 1) // 10  # Ceiling division

for page in range(1, pages_needed + 1):
    payload = {
        "q": query,
        "num": 10,  # Max per page
        "page": page,
        "gl": gl,
        "hl": hl,
    }
    # Fetch and accumulate results...
```

**Benefits**:
- Can now actually retrieve up to 100 results (previously max was 10)
- Stops early if no more results available
- Properly ranks results across all pages

### 2. ✅ Added Danish Defaults

**Default Parameters**:
- `gl="dk"` - Denmark (country)
- `hl="da"` - Danish (language)

```python
# Set Danish defaults
gl = kwargs.get("gl", "dk")  # Default to Denmark
hl = kwargs.get("hl", "da")  # Default to Danish
```

### 3. ✅ Added UI Controls for Language/Country

**Location**: `frontend/templates/search/new.html`

Added two dropdowns after "Max Results" field:

**Language Options**:
- Danish (Dansk) - **default**
- English
- German (Deutsch)
- French (Français)
- Spanish (Español)
- Swedish (Svenska)
- Norwegian (Norsk)

**Country Options**:
- Denmark - **default**
- United States
- United Kingdom
- Germany
- France
- Sweden
- Norway

### 4. ✅ Updated Backend Schema (backend/schemas/search.py)

Added fields to `SearchExecuteRequest`:
```python
language: str = Field("da", description="Language code (hl parameter) - defaults to Danish")
country: str = Field("dk", description="Country code (gl parameter) - defaults to Denmark")
```

### 5. ✅ Updated API Endpoint (backend/api/search.py)

Modified to pass language and country to the service:
```python
await service.execute_search(
    session=session,
    queries=request.queries,
    search_engine=request.search_engine,
    max_results=request.max_results,
    language=request.language,  # NEW
    country=request.country,     # NEW
    allowed_domains=request.allowed_domains
)
```

### 6. ✅ Updated Search Service (backend/services/search_service.py)

Modified methods to accept and pass through language/country parameters:

**execute_search()**:
```python
async def execute_search(
    self,
    session: SearchSession,
    queries: list[str],
    search_engine: str,
    max_results: int,
    language: str = "da",  # NEW
    country: str = "dk",   # NEW
    allowed_domains: Optional[list[str]] = None
) -> SearchSession:
```

**_execute_single_query()**:
```python
results = await engine.search(
    query=query_text,
    max_results=max_results,
    hl=language,  # NEW
    gl=country    # NEW
)
```

## Testing

### Test Pagination

Create a search with `max_results=100`:
```python
# Should make 10 API calls (pages 1-10)
# Should return up to 100 results
```

### Test Danish Defaults

Create a search without specifying language/country:
```python
# Should use gl="dk" and hl="da" by default
# Results should be Danish websites
```

### Test Custom Language/Country

Create a search with English/US:
```python
{
    "language": "en",
    "country": "us",
    "queries": ["climate change"],
    "max_results": 50
}
# Should make 5 API calls (pages 1-5)
# Results should be English, US-focused
```

## API Cost Impact

**Before**: Max 1 API call per query (10 results max)
**After**: Up to 10 API calls per query (for 100 results)

**Example**:
- 5 queries × 100 results each = 50 API calls
- At Serper pricing (~$2 per 1000 calls) = $0.10

**Recommendation**: Use lower `max_results` values (10-30) for most searches to minimize costs.

## Files Modified

1. ✅ `backend/core/search_engines/serper.py` - Pagination logic
2. ✅ `backend/schemas/search.py` - Added language/country fields
3. ✅ `backend/api/search.py` - Pass parameters through
4. ✅ `backend/services/search_service.py` - Accept and use parameters
5. ✅ `frontend/templates/search/new.html` - Added UI dropdowns

## Configuration

No configuration changes needed. Defaults work out of the box:
- Language: Danish (`da`)
- Country: Denmark (`dk`)

Users can override via the UI or API.

## Example API Request

```bash
curl -X POST "http://your-server:8080/api/search/execute" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "Danish Climate Research",
    "queries": ["klimaforandringer", "vedvarende energi"],
    "search_engine": "serper",
    "max_results": 50,
    "language": "da",
    "country": "dk"
  }'
```

## Logging

The updated code logs pagination progress:
```
INFO: Fetching page 1/5 for query: klimaforandringer
INFO: Fetching page 2/5 for query: klimaforandringer
...
INFO: Serper search for 'klimaforandringer' returned 47 results from 5 page(s) (gl=dk, hl=da)
```

## Next Steps

1. **Test the pagination** with a real Serper API key
2. **Monitor API usage** to ensure costs stay within budget
3. **Consider caching** results to avoid duplicate API calls
4. **Add rate limiting** if making many large searches

## Status

✅ **Ready for use** - All changes deployed with uvicorn --reload
