# CV Management Service

This service manages CV/résumé creation, editing, and retrieval for the CandidateV application.

## Features

- CV creation and management
- Template selection and customization
- Structured CV data storage (experiences, education, skills, etc.)
- Database persistence with versioning support
- Support for both SQLite (development) and PostgreSQL (production)

## Development Guide

### Environment Setup

The service can use either SQLite (for development) or PostgreSQL (for production).

#### Environment Variables

- `DATABASE_URL`: Database connection string
- `PORT`: Server port (default: 8002)
- `JWT_SECRET`: Secret key for JWT validation
- `JWT_ALGORITHM`: Algorithm for JWT (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT expiration time
- `BASE_URL`: Base URL for the service
- `CORS_ORIGINS`: Allowed origins for CORS

### Scripts

We provide several scripts to help with development:

#### 1. Development Starter (Recommended)

This script sets up everything in one go: environment variables, database, and starts the service.

```bash
python dev_start.py
```

#### 2. Manual Setup

If you prefer manual setup:

1. Set environment variables:
   ```bash
   export DATABASE_URL=sqlite:///./cv_service.db
   export PORT=8002
   export JWT_SECRET=your-secret-key
   ```

2. Run the service:
   ```bash
   python -m uvicorn app.main:app --reload --port 8002
   ```

### Database

The service can use SQLite for development or PostgreSQL for production:

- **SQLite**: Uses `sqlite:///./cv_service.db` (default for development)
- **PostgreSQL**: Set `DATABASE_URL` to a PostgreSQL connection string

#### Database Schema

The CV Service uses the following tables:

- `cvs`: Main CV data including metadata and user information
- `templates`: CV templates with styling options
- Relation tables: `experiences`, `education`, `skills`, `languages`, `projects`, `certifications`, `references`

### API Endpoints

#### CV Management

- `GET /api/cv`: Get all CVs for the current user
- `POST /api/cv`: Create a new CV
- `GET /api/cv/{cv_id}`: Get a specific CV
- `PUT /api/cv/{cv_id}/metadata`: Update CV metadata
- `PUT /api/cv/{cv_id}/content`: Update CV content
- `DELETE /api/cv/{cv_id}`: Delete a CV

#### Templates

- `GET /api/cv/templates`: Get all templates
- `GET /api/cv/templates/{template_id}`: Get a specific template

#### Health Check

- `GET /api/health`: Check service health

## Implementation Details

### Database Compatibility

The service is designed to work with both SQLite (for development) and PostgreSQL (for production) databases. This is achieved through conditional code paths in the model definitions:

```python
# In models.py
if is_sqlite:
    # SQLite version (no UUID support)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Store JSON as strings in SQLite
    style_options = Column(String, nullable=True)
else:
    # PostgreSQL version
    from sqlalchemy.dialects.postgresql import UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    style_options = Column(JSONB, nullable=True)
```

### JSON Handling

The service automatically handles JSON serialization/deserialization based on the database:

- For SQLite, JSON fields are stored as strings and deserialized on read
- For PostgreSQL, native JSONB fields are used

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check if DATABASE_URL is set correctly
   - For SQLite, ensure the directory is writable
   - For PostgreSQL, check credentials and network access

2. **JWT Validation Errors**
   - Ensure JWT_SECRET and JWT_ALGORITHM match the Auth Service settings

### Logs

The service logs to stdout with the following format:
```
TIMESTAMP - LOGGER_NAME - LEVEL - MESSAGE
```

## Contract Validation

This service implements contract validation using JSON Schema definitions from the shared contracts, ensuring API compatibility with the frontend and other services. 