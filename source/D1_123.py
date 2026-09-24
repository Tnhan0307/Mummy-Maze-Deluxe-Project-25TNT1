import json
import hashlib
import os
from typing import Dict, Optional, Any
# Giả định các class này đã được cập nhật property tương ứng bên models.py
from models import Profile, GameState, Difficulty

# Cấu hình đường dẫn
DATA_DIR = "data"
SAVES_DIR = os.path.join(DATA_DIR, "saves", "games")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")

os.makedirs(SAVES_DIR, exist_ok=True)

# --- Helper Functions ---

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _profile_to_dict(profile: Profile) -> dict:
    """Chuyển đổi object Profile sang dict theo cấu trúc mới."""
    return {
        "username": profile.username,
        "display_name": profile.display_name,
        "password_hash": profile.password_hash,
        # Thay đổi: unlocked_levels -> current_save
        "current_save": getattr(profile, "current_save", None),
        # Thay đổi: best_steps -> total_time
        "total_time": getattr(profile, "total_time", 0.0),
        # Thay đổi: options structure
        "options": getattr(profile, "options", {
            "music_volume": 0.5, 
            "sfx_volume": 0.5, 
            "language": "en", 
            "show_ankh": True
        })
    }

def _dict_to_profile(data: dict) -> Profile:
    """Chuyển đổi dict từ JSON sang object Profile."""
    p = Profile(
        username=data["username"],
        password="", 
        display_name=data["display_name"]
    )
    p.password_hash = data["password_hash"]
    
    # Map các trường mới vào object Profile
    p.current_save = data.get("current_save", None)
    p.total_time = data.get("total_time", 0.0)
    
    # Load options, nếu thiếu thì fill default
    opts = data.get("options", {})
    p.options = {
        "music_volume": opts.get("music_volume", 0.5), # Default 50%
        "sfx_volume": opts.get("sfx_volume", 0.5),
        "language": "en", # Force English
        "show_ankh": opts.get("show_ankh", True)
    }
    return p

# --- API FUNCTIONS ---

def load_profiles() -> Dict[str, Profile]:
    if not os.path.exists(PROFILES_FILE):
        return {}
    
    try:
        with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {u: _dict_to_profile(info) for u, info in data.items()}
    except (json.JSONDecodeError, IOError):
        return {}

def save_profiles(profiles: Dict[str, Profile]) -> None:
    data = {u: _profile_to_dict(p) for u, p in profiles.items()}
    with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def register(username: str, password: str, display_name: str) -> Optional[Profile]:
    profiles = load_profiles()
    
    if username in profiles:
        return None 
    
    new_profile = Profile(username=username, password=password, display_name=display_name)
    new_profile.password_hash = _hash_password(password)
    
    # Khởi tạo giá trị mặc định mới
    new_profile.current_save = None # Chưa có save nào
    new_profile.total_time = 0.0
    new_profile.options = {
        "music_volume": 1.0, # Max volume
        "sfx_volume": 1.0,
        "language": "en",
        "show_ankh": True
    }

    profiles[username] = new_profile
    save_profiles(profiles)
    return new_profile

def login(username: str, password: str) -> Optional[Profile]:
    profiles = load_profiles()
    
    if username not in profiles:
        return None
    
    profile = profiles[username]
    if profile.password_hash == _hash_password(password):
        return profile
    
    return None

def save_game(profile: Profile, state: GameState, slot: int = 0) -> None:
    """
    Lưu game state xuống file JSON.
    Cấu trúc khớp với format level.json và các yêu cầu mới.
    """
    filename = f"{profile.username}_slot{slot}.json"
    filepath = os.path.join(SAVES_DIR, filename)

    # Xử lý Difficulty: chuyển Enum hoặc String về chữ thường
    diff = getattr(state, "difficulty", "normal")
    if hasattr(diff, "name"): # Nếu là Enum
        diff_str = diff.name.lower()
    else:
        diff_str = str(diff).lower() # Nếu là string
        
    # Chuẩn bị data cho Objects (Gate, Key, Traps)
    # Giả định state.gate, state.key là object Entity hoặc None
    
    # 1. Gate
    gate_info = None
    if hasattr(state, "gate") and state.gate:
        gate_info = {
            "pos": state.gate.pos,
            "status": "open" if getattr(state.gate, "is_open", False) else "close"
        }

    # 2. Key (Optional)
    key_info = None
    if hasattr(state, "key") and state.key:
        key_info = {
            "pos": state.key.pos,
            "is_collected": getattr(state.key, "is_collected", False)
        }

    # 3. Traps (List)
    traps_list = []
    if hasattr(state, "traps"):
        for trap in state.traps:
            traps_list.append({
                "type": getattr(trap, "type", "spike"), # Ví dụ: spike, pit
                "pos": trap.pos,
                "active": getattr(trap, "active", True)
            })

    save_data = {
        # Thông tin định danh level
        "pyramid_id": getattr(state, "pyramid_id", "pyramid_tutorial"),
        "level_id": getattr(state, "level_id", "level_01"),
        
        # Trạng thái game
        "difficulty": diff_str,  # easy / normal / hard
        "time": getattr(state, "time", 0.0), # Thay move_count bằng time
        "status": getattr(state, "status", "RUNNING"),
        
        # Player
        "player": {
            "pos": state.player.pos,
            "hp": getattr(state.player, "hp", 3)
        },

        # Enemies
        "enemies": [
            {
                "type": e.type, 
                "pos": e.pos, 
                "id": getattr(e, "id", i), # Fallback id index nếu k có id
                "is_alive": getattr(e, "is_alive", True)
            } 
            for i, e in enumerate(getattr(state, "enemies", []))
        ],

        # Objects đặc biệt (theo yêu cầu)
        "objects": {
            "gate": gate_info,
            "key": key_info,
            "traps": traps_list
        }
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=4)

def load_game(profile: Profile, slot: int = 0) -> Optional[GameState]:
    """
    Load data thô từ file save.
    Hàm này trả về GameState sơ khai chứa dữ liệu để Logic xử lý tiếp.
    """
    filename = f"{profile.username}_slot{slot}.json"
    filepath = os.path.join(SAVES_DIR, filename)
    
    if not os.path.exists(filepath):
        return None
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Tạo GameState trống (Logic cần fill data thật dựa trên saved_data_payload)
        # Lưu ý: Các tham số khởi tạo này phụ thuộc vào models.GameState của bạn
        loaded_state = GameState(
            difficulty=data.get("difficulty", "normal")
        )
        
        # Inject toàn bộ raw data vào state để Logic layer bung ra
        loaded_state.saved_data_payload = data 
        
        return loaded_state
        
    except Exception as e:
        print(f"Error loading save: {e}")
        return None