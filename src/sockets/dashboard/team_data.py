import hashlib
import logging
from typing import Dict, List, Tuple, Any, Optional
from sqlalchemy.orm import joinedload
from src.models.quiz_models import Teams, Answers, PairQuestionRounds, ItemEnum
from .cache_management import (
    selective_cache, _hash_cache, _correlation_cache, _success_cache,
    _safe_dashboard_operation
)

# Configure logging
logger = logging.getLogger(__name__)

def _get_team_id_from_name(team_name: str) -> Optional[int]:
    """Helper function to resolve team_name to team_id from state or database."""
    try:
        from src.state import state
        
        # First check active teams
        team_info = state.active_teams.get(team_name)
        if team_info and 'team_id' in team_info:
            return team_info['team_id']
        
        # Fall back to database lookup
        team = Teams.query.filter_by(team_name=team_name).first()
        return team.team_id if team else None
    except Exception as e:
        logger.error(f"Error getting team_id for team_name {team_name}: {str(e)}", exc_info=True)
        return None

@selective_cache(_hash_cache)
def compute_team_hashes(team_name: str) -> Tuple[str, str]:
    """Generate unique history hashes for team data consistency checking."""
    try:
        # Get team_id from team_name
        team_id = _get_team_id_from_name(team_name)
        if team_id is None:
            logger.warning(f"Could not find team_id for team_name: {team_name}")
            return "NO_TEAM", "NO_TEAM"
        
        # Get all rounds and answers for this team in chronological order
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()

        # Create history string containing both questions and answers
        history = []
        for round in rounds:
            history.append(f"P1:{round.player1_item.value if round.player1_item else 'None'}")
            history.append(f"P2:{round.player2_item.value if round.player2_item else 'None'}")
        for answer in answers:
            history.append(f"A:{answer.assigned_item.value}:{answer.response_value}")
        
        history_str = "|".join(history)

        # logger.debug(f"History for team {team_id}: {history_str}")
        # logger.debug(rounds)
        
        # Generate two different hashes
        hash1 = hashlib.sha256(history_str.encode()).hexdigest()[:8]
        hash2 = hashlib.md5(history_str.encode()).hexdigest()[:8]
        
        return hash1, hash2
    except Exception as e:
        logger.error(f"Error computing team hashes: {str(e)}")
        return "ERROR", "ERROR"

