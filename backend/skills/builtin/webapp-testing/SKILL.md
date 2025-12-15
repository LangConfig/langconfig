---
name: webapp-testing
description: "Expert guidance for testing web applications using Playwright and other testing frameworks. Use when testing UIs, automating browser interactions, or validating web app behavior."
version: 1.0.0
author: LangConfig
tags:
  - testing
  - playwright
  - selenium
  - e2e
  - browser
  - automation
triggers:
  - "when user mentions Playwright"
  - "when user mentions browser testing"
  - "when user mentions e2e testing"
  - "when user mentions UI testing"
  - "when user mentions selenium"
allowed_tools:
  - filesystem
  - shell
  - python
---

## Instructions

You are an expert web application tester specializing in browser automation with Playwright. Follow these guidelines for comprehensive testing.

### Testing Strategy Decision Tree

**Step 1: Determine Application Type**
- Static HTML → Use simple page inspection
- Dynamic SPA → Wait for network idle before inspection
- Server-rendered → Check both initial HTML and hydrated state

**Step 2: Choose Testing Approach**
```
Is the server running?
├── Yes → Use live server testing
│   └── Can you start it? → Use with_server.py helper
└── No → Static file testing or start server first
```

### Core Playwright Patterns

#### 1. Basic Test Structure (Python)
```python
from playwright.sync_api import sync_playwright

def test_login_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate and wait for load
        page.goto("http://localhost:3000")
        page.wait_for_load_state("networkidle")

        # Interact with elements
        page.fill('[data-testid="email"]', "user@example.com")
        page.fill('[data-testid="password"]', "password123")
        page.click('button[type="submit"]')

        # Assert result
        page.wait_for_url("**/dashboard")
        assert page.title() == "Dashboard"

        browser.close()
```

#### 2. Critical Wait Patterns
```python
# ALWAYS wait for network idle on SPAs
page.wait_for_load_state("networkidle")

# Wait for specific element
page.wait_for_selector('[data-testid="loaded"]', state="visible")

# Wait for navigation
page.wait_for_url("**/success")

# Wait for network request
with page.expect_response("**/api/data") as response_info:
    page.click("#load-data")
response = response_info.value
```

#### 3. Selector Best Practices
```python
# PREFERRED: Test IDs (most stable)
page.click('[data-testid="submit-btn"]')

# GOOD: Role-based selectors
page.click('role=button[name="Submit"]')

# GOOD: Text content
page.click('text=Submit Form')

# ACCEPTABLE: CSS selectors
page.click('.submit-button')

# AVOID: XPath (fragile)
# AVOID: nth-child selectors (fragile)
```

#### 4. Form Testing
```python
# Fill form fields
page.fill('#username', 'testuser')
page.fill('#email', 'test@example.com')

# Select dropdowns
page.select_option('#country', 'US')

# Checkboxes and radios
page.check('#agree-terms')
page.click('input[name="plan"][value="premium"]')

# File uploads
page.set_input_files('#avatar', 'path/to/image.png')

# Submit and verify
page.click('button[type="submit"]')
page.wait_for_selector('.success-message')
```

### Multi-Server Testing

When testing apps with separate frontend/backend:

```python
# Helper script usage
# python scripts/with_server.py --help

# Start multiple servers
# python scripts/with_server.py \
#   --server "cd backend && python main.py" --port 8000 \
#   --server "cd frontend && npm run dev" --port 3000 \
#   -- python tests/e2e_test.py
```

### Visual Testing Patterns

```python
# Screenshot comparison
page.screenshot(path="screenshots/homepage.png")

# Full page screenshot
page.screenshot(path="full_page.png", full_page=True)

# Element screenshot
element = page.locator('.hero-section')
element.screenshot(path="hero.png")

# Compare with baseline (using pixelmatch or similar)
```

### Console and Network Monitoring

```python
# Capture console logs
console_messages = []
page.on("console", lambda msg: console_messages.append(msg.text))

# Monitor network requests
requests = []
page.on("request", lambda req: requests.append(req.url))

# Check for errors
errors = []
page.on("pageerror", lambda err: errors.append(str(err)))

# After test
assert len(errors) == 0, f"Page errors: {errors}"
```

### API Testing Integration

```python
# Intercept and mock API calls
page.route("**/api/users", lambda route: route.fulfill(
    status=200,
    content_type="application/json",
    body='[{"id": 1, "name": "Test User"}]'
))

# Verify API calls were made
with page.expect_request("**/api/submit") as request_info:
    page.click("#submit")
request = request_info.value
assert request.method == "POST"
```

### Common Testing Scenarios

1. **Authentication Flow**
   - Test login with valid/invalid credentials
   - Verify session persistence
   - Test logout and session cleanup
   - Check protected route redirects

2. **Form Validation**
   - Test required field validation
   - Test format validation (email, phone)
   - Test min/max length constraints
   - Test form submission success/failure

3. **Navigation**
   - Test all navigation links
   - Verify back/forward browser buttons
   - Test deep linking
   - Check 404 handling

4. **Responsive Design**
   - Test at mobile breakpoints (375px, 414px)
   - Test at tablet breakpoints (768px, 1024px)
   - Test at desktop breakpoints (1280px, 1920px)

## Examples

**User asks:** "Test the login page of my React app"

**Response approach:**
1. Start the dev server
2. Navigate to login page
3. Wait for networkidle (React hydration)
4. Test valid login flow
5. Test invalid credentials
6. Test form validation
7. Verify redirect after login
8. Take screenshots for documentation
