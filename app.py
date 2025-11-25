import streamlit as st
import chess
import chess.svg
import os
import time


# --- CONFIGURAÇÃO DO AMBIENTE E PERMISSÕES ---
STOCKFISH_PATH = "./stockfish" 

if os.path.exists(STOCKFISH_PATH):
    if not os.access(STOCKFISH_PATH, os.X_OK):
        try:
            os.chmod(STOCKFISH_PATH, 0o755)
        except Exception as e:
            st.warning(f"Aviso de Permissão: {e}")


try:
    from stockfish import Stockfish
except ImportError:
    st.error("🚨 Biblioteca 'stockfish' não encontrada. Instale com: pip install stockfish")
    st.stop()


# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Titan Chess - Sandbox Mode", layout="wide", page_icon="♟️")


# CSS Otimizado
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #c9d1d9; }
    .stButton>button { border: 1px solid #30363d; background-color: #21262d; color: #c9d1d9; transition: all 0.2s; }
    .stButton>button:hover { border-color: #58a6ff; color: #58a6ff; transform: scale(1.02); }
    .stTextArea textarea { font-family: 'Courier New', monospace; background-color: #0d1117; }
    </style>
""", unsafe_allow_html=True)


# --- ESTADO PERSISTENTE ---
def init_state():
    if 'board' not in st.session_state:
        st.session_state.board = chess.Board()
    if 'game_log' not in st.session_state:
        st.session_state.game_log = []
    if 'stockfish' not in st.session_state:
        st.session_state.stockfish = None
    if 'engine_params' not in st.session_state:
        st.session_state.engine_params = {}
    if 'orientation' not in st.session_state:
        st.session_state.orientation = chess.WHITE
    if 'selected_square' not in st.session_state:
        st.session_state.selected_square = None
    if 'valid_moves_from_square' not in st.session_state:
        st.session_state.valid_moves_from_square = []


# --- CARREGAMENTO DO MOTOR ---
@st.cache_resource(show_spinner=False)
def load_engine_process(path):
    """Instancia o Stockfish com configuração otimizada"""
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
        st.error(f"Erro ao carregar o motor: {e}")
        return None


def update_engine_dynamic(sf_instance, depth, skill):
    """Atualiza parâmetros dinâmicos do motor"""
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


# --- CONVERSÃO DE COORDENADAS ---
def pixel_to_square(x, y, board_size=650, orientation=chess.WHITE):
    """Converte coordenadas de pixel para notação chess"""
    square_size = board_size / 8
    file_idx = int(x // square_size)
    rank_idx = int(y // square_size)
    
    if orientation == chess.BLACK:
        file_idx = 7 - file_idx
        rank_idx = 7 - rank_idx
    
    file = chr(ord('a') + file_idx)
    rank = str(8 - rank_idx)
    
    return file + rank


def process_move(board, move_input, is_uci=False):
    """Processa movimento em notação SAN ou UCI"""
    try:
        if is_uci:
            move = board.parse_uci(move_input) if len(move_input) == 4 else board.parse_san(move_input)
        else:
            try:
                move = board.parse_san(move_input)
            except:
                move = board.parse_uci(move_input)
        
        if move in board.legal_moves:
            return True, f"✓ Movimento: {move}", move
        else:
            return False, f"⚠️ Movimento ilegal: {move_input}", None
    except Exception as e:
        return False, f"⚠️ Erro: {str(e)}", None


# --- LÓGICA PRINCIPAL ---
def main():
    init_state()

    # --- BARRA LATERAL ---
    with st.sidebar:
        st.title("♟️ Titan Chess")
        
        # Seletor de Modo de Jogo
        st.markdown("### 🎮 Modo de Jogo")
        game_mode = st.selectbox(
            "Selecione a Dinâmica:",
            [
                "Sandbox (Livre - Jogar pelos dois)",
                "Humano vs Stockfish (Jogar de Brancas)",
                "Stockfish vs Humano (Jogar de Pretas)"
            ],
            help="Sandbox permite que você mova qualquer peça."
        )

        st.divider()

        # Controles de Reset e Orientação
        col_reset, col_flip = st.columns(2)
        with col_reset:
            if st.button("🔄 Reiniciar", width="content"):
                st.session_state.board.reset()
                st.session_state.game_log = []
                st.session_state.selected_square = None
                st.session_state.valid_moves_from_square = []
                st.rerun()
        with col_flip:
            if st.button("🔄 Virar", width="content"):
                st.session_state.orientation = chess.BLACK if st.session_state.orientation == chess.WHITE else chess.WHITE
                st.rerun()

        st.divider()
        
        # Configuração do Motor
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
        st.warning("⚠️ Motor não carregado. Você pode jogar no modo manual.")

    # --- ÁREA DO TABULEIRO ---
    col_board, col_hud = st.columns([1.5, 1])

    with col_board:
        st.subheader("♟️ Tabuleiro Interativo")
        
        board = st.session_state.board
        
        # Renderiza o SVG
        svg = chess.svg.board(
            board, 
            lastmove=board.peek() if board.move_stack else None,
            size=650,
            coordinates=True,
            orientation=st.session_state.orientation,
        )
        
        st.image(svg, use_container_width=False, width=650)
        
        st.divider()
        st.markdown("### 📍 Modos de Movimento")
        
        # Tabs para os dois modos
        tab1, tab2 = st.tabs(["Notação Chess", "Coordenadas (X, Y)"])
        
        with tab1:
            st.markdown("**Digite movimentos em notação chess:**\n- UCI: `e2e4`, `g1f3`\n- SAN: `e4`, `Nf3`")
            
            col_input, col_btn = st.columns([3, 1])
            with col_input:
                move_input = st.text_input(
                    "Movimento:",
                    placeholder="ex: e2e4 ou e4",
                    key="move_input_notation",
                    label_visibility="collapsed"
                )
            with col_btn:
                if st.button("🎯 Mover", width="content", key="btn_notation"):
                    if move_input.strip():
                        # Validar cor
                        ai_should_play = False
                        if game_mode == "Humano vs Stockfish" and board.turn == chess.WHITE:
                            ai_should_play = False  # Humano joga de Brancas
                        elif game_mode == "Stockfish vs Humano" and board.turn == chess.BLACK:
                            ai_should_play = False  # Humano joga de Pretas
                        
                        success, msg, move = process_move(board, move_input.strip(), is_uci=False)
                        if success:
                            board.push(move)
                            st.session_state.game_log.append(str(move))
                            st.success(msg)
                            time.sleep(0.3)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("⚠️ Digite um movimento!")
        
        with tab2:
            st.markdown("**Clique na peça (1º), depois no destino (2º):**\n- X: 0-650 | Y: 0-650")
            
            col1, col2, col3 = st.columns([1.5, 1.5, 1])
            with col1:
                click_x = st.number_input("X (pixels):", min_value=0, max_value=650, step=1, key="click_x", value=100)
            with col2:
                click_y = st.number_input("Y (pixels):", min_value=0, max_value=650, step=1, key="click_y", value=100)
            with col3:
                if st.button("🎯 Processar", width="content", key="btn_coords"):
                    square_name = pixel_to_square(click_x, click_y, 650, st.session_state.orientation)
                    square_obj = chess.parse_square(square_name)
                    
                    if st.session_state.selected_square is None:
                        piece = board.piece_at(square_obj)
                        if piece and piece.color == board.turn:
                            st.session_state.selected_square = square_name
                            moves = [str(m) for m in board.legal_moves if str(m)[:2] == square_name]
                            st.session_state.valid_moves_from_square = moves
                            st.success(f"✓ Peça selecionada: **{square_name}**")
                            st.rerun()
                        else:
                            st.error(f"⚠️ Nenhuma peça em {square_name}!")
                    else:
                        from_sq = st.session_state.selected_square
                        to_sq = square_name
                        move_uci = from_sq + to_sq
                        
                        success, msg, move = process_move(board, move_uci, is_uci=True)
                        if success:
                            board.push(move)
                            st.session_state.game_log.append(move_uci)
                            st.session_state.selected_square = None
                            st.session_state.valid_moves_from_square = []
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                            st.session_state.selected_square = None
                            st.rerun()

    # --- PAINEL DE INFORMAÇÕES E IA ---
    with col_hud:
        turn_color = "Brancas" if board.turn == chess.WHITE else "Pretas"
        color_css = "blue" if board.turn == chess.WHITE else "red"
        
        st.markdown(f"### Vez das :{color_css}[{turn_color}]")
        
        # Mostrar seleção
        if st.session_state.selected_square:
            st.info(f"📍 Selecionado: **{st.session_state.selected_square}**")
            if st.session_state.valid_moves_from_square:
                st.caption(f"**{len(st.session_state.valid_moves_from_square)}** movimentos válidos")
        
        st.divider()
        
        # Lógica de Controle da IA
        ai_should_play = False
        if game_mode == "Humano vs Stockfish" and board.turn == chess.BLACK:
            ai_should_play = True
        elif game_mode == "Stockfish vs Humano" and board.turn == chess.WHITE:
            ai_should_play = True
        
        # Botão Manual de "Lance da IA"
        if st.button("⚡ Lance Sugerido (IA)", type="secondary", width="content"):
            ai_should_play = True
        
        # Execução da IA
        if ai_should_play and st.session_state.stockfish and not board.is_game_over():
            with st.spinner(f"🤖 Stockfish pensando (depth={depth})..."):
                st.session_state.stockfish.set_fen_position(board.fen())
                best_move_uci = st.session_state.stockfish.get_best_move_time(1000)
                
                if best_move_uci:
                    move = chess.Move.from_uci(best_move_uci)
                    board.push(move)
                    st.session_state.game_log.append(best_move_uci)
                    st.session_state.selected_square = None
                    st.session_state.valid_moves_from_square = []
                    st.success(f"✓ Stockfish jogou: **{best_move_uci}**")
                    time.sleep(0.5)
                    st.rerun()

        st.divider()
        
        # Feedback de Fim de Jogo
        if board.is_checkmate():
            st.error(f"🏁 Xeque-mate! Vitória das {'Pretas' if board.turn == chess.WHITE else 'Brancas'}.")
        elif board.is_stalemate():
            st.warning("🤝 Empate por Afogamento (Stalemate).")
        elif board.is_insufficient_material():
            st.warning("🤝 Empate por Material Insuficiente.")
        elif board.is_check():
            st.warning(f"⚠️ XEQUE! {turn_color} em xeque!")

        st.divider()
        
        # Histórico de Lances
        if st.session_state.game_log:
            st.markdown("#### 📋 Histórico")
            
            pgn_text = ""
            for i, move in enumerate(st.session_state.game_log):
                if i % 2 == 0:
                    pgn_text += f"{(i // 2) + 1}. {move} "
                else:
                    pgn_text += f"{move}  \n"
            
            st.text_area("Partida em PGN", pgn_text, height=150, disabled=True)
            
            # Estatísticas
            st.markdown("**Estatísticas:**")
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("Movimentos", len(st.session_state.game_log))
            with col_s2:
                st.metric("Rodadas", (len(st.session_state.game_log) + 1) // 2)
            with col_s3:
                status = "🏁 Fim" if board.is_game_over() else "🎮 Jogando"
                st.metric("Status", status)


if __name__ == "__main__":
    main()