#!/usr/bin/env python3
"""
Database Index Migration Script for CHSH Game

Adds performance indexes to the database to optimize query performance,
particularly for dashboard queries and game statistics.

Usage:
    python migrations/add_database_indexes.py
"""

import sys
import os
import logging
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project root to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import db, app

def add_database_indexes():
    """Add performance indexes to the database."""
    logger.info("Adding database indexes for performance optimization...")
    
    with app.app_context():
        # Get database engine name
        engine_name = db.engine.name
        logger.info(f"Database engine: {engine_name}")
        
        # Define indexes based on common query patterns
        indexes = [
            # Teams table indexes
            "CREATE INDEX IF NOT EXISTS idx_teams_active ON teams(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_teams_created_at ON teams(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_teams_player_sessions ON teams(player1_session_id, player2_session_id);",
            
            # PairQuestionRounds table indexes  
            "CREATE INDEX IF NOT EXISTS idx_rounds_team_id ON pair_question_rounds(team_id);",
            "CREATE INDEX IF NOT EXISTS idx_rounds_team_round ON pair_question_rounds(team_id, round_number_for_team);",
            "CREATE INDEX IF NOT EXISTS idx_rounds_created_at ON pair_question_rounds(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_rounds_items ON pair_question_rounds(player1_item, player2_item);",
            
            # Answers table indexes
            "CREATE INDEX IF NOT EXISTS idx_answers_round_id ON answers(round_id);",
            "CREATE INDEX IF NOT EXISTS idx_answers_player_session ON answers(player_session_id);",
            "CREATE INDEX IF NOT EXISTS idx_answers_round_player ON answers(round_id, player_session_id);",
            "CREATE INDEX IF NOT EXISTS idx_answers_created_at ON answers(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_answers_answer_value ON answers(answer);",
            
            # Composite indexes for complex queries
            "CREATE INDEX IF NOT EXISTS idx_rounds_answers_join ON pair_question_rounds(round_id, team_id);",
            "CREATE INDEX IF NOT EXISTS idx_team_stats_query ON teams(team_id, is_active, created_at);",
        ]
        
        # SQLite specific indexes (if needed)
        if engine_name == 'sqlite':
            sqlite_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_teams_name_active ON teams(team_name, is_active);",
            ]
            indexes.extend(sqlite_indexes)
        
        # PostgreSQL specific indexes (if needed)
        elif engine_name == 'postgresql':
            postgres_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_teams_name_active ON teams(team_name, is_active);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rounds_team_created ON pair_question_rounds(team_id, created_at DESC);",
            ]
            indexes.extend(postgres_indexes)
        
        # Execute index creation
        success_count = 0
        for index_sql in indexes:
            try:
                logger.info(f"Creating index: {index_sql}")
                db.session.execute(text(index_sql))
                logger.info("✓ Index created successfully")
                success_count += 1
            except Exception as e:
                logger.warning(f"⚠ Warning: Could not create index: {str(e)}")
                # Continue with other indexes even if one fails
                continue
        
        # Commit all changes
        db.session.commit()
        
        logger.info(f"\n✅ Database indexes added successfully!")
        logger.info("Database query performance should now be significantly improved.")
        
    except Exception as e:
        logger.error(f"❌ Error adding database indexes: {str(e)}")
        if 'db' in locals():
            db.session.rollback()
        raise

def check_existing_indexes():
    """Check what indexes already exist in the database."""
    try:
        with app.app_context():
            engine_name = db.engine.name
            
            logger.info("Checking existing indexes...")
            
            if engine_name == 'sqlite':
                # SQLite query to list indexes
                result = db.session.execute(text("""
                    SELECT name, tbl_name 
                    FROM sqlite_master 
                    WHERE type = 'index' 
                    AND name NOT LIKE 'sqlite_autoindex%'
                    ORDER BY tbl_name, name;
                """))
                
            elif engine_name == 'postgresql':
                # PostgreSQL query to list indexes
                result = db.session.execute(text("""
                    SELECT indexname, tablename 
                    FROM pg_indexes 
                    WHERE schemaname = 'public'
                    AND indexname NOT LIKE '%pkey'
                    ORDER BY tablename, indexname;
                """))
            else:
                logger.warning(f"Unsupported database engine: {engine_name}")
                return
            
            indexes = result.fetchall()
            
            logger.info("\nExisting indexes:")
            for idx in indexes:
                logger.info(f"  - {idx[0]} on {idx[1]}")
            
            if not indexes:
                logger.info("No custom indexes found.")
                
    except Exception as e:
        logger.error(f"Error checking existing indexes: {str(e)}")

if __name__ == "__main__":
    logger.info("CHSH-Game Database Index Migration")
    logger.info("=" * 40)
    
    try:
        # Check existing indexes first
        check_existing_indexes()
        
        logger.info("This will add performance indexes to your database.")
        
        # Add the indexes
        add_database_indexes()
        
    except KeyboardInterrupt:
        logger.info("Migration cancelled.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)