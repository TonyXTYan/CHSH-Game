#!/usr/bin/env python3
"""
Database migration script to add performance indexes
Run this script to add the new indexes to improve query performance.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sys
import os

# Add the parent directory to Python path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import app, db

def add_indexes():
    """Add database indexes for performance optimization."""
    try:
        with app.app_context():
            print("Adding database indexes for performance optimization...")
            
            # Get database connection
            connection = db.engine.connect()
            
            # Check if we're using SQLite or PostgreSQL
            engine_name = db.engine.name
            print(f"Database engine: {engine_name}")
            
            # Define index creation statements
            indexes = [
                # Teams table indexes
                "CREATE INDEX IF NOT EXISTS idx_teams_team_name ON teams (team_name)",
                "CREATE INDEX IF NOT EXISTS idx_teams_is_active ON teams (is_active)",
                "CREATE INDEX IF NOT EXISTS idx_teams_created_at ON teams (created_at)",
                "CREATE INDEX IF NOT EXISTS idx_teams_active_created ON teams (is_active, created_at)",
                
                # Answers table indexes
                "CREATE INDEX IF NOT EXISTS idx_answers_team_id ON answers (team_id)",
                "CREATE INDEX IF NOT EXISTS idx_answers_player_session_id ON answers (player_session_id)",
                "CREATE INDEX IF NOT EXISTS idx_answers_question_round_id ON answers (question_round_id)",
                "CREATE INDEX IF NOT EXISTS idx_answers_assigned_item ON answers (assigned_item)",
                "CREATE INDEX IF NOT EXISTS idx_answers_timestamp ON answers (timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_answers_team_timestamp ON answers (team_id, timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_answers_round_team ON answers (question_round_id, team_id)",
                "CREATE INDEX IF NOT EXISTS idx_answers_team_item ON answers (team_id, assigned_item)",
                
                # PairQuestionRounds table indexes
                "CREATE INDEX IF NOT EXISTS idx_rounds_team_id ON pair_question_rounds (team_id)",
                "CREATE INDEX IF NOT EXISTS idx_rounds_round_number_for_team ON pair_question_rounds (round_number_for_team)",
                "CREATE INDEX IF NOT EXISTS idx_rounds_player1_item ON pair_question_rounds (player1_item)",
                "CREATE INDEX IF NOT EXISTS idx_rounds_player2_item ON pair_question_rounds (player2_item)",
                "CREATE INDEX IF NOT EXISTS idx_rounds_timestamp_initiated ON pair_question_rounds (timestamp_initiated)",
                "CREATE INDEX IF NOT EXISTS idx_rounds_team_timestamp ON pair_question_rounds (team_id, timestamp_initiated)",
                "CREATE INDEX IF NOT EXISTS idx_rounds_team_items ON pair_question_rounds (team_id, player1_item, player2_item)",
            ]
            
            # Execute index creation statements
            for index_sql in indexes:
                try:
                    print(f"Creating index: {index_sql}")
                    connection.execute(db.text(index_sql))
                    print("✓ Index created successfully")
                except Exception as e:
                    print(f"⚠ Warning: Could not create index: {str(e)}")
                    # Continue with other indexes even if one fails
                    continue
            
            # Commit the changes
            connection.commit()
            connection.close()
            
            print("\n✅ Database indexes added successfully!")
            print("Database query performance should now be significantly improved.")
            
    except Exception as e:
        print(f"❌ Error adding database indexes: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def check_existing_indexes():
    """Check what indexes already exist in the database."""
    try:
        with app.app_context():
            connection = db.engine.connect()
            engine_name = db.engine.name
            
            print("Checking existing indexes...")
            
            if engine_name == 'sqlite':
                # SQLite query to list indexes
                result = connection.execute(db.text("""
                    SELECT name, tbl_name, sql 
                    FROM sqlite_master 
                    WHERE type = 'index' AND tbl_name IN ('teams', 'answers', 'pair_question_rounds')
                    ORDER BY tbl_name, name
                """))
            elif engine_name == 'postgresql':
                # PostgreSQL query to list indexes
                result = connection.execute(db.text("""
                    SELECT indexname, tablename, indexdef 
                    FROM pg_indexes 
                    WHERE tablename IN ('teams', 'answers', 'pair_question_rounds')
                    ORDER BY tablename, indexname
                """))
            else:
                print(f"Unsupported database engine: {engine_name}")
                return
            
            indexes = result.fetchall()
            if indexes:
                print("\nExisting indexes:")
                for idx in indexes:
                    print(f"  - {idx[0]} on {idx[1]}")
            else:
                print("No custom indexes found.")
            
            connection.close()
            
    except Exception as e:
        print(f"Error checking existing indexes: {str(e)}")

if __name__ == "__main__":
    print("CHSH-Game Database Index Migration")
    print("=" * 40)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check_existing_indexes()
    else:
        print("This will add performance indexes to your database.")
        response = input("Continue? (y/N): ")
        if response.lower() in ['y', 'yes']:
            add_indexes()
        else:
            print("Migration cancelled.")