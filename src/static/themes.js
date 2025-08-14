// Theme System for CHSH Game
// This file contains all theme definitions and utilities

const THEMES = {
    classic: {
        name: 'Classic',
        description: 'Traditional ABXY notation',
        items: {
            A: 'A',
            B: 'B', 
            X: 'X',
            Y: 'Y'
        },
        playerHints: {
            1: 'Your questions: A or B',
            2: 'Your questions: X or Y'
        },
        questionBoxColors: {
            1: '#e3f2fd', // Light blue (original)
            2: '#e3f2fd', // Light blue (original)
            default: '#f5f5f5' // Gray when not in team
        },
        questionTextColor: '#1565c0',
        gameRules: {
            classic: {
                title: 'Game Rules (Classic Mode)',
                content: `
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Discuss and agree on a shared strategy before the game starts.</li>
                        <li><strong>No</strong> communicate during the game.</li>
                        <li>Watch the dashboard to see your teams' progress.</li>
                        <li>Focus on <strong>consistency</strong> rather than <strong>randomness</strong>.</li>
                        <li>This app is fragile, please keep browser page open to stay connected.</li>
                    </ul>
                `
            },
            new: {
                title: 'Game Rules (Simplified Mode)', 
                content: `
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Discuss and agree on a shared strategy before the game starts.</li>
                        <li><strong>No</strong> communicate during the game.</li>
                        <li>Watch the dashboard to see your teams' progress.</li>
                        <li>Player 1 will only receive A or B questions.</li>
                        <li>Player 2 will only receive X or Y questions.</li>
                        <li>Focus on <strong>consistency</strong> and <strong>coordination</strong>.</li>
                        <li>This app is fragile, please keep browser page open to stay connected.</li>
                    </ul>
                `
            },
            simplified: {
                title: 'Game Rules (Simplified Mode)', 
                content: `
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Discuss and agree on a shared strategy before the game starts.</li>
                        <li><strong>No</strong> communicate during the game.</li>
                        <li>Watch the dashboard to see your teams' progress.</li>
                        <li>Player 1 will only receive A or B questions.</li>
                        <li>Player 2 will only receive X or Y questions.</li>
                        <li>Focus on <strong>consistency</strong> and <strong>coordination</strong>.</li>
                        <li>This app is fragile, please keep browser page open to stay connected.</li>
                    </ul>
                `
            }
        },
        winningConditions: {
            classic: {
                title: 'Winning Conditions (Classic Mode)',
                content: `
                    <div style="margin-bottom: 15px;">
                        <strong>🎯 Best Balanced ⏐⟨Tr⟩⏐ (Consistency):</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>If you and your partner are asked the <strong>same question</strong> (A/A, B/B, X/X, or Y/Y), aim to give the <strong>same answer</strong> (True/True or False/False).</li>
                            <li>To achieve balance, your answers should be  <strong>50% True</strong> and <strong>50% False</strong>.</li>
                            <li>The score is computed as:
                                <ul style="margin: 5px 0; padding-left: 20px;">
                                    <li><strong>⟨Tr⟩ = Trace / 4</strong>: ±1 if teammates always agree, 0 if always disagree.</li>
                                    <li><strong>Balance</strong> = 1 if your answers are evenly split between True and False, 0 if always the same.</li>
                                    <li><strong>Final score</strong>:  
                                        <code>Balanced |⟨Tr⟩| = 0.5 × (Balance + |⟨Tr⟩|)</code>
                                    </li>
                                </ul>
                            </li>
                        </ul>
                    </div>
                    <div>
                        <strong>🏆 Best CHSH (Correlation):</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>If one of you receives <strong>B</strong> and the other <strong>Y</strong>, you should try to give <strong>different answers</strong> (one True, one False).</li>
                            <li>For all other question combinations, you should give the <strong>same answer</strong> as much as possible.</li>
                            <li>The maximum possible value for CHSH is 4</li>
                        </ul>
                    </div>
                `
            },
            new: {
                title: 'Winning Conditions (Simplified Mode)',
                content: `
                    <div>
                        <strong>🏆 Best Success Rate:</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>When Player 1 gets <strong>B</strong> and Player 2 gets <strong>Y</strong>, you should give <strong>different answers</strong> (one True, one False).</li>
                            <li>For all other combinations (A-X, A-Y, B-X), you should give the <strong>same answer</strong> as much as possible.</li>
                            <li>Success rate is calculated as the percentage of rounds where you follow the optimal strategy.</li>
                            <li>Aim for the highest success rate possible!</li>
                        </ul>
                    </div>
                `
            },
            simplified: {
                title: 'Winning Conditions (Simplified Mode)',
                content: `
                    <div>
                        <strong>🏆 Best Success Rate:</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>When Player 1 gets <strong>B</strong> and Player 2 gets <strong>Y</strong>, you should give <strong>different answers</strong> (one True, one False).</li>
                            <li>For all other combinations (A-X, A-Y, B-X), you should give the <strong>same answer</strong> as much as possible.</li>
                            <li>Success rate is calculated as the percentage of rounds where you follow the optimal strategy.</li>
                            <li>Aim for the highest success rate possible!</li>
                        </ul>
                    </div>
                `
            }
        }
    },
    
    food: {
        name: 'Food Ingredients',
        description: 'Cooking-themed ingredients',
        items: {
            A: '🍞 Bread',
            B: '🥟 Dumplings',
            X: '🥬 Lettuce', 
            Y: '🍫 Chocolate'
        },
        playerHints: {
            1: 'Your ingredients: 🍞 or 🥟',
            2: 'Your ingredients: 🥬 or 🍫'
        },
        questionBoxColors: {
            1: '#f3e5f5', // Light purple for player 1
            2: '#fff9c4', // Light yellow for player 2
            default: '#f5f5f5' // Gray when not in team
        },
        questionTextColor: '#4a148c', // Purple text
        gameRules: {
            classic: {
                title: 'Cooking Rules (Classic Mode)',
                content: `
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Plan your cooking strategy with your partner before starting!</li>
                        <li><strong>No</strong> talking during cooking time.</li>
                        <li>Watch the dashboard to see how all chefs are doing.</li>
                        <li>Focus on <strong>consistent recipes</strong> rather than <strong>random cooking</strong>.</li>
                        <li>Keep your kitchen (browser) open to stay connected!</li>
                    </ul>
                `
            },
            new: {
                title: 'Cooking Rules (Simplified Mode)',
                content: `
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Plan your cooking strategy with your partner before starting!</li>
                        <li><strong>No</strong> talking during cooking time.</li>
                        <li>Watch the dashboard to see how all chefs are doing.</li>
                        <li>Chef 1 specializes in: 🍞 Bread and 🥟 Dumplings</li>
                        <li>Chef 2 specializes in: 🥬 Lettuce and 🍫 Chocolate</li>
                        <li>Focus on <strong>consistent recipes</strong> and <strong>teamwork</strong>.</li>
                        <li>Keep your kitchen (browser) open to stay connected!</li>
                    </ul>
                `
            },
            simplified: {
                title: 'Cooking Rules (Simplified Mode)',
                content: `
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Plan your cooking strategy with your partner before starting!</li>
                        <li><strong>No</strong> talking during cooking time.</li>
                        <li>Watch the dashboard to see how all chefs are doing.</li>
                        <li>Chef 1 specializes in: 🍞 Bread and 🥟 Dumplings</li>
                        <li>Chef 2 specializes in: 🥬 Lettuce and 🍫 Chocolate</li>
                        <li>Focus on <strong>consistent recipes</strong> and <strong>teamwork</strong>.</li>
                        <li>Keep your kitchen (browser) open to stay connected!</li>
                    </ul>
                `
            }
        },
        winningConditions: {
            classic: {
                title: 'Recipe Success (Classic Mode)',
                content: `
                    <div style="margin-bottom: 15px;">
                        <strong>🎯 Best Balanced Recipe (Consistency):</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>When you both get the <strong>same ingredient</strong> (🍞🍞, 🥟🥟, 🥬🥬, or 🍫🍫), try to make the <strong>same choice</strong> (both Like/both Dislike).</li>
                            <li>For balance, your choices should be <strong>50% Like</strong> and <strong>50% Dislike</strong>.</li>
                            <li>Recipe scoring:
                                <ul style="margin: 5px 0; padding-left: 20px;">
                                    <li><strong>Agreement Score</strong>: +1 when both chefs agree, -1 when you disagree</li>
                                    <li><strong>Balance Score</strong>: 1 if choices are evenly split, 0 if always the same</li>
                                    <li><strong>Final Recipe Score</strong>: Average of Agreement and Balance</li>
                                </ul>
                            </li>
                        </ul>
                    </div>
                    <div>
                        <strong>🏆 Best Flavor Harmony (Coordination):</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>When one chef gets <strong>🥟 Dumplings</strong> and the other gets <strong>🍫 Chocolate</strong>, try to give <strong>different opinions</strong> (one Like, one Dislike).</li>
                            <li>For all other ingredient pairs, try to give the <strong>same opinion</strong>.</li>
                            <li>Perfect harmony creates the best dishes!</li>
                        </ul>
                    </div>
                `
            },
            new: {
                title: 'Recipe Success (Simplified Mode)',
                content: `
                    <div>
                        <strong>🏆 Best Recipe Success Rate:</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>When Chef 1 gets <strong>🥟 Dumplings</strong> and Chef 2 gets <strong>🍫 Chocolate</strong>, give <strong>different opinions</strong> (one Like, one Dislike).</li>
                            <li>For other combinations (🍞-🥬, 🍞-🍫, 🥟-🥬), give the <strong>same opinion</strong>.</li>
                            <li>Success rate shows how often you follow the perfect recipe!</li>
                            <li>Aim to be the top chef team!</li>
                        </ul>
                    </div>
                `
            },
            simplified: {
                title: 'Recipe Success (Simplified Mode)',
                content: `
                    <div>
                        <strong>🏆 Best Recipe Success Rate:</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>When Chef 1 gets <strong>🥟 Dumplings</strong> and Chef 2 gets <strong>🍫 Chocolate</strong>, give <strong>different opinions</strong> (one Like, one Dislike).</li>
                            <li>For other combinations (🍞-🥬, 🍞-🍫, 🥟-🥬), give the <strong>same opinion</strong>.</li>
                            <li>Success rate shows how often you follow the perfect recipe!</li>
                            <li>Aim to be the top chef team!</li>
                        </ul>
                    </div>
                `
            }
        }
    },
    
    aqmjoe: {
        name: 'AQM Joe',
        description: 'Color and food themed questions',
        items: {
            A: 'Favourite Color?',
            B: 'Favourite Color?',
            X: 'Favourite Food?',
            Y: 'Favourite Food?'
        },
        playerHints: {
            1: 'You will answer questions about colors and food',
            2: 'You will answer questions about colors and food'
        },
        questionBoxColors: {
            1: '#e8f5e8', // Light green for AQM Joe theme
            2: '#e8f5e8', // Light green for AQM Joe theme
            default: '#f5f5f5' // Gray when not in team
        },
        questionTextColor: '#2e7d32', // Dark green text
        gameRules: {
            classic: {
                title: 'AQM Joe Rules (Classic Mode)',
                content: `
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Plan your strategy with your partner before starting!</li>
                        <li><strong>No</strong> communication during the game.</li>
                        <li>Both players can receive color or food questions.</li>
                        <li>Focus on <strong>consistency</strong> rather than <strong>randomness</strong>.</li>
                        <li>Keep your browser open to stay connected!</li>
                    </ul>
                `
            },
            simplified: {
                title: 'AQM Joe Rules (Simplified Mode)',
                content: `
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Plan your strategy with your partner before starting!</li>
                        <li><strong>No</strong> communication during the game.</li>
                        <li>Player 1 gets color questions, Player 2 gets food questions.</li>
                        <li>Focus on <strong>consistency</strong> and <strong>coordination</strong>.</li>
                        <li>Keep your browser open to stay connected!</li>
                    </ul>
                `
            },
            aqmjoe: {
                title: 'AQM Joe Rules (AQM Joe Mode)',
                content: `
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Plan your strategy with your partner before starting!</li>
                        <li><strong>No</strong> communication during the game.</li>
                        <li>Both players can receive color or food questions.</li>
                        <li>Follow the AQM Joe success rules for best results.</li>
                        <li>Keep your browser open to stay connected!</li>
                    </ul>
                `
            }
        },
        winningConditions: {
            classic: {
                title: 'AQM Joe Conditions (Classic Mode)',
                content: `
                    <div style="margin-bottom: 15px;">
                        <strong>🎯 Best Balanced ⏐⟨Tr⟩⏐ (Consistency):</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>When both get the <strong>same question type</strong>, try to give the <strong>same answer</strong>.</li>
                            <li>Balance your answers: <strong>50% Green/Peas</strong> and <strong>50% Red/Carrots</strong>.</li>
                            <li>The AQM Joe theme only changes labels in classic mode.</li>
                        </ul>
                    </div>
                    <div>
                        <strong>🏆 Best CHSH (Correlation):</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>Standard CHSH rules apply with AQM Joe labels.</li>
                            <li>Focus on correlation patterns for optimal CHSH score.</li>
                        </ul>
                    </div>
                `
            },
            simplified: {
                title: 'AQM Joe Conditions (Simplified Mode)',
                content: `
                    <div>
                        <strong>🏆 Best Success Rate:</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>Standard simplified mode rules apply.</li>
                            <li>Follow optimal strategy for highest success rate.</li>
                        </ul>
                    </div>
                `
            },
            aqmjoe: {
                title: 'AQM Joe Success Rules (AQM Joe Mode)',
                content: `
                    <div>
                        <strong>🏆 AQM Joe Success Policy:</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li><strong>Mixed Color-Food:</strong> If one partner answers "Green", the other must answer "Peas" to succeed.</li>
                            <li><strong>Both Color:</strong> Both partners can answer "Green" sometimes (no constraint).</li>
                            <li><strong>Both Food:</strong> Never both answer "Peas" (at least one must choose "Carrots").</li>
                            <li>Optimize your strategy to maximize success rate!</li>
                        </ul>
                    </div>
                `
            }
        }
    }
};