@selective_cache(_success_cache)
def compute_success_metrics(team_name: str) -> Tuple[List[List[Tuple[int, int]]], List[str], float, float, Dict[Tuple[str, str], int], Dict[Tuple[str, str], int], Dict[str, Dict[str, int]]]:
    """
    Compute success metrics for new mode instead of correlation matrix.
    Returns success rate matrix, overall success metrics, and individual player balance data.
    """
    try:
        # Get team_id from team_name
        team_id = _get_team_id_from_name(team_name)
        if team_id is None:
            logger.warning(f"Could not find team_id for team_name: {team_name}")
            return ([[(0, 0) for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, 0.0, {}, {}, {})
        
        # Get all rounds and their corresponding answers for this team
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        round_map = {round.round_id: round for round in rounds}
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()
        
        # Group answers by round_id
        answers_by_round: Dict[int, List[Any]] = {}
        for answer in answers:
            if answer.question_round_id not in answers_by_round:
                answers_by_round[answer.question_round_id] = []
            answers_by_round[answer.question_round_id].append(answer)
        
        # Initialize success metrics
        item_values = ['A', 'B', 'X', 'Y']
        success_matrix = [[(0, 0) for _ in range(4)] for _ in range(4)]  # (successful_rounds, total_rounds)
        
        # Count pairs for each item combination
        pair_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        success_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        
        # Track individual player responses for balance calculation
        # NEW MODE: Track each player's responses to their assigned question types
        player_responses: Dict[str, Dict[str, int]] = {}  # {item: {'true': count, 'false': count}}
        for item in item_values:
            player_responses[item] = {'true': 0, 'false': 0}
        
        total_rounds = 0
        successful_rounds = 0
        
        # Analyze each round that has both player answers
        for round_id, round_answers in answers_by_round.items():
            # Skip if we don't have exactly 2 answers (one from each player)
            if len(round_answers) != 2 or round_id not in round_map:
                continue
                
            round_obj = round_map[round_id]
            p1_item = round_obj.player1_item.value if round_obj.player1_item else None
            p2_item = round_obj.player2_item.value if round_obj.player2_item else None
            
            # Skip if we don't have both items
            if not p1_item or not p2_item:
                continue
                
            # Get player responses
            p1_answer = None
            p2_answer = None

            ans_A = round_answers[0]
            ans_B = round_answers[1]

            if p1_item == p2_item:
                # Both players were assigned the same item
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
            else:
                # Different items
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p2_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                elif ans_A.assigned_item.value == p2_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_B.response_value 
                    p2_answer = ans_A.response_value
            
            # Skip if we don't have both answers
            if p1_answer is None or p2_answer is None:
                continue
                
            # Track individual player responses for balance calculation
            player_responses[p1_item]['true' if p1_answer else 'false'] += 1
            player_responses[p2_item]['true' if p2_answer else 'false'] += 1
                
            # Apply success rules for new mode
            # Success Rule: {B,Y} combinations require different answers; all others require same answers
            is_by_combination = (p1_item == 'B' and p2_item == 'Y') or (p1_item == 'Y' and p2_item == 'B')
            players_answered_differently = p1_answer != p2_answer
            
            if is_by_combination:
                # B,Y combination: players should answer differently
                is_successful = players_answered_differently
            else:
                # All other combinations: players should answer the same
                is_successful = not players_answered_differently
            
            # Update counts
            total_rounds += 1
            if is_successful:
                successful_rounds += 1
                success_counts[(p1_item, p2_item)] += 1
            
            pair_counts[(p1_item, p2_item)] += 1
        
        # Populate the success matrix with (successful, total) tuples
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                successful = success_counts.get((row_item, col_item), 0)
                total = pair_counts.get((row_item, col_item), 0)
                success_matrix[i][j] = (successful, total)
        
        # Calculate overall success rate and normalized score
        overall_success_rate = successful_rounds / total_rounds if total_rounds > 0 else 0.0
        
        # Normalized cumulative score: +1 for success, -1 for failure, divided by total rounds
        score_sum = successful_rounds - (total_rounds - successful_rounds)  # successful - failed
        normalized_cumulative_score = score_sum / total_rounds if total_rounds > 0 else 0.0
        
        return (success_matrix, item_values, overall_success_rate, normalized_cumulative_score, success_counts, pair_counts, player_responses)
        
    except Exception as e:
        logger.error(f"Error computing success metrics: {str(e)}", exc_info=True)
        return ([[(0, 0) for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, 0.0, {}, {}, {})

@selective_cache(_correlation_cache)
def compute_correlation_matrix(team_name: str) -> Tuple[List[List[Tuple[int, int]]], List[str], float, Dict[str, float], Dict[str, Dict[str, int]], Dict[Tuple[str, str], int], Dict[Tuple[str, str], int]]:
    """
    Compute correlation matrix data for classic mode.
    Returns correlation matrix, analysis data, and statistics.
    """
    try:
        # Get team_id from team_name
        team_id = _get_team_id_from_name(team_name)
        if team_id is None:
            logger.warning(f"Could not find team_id for team_name: {team_name}")
            return ([[(0, 0) for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, {}, {}, {}, {})
        
        # Get all rounds and their corresponding answers for this team
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        round_map = {round.round_id: round for round in rounds}
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()
        
        # Group answers by round_id
        answers_by_round: Dict[int, List[Any]] = {}
        for answer in answers:
            if answer.question_round_id not in answers_by_round:
                answers_by_round[answer.question_round_id] = []
            answers_by_round[answer.question_round_id].append(answer)
        
        # Initialize correlation matrix
        item_values = ['A', 'B', 'X', 'Y']
        correlation_matrix = [[(0, 0) for _ in range(4)] for _ in range(4)]  # (correlated_rounds, total_rounds)
        
        # Count pairs for each item combination
        pair_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        correlated_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        
        # Track individual player responses for balance calculation
        player_responses: Dict[str, Dict[str, int]] = {}  # {item: {'true': count, 'false': count}}
        for item in item_values:
            player_responses[item] = {'true': 0, 'false': 0}
        
        total_rounds = 0
        correlated_rounds = 0
        
        # Analyze each round that has both player answers
        for round_id, round_answers in answers_by_round.items():
            # Skip if we don't have exactly 2 answers (one from each player)
            if len(round_answers) != 2 or round_id not in round_map:
                continue
                
            round_obj = round_map[round_id]
            p1_item = round_obj.player1_item.value if round_obj.player1_item else None
            p2_item = round_obj.player2_item.value if round_obj.player2_item else None
            
            # Skip if we don't have both items
            if not p1_item or not p2_item:
                continue
                
            # Get player responses
            p1_answer = None
            p2_answer = None

            ans_A = round_answers[0]
            ans_B = round_answers[1]

            if p1_item == p2_item:
                # Both players were assigned the same item
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
            else:
                # Different items
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p2_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                elif ans_A.assigned_item.value == p2_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_B.response_value 
                    p2_answer = ans_A.response_value
            
            # Skip if we don't have both answers
            if p1_answer is None or p2_answer is None:
                continue
                
            # Track individual player responses for balance calculation
            player_responses[p1_item]['true' if p1_answer else 'false'] += 1
            player_responses[p2_item]['true' if p2_answer else 'false'] += 1
                
            # Classic mode: correlation means both players answered the same
            is_correlated = p1_answer == p2_answer
            
            # Update counts
            total_rounds += 1
            if is_correlated:
                correlated_rounds += 1
                correlated_counts[(p1_item, p2_item)] += 1
            
            pair_counts[(p1_item, p2_item)] += 1
        
        # Populate the correlation matrix with (correlated, total) tuples
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                correlated = correlated_counts.get((row_item, col_item), 0)
                total = pair_counts.get((row_item, col_item), 0)
                correlation_matrix[i][j] = (correlated, total)
        
        # Calculate overall correlation rate
        overall_correlation_rate = correlated_rounds / total_rounds if total_rounds > 0 else 0.0
        
        # Calculate correlation coefficients for each pair type
        correlation_coefficients: Dict[str, float] = {}
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                pair_key = f"{row_item}-{col_item}"
                correlated = correlated_counts.get((row_item, col_item), 0)
                total = pair_counts.get((row_item, col_item), 0)
                correlation_coefficients[pair_key] = correlated / total if total > 0 else 0.0
        
        return (correlation_matrix, item_values, overall_correlation_rate, correlation_coefficients, player_responses, correlated_counts, pair_counts)
        
    except Exception as e:
        logger.error(f"Error computing correlation matrix: {str(e)}", exc_info=True)
        return ([[(0, 0) for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, {}, {}, {}, {})

def _compute_team_hashes_optimized(team_id: int, team_rounds: List[Any], team_answers: List[Any]) -> Tuple[str, str]:
    """Optimized version that works with pre-fetched data."""
    try:
        # Create history string containing both questions and answers
        history = []
        for round in team_rounds:
            history.append(f"P1:{round.player1_item.value if round.player1_item else 'None'}")
            history.append(f"P2:{round.player2_item.value if round.player2_item else 'None'}")
        for answer in team_answers:
            history.append(f"A:{answer.assigned_item.value}:{answer.response_value}")
        
        history_str = "|".join(history)
        
        # Generate two different hashes
        hash1 = hashlib.sha256(history_str.encode()).hexdigest()[:8]
        hash2 = hashlib.md5(history_str.encode()).hexdigest()[:8]
        
        return hash1, hash2
    except Exception as e:
        logger.error(f"Error computing optimized team hashes: {str(e)}")
        return "ERROR", "ERROR"

def _compute_correlation_matrix_optimized(team_id: int, team_rounds: List[Any], team_answers: List[Any]) -> Tuple[List[List[Tuple[int, int]]], List[str], float, Dict[str, float], Dict[str, Dict[str, int]], Dict[Tuple[str, str], int], Dict[Tuple[str, str], int]]:
    """Optimized correlation matrix computation using pre-fetched data."""
    try:
        # Create round map
        round_map = {round.round_id: round for round in team_rounds}
        
        # Group answers by round_id
        answers_by_round: Dict[int, List[Any]] = {}
        for answer in team_answers:
            if answer.question_round_id not in answers_by_round:
                answers_by_round[answer.question_round_id] = []
            answers_by_round[answer.question_round_id].append(answer)
        
        # Initialize correlation matrix
        item_values = ['A', 'B', 'X', 'Y']
        correlation_matrix = [[(0, 0) for _ in range(4)] for _ in range(4)]  # (correlated_rounds, total_rounds)
        
        # Count pairs for each item combination
        pair_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        correlated_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        
        # Track individual player responses for balance calculation
        player_responses: Dict[str, Dict[str, int]] = {}  # {item: {'true': count, 'false': count}}
        for item in item_values:
            player_responses[item] = {'true': 0, 'false': 0}
        
        total_rounds = 0
        correlated_rounds = 0
        
        # Analyze each round that has both player answers
        for round_id, round_answers in answers_by_round.items():
            # Skip if we don't have exactly 2 answers (one from each player)
            if len(round_answers) != 2 or round_id not in round_map:
                continue
                
            round_obj = round_map[round_id]
            p1_item = round_obj.player1_item.value if round_obj.player1_item else None
            p2_item = round_obj.player2_item.value if round_obj.player2_item else None
            
            # Skip if we don't have both items
            if not p1_item or not p2_item:
                continue
                
            # Get player responses
            p1_answer = None
            p2_answer = None

            ans_A = round_answers[0]
            ans_B = round_answers[1]

            if p1_item == p2_item:
                # Both players were assigned the same item
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
            else:
                # Different items
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p2_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                elif ans_A.assigned_item.value == p2_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_B.response_value 
                    p2_answer = ans_A.response_value
            
            # Skip if we don't have both answers
            if p1_answer is None or p2_answer is None:
                continue
                
            # Track individual player responses for balance calculation
            player_responses[p1_item]['true' if p1_answer else 'false'] += 1
            player_responses[p2_item]['true' if p2_answer else 'false'] += 1
                
            # Classic mode: correlation means both players answered the same
            is_correlated = p1_answer == p2_answer
            
            # Update counts
            total_rounds += 1
            if is_correlated:
                correlated_rounds += 1
                correlated_counts[(p1_item, p2_item)] += 1
            
            pair_counts[(p1_item, p2_item)] += 1
        
        # Populate the correlation matrix with (correlated, total) tuples
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                correlated = correlated_counts.get((row_item, col_item), 0)
                total = pair_counts.get((row_item, col_item), 0)
                correlation_matrix[i][j] = (correlated, total)
        
        # Calculate overall correlation rate
        overall_correlation_rate = correlated_rounds / total_rounds if total_rounds > 0 else 0.0
        
        # Calculate correlation coefficients for each pair type
        correlation_coefficients: Dict[str, float] = {}
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                pair_key = f"{row_item}-{col_item}"
                correlated = correlated_counts.get((row_item, col_item), 0)
                total = pair_counts.get((row_item, col_item), 0)
                correlation_coefficients[pair_key] = correlated / total if total > 0 else 0.0
        
        return (correlation_matrix, item_values, overall_correlation_rate, correlation_coefficients, player_responses, correlated_counts, pair_counts)
        
    except Exception as e:
        logger.error(f"Error computing optimized correlation matrix: {str(e)}", exc_info=True)
        return ([[(0, 0) for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, {}, {}, {}, {})

def _compute_success_metrics_optimized(team_id: int, team_rounds: List[Any], team_answers: List[Any]) -> Tuple[List[List[Tuple[int, int]]], List[str], float, float, Dict[Tuple[str, str], int], Dict[Tuple[str, str], int], Dict[str, Dict[str, int]]]:
    """Optimized success metrics computation using pre-fetched data."""
    try:
        # Create round map
        round_map = {round.round_id: round for round in team_rounds}
        
        # Group answers by round_id
        answers_by_round: Dict[int, List[Any]] = {}
        for answer in team_answers:
            if answer.question_round_id not in answers_by_round:
                answers_by_round[answer.question_round_id] = []
            answers_by_round[answer.question_round_id].append(answer)
        
        # Initialize success metrics
        item_values = ['A', 'B', 'X', 'Y']
        success_matrix = [[(0, 0) for _ in range(4)] for _ in range(4)]  # (successful_rounds, total_rounds)
        
        # Count pairs for each item combination
        pair_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        success_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        
        # Track individual player responses for balance calculation
        # NEW MODE: Track each player's responses to their assigned question types
        player_responses: Dict[str, Dict[str, int]] = {}  # {item: {'true': count, 'false': count}}
        for item in item_values:
            player_responses[item] = {'true': 0, 'false': 0}
        
        total_rounds = 0
        successful_rounds = 0
        
        # Analyze each round that has both player answers
        for round_id, round_answers in answers_by_round.items():
            # Skip if we don't have exactly 2 answers (one from each player)
            if len(round_answers) != 2 or round_id not in round_map:
                continue
                
            round_obj = round_map[round_id]
            p1_item = round_obj.player1_item.value if round_obj.player1_item else None
            p2_item = round_obj.player2_item.value if round_obj.player2_item else None
            
            # Skip if we don't have both items
            if not p1_item or not p2_item:
                continue
                
            # Get player responses
            p1_answer = None
            p2_answer = None

            ans_A = round_answers[0]
            ans_B = round_answers[1]

            if p1_item == p2_item:
                # Both players were assigned the same item
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
            else:
                # Different items
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p2_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                elif ans_A.assigned_item.value == p2_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_B.response_value 
                    p2_answer = ans_A.response_value
            
            # Skip if we don't have both answers
            if p1_answer is None or p2_answer is None:
                continue
                
            # Track individual player responses for balance calculation
            player_responses[p1_item]['true' if p1_answer else 'false'] += 1
            player_responses[p2_item]['true' if p2_answer else 'false'] += 1
                
            # Apply success rules for new mode
            # Success Rule: {B,Y} combinations require different answers; all others require same answers
            is_by_combination = (p1_item == 'B' and p2_item == 'Y') or (p1_item == 'Y' and p2_item == 'B')
            players_answered_differently = p1_answer != p2_answer
            
            if is_by_combination:
                # B,Y combination: players should answer differently
                is_successful = players_answered_differently
            else:
                # All other combinations: players should answer the same
                is_successful = not players_answered_differently
            
            # Update counts
            total_rounds += 1
            if is_successful:
                successful_rounds += 1
                success_counts[(p1_item, p2_item)] += 1
            
            pair_counts[(p1_item, p2_item)] += 1
        
        # Populate the success matrix with (successful, total) tuples
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                successful = success_counts.get((row_item, col_item), 0)
                total = pair_counts.get((row_item, col_item), 0)
                success_matrix[i][j] = (successful, total)
        
        # Calculate overall success rate and normalized score
        overall_success_rate = successful_rounds / total_rounds if total_rounds > 0 else 0.0
        
        # Normalized cumulative score: +1 for success, -1 for failure, divided by total rounds
        score_sum = successful_rounds - (total_rounds - successful_rounds)  # successful - failed
        normalized_cumulative_score = score_sum / total_rounds if total_rounds > 0 else 0.0
        
        return (success_matrix, item_values, overall_success_rate, normalized_cumulative_score, success_counts, pair_counts, player_responses)
        
    except Exception as e:
        logger.error(f"Error computing optimized success metrics: {str(e)}", exc_info=True)
        return ([[(0, 0) for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, 0.0, {}, {}, {})