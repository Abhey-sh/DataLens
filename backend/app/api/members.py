"""
FastAPI routes for members validation.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from loguru import logger

from app.validation.members.service import MembersValidationService
from app.schemas.validation import ValidationResponseSchema, AutoFixRequestSchema
from app.core.exceptions import (
    ValidationException,
    FileValidationException,
    BusinessRuleException,
)

router = APIRouter(prefix="/api/members", tags=["members"])

# Store service instance for state management
validation_service: MembersValidationService = None


@router.post("/validate", response_model=ValidationResponseSchema)
async def validate_members(file: UploadFile = File(...)):
    """
    Upload and validate a members CSV file.
    
    Returns validation results with all business rules and affected rows.
    """
    global validation_service
    
    logger.info(f"Received file upload: {file.filename}")
    
    if not file.filename.endswith(".csv"):
        logger.warning(f"Invalid file format: {file.filename}")
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Initialize service and validate
        validation_service = MembersValidationService()
        response = validation_service.validate(content)
        
        logger.info(f"Validation completed: {response.summary.rows_with_issues} rows with issues")
        return response
        
    except FileValidationException as e:
        logger.error(f"File validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except BusinessRuleException as e:
        logger.error(f"Business rule validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during validation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auto-fix")
async def apply_auto_fix(request: AutoFixRequestSchema):
    """
    Apply automatic fix for a specific business rule.
    """
    global validation_service
    
    if not validation_service:
        raise HTTPException(status_code=400, detail="No active validation session")
    
    try:
        validation_service.apply_auto_fix(request.rule_id)
        logger.info(f"Auto-fix applied for rule {request.rule_id}")
        return {"status": "success", "message": f"Auto-fix applied for {request.rule_id}"}
    except Exception as e:
        logger.error(f"Auto-fix failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-log")
async def get_audit_log():
    """
    Get the audit log for the current validation session.
    """
    global validation_service
    
    if not validation_service:
        raise HTTPException(status_code=400, detail="No active validation session")
    
    try:
        audit_log = validation_service.get_audit_log()
        return {"audit_log": audit_log}
    except Exception as e:
        logger.error(f"Failed to retrieve audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e))
