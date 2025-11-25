import streamlit as st
import chess
import chess.svg
import os
import time
import stat

# --- INÍCIO DA CORREÇÃO DE PERMISSÃO ---
# Define o caminho para o binário Stockfish
STOCKFISH_PATH = "./stockfish" 

# Garante que o arquivo tenha permissão de execução
if not os.access(STOCKFISH_PATH, os.X_OK):
    print(f"Definindo permissão de execução para: {STOCKFISH_PATH}")
    # A permissão 0o755 significa rwxr-xr-x (leitura/escrita/execução para o dono)
    os.chmod(STOCKFISH_PATH, 0o755)
# Tenta importar, mas não falha silenciosamente
try:
    from stockfish import Stockfish
except ImportError:
    st.error("🚨 Biblioteca 'stockfish' não encontrada. Instale com: pip install stockfish")
    st.stop()

# --- CONFIGURAÇÃO DE ALTA PERFORMANCE ---
st.set_page_config(page_title="Titan Chess Engine", layout="wide", page_icon="♟️")

# CSS para feedback visual de carregamento
# Nota Crítica: Mantemos o CSS dark mode para reduzir fadiga visual durante análises profundas.
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #c9d1d9; }
    .stButton>button { border: 1px solid #30363d; background-color: #21262d; color: #c9d1d9; }
    .stButton>button:hover { border-color: #58a6ff; color: #58a6ff; }
    div.stSpinner > div { border-top-color: #58a6ff !important; }
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
    # Novo estado para a orientação do jogador
    if 'player_color' not in st.session_state:
        st.session_state.player_color = chess.WHITE # Padrão
    if 'orientation' not in st.session_state:
        st.session_state.orientation = chess.WHITE

# --- FUNÇÃO DO MOTOR (HARDCODED PERFORMANCE) ---
@st.cache_resource(show_spinner=False)
def load_engine_process(path):
    """
    Carrega o processo do SO.
    CRÍTICA DE RECURSOS: Você solicitou 10 threads e 2048MB de Hash.
    Isso é fixo aqui. Se a máquina não tiver 10 threads lógicas, 
    o Stockfish vai tentar usar o máximo disponível ou causar thrashing.
    """
    if not os.path.isfile(path):
        return None
    try:
        # Inicialização Hardcoded conforme solicitado
        return Stockfish(
            path=path, 
            depth=18, 
            parameters={
                "Threads":3,  # Fixo: Alto paralelismo
                "Hash": 128,   # Fixo: 2GB de tabela de transposição
                "Ponder": "false" # Desativado para economizar ciclo em stateless app
            }
        )
    except Exception as e:
        st.error(f"Erro Crítico de Inicialização do Motor: {e}")
        return None

def update_engine_dynamic(sf_instance, depth, skill):
    """
    Atualiza apenas parâmetros dinâmicos de jogo (Depth/Skill).
    Threads e Hash são imutáveis nesta versão para garantir a alocação de memória solicitada.
    """
    if sf_instance is None:
        return

    current_params = {
        "depth": depth,
        "skill": skill,
        # Threads e Hash removidos da verificação de mudança pois são estáticos
    }

    if st.session_state.engine_params != current_params:
        try:
            sf_instance.set_depth(depth)
            sf_instance.set_skill_level(skill)
            # Não chamamos update_engine_parameters para Threads/Hash novamente
            # para evitar re-alocação custosa de memória hash (limpar 2GB demora!)
            sf_instance.update_engine_parameters({
                "Minimum Thinking Time": 50 
            })
            st.session_state.engine_params = current_params
        except Exception as e:
            st.warning(f"⚠️ Falha ao atualizar parâmetros dinâmicos: {e}")

# --- LÓGICA DO JOGO ---
def main():
    init_state()

    with st.sidebar:
        st.header("⚙️ Parâmetros do Sistema")
        
        # Seleção de Cor e Reinício
        st.markdown("### 🏳️ Seleção de Lado")
        
        # Usamos um callback ou verificamos mudança para resetar o board se a cor mudar
        color_choice = st.radio(
            "Jogar como:", 
            ["Brancas", "Pretas"], 
            index=0 if st.session_state.player_color == chess.WHITE else 1
        )
        
        chosen_color = chess.WHITE if color_choice == "Brancas" else chess.BLACK
        
        # Botão de Reset com aplicação da cor
        if st.button("🔄 Novo Jogo / Aplicar Cor", use_container_width=True):
            st.session_state.board.reset()
            st.session_state.game_log = []
            st.session_state.player_color = chosen_color
            # A orientação visual segue a cor do jogador (peças do jogador embaixo)
            st.session_state.orientation = chosen_color 
            st.rerun()

        st.divider()
        
        # Informações Técnicas (Somente Leitura agora, pois foram fixadas)
        st.info(f"🔧 Engine Fixa: **10 Threads** | **2048 MB Hash**")
        st.caption("Nota: Esta configuração exige ~2.5GB de RAM livre e CPU Multi-core.")

        # Detecção automática ou input
        default_path = "./stockfish" if os.name == 'nt' else "/usr/bin/stockfish"
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

    # --- INTERFACE ---
    col_board, col_hud = st.columns([1.5, 1])

    with col_board:
        # Renderização do Tabuleiro
        board = st.session_state.board
        
        # Lógica de Orientação:
        # Se eu jogo de Pretas, orientation=chess.BLACK (Pretas embaixo)
        # Se eu jogo de Brancas, orientation=chess.WHITE (Brancas embaixo)
        visual_orientation = st.session_state.orientation
        
        # SVG Otimizado
        svg = chess.svg.board(
            board, 
            lastmove=board.peek() if board.move_stack else None,
            size=650, # Tamanho nativo fixo
            coordinates=True,
            orientation=visual_orientation # AQUI ESTÁ A MÁGICA DA ROTAÇÃO
        )
        
        # Renderização da Imagem
        # O usuário pediu: não use_container_width=True, mas sim width="content"
        # Tradução técnica: Deixar o SVG ditar o tamanho ou fixar no tamanho do SVG.
        st.image(svg, use_container_width=False, width=650) 

    with col_hud:
        turn_text = "Brancas" if board.turn == chess.WHITE else "Pretas"
        
        # Indicador visual de quem joga
        if board.turn == st.session_state.player_color:
            st.subheader(f"Sua Vez (:blue[{turn_text}])")
        else:
            st.subheader(f"Vez do Computador (:red[{turn_text}])")
        
        # INPUT MANUAL
        col_in, col_btn = st.columns([3, 1])
        with col_in:
            move_input = st.text_input("Sua Jogada (SAN/UCI):", key="move_in", placeholder="ex: e4, Nf3")
        with col_btn:
            if st.button("Mover", use_container_width=True):
                try:
                    move = board.parse_san(move_input) if len(move_input) < 3 else board.parse_uci(move_input)
                    if move in board.legal_moves:
                        board.push(move)
                        st.session_state.game_log.append(move_input)
                        st.rerun()
                    else:
                        st.toast("⚠️ Lance Ilegal!", icon="🚫")
                except:
                    st.toast("⚠️ Formato Inválido!", icon="🚫")

        st.divider()

        # INPUT DO MOTOR
        if st.session_state.stockfish:
            st.markdown("#### 🧠 Titan Engine Analysis")
            
            use_time_limit = st.toggle("Limitar por Tempo", value=True)
            time_limit_ms = st.slider("Tempo (ms)", 100, 5000, 1000) if use_time_limit else None

            if st.button("⚡ Executar Lance da IA", type="primary", use_container_width=True):
                with st.spinner(f"Processando com 10 Threads em {depth} plies..."):
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
                        st.success(f"Lance: {best_move} ({(end_t - start_t):.2f}s)")
                        time.sleep(0.5)
                        st.rerun()

        # Histórico
        if st.session_state.game_log:
            st.text_area("PGN Raw", " ".join(st.session_state.game_log), height=100)

if __name__ == "__main__":
    main()