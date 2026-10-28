"""File upload endpoint."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import RejectedFileOut, UploadResponseOut, UploadedFileOut
from backend.config import get_settings
from backend.db.base import get_db
from backend.db.models import UploadedFile
from backend.parsers.pdf_parser import PDFParseError, PDFParser
from backend.utils.deduplication import sha256_bytes

router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger(__name__)


@router.post("", response_model=UploadResponseOut)
async def upload_files(
    files: list[UploadFile],
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    settings.ensure_data_dirs()
    parser = PDFParser()

    uploaded: list[UploadedFileOut] = []
    rejected: list[RejectedFileOut] = []

    for file in files:
        filename = file.filename or "upload.pdf"
        content = await file.read()
        size = len(content)

        if size > settings.max_upload_size_bytes:
            rejected.append(
                RejectedFileOut(
                    filename=filename,
                    reason=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
                )
            )
            continue

        try:
            parsed = parser.parse_bytes(content, filename)
        except PDFParseError as exc:
            rejected.append(RejectedFileOut(filename=filename, reason=str(exc)))
            continue

        content_hash = sha256_bytes(content)

        # Check for existing file with same hash
        from sqlalchemy import select
        existing = await db.execute(
            select(UploadedFile).where(UploadedFile.content_hash == content_hash)
        )
        uf = existing.scalar_one_or_none()

        if uf and uf.parsed_ok:
            logger.info("Reusing already-parsed file for hash %s", content_hash)
            uploaded.append(
                UploadedFileOut(
                    file_id=uf.id,
                    filename=filename,
                    size_bytes=size,
                    status="OK",
                )
            )
            continue

        # Save to disk
        storage_path = settings.uploads_dir / f"{content_hash}.pdf"
        storage_path.write_bytes(content)

        db_file = UploadedFile(
            original_filename=filename,
            storage_path=str(storage_path),
            content_hash=content_hash,
            file_size_bytes=size,
            parsed_ok=True,
        )
        db.add(db_file)
        await db.flush()
        await db.refresh(db_file)

        uploaded.append(
            UploadedFileOut(
                file_id=db_file.id,
                filename=filename,
                size_bytes=size,
                status="OK",
            )
        )

    return UploadResponseOut(uploaded=uploaded, rejected=rejected)
