"""
Dashboard Computations

This module contains the core computation functions for calculating
team hashes, correlation matrices, and success metrics.
"""

import hashlib
import logging
from typing import Dict, List, Tuple, Any, Optional
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from .cache_system import selective_cache, _hash_cache, _correlation_cache, _success_cache
from .client_management import _get_team_id_from_name

logger = logging.getLogger(__name__)

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
    Compute the correlation matrix for the given team.
    Returns (corr_matrix, item_values, avg_same_item_balance, same_item_balance, same_item_responses, correlation_sums, pair_counts).
    """
    try:
        # Get team_id from team_name
        team_id = _get_team_id_from_name(team_name)
        if team_id is None:
            logger.warning(f"Could not find team_id for team_name: {team_name}")
            return ([[ (0,0) for _ in range(4) ] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, {}, {}, {}, {})
        
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
        
        # Prepare the 4x4 correlation matrix for A, B, X, Y combinations
        item_values = ['A', 'B', 'X', 'Y']
        # corr_matrix will store (numerator, denominator) tuples
        corr_matrix = [[(0, 0) for _ in range(4)] for _ in range(4)]
        
        # Count pairs for each item combination
        pair_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        correlation_sums: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        
        # Track same-item responses for the new metric
        same_item_responses: Dict[str, Dict[str, int]] = {}
        
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
                
            # Get player responses (True/False)
            p1_answer = None
            p2_answer = None

            ans_A = round_answers[0]
            ans_B = round_answers[1]

            if p1_item == p2_item:
                # Both players were assigned the same item
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                    
                    # Track responses for same-item balance metric
                    if p1_item not in same_item_responses:
                        same_item_responses[p1_item] = {'true': 0, 'false': 0}
                    
                    # Count each response separately
                    same_item_responses[p1_item]['true' if p1_answer else 'false'] += 1
                    same_item_responses[p1_item]['true' if p2_answer else 'false'] += 1
            else:
                # p1_item and p2_item are different
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p2_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                elif ans_A.assigned_item.value == p2_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_B.response_value 
                    p2_answer = ans_A.response_value
            
            # Skip if we don't have both answers
            if p1_answer is None or p2_answer is None:
                continue
                
            # Calculate correlation: (T,T) or (F,F) count as 1, (T,F) or (F,T) count as -1
            correlation = 1 if p1_answer == p2_answer else -1
            
            pair_counts[(p1_item, p2_item)] += 1
            correlation_sums[(p1_item, p2_item)] += correlation
        
        # Populate the corr_matrix with (numerator, denominator) tuples
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                numerator = correlation_sums.get((row_item, col_item), 0)
                denominator = pair_counts.get((row_item, col_item), 0)
                corr_matrix[i][j] = (numerator, denominator)
        
        # Calculate the same-item balance metric
        same_item_balance: Dict[str, float] = {}
        for item, counts in same_item_responses.items():
            total = counts['true'] + counts['false']
            if total == 0:
                same_item_balance[item] = 0.0
            else:
                diff = abs(counts['true'] - counts['false'])
                same_item_balance[item] = 1.0 - diff / total
        
        # Calculate the average balance across all same items
        if same_item_responses:
            avg_same_item_balance = sum(same_item_balance.values()) / len(same_item_balance)
        else:
            avg_same_item_balance = 0.0  # Default if no same-item responses
        
        return (corr_matrix, item_values,
                avg_same_item_balance, same_item_balance, same_item_responses,
                correlation_sums, pair_counts)
    except Exception as e:
        logger.error(f"Error computing correlation matrix: {str(e)}", exc_info=True)
        return ([[ (0,0) for _ in range(4) ] for _ in range(4)],
                ['A', 'B', 'X', 'Y'], 0.0, {}, {}, {}, {})

def compute_correlation_stats(team_name: str) -> Tuple[float, float, float]:  # NOT USED
    try:
        # Get the correlation matrix and new metrics  
        result = compute_correlation_matrix(team_name)  # type: ignore
        corr_matrix, item_values = result[0], result[1]
        same_item_balance_avg = result[2]
        
        # Validate matrix dimensions and contents
        if not all(isinstance(row, list) and len(row) == 4 for row in corr_matrix) or len(corr_matrix) != 4:
            logger.error(f"Invalid correlation matrix dimensions for team_name {team_name}")
            return 0.0, 0.0, 0.0
            
        # Validate expected item values
        expected_items = ['A', 'B', 'X', 'Y']
        if not all(item in item_values for item in expected_items):
            logger.error(f"Missing expected items in correlation matrix for team_name {team_name}")
            return 0.0, 0.0, 0.0
            
        # Calculate first statistic: Trace(corr_matrix) / 4
        try:
            trace_sum = sum(corr_matrix[i][i] for i in range(4))
            trace_average_statistic = trace_sum / 4
        except (TypeError, IndexError) as e:
            logger.error(f"Error calculating trace statistic: {e}")
            trace_average_statistic = 0.0
        
        # Calculate second statistic using CHSH game formula
        # corrAX + corrAY + corrBX - corrBY + corrXA + corrXB + corrYA - corrYB
        # Get indices for A, B, X, Y from item_values
        try:
            A_idx = item_values.index('A')
            B_idx = item_values.index('B')
            X_idx = item_values.index('X')
            Y_idx = item_values.index('Y')
            
            chsh_value_statistic = (
                corr_matrix[A_idx][X_idx] + corr_matrix[A_idx][Y_idx] + 
                corr_matrix[B_idx][X_idx] - corr_matrix[B_idx][Y_idx] +
                corr_matrix[X_idx][A_idx] + corr_matrix[X_idx][B_idx] + 
                corr_matrix[Y_idx][A_idx] - corr_matrix[Y_idx][B_idx]
            )/2
        except (ValueError, IndexError, TypeError) as e:
            logger.error(f"Error calculating CHSH statistic: {e}")
            chsh_value_statistic = 0.0
        
        return trace_average_statistic, chsh_value_statistic, same_item_balance_avg
    except Exception as e:
        logger.error(f"Error computing correlation statistics: {str(e)}", exc_info=True)
        return 0.0, 0.0, 0.0