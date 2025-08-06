"""
Matching Algorithm Service

Implements category-aware matching with reciprocal preferences for speed dating events.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Attendee,
    AttendeeCategory,
    Match,
    MatchResponse,
    Round,
)


class MatchingService:
    """Service for creating matches between attendees based on categories and preferences."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_round_matches(self, round_id: uuid.UUID) -> list[Match]:
        """Create all matches for a given round using category-aware algorithm."""

        # Get round and event information
        round_result = await self.session.execute(
            select(Round).options(selectinload(Round.event)).where(Round.id == round_id)
        )
        round_obj = round_result.scalar_one_or_none()

        if not round_obj:
            raise ValueError("Round not found")

        # Get all checked-in attendees for the event
        attendees_result = await self.session.execute(
            select(Attendee).where(
                Attendee.event_id == round_obj.event_id,
                Attendee.checked_in,
                Attendee.registration_confirmed,
            )
        )
        attendees = list(attendees_result.scalars())

        # Group attendees by category
        attendees_by_category = self._group_by_category(attendees)

        # Calculate capacity limits based on reciprocal preferences
        capacity_limits = self._calculate_capacity_limits(attendees_by_category)

        # Apply capacity constraints
        limited_attendees = self._apply_capacity_limits(
            attendees_by_category, capacity_limits
        )

        # Generate optimal pairings
        pairings = self._generate_optimal_pairings(limited_attendees)

        # Create match records
        matches = []
        for table_number, (attendee1, attendee2) in enumerate(pairings, 1):
            match = Match(
                event_id=round_obj.event_id,
                round_id=round_id,
                attendee1_id=attendee1.id,
                attendee2_id=attendee2.id,
                table_number=table_number,
            )
            matches.append(match)
            self.session.add(match)

        await self.session.commit()
        return matches

    def _group_by_category(
        self, attendees: list[Attendee]
    ) -> dict[AttendeeCategory, list[Attendee]]:
        """Group attendees by their categories."""
        groups = {
            AttendeeCategory.TOP_MALE: [],
            AttendeeCategory.TOP_FEMALE: [],
            AttendeeCategory.BOTTOM_MALE: [],
            AttendeeCategory.BOTTOM_FEMALE: [],
        }

        for attendee in attendees:
            groups[attendee.category].append(attendee)

        return groups

    def _calculate_capacity_limits(
        self, attendees_by_category: dict[AttendeeCategory, list[Attendee]]
    ) -> dict[AttendeeCategory, int]:
        """Calculate capacity limits based on reciprocal matching preferences."""

        # Get counts for each category
        counts = {
            category: len(attendees)
            for category, attendees in attendees_by_category.items()
        }

        # Calculate reciprocal pair limits
        reciprocal_limits = {
            # Top Male can match with Top Female and Bottom Female
            AttendeeCategory.TOP_MALE: min(
                counts[AttendeeCategory.TOP_FEMALE]
                + counts[AttendeeCategory.BOTTOM_FEMALE],
                counts[AttendeeCategory.TOP_MALE],
            ),
            # Top Female can match with Top Male and Bottom Male
            AttendeeCategory.TOP_FEMALE: min(
                counts[AttendeeCategory.TOP_MALE]
                + counts[AttendeeCategory.BOTTOM_MALE],
                counts[AttendeeCategory.TOP_FEMALE],
            ),
            # Bottom Male can match with Top Female and Bottom Female
            AttendeeCategory.BOTTOM_MALE: min(
                counts[AttendeeCategory.TOP_FEMALE]
                + counts[AttendeeCategory.BOTTOM_FEMALE],
                counts[AttendeeCategory.BOTTOM_MALE],
            ),
            # Bottom Female can match with Top Male and Bottom Male
            AttendeeCategory.BOTTOM_FEMALE: min(
                counts[AttendeeCategory.TOP_MALE]
                + counts[AttendeeCategory.BOTTOM_MALE],
                counts[AttendeeCategory.BOTTOM_FEMALE],
            ),
        }

        # Find the most constraining reciprocal group
        # This ensures we don't exceed the smallest matching group
        min_reciprocal_capacity = min(reciprocal_limits.values())

        # Apply the minimum constraint to all categories
        return {
            category: min(count, min_reciprocal_capacity)
            for category, count in counts.items()
        }

    def _apply_capacity_limits(
        self,
        attendees_by_category: dict[AttendeeCategory, list[Attendee]],
        capacity_limits: dict[AttendeeCategory, int],
    ) -> dict[AttendeeCategory, list[Attendee]]:
        """Apply capacity limits to attendee groups."""

        limited_groups = {}

        for category, attendees in attendees_by_category.items():
            limit = capacity_limits[category]

            if len(attendees) <= limit:
                limited_groups[category] = attendees
            else:
                # Use registration order for fairness (first come, first served)
                sorted_attendees = sorted(attendees, key=lambda a: a.registered_at)
                limited_groups[category] = sorted_attendees[:limit]

        return limited_groups

    def _generate_optimal_pairings(
        self, attendees_by_category: dict[AttendeeCategory, list[Attendee]]
    ) -> list[tuple[Attendee, Attendee]]:
        """Generate optimal pairings based on reciprocal preferences."""

        pairings = []

        # Create working copies to track availability
        available = {
            category: attendees.copy()
            for category, attendees in attendees_by_category.items()
        }

        # Priority pairing order based on reciprocal interest strength
        pairing_strategies = [
            # Strategy 1: Top Male with Top Female (highest reciprocal interest)
            (AttendeeCategory.TOP_MALE, AttendeeCategory.TOP_FEMALE),
            # Strategy 2: Bottom Male with Bottom Female (highest reciprocal interest)
            (AttendeeCategory.BOTTOM_MALE, AttendeeCategory.BOTTOM_FEMALE),
            # Strategy 3: Top Male with Bottom Female (moderate reciprocal interest)
            (AttendeeCategory.TOP_MALE, AttendeeCategory.BOTTOM_FEMALE),
            # Strategy 4: Bottom Male with Top Female (moderate reciprocal interest)
            (AttendeeCategory.BOTTOM_MALE, AttendeeCategory.TOP_FEMALE),
        ]

        # Apply each strategy in order
        for category1, category2 in pairing_strategies:
            group1 = available[category1]
            group2 = available[category2]

            # Pair as many as possible from these categories
            pairs_count = min(len(group1), len(group2))

            for _i in range(pairs_count):
                attendee1 = group1.pop(0)
                attendee2 = group2.pop(0)
                pairings.append((attendee1, attendee2))

        return pairings

    async def get_round_statistics(self, round_id: uuid.UUID) -> dict:
        """Get statistics for a round's matches."""

        matches_result = await self.session.execute(
            select(Match)
            .options(selectinload(Match.attendee1), selectinload(Match.attendee2))
            .where(Match.round_id == round_id)
        )
        matches = list(matches_result.scalars())

        if not matches:
            return {
                "total_matches": 0,
                "completed_responses": 0,
                "mutual_matches": 0,
                "category_distribution": {},
                "response_rate": 0.0,
            }

        # Calculate statistics
        total_matches = len(matches)
        completed_responses = sum(1 for match in matches if match.both_responded)
        mutual_matches = sum(1 for match in matches if match.is_mutual_match)

        # Category distribution
        category_pairs = {}
        for match in matches:
            pair_key = (
                f"{match.attendee1.category.value} + {match.attendee2.category.value}"
            )
            category_pairs[pair_key] = category_pairs.get(pair_key, 0) + 1

        response_rate = (
            (completed_responses / total_matches * 100) if total_matches > 0 else 0
        )

        return {
            "total_matches": total_matches,
            "completed_responses": completed_responses,
            "mutual_matches": mutual_matches,
            "category_distribution": category_pairs,
            "response_rate": round(response_rate, 2),
        }

    async def validate_attendee_compatibility(
        self, attendee1_id: uuid.UUID, attendee2_id: uuid.UUID
    ) -> bool:
        """Check if two attendees can be matched together."""

        attendees_result = await self.session.execute(
            select(Attendee).where(Attendee.id.in_([attendee1_id, attendee2_id]))
        )
        attendees = list(attendees_result.scalars())

        if len(attendees) != 2:
            return False

        attendee1, attendee2 = attendees

        # Use the model's built-in compatibility check
        return attendee1.can_match_with(attendee2)

    async def get_event_matching_summary(self, event_id: uuid.UUID) -> dict:
        """Get comprehensive matching summary for an event."""

        # Get all attendees
        attendees_result = await self.session.execute(
            select(Attendee).where(
                Attendee.event_id == event_id, Attendee.registration_confirmed
            )
        )
        attendees = list(attendees_result.scalars())

        # Group by category
        attendees_by_category = self._group_by_category(attendees)

        # Calculate theoretical maximum matches
        capacity_limits = self._calculate_capacity_limits(attendees_by_category)
        max_possible_matches = min(capacity_limits.values())

        # Get actual match statistics
        matches_result = await self.session.execute(
            select(func.count(Match.id)).where(Match.event_id == event_id)
        )
        total_matches = matches_result.scalar() or 0

        # Get mutual matches count
        mutual_matches_result = await self.session.execute(
            select(func.count(Match.id)).where(
                Match.event_id == event_id,
                Match.attendee1_response == MatchResponse.YES,
                Match.attendee2_response == MatchResponse.YES,
            )
        )
        mutual_matches = mutual_matches_result.scalar() or 0

        return {
            "total_attendees": len(attendees),
            "attendees_by_category": {
                category.value: len(attendees)
                for category, attendees in attendees_by_category.items()
            },
            "capacity_limits": {
                category.value: limit for category, limit in capacity_limits.items()
            },
            "max_possible_matches": max_possible_matches,
            "total_matches_created": total_matches,
            "mutual_matches": mutual_matches,
            "matching_efficiency": (total_matches / max_possible_matches * 100)
            if max_possible_matches > 0
            else 0,
        }


async def create_matching_service(session: AsyncSession) -> MatchingService:
    """Factory function to create a MatchingService instance."""
    return MatchingService(session)
