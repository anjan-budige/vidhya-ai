from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import httpx
import os

from app.routers.auth import require_superadmin, CurrentAdmin
from app.config import get_settings

router = APIRouter()
settings = get_settings()

class ApiSettingsRequest(BaseModel):
    mistral_api_key: str = Field(..., pattern=r"^[^\n\r]+$")
    mistral_chat_model: str = Field(..., pattern=r"^[^\n\r]+$")
    mistral_embed_model: str = Field(..., pattern=r"^[^\n\r]+$")

class ValidateMistralRequest(BaseModel):
    api_key: str

class ApiSettingsResponse(BaseModel):
    mistral_api_key_masked: str
    mistral_chat_model: str
    mistral_embed_model: str

@router.get("/api", response_model=ApiSettingsResponse, status_code=status.HTTP_200_OK)
async def get_api_settings(current_admin: CurrentAdmin = Depends(require_superadmin)):
    """Get current API settings (masks the key)"""
    # Load raw from env if possible or settings
    key = settings.MISTRAL_API_KEY
    masked = f"****{key[-4:]}" if len(key) > 4 else ""
    
    return ApiSettingsResponse(
        mistral_api_key_masked=masked,
        mistral_chat_model=settings.MISTRAL_CHAT_MODEL,
        mistral_embed_model=settings.MISTRAL_EMBED_MODEL
    )

@router.put("/api", status_code=status.HTTP_200_OK)
async def update_api_settings(payload: ApiSettingsRequest, current_admin: CurrentAdmin = Depends(require_superadmin)):
    """Update API settings by rewriting the .env file"""
    env_path = ".env"
    if not os.path.exists(env_path):
        raise HTTPException(status_code=500, detail=".env file not found on the server.")
        
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        new_lines = []
        found_key = False
        found_chat = False
        found_embed = False
        
        for line in lines:
            if line.startswith("MISTRAL_API_KEY="):
                new_lines.append(f"MISTRAL_API_KEY={payload.mistral_api_key.strip()}\n")
                found_key = True
            elif line.startswith("MISTRAL_CHAT_MODEL="):
                new_lines.append(f"MISTRAL_CHAT_MODEL={payload.mistral_chat_model.strip()}\n")
                found_chat = True
            elif line.startswith("MISTRAL_EMBED_MODEL="):
                new_lines.append(f"MISTRAL_EMBED_MODEL={payload.mistral_embed_model.strip()}\n")
                found_embed = True
            else:
                new_lines.append(line)
                
        # If they weren't in the .env originally, append them
        if not found_key:
            new_lines.append(f"MISTRAL_API_KEY={payload.mistral_api_key.strip()}\n")
        if not found_chat:
            new_lines.append(f"MISTRAL_CHAT_MODEL={payload.mistral_chat_model.strip()}\n")
        if not found_embed:
            new_lines.append(f"MISTRAL_EMBED_MODEL={payload.mistral_embed_model.strip()}\n")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        return {"message": "Settings saved to .env. Please restart the Docker backend for changes to take effect."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write to .env: {str(e)}")

@router.post("/validate-mistral", status_code=status.HTTP_200_OK)
async def validate_mistral_api(payload: ValidateMistralRequest, current_admin: CurrentAdmin = Depends(require_superadmin)):
    """Validates the Mistral API key and fetches available models"""
    headers = {
        "Authorization": f"Bearer {payload.api_key}",
        "Accept": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.mistral.ai/v1/models", headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Invalid API Key or Mistral API error.")
                
            data = response.json()
            models = data.get("data", [])
            
            # Sort models to categorize them
            chat_models = [m["id"] for m in models if "embed" not in m["id"].lower() and "moderation" not in m["id"].lower()]
            embed_models = [m["id"] for m in models if "embed" in m["id"].lower()]
            
            return {
                "valid": True,
                "chat_models": chat_models,
                "embed_models": embed_models
            }
            
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to Mistral API: {str(e)}")
