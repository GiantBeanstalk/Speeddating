"""
Custom Faker providers for Speed Dating application.

Provides realistic UK-specific data and domain-specific fake data
for events, venues, attendee categories, and other speed dating concepts.
"""

import random
from datetime import UTC, datetime, timedelta
from typing import List

from faker import Faker
from faker.providers import BaseProvider


class UKDataProvider(BaseProvider):
    """Provider for realistic UK-specific data."""
    
    uk_postcodes = [
        "SW1A 1AA", "M1 1AA", "B1 1HQ", "LS1 1AA", "NE1 1AA",
        "GL1 1AA", "S1 1AA", "CV1 1AA", "NG1 1AA", "DE1 1AA",
        "E1 6AN", "W1 1AA", "EC1A 1BB", "WC1A 1AA", "N1 1AA",
        "SE1 1AA", "SW1 1AA", "NW1 1AA", "E14 1AA", "W2 1AA"
    ]
    
    uk_cities = [
        "London", "Manchester", "Birmingham", "Leeds", "Newcastle",
        "Gloucester", "Sheffield", "Coventry", "Nottingham", "Derby",
        "Brighton", "Bristol", "Liverpool", "Edinburgh", "Glasgow",
        "Cardiff", "Belfast", "Oxford", "Cambridge", "Bath"
    ]
    
    uk_phone_prefixes = [
        "020", "0121", "0161", "0113", "0191", "01452", "0114",
        "024", "0115", "01332", "01273", "0117", "0151", "0131",
        "0141", "029", "028", "01865", "01223", "01225"
    ]
    
    fetlife_username_patterns = [
        "KinkyKitten{}", "RopeBunny{}", "DomDaddy{}", "SubSlut{}",
        "MasterOf{}", "SlaveGirl{}", "SirStephen{}", "MissMarple{}",
        "LordOfPain{}", "AngelOfLust{}", "DarkKnight{}", "SweetSub{}",
        "PowerfulDom{}", "PlayfulKitten{}", "StrictMaster{}",
        "NaughtyNurse{}", "BadBoy{}", "GoodGirl{}", "Switchy{}",
        "VanillaVixen{}", "KinkExplorer{}", "BDSMBeginner{}"
    ]
    
    def uk_postcode(self) -> str:
        """Generate a realistic UK postcode."""
        return self.random_element(self.uk_postcodes)
    
    def uk_city(self) -> str:
        """Generate a UK city name."""
        return self.random_element(self.uk_cities)
    
    def uk_phone_number(self) -> str:
        """Generate a realistic UK phone number."""
        prefix = self.random_element(self.uk_phone_prefixes)
        if prefix == "020":  # London
            return f"{prefix} {self.random_int(7000, 8999)} {self.random_int(1000, 9999)}"
        elif len(prefix) == 4:  # 3-digit area code
            return f"{prefix} {self.random_int(100, 999)} {self.random_int(1000, 9999)}"
        else:  # 4-digit area code
            return f"{prefix} {self.random_int(100000, 999999)}"
    
    def fetlife_username(self) -> str:
        """Generate a realistic FetLife username."""
        pattern = self.random_element(self.fetlife_username_patterns)
        if "{}" in pattern:
            suffix = self.random_int(1, 9999)
            return pattern.format(suffix)
        return pattern
    
    def uk_address(self) -> str:
        """Generate a realistic UK address."""
        street_number = self.random_int(1, 999)
        street_name = self.generator.street_name()
        city = self.uk_city()
        postcode = self.uk_postcode()
        return f"{street_number} {street_name}, {city} {postcode}"


