# Server Functionality Tests

## Overview

This document describes the comprehensive server functionality tests added to verify that the Flask server is working correctly after startup. These tests ensure that all web pages load properly, UI elements are present, APIs function correctly, and the server handles various scenarios robustly.

## Test File Location

- **File**: `tests/integration/test_server_functionality.py`
- **Test Class**: `TestServerFunctionality`
- **Total Tests**: 17 comprehensive tests
- **Test Type**: Integration tests (marked with `@pytest.mark.integration`)

## Test Coverage

### 1. Basic Server Health
- **`test_server_is_running`**: Verifies server is accessible and responding
- **`test_server_performance_basic`**: Ensures response time is under 5 seconds
- **`test_multiple_concurrent_requests`**: Tests server handles 5 concurrent requests

### 2. Web Page Loading
- **`test_main_page_loads`**: Verifies index.html loads with correct title and content type
- **`test_dashboard_page_loads`**: Ensures dashboard.html loads with proper headers
- **`test_about_page_loads`**: Confirms about.html is accessible

### 3. UI Element Verification
- **`test_main_page_key_elements`**: Checks for essential UI components:
  - Create team button (`createTeamBtn`)
  - Team name input field (`teamNameInput`)
  - Question section (initially hidden)
  - True/False answer buttons
  - Status message area

- **`test_dashboard_key_elements`**: Verifies dashboard components:
  - Metric cards (active teams, connected players, total responses)
  - Game control buttons (Start Game, Pause)
  - Teams table with correct headers
  - Answer log section and toggle button

### 4. Static File Serving
- **`test_static_css_files_load`**: Ensures CSS files are served correctly:
  - `styles.css` (main styles)
  - `dashboard.css` (dashboard styles)
  - Verifies correct MIME type and non-empty content

- **`test_static_js_files_load`**: Confirms JavaScript files load properly:
  - `app.js` (main application logic)
  - `socket-handlers.js` (WebSocket handling)
  - `dashboard.js` (dashboard functionality)
  - Validates MIME types and content

### 5. API Endpoint Testing
- **`test_api_server_id_endpoint`**: Tests `/api/server/id` endpoint:
  - Returns 200 status code
  - Provides JSON response with `instance_id`
  - Validates data types and structure

- **`test_dashboard_data_api_endpoint`**: Tests `/api/dashboard/data` endpoint:
  - Returns answers array with proper structure
  - Validates answer object schema if data exists
  - Ensures JSON format and required fields

- **`test_download_csv_endpoint`**: Verifies `/download` CSV endpoint:
  - Returns proper CSV content type
  - Sets attachment headers for download
  - Generates non-empty CSV content
  - Validates basic CSV structure

### 6. Security & Error Handling
- **`test_path_traversal_protection`**: Tests security against path traversal attacks:
  - Tries various malicious paths (`../../../etc/passwd`, etc.)
  - Ensures server doesn't serve system files
  - Validates either 403/404 or safe fallback to index.html

- **`test_nonexistent_page_fallback`**: Confirms SPA routing behavior:
  - Non-existent pages fall back to index.html
  - Maintains proper game application structure

- **`test_error_handling_404`**: Tests 404 handling for static files:
  - Missing static files return appropriate responses
  - Error handling doesn't break application

- **`test_content_security_headers`**: Documents security headers (informational):
  - Checks for common security headers
  - Non-blocking test for security best practices

## Test Features

### HTML Parsing & Validation
- Uses **BeautifulSoup4** for robust HTML parsing
- Validates page structure, element presence, and content
- Checks CSS classes, IDs, and element attributes
- Verifies expected text content in buttons and headers

### API Response Validation
- Tests JSON API responses for correct structure
- Validates data types and required fields
- Ensures proper HTTP status codes and headers
- Checks API error handling

### Performance Testing
- Basic response time validation
- Concurrent request handling
- Server stability under load

### Security Testing
- Path traversal attack prevention
- Input validation and sanitization
- Proper error handling without information disclosure

## Dependencies Added

- **`beautifulsoup4==4.12.3`**: For HTML parsing and element verification
- **`requests==2.32.3`**: For HTTP requests (already present)

## Usage Examples

### Run All Server Functionality Tests
```bash
pytest tests/integration/test_server_functionality.py -v
```

### Run Specific Test Categories
```bash
# Test only page loading
pytest tests/integration/test_server_functionality.py::TestServerFunctionality::test_main_page_loads -v

# Test only API endpoints
pytest tests/integration/test_server_functionality.py::TestServerFunctionality::test_api_server_id_endpoint -v

# Test security features
pytest tests/integration/test_server_functionality.py::TestServerFunctionality::test_path_traversal_protection -v
```

### Run with Coverage
```bash
pytest tests/integration/test_server_functionality.py --cov=src --cov-report=html
```

## Test Results

✅ **All 17 tests pass** successfully:

```
tests/integration/test_server_functionality.py::TestServerFunctionality::test_server_is_running PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_main_page_loads PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_main_page_key_elements PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_dashboard_page_loads PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_dashboard_key_elements PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_about_page_loads PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_static_css_files_load PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_static_js_files_load PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_api_server_id_endpoint PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_dashboard_data_api_endpoint PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_download_csv_endpoint PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_nonexistent_page_fallback PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_path_traversal_protection PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_server_performance_basic PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_multiple_concurrent_requests PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_content_security_headers PASSED
tests/integration/test_server_functionality.py::TestServerFunctionality::test_error_handling_404 PASSED

17 passed in 1.92s
```

## Benefits

1. **Comprehensive Coverage**: Tests all major aspects of web server functionality
2. **UI Validation**: Ensures critical user interface elements are present and functional
3. **API Verification**: Validates all public API endpoints work correctly
4. **Security Testing**: Protects against common web vulnerabilities
5. **Performance Monitoring**: Basic performance and load testing
6. **Regression Prevention**: Catches issues when server configuration changes
7. **CI/CD Integration**: Automated validation in continuous integration pipeline

## Integration with Existing Test Suite

These tests integrate seamlessly with the existing pytest server integration:
- **Automatic Server Startup**: Uses the same Flask server fixture from `conftest.py`
- **Proper Test Isolation**: Each test is independent and doesn't affect others
- **Fast Execution**: All 17 tests complete in under 2 seconds
- **CI Compatible**: Works with existing GitHub Actions workflow

The server functionality tests provide comprehensive validation that the CHSH Game web application is working correctly at all levels - from basic server health to complex UI interactions and API functionality.