# Real-Time Round Management System

This document describes the real-time round management and timer system for the Speed Dating application.

## Overview

The real-time system provides:
- WebSocket-based real-time communication
- Automatic round timers with break periods
- Event countdown timers for first round start
- Live timer updates for organizers and attendees
- Real-time announcements and notifications
- Connection management for multiple users

## Architecture

### Components

1. **WebSocket Manager** (`app/services/websocket_manager.py`)
   - `ConnectionManager`: Manages WebSocket connections and rooms
   - `RoundTimerManager`: Handles real-time round timers
   - `EventCountdownManager`: Manages event countdown timers

2. **WebSocket Endpoints** (`app/api/websockets.py`)
   - `/ws/event/{event_id}`: Event-wide updates
   - `/ws/round/{round_id}/timer`: Round timer updates
   - `/ws/admin/dashboard`: Admin dashboard updates

3. **Enhanced Round API** (`app/api/rounds.py`)
   - Integration with WebSocket broadcasting
   - Real-time timer management
   - Announcement system

## WebSocket Endpoints

### Event Room: `/ws/event/{event_id}`

Connect to event-wide updates:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/event/{event_id}?token={jwt_token}');
```

**Message Types:**
- `connected`: Welcome message with countdown status
- `countdown_started`: Event countdown initiated
- `countdown_update`: Real-time countdown updates (every second)
- `countdown_warning`: Countdown warnings (10min, 5min, 2min, 1min, 30sec, 10sec)
- `countdown_completed`: Countdown finished
- `countdown_cancelled`: Countdown stopped by organizer
- `countdown_extended`: Countdown time extended
- `round_started`: Round has started
- `round_ended`: Round has ended
- `break_started`: Break period started
- `round_announcement`: Announcements from organizers

### Round Timer: `/ws/round/{round_id}/timer`

Connect to real-time round timer:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/round/{round_id}/timer?token={jwt_token}');
```

**Message Types:**
- `timer_connected`: Connection established
- `timer_update`: Real-time timer updates (every second)
- `timer_warning`: Warnings (1 minute, 30 seconds, countdown)
- `round_ended`: Round completed
- `break_started`: Break period started
- `break_ended`: Break period ended
- `announcement`: Organizer announcements
- `round_extended`: Round time extended

### Admin Dashboard: `/ws/admin/dashboard`

Admin-only WebSocket for dashboard updates:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/admin/dashboard?token={jwt_token}');
```

## Timer System

### Round Timer Features

- **Precise Timing**: Uses system time for accuracy
- **Automatic Warnings**: 1 minute, 30 seconds, and countdown alerts
- **Break Management**: Automatic break periods after rounds
- **Real-time Updates**: Second-by-second progress updates
- **Progress Tracking**: Visual progress bars and completion percentages

### Event Countdown Features

- **Pre-Event Coordination**: Organizers can start countdown before first round
- **Flexible Duration**: 1-60 minute countdown periods
- **Custom Messages**: Personalized countdown messages for attendees
- **Progressive Warnings**: Alerts at 10, 5, 2, 1 minutes, 30 and 10 seconds
- **Extension Support**: Organizers can extend countdown if needed
- **Real-time Sync**: All connected users see synchronized countdown

### Timer Messages

```javascript
// Timer update message
{
  "type": "timer_update",
  "round_id": "uuid",
  "phase": "round" | "break",
  "time_remaining": 180, // seconds
  "total_duration": 300,  // seconds
  "status": "active",
  "percentage_complete": 40.0
}

// Warning message
{
  "type": "timer_warning",
  "round_id": "uuid",
  "message": "1 minute remaining",
  "warning_type": "one_minute"
}

// Countdown update message
{
  "type": "countdown_update",
  "event_id": "uuid",
  "time_remaining": 300, // seconds
  "total_duration": 600,  // seconds
  "percentage_complete": 50.0,
  "message": "Event starts in 10 minutes!",
  "target_time": "2025-01-01T20:00:00Z"
}