class SpeedDatingProvider(BaseProvider):
    """Provider for speed dating specific fake data."""
    
    venue_names = [
        "The Cock Tavern", "Revolution Bar", "All Bar One", "Slug & Lettuce",
        "The Living Room", "Pitcher & Piano", "Be At One", "The Alchemist",
        "Dirty Martini", "The Botanist", "Cosy Club", "Turtle Bay",
        "TGI Friday's", "Zizzi", "Côte Brasserie", "Miller & Carter",
        "The Ivy", "Dishoom", "Hawksmoor", "Aqua Shard", "Sketch",
        "The Shard", "Sky Garden", "Rooftop Bar", "The George",
        "The Red Lion", "The Crown & Anchor", "The White Horse"
    ]
    
    venue_types = [
        "Cocktail Bar", "Wine Bar", "Gastropub", "Restaurant & Bar",
        "Rooftop Lounge", "Hotel Bar", "Speakeasy", "Sports Bar",
        "Craft Beer House", "Champagne Bar", "Whiskey Bar", "Gin Palace"
    ]
    
    event_names = [
        "Singles Mingle Monday", "Tuesday Night Speed Dating", "Wine & Dine Wednesday",
        "Thirsty Thursday Speed Dating", "Friday Night Flirtation", "Saturday Singles Social",
        "Sunday Sunset Speed Dating", "After Work Speed Dating", "Lunch Break Love",
        "Happy Hour Hearts", "Speed Dating Spectacular", "Love at First Sight",
        "Chemistry Connection", "Spark & Sparkle", "Match Made Monday",
        "Date Night Delight", "Singles Soirée", "Romance & Cocktails",
        "Speed Dating Extravaganza", "First Impression Friday"
    ]
    
    categories = [
        {"name": "Young Professionals", "min_age": 22, "max_age": 35},
        {"name": "Thirty Something", "min_age": 30, "max_age": 45},
        {"name": "Mature Singles", "min_age": 40, "max_age": 60},
        {"name": "Silver Singles", "min_age": 55, "max_age": 75},
        {"name": "Graduate Speed Dating", "min_age": 25, "max_age": 40},
        {"name": "Creative Professionals", "min_age": 25, "max_age": 45},
        {"name": "Tech Workers", "min_age": 24, "max_age": 40},
        {"name": "Healthcare Heroes", "min_age": 26, "max_age": 50},
    ]
    
    professions = [
        "Software Engineer", "Teacher", "Nurse", "Doctor", "Lawyer",
        "Accountant", "Marketing Manager", "Designer", "Consultant",
        "Project Manager", "Sales Executive", "HR Manager", "Architect",
        "Physiotherapist", "Police Officer", "Social Worker", "Chef",
        "Journalist", "Personal Trainer", "Pharmacist", "Dentist",
        "Vet", "Engineer", "Scientist", "Therapist", "Artist"
    ]
    
    hobbies = [
        "Reading", "Traveling", "Cooking", "Photography", "Hiking",
        "Yoga", "Running", "Cycling", "Swimming", "Dancing",
        "Music", "Art", "Theatre", "Cinema", "Wine Tasting",
        "Rock Climbing", "Skiing", "Surfing", "Gardening", "Fitness",
        "Meditation", "Writing", "Languages", "History", "Nature"
    ]
    
    bio_templates = [
        "Love {hobby1} and {hobby2}. {profession} by day, adventurer by night! Looking for someone to share {hobby3} with.",
        "Passionate {profession} who enjoys {hobby1}, {hobby2} and exploring new places. Life's too short for boring conversations!",
        "{profession} with a love for {hobby1} and {hobby2}. Always up for trying new restaurants or planning the next adventure.",
        "When I'm not working as a {profession}, you'll find me {hobby1} or {hobby2}. Looking for someone who shares my zest for life!",
        "Easy-going {profession} who loves {hobby1}, {hobby2} and good wine. Let's see if we have chemistry!",
        "Ambitious {profession} by day, {hobby1} enthusiast by evening. Love {hobby2} and meeting new people.",
        "{profession} who believes in work-life balance. Enjoy {hobby1}, {hobby2} and spontaneous weekend trips.",
    ]
    
    def venue_name(self) -> str:
        """Generate a realistic venue name."""
        return self.random_element(self.venue_names)
    
    def venue_type(self) -> str:
        """Generate a venue type."""
        return self.random_element(self.venue_types)
    
    def event_name(self) -> str:
        """Generate a speed dating event name."""
        return self.random_element(self.event_names)
    
    def age_category(self) -> dict:
        """Generate an age category for speed dating."""
        return self.random_element(self.categories)
    
    def profession(self) -> str:
        """Generate a realistic profession."""
        return self.random_element(self.professions)
    
    def hobby(self) -> str:
        """Generate a hobby."""
        return self.random_element(self.hobbies)
    
    def hobbies_list(self, count: int = 3) -> List[str]:
        """Generate a list of hobbies."""
        return self.random_choices(self.hobbies, length=count)
    
    def bio(self) -> str:
        """Generate a realistic dating profile bio."""
        template = self.random_element(self.bio_templates)
        hobbies = self.random_choices(self.hobbies, length=3)
        return template.format(
            profession=self.profession(),
            hobby1=hobbies[0].lower(),
            hobby2=hobbies[1].lower(),
            hobby3=hobbies[2].lower()
        )
    
    def event_date(self, days_ahead: int = 30) -> datetime:
        """Generate a future event date."""
        start_date = datetime.now(UTC) + timedelta(days=1)
        end_date = start_date + timedelta(days=days_ahead)
        
        # Generate random date, but prefer weekday evenings and weekends
        random_date = self.generator.date_time_between(
            start_date=start_date,
            end_date=end_date,
            tzinfo=UTC
        )
        
        # Adjust to evening time (18:00-21:00) for speed dating events
        evening_hour = self.random_int(18, 21)
        evening_minute = self.random_choices([0, 15, 30, 45])[0]
        
        return random_date.replace(
            hour=evening_hour,
            minute=evening_minute,
            second=0,
            microsecond=0
        )
    
    def round_duration(self) -> int:
        """Generate realistic round duration in minutes."""
        return self.random_choices([3, 4, 5, 6, 8], weights=[10, 30, 40, 15, 5])[0]
    
    def max_attendees(self) -> int:
        """Generate realistic maximum attendees for an event."""
        return self.random_choices([20, 24, 30, 36, 40], weights=[20, 30, 30, 15, 5])[0]


def setup_faker_providers(fake: Faker = None) -> Faker:
    """Set up all custom providers on a Faker instance."""
    if fake is None:
        fake = Faker("en_GB")
    
    fake.add_provider(UKDataProvider)
    fake.add_provider(SpeedDatingProvider)
    
    return fake


# Global instance for easy importing
fake = setup_faker_providers()