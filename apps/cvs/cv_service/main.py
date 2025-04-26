import os
import logging
import sys
import uvicorn
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("cv_service")

# Import app from our module
from app.main import app

# Try to import contract validation if available
try:
    from shared.contracts import add_contract_validation
    # Add contract validation
    add_contract_validation(app, service_name="cv_service", contract_version="1.0.0")
    logger.info("Contract validation added")
except ImportError:
    logger.warning("Contract validation not available - running without validation")

# Load OpenAPI spec from file (if available)
@app.on_event("startup")
async def startup_event():
    try:
        # Try to generate OpenAPI schema from contract
        try:
            from shared.contracts.validator import ContractValidator
            validator = ContractValidator("cv_service")
            openapi_schema = validator.generate_openapi_schema()
            if openapi_schema:
                app.openapi_schema = openapi_schema
                logger.info("Generated OpenAPI schema from contract")
                return
        except (ImportError, Exception) as e:
            logger.warning(f"Could not generate OpenAPI schema from contract: {str(e)}")
        
        # Load custom OpenAPI spec from YAML file
        openapi_yaml_path = os.path.join(os.path.dirname(__file__), "openapi.yaml")
        if os.path.exists(openapi_yaml_path):
            with open(openapi_yaml_path) as f:
                openapi_schema = yaml.safe_load(f)
                app.openapi_schema = openapi_schema
                logger.info("Loaded OpenAPI schema from file")
        else:
            logger.info("No custom OpenAPI schema found, using auto-generated")
    except Exception as e:
        logger.error(f"Error loading OpenAPI schema: {str(e)}")

# Replace FastAPI's default OpenAPI with our custom one
def custom_openapi():
    if hasattr(app, 'openapi_schema'):
        return app.openapi_schema
    return app.openapi()

app.openapi = custom_openapi

# Serve OpenAPI UI
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - ReDoc",
    )

# Get OpenAPI schema
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_schema():
    return app.openapi()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8002"))
    logger.info(f"Starting CV Management Service on port {port}")
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port,
        reload=True
    ) 