# Match Results and Export System

## Overview

The Match Results system provides comprehensive functionality for analyzing, aggregating, and exporting speed dating match data. This system allows event organizers to gain insights into event performance and provides attendees with their personal match results.

## Key Features

### Statistics and Analytics
- **Event-wide Statistics**: Complete event performance analysis including response rates, mutual match rates, and success metrics
- **Category Analysis**: Breakdown of match success by attendee categories
- **Round-by-Round Analysis**: Performance metrics for each round of speed dating  
- **Response Rate Tracking**: Detailed analysis of attendee participation and engagement
- **Rating Statistics**: Analysis of attendee ratings and feedback

### Export Functionality
- **All Matches CSV**: Complete export of all match data with responses, ratings, and timestamps
- **Mutual Matches CSV**: Export of successful matches for easy distribution to participants
- **Attendee Summary CSV**: Per-attendee statistics and performance metrics
- **Statistics JSON**: Machine-readable export of all statistics for data analysis

### Individual Results
- **Personal Match History**: Attendees can view their complete match history
- **Response Tracking**: View given and received responses
- **Success Metrics**: Personal statistics including mutual matches and ratings

## API Endpoints

### Organizer Endpoints (Require Admin Access)

#### Get Event Statistics
```
GET /api/match-results/events/{event_id}/statistics
```
Returns comprehensive event statistics including:
- Total matches and mutual matches
- Response rates and success rates
- Category breakdowns
- Round-by-round analysis
- Rating and timing statistics

#### Get Mutual Matches
```
GET /api/match-results/events/{event_id}/mutual-matches
```
Returns all mutual matches for an event with detailed attendee information.

#### Export All Matches
```
GET /api/match-results/events/{event_id}/export/all-matches.csv
```
Downloads a CSV file containing all match data.

#### Export Mutual Matches
```
GET /api/match-results/events/{event_id}/export/mutual-matches.csv
```
Downloads a CSV file containing only successful matches.

#### Export Attendee Summary
```
GET /api/match-results/events/{event_id}/export/attendee-summary.csv
```
Downloads a CSV file with per-attendee statistics.

#### Export Statistics as JSON
```
GET /api/match-results/events/{event_id}/export/statistics.json
```
Downloads complete event statistics in JSON format.

### Attendee Endpoints

#### Get Personal Results
```
GET /api/match-results/attendees/{attendee_id}/results
```
Returns detailed match results for a specific attendee. Attendees can only view their own results unless they have organizer permissions.

## Data Structure

### Event Statistics Response
```json
{
  "event_id": "uuid",
  "event_name": "Event Name",
  "event_date": "2024-01-01T10:00:00Z",
  "total_attendees": 50,
  "total_matches": 125,
  "mutual_matches": 15,
  "response_rate": 85.5,
  "mutual_match_rate": 12.0,
  "success_rate": 17.6,
  "attendee_response_rates": [...],
  "category_statistics": {...},
  "round_statistics": [...],
  "rating_statistics": {...},
  "timing_statistics": {...}
}
```

### Mutual Match Response
```json
{
  "match_id": "uuid",
  "round_number": 1,
  "table_number": 5,
  "attendee1": {
    "id": "uuid",
    "display_name": "John",
    "category": "man_seeking_woman",
    "age": 28,
    "rating_given": 4,
    "response_time": "2024-01-01T10:15:00Z"
  },
  "attendee2": {
    "id": "uuid", 
    "display_name": "Jane",
    "category": "woman_seeking_man",
    "age": 26,
    "rating_given": 5,
    "response_time": "2024-01-01T10:16:00Z"
  },
  "created_at": "2024-01-01T10:00:00Z"
}
```

## Usage Examples

### Getting Event Statistics
```python
import httpx

# Get comprehensive event statistics
response = httpx.get(
    f"/api/match-results/events/{event_id}/statistics",
    headers={"Authorization": f"Bearer {token}"}
)
statistics = response.json()

print(f"Event had {statistics['total_matches']} matches")
print(f"Mutual match rate: {statistics['mutual_match_rate']:.1f}%")
```

### Exporting Mutual Matches
```python
import httpx

# Download mutual matches CSV
response = httpx.get(
    f"/api/match-results/events/{event_id}/export/mutual-matches.csv",
    headers={"Authorization": f"Bearer {token}"}
)

# Save to file
with open("mutual_matches.csv", "w") as f:
    f.write(response.text)
```

## CSV Export Formats

### All Matches CSV Columns
- Match ID, Event ID, Round Number, Table Number
- Attendee1 details (ID, Name, Category, Age, Response, Rating, Response Time)
- Attendee2 details (ID, Name, Category, Age, Response, Rating, Response Time)
- Is Mutual Match, Both Responded, Created At

### Mutual Matches CSV Columns
- Match ID, Round Number, Table Number
- Person 1 details (Name, Category, Age, Rating Given)
- Person 2 details (Name, Category, Age, Rating Given)
- Match Created At

### Attendee Summary CSV Columns
- Attendee ID, Display Name, Category, Age
- Total Matches, Responses Given, Response Rate (%)
- Yes/No Responses Given, Mutual Matches, Success Rate (%)
- Average Rating Given/Received

## Security and Privacy

- **Admin Access Required**: All event-level statistics and exports require organizer permissions
- **Personal Data Protection**: Attendees can only access their own results unless they have admin privileges
- **Contact Information**: Contact details are excluded from exports to protect privacy
- **Anonymization Options**: Consider implementing attendee anonymization for research purposes

## Integration with Other Systems

The match results system integrates with:
- **Event Management**: Links to event and round data
- **Attendee Management**: Connects to attendee profiles and categories
- **Authentication**: Respects user permissions and access controls
- **WebSocket System**: Can trigger real-time updates for match notifications

## Performance Considerations

- **Database Optimization**: Uses eager loading to minimize database queries
- **CSV Generation**: Streams large exports to handle events with many matches
- **Caching**: Consider implementing caching for frequently accessed statistics
- **Pagination**: Large result sets should be paginated for better performance

## Future Enhancements

- **Real-time Statistics**: Live updating statistics during events
- **Advanced Analytics**: Machine learning insights and match prediction
- **Custom Reports**: Configurable report generation
- **Integration APIs**: Webhooks for external system integration
- **Mobile Optimization**: Mobile-friendly result viewing