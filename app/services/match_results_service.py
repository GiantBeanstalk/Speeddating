"""
Match Results Service

Provides aggregation, analysis, and export functionality for speed dating match results.
"""

import csv
import io
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Attendee, Event, Match, MatchResponse, Round


class MatchResultsService:
    """Service for aggregating and exporting match results."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_event_match_statistics(self, event_id: uuid.UUID) -> Dict[str, Any]:
        """
        Get comprehensive match statistics for an event.
        
        Returns aggregated data including:
        - Total matches created
        - Response rates
        - Mutual match statistics
        - Category breakdowns
        - Round-by-round analysis
        """
        # Get event with all related data
        event_result = await self.session.execute(
            select(Event)
            .options(
                selectinload(Event.matches).selectinload(Match.attendee1),
                selectinload(Event.matches).selectinload(Match.attendee2),
                selectinload(Event.matches).selectinload(Match.round),
                selectinload(Event.rounds),
                selectinload(Event.attendees)
            )
            .where(Event.id == event_id)
        )
        event = event_result.scalar_one_or_none()
        
        if not event:
            raise ValueError(f"Event with ID {event_id} not found")

        matches = event.matches
        total_matches = len(matches)
        
        if total_matches == 0:
            return self._empty_statistics(event)

        # Basic match statistics
        mutual_matches = [m for m in matches if m.is_mutual_match]
        responded_matches = [m for m in matches if m.both_responded]
        
        # Response statistics
        total_possible_responses = total_matches * 2  # Each match has 2 potential responses
        actual_responses = sum(
            1 for match in matches 
            for response in [match.attendee1_response, match.attendee2_response]
            if response != MatchResponse.NO_RESPONSE
        )
        
        # Calculate response rates by attendee
        attendee_response_rates = await self._calculate_attendee_response_rates(matches)
        
        # Category analysis
        category_stats = await self._calculate_category_statistics(matches)
        
        # Round-by-round analysis
        round_stats = await self._calculate_round_statistics(matches)
        
        # Rating analysis
        rating_stats = await self._calculate_rating_statistics(matches)
        
        # Timing analysis
        timing_stats = await self._calculate_timing_statistics(matches)

        return {
            "event_id": str(event_id),
            "event_name": event.name,
            "event_date": event.start_time.isoformat() if event.start_time else None,
            "total_attendees": len(event.attendees),
            "total_matches": total_matches,
            "mutual_matches": len(mutual_matches),
            "matches_with_both_responses": len(responded_matches),
            "response_rate": (actual_responses / total_possible_responses) * 100 if total_possible_responses > 0 else 0,
            "mutual_match_rate": (len(mutual_matches) / total_matches) * 100,
            "success_rate": (len(mutual_matches) / len(responded_matches)) * 100 if responded_matches else 0,
            "attendee_response_rates": attendee_response_rates,
            "category_statistics": category_stats,
            "round_statistics": round_stats,
            "rating_statistics": rating_stats,
            "timing_statistics": timing_stats,
            "generated_at": datetime.now(UTC).isoformat()
        }

    async def get_mutual_matches_for_event(self, event_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Get all mutual matches for an event with detailed information."""
        matches_result = await self.session.execute(
            select(Match)
            .options(
                selectinload(Match.attendee1),
                selectinload(Match.attendee2),
                selectinload(Match.round)
            )
            .where(
                Match.event_id == event_id,
                Match.attendee1_response == MatchResponse.YES,
                Match.attendee2_response == MatchResponse.YES
            )
        )
        
        mutual_matches = matches_result.scalars().all()
        
        return [
            {
                "match_id": str(match.id),
                "round_number": match.round.round_number if match.round else None,
                "table_number": match.table_number,
                "attendee1": {
                    "id": str(match.attendee1.id),
                    "display_name": match.attendee1.display_name,
                    "category": match.attendee1.category.value,
                    "age": match.attendee1.age,
                    "rating_given": match.attendee1_rating,
                    "response_time": match.attendee1_response_time.isoformat() if match.attendee1_response_time else None,
                    "has_notes": bool(match.attendee1_notes)
                },
                "attendee2": {
                    "id": str(match.attendee2.id),
                    "display_name": match.attendee2.display_name,
                    "category": match.attendee2.category.value,
                    "age": match.attendee2.age,
                    "rating_given": match.attendee2_rating,
                    "response_time": match.attendee2_response_time.isoformat() if match.attendee2_response_time else None,
                    "has_notes": bool(match.attendee2_notes)
                },
                "created_at": match.created_at.isoformat()
            }
            for match in mutual_matches
        ]

    async def export_match_results_csv(self, event_id: uuid.UUID) -> io.StringIO:
        """Export match results to CSV format."""
        matches_result = await self.session.execute(
            select(Match)
            .options(
                selectinload(Match.attendee1),
                selectinload(Match.attendee2),
                selectinload(Match.round)
            )
            .where(Match.event_id == event_id)
        )
        
        matches = matches_result.scalars().all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Match ID', 'Event ID', 'Round Number', 'Table Number',
            'Attendee1 ID', 'Attendee1 Name', 'Attendee1 Category', 'Attendee1 Age',
            'Attendee1 Response', 'Attendee1 Rating', 'Attendee1 Response Time',
            'Attendee2 ID', 'Attendee2 Name', 'Attendee2 Category', 'Attendee2 Age',
            'Attendee2 Response', 'Attendee2 Rating', 'Attendee2 Response Time',
            'Is Mutual Match', 'Both Responded', 'Created At'
        ])
        
        # Write data rows
        for match in matches:
            writer.writerow([
                str(match.id),
                str(match.event_id),
                match.round.round_number if match.round else '',
                match.table_number or '',
                str(match.attendee1.id),
                match.attendee1.display_name,
                match.attendee1.category.value,
                match.attendee1.age or '',
                match.attendee1_response.value,
                match.attendee1_rating or '',
                match.attendee1_response_time.isoformat() if match.attendee1_response_time else '',
                str(match.attendee2.id),
                match.attendee2.display_name,
                match.attendee2.category.value,
                match.attendee2.age or '',
                match.attendee2_response.value,
                match.attendee2_rating or '',
                match.attendee2_response_time.isoformat() if match.attendee2_response_time else '',
                match.is_mutual_match,
                match.both_responded,
                match.created_at.isoformat()
            ])
        
        output.seek(0)
        return output

    async def export_mutual_matches_csv(self, event_id: uuid.UUID) -> io.StringIO:
        """Export only mutual matches to CSV format."""
        mutual_matches = await self.get_mutual_matches_for_event(event_id)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Match ID', 'Round Number', 'Table Number',
            'Person 1 Name', 'Person 1 Category', 'Person 1 Age', 'Person 1 Rating Given',
            'Person 2 Name', 'Person 2 Category', 'Person 2 Age', 'Person 2 Rating Given',
            'Match Created At'
        ])
        
        # Write data rows
        for match in mutual_matches:
            writer.writerow([
                match['match_id'],
                match['round_number'] or '',
                match['table_number'] or '',
                match['attendee1']['display_name'],
                match['attendee1']['category'],
                match['attendee1']['age'] or '',
                match['attendee1']['rating_given'] or '',
                match['attendee2']['display_name'],
                match['attendee2']['category'],
                match['attendee2']['age'] or '',
                match['attendee2']['rating_given'] or '',
                match['created_at']
            ])
        
        output.seek(0)
        return output

    async def export_attendee_summary_csv(self, event_id: uuid.UUID) -> io.StringIO:
        """Export per-attendee match summary to CSV."""
        # Get all attendees for the event
        attendees_result = await self.session.execute(
            select(Attendee)
            .where(Attendee.event_id == event_id)
        )
        attendees = attendees_result.scalars().all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Attendee ID', 'Display Name', 'Category', 'Age',
            'Total Matches', 'Responses Given', 'Response Rate (%)',
            'Yes Responses Given', 'No Responses Given',
            'Mutual Matches', 'Success Rate (%)',
            'Average Rating Given', 'Average Rating Received'
        ])
        
        # Calculate statistics for each attendee
        for attendee in attendees:
            stats = await self._get_attendee_match_stats(attendee.id)
            
            writer.writerow([
                str(attendee.id),
                attendee.display_name,
                attendee.category.value,
                attendee.age or '',
                stats['total_matches'],
                stats['responses_given'],
                round(stats['response_rate'], 1),
                stats['yes_responses'],
                stats['no_responses'],
                stats['mutual_matches'],
                round(stats['success_rate'], 1),
                round(stats['avg_rating_given'], 1) if stats['avg_rating_given'] else '',
                round(stats['avg_rating_received'], 1) if stats['avg_rating_received'] else ''
            ])
        
        output.seek(0)
        return output

    async def get_attendee_detailed_results(self, attendee_id: uuid.UUID) -> Dict[str, Any]:
        """Get detailed match results for a specific attendee."""
        # Get attendee
        attendee_result = await self.session.execute(
            select(Attendee).where(Attendee.id == attendee_id)
        )
        attendee = attendee_result.scalar_one_or_none()
        
        if not attendee:
            raise ValueError(f"Attendee with ID {attendee_id} not found")

        # Get all matches for this attendee
        matches_result = await self.session.execute(
            select(Match)
            .options(
                selectinload(Match.attendee1),
                selectinload(Match.attendee2),
                selectinload(Match.round)
            )
            .where(
                (Match.attendee1_id == attendee_id) |
                (Match.attendee2_id == attendee_id)
            )
        )
        matches = matches_result.scalars().all()

        # Process matches
        match_details = []
        for match in matches:
            is_attendee1 = match.attendee1_id == attendee_id
            other_attendee = match.attendee2 if is_attendee1 else match.attendee1
            my_response = match.attendee1_response if is_attendee1 else match.attendee2_response
            other_response = match.attendee2_response if is_attendee1 else match.attendee1_response
            my_rating = match.attendee1_rating if is_attendee1 else match.attendee2_rating
            other_rating = match.attendee2_rating if is_attendee1 else match.attendee1_rating
            
            match_details.append({
                "match_id": str(match.id),
                "round_number": match.round.round_number if match.round else None,
                "table_number": match.table_number,
                "other_person": {
                    "id": str(other_attendee.id),
                    "display_name": other_attendee.display_name,
                    "category": other_attendee.category.value,
                    "age": other_attendee.age
                },
                "my_response": my_response.value,
                "their_response": other_response.value,
                "is_mutual_match": match.is_mutual_match,
                "my_rating_given": my_rating,
                "rating_received": other_rating,
                "created_at": match.created_at.isoformat()
            })

        # Calculate summary statistics
        stats = await self._get_attendee_match_stats(attendee_id)

        return {
            "attendee": {
                "id": str(attendee.id),
                "display_name": attendee.display_name,
                "category": attendee.category.value,
                "age": attendee.age
            },
            "statistics": stats,
            "matches": match_details
        }

    # Private helper methods
    
    def _empty_statistics(self, event: Event) -> Dict[str, Any]:
        """Return empty statistics structure when no matches exist."""
        return {
            "event_id": str(event.id),
            "event_name": event.name,
            "event_date": event.start_time.isoformat() if event.start_time else None,
            "total_attendees": len(event.attendees) if event.attendees else 0,
            "total_matches": 0,
            "mutual_matches": 0,
            "matches_with_both_responses": 0,
            "response_rate": 0,
            "mutual_match_rate": 0,
            "success_rate": 0,
            "attendee_response_rates": [],
            "category_statistics": {},
            "round_statistics": [],
            "rating_statistics": {},
            "timing_statistics": {},
            "generated_at": datetime.now(UTC).isoformat()
        }

    async def _calculate_attendee_response_rates(self, matches: List[Match]) -> List[Dict[str, Any]]:
        """Calculate response rates for each attendee."""
        attendee_stats = {}
        
        for match in matches:
            # Track stats for attendee 1
            if match.attendee1_id not in attendee_stats:
                attendee_stats[match.attendee1_id] = {
                    "name": match.attendee1.display_name,
                    "category": match.attendee1.category.value,
                    "total_matches": 0,
                    "responses_given": 0,
                    "yes_responses": 0
                }
            
            attendee_stats[match.attendee1_id]["total_matches"] += 1
            if match.attendee1_response != MatchResponse.NO_RESPONSE:
                attendee_stats[match.attendee1_id]["responses_given"] += 1
                if match.attendee1_response == MatchResponse.YES:
                    attendee_stats[match.attendee1_id]["yes_responses"] += 1
            
            # Track stats for attendee 2
            if match.attendee2_id not in attendee_stats:
                attendee_stats[match.attendee2_id] = {
                    "name": match.attendee2.display_name,
                    "category": match.attendee2.category.value,
                    "total_matches": 0,
                    "responses_given": 0,
                    "yes_responses": 0
                }
            
            attendee_stats[match.attendee2_id]["total_matches"] += 1
            if match.attendee2_response != MatchResponse.NO_RESPONSE:
                attendee_stats[match.attendee2_id]["responses_given"] += 1
                if match.attendee2_response == MatchResponse.YES:
                    attendee_stats[match.attendee2_id]["yes_responses"] += 1
        
        # Calculate rates
        result = []
        for attendee_id, stats in attendee_stats.items():
            response_rate = (stats["responses_given"] / stats["total_matches"]) * 100 if stats["total_matches"] > 0 else 0
            yes_rate = (stats["yes_responses"] / stats["responses_given"]) * 100 if stats["responses_given"] > 0 else 0
            
            result.append({
                "attendee_id": str(attendee_id),
                "name": stats["name"],
                "category": stats["category"],
                "total_matches": stats["total_matches"],
                "response_rate": response_rate,
                "yes_rate": yes_rate,
                "responses_given": stats["responses_given"],
                "yes_responses": stats["yes_responses"]
            })
        
        return sorted(result, key=lambda x: x["response_rate"], reverse=True)

    async def _calculate_category_statistics(self, matches: List[Match]) -> Dict[str, Any]:
        """Calculate statistics broken down by attendee categories."""
        category_pairs = {}
        
        for match in matches:
            cat1 = match.attendee1.category.value
            cat2 = match.attendee2.category.value
            
            # Create consistent pair key (alphabetical order)
            pair_key = f"{min(cat1, cat2)}-{max(cat1, cat2)}"
            
            if pair_key not in category_pairs:
                category_pairs[pair_key] = {
                    "total_matches": 0,
                    "mutual_matches": 0,
                    "both_responded": 0
                }
            
            category_pairs[pair_key]["total_matches"] += 1
            if match.is_mutual_match:
                category_pairs[pair_key]["mutual_matches"] += 1
            if match.both_responded:
                category_pairs[pair_key]["both_responded"] += 1
        
        # Calculate rates
        for pair_stats in category_pairs.values():
            pair_stats["mutual_match_rate"] = (
                (pair_stats["mutual_matches"] / pair_stats["total_matches"]) * 100
                if pair_stats["total_matches"] > 0 else 0
            )
            pair_stats["response_rate"] = (
                (pair_stats["both_responded"] / pair_stats["total_matches"]) * 100
                if pair_stats["total_matches"] > 0 else 0
            )
        
        return category_pairs

    async def _calculate_round_statistics(self, matches: List[Match]) -> List[Dict[str, Any]]:
        """Calculate statistics for each round."""
        round_stats = {}
        
        for match in matches:
            round_num = match.round.round_number if match.round else "Unknown"
            
            if round_num not in round_stats:
                round_stats[round_num] = {
                    "round_number": round_num,
                    "total_matches": 0,
                    "mutual_matches": 0,
                    "both_responded": 0
                }
            
            round_stats[round_num]["total_matches"] += 1
            if match.is_mutual_match:
                round_stats[round_num]["mutual_matches"] += 1
            if match.both_responded:
                round_stats[round_num]["both_responded"] += 1
        
        # Calculate rates and return as sorted list
        result = []
        for stats in round_stats.values():
            stats["mutual_match_rate"] = (
                (stats["mutual_matches"] / stats["total_matches"]) * 100
                if stats["total_matches"] > 0 else 0
            )
            stats["response_rate"] = (
                (stats["both_responded"] / stats["total_matches"]) * 100
                if stats["total_matches"] > 0 else 0
            )
            result.append(stats)
        
        # Sort by round number, putting "Unknown" last
        return sorted(result, key=lambda x: (x["round_number"] == "Unknown", x["round_number"]))

    async def _calculate_rating_statistics(self, matches: List[Match]) -> Dict[str, Any]:
        """Calculate rating statistics."""
        ratings = []
        
        for match in matches:
            if match.attendee1_rating:
                ratings.append(match.attendee1_rating)
            if match.attendee2_rating:
                ratings.append(match.attendee2_rating)
        
        if not ratings:
            return {
                "total_ratings": 0,
                "average_rating": 0,
                "rating_distribution": {}
            }
        
        # Calculate distribution
        rating_dist = {}
        for rating in ratings:
            rating_dist[rating] = rating_dist.get(rating, 0) + 1
        
        return {
            "total_ratings": len(ratings),
            "average_rating": sum(ratings) / len(ratings),
            "rating_distribution": rating_dist
        }

    async def _calculate_timing_statistics(self, matches: List[Match]) -> Dict[str, Any]:
        """Calculate response timing statistics."""
        response_times = []
        
        for match in matches:
            if match.attendee1_response_time and match.created_at:
                delta = match.attendee1_response_time - match.created_at
                response_times.append(delta.total_seconds())
            
            if match.attendee2_response_time and match.created_at:
                delta = match.attendee2_response_time - match.created_at
                response_times.append(delta.total_seconds())
        
        if not response_times:
            return {
                "total_responses": 0,
                "average_response_time_seconds": 0,
                "fastest_response_seconds": 0,
                "slowest_response_seconds": 0
            }
        
        return {
            "total_responses": len(response_times),
            "average_response_time_seconds": sum(response_times) / len(response_times),
            "fastest_response_seconds": min(response_times),
            "slowest_response_seconds": max(response_times)
        }

    async def _get_attendee_match_stats(self, attendee_id: uuid.UUID) -> Dict[str, Any]:
        """Get detailed match statistics for a specific attendee."""
        matches_result = await self.session.execute(
            select(Match)
            .where(
                (Match.attendee1_id == attendee_id) |
                (Match.attendee2_id == attendee_id)
            )
        )
        matches = matches_result.scalars().all()
        
        total_matches = len(matches)
        responses_given = 0
        yes_responses = 0
        no_responses = 0
        mutual_matches = 0
        ratings_given = []
        ratings_received = []
        
        for match in matches:
            is_attendee1 = match.attendee1_id == attendee_id
            
            # Count responses given
            my_response = match.attendee1_response if is_attendee1 else match.attendee2_response
            if my_response != MatchResponse.NO_RESPONSE:
                responses_given += 1
                if my_response == MatchResponse.YES:
                    yes_responses += 1
                else:
                    no_responses += 1
            
            # Count mutual matches
            if match.is_mutual_match:
                mutual_matches += 1
            
            # Collect ratings
            my_rating = match.attendee1_rating if is_attendee1 else match.attendee2_rating
            other_rating = match.attendee2_rating if is_attendee1 else match.attendee1_rating
            
            if my_rating:
                ratings_given.append(my_rating)
            if other_rating:
                ratings_received.append(other_rating)
        
        response_rate = (responses_given / total_matches) * 100 if total_matches > 0 else 0
        success_rate = (mutual_matches / responses_given) * 100 if responses_given > 0 else 0
        avg_rating_given = sum(ratings_given) / len(ratings_given) if ratings_given else None
        avg_rating_received = sum(ratings_received) / len(ratings_received) if ratings_received else None
        
        return {
            "total_matches": total_matches,
            "responses_given": responses_given,
            "response_rate": response_rate,
            "yes_responses": yes_responses,
            "no_responses": no_responses,
            "mutual_matches": mutual_matches,
            "success_rate": success_rate,
            "avg_rating_given": avg_rating_given,
            "avg_rating_received": avg_rating_received,
            "ratings_given_count": len(ratings_given),
            "ratings_received_count": len(ratings_received)
        }


async def create_match_results_service(session: AsyncSession) -> MatchResultsService:
    """Factory function to create a MatchResultsService instance."""
    return MatchResultsService(session)