// Countdown warning message
{
  "type": "countdown_warning",
  "event_id": "uuid",
  "message": "⚠️ 5 minutes until event starts!",
  "warning_type": "five_minutes",
  "time_remaining": 300
}
```

## API Integration

### Starting a Round with Timer

```python
# POST /api/rounds/{round_id}/start
# Automatically starts WebSocket timer and broadcasts to participants
```

### Making Announcements

```python
# POST /api/rounds/{round_id}/announce
{
  "message": "Please move to your next table"
}
```

### Extending Round Time

```python
# POST /api/rounds/{round_id}/extend
{
  "additional_minutes": 2
}
```

## Client Integration

### Basic WebSocket Client

```javascript
class RoundTimer {
  constructor(roundId, token) {
    this.roundId = roundId;
    this.token = token;
    this.ws = null;
  }
  
  connect() {
    const url = `ws://localhost:8000/ws/round/${this.roundId}/timer?token=${this.token}`;
    this.ws = new WebSocket(url);
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };
  }
  
  handleMessage(data) {
    switch(data.type) {
      case 'timer_update':
        this.updateTimer(data.time_remaining);
        break;
      case 'timer_warning':
        this.showWarning(data.message);
        break;
      case 'announcement':
        this.showAnnouncement(data.message);
        break;
    }
  }
}
```

### React Integration

```jsx
import { useEffect, useState } from 'react';

function RoundTimer({ roundId, token }) {
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [status, setStatus] = useState('disconnected');
  
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/round/${roundId}/timer?token=${token}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'timer_update') {
        setTimeRemaining(data.time_remaining);
        setStatus(data.phase);
      }
    };
    
    return () => ws.close();
  }, [roundId, token]);
  
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  return (
    <div>
      <h2>Round Timer</h2>
      <div className="timer">{formatTime(timeRemaining)}</div>
      <div className="status">{status}</div>
    </div>
  );
}
```

## Security

### Authentication
- All WebSocket connections require JWT token authentication
- Tokens are validated on connection and periodically during use
- Users can only access events/rounds they have permission for

### Authorization
- **Organizers**: Full access to events they own
- **Attendees**: Can only access events they're registered for
- **Admins**: Additional dashboard access

### Connection Management
- Automatic cleanup of disconnected clients
- Connection limits and rate limiting (future enhancement)
- IP monitoring and security logging (future enhancement)

## Testing

### Demo Page
Visit `/static/timer-demo.html` for a live demo of the timer system.

### WebSocket Testing
```bash
# Test WebSocket connection with wscat
npm install -g wscat
wscat -c "ws://localhost:8000/ws/round/{round_id}/timer?token={jwt_token}"
```

## Deployment Considerations

### Production Setup
1. **Redis**: Replace in-memory storage with Redis for scalability
2. **Load Balancing**: Use sticky sessions or Redis for WebSocket scaling
3. **Monitoring**: Add WebSocket connection monitoring
4. **SSL**: Use WSS in production environments

### Configuration
```python
# Production WebSocket settings
WEBSOCKET_MAX_CONNECTIONS = 1000
WEBSOCKET_HEARTBEAT_INTERVAL = 30
WEBSOCKET_CLEANUP_INTERVAL = 60
```

## Future Enhancements

1. **Voice Notifications**: Text-to-speech announcements
2. **Mobile Push**: Push notifications for mobile apps
3. **Analytics**: Connection and usage analytics
4. **Scalability**: Redis backend for multi-server deployment
5. **Advanced Timers**: Custom timer presets and schedules
6. **Integration**: Calendar and external system integrations

## Troubleshooting

### Common Issues

1. **Connection Refused**: Check JWT token validity
2. **Timer Sync Issues**: Verify system time synchronization
3. **High Memory Usage**: Monitor connection cleanup
4. **WebSocket Drops**: Check network stability and heartbeat settings

### Debug Mode
Enable WebSocket debugging:
```python
import logging
logging.getLogger('websockets').setLevel(logging.DEBUG)
```

## API Reference

### WebSocket Health Check
```
GET /ws/health
```

### Active Timers
```
GET /api/rounds/active-timers
```

### Round Management
```
POST /api/rounds/{round_id}/start
POST /api/rounds/{round_id}/end
POST /api/rounds/{round_id}/announce
POST /api/rounds/{round_id}/extend
```

### Event Countdown Management
```
POST /api/events/{event_id}/countdown/start
POST /api/events/{event_id}/countdown/stop
POST /api/events/{event_id}/countdown/extend
GET /api/events/{event_id}/countdown/status
GET /api/events/active-countdowns
```