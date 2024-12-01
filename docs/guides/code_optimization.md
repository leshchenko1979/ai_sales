# Code Optimization Guidelines

## 1. Code Structure
- Main functions and public methods at the beginning
- Helper/private methods at the end
- Group related methods together
- Reduce code nesting
- Follow DRY principle (Don't Repeat Yourself)

## 2. Imports
### High-level imports preferred:
```python
# Preferred
from core import db
from core.accounts import models

# Instead of
from core.accounts.models.profile import AccountProfile
from core.db.base import BaseQueries
```

### Import organization:
1. Standard library imports
2. Third-party imports
3. Local application imports
4. Blank line between import groups

## 3. Method Organization
Group methods in this order:
1. Core/Main operations
2. Bulk operations
3. Secondary operations
4. Factory methods
5. Helper methods

## 4. Error Handling
- Centralize error handling with decorators
- Use specific error types
- Proper logging of errors
- Safe rollback on failures
- Return meaningful error responses

## 5. Database Operations
- Safe commit/rollback handling
- Session management through context managers
- Query optimization
- Proper transaction handling
- Connection pooling consideration

## 6. Code Quality
- Clear method and variable names
- Comprehensive docstrings
- Type hints where applicable
- Remove unused code
- Keep methods focused and single-purpose

## 7. Class Structure
### Order of class elements:
1. Class docstring
2. Class attributes
3. `__init__`
4. Public methods
5. Protected methods
6. Private methods
7. Static/class methods at the end

## 8. Comments and Documentation
- Clear docstrings for classes and methods
- Comments for complex logic
- Type hints for better code understanding
- Examples in docstrings for complex methods

## 9. Performance Considerations
- Lazy loading when appropriate
- Efficient database queries
- Proper indexing
- Caching where beneficial
- Asynchronous operations when needed

## 10. Testing
- Ensure testability of code
- Separate concerns for better testing
- Mock external dependencies
- Consider edge cases
