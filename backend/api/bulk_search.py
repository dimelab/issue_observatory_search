"""Bulk search API endpoints for CSV uploads."""
import io
import logging
import pandas as pd
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models.user import User
from backend.models.bulk_search import BulkSearchUpload, BulkSearchRow
from backend.utils.dependencies import CurrentUser
from backend.schemas.advanced_search import (
    BulkSearchValidationResponse,
    BulkSearchExecuteRequest,
    BulkSearchStatusResponse,
)
from backend.tasks.advanced_search_tasks import bulk_search_task
from celery.result import AsyncResult

router = APIRouter(prefix="/bulk-search", tags=["bulk-search"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=BulkSearchValidationResponse)
async def upload_bulk_search_csv(
    file: UploadFile = File(...),
    validate_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Upload and validate a bulk search CSV file.

    Expected CSV format:
    query,framing,language,max_results,date_from,date_to,tld_filter,search_engine

    Args:
        file: CSV file upload
        validate_only: If True, only validate without storing
        db: Database session
        current_user: Current user

    Returns:
        Validation response with errors if any
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Read CSV
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))

        # Validate required columns
        required_columns = ["query"]
        optional_columns = [
            "framing",
            "language",
            "max_results",
            "date_from",
            "date_to",
            "tld_filter",
            "search_engine",
        ]

        missing_required = set(required_columns) - set(df.columns)
        if missing_required:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_required)}",
            )

        # Validate rows
        validation_errors = {}
        valid_rows = 0
        invalid_rows = 0

        for idx, row in df.iterrows():
            row_errors = []

            # Validate query
            if pd.isna(row.get("query")) or not str(row.get("query")).strip():
                row_errors.append("Query is required")

            # Validate max_results
            if "max_results" in row and not pd.isna(row["max_results"]):
                try:
                    max_res = int(row["max_results"])
                    if max_res < 1 or max_res > 100:
                        row_errors.append("max_results must be between 1 and 100")
                except (ValueError, TypeError):
                    row_errors.append("max_results must be a number")

            # Validate search_engine
            if "search_engine" in row and not pd.isna(row["search_engine"]):
                engine = str(row["search_engine"]).lower()
                valid_engines = ["google_custom", "serper", "serpapi_google"]
                if engine not in valid_engines:
                    row_errors.append(
                        f"search_engine must be one of: {', '.join(valid_engines)}"
                    )

            # Validate TLD filter format
            if "tld_filter" in row and not pd.isna(row["tld_filter"]):
                tld_filter = str(row["tld_filter"])
                tlds = tld_filter.split("|")
                for tld in tlds:
                    if not tld.startswith("."):
                        row_errors.append(
                            f"TLD '{tld}' must start with a dot (e.g., '.dk')"
                        )

            if row_errors:
                validation_errors[f"row_{idx + 2}"] = row_errors  # +2 for 1-indexed + header
                invalid_rows += 1
            else:
                valid_rows += 1

        # Determine validation status
        if invalid_rows > 0:
            validation_status = "invalid"
        else:
            validation_status = "valid"

        # Store upload record
        upload = BulkSearchUpload(
            user_id=current_user.id,
            filename=file.filename,
            row_count=len(df),
            validation_status=validation_status,
            validation_errors=validation_errors if validation_errors else None,
        )
        db.add(upload)
        await db.flush()

        # Store rows if valid and not validate_only
        if validation_status == "valid" and not validate_only:
            for idx, row in df.iterrows():
                # Parse row data
                query_data = {
                    "query": str(row["query"]).strip(),
                    "framing": str(row.get("framing", "neutral")).strip() if "framing" in row else "neutral",
                    "language": str(row.get("language", "en")).strip() if "language" in row else "en",
                    "max_results": int(row.get("max_results", 10)) if "max_results" in row and not pd.isna(row["max_results"]) else 10,
                    "search_engine": str(row.get("search_engine", "google_custom")).strip().lower() if "search_engine" in row else "google_custom",
                }

                # Parse date fields
                if "date_from" in row and not pd.isna(row["date_from"]):
                    query_data["date_from"] = str(row["date_from"])
                if "date_to" in row and not pd.isna(row["date_to"]):
                    query_data["date_to"] = str(row["date_to"])

                # Parse TLD filter
                if "tld_filter" in row and not pd.isna(row["tld_filter"]):
                    query_data["tld_filter"] = str(row["tld_filter"]).split("|")

                bulk_row = BulkSearchRow(
                    upload_id=upload.id,
                    row_number=idx + 1,
                    query_data=query_data,
                    status="pending",
                )
                db.add(bulk_row)

        await db.commit()
        await db.refresh(upload)

        logger.info(
            f"Uploaded bulk search CSV: {file.filename} "
            f"({valid_rows} valid, {invalid_rows} invalid)"
        )

        return BulkSearchValidationResponse(
            upload_id=upload.id,
            filename=upload.filename,
            row_count=upload.row_count,
            validation_status=validation_status,
            validation_errors=validation_errors if validation_errors else None,
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
        )

    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    except pd.errors.ParserError as e:
        raise HTTPException(status_code=400, detail=f"CSV parsing error: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing bulk search upload: {e}")
        raise HTTPException(status_code=500, detail=f"Upload processing error: {str(e)}")


