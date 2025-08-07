/**
 * WebSocket client for real-time timer updates
 */

class WebSocketClient {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.isConnecting = false;
        this.listeners = new Map();
        
        // Initialize connection
        this.connect();
        
        // Set up page visibility handling
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && !this.socket) {
                this.connect();
            }
        });
    }

    connect() {
        if (this.isConnecting || (this.socket && this.socket.readyState === WebSocket.OPEN)) {
            return;
        }

        this.isConnecting = true;
        this.updateConnectionStatus('connecting');

        const wsUrl = `ws://${window.location.host}/ws/events/general`;
        
        try {
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected');
                
                // Send authentication if user is logged in
                this.authenticate();
            };

            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            this.socket.onclose = (event) => {
                console.log('WebSocket disconnected', event.code, event.reason);
                this.isConnecting = false;
                this.socket = null;
                this.updateConnectionStatus('disconnected');
                
                // Attempt to reconnect if it wasn't a manual close
                if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    setTimeout(() => {
                        this.reconnectAttempts++;
                        this.connect();
                    }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts));
                }
            };

            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.isConnecting = false;
                this.updateConnectionStatus('disconnected');
            };

        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.isConnecting = false;
            this.updateConnectionStatus('disconnected');
        }
    }

    authenticate() {
        // Send authentication message if needed
        // This would typically include a JWT token
        this.send({
            type: 'auth',
            token: this.getAuthToken()
        });
    }

    getAuthToken() {
        // Get auth token from localStorage or cookie
        return localStorage.getItem('auth_token') || '';
    }

    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not connected, cannot send message:', data);
        }
    }

    handleMessage(data) {
        console.log('WebSocket message received:', data);

        switch (data.type) {
            case 'timer_update':
                this.handleTimerUpdate(data);
                break;
            case 'round_started':
                this.handleRoundStarted(data);
                break;
            case 'round_ended':
                this.handleRoundEnded(data);
                break;
            case 'break_started':
                this.handleBreakStarted(data);
                break;
            case 'countdown_started':
                this.handleCountdownStarted(data);
                break;
            case 'countdown_update':
                this.handleCountdownUpdate(data);
                break;
            case 'countdown_ended':
                this.handleCountdownEnded(data);
                break;
            case 'countdown_warning':
                this.handleCountdownWarning(data);
                break;
            case 'error':
                this.handleError(data);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }

        // Emit to registered listeners
        if (this.listeners.has(data.type)) {
            this.listeners.get(data.type).forEach(callback => callback(data));
        }
    }

    handleTimerUpdate(data) {
        const timerElement = document.getElementById('timer-display');
        if (timerElement) {
            const minutes = Math.floor(data.seconds_remaining / 60);
            const seconds = data.seconds_remaining % 60;
            const timeStr = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            
            timerElement.textContent = timeStr;
            
            // Add warning class if less than 30 seconds
            if (data.seconds_remaining <= 30) {
                timerElement.classList.add('warning');
            } else {
                timerElement.classList.remove('warning');
            }
        }

        // Update round status
        const statusElement = document.getElementById('round-status');
        if (statusElement) {
            statusElement.textContent = data.message || 'Round in progress';
        }
    }

    handleRoundStarted(data) {
        if (window.App) {
            window.App.utils.showFlash(`Round ${data.round_number} has started!`, 'info');
        }
        
        // Update UI elements
        const roundElements = document.querySelectorAll('[data-round-status]');
        roundElements.forEach(element => {
            element.textContent = 'In Progress';
            element.className = 'badge badge-primary';
        });
    }

    handleRoundEnded(data) {
        if (window.App) {
            window.App.utils.showFlash(`Round ${data.round_number} has ended!`, 'info');
        }

        // Update timer display
        const timerElement = document.getElementById('timer-display');
        if (timerElement) {
            timerElement.textContent = '00:00';
            timerElement.classList.remove('warning');
        }
    }

    handleBreakStarted(data) {
        if (window.App) {
            window.App.utils.showFlash(`Break started: ${data.break_duration_minutes} minutes`, 'info');
        }
    }

    handleCountdownStarted(data) {
        if (window.App) {
            window.App.utils.showFlash(`Event countdown started: ${data.duration_minutes} minutes`, 'info');
        }
    }

    handleCountdownUpdate(data) {
        const countdownElement = document.getElementById('countdown-display');
        if (countdownElement) {
            const minutes = Math.floor(data.seconds_remaining / 60);
            const seconds = data.seconds_remaining % 60;
            const timeStr = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            
            countdownElement.textContent = timeStr;
            
            // Add warning class if less than 2 minutes
            if (data.seconds_remaining <= 120) {
                countdownElement.classList.add('warning');
            }
        }

        // Update countdown message
        const messageElement = document.getElementById('countdown-message');
        if (messageElement) {
            messageElement.textContent = data.message || '';
        }
    }

    handleCountdownEnded(data) {
        if (window.App) {
            window.App.utils.showFlash('Event is starting now!', 'success');
        }

        const countdownElement = document.getElementById('countdown-display');
        if (countdownElement) {
            countdownElement.textContent = '00:00';
            countdownElement.classList.remove('warning');
        }
    }

    handleCountdownWarning(data) {
        if (window.App) {
            window.App.utils.showFlash(data.message, 'warning');
        }
    }

    handleError(data) {
        console.error('WebSocket error message:', data.message);
        if (window.App) {
            window.App.utils.showFlash(data.message, 'error');
        }
    }

    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connection-status');
        if (!statusElement) return;

        statusElement.className = `connection-status badge ${status}`;
        
        const statusText = {
            'connecting': 'Connecting...',
            'connected': 'Connected',
            'disconnected': 'Disconnected'
        };

        const textElement = statusElement.querySelector('#connection-text');
        if (textElement) {
            textElement.textContent = statusText[status] || status;
        }

        // Show/hide status indicator
        if (status === 'connected') {
            setTimeout(() => {
                statusElement.classList.add('hidden');
            }, 2000);
        } else {
            statusElement.classList.remove('hidden');
        }
    }

    // Public methods for subscribing to events
    on(eventType, callback) {
        if (!this.listeners.has(eventType)) {
            this.listeners.set(eventType, []);
        }
        this.listeners.get(eventType).push(callback);
    }

    off(eventType, callback) {
        if (this.listeners.has(eventType)) {
            const callbacks = this.listeners.get(eventType);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.close(1000, 'Manual disconnect');
            this.socket = null;
        }
    }
}

// Initialize WebSocket client when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if user is authenticated
    if (document.body.dataset.authenticated === 'true') {
        window.wsClient = new WebSocketClient();
        
        // Make it available globally
        window.SpeedDatingApp = window.SpeedDatingApp || {};
        window.SpeedDatingApp.ws = window.wsClient;
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.wsClient) {
        window.wsClient.disconnect();
    }
});