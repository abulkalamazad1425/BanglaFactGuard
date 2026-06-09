"""
app/features/multimodal/router.py
POST /api/v1/multimodal/verify   — Submit image/video/audio for fact-check
GET  /api/v1/multimodal/{id}     — Get multimodal submission status
"""
from fastapi import APIRouter
router = APIRouter(prefix="/multimodal", tags=["Multimodal Fact-Check"])
# TODO: Implement multimodal endpoints

