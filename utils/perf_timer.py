"""
Performance Timer Utility

A simple utility class to measure and log execution time of code blocks.

Usage:
    from utils.perf_timer import PerfTimer
    
    timer = PerfTimer("My Operation")
    timer.start_ticker()
    
    # ... some code ...
    timer.settick("Step 1 completed")
    
    # ... more code ...
    timer.settick("Step 2 completed")
    
    # ... final code ...
    timer.end_ticker("Operation finished")
"""

import time


class PerfTimer:
    """
    Performance timer for tracking execution time of operations.
    
    Provides methods to start timing, log intermediate checkpoints,
    and end timing with console output.
    """
    
    def __init__(self, name: str = "Timer"):
        """
        Initialize the performance timer.
        
        Args:
            name: A descriptive name for this timer (used in log outputs)
        """
        self.name = name
        self.start_time = None
        self.last_tick_time = None
        self.is_running = False
    
    def start_ticker(self, message: str = "Started"):
        """
        Start the performance timer.
        
        Args:
            message: Optional message to log when starting
        """
        self.start_time = time.perf_counter()
        self.last_tick_time = self.start_time
        self.is_running = True
        print(f"[PERF][{self.name}] {message} at {time.strftime('%H:%M:%S')}")
    
    def settick(self, label: str = "Checkpoint"):
        """
        Log an intermediate checkpoint without stopping the timer.
        
        Logs:
        - Time since last tick (or start)
        - Total elapsed time since start
        
        Args:
            label: Description of this checkpoint
        """
        if not self.is_running:
            print(f"[PERF][{self.name}] ERROR: Timer not started. Call start_ticker() first.")
            return
        
        current_time = time.perf_counter()
        since_last = (current_time - self.last_tick_time) * 1000  # Convert to ms
        total_elapsed = (current_time - self.start_time) * 1000  # Convert to ms
        
        # Format times intelligently (ms for < 1000ms, seconds otherwise)
        if since_last < 1000:
            since_last_str = f"{since_last:.2f}ms"
        else:
            since_last_str = f"{since_last / 1000:.3f}s"
        
        if total_elapsed < 1000:
            total_elapsed_str = f"{total_elapsed:.2f}ms"
        else:
            total_elapsed_str = f"{total_elapsed / 1000:.3f}s"
        
        print(f"[PERF][{self.name}] {label} | +{since_last_str} | Total: {total_elapsed_str}")
        
        self.last_tick_time = current_time
    
    def end_ticker(self, message: str = "Completed"):
        """
        End the performance timer and log final results.
        
        Args:
            message: Final message to log
        """
        if not self.is_running:
            print(f"[PERF][{self.name}] ERROR: Timer not started. Call start_ticker() first.")
            return
        
        end_time = time.perf_counter()
        since_last = (end_time - self.last_tick_time) * 1000  # Convert to ms
        total_elapsed = (end_time - self.start_time) * 1000  # Convert to ms
        
        # Format times intelligently
        if since_last < 1000:
            since_last_str = f"{since_last:.2f}ms"
        else:
            since_last_str = f"{since_last / 1000:.3f}s"
        
        if total_elapsed < 1000:
            total_elapsed_str = f"{total_elapsed:.2f}ms"
        else:
            total_elapsed_str = f"{total_elapsed / 1000:.3f}s"
        
        print(f"[PERF][{self.name}] {message} | +{since_last_str} | ⏱️  TOTAL: {total_elapsed_str}")
        
        self.is_running = False
        self.start_time = None
        self.last_tick_time = None


# Example usage
if __name__ == "__main__":
    # Simple example
    timer = PerfTimer("Example Operation")
    timer.start_ticker("Beginning work")
    
    time.sleep(0.1)
    timer.settick("Step 1: Data loaded")
    
    time.sleep(0.05)
    timer.settick("Step 2: Processing done")
    
    time.sleep(0.02)
    timer.end_ticker("All work completed")
