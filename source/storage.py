import json
import hashlib
import os
from typing import Dict, Optional, Any, List

# Cố gắng import các class từ models và config
# Lưu ý: Cần đảm bảo file models.py và config.py đã có các Enum/Class này
try:
    from models import Profile, GameState, Entity, Maze
    from config import Difficulty, EntityKind, GameMode
except ImportError:
    # Fallback cho trường hợp chạy debug lẻ hoặc sai cấu trúc folder
    from .models import Profile, GameState, Entity, Maze
    from .config import Difficulty, EntityKind, GameMode

# --- CẤU HÌNH ĐƯỜNG DẪN ---
DATA_DIR = "data"
SAVES_DIR = os.path.join(DATA_DIR, "saves", "games")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")

# Đảm bảo thư mục tồn tại
os.makedirs(SAVES_DIR, exist_ok=True)

# --- HELPER FUNCTIONS ---

def _hash_password(password: str) -> str:
    """Mã hóa mật khẩu dùng SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def _profile_to_dict(profile: Profile) -> dict:
    """Chuyển đối tượng Profile thành Dictionary để lưu JSON."""
    return {
        "username": profile.username,
        "display_name": profile.display_name,
        "password_hash": profile.password_hash,
        "current_save": getattr(profile, "current_save", ""),
        "total_time": getattr(profile, "total_time", 0.0),

        # [Task D] Lưu tiến độ chơi
        "unlocked_levels": getattr(profile, "unlocked_levels", []),
        "best_steps": getattr(profile, "best_steps", {}),

        # [Task D] Lưu tùy chọn
        "options": getattr(profile, "options", {
            "music_on": True, "sfx_on": True, "language": "vi"
        })
    }

def _dict_to_profile(data: dict) -> Profile:
    """Chuyển Dictionary từ JSON thành đối tượng Profile."""
    p = Profile(
        username=data["username"],
        display_name=data["display_name"]
    )
    p.password_hash = data.get("password_hash", "")
    p.current_save = data.get("current_save", "")
    p.total_time = data.get("total_time", 0.0)

    # [Task D] Khôi phục tiến độ
    p.unlocked_levels = data.get("unlocked_levels", [])
    # Lưu ý: Python cho phép gán thuộc tính mới cho object kể cả khi class chưa định nghĩa
    p.best_steps = data.get("best_steps", {})

    # [Task D] Khôi phục tùy chọn
    default_options = {"music_on": True, "sfx_on": True, "language": "vi"}
    p.options = data.get("options", default_options)

    return p

# --- API QUẢN LÝ PROFILE (Authentication) ---

def load_profiles() -> Dict[str, Profile]:
    """Đọc toàn bộ profiles từ file JSON."""
    if not os.path.exists(PROFILES_FILE):
        return {}
    try:
        with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {u: _dict_to_profile(info) for u, info in data.items()}
    except (json.JSONDecodeError, IOError):
        return {}

def save_profiles(profiles: Dict[str, Profile]) -> None:
    """Ghi đè toàn bộ profiles vào file JSON."""
    data = {u: _profile_to_dict(p) for u, p in profiles.items()}
    with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def register(username: str, password: str, display_name: str) -> Optional[Profile]:
    """Đăng ký user mới. Trả về Profile nếu thành công, None nếu trùng username."""
    profiles = load_profiles()
    if username in profiles:
        return None

    new_profile = Profile(username=username, display_name=display_name)
    new_profile.password_hash = _hash_password(password)

    # Khởi tạo giá trị mặc định cho user mới
    new_profile.unlocked_levels = ["level_01"] # Mặc định mở level 1
    new_profile.best_steps = {}

    profiles[username] = new_profile
    save_profiles(profiles)
    return new_profile

def login(username: str, password: str) -> Optional[Profile]:
    """Đăng nhập. Trả về Profile nếu đúng user/pass."""
    profiles = load_profiles()
    if username not in profiles:
        return None

    profile = profiles[username]
    if profile.password_hash == _hash_password(password):
        return profile
    return None

def get_guest_profile() -> Profile:
    """Tạo profile khách (không lưu password)."""
    p = Profile(username="guest", display_name="Khách")
    p.unlocked_levels = ["level_01", "level_02", "level_03"] # Khách được chơi hết để test
    return p

# --- API LƯU / TẢI GAME (Save/Load System) ---

def save_game(profile: Profile, state: GameState, slot: int = 0) -> None:
    """Lưu trạng thái game hiện tại vào file riêng biệt."""
    filename = f"{profile.username}_slot{slot}.json"
    filepath = os.path.join(SAVES_DIR, filename)

    # 1. Serialize Enemies
    enemies_data = []
    for e in state.enemies:
        enemies_data.append({
            "type": e.kind.name, # Lưu tên Enum (VD: "MUMMY_WHITE")
            "pos": e.pos,
            "alive": getattr(e, "alive", True)
        })

    # 2. Serialize GameState
    # [Task D] Cần lưu move_count, status, level_id
    save_data = {
        "level_id": getattr(state, "level_id", "level_1"),
        "difficulty": getattr(state, "difficulty", Difficulty.NORMAL).value, # Lưu string value của Enum
        "move_count": state.move_count,
        "status": state.status,

        "player": {
            "pos": state.player.pos,
            "alive": state.player.alive
        },
        "enemies": enemies_data,

        # Có thể lưu thêm timestamp hoặc seed nếu là map random
        "is_random": False
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=4)

    # Cập nhật thông tin save mới nhất vào profile
    profile.current_save = filename
    # Lưu lại profile để nhớ save gần nhất
    profiles = load_profiles()
    if profile.username in profiles:
        profiles[profile.username] = profile
        save_profiles(profiles)

def load_game(profile: Profile, slot: int = 0) -> Optional[GameState]:
    """
    Tải save game.
    Lưu ý: Hàm này trả về GameState với maze=None.
    Logic game cần gọi maze_data.load_level_txt(state.level_id) để nạp map gốc,
    sau đó gán lại player/enemies từ state này vào.
    """
    filename = f"{profile.username}_slot{slot}.json"
    filepath = os.path.join(SAVES_DIR, filename)

    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 1. Tái tạo Player Entity
        p_data = data["player"]
        player = Entity(
            kind=EntityKind.PLAYER,
            pos=tuple(p_data["pos"]), # Chuyển list [x,y] về tuple (x,y)
            alive=p_data.get("alive", True)
        )

        # 2. Tái tạo Enemies List
        enemies = []
        for e_data in data["enemies"]:
            # Tìm Enum tương ứng với string (VD: "MUMMY_WHITE" -> EntityKind.MUMMY_WHITE)
            kind_name = e_data["type"]
            kind_enum = getattr(EntityKind, kind_name, EntityKind.MUMMY_WHITE)

            e = Entity(
                kind=kind_enum,
                pos=tuple(e_data["pos"]),
                alive=e_data.get("alive", True)
            )
            enemies.append(e)

        # 3. Lấy thông tin meta
        level_id = data.get("level_id", "level_1")
        # Chuyển string difficulty về Enum
        diff_str = data.get("difficulty", "normal")
        # Map thủ công hoặc dùng loop để tìm Enum đúng
        difficulty = Difficulty.NORMAL
        for d in Difficulty:
            if d.value == diff_str:
                difficulty = d
                break

        # 4. Tạo GameState (với Maze = None)
        # Logic bên ngoài sẽ phụ trách load Maze dựa trên level_id
        state = GameState(
            maze=None, # Placeholder
            player=player,
            enemies=enemies,
            mode=GameMode.ADVENTURE, # Mặc định hoặc lưu thêm trong save
            difficulty=difficulty,
            move_count=data.get("move_count", 0),
            status=data.get("status", "RUNNING")
        )

        # Gán thuộc tính tạm để logic biết map nào cần load
        state.level_id = level_id

        return state

    except Exception as e:
        print(f"[Error] Load game failed: {e}")
        return None

# ... (Code cũ của bạn ở trên) ...

# --- PHẦN TEST NHANH (Thêm vào cuối file) ---
if __name__ == "__main__":
    print("Đang chạy test riêng file storage...")
    
    # Test thử đăng ký
    u = "admin_test"
    p = "123456"
    reg = register(u, p, "Admin Test")
    print(f"Đăng ký: {reg}")
    
    # Test thử đăng nhập
    log = login(u, p)
    if log:
        print(f"Đăng nhập thành công: {log.username}")
        # Test thử load game của user này
        g = load_game(log, 0)
        print(f"Load game slot 0: {g}")
    else:
        print("Đăng nhập thất bại.")
