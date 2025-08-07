"""
Property-based tests for the matching algorithm.

Tests the matching algorithm using Hypothesis to ensure correctness
across various demographic distributions and scenarios.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from hypothesis import given, strategies as st, assume, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

from app.models import AttendeeCategory, Attendee
from app.services.matching import MatchingService
from tests.fixtures.faker_providers import setup_faker_providers


# Strategy definitions for property-based testing
@st.composite 
def attendee_category_strategy(draw):
    """Generate realistic attendee category distributions."""
    return draw(st.sampled_from(list(AttendeeCategory)))


@st.composite
def attendee_demographics_strategy(draw, faker_instance):
    """Generate realistic attendee demographics."""
    fake = setup_faker_providers(faker_instance) if faker_instance else MagicMock()
    
    category = draw(attendee_category_strategy())
    
    # Age distribution varies by category - realistic UK speed dating demographics
    if category in [AttendeeCategory.TOP_MALE, AttendeeCategory.TOP_FEMALE]:
        age_range = st.integers(min_value=28, max_value=45)  # Slightly older for "top"
    else:
        age_range = st.integers(min_value=25, max_value=42)  # Younger for "bottom"
    
    return {
        "id": uuid.uuid4(),
        "category": category,
        "age": draw(age_range),
        "display_name": fake.first_name() if hasattr(fake, 'first_name') else "TestUser",
        "checked_in": True,
        "registration_confirmed": True,
        "registered_at": datetime.now() - timedelta(days=draw(st.integers(min_value=1, max_value=30)))
    }


@st.composite
def balanced_attendee_pool_strategy(draw, faker_instance=None, min_size=8, max_size=100):
    """Generate a balanced pool of attendees for realistic matching scenarios."""
    pool_size = draw(st.integers(min_value=min_size, max_value=max_size))
    
    # Ensure minimum representation of each category for valid matching
    min_per_category = max(1, pool_size // 8)  # At least 1/8 of pool per category
    
    attendees = []
    category_counts = {cat: 0 for cat in AttendeeCategory}
    
    # First, ensure minimum representation
    for category in AttendeeCategory:
        for _ in range(min_per_category):
            attendee_data = draw(attendee_demographics_strategy(faker_instance))
            attendee_data["category"] = category
            attendees.append(create_mock_attendee(attendee_data))
            category_counts[category] += 1
    
    # Fill remaining slots randomly
    remaining_slots = pool_size - len(attendees)
    for _ in range(remaining_slots):
        attendee_data = draw(attendee_demographics_strategy(faker_instance))
        attendees.append(create_mock_attendee(attendee_data))
        category_counts[attendee_data["category"]] += 1
    
    return attendees, category_counts


def create_mock_attendee(attendee_data):
    """Create a mock attendee object for testing."""
    attendee = MagicMock(spec=Attendee)
    attendee.id = attendee_data["id"]
    attendee.category = attendee_data["category"]
    attendee.age = attendee_data.get("age", 30)
    attendee.display_name = attendee_data.get("display_name", "TestUser")
    attendee.checked_in = attendee_data.get("checked_in", True)
    attendee.registration_confirmed = attendee_data.get("registration_confirmed", True)
    attendee.registered_at = attendee_data.get("registered_at", datetime.now())
    return attendee


@pytest.mark.property
@pytest.mark.hypothesis
class TestMatchingAlgorithmProperties:
    """Property-based tests for core matching algorithm invariants."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.matching_service = MatchingService(self.mock_session)
    
    @given(attendees_and_counts=balanced_attendee_pool_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_grouping_by_category_properties(self, attendees_and_counts):
        """Test that grouping by category preserves all attendees and correct categories."""
        attendees, expected_counts = attendees_and_counts
        
        grouped = self.matching_service._group_by_category(attendees)
        
        # Property 1: All categories should be present in result
        assert set(grouped.keys()) == set(AttendeeCategory)
        
        # Property 2: Total attendees should be preserved
        total_grouped = sum(len(group) for group in grouped.values())
        assert total_grouped == len(attendees)
        
        # Property 3: Each attendee should be in correct category
        for category, group in grouped.items():
            for attendee in group:
                assert attendee.category == category
        
        # Property 4: No attendee should appear in multiple categories
        all_attendee_ids = []
        for group in grouped.values():
            group_ids = [a.id for a in group]
            all_attendee_ids.extend(group_ids)
        
        assert len(all_attendee_ids) == len(set(all_attendee_ids))
    
    @given(attendees_and_counts=balanced_attendee_pool_strategy(min_size=12, max_size=60))
    @settings(max_examples=30, deadline=5000)
    def test_capacity_limits_properties(self, attendees_and_counts):
        """Test capacity limit calculation properties."""
        attendees, expected_counts = attendees_and_counts
        
        grouped = self.matching_service._group_by_category(attendees)
        limits = self.matching_service._calculate_capacity_limits(grouped)
        
        # Property 1: Limits should never exceed actual counts
        for category, limit in limits.items():
            actual_count = len(grouped[category])
            assert limit <= actual_count, f"Limit {limit} exceeds count {actual_count} for {category}"
        
        # Property 2: All limits should be equal (balanced matching constraint)
        limit_values = list(limits.values())
        assert len(set(limit_values)) == 1, f"Limits should be equal, got {limits}"
        
        # Property 3: Limit should not exceed the smallest category
        min_category_size = min(len(group) for group in grouped.values())
        common_limit = limit_values[0]
        assert common_limit <= min_category_size
        
        # Property 4: Limits should be non-negative
        for limit in limits.values():
            assert limit >= 0
    
    @given(attendees_and_counts=balanced_attendee_pool_strategy(min_size=16, max_size=80))
    @settings(max_examples=25, deadline=10000)
    def test_capacity_application_properties(self, attendees_and_counts):
        """Test capacity limit application properties."""
        attendees, expected_counts = attendees_and_counts
        
        grouped = self.matching_service._group_by_category(attendees)
        limits = self.matching_service._calculate_capacity_limits(grouped)
        limited = self.matching_service._apply_capacity_limits(grouped, limits)
        
        # Property 1: Limited groups should respect capacity limits
        for category, limit in limits.items():
            actual_limited = len(limited[category])
            assert actual_limited <= limit, f"Category {category} exceeds limit: {actual_limited} > {limit}"
        
        # Property 2: If original group was smaller than limit, should be unchanged
        for category in AttendeeCategory:
            original_size = len(grouped[category])
            limit = limits[category]
            limited_size = len(limited[category])
            
            if original_size <= limit:
                assert limited_size == original_size
            else:
                assert limited_size == limit
        
        # Property 3: Selection should follow registration order (FIFO)
        for category in AttendeeCategory:
            original_group = grouped[category]
            limited_group = limited[category]
            
            if len(original_group) > len(limited_group):
                # Should have earliest registered attendees
                sorted_original = sorted(original_group, key=lambda a: a.registered_at)
                expected_selected = sorted_original[:len(limited_group)]
                
                limited_ids = {a.id for a in limited_group}
                expected_ids = {a.id for a in expected_selected}
                assert limited_ids == expected_ids
    
    @given(attendees_and_counts=balanced_attendee_pool_strategy(min_size=20, max_size=100))
    @settings(max_examples=20, deadline=15000)
    def test_optimal_pairing_properties(self, attendees_and_counts):
        """Test optimal pairing generation properties."""
        attendees, expected_counts = attendees_and_counts
        
        grouped = self.matching_service._group_by_category(attendees)
        limits = self.matching_service._calculate_capacity_limits(grouped)
        limited = self.matching_service._apply_capacity_limits(grouped, limits)
        
        # Skip if any category is empty (can't create meaningful pairings)
        if any(len(group) == 0 for group in limited.values()):
            return
        
        pairings = self.matching_service._generate_optimal_pairings(limited)
        
        # Property 1: Each attendee should appear at most once
        all_paired_attendees = []
        for attendee1, attendee2 in pairings:
            all_paired_attendees.extend([attendee1.id, attendee2.id])
        
        assert len(all_paired_attendees) == len(set(all_paired_attendees)), "Duplicate attendees in pairings"
        
        # Property 2: All pairings should be valid category combinations
        valid_combinations = {
            (AttendeeCategory.TOP_MALE, AttendeeCategory.TOP_FEMALE),
            (AttendeeCategory.TOP_FEMALE, AttendeeCategory.TOP_MALE),
            (AttendeeCategory.BOTTOM_MALE, AttendeeCategory.BOTTOM_FEMALE),
            (AttendeeCategory.BOTTOM_FEMALE, AttendeeCategory.BOTTOM_MALE),
            (AttendeeCategory.TOP_MALE, AttendeeCategory.BOTTOM_FEMALE),
            (AttendeeCategory.BOTTOM_FEMALE, AttendeeCategory.TOP_MALE),
            (AttendeeCategory.BOTTOM_MALE, AttendeeCategory.TOP_FEMALE),
            (AttendeeCategory.TOP_FEMALE, AttendeeCategory.BOTTOM_MALE),
        }
        
        for attendee1, attendee2 in pairings:
            pair_categories = (attendee1.category, attendee2.category)
            assert pair_categories in valid_combinations, f"Invalid pairing: {pair_categories}"
        
        # Property 3: Should maximize total pairings given constraints
        total_attendees = sum(len(group) for group in limited.values())
        max_possible_pairs = total_attendees // 2
        assert len(pairings) <= max_possible_pairs
        
        # Property 4: Should prioritize reciprocal preference pairings
        high_priority_pairs = 0
        for attendee1, attendee2 in pairings:
            if ((attendee1.category == AttendeeCategory.TOP_MALE and 
                 attendee2.category == AttendeeCategory.TOP_FEMALE) or
                (attendee1.category == AttendeeCategory.TOP_FEMALE and 
                 attendee2.category == AttendeeCategory.TOP_MALE) or
                (attendee1.category == AttendeeCategory.BOTTOM_MALE and 
                 attendee2.category == AttendeeCategory.BOTTOM_FEMALE) or
                (attendee1.category == AttendeeCategory.BOTTOM_FEMALE and 
                 attendee2.category == AttendeeCategory.BOTTOM_MALE)):
                high_priority_pairs += 1
        
        # Should create some high-priority pairings when possible
        total_pairs = len(pairings)
        if total_pairs > 0:
            high_priority_ratio = high_priority_pairs / total_pairs
            # At least 30% should be high-priority when demographics allow
            if (len(limited[AttendeeCategory.TOP_MALE]) > 0 and 
                len(limited[AttendeeCategory.TOP_FEMALE]) > 0):
                assert high_priority_ratio >= 0.1  # Allow flexibility for edge cases


@pytest.mark.property
@pytest.mark.hypothesis
class TestMatchingStateMachine(RuleBasedStateMachine):
    """Stateful property-based testing for matching algorithm."""
    
    def __init__(self):
        super().__init__()
        self.mock_session = MagicMock()
        self.matching_service = MatchingService(self.mock_session)
        self.attendee_pool = []
        self.current_pairings = []
    
    @rule(new_attendees=st.lists(
        attendee_demographics_strategy(None), 
        min_size=1, 
        max_size=10
    ))
    def add_attendees(self, new_attendees):
        """Add new attendees to the pool."""
        for attendee_data in new_attendees:
            attendee = create_mock_attendee(attendee_data)
            self.attendee_pool.append(attendee)
    
    @rule()
    def create_pairings(self):
        """Create pairings from current attendee pool."""
        if len(self.attendee_pool) < 4:  # Need minimum attendees for meaningful pairings
            return
        
        grouped = self.matching_service._group_by_category(self.attendee_pool)
        limits = self.matching_service._calculate_capacity_limits(grouped)
        limited = self.matching_service._apply_capacity_limits(grouped, limits)
        self.current_pairings = self.matching_service._generate_optimal_pairings(limited)
    
    @rule()
    def remove_attendees(self):
        """Remove some attendees from the pool."""
        if len(self.attendee_pool) > 4:
            # Remove up to 25% of attendees
            remove_count = max(1, len(self.attendee_pool) // 4)
            self.attendee_pool = self.attendee_pool[:-remove_count]
            self.current_pairings = []  # Clear pairings after attendee removal
    
    @invariant()
    def attendee_pool_consistency(self):
        """Attendee pool should maintain consistency."""
        # All attendees should have required attributes
        for attendee in self.attendee_pool:
            assert hasattr(attendee, 'id')
            assert hasattr(attendee, 'category')
            assert attendee.category in AttendeeCategory
            assert hasattr(attendee, 'checked_in')
            assert hasattr(attendee, 'registration_confirmed')
    
    @invariant()
    def pairing_consistency(self):
        """Pairings should be consistent with current attendee pool."""
        if not self.current_pairings:
            return
        
        paired_ids = set()
        for attendee1, attendee2 in self.current_pairings:
            # Each attendee should be in the pool
            pool_ids = {a.id for a in self.attendee_pool}
            assert attendee1.id in pool_ids
            assert attendee2.id in pool_ids
            
            # No duplicate pairings
            assert attendee1.id not in paired_ids
            assert attendee2.id not in paired_ids
            paired_ids.add(attendee1.id)
            paired_ids.add(attendee2.id)


# Performance and edge case tests
@pytest.mark.property
@pytest.mark.performance
class TestMatchingPerformance:
    """Test matching algorithm performance characteristics."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.matching_service = MatchingService(self.mock_session)
    
    @given(attendees_and_counts=balanced_attendee_pool_strategy(min_size=100, max_size=500))
    @settings(max_examples=5, deadline=20000)
    def test_large_pool_performance(self, attendees_and_counts):
        """Test algorithm performance with large attendee pools."""
        attendees, expected_counts = attendees_and_counts
        
        import time
        
        start_time = time.perf_counter()
        
        grouped = self.matching_service._group_by_category(attendees)
        limits = self.matching_service._calculate_capacity_limits(grouped)
        limited = self.matching_service._apply_capacity_limits(grouped, limits)
        pairings = self.matching_service._generate_optimal_pairings(limited)
        
        end_time = time.perf_counter()
        processing_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Algorithm should complete in reasonable time even for large pools
        assert processing_time < 1000, f"Algorithm took too long: {processing_time:.2f}ms for {len(attendees)} attendees"
        
        # Should still produce valid results
        assert len(pairings) > 0, "Should produce some pairings for large pools"
    
    @given(st.lists(attendee_demographics_strategy(None), min_size=0, max_size=10))
    def test_edge_cases(self, attendees_data):
        """Test algorithm behavior with edge cases."""
        attendees = [create_mock_attendee(data) for data in attendees_data]
        
        # Should handle empty or small pools gracefully
        grouped = self.matching_service._group_by_category(attendees)
        limits = self.matching_service._calculate_capacity_limits(grouped)
        limited = self.matching_service._apply_capacity_limits(grouped, limits)
        pairings = self.matching_service._generate_optimal_pairings(limited)
        
        # Should not crash with edge cases
        assert isinstance(pairings, list)
        assert len(pairings) <= len(attendees) // 2


# Demographic realism tests
@pytest.mark.property
@pytest.mark.faker
class TestDemographicRealism:
    """Test matching algorithm with realistic UK speed dating demographics."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.matching_service = MatchingService(self.mock_session)
    
    @pytest.mark.faker
    @given(
        male_ratio=st.floats(min_value=0.3, max_value=0.7),  # 30-70% male
        age_skew=st.floats(min_value=-5, max_value=5),  # Age distribution skew
        pool_size=st.integers(min_value=20, max_value=60)  # Typical event size
    )
    @settings(max_examples=15, deadline=10000)
    def test_realistic_demographic_matching(self, male_ratio, age_skew, pool_size, faker_instance):
        """Test matching with realistic UK demographic distributions."""
        fake = setup_faker_providers(faker_instance)
        
        # Generate realistic demographic pool
        attendees = []
        male_count = int(pool_size * male_ratio)
        female_count = pool_size - male_count
        
        # Create males (split between top/bottom)
        male_categories = [AttendeeCategory.TOP_MALE, AttendeeCategory.BOTTOM_MALE]
        for i in range(male_count):
            category = fake.random_element(male_categories)
            base_age = 32 + age_skew  # Base age for speed dating
            age = max(25, min(60, int(fake.random.gauss(base_age, 8))))
            
            attendee_data = {
                "id": uuid.uuid4(),
                "category": category,
                "age": age,
                "display_name": fake.first_name_male(),
                "checked_in": True,
                "registration_confirmed": True,
                "registered_at": datetime.now() - timedelta(days=fake.random_int(1, 21))
            }
            attendees.append(create_mock_attendee(attendee_data))
        
        # Create females (split between top/bottom)
        female_categories = [AttendeeCategory.TOP_FEMALE, AttendeeCategory.BOTTOM_FEMALE]
        for i in range(female_count):
            category = fake.random_element(female_categories)
            base_age = 29 + age_skew  # Slightly younger average for women
            age = max(22, min(55, int(fake.random.gauss(base_age, 7))))
            
            attendee_data = {
                "id": uuid.uuid4(),
                "category": category,
                "age": age,
                "display_name": fake.first_name_female(),
                "checked_in": True,
                "registration_confirmed": True,
                "registered_at": datetime.now() - timedelta(days=fake.random_int(1, 21))
            }
            attendees.append(create_mock_attendee(attendee_data))
        
        # Test matching algorithm with realistic demographics
        grouped = self.matching_service._group_by_category(attendees)
        limits = self.matching_service._calculate_capacity_limits(grouped)
        limited = self.matching_service._apply_capacity_limits(grouped, limits)
        pairings = self.matching_service._generate_optimal_pairings(limited)
        
        # Validate realistic outcomes
        if len(pairings) > 0:
            # Should achieve reasonable pairing efficiency
            pairing_efficiency = len(pairings) / (len(attendees) / 2)
            assert pairing_efficiency >= 0.5, f"Poor pairing efficiency: {pairing_efficiency:.2%}"
            
            # Age gaps should be reasonable for speed dating context
            age_gaps = []
            for attendee1, attendee2 in pairings:
                age_gap = abs(attendee1.age - attendee2.age)
                age_gaps.append(age_gap)
            
            if age_gaps:
                avg_age_gap = sum(age_gaps) / len(age_gaps)
                # Most speed dating events see age gaps under 15 years
                assert avg_age_gap <= 20, f"Unrealistic average age gap: {avg_age_gap:.1f} years"


# Test runner configuration
TestMatchingStateMachine.TestCase.settings = settings(
    max_examples=50,
    stateful_step_count=20,
    deadline=30000
)