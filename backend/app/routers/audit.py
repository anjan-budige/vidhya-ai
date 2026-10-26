from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, desc
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_admin_or_above, get_pagination
from app.models.audit_log import AuditLog
from app.models.admin import Admin
from app.schemas.auth import CurrentAdmin
from app.schemas.base import PaginationParams
from app.schemas.admin import AuditLogResponse, PaginatedAuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("/", response_model=PaginatedAuditLogResponse, status_code=status.HTTP_200_OK)
async def list_audit_logs(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db)
):
    """
    List paginated audit logs (Admin only).
    """
    offset = (pagination.page - 1) * pagination.page_size
    
    stmt = (
        select(AuditLog, Admin.username)
        .outerjoin(Admin, AuditLog.admin_id == Admin.id)
        .order_by(desc(AuditLog.created_at))
        .offset(offset)
        .limit(pagination.page_size)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    count_stmt = select(sqlalchemy.func.count()).select_from(AuditLog)
    total_result = await db.execute(count_stmt)
    total_count = total_result.scalar() or 0
    
    response_list = []
    for log, admin_username in rows:
        response_list.append(AuditLogResponse(
            id=log.id,
            admin_id=log.admin_id,
            admin_username=admin_username,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=str(log.ip_address) if log.ip_address else None,
            created_at=log.created_at
        ))
        
    return PaginatedAuditLogResponse(
        items=response_list,
        total=total_count,
        page=pagination.page,
        page_size=pagination.page_size
    )
