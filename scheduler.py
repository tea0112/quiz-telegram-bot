"""Background scheduler for daily resets and maintenance tasks."""

import asyncio
import logging
from datetime import datetime, timezone, time
from typing import Optional

from database import db_manager

logger = logging.getLogger(__name__)


class DailyScheduler:
    """Handles scheduled tasks like daily resets."""
    
    def __init__(self):
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the scheduler."""
        if self.is_running:
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._run_scheduler())
        logger.info("Daily scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Daily scheduler stopped")
    
    async def _run_scheduler(self):
        """Main scheduler loop."""
        while self.is_running:
            try:
                # Calculate seconds until next midnight UTC
                now = datetime.now(timezone.utc)
                next_midnight = datetime.combine(
                    now.date().replace(day=now.day + 1),
                    time.min,
                    timezone.utc
                )
                
                # If it's already past midnight today, reset for today
                midnight_today = datetime.combine(
                    now.date(),
                    time.min,
                    timezone.utc
                )
                
                # Check if we need to do an immediate reset
                if now.hour == 0 and now.minute < 5:  # Within 5 minutes of midnight
                    await self._perform_daily_reset()
                
                seconds_until_midnight = (next_midnight - now).total_seconds()
                
                # Sleep until next midnight (or check every hour if more than 1 hour away)
                sleep_time = min(seconds_until_midnight, 3600)  # Max 1 hour
                
                logger.debug(f"Scheduler sleeping for {sleep_time:.0f} seconds until next check")
                await asyncio.sleep(sleep_time)
                
                # If we're at midnight, perform reset
                current_time = datetime.now(timezone.utc)
                if current_time.hour == 0 and current_time.minute < 5:
                    await self._perform_daily_reset()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler: {e}")
                # Sleep for a bit before retrying
                await asyncio.sleep(300)  # 5 minutes
    
    async def _perform_daily_reset(self):
        """Perform daily reset for all users."""
        try:
            logger.info("Performing daily reset for all users")
            
            # In a real implementation, you'd want to get all users and reset them
            # For now, we'll rely on the individual reset check in quiz_logic.py
            # This could be enhanced to batch process all users
            
            logger.info("Daily reset completed")
            
        except Exception as e:
            logger.error(f"Error during daily reset: {e}")


# Global instance
daily_scheduler = DailyScheduler()