@router.post("/execute/{upload_id}")
async def execute_bulk_search(
    upload_id: int,
    request: BulkSearchExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Execute a validated bulk search upload.

    Args:
        upload_id: Upload ID
        request: Execution parameters
        db: Database session
        current_user: Current user

    Returns:
        Task ID and status URL
    """
    # Get upload
    result = await db.execute(
        select(BulkSearchUpload).where(
            BulkSearchUpload.id == upload_id,
            BulkSearchUpload.user_id == current_user.id,
        )
    )
    upload = result.scalar_one_or_none()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if upload.validation_status != "valid":
        raise HTTPException(
            status_code=400,
            detail="Cannot execute invalid upload. Fix errors and re-upload.",
        )

    if upload.task_id:
        raise HTTPException(
            status_code=400,
            detail=f"Upload already executing (task: {upload.task_id})",
        )

    # Start Celery task
    task = bulk_search_task.delay(
        upload_id=upload_id,
        user_id=current_user.id,
        session_name=request.session_name,
        description=request.description,
    )

    # Update upload with task ID
    upload.task_id = task.id
    await db.commit()

    logger.info(f"Started bulk search execution: task {task.id}")

    return {
        "upload_id": upload_id,
        "task_id": task.id,
        "status": "processing",
        "message": "Bulk search execution started",
        "status_url": f"/api/bulk-search/status/{task.id}",
    }


@router.get("/status/{task_id}", response_model=BulkSearchStatusResponse)
async def get_bulk_search_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Get status of a bulk search task.

    Args:
        task_id: Celery task ID
        db: Database session
        current_user: Current user

    Returns:
        Task status and progress
    """
    # Get upload by task ID
    result = await db.execute(
        select(BulkSearchUpload).where(
            BulkSearchUpload.task_id == task_id,
            BulkSearchUpload.user_id == current_user.id,
        )
    )
    upload = result.scalar_one_or_none()

    if not upload:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get task result
    task_result = AsyncResult(task_id)

    # Count completed and failed rows
    rows_result = await db.execute(
        select(BulkSearchRow).where(BulkSearchRow.upload_id == upload.id)
    )
    rows = list(rows_result.scalars().all())

    completed_rows = sum(1 for r in rows if r.status == "completed")
    failed_rows = sum(1 for r in rows if r.status == "failed")
    total_rows = len(rows)

    # Calculate progress
    progress_percentage = (
        ((completed_rows + failed_rows) / total_rows * 100) if total_rows > 0 else 0
    )

    # Determine status
    if task_result.state == "PENDING":
        status = "pending"
    elif task_result.state == "PROGRESS":
        status = "processing"
    elif task_result.state == "SUCCESS":
        status = "completed"
    elif task_result.state == "FAILURE":
        status = "failed"
    else:
        status = task_result.state.lower()

    return BulkSearchStatusResponse(
        upload_id=upload.id,
        task_id=task_id,
        status=status,
        total_rows=total_rows,
        completed_rows=completed_rows,
        failed_rows=failed_rows,
        progress_percentage=round(progress_percentage, 2),
    )


@router.get("/results/{upload_id}")
async def get_bulk_search_results(
    upload_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Get results summary for a completed bulk search.

    Args:
        upload_id: Upload ID
        db: Database session
        current_user: Current user

    Returns:
        Results summary
    """
    # Get upload
    result = await db.execute(
        select(BulkSearchUpload).where(
            BulkSearchUpload.id == upload_id,
            BulkSearchUpload.user_id == current_user.id,
        )
    )
    upload = result.scalar_one_or_none()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Get rows
    rows_result = await db.execute(
        select(BulkSearchRow).where(BulkSearchRow.upload_id == upload_id)
    )
    rows = list(rows_result.scalars().all())

    # Summarize results
    total = len(rows)
    completed = sum(1 for r in rows if r.status == "completed")
    failed = sum(1 for r in rows if r.status == "failed")
    pending = sum(1 for r in rows if r.status == "pending")

    # Get failed row details
    failed_rows = [
        {
            "row_number": r.row_number,
            "query": r.query_data.get("query"),
            "error": r.error_message,
        }
        for r in rows
        if r.status == "failed"
    ]

    return {
        "upload_id": upload_id,
        "session_id": upload.session_id,
        "filename": upload.filename,
        "total_rows": total,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "failed_rows": failed_rows[:20],  # Limit to first 20
        "executed_at": upload.executed_at,
        "completed_at": upload.completed_at,
    }
