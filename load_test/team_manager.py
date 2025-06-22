"""
Team management for CHSH Game load testing.

Handles team creation, player assignment, and coordination.
"""

import asyncio
import random
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from faker import Faker
from loguru import logger

from .config import LoadTestConfig, ConnectionStrategy
from .player import Player, PlayerState
from .metrics import LoadTestMetrics


@dataclass
class Team:
    """Represents a team in the load test."""
    name: str
    creator: Player
    joiner: Optional[Player] = None
    created_at: Optional[float] = None
    paired_at: Optional[float] = None
    
    @property
    def is_complete(self) -> bool:
        """Check if team has both players."""
        return self.joiner is not None
    
    @property
    def players(self) -> List[Player]:
        """Get all players in the team."""
        players = [self.creator]
        if self.joiner:
            players.append(self.joiner)
        return players


class TeamManager:
    """
    Manages team creation and player coordination for load testing.
    """
    
    def __init__(self, config: LoadTestConfig, metrics: LoadTestMetrics):
        self.config = config
        self.metrics = metrics
        self.fake = Faker()
        
        # Team tracking
        self.teams: List[Team] = []
        self.players: List[Player] = []
        
        # Connection management
        self.connection_semaphore = asyncio.Semaphore(20)  # Limit concurrent operations
        
        # Shutdown flag
        self.should_shutdown = False
    
    async def create_players(self) -> List[Player]:
        """
        Create all player instances for the load test.
        
        Returns:
            List of created Player instances
        """
        total_players = self.config.total_players
        logger.info(f"Creating {total_players} players for {self.config.num_teams} teams")
        
        players = []
        for i in range(total_players):
            player_id = f"player_{i+1:04d}"
            player = Player(
                player_id=player_id,
                config=self.config,
                metrics_callback=self.metrics.record_event
            )
            
            # Add to metrics tracking
            self.metrics.add_player(player_id)
            players.append(player)
        
        self.players = players
        
        # Establish connections for all players
        logger.info("Establishing connections for all players...")
        success_rate = await self.establish_connections()
        logger.info(f"Connection establishment completed with {success_rate:.1%} success rate")
        
        return players
    
    async def establish_connections(self) -> float:
        """
        Establish Socket.io connections for all players.
        
        Returns:
            Success rate (0.0 to 1.0)
        """
        logger.info(f"Establishing connections using {self.config.connection_strategy.value} strategy")
        
        if self.config.connection_strategy == ConnectionStrategy.IMMEDIATE:
            return await self._connect_immediate()
        elif self.config.connection_strategy == ConnectionStrategy.BURST:
            return await self._connect_burst()
        else:  # GRADUAL
            return await self._connect_gradual()
    
    async def _connect_immediate(self) -> float:
        """Connect all players simultaneously."""
        logger.info("Connecting all players immediately")
        
        tasks = []
        for player in self.players:
            if self.should_shutdown:
                break
            task = asyncio.create_task(self._connect_player_with_semaphore(player))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = sum(1 for result in results if result is True)
        
        success_rate = successful / len(self.players) if self.players else 0.0
        logger.info(f"Immediate connection: {successful}/{len(self.players)} successful ({success_rate:.1%})")
        
        return success_rate
    
    async def _connect_burst(self) -> float:
        """Connect players in bursts."""
        batch_size = self.config.burst_size
        delay_between_batches = 2.0  # 2 second delay between bursts
        
        logger.info(f"Connecting players in bursts of {batch_size}")
        
        successful = 0
        total = len(self.players)
        
        for i in range(0, total, batch_size):
            if self.should_shutdown:
                break
                
            batch = self.players[i:i + batch_size]
            logger.debug(f"Connecting batch {i//batch_size + 1}: players {i+1}-{min(i+batch_size, total)}")
            
            # Connect batch
            tasks = [self._connect_player_with_semaphore(player) for player in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            batch_successful = sum(1 for result in results if result is True)
            successful += batch_successful
            
            logger.debug(f"Batch {i//batch_size + 1}: {batch_successful}/{len(batch)} successful")
            
            # Delay before next batch (except for last batch)
            if i + batch_size < total and not self.should_shutdown:
                await asyncio.sleep(delay_between_batches)
        
        success_rate = successful / total if total > 0 else 0.0
        logger.info(f"Burst connection: {successful}/{total} successful ({success_rate:.1%})")
        
        return success_rate
    
    async def _connect_gradual(self) -> float:
        """Connect players gradually at specified rate."""
        rate = self.config.connections_per_second
        delay = 1.0 / rate
        
        logger.info(f"Connecting players gradually at {rate}/second")
        
        successful = 0
        total = len(self.players)
        
        for i, player in enumerate(self.players):
            if self.should_shutdown:
                break
                
            # Connect player
            result = await self._connect_player_with_semaphore(player)
            if result:
                successful += 1
            
            # Progress logging
            if (i + 1) % 50 == 0 or i == total - 1:
                logger.debug(f"Connected {i+1}/{total} players ({successful} successful)")
            
            # Rate limiting delay (except for last player)
            if i < total - 1 and not self.should_shutdown:
                await asyncio.sleep(delay)
        
        success_rate = successful / total if total > 0 else 0.0
        logger.info(f"Gradual connection: {successful}/{total} successful ({success_rate:.1%})")
        
        return success_rate
    
    async def _connect_player_with_semaphore(self, player: Player) -> bool:
        """Connect a single player with semaphore protection."""
        async with self.connection_semaphore:
            return await player.connect()
    
    async def create_teams(self) -> List[Team]:
        """
        Create teams and assign players.
        
        Returns:
            List of created teams
        """
        logger.info(f"Creating {self.config.num_teams} teams")
        
        # Filter connected players
        connected_players = [p for p in self.players if p.state == PlayerState.CONNECTED]
        
        if len(connected_players) < self.config.total_players:
            logger.warning(f"Only {len(connected_players)} players connected, expected {self.config.total_players}")
        
        if len(connected_players) < 2:
            raise RuntimeError("Need at least 2 connected players to create teams")
        
        # Create teams
        teams = []
        for i in range(min(self.config.num_teams, len(connected_players) // 2)):
            if self.should_shutdown:
                break
                
            # Get next two players
            creator = connected_players[i * 2]
            joiner = connected_players[i * 2 + 1]
            
            # Generate unique team name
            team_name = self._generate_team_name()
            
            # Create team
            team = Team(name=team_name, creator=creator, joiner=joiner)
            teams.append(team)
        
        self.teams = teams
        logger.info(f"Created {len(teams)} teams")
        
        # Execute team creation
        await self._execute_team_creation()
        
        return teams
    
    def _generate_team_name(self) -> str:
        """Generate a unique team name."""
        existing_names = {team.name for team in self.teams}
        
        attempts = 0
        while attempts < 100:  # Prevent infinite loop
            # Generate name using faker with valid methods
            try:
                if random.choice([True, False]):
                    # Use first_name and last_name for more natural combinations
                    first_part = self.fake.first_name().title()
                    second_part = self.fake.last_name().title()
                    name = f"{first_part}{second_part}"
                else:
                    # Use color_name and company for variety
                    color = self.fake.color_name().title()
                    company = self.fake.company().replace(' ', '').replace(',', '').replace('.', '')
                    name = f"{color}{company}"[:20]  # Limit length
            except AttributeError:
                # Fallback to simple word generation if methods don't exist
                name = f"Team{self.fake.random_int(min=1000, max=9999)}"
            
            # Add random number to ensure uniqueness
            name = f"{name}{random.randint(100, 999)}"
            
            if name not in existing_names:
                return name
            
            attempts += 1
        
        # Fallback to guaranteed unique name
        return f"Team{len(self.teams) + 1:04d}"
    
    async def _execute_team_creation(self):
        """Execute the actual team creation process."""
        logger.info("Executing team creation on server")
        
        # Create teams sequentially to avoid server overload
        successful_teams = 0
        
        for i, team in enumerate(self.teams):
            if self.should_shutdown:
                break
                
            try:
                # Creator creates the team
                success = await team.creator.create_team(team.name)
                if not success:
                    logger.warning(f"Team {team.name} creation failed")
                    continue
                
                team.created_at = asyncio.get_event_loop().time()
                
                # Short delay before joiner joins
                await asyncio.sleep(0.5)
                
                # Joiner joins the team
                if team.joiner is not None:
                    success = await team.joiner.join_team(team.name)
                    if not success:
                        logger.warning(f"Team {team.name} join failed")
                        continue
                else:
                    logger.warning(f"Team {team.name} has no joiner")
                    continue
                
                team.paired_at = asyncio.get_event_loop().time()
                successful_teams += 1
                
                logger.debug(f"Team {team.name} created and paired successfully ({i+1}/{len(self.teams)})")
                
                # Small delay between team operations
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error creating team {team.name}: {str(e)}")
        
        logger.info(f"Successfully created and paired {successful_teams}/{len(self.teams)} teams")
    
    async def wait_for_game_start(self, timeout: float = 60.0) -> bool:
        """
        Wait for the game to start.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if game started, False if timeout
        """
        logger.info("Waiting for game to start...")
        
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.should_shutdown:
                return False
                
            # Check if any player reports game started
            for player in self.players:
                if player.game_started:
                    logger.info("Game start detected!")
                    self.metrics.record_game_start()
                    return True
            
            await asyncio.sleep(0.5)
        
        logger.warning(f"Game start timeout after {timeout}s")
        return False
    
    async def monitor_game_progress(self):
        """Monitor ongoing game progress."""
        logger.info("Monitoring game progress...")
        
        last_report_time = asyncio.get_event_loop().time()
        report_interval = 30.0  # Report every 30 seconds
        
        while not self.should_shutdown:
            current_time = asyncio.get_event_loop().time()
            
            # Periodic progress report
            if current_time - last_report_time >= report_interval:
                self._log_progress_report()
                last_report_time = current_time
            
            # Check if test should end
            if self._should_end_test():
                logger.info("Test completion criteria met")
                break
            
            await asyncio.sleep(5.0)  # Check every 5 seconds
    
    def _log_progress_report(self):
        """Log current progress statistics."""
        connected_players = len([p for p in self.players if p.state != PlayerState.DISCONNECTED])
        total_rounds = sum(p.rounds_completed for p in self.players)
        total_answers = sum(p.metrics.answers_submitted for p in self.players)
        
        logger.info(f"Progress: {connected_players} players connected, "
                   f"{total_rounds} rounds completed, {total_answers} answers submitted")
    
    def _should_end_test(self) -> bool:
        """Check if test should end based on criteria."""
        # Check max duration
        elapsed = asyncio.get_event_loop().time() - self.metrics.start_time
        if elapsed >= self.config.max_test_duration:
            logger.info(f"Maximum test duration ({self.config.max_test_duration}s) reached")
            return True
        
        # Check if any team reached max rounds
        max_rounds_reached = any(
            p.rounds_completed >= self.config.max_rounds_per_team 
            for p in self.players
        )
        if max_rounds_reached:
            logger.info(f"Maximum rounds per team ({self.config.max_rounds_per_team}) reached")
            return True
        
        # Check if too many players disconnected
        connected_players = len([p for p in self.players if p.state != PlayerState.DISCONNECTED])
        if connected_players < len(self.players) * 0.5:  # Less than 50% connected
            logger.warning("More than 50% of players disconnected, ending test")
            return True
        
        return False
    
    async def shutdown(self):
        """Gracefully shutdown all players and teams."""
        logger.info("Shutting down team manager...")
        self.should_shutdown = True
        
        # Disconnect all players
        disconnect_tasks = []
        for player in self.players:
            task = asyncio.create_task(player.disconnect())
            disconnect_tasks.append(task)
        
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        
        logger.info("Team manager shutdown complete")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of all teams and players."""
        return {
            'total_teams': len(self.teams),
            'complete_teams': len([t for t in self.teams if t.is_complete]),
            'total_players': len(self.players),
            'connected_players': len([p for p in self.players if p.state == PlayerState.CONNECTED]),
            'players_in_teams': len([p for p in self.players if p.team_name is not None]),
            'total_rounds_completed': sum(p.rounds_completed for p in self.players),
            'teams': [
                {
                    'name': team.name,
                    'complete': team.is_complete,
                    'creator_id': team.creator.player_id,
                    'joiner_id': team.joiner.player_id if team.joiner else None,
                    'rounds_completed': sum(p.rounds_completed for p in team.players)
                }
                for team in self.teams
            ]
        }