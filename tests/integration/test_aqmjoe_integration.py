import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock

from src.config import app, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from src.game_logic import start_new_round_for_pair
from src.sockets.dashboard import compute_success_metrics, on_set_theme_and_mode, on_change_game_theme


class TestAQMJoeIntegration:
    def setup_method(self):
        # Temp DB per test
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.temp_db_fd)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.temp_db_path}'

        state.reset()
        state.game_started = True

        with app.app_context():
            db.drop_all()
            db.create_all()

        # Create team in DB and state
        with app.app_context():
            team = Teams(team_name='aqm_team', is_active=True)
            team.player1_session_id = 'p1'
            team.player2_session_id = 'p2'
            db.session.add(team)
            db.session.commit()
            self.team_id = team.team_id

        state.active_teams['aqm_team'] = {
            'team_id': self.team_id,
            'players': ['p1', 'p2'],
            'current_round_number': 0,
            'combo_tracker': {},
            'current_db_round_id': None,
            'answered_current_round': {},
            'player_slots': {'p1': 1, 'p2': 2}
        }

    def teardown_method(self):
        state.reset()
        with app.app_context():
            try:
                db.session.close()
                db.session.remove()
            except:
                pass
        try:
            if os.path.exists(self.temp_db_path):
                os.unlink(self.temp_db_path)
        except:
            pass

    @patch('random.shuffle', side_effect=lambda x: x)
    @patch('src.game_logic.socketio')
    def test_aqmjoe_assignment_allows_any_items(self, mock_socketio, _):
        state.game_mode = 'aqmjoe'

        # Generate several rounds under app & request context
        with app.test_request_context():
            with app.app_context():
                for _ in range(20):
                    start_new_round_for_pair('aqm_team')

        # Check DB rounds include at least one non-simplified combo
        with app.app_context():
            rounds = PairQuestionRounds.query.filter_by(team_id=self.team_id).all()
            assert len(rounds) > 0
            simplified_set = {
                (ItemEnum.A, ItemEnum.X), (ItemEnum.A, ItemEnum.Y),
                (ItemEnum.B, ItemEnum.X), (ItemEnum.B, ItemEnum.Y)
            }
            combos = {(r.player1_item, r.player2_item) for r in rounds}
            assert not combos.issubset(simplified_set), 'AQM Joe should include non-simplified combinations'

    @patch('src.sockets.dashboard.logger')
    def test_aqmjoe_success_policy_metrics(self, _mock_logger):
        state.game_mode = 'aqmjoe'

        with app.app_context():
            # Create rounds with controlled answers
            round_no = 0
            def add_round(p1_item, p2_item, p1_ans, p2_ans):
                nonlocal round_no
                round_no += 1
                rnd = PairQuestionRounds(team_id=self.team_id, round_number_for_team=round_no,
                                         player1_item=p1_item, player2_item=p2_item)
                db.session.add(rnd)
                db.session.flush()
                a1 = Answers(team_id=self.team_id, question_round_id=rnd.round_id,
                             player_session_id='p1', assigned_item=p1_item, response_value=p1_ans)
                a2 = Answers(team_id=self.team_id, question_round_id=rnd.round_id,
                             player_session_id='p2', assigned_item=p2_item, response_value=p2_ans)
                db.session.add(a1)
                db.session.add(a2)
                db.session.commit()

            # Food–Food both Peas -> fail
            add_round(ItemEnum.X, ItemEnum.Y, True, True)
            # Mixed: Green->Peas success
            add_round(ItemEnum.A, ItemEnum.X, True, True)
            # Mixed: Red<->Carrots success
            add_round(ItemEnum.B, ItemEnum.Y, False, False)
            # Color–Color neutral success
            add_round(ItemEnum.A, ItemEnum.B, True, False)

            matrix, labels, overall_success_rate, norm_score, success_counts, pair_counts, _ = compute_success_metrics('aqm_team')
            # Expect at least 3 successes out of 4
            assert overall_success_rate >= 0.5
            # Validate Food–Food both Peas counted as failure
            assert pair_counts.get(('X', 'Y')) == 1
            assert success_counts.get(('X', 'Y'), 0) == 0

    def test_theme_mode_linking_and_alias_handling(self):
        # Real socket path for on_change_game_theme (linking enforced)
        with app.test_request_context():
            with patch('src.sockets.dashboard.request') as mock_req:
                mock_req.sid = 'dashX'
                state.dashboard_clients.add('dashX')
                state.game_mode = 'classic'
                on_change_game_theme({'theme': 'aqmjoe'})
                assert state.game_mode == 'aqmjoe'

        # Test atomic set_theme_and_mode with auth in request context
        with app.test_request_context():
            with patch('src.sockets.dashboard.request') as mock_req, \
                 patch('src.sockets.dashboard.socketio') as mock_io:
                mock_req.sid = 'dash1'
                state.dashboard_clients.add('dash1')
                # Selecting aqmjoe mode or theme forces both to aqmjoe
                on_set_theme_and_mode({'theme': 'food', 'mode': 'aqmjoe'})
                assert state.game_mode == 'aqmjoe'
                assert state.game_theme == 'aqmjoe'
                # Switching away from AQM Joe via theme change auto-sets mode to simplified
                state.game_mode = 'aqmjoe'
                on_change_game_theme({'theme': 'food'})
                assert state.game_mode == 'simplified'

                # Alias: 'new' should normalize to 'simplified'
                on_set_theme_and_mode({'theme': 'food', 'mode': 'new'})
                assert state.game_mode == 'simplified'
                # Verify emission used normalized mode
                mock_io.emit.assert_any_call('game_mode_changed', {'mode': 'simplified'})