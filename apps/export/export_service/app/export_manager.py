import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import uuid4
import aiofiles
from fastapi import BackgroundTasks

from app.document_generator import DocumentGenerator
from app.cv_service_client import fetch_cv_data

# Set up logging
logger = logging.getLogger("export_service.export_manager")

# Environment variables
EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")
EXPORT_RETENTION_DAYS = int(os.getenv("EXPORT_RETENTION_DAYS", "7"))
os.makedirs(EXPORT_DIR, exist_ok=True)

# In-memory store of export jobs
EXPORT_JOBS = {}

class ExportManager:
    """
    Manages the export job workflow, storage, and cleanup
    """
    
    @staticmethod
    async def create_export_job(cv_id: str, format: str, user_id: str, template_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new export job and start the background task
        
        Args:
            cv_id: The ID of the CV to export
            format: The format to export to (pdf or docx)
            user_id: The ID of the user requesting the export
            template_options: Optional template configuration options
            
        Returns:
            The created export job data
        """
        # Create job ID
        export_id = str(uuid4())
        
        # Create job record
        now = datetime.utcnow()
        
        job = {
            "id": export_id,
            "user_id": user_id,
            "cv_id": cv_id,
            "format": format.lower(),
            "template_options": template_options or {},
            "status": "pending",
            "progress": 0,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "download_url": None,
            "filepath": None,
            "error": None
        }
        
        # Store job
        EXPORT_JOBS[export_id] = job
        
        logger.info(f"Created export job {export_id} for CV {cv_id} in {format} format")
        
        return job
    
    @staticmethod
    async def process_export_job(export_id: str, token: str) -> None:
        """
        Process an export job
        
        Args:
            export_id: The ID of the export job
            token: JWT authentication token
        """
        if export_id not in EXPORT_JOBS:
            logger.error(f"Export job {export_id} not found")
            return
        
        job = EXPORT_JOBS[export_id]
        
        try:
            # Update job status
            job["status"] = "processing"
            job["updated_at"] = datetime.utcnow()
            
            # Fetch CV data
            logger.info(f"Fetching CV data for job {export_id}")
            cv_data = await fetch_cv_data(job["cv_id"], token)
            
            # Update progress
            job["progress"] = 30
            job["updated_at"] = datetime.utcnow()
            
            # Create output file path
            format = job["format"].lower()
            filename = f"{export_id}.{format}"
            filepath = os.path.join(EXPORT_DIR, filename)
            
            # Generate document
            logger.info(f"Generating {format} document for job {export_id}")
            await DocumentGenerator.generate_document(
                cv_data=cv_data,
                output_path=filepath,
                format=format,
                template_options=job["template_options"]
            )
            
            # Update job status
            job["progress"] = 100
            job["status"] = "completed"
            job["filepath"] = filepath
            job["download_url"] = f"/api/export/download/{export_id}"
            job["completed_at"] = datetime.utcnow()
            job["updated_at"] = job["completed_at"]
            
            logger.info(f"Completed export job {export_id}")
            
        except Exception as e:
            logger.error(f"Error processing export job {export_id}: {str(e)}")
            job["status"] = "failed"
            job["error"] = str(e)
            job["updated_at"] = datetime.utcnow()
    
    @staticmethod
    async def get_export_job(export_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an export job by ID
        
        Args:
            export_id: The ID of the export job
            user_id: The ID of the user requesting the job
            
        Returns:
            The export job data, or None if not found or not owned by the user
        """
        if export_id not in EXPORT_JOBS:
            return None
        
        job = EXPORT_JOBS[export_id]
        
        # Check ownership
        if job["user_id"] != user_id:
            logger.warning(f"User {user_id} attempted to access export job {export_id} owned by {job['user_id']}")
            return None
        
        return job
    
    @staticmethod
    async def get_user_export_jobs(user_id: str) -> List[Dict[str, Any]]:
        """
        Get all export jobs for a user
        
        Args:
            user_id: The ID of the user
            
        Returns:
            A list of export jobs owned by the user
        """
        return [job for job in EXPORT_JOBS.values() if job["user_id"] == user_id]
    
    @staticmethod
    async def delete_export_job(export_id: str, user_id: str) -> bool:
        """
        Delete an export job
        
        Args:
            export_id: The ID of the export job
            user_id: The ID of the user requesting deletion
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if export_id not in EXPORT_JOBS:
            return False
        
        job = EXPORT_JOBS[export_id]
        
        # Check ownership
        if job["user_id"] != user_id:
            logger.warning(f"User {user_id} attempted to delete export job {export_id} owned by {job['user_id']}")
            return False
        
        # Delete file if it exists
        if job.get("filepath") and os.path.exists(job["filepath"]):
            try:
                os.remove(job["filepath"])
                logger.info(f"Deleted export file for job {export_id}")
            except Exception as e:
                logger.error(f"Error deleting export file for job {export_id}: {str(e)}")
        
        # Delete job from store
        del EXPORT_JOBS[export_id]
        logger.info(f"Deleted export job {export_id}")
        
        return True
    
    @staticmethod
    async def cleanup_old_exports() -> None:
        """Cleanup export jobs and files older than retention period"""
        logger.info("Starting cleanup of old export jobs")
        
        retention_date = datetime.utcnow() - timedelta(days=EXPORT_RETENTION_DAYS)
        jobs_to_delete = []
        
        for export_id, job in EXPORT_JOBS.items():
            created_at = job.get("created_at", datetime.utcnow())
            
            if created_at < retention_date:
                # Delete file if it exists
                if job.get("filepath") and os.path.exists(job["filepath"]):
                    try:
                        os.remove(job["filepath"])
                        logger.info(f"Cleanup: Deleted export file for job {export_id}")
                    except Exception as e:
                        logger.error(f"Cleanup: Error deleting export file for job {export_id}: {str(e)}")
                
                jobs_to_delete.append(export_id)
        
        # Delete jobs from store
        for export_id in jobs_to_delete:
            del EXPORT_JOBS[export_id]
            logger.info(f"Cleanup: Deleted export job {export_id}")
        
        logger.info(f"Cleanup: Deleted {len(jobs_to_delete)} old export jobs")
    
    @staticmethod
    async def schedule_cleanup(background_tasks: BackgroundTasks) -> None:
        """Schedule periodic cleanup of old export jobs"""
        
        async def periodic_cleanup():
            while True:
                await asyncio.sleep(86400)  # 24 hours
                await ExportManager.cleanup_old_exports()
        
        background_tasks.add_task(periodic_cleanup) 