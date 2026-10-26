import uuid
from datetime import datetime, timezone
from typing import List

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    get_redis_client,
    get_current_user,
    get_pagination
)
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.conversation import ConversationService
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationListResponse,
    ConversationUpdateRequest
)
from app.schemas.auth import CurrentUser
from app.schemas.base import PaginationParams
from app.schemas.message import MessageResponse

router = APIRouter(prefix="/conversations", tags=["Chat Conversations"])


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_conversation(
    payload: ConversationCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Start a new chat conversation thread.
    Automatically validates concurrent plan thread limit caps.
    """
    conv = await ConversationService.create_conversation(
        user_id=current_user.id,
        title=payload.title,
        db=db,
        redis=redis
    )
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/", response_model=List[ConversationListResponse], status_code=status.HTTP_200_OK)
async def list_conversations(
    current_user: CurrentUser = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db)
):
    """
    List paginated chat conversations for the current user.
    """
    offset = (pagination.page - 1) * pagination.page_size

    stmt = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(desc(Conversation.last_activity_at))
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    return conversations


@router.get("/{conv_id}", response_model=ConversationResponse, status_code=status.HTTP_200_OK)
async def get_conversation_details(
    conv_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve specific conversation metadata.
    """
    conv = await ConversationService.get_conversation(conv_id, db)
    
    if conv.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: unauthorized thread owner."
        )
        
    return conv


@router.get("/{conv_id}/messages", response_model=List[MessageResponse], status_code=status.HTTP_200_OK)
async def get_conversation_messages(
    conv_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve paginated messages for a specific conversation thread.
    """
    conv = await ConversationService.get_conversation(conv_id, db)
    
    if conv.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: unauthorized thread owner."
        )
        
    offset = (pagination.page - 1) * pagination.page_size
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    response_list = []
    for msg in messages:
        ref_list = msg.retrieved_chunks.get("references") if msg.retrieved_chunks else None
        
        response_list.append(
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                user_id=msg.user_id,
                role=msg.role,
                content=msg.content,
                token_count=msg.token_count,
                confidence_score=msg.confidence_score,
                was_cached=msg.was_cached,
                is_in_context=msg.is_in_context,
                is_summarized=msg.is_summarized,
                created_at=msg.created_at,
                sources=ref_list
            )
        )
    return response_list


@router.patch("/{conv_id}", response_model=ConversationResponse, status_code=status.HTTP_200_OK)
async def rename_chat_thread(
    conv_id: uuid.UUID,
    payload: ConversationUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Rename a saved conversation. Activity order is left untouched so the
    sidebar does not jump when a title is edited.
    """
    conv = await ConversationService.get_conversation(conv_id, db)

    if conv.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: unauthorized thread owner."
        )

    title = payload.title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title cannot be blank."
        )

    conv.title = title[:120]
    await db.commit()
    await db.refresh(conv)
    return conv


@router.delete("/{conv_id}", status_code=status.HTTP_200_OK)
async def delete_chat_thread(
    conv_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Delete a conversation thread completely.
    """
    conv = await ConversationService.get_conversation(conv_id, db)
    
    if conv.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied."
        )
        
    from app.models.ai_query import AIQuery
    await db.execute(delete(AIQuery).where(AIQuery.conversation_id == conv_id))
    
    from app.models.message import Message
    await db.execute(delete(Message).where(Message.conversation_id == conv_id))
    
    await db.execute(delete(Conversation).where(Conversation.id == conv_id))
    await db.commit()
    
    return {"detail": "Conversation thread deleted."}
