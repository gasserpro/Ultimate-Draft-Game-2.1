import streamlit as st
import pandas as pd
import random
import os
import json

# --- PAGE CONFIG ---
st.set_page_config(page_title="Ultimate Draft Engine", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stImage > img { border-radius: 12px; border: 3px solid #444; object-fit: cover; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    .manager-stat { background-color: #f0f2f6; padding: 12px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid #ff4b4b; }
    .how-to-play-box { background-color: #1e293b; color: white; padding: 20px; border-radius: 12px; border: 2px solid #3b82f6; margin-top: 20px; }
    .bounce-arrow { font-size: 30px; text-align: center; animation: bounce 2s infinite; }
    @keyframes bounce {
        0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
        40% { transform: translateY(-10px); }
        60% { transform: translateY(-5px); }
    }
    </style>
    """, unsafe_allow_html=True)

st.title("⚽ Ultimate Draft Engine")

# --- AUTO-SAVE / RESTORE PROGRESS SYSTEM ---
SAVE_FILE = "draft_session_state.json"

def save_game_state():
    state_to_save = {
        "game_stage": st.session_state.game_stage,
        "current_round": st.session_state.current_round,
        "teams": st.session_state.teams,
        "budgets": st.session_state.budgets,
        "all_drafted": st.session_state.all_drafted,
        "drafters": st.session_state.get("drafters", []),
        "num_shown": st.session_state.get("num_shown", 3),
        "num_mystery": st.session_state.get("num_mystery", 2),
        "round_generated": st.session_state.get("round_generated", False),
        "round_pool_data": [
            {
                "type": card["type"],
                "data": card["data"],
                "chaos": card.get("chaos"),
                "revealed": card["revealed"]
            } for card in st.session_state.get("round_pool", [])
        ] if st.session_state.get("round_pool") else []
    }
    with open(SAVE_FILE, "w") as f:
        json.dump(state_to_save, f)

def load_saved_game_state():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                saved = json.load(f)
            st.session_state.game_stage = saved["game_stage"]
            st.session_state.current_round = saved["current_round"]
            st.session_state.teams = saved["teams"]
            st.session_state.budgets = saved["budgets"]
            st.session_state.all_drafted = saved["all_drafted"]
            st.session_state.drafters = saved["drafters"]
            st.session_state.num_shown = saved["num_shown"]
            st.session_state.num_mystery = saved["num_mystery"]
            st.session_state.round_generated = saved["round_generated"]
            st.session_state.round_pool = saved["round_pool_data"]
            return True
        except Exception:
            return False
    return False

def reset_saved_game():
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)

# --- INITIALIZE STATE ---
if "game_stage" not in st.session_state:
    if not load_saved_game_state():
        st.session_state.game_stage = "setup"
        st.session_state.current_round = 1
        st.session_state.teams = {}
        st.session_state.budgets = {}
        st.session_state.all_drafted = []

@st.cache_data(show_spinner=False)
def load_data():
    file_path = "/content/players pool.xlsx"
    if not os.path.exists(file_path): file_path = "players pool.xlsx"

    try:
        df = pd.read_excel(file_path).reset_index(drop=True)
        df.columns = [str(c).strip().lower() for c in df.columns]

        # SMART COLUMN MAPPING (Avoids duplicate names)
        final_cols = {}
        for col in df.columns:
            if 'image_url' not in final_cols and any(k in col for k in ['image', 'url', 'img', 'link']):
                final_cols[col] = 'image_url'
            elif 'name' not in final_cols and any(k in col for k in ['name', 'player', 'footballer']):
                final_cols[col] = 'name'
            elif 'position' not in final_cols and any(k in col for k in ['pos', 'role', 'spot']):
                final_cols[col] = 'position'

        df = df.rename(columns=final_cols)

        # Clean specific columns if they exist
        if 'name' in df.columns: df['name'] = df['name'].fillna("Unknown").astype(str).str.strip()
        if 'position' in df.columns: df['position'] = df['position'].fillna("??").astype(str).str.upper().str.strip()
        if 'image_url' in df.columns: df['image_url'] = df['image_url'].fillna("").astype(str).str.strip()

        return df[['name', 'position', 'image_url']]
    except Exception as e:
        st.error(f"Excel Load Error: {e}")
        return pd.DataFrame(columns=['name', 'position', 'image_url'])

df_players = load_data()

# Chaos cards pool with Budget Boost(100) as requested
chaos_cards_pool = ["Switch", "Just Say No", "Protect", "Budget Boost(100)"]

# --- SETUP STAGE ---
if st.session_state.game_stage == "setup":
    # Resume prompt if game state file is found
    if os.path.exists(SAVE_FILE):
        st.warning("⚠️ An unfinished draft was found!")
        col_res1, col_res2 = st.columns(2)
        if col_res1.button("📂 Resume Previous Game"):
            load_saved_game_state()
            st.rerun()
        if col_res2.button("🗑️ Start Completely Fresh"):
            reset_saved_game()
            st.rerun()

    st.subheader("Game Setup")
    c1, c2 = st.columns(2)
    num_managers = c1.number_input("Number of Managers:", 1, 8, 3)
    num_shown = c2.number_input("Visible Players per round:", 1, 15, 3)
    num_mystery = c1.number_input("Mystery Slots per round:", 0, 10, 2)

    st.divider()
    manager_names, manager_budgets = [], []
    for i in range(num_managers):
        m_c1, m_c2 = st.columns(2)
        m_name = m_c1.text_input(f"Manager {i+1} Name", f"Manager {i+1}", key=f"n_{i}")
        m_budget = m_c2.number_input(f"Budget for {m_name}", value=600, key=f"b_{i}", step=1)
        manager_names.append(m_name)
        manager_budgets.append(m_budget)

    if st.button("🚀 Start Draft"):
        st.session_state.drafters = manager_names
        st.session_state.budgets = {manager_names[i]: manager_budgets[i] for i in range(num_managers)}
        st.session_state.num_shown = num_shown
        st.session_state.num_mystery = num_mystery
        st.session_state.teams = {name: [] for name in manager_names}
        st.session_state.all_drafted = []
        st.session_state.game_stage = "drafting"
        st.session_state.current_round = 1
        st.session_state.round_generated = False
        save_game_state()
        st.rerun()

    # --- HOW TO PLAY SECTION WITH DOWNWARD ARROW ---
    st.divider()
    st.markdown("<p style='text-align: center; font-weight: bold; font-size: 20px; margin-bottom: 5px;'>How to Play</p>", unsafe_allow_html=True)
    st.markdown("<div class='bounce-arrow'>⬇️</div>", unsafe_allow_html=True)
    
    st.markdown("""
    <div class='how-to-play-box'>
        <h3>🎮 Rules & Instructions:</h3>
        <p><i>[Welcome to the Ultimate Draft Engine, a high-stakes, tactical game where managers compete over twelve intense rounds to build the perfect squad of eleven players and one manager. Starting with a set budget, you must constantly choose between bidding your hard-earned cash on highly coveted, visible star players in live auctions or taking a gamble on the mystery pool. Mystery cards are completely free to claim, but they come with a catch: a thirty percent chance of triggering game-changing chaos cards like Switch, Just Say No, Protect, or the massive Budget Boost(100), which instantly adds one hundred dollars back to your transfer funds. With a robust auto-save feature that protects your progress from sudden Wi-Fi cuts, the stage is perfectly set for an unpredictable, fast-paced battle of strategy, luck, and absolute chaos.]</i></p>
    </div>
    """, unsafe_allow_html=True)

# --- DRAFTING STAGE ---
elif st.session_state.game_stage == "drafting":
    positions = ["GK", "CB", "CB", "LB", "RB", "CM", "CM", "CM", "LW", "RW", "ST", "MANAGER"]

    if st.session_state.current_round > len(positions):
        st.title("🏆 DRAFT COMPLETE!")
        for m in st.session_state.drafters:
            st.write(f"### {m}'s Squad")
            st.info(", ".join([str(x) for x in st.session_state.teams[m]]))
        if st.button("🔄 New Game"):
            reset_saved_game()
            st.session_state.game_stage = "setup"
            st.rerun()
        st.stop()

    with st.sidebar:
        st.title("📊 Manager Status")
        for m in st.session_state.drafters:
            st.markdown(f"<div class='manager-stat'><b>{m}</b><br>Budget: ${st.session_state.budgets[m]}</div>", unsafe_allow_html=True)
            for p in st.session_state.teams[m]: st.caption(f"• {p}")
            st.divider()
        if st.button("Restart"):
            reset_saved_game()
            st.session_state.game_stage = "setup"
            st.rerun()

    curr_pos = positions[st.session_state.current_round-1]
    st.header(f"Round {st.session_state.current_round}: {curr_pos}")

    if not st.session_state.round_generated:
        available = df_players[df_players['position'] == curr_pos]
        available = available[~available['name'].isin(st.session_state.all_drafted)].reset_index(drop=True)

        needed = st.session_state.num_shown + st.session_state.num_mystery
        act_shown = min(st.session_state.num_shown, len(available))
        act_mystery = min(st.session_state.num_mystery, len(available) - act_shown)

        if (act_shown + act_mystery) > 0:
            round_selection = available.sample(act_shown + act_mystery).to_dict(orient="records")
            pool = []
            for _ in range(act_shown): pool.append({"type": "visible", "data": round_selection.pop(0), "revealed": True})
            for _ in range(act_mystery):
                p_data = round_selection.pop(0)
                chaos = random.choice(chaos_cards_pool) if random.random() < 0.30 else None
                pool.append({"type": "mystery", "data": p_data, "chaos": chaos, "revealed": False})
            random.shuffle(pool)
            st.session_state.round_pool = pool
        else:
            st.session_state.round_pool = []

        st.session_state.round_generated = True
        save_game_state()
        st.rerun()

    if st.session_state.round_pool:
        cols = st.columns(len(st.session_state.round_pool))
        for i, card in enumerate(st.session_state.round_pool):
            with cols[i]:
                if not card["revealed"]:
                    st.image("https://media.giphy.com/media/l0HlRnAWX5eUXU0qQ/giphy.gif", use_container_width=True)
                    if st.button(f"Reveal {i+1}", key=f"rev_{i}"):
                        card["revealed"] = True
                        save_game_state()
                        st.rerun()
                else:
                    p_data = card["data"]
                    img = str(p_data.get("image_url", "")).strip()
                    
                    # Safe image check + updated Streamlit syntax
                    if pd.notna(img) and str(img).strip():
                        st.image(img, use_container_width=True)
                    else:
                        st.image("https://via.placeholder.com/300x400?text=No+Photo", use_container_width=True)

                    st.write(f"### {p_data.get('name', 'Unknown')}")
                    
                    if card.get("chaos"): 
                        st.error(f"🃏 CHAOS: {card['chaos']}")

                    selected_mgr = st.selectbox("Assign to:", st.session_state.drafters, key=f"mgr_s_{i}")
                    
                    if card["type"] == "mystery":
                        if st.button("Claim Free", key=f"btn_{i}"):
                            st.session_state.teams[selected_mgr].append(p_data['name'])
                            if card.get("chaos"):
                                st.session_state.teams[selected_mgr].append(f"Chaos: {card['chaos']}")
                                # Check for Budget Boost(100) card
                                if card["chaos"] == "Budget Boost(100)":
                                    st.session_state.budgets[selected_mgr] += 100
                            st.session_state.all_drafted.append(p_data['name'])
                            save_game_state()
                            st.rerun()
                    else:
                        bid = st.number_input("Final Bid:", 0, st.session_state.budgets[selected_mgr], 0, key=f"bid_{i}", step=1)
                        if st.button("Confirm Draft", key=f"btn_{i}"):
                            st.session_state.budgets[selected_mgr] -= int(bid)
                            st.session_state.teams[selected_mgr].append(p_data['name'])
                            st.session_state.all_drafted.append(p_data['name'])
                            save_game_state()
                            st.rerun()
    else:
        st.warning(f"No more players available for {curr_pos}!")

    st.divider()
    if st.button("➡️ Next Round"):
        st.session_state.current_round += 1
        st.session_state.round_generated = False
        save_game_state()
        st.rerun()