// Theme utility functions
class ThemeManager {
    constructor() {
        this.currentTheme = 'food';
        this.currentMode = 'simplified';
    }
    
    setTheme(themeName) {
        if (THEMES[themeName]) {
            this.currentTheme = themeName;
            this.applyTheme();
        }
    }
    
    setMode(mode) {
        this.currentMode = mode;
        this.applyTheme();
    }
    
    getTheme() {
        return THEMES[this.currentTheme];
    }
    
    getItemDisplay(item) {
        const theme = this.getTheme();
        return theme.items[item] || item;
    }
    
    getAnswerLabels(item) {
        /**
         * Get answer labels for a specific item based on current theme.
         * For AQM Joe theme: A/B (color) -> True="Green"/False="Red", X/Y (food) -> True="Peas"/False="Carrots"
         * For other themes: use standard True/False
         */
        if (this.currentTheme === 'aqmjoe') {
            if (item === 'A' || item === 'B') {
                // Color questions
                return { true: 'Green', false: 'Red' };
            } else if (item === 'X' || item === 'Y') {
                // Food questions  
                return { true: 'Peas', false: 'Carrots' };
            }
        }
        // Default for all other themes
        return { true: 'True', false: 'False' };
    }
    
    getPlayerHint(playerNumber) {
        const theme = this.getTheme();
        
        // In classic and aqmjoe modes, both players can receive all question types
        if (this.currentMode === 'classic' || this.currentMode === 'aqmjoe') {
            if (theme.name === 'Food Ingredients') {
                return 'You will need to answer questions from all ingredients (🍞, 🥟, 🥬, 🍫)';
            } else if (theme.name === 'AQM Joe') {
                return 'You will answer questions about colors and food';
            } else {
                return 'You will need to answer questions from all categories (A, B, X, Y)';
            }
        }
        
        // In simplified mode, return player-specific hints
        return theme.playerHints[playerNumber] || '';
    }
    
