"""
Match Results API endpoints.

Provides endpoints for retrieving, analyzing, and exporting speed dating match results.
"""

import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_active_organizer, current_active_user
from app.database import get_async_session
from app.models import User
from app.services.match_results_service import create_match_results_service

router = APIRouter(prefix="/match-results", tags=["Match Results"])


@router.get("/events/{event_id}/statistics")
async def get_event_match_statistics(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
) -> Dict[str, Any]:
    """
    Get comprehensive match statistics for an event.
    
    Returns aggregated data including response rates, mutual matches,
    category breakdowns, and round-by-round analysis.
    
    Requires organizer permissions.
    """
    try:
        results_service = await create_match_results_service(session)
        statistics = await results_service.get_event_match_statistics(event_id)
        return statistics
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve match statistics",
        ) from e


@router.get("/events/{event_id}/mutual-matches")
async def get_mutual_matches(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """
    Get all mutual matches for an event.
    
    Returns detailed information about all matches where both attendees
    responded 'yes' to each other.
    
    Requires organizer permissions.
    """
    try:
        results_service = await create_match_results_service(session)
        mutual_matches = await results_service.get_mutual_matches_for_event(event_id)
        
        return {
            "event_id": str(event_id),
            "total_mutual_matches": len(mutual_matches),
            "mutual_matches": mutual_matches,
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve mutual matches",
        ) from e


@router.get("/events/{event_id}/export/all-matches.csv")
async def export_all_matches_csv(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """
    Export all match results for an event to CSV format.
    
    Returns a CSV file containing all matches with detailed information
    including responses, ratings, and timing data.
    
    Requires organizer permissions.
    """
    try:
        results_service = await create_match_results_service(session)
        csv_data = await results_service.export_match_results_csv(event_id)
        
        # Get CSV content
        csv_content = csv_data.getvalue()
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=event_{event_id}_all_matches.csv"
            },
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export match results",
        ) from e


@router.get("/events/{event_id}/export/mutual-matches.csv")
async def export_mutual_matches_csv(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """
    Export mutual matches for an event to CSV format.
    
    Returns a CSV file containing only the matches where both attendees
    responded 'yes', formatted for easy sharing with participants.
    
    Requires organizer permissions.
    """
    try:
        results_service = await create_match_results_service(session)
        csv_data = await results_service.export_mutual_matches_csv(event_id)
        
        # Get CSV content
        csv_content = csv_data.getvalue()
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=event_{event_id}_mutual_matches.csv"
            },
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export mutual matches",
        ) from e


@router.get("/events/{event_id}/export/attendee-summary.csv")
async def export_attendee_summary_csv(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """
    Export per-attendee match summary to CSV format.
    
    Returns a CSV file with summary statistics for each attendee,
    including response rates, mutual matches, and ratings.
    
    Requires organizer permissions.
    """
    try:
        results_service = await create_match_results_service(session)
        csv_data = await results_service.export_attendee_summary_csv(event_id)
        
        # Get CSV content
        csv_content = csv_data.getvalue()
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=event_{event_id}_attendee_summary.csv"
            },
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export attendee summary",
        ) from e


@router.get("/attendees/{attendee_id}/results")
async def get_attendee_detailed_results(
    attendee_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """
    Get detailed match results for a specific attendee.
    
    Returns comprehensive information about all matches for the attendee,
    including responses, mutual matches, and personal statistics.
    
    Attendees can only view their own results. Organizers can view any attendee's results.
    """
    # Check permissions - users can only see their own results unless they're an organizer
    if not current_user.is_organizer and not current_user.is_superuser:
        # Check if the current user is the attendee requesting their own results
        from app.models import Attendee
        from sqlalchemy import select
        
        attendee_result = await session.execute(
            select(Attendee).where(Attendee.id == attendee_id)
        )
        attendee = attendee_result.scalar_one_or_none()
        
        if not attendee or attendee.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own match results"
            )
    
    try:
        results_service = await create_match_results_service(session)
        detailed_results = await results_service.get_attendee_detailed_results(attendee_id)
        return detailed_results
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve attendee results",
        ) from e


@router.get("/events/{event_id}/export/statistics.json")
async def export_event_statistics_json(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """
    Export complete event statistics as JSON.
    
    Returns comprehensive match statistics and analysis in JSON format,
    suitable for data analysis or integration with other systems.
    
    Requires organizer permissions.
    """
    try:
        results_service = await create_match_results_service(session)
        statistics = await results_service.get_event_match_statistics(event_id)
        
        import json
        json_content = json.dumps(statistics, indent=2, default=str)
        
        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=event_{event_id}_statistics.json"
            },
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export event statistics",
        ) from e