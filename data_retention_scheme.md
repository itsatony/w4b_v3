# Revised Data Retention Scheme

| Time Period | Sensor Data Frequency | Image Frequency | Additional Data |
|-------------|------------------------|------------------|-----------------|
| Last 30 hours (day: 04:00-22:00) | Every 1 minute | Every 20 minutes | Highs and lows per unit |
| Last 30 hours (night: 22:00-04:00) | Every 10 minutes | Once at 00:00 | Highs and lows per unit |
| Last 70 days | 20-minute averages | Every 3 days (day only) | Daily highs and lows per unit |
| 70 days to 13 months | 6 hour averages (4 per day) | Weekly at noon | Daily highs and lows per unit |
| Older than 13 months | Daily average (1 day, 1 night) | None | Daily highs and lows per unit |

For audio, we follow a 2-level pre-filter approach on the edge device:

1. First Level (Always-On):

Low-resource amplitude monitoring
Basic frequency band monitoring (bee sounds typically 200-500Hz)
Uses minimal processing power

2. Second Level (Triggered Analysis):

Activated when first level detects potential interest
More sophisticated frequency analysis
Pattern matching against known bee sounds
Human voice filtering (typically 85-255Hz)

3. Upon event detection, a 10-second audio clip is captured and stored in the DB.

[ai discussion for audio prefiltering](https://claude.ai/chat/fa850047-6c85-4517-950f-39d36af9f9d6)

## Additional Data Retention Rules

1. Temperature spikes: If temperature changes by more than 5°C in an hour, increase sensor data frequency to every 1 minute for the next hour.
2. Rainfall events: During detected rainfall, increase sensor data frequency to every 5 minutes for the duration of the event.
3. User-triggered high-resolution mode: Allow beekeepers to manually trigger a 20min high-resolution mode (20sec sensor intervals, manual image-capture) for specific activities like hive inspections.
4. Anomaly detection: If any sensor detects values outside of predefined normal ranges, automatically increase data collection frequency for all sensors on that hive for the next hour.

## Data Reduction Techniques

1. Use delta encoding for sensor data to only store changes in values.
2. Implement lossy compression for images, favoring smaller file sizes over perfect quality.
3. For long-term storage, only keep data points that represent significant changes or daily min/max values.
4. Use a rolling window to calculate averages and discard old data points.
