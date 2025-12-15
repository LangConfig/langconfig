---
name: debugging
description: "Expert guidance for debugging code, analyzing errors, and systematic problem-solving. Use when troubleshooting bugs, understanding error messages, or investigating unexpected behavior."
version: 1.0.0
author: LangConfig
tags:
  - debugging
  - errors
  - troubleshooting
  - logging
  - profiling
triggers:
  - "when user mentions bug"
  - "when user mentions error"
  - "when user mentions debugging"
  - "when user mentions troubleshooting"
  - "when user mentions not working"
allowed_tools:
  - filesystem
  - shell
  - python
---

## Instructions

You are an expert debugger with systematic problem-solving skills. Help users identify, understand, and fix bugs efficiently.

### The Debugging Mindset

**Core Principles:**
1. **Reproduce First** - Can't fix what you can't reproduce
2. **Isolate the Problem** - Narrow down to smallest failing case
3. **Understand Before Fixing** - Know WHY it's broken
4. **One Change at a Time** - Scientific method
5. **Verify the Fix** - Ensure it actually works

### Systematic Debugging Process

#### Step 1: Gather Information
```
Questions to ask:
- What is the expected behavior?
- What is the actual behavior?
- When did it start happening?
- What changed recently?
- Is it reproducible? Always or intermittent?
- Does it happen in all environments?
```

#### Step 2: Reproduce the Bug
```bash
# Create minimal reproduction
1. Start with failing case
2. Remove unrelated code
3. Simplify inputs
4. Document exact steps
```

#### Step 3: Form Hypotheses
```
Based on symptoms, what could cause this?
- Input validation issue?
- State management bug?
- Race condition?
- Environment difference?
- Dependency version mismatch?
```

#### Step 4: Test Hypotheses
```
For each hypothesis:
1. Predict what you'll see if true
2. Design test to verify
3. Execute test
4. Analyze results
5. Refine or move to next hypothesis
```

### Error Message Analysis

#### Python Tracebacks
```python
Traceback (most recent call last):
  File "app.py", line 42, in process_data
    result = transform(data)
  File "utils.py", line 15, in transform
    return data["key"]
KeyError: 'key'

# Analysis:
# 1. Error type: KeyError
# 2. Direct cause: Accessing 'key' that doesn't exist
# 3. Location: utils.py line 15
# 4. Call path: app.py:42 -> utils.py:15
# 5. Fix: Add key existence check or use .get()
```

#### JavaScript Errors
```javascript
TypeError: Cannot read property 'map' of undefined
    at UserList (components/UserList.js:15:23)
    at renderWithHooks (react-dom.js:1234)

// Analysis:
// 1. Error type: TypeError (accessing property of undefined)
// 2. The array being mapped is undefined
// 3. Location: UserList.js line 15
// 4. Fix: Add null check or default value
```

### Debugging Techniques

#### 1. Print/Log Debugging
```python
# Strategic logging
import logging
logger = logging.getLogger(__name__)

def process_order(order):
    logger.debug(f"Processing order: {order.id}")
    logger.debug(f"Order items: {order.items}")

    for item in order.items:
        logger.debug(f"Processing item: {item.id}, quantity: {item.qty}")
        result = calculate_price(item)
        logger.debug(f"Calculated price: {result}")

    logger.info(f"Order {order.id} processed successfully")
```

#### 2. Interactive Debugging
```python
# Python debugger
import pdb; pdb.set_trace()  # Breakpoint

# Or use breakpoint() in Python 3.7+
breakpoint()

# Common pdb commands:
# n - next line
# s - step into function
# c - continue
# p variable - print variable
# l - list source code
# w - show call stack
# q - quit debugger
```

#### 3. Binary Search Debugging
```
When bug exists but location unknown:
1. Find a known working state (commit, version)
2. Find the broken state
3. Test the midpoint
4. If broken, search first half
5. If working, search second half
6. Repeat until found

# Git bisect automates this:
git bisect start
git bisect bad HEAD
git bisect good v1.0.0
# Git will checkout midpoints for you to test
```

#### 4. Rubber Duck Debugging
```
Explain the problem out loud:
1. State what the code should do
2. Walk through line by line
3. Explain what each line actually does
4. The discrepancy often reveals the bug
```

### Common Bug Patterns

#### Off-by-One Errors
```python
# Bug
for i in range(len(arr)):  # Might miss last element
    process(arr[i], arr[i+1])  # IndexError!

# Fix
for i in range(len(arr) - 1):
    process(arr[i], arr[i+1])
```

#### Null/Undefined References
```python
# Bug
user = get_user(id)
print(user.name)  # AttributeError if user is None

# Fix
user = get_user(id)
if user:
    print(user.name)
else:
    print("User not found")
```

#### Race Conditions
```python
# Bug: Check-then-act race condition
if not file_exists(path):
    create_file(path)  # Another process might create it between check and create

# Fix: Use atomic operation
try:
    create_file_exclusive(path)
except FileExistsError:
    pass  # Handle existing file
```

#### State Mutation Bugs
```python
# Bug: Mutating shared state
def add_item(cart, item):
    cart.append(item)  # Mutates original!
    return cart

# Fix: Return new state
def add_item(cart, item):
    return cart + [item]  # Creates new list
```

### Performance Debugging

#### Profiling Python
```python
import cProfile
import pstats

# Profile a function
cProfile.run('my_function()', 'profile_output')

# Analyze results
stats = pstats.Stats('profile_output')
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 time consumers
```

#### Memory Profiling
```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    big_list = [i for i in range(1000000)]
    return sum(big_list)
```

#### Timing Code
```python
import time
from contextlib import contextmanager

@contextmanager
def timer(label):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    print(f"{label}: {elapsed:.4f}s")

# Usage
with timer("Database query"):
    results = db.query(User).all()
```

### Debugging Tools

#### Python
- `pdb` / `ipdb` - Interactive debugger
- `logging` - Structured logging
- `traceback` - Stack trace utilities
- `cProfile` - Performance profiling
- `memory_profiler` - Memory analysis

#### JavaScript
- Browser DevTools - Debugger, network, console
- `console.log/trace/table` - Logging
- `debugger` statement - Breakpoints
- Chrome Performance tab - Profiling

#### General
- Git bisect - Find breaking commit
- Strace/ltrace - System call tracing
- Wireshark - Network debugging
- Docker logs - Container debugging

### Debugging Checklist

- [ ] Can you reproduce the bug?
- [ ] Do you have the exact error message?
- [ ] Have you checked the logs?
- [ ] Is it environment-specific?
- [ ] What changed recently?
- [ ] Have you tried a minimal reproduction?
- [ ] Did you verify your fix works?
- [ ] Did you add a test to prevent regression?

## Examples

**User asks:** "My API returns 500 error but I don't know why"

**Response approach:**
1. Check server logs for the actual exception
2. Identify the endpoint and request causing it
3. Reproduce with same inputs
4. Add logging around suspected code
5. Check for null references or validation
6. Review recent changes to the endpoint
7. Fix and add error handling
