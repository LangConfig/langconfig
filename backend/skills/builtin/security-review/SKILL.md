---
name: security-review
description: "Comprehensive security code review covering OWASP Top 10, authentication, authorization, and secure coding practices. Use when reviewing code for vulnerabilities or implementing security features."
version: 1.0.0
author: LangConfig
tags:
  - security
  - owasp
  - vulnerabilities
  - authentication
  - authorization
  - code-review
triggers:
  - "when user mentions security"
  - "when user mentions vulnerability"
  - "when user mentions OWASP"
  - "when user mentions authentication"
  - "when user mentions XSS"
  - "when user mentions SQL injection"
allowed_tools:
  - filesystem
  - grep
---

## Instructions

You are a security expert conducting code reviews. Focus on identifying vulnerabilities and recommending secure alternatives.

### OWASP Top 10 Checklist (2021)

#### 1. Broken Access Control (A01)
**Look for:**
- Missing authorization checks on endpoints
- Direct object references without validation
- Privilege escalation paths
- CORS misconfigurations

**Bad:**
```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return db.query(User).get(user_id)  # No auth check!
```

**Good:**
```python
@app.get("/users/{user_id}")
def get_user(user_id: int, current_user: User = Depends(get_current_user)):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(403, "Access denied")
    return db.query(User).get(user_id)
```

#### 2. Cryptographic Failures (A02)
**Look for:**
- Sensitive data in plaintext
- Weak encryption algorithms (MD5, SHA1)
- Hardcoded secrets
- Missing HTTPS

**Bad:**
```python
password_hash = hashlib.md5(password.encode()).hexdigest()
API_KEY = "sk-1234567890"  # Hardcoded!
```

**Good:**
```python
from passlib.hash import bcrypt
password_hash = bcrypt.hash(password)
API_KEY = os.environ.get("API_KEY")
```

#### 3. Injection (A03)
**Look for:**
- SQL injection
- Command injection
- LDAP injection
- Template injection

**Bad:**
```python
query = f"SELECT * FROM users WHERE name = '{user_input}'"
os.system(f"convert {filename} output.png")
```

**Good:**
```python
query = "SELECT * FROM users WHERE name = :name"
db.execute(query, {"name": user_input})

import subprocess
subprocess.run(["convert", filename, "output.png"], check=True)
```

#### 4. Insecure Design (A04)
**Look for:**
- Missing rate limiting
- No account lockout
- Predictable resource IDs
- Missing security headers

**Implement:**
```python
# Rate limiting
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/login")
@limiter.limit("5/minute")
def login(request: Request):
    ...

# Security headers
app.add_middleware(
    SecurityHeadersMiddleware,
    content_security_policy="default-src 'self'",
    x_frame_options="DENY"
)
```

#### 5. Security Misconfiguration (A05)
**Look for:**
- Debug mode in production
- Default credentials
- Unnecessary features enabled
- Verbose error messages

**Check:**
```python
# Bad
DEBUG = True
SECRET_KEY = "change-me"

# Good
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY must be set")
```

#### 6. Vulnerable Components (A06)
**Look for:**
- Outdated dependencies
- Known vulnerable packages
- Unmaintained libraries

**Tools:**
```bash
# Python
pip-audit
safety check

# JavaScript
npm audit
snyk test

# General
dependabot alerts
```

#### 7. Authentication Failures (A07)
**Look for:**
- Weak password requirements
- Missing MFA
- Session fixation
- Credential stuffing vulnerability

**Implement:**
```python
# Strong password validation
import re

def validate_password(password: str) -> bool:
    if len(password) < 12:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[!@#$%^&*]', password):
        return False
    return True

# Secure session configuration
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Strict',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1)
)
```

#### 8. Software/Data Integrity Failures (A08)
**Look for:**
- Missing integrity checks on updates
- Insecure deserialization
- Untrusted CI/CD pipelines

**Bad:**
```python
import pickle
data = pickle.loads(user_input)  # Dangerous!
```

**Good:**
```python
import json
data = json.loads(user_input)  # Safe for untrusted input
```

#### 9. Security Logging Failures (A09)
**Look for:**
- Missing audit logs
- Sensitive data in logs
- No alerting on failures

**Implement:**
```python
import logging

# Configure secure logging
logger = logging.getLogger("security")
logger.setLevel(logging.INFO)

# Log security events
def login(username: str, password: str):
    user = authenticate(username, password)
    if user:
        logger.info(f"Successful login: user={username} ip={request.client.host}")
    else:
        logger.warning(f"Failed login attempt: user={username} ip={request.client.host}")
```

#### 10. Server-Side Request Forgery (A10)
**Look for:**
- User-controlled URLs in requests
- Internal service access
- Cloud metadata endpoints

**Bad:**
```python
@app.get("/fetch")
def fetch_url(url: str):
    return requests.get(url).content  # SSRF!
```

**Good:**
```python
from urllib.parse import urlparse

ALLOWED_HOSTS = ["api.example.com", "cdn.example.com"]

@app.get("/fetch")
def fetch_url(url: str):
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(400, "URL not allowed")
    if parsed.scheme not in ["http", "https"]:
        raise HTTPException(400, "Invalid scheme")
    return requests.get(url).content
```

### Security Review Checklist

#### Authentication
- [ ] Passwords hashed with bcrypt/argon2
- [ ] Session tokens are random and long enough
- [ ] Session invalidation on logout
- [ ] Account lockout after failed attempts
- [ ] Secure password reset flow

#### Authorization
- [ ] All endpoints have auth checks
- [ ] Role-based access control implemented
- [ ] No privilege escalation paths
- [ ] API keys properly scoped

#### Input Validation
- [ ] All user input validated
- [ ] File upload restrictions (type, size)
- [ ] URL parameters sanitized
- [ ] JSON schema validation

#### Output Encoding
- [ ] HTML output escaped
- [ ] JSON responses properly formatted
- [ ] No sensitive data in responses
- [ ] Error messages don't leak info

#### Data Protection
- [ ] Sensitive data encrypted at rest
- [ ] TLS for data in transit
- [ ] Secrets in environment variables
- [ ] PII properly handled

## Examples

**User asks:** "Review my authentication code for security issues"

**Response approach:**
1. Check password hashing algorithm
2. Review session management
3. Look for timing attacks
4. Check rate limiting
5. Review token generation
6. Verify secure cookie settings
7. Check for credential exposure in logs
