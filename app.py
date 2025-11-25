import streamlit as st
import chess
import chess.svg
import os
import time

# --- INÍCIO DA CORREÇÃO DE PERMISSÃO ---
STOCKFISH_PATH = "./stockfish" 

if not os.access(STOCKFISH_PATH, os.X_OK):
    print(f"Definindo permissão de execução para: {STOCKFISH_PATH}")
    os.chmod(STOCKFISH_PATH, 0o755)

try:
    from stockfish import Stockfish
except ImportError:
    st.error("🚨 Biblioteca 'stockfish' não encontrada. Instale com: pip install stockfish")
    st.stop()


# --- CONFIGURAÇÃO DE ALTA PERFORMANCE ---
st.set_page_config(page_title="Titan Chess Engine", layout="wide", page_icon="♟️")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #c9d1d9; }
    .stButton>button { border: 1px solid #30363d; background-color: #21262d; color: #c9d1d9; }
    .stButton>button:hover { border-color: #58a6ff; color: #58a6ff; }
    div.stSpinner > div { border-top-color: #58a6ff !important; }
    .selected-square { border: 4px solid #58a6ff; border-radius: 4px; }
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
    if 'player_color' not in st.session_state:
        st.session_state.player_color = chess.WHITE
    if 'orientation' not in st.session_state:
        st.session_state.orientation = chess.WHITE
    if 'selected_square' not in st.session_state:
        st.session_state.selected_square = None
    if 'valid_moves_from_square' not in st.session_state:
        st.session_state.valid_moves_from_square = []
    if 'click_count' not in st.session_state:
        st.session_state.click_count = 0


# --- FUNÇÃO DO MOTOR ---
@st.cache_resource(show_spinner=False)
def load_engine_process(path):
    """Carrega o Stockfish 17.1 com configuração otimizada"""
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
        st.error(f"Erro Crítico de Inicialização do Motor: {e}")
        return None


def update_engine_dynamic(sf_instance, depth, skill):
    """Atualiza parâmetros dinâmicos do engine"""
    if sf_instance is None:
        return

    current_params = {
        "depth": depth,
        "skill": skill,
    }

    if st.session_state.engine_params != current_params:
        try:
            sf_instance.set_depth(depth)
            sf_instance.set_skill_level(skill)
            sf_instance.update_engine_parameters({
                "Minimum Thinking Time": 50 
            })
            st.session_state.engine_params = current_params
        except Exception as e:
            st.warning(f"⚠️ Falha ao atualizar parâmetros dinâmicos: {e}")


# --- CONVERSÃO DE COORDENADAS ---
def pixel_to_square(x, y, board_size=650, orientation=chess.WHITE):
    """
    Converte coordenadas de pixel para notação chess (e.g., 'e4')
    """
    square_size = board_size / 8
    file_idx = int(x // square_size)
    rank_idx = int(y // square_size)
    
    # Ajusta baseado na orientação
    if orientation == chess.BLACK:
        file_idx = 7 - file_idx
        rank_idx = 7 - rank_idx
    
    file = chr(ord('a') + file_idx)
    rank = str(8 - rank_idx)
    
    return file + rank


# --- LÓGICA DO JOGO ---
def main():
    init_state()

    with st.sidebar:
        st.header("⚙️ Parâmetros do Sistema")
        
        st.markdown("### 🏳️ Seleção de Lado")
        
        color_choice = st.radio(
            "Jogar como:", 
            ["Brancas", "Pretas"], 
            index=0 if st.session_state.player_color == chess.WHITE else 1
        )
        
        chosen_color = chess.WHITE if color_choice == "Brancas" else chess.BLACK
        
        if st.button("🔄 Novo Jogo / Aplicar Cor", use_container_width=True):
            st.session_state.board.reset()
            st.session_state.game_log = []
            st.session_state.selected_square = None
            st.session_state.valid_moves_from_square = []
            st.session_state.player_color = chosen_color
            st.session_state.orientation = chosen_color 
            st.rerun()

        st.divider()
        
        st.info(f"🔧 Engine: **3 Threads** | **128 MB Hash**")
        st.caption("Stockfish 17.1 otimizado para Streamlit Cloud")

        default_path = "./stockfish"
        engine_path = st.text_input("Path do Motor:", value=default_path)
        
        depth = st.slider("Profundidade de Análise", 10, 30, 18)
        skill = st.slider("Nível de Habilidade (Elo Simulado)", 0, 20, 20)


    # --- CARREGAMENTO DO MOTOR ---
    engine = load_engine_process(engine_path)
    
    if engine:
        update_engine_dynamic(engine, depth, skill)
        st.session_state.stockfish = engine
    else:
        st.error(f"❌ Motor não encontrado em: {engine_path}")
        st.stop()


    # --- INTERFACE ---
    col_board, col_hud = st.columns([1.5, 1])

    with col_board:
        st.subheader("♟️ Tabuleiro Interativo")
        
        board = st.session_state.board
        visual_orientation = st.session_state.orientation
        
        # Renderiza o SVG do tabuleiro (compatível com Streamlit Cloud)
        svg = chess.svg.board(
            board, 
            lastmove=board.peek() if board.move_stack else None,
            size=650,
            coordinates=True,
            orientation=visual_orientation,
            arrows=[],  # Sem setas adicionais para economizar recursos
        )
        
        # Renderiza SVG diretamente (sem cairosvg)
        st.image(svg, use_container_width=False, width=650)
        
        # Interface de cliques - compatível com streamlit-image-coordinates
        st.markdown("**Clique na peça desejada, depois no destino**")
        
        try:
            from streamlit_image_coordinates import streamlit_image_coordinates
            
            # Renderiza SVG novamente para capturar cliques
            coords = streamlit_image_coordinates(svg, width=650)
            
            if coords:
                x, y = coords['x'], coords['y']
                square_name = pixel_to_square(x, y, 650, visual_orientation)
                square_obj = chess.parse_square(square_name)
                
                # Se nenhum quadrado selecionado, seleciona a peça
                if st.session_state.selected_square is None:
                    piece = board.piece_at(square_obj)
                    if piece and piece.color == board.turn and piece.color == st.session_state.player_color:
                        st.session_state.selected_square = square_name
                        # Calcula moves válidos
                        moves = [str(m) for m in board.legal_moves if str(m)[:2] == square_name]
                        st.session_state.valid_moves_from_square = moves
                        st.success(f"✓ Peça selecionada: {square_name}")
                        st.rerun()
                    else:
                        st.error("⚠️ Nenhuma peça sua neste quadrado!")
                else:
                    # Tenta fazer o movimento
                    from_sq = st.session_state.selected_square
                    to_sq = square_name
                    move_uci = from_sq + to_sq
                    
                    try:
                        move = chess.Move.from_uci(move_uci)
                        if move in board.legal_moves:
                            board.push(move)
                            st.session_state.game_log.append(move_uci)
                            st.session_state.selected_square = None
                            st.session_state.valid_moves_from_square = []
                            st.success(f"✓ Movimento: {move_uci}")
                            st.rerun()
                        else:
                            st.error(f"⚠️ Movimento ilegal: {move_uci}")
                            st.session_state.selected_square = None
                            st.session_state.valid_moves_from_square = []
                            st.rerun()
                    except:
                        st.error("⚠️ Erro ao processar movimento!")
                        st.session_state.selected_square = None
                        st.rerun()
        
        except ImportError:
            st.warning("⚠️ streamlit-image-coordinates não instalado. Usando modo manual:")
            
            col1, col2 = st.columns(2)
            with col1:
                click_x = st.number_input("Clique X (pixel):", min_value=0, max_value=650, step=1, key="click_x")
            with col2:
                click_y = st.number_input("Clique Y (pixel):", min_value=0, max_value=650, step=1, key="click_y")
            
            if st.button("Processar Clique", use_container_width=True):
                square_name = pixel_to_square(click_x, click_y, 650, visual_orientation)
                square_obj = chess.parse_square(square_name)
                
                # Se nenhum quadrado selecionado, seleciona a peça
                if st.session_state.selected_square is None:
                    piece = board.piece_at(square_obj)
                    if piece and piece.color == board.turn and piece.color == st.session_state.player_color:
                        st.session_state.selected_square = square_name
                        # Calcula moves válidos
                        moves = [str(m) for m in board.legal_moves if str(m)[:2] == square_name]
                        st.session_state.valid_moves_from_square = moves
                        st.success(f"✓ Peça selecionada: {square_name}")
                        st.rerun()
                    else:
                        st.error("⚠️ Nenhuma peça sua neste quadrado!")
                else:
                    # Tenta fazer o movimento
                    from_sq = st.session_state.selected_square
                    to_sq = square_name
                    move_uci = from_sq + to_sq
                    
                    try:
                        move = chess.Move.from_uci(move_uci)
                        if move in board.legal_moves:
                            board.push(move)
                            st.session_state.game_log.append(move_uci)
                            st.session_state.selected_square = None
                            st.session_state.valid_moves_from_square = []
                            st.success(f"✓ Movimento: {move_uci}")
                            st.rerun()
                        else:
                            st.error(f"⚠️ Movimento ilegal: {move_uci}")
                            st.session_state.selected_square = None
                            st.session_state.valid_moves_from_square = []
                            st.rerun()
                    except:
                        st.error("⚠️ Erro ao processar movimento!")
                        st.session_state.selected_square = None
                        st.rerun()

    with col_hud:
        turn_text = "Brancas" if board.turn == chess.WHITE else "Pretas"
        
        if board.turn == st.session_state.player_color:
            st.subheader(f"Sua Vez (:blue[{turn_text}])")
            if st.session_state.selected_square:
                st.info(f"📍 Selecionado: {st.session_state.selected_square}")
                if st.session_state.valid_moves_from_square:
                    st.caption(f"Destinos válidos: {len(st.session_state.valid_moves_from_square)}")
                    with st.expander("Ver todos os movimentos"):
                        st.write(", ".join(st.session_state.valid_moves_from_square))
        else:
            st.subheader(f"Vez do Computador (:red[{turn_text}])")
        
        st.divider()

        # ENGINE
        if st.session_state.stockfish:
            st.markdown("#### 🧠 Titan Engine Analysis")
            
            use_time_limit = st.toggle("Limitar por Tempo", value=True)
            time_limit_ms = st.slider("Tempo (ms)", 100, 5000, 1000) if use_time_limit else None

            if st.button("⚡ Executar Lance da IA", type="primary", use_container_width=True):
                with st.spinner(f"Processando com 3 Threads em {depth} plies..."):
                    st.session_state.stockfish.set_fen_position(board.fen())
                    
                    start_t = time.time()
                    
                    if use_time_limit:
                        best_move = st.session_state.stockfish.get_best_move_time(time_limit_ms)
                    else:
                        best_move = st.session_state.stockfish.get_best_move()
                    
                    end_t = time.time()
                    
                    if best_move:
                        move = chess.Move.from_uci(best_move)
                        board.push(move)
                        st.session_state.game_log.append(best_move)
                        st.session_state.selected_square = None
                        st.session_state.valid_moves_from_square = []
                        st.success(f"Lance: {best_move} ({(end_t - start_t):.2f}s)")
                        time.sleep(0.5)
                        st.rerun()

        st.divider()

        # Histórico
        if st.session_state.game_log:
            st.text_area("PGN Raw", " ".join(st.session_state.game_log), height=100)
            
            # Estatísticas
            st.caption(f"Total de movimentos: {len(st.session_state.game_log)}")


if __name__ == "__main__":
    main()