    getQuestionBoxColor(playerNumber) {
        const theme = this.getTheme();
        if (playerNumber) {
            return theme.questionBoxColors[playerNumber] || theme.questionBoxColors.default;
        }
        return theme.questionBoxColors.default;
    }
    
    getQuestionTextColor() {
        const theme = this.getTheme();
        return theme.questionTextColor || '#1565c0';
    }
    
    applyTheme() {
        // Update game rules and winning conditions (doesn't need player data)
        this.updateGameRulesAndConditions();
        
        // Note: Question box styling and player responsibility messages are handled
        // by the app.js functions that have access to the proper player data
    }
    
    updateGameRulesAndConditions() {
        const theme = this.getTheme();
        
        // Update game rules
        const gameRulesTitle = document.getElementById('game-rules-title');
        const gameRulesContent = document.getElementById('game-rules-content');
        
        if (gameRulesTitle && gameRulesContent && theme.gameRules[this.currentMode]) {
            gameRulesTitle.textContent = theme.gameRules[this.currentMode].title;
            gameRulesContent.innerHTML = theme.gameRules[this.currentMode].content;
        }
        
        // Update winning conditions
        const winningTitle = document.getElementById('winning-conditions-title');
        const winningContent = document.getElementById('winning-conditions-content');
        
        if (winningTitle && winningContent && theme.winningConditions[this.currentMode]) {
            winningTitle.textContent = theme.winningConditions[this.currentMode].title;
            winningContent.innerHTML = theme.winningConditions[this.currentMode].content;
        }
    }
    
    // Get all available themes for selector
    getAvailableThemes() {
        return Object.keys(THEMES).map(key => ({
            key,
            name: THEMES[key].name,
            description: THEMES[key].description
        }));
    }
}

// Global theme manager instance
window.themeManager = new ThemeManager();