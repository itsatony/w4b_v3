#!/usr/bin/env python3
"""
Prometheus metrics for the w4b sensor management system.

This module provides a centralized interface for creating and managing
Prometheus metrics throughout the sensor management system.
"""

import logging
from typing import Dict, Any, Optional
import functools

from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server


class MetricsManager:
    """
    Centralized manager for Prometheus metrics.
    
    This class provides a unified interface for creating, accessing, and
    updating Prometheus metrics throughout the application, ensuring
    consistent naming and labeling.
    
    Attributes:
        metrics (Dict[str, Any]): Dictionary of all registered metrics
        prefix (str): Prefix for all metric names
        default_labels (Dict[str, str]): Labels to apply to all metrics
        logger (logging.Logger): Logger for metrics operations
    """
    
    def __init__(
        self,
        prefix: str = "w4b",
        default_labels: Optional[Dict[str, str]] = None
    ):
        """
        Initialize metrics manager.
        
        Args:
            prefix: Prefix for all metric names
            default_labels: Labels to apply to all metrics
        """
        self.metrics = {}
        self.prefix = prefix
        self.default_labels = default_labels or {}
        self.logger = logging.getLogger("monitoring.metrics")
        
    def start_server(self, port: int = 9100) -> None:
        """
        Start the Prometheus metrics HTTP server.
        
        Args:
            port: HTTP port to listen on
        """
        self.logger.info(f"Starting Prometheus metrics server on port {port}")
        start_http_server(port)
        
    def _full_name(self, name: str) -> str:
        """
        Generate a fully-qualified metric name with prefix.
        
        Args:
            name: Base metric name
            
        Returns:
            str: Full metric name with prefix
        """
        return f"{self.prefix}_{name}"
        
    def create_counter(
        self,
        name: str,
        description: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Counter:
        """
        Create a Prometheus Counter.
        
        Args:
            name: Metric name without prefix
            description: Metric description
            labels: Label names for this counter
            
        Returns:
            Counter: Newly created counter
        """
        full_name = self._full_name(name)
        
        # Combine default and metric-specific labels
        all_labels = {**self.default_labels}
        if labels:
            label_names = list(labels.keys())
        else:
            label_names = list(all_labels.keys())
            
        # Create the counter
        counter = Counter(
            full_name,
            description,
            label_names
        )
        
        # Store in metrics dict
        self.metrics[name] = counter
        self.logger.debug(f"Created counter {full_name}")
        
        return counter
        
    def create_gauge(
        self,
        name: str,
        description: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Gauge:
        """
        Create a Prometheus Gauge.
        
        Args:
            name: Metric name without prefix
            description: Metric description
            labels: Label names for this gauge
            
        Returns:
            Gauge: Newly created gauge
        """
        full_name = self._full_name(name)
        
        # Combine default and metric-specific labels
        all_labels = {**self.default_labels}
        if labels:
            label_names = list(labels.keys())
        else:
            label_names = list(all_labels.keys())
            
        # Create the gauge
        gauge = Gauge(
            full_name,
            description,
            label_names
        )
        
        # Store in metrics dict
        self.metrics[name] = gauge
        self.logger.debug(f"Created gauge {full_name}")
        
        return gauge
        
    def create_histogram(
        self,
        name: str,
        description: str,
        buckets: Optional[list] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> Histogram:
        """
        Create a Prometheus Histogram.
        
        Args:
            name: Metric name without prefix
            description: Metric description
            buckets: Optional custom buckets
            labels: Label names for this histogram
            
        Returns:
            Histogram: Newly created histogram
        """
        full_name = self._full_name(name)
        
        # Combine default and metric-specific labels
        all_labels = {**self.default_labels}
        if labels:
            label_names = list(labels.keys())
        else:
            label_names = list(all_labels.keys())
            
        # Create the histogram
        kwargs = {"buckets": buckets} if buckets else {}
        histogram = Histogram(
            full_name,
            description,
            label_names,
            **kwargs
        )
        
        # Store in metrics dict
        self.metrics[name] = histogram
        self.logger.debug(f"Created histogram {full_name}")
        
        return histogram
        
    def create_info(
        self,
        name: str,
        description: str
    ) -> Info:
        """
        Create a Prometheus Info metric.
        
        Args:
            name: Metric name without prefix
            description: Metric description
            
        Returns:
            Info: Newly created info metric
        """
        full_name = self._full_name(name)
        
        # Create the info
        info = Info(
            full_name,
            description
        )
        
        # Store in metrics dict
        self.metrics[name] = info
        self.logger.debug(f"Created info {full_name}")
        
        return info
        
    def get(self, name: str) -> Any:
        """
        Get a metric by name.
        
        Args:
            name: Metric name without prefix
            
        Returns:
            The requested metric or None if not found
        """
        return self.metrics.get(name)
        
    def inc_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Increment a counter by name.
        
        Args:
            name: Metric name without prefix
            value: Amount to increment by
            labels: Labels to use for this increment
        """
        counter = self.metrics.get(name)
        if not counter:
            self.logger.warning(f"Attempted to increment non-existent counter: {name}")
            return
            
        if labels:
            counter.labels(**labels).inc(value)
        else:
            counter.inc(value)
            
    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Set a gauge to a specific value.
        
        Args:
            name: Metric name without prefix
            value: Value to set
            labels: Labels to use for this gauge
        """
        gauge = self.metrics.get(name)
        if not gauge:
            self.logger.warning(f"Attempted to set non-existent gauge: {name}")
            return
            
        if labels:
            gauge.labels(**labels).set(value)
        else:
            gauge.set(value)
            
    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record an observation in a histogram.
        
        Args:
            name: Metric name without prefix
            value: Value to observe
            labels: Labels to use for this observation
        """
        histogram = self.metrics.get(name)
        if not histogram:
            self.logger.warning(f"Attempted to observe non-existent histogram: {name}")
            return
            
        if labels:
            histogram.labels(**labels).observe(value)
        else:
            histogram.observe(value)
            
    def set_info(
        self,
        name: str,
        info: Dict[str, str]
    ) -> None:
        """
        Set all values of an info metric.
        
        Args:
            name: Metric name without prefix
            info: Dictionary of info values
        """
        info_metric = self.metrics.get(name)
        if not info_metric:
            self.logger.warning(f"Attempted to set non-existent info: {name}")
            return
            
        info_metric.info(info)
        

# Singleton instance
_instance = None

def get_instance(
    prefix: str = "w4b",
    default_labels: Optional[Dict[str, str]] = None
) -> MetricsManager:
    """
    Get the singleton MetricsManager instance.
    
    Args:
        prefix: Prefix for all metric names
        default_labels: Labels to apply to all metrics
        
    Returns:
        MetricsManager: The singleton instance
    """
    global _instance
    if _instance is None:
        _instance = MetricsManager(prefix, default_labels)
    return _instance


def timing(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """
    Decorator to time a function and record as a histogram.
    
    Args:
        metric_name: Name of the histogram metric
        labels: Optional labels for the metric
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            import time
            
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                metrics = get_instance()
                metrics.observe_histogram(metric_name, duration, labels)
                
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                metrics = get_instance()
                metrics.observe_histogram(metric_name, duration, labels)
                
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


def init_default_metrics(hive_id: str) -> MetricsManager:
    """
    Initialize default metrics for the system.
    
    Args:
        hive_id: ID of the hive
        
    Returns:
        MetricsManager: The metrics manager instance
    """
    metrics = get_instance(default_labels={"hive_id": hive_id})
    
    # System metrics
    metrics.create_info("system_info", "System information")
    metrics.create_gauge("system_uptime", "System uptime in seconds")
    metrics.create_gauge("system_memory_usage", "System memory usage")
    
    # Sensor metrics
    metrics.create_gauge(
        "sensor_status",
        "Sensor operational status (1=OK, 0=Error)",
        {"sensor_id": "", "sensor_type": ""}
    )
    metrics.create_counter(
        "sensor_read_total",
        "Total number of sensor read operations",
        {"sensor_id": "", "status": ""}
    )
    metrics.create_counter(
        "sensor_errors_total",
        "Total number of sensor errors",
        {"sensor_id": "", "error_type": ""}
    )
    metrics.create_histogram(
        "sensor_read_duration",
        "Duration of sensor read operations in seconds",
        [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
        {"sensor_id": ""}
    )
    
    # Database metrics
    metrics.create_gauge(
        "db_connection_status",
        "Database connection status (1=connected, 0=disconnected)"
    )
    metrics.create_counter(
        "db_queries_total",
        "Total number of database queries",
        {"operation": "", "status": ""}
    )
    metrics.create_histogram(
        "db_query_duration",
        "Duration of database queries in seconds",
        [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
        {"operation": ""}
    )
    metrics.create_gauge(
        "db_batch_size",
        "Number of items in the current database batch"
    )
    
    # Collection metrics
    metrics.create_counter(
        "collections_total",
        "Total number of collection cycles"
    )
    metrics.create_gauge(
        "buffer_size",
        "Current buffer size for readings"
    )
    metrics.create_counter(
        "readings_collected_total",
        "Total number of readings collected",
        {"sensor_id": "", "status": ""}
    )
    
    return metrics
