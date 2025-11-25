import streamlit as st
import chess
import chess.svg
import os
import time
import stat

# --- GESTÃO DE DEPENDÊNCIAS DO FRONT-END ---
# A interatividade visual depende desta biblioteca ponte (JS <-> Python).
try:
    from streamlit_chessboard import render_chessboard
except ImportError:
    st.error("""
    🚨 **Dependência Crítica Ausente**
    
    Para manipular o tabuleiro livremente, precisamos do componente de interface.
    Instale via terminal:
    `pip install streamlit-chessboard`
    """)
    st.stop()

# --- CONFIGURAÇÃO DO AMBIENTE E PERMISSÕES ---
STOCKFISH_PATH = "./stockfish" 

# Verificação proativa de integridade do binário
if os.path.exists(STOCKFISH_PATH):
    if not os.access(STOCKFISH_PATH, os.X_OK):
        # Tenta conceder permissão de execução (chmod +x)
        try:
            os.chmod(STOCKFISH_PATH, 0o755)
        except Exception as e:
            st.warning(f"Aviso de Permissão: Não foi possível tornar o Stockfish executável automaticamente. Erro: {e}")

try:
    from stockfish import Stockfish
except ImportError:
    st.error("🚨 Biblioteca 'stockfish' não encontrada. Instale com: pip install stockfish")
    st.stop()

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Titan Chess - Sandbox Mode", layout="wide", page_icon="♟️")

# CSS Otimizado para Foco e Contraste
st.markdown("""
    <style>
    /* Fundo escuro profundo para reduzir fadiga visual (Dark Mode Nativo) */
    .stApp { background-color: #0e1117; color: #c9d1d9; }
    
    /* Botões com feedback tátil visual */
    .stButton>button { border: 1px solid #30363d; background-color: #21262d; color: #c9d1d9; transition: all 0.2s; }
    .stButton>button:hover { border-color: #58a6ff; color: #58a6ff; transform: scale(1.02); }
    
    /* Centralização do Tabuleiro */
    iframe { display: block; margin: 0 auto; }
    
    /* Melhoria na legibilidade dos logs */
    .stTextArea textarea { font-family: 'Courier New', monospace; background-color: #0d1117; }
    </style>
""", unsafe_allow_html=True)

# --- ESTADO PERSISTENTE (State Management) ---
def init_state():
    # O tabuleiro lógico (backend)
    if 'board' not in st.session_state:
        st.session_state.board = chess.Board()
    
    # Histórico de lances (para display de PGN)
    if 'game_log' not in st.session_state:
        st.session_state.game_log = []
    
    # Instância do motor Stockfish
    if 'stockfish' not in st.session_state:
        st.session_state.stockfish = None
    
    # Parâmetros para evitar recargas desnecessárias do motor
    if 'engine_params' not in st.session_state:
        st.session_state.engine_params = {}
    
    # Controle de Orientação Visual (Flip Board)
    if 'orientation' not in st.session_state:
        st.session_state.orientation = 'white'

# --- CARREGAMENTO E OTIMIZAÇÃO DO MOTOR ---
@st.cache_resource(show_spinner=False)
def load_engine_process(path):
    """
    Instancia o processo do Stockfish com alocação fixa de memória.
    Configurado para alta performance (3 Threads, 128MB Hash).
    """
    if not os.path.isfile(path):
        return None
    try:
        return Stockfish(
            path=path, 
            depth=18, 
            parameters={
                "Threads": 3, 
                "Hash": 128, 
                "Ponder": "false"
            }
        )
    except Exception as e:
        st.error(f"Erro ao carregar o binário do motor: {e}")
        return None

def update_engine_dynamic(sf_instance, depth, skill):
    """Atualiza a força do motor sem reiniciar o processo."""
    if sf_instance is None:
        return

    current_params = {"depth": depth, "skill": skill}
    if st.session_state.engine_params != current_params:
        try:
            sf_instance.set_depth(depth)
            sf_instance.set_skill_level(skill)
            st.session_state.engine_params = current_params
        except Exception:
            pass

# --- LÓGICA PRINCIPAL ---
def main():
    init_state()

    # --- BARRA LATERAL (CONTROLES) ---
    with st.sidebar:
        st.title("♟️ Titan Chess")
        
        # 1. Seletor de Modo de Jogo (A CHAVE DA SUA SOLUÇÃO)
        st.markdown("### 🎮 Modo de Jogo")
        game_mode = st.selectbox(
            "Selecione a Dinâmica:",
            [
                "Sandbox (Livre - Jogar pelos dois)",
                "Humano vs Stockfish (Jogar de Brancas)",
                "Stockfish vs Humano (Jogar de Pretas)"
            ],
            help="Sandbox permite que você mova qualquer peça (desde que seja o turno dela)."
        )

        st.divider()

        # 2. Controles de Reset e Orientação
        col_reset, col_flip = st.columns(2)
        with col_reset:
            if st.button("🔄 Reiniciar", width="content"):
                st.session_state.board.reset()
                st.session_state.game_log = []
                st.rerun()
        with col_flip:
            if st.button("d2d7 Virar", width="content"):
                st.session_state.orientation = 'black' if st.session_state.orientation == 'white' else 'white'
                st.rerun()

        st.divider()
        
        # 3. Configuração do Motor
        st.markdown("### 🧠 Configuração da IA")
        engine_path = st.text_input("Caminho do Motor:", value="./stockfish")
        depth = st.slider("Profundidade (Depth)", 10, 30, 18)
        skill = st.slider("Habilidade (Skill Level)", 0, 20, 20)

    # Inicialização do Motor
    engine = load_engine_process(engine_path)
    if engine:
        update_engine_dynamic(engine, depth, skill)
        st.session_state.stockfish = engine
    else:
        st.warning("⚠️ Motor não carregado. Você pode jogar no modo manual, mas sem análise.")

    # --- ÁREA DO TABULEIRO ---
    col_board, col_hud = st.columns([1.5, 1])

    with col_board:
        board = st.session_state.board
        
        # Renderização do Tabuleiro Interativo
        # No modo Sandbox, a orientação visual não dita quem pode mover.
        # O componente permite mover qualquer peça que tenha lances legais no turno atual.
        move_data = render_chessboard(
            board.fen(), 
            key=f"board_{len(st.session_state.game_log)}_{st.session_state.orientation}", 
            orientation=st.session_state.orientation
        )

        # PROCESSAMENTO DO MOVIMENTO DO USUÁRIO
        if move_data:
            new_fen = move_data['fen']
            # Se o FEN mudou, significa que o usuário arrastou uma peça com sucesso
            if new_fen != board.fen():
                # Precisamos descobrir qual foi o lance para atualizar o log
                # Criamos um tabuleiro temporário para validar e extrair o lance
                # O 'render_chessboard' já valida se o lance é legal visualmente, 
                # mas precisamos sincronizar o backend Python.
                
                # A estratégia mais robusta aqui é iterar sobre os lances legais do estado atual
                # e ver qual deles resulta no novo FEN.
                for move in board.legal_moves:
                    board.push(move)
                    if board.fen() == new_fen:
                        # Encontramos o lance!
                        st.session_state.game_log.append(move.uci())
                        st.rerun() # Recarrega para confirmar
                        break
                    board.pop() # Desfaz se não for este

    # --- PAINEL DE INFORMAÇÕES E IA ---
    with col_hud:
        # Status do Turno
        turn_color = "Brancas" if board.turn == chess.WHITE else "Pretas"
        color_css = "blue" if board.turn == chess.WHITE else "red"
        
        st.markdown(f"### Vez das :{color_css}[{turn_color}]")
        
        # Lógica de Controle da IA
        # A IA só joga automaticamente se NÃO estivermos no modo Sandbox
        # E se for a vez dela.
        
        ai_should_play = False
        if game_mode == "Humano vs Stockfish" and board.turn == chess.BLACK:
            ai_should_play = True
        elif game_mode == "Stockfish vs Humano" and board.turn == chess.WHITE:
            ai_should_play = True
            
        # Botão Manual de "Lance da IA" (Sempre disponível para ajuda, mesmo no Sandbox)
        if st.button("⚡ Lance Sugerido (IA)", type="secondary", width="content"):
            ai_should_play = True # Força a IA a jogar este turno
            
        # Execução da IA
        if ai_should_play and st.session_state.stockfish and not board.is_game_over():
            with st.spinner(f"Stockfish pensando..."):
                st.session_state.stockfish.set_fen_position(board.fen())
                
                # Controle de tempo simples
                best_move_uci = st.session_state.stockfish.get_best_move_time(1000)
                
                if best_move_uci:
                    move = chess.Move.from_uci(best_move_uci)
                    board.push(move)
                    st.session_state.game_log.append(best_move_uci)
                    st.rerun()

        # Feedback de Fim de Jogo
        if board.is_checkmate():
            st.error(f"Xeque-mate! Vitória das {'Pretas' if board.turn == chess.WHITE else 'Brancas'}.")
        elif board.is_stalemate():
            st.warning("Empate por Afogamento (Stalemate).")
        elif board.is_insufficient_material():
            st.warning("Empate por Material Insuficiente.")

        st.divider()
        
        # Histórico de Lances (PGN Simplificado)
        if st.session_state.game_log:
            pgn_text = ""
            for i, move in enumerate(st.session_state.game_log):
                if i % 2 == 0:
                    pgn_text += f"{(i // 2) + 1}. {move} "
                else:
                    pgn_text += f"{move}  \n"
            
            st.text_area("Histórico da Partida", pgn_text, height=200)

if __name__ == "__main__":
    main()