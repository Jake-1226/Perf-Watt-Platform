# Frontend Architecture

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Last Updated:** March 4, 2026

## Overview

The frontend is a single-page React application that provides a modern, responsive interface for the Performance Test Platform. It uses HTM (Hyperscript Tagged Markup) instead of JSX, eliminating the need for a build step while maintaining full React functionality.

## Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Framework** | React | 18.2.0 | Component-based UI framework |
| **Markup** | HTM | Latest | JSX alternative, no build step |
| **Styling** | Tailwind CSS | 3.4+ | Utility-first CSS framework |
| **Charts** | Recharts | 2.13.3 | Data visualization |
| **HTTP Client** | Fetch API | Native | API communication |
| **WebSocket** | WebSocket API | Native | Real-time data streaming |
| **Icons** | Lucide React | Latest | Icon components |

## Application Structure

### Single File Architecture

The entire frontend is contained in a single `static/index.html` file:

```html
<!DOCTYPE html>
<html>
<head>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- React and dependencies -->
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    
    <!-- HTM for JSX without build step -->
    <script src="https://unpkg.com/htm@3.1.1/dist/htm.umd.js"></script>
    
    <!-- Recharts for data visualization -->
    <script src="https://unpkg.com/recharts@2.13.3/umd/Recharts.js"></script>
    
    <!-- Lucide icons -->
    <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
</head>
<body>
    <div id="root"></div>
    <script src="index.js"></script>
</body>
</html>
```

### Component Architecture

The application follows a tab-based navigation pattern with six main sections:

```javascript
// Main App Component
const App = () => {
    const [activeTab, setActiveTab] = useState('home');
    const [configs, setConfigs] = useState([]);
    const [currentConfig, setCurrentConfig] = useState(null);
    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    // ... other state
    
    return html`
        <div className="min-h-screen bg-gray-50">
            ${Header({ activeTab, setActiveTab })}
            ${renderActiveTab()}
        </div>
    `;
};
```

## Tab-Based Navigation

### 1. Home Tab
- **Purpose**: Landing page with saved configurations and recent runs
- **Components**: ConfigGrid, RecentRunsTable, QuickActions
- **Functionality**: 
  - Display saved server configurations
  - Show recent test runs with status
  - Quick access to common actions

### 2. Connect Tab
- **Purpose**: Establish connections to target servers
- **Components**: ConnectionForm, ConnectionStatus, TestConnection
- **Functionality**:
  - Add/edit server configurations
  - Test SSH connections to OS and iDRAC
  - Save connection profiles

### 3. Sanity Tab
- **Purpose**: Verify system readiness and tool availability
- **Components**: SystemInfo, ToolCheck, SensorCheck
- **Functionality**:
  - Display system information (CPU, memory, storage)
  - Verify benchmark tool availability
  - Test iDRAC sensor access

### 4. Config Tab
- **Purpose**: Configure test parameters and phases
- **Components**: PhaseConfig, DurationSettings, AdvancedOptions
- **Functionality**:
  - Set phase durations and rest periods
  - Customize phase sequence
  - Configure benchmark parameters

### 5. Dashboard Tab
- **Purpose**: Real-time monitoring during test execution
- **Components**: LiveCharts, MetricCards, LogViewer, PhaseProgress
- **Functionality**:
  - Real-time charts for CPU, memory, power
  - Live log streaming
  - Phase progress indicators
  - Test control buttons

### 6. Report Tab
- **Purpose**: Generate and download test reports
- **Components**: ReportGenerator, ReportPreview, DownloadButton
- **Functionality**:
  - Generate Excel reports
  - Preview report contents
  - Download reports and data exports

## State Management

### Global State Pattern

The application uses React hooks for state management:

```javascript
// Connection state
const [connectionStatus, setConnectionStatus] = useState('disconnected');
const [currentConfig, setCurrentConfig] = useState(null);

// Test state
const [testStatus, setTestStatus] = useState('idle');
const [currentPhase, setCurrentPhase] = useState(null);
const [runId, setRunId] = useState(null);

// Data state
const [telemetryData, setTelemetryData] = useState([]);
const [systemInfo, setSystemInfo] = useState({});
const [configs, setConfigs] = useState([]);
```

### WebSocket Integration

Real-time data streaming via WebSocket:

```javascript
const useWebSocket = (url) => {
    const [socket, setSocket] = useState(null);
    const [data, setData] = useState(null);
    
    useEffect(() => {
        const ws = new WebSocket(url);
        
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            setData(message);
        };
        
        setSocket(ws);
        return () => ws.close();
    }, [url]);
    
    return { socket, data };
};
```

## Data Visualization

### Chart Components

Using Recharts for real-time data visualization:

```javascript
const CPUChart = ({ data }) => html`
    <${LineChart} width=${600} height=${300} data=${data}>
        <${CartesianGrid} strokeDasharray="3 3" />
        <${XAxis} dataKey="timestamp" />
        <${YAxis} />
        <${Tooltip} />
        <${Legend} />
        <${Line} 
            type="monotone" 
            dataKey="cpu_utilization" 
            stroke="#8884d8" 
            strokeWidth=${2}
        />
    </LineChart>
`;
```

### Chart Types

1. **CPU Utilization Chart**: Line chart showing CPU usage over time
2. **Memory Usage Chart**: Area chart for memory consumption
3. **Power Consumption Chart**: Line chart for power metrics
4. **Temperature Chart**: Multi-line chart for thermal sensors
5. **Phase Progress Chart**: Gantt-style chart for phase timing

## API Integration

### HTTP Client

Using Fetch API for REST API communication:

```javascript
const apiClient = {
    async get(endpoint) {
        const response = await fetch(`/api${endpoint}`);
        return response.json();
    },
    
    async post(endpoint, data) {
        const response = await fetch(`/api${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return response.json();
    },
    
    async delete(endpoint) {
        const response = await fetch(`/api${endpoint}`, {
            method: 'DELETE'
        });
        return response.json();
    }
};
```

### API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/configs` | GET | List saved configurations |
| `/api/configs` | POST | Save new configuration |
| `/api/configs/{id}` | DELETE | Delete configuration |
| `/api/connect` | POST | Establish connection |
| `/api/sanity_check` | POST | Run system sanity check |
| `/api/test/start` | POST | Start test execution |
| `/api/test/stop` | POST | Stop test execution |
| `/api/test/status` | GET | Get test status |
| `/api/telemetry/latest` | GET | Get latest telemetry data |
| `/api/report/generate` | POST | Generate report |

## Error Handling

### Error Boundary

React Error Boundary for graceful error handling:

```javascript
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }
    
    static getDerivedStateFromError(error) {
        return { hasError: true };
    }
    
    componentDidCatch(error, errorInfo) {
        console.error('Frontend Error:', error, errorInfo);
    }
    
    render() {
        if (this.state.hasError) {
            return html`
                <div className="p-4 bg-red-50 border border-red-200 rounded">
                    <h3 className="text-red-800 font-semibold">Something went wrong</h3>
                    <p className="text-red-600">Please refresh the page and try again.</p>
                </div>
            `;
        }
        
        return this.props.children;
    }
}
```

### Network Error Handling

Graceful handling of network issues:

```javascript
const withErrorHandling = (asyncFunction) => {
    return async (...args) => {
        try {
            return await asyncFunction(...args);
        } catch (error) {
            console.error('API Error:', error);
            showNotification('An error occurred. Please try again.', 'error');
            throw error;
        }
    };
};
```

## Responsive Design

### Tailwind CSS Breakpoints

```css
/* Tailwind CSS breakpoints used */
sm: 640px   /* Small screens */
md: 768px   /* Medium screens */
lg: 1024px  /* Large screens */
xl: 1280px  /* Extra large screens */
2xl: 1536px /* 2X large screens */
```

### Responsive Patterns

```javascript
const ResponsiveGrid = ({ children }) => html`
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        ${children}
    </div>
`;
```

## Performance Optimization

### Code Splitting

Although using a single file, the application loads dependencies efficiently:

```html
<!-- Load critical CSS first -->
<link href="https://cdn.tailwindcss.com" rel="stylesheet">

<!-- Load React and dependencies -->
<script async src="https://unpkg.com/react@18/umd/react.production.min.js"></script>

<!-- Load charts and visualization libraries -->
<script async src="https://unpkg.com/recharts@2.13.3/umd/Recharts.js"></script>
```

### Memory Management

Efficient data handling for real-time updates:

```javascript
const useTelemetryData = () => {
    const [data, setData] = useState([]);
    const maxDataPoints = 1000; // Limit data points for performance
    
    const addDataPoint = useCallback((newPoint) => {
        setData(prevData => {
            const updated = [...prevData, newPoint];
            return updated.slice(-maxDataPoints); // Keep only recent data
        });
    }, [maxDataPoints]);
    
    return { data, addDataPoint };
};
```

## Accessibility

### ARIA Labels

Semantic HTML with proper ARIA labels:

```javascript
const AccessibleButton = ({ children, onClick, disabled = false }) => html`
    <button
        onClick=${onClick}
        disabled=${disabled}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
        aria-label=${children}
        role="button"
    >
        ${children}
    </button>
`;
```

### Keyboard Navigation

Full keyboard support for all interactive elements:

```javascript
const KeyboardNavigation = () => {
    useEffect(() => {
        const handleKeyDown = (event) => {
            if (event.key === 'Tab') {
                // Handle tab navigation
            }
            if (event.key === 'Enter') {
                // Handle enter key
            }
        };
        
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, []);
};
```

## Development Guidelines

### Code Organization

1. **Component Naming**: PascalCase for components
2. **File Structure**: Logical grouping of related components
3. **State Management**: Keep state close to where it's used
4. **Props Interface**: Clear prop documentation

### Styling Conventions

1. **Utility Classes**: Use Tailwind utilities
2. **Responsive Design**: Mobile-first approach
3. **Color Scheme**: Consistent color palette
4. **Spacing**: Use Tailwind spacing scale

### Performance Best Practices

1. **Lazy Loading**: Load components as needed
2. **Memoization**: Use React.memo for expensive components
3. **Debouncing**: Debounce user inputs
4. **Virtual Scrolling**: For large data lists

## Browser Compatibility

### Supported Browsers

- **Chrome**: 90+
- **Firefox**: 88+
- **Safari**: 14+
- **Edge**: 90+

### Feature Detection

```javascript
const checkBrowserSupport = () => {
    const features = {
        websockets: typeof WebSocket !== 'undefined',
        fetch: typeof fetch !== 'undefined',
        localStorage: typeof localStorage !== 'undefined'
    };
    
    const unsupported = Object.entries(features)
        .filter(([_, supported]) => !supported)
        .map(([feature]) => feature);
    
    if (unsupported.length > 0) {
        showNotification(`Unsupported features: ${unsupported.join(', ')}`, 'error');
    }
};
```

## Future Enhancements

### Planned Improvements

1. **Progressive Web App**: Add PWA capabilities
2. **Offline Support**: Cache critical resources
3. **Dark Mode**: Add theme switching
4. **Advanced Charts**: More sophisticated visualizations
5. **Export Options**: Additional export formats

### Technical Debt

1. **Build Process**: Consider adding build step for optimization
2. **TypeScript**: Add TypeScript for better type safety
3. **Testing**: Add unit and integration tests
4. **Documentation**: Inline code documentation
