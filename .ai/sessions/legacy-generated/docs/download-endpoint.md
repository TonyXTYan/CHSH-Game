# Download CSV Endpoint

## Overview

A new `/download` endpoint has been added to provide direct CSV download functionality that mirrors the behavior of the "Download CSV" button on the dashboard.

## Endpoint Details

- **URL**: `/download`
- **Method**: `GET`
- **Response**: CSV file with game data
- **Content-Type**: `text/csv`
- **Filename**: `chsh-game-data.csv`

## Functionality

The `/download` endpoint:

1. Retrieves all answers from the database in chronological order
2. Generates CSV content in memory using Python's `csv` module
3. Returns the CSV file with appropriate headers for browser download
4. Uses the same data structure and format as the original "Download CSV" button

## CSV Format

The CSV file includes the following columns:

1. **Timestamp** - Formatted as MM/DD/YYYY, HH:MM:SS AM/PM
2. **Team Name** - Name of the team
3. **Team ID** - Database ID of the team
4. **Player ID** - Session ID of the player
5. **Round ID** - Database ID of the question round
6. **Question Item (A/B/X/Y)** - The item assigned to the player
7. **Answer (True/False)** - The player's response

## Usage Examples

### Direct URL Access
```
GET http://localhost:8080/download
```

### Using curl
```bash
curl -o chsh-game-data.csv http://localhost:8080/download
```

### Using wget
```bash
wget -O chsh-game-data.csv http://localhost:8080/download
```

## Error Handling

- **500 Internal Server Error**: Returned if there's a database error or other server-side issue
- Error responses include a plain text error message describing the issue

## Testing

The endpoint is covered by unit tests in `tests/unit/test_dashboard_sockets.py`:

- `test_download_csv_endpoint` - Tests normal operation
- `test_download_csv_endpoint_error` - Tests error handling
- `test_download_csv_endpoint_empty_data` - Tests with no data

## Comparison with Dashboard Button

The `/download` endpoint provides identical functionality to the "Download CSV" button:

- **Dashboard Button**: Fetches data via AJAX from `/api/dashboard/data`, processes to CSV in JavaScript, triggers download
- **Download Endpoint**: Fetches data directly from database, generates CSV server-side, returns as file download

Both methods produce the same CSV format and content.

## Implementation Details

The endpoint is implemented in `src/sockets/dashboard.py`:

```python
@app.route('/download', methods=['GET'])
def download_csv():
    # Implementation details...
```

Key features:
- Uses `io.StringIO()` for in-memory CSV generation
- Proper HTTP headers for file download
- Timestamp formatting matches JavaScript `toLocaleString()`
- Comprehensive error handling with rollback on database errors
