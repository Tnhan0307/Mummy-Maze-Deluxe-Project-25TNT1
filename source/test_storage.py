# file: test_storage.py
import storage
from models import GameState, Entity
from config import Difficulty, EntityKind, GameMode

def run_test():
    print("=== BẮT ĐẦU TEST STORAGE ===")

    # 1. Test Đăng ký
    print("\n[1] Test Đăng ký...")
    # Thử xóa user cũ nếu có để test cho sạch (optional)
    try:
        p = storage.register("testuser_01", "matkhau123", "Người Test")
        if p:
            print("✅ Đăng ký thành công:", p.display_name)
        else:
            print("⚠️ User đã tồn tại (Không sao, test tiếp)")
    except Exception as e:
        print("❌ Lỗi đăng ký:", e)

    # 2. Test Đăng nhập
    print("\n[2] Test Đăng nhập...")
    profile = storage.login("testuser_01", "matkhau123")
    if profile:
        print("✅ Đăng nhập thành công! Level đã mở:", profile.unlocked_levels)
    else:
        print("❌ Đăng nhập thất bại -> Dừng test.")
        return

    # 3. Test Save Game
    print("\n[3] Test Lưu Game (Save)...")
    # Tạo một trạng thái giả để lưu
    dummy_player = Entity(kind=EntityKind.PLAYER, pos=(1, 1))
    dummy_enemy = Entity(kind=EntityKind.MUMMY_WHITE, pos=(3, 3))
    
    # Tạo GameState giả
    state = GameState(
        maze=None, # Save không lưu maze nên để None ok
        player=dummy_player,
        enemies=[dummy_enemy],
        mode=GameMode.ADVENTURE,
        difficulty=Difficulty.HARD,
        move_count=10,
        status="RUNNING"
    )
    # Gán ID level giả định
    state.level_id = "level_test"

    try:
        storage.save_game(profile, state, slot=0)
        print("✅ Đã gọi hàm save_game không báo lỗi.")
    except Exception as e:
        print("❌ Lỗi khi lưu:", e)

    # 4. Test Load Game
    print("\n[4] Test Tải Game (Load)...")
    loaded_state = storage.load_game(profile, slot=0)
    
    if loaded_state:
        print("✅ Load thành công!")
        print(f"   - Level ID: {loaded_state.level_id}")
        print(f"   - Số bước (Move count): {loaded_state.move_count}")
        print(f"   - Vị trí Player: {loaded_state.player.pos}")
        
        # Kiểm tra xem dữ liệu có khớp không
        if loaded_state.move_count == 10 and loaded_state.player.pos == (1, 1):
            print("🌟 DỮ LIỆU CHÍNH XÁC TUYỆT ĐỐI!")
        else:
            print("⚠️ Dữ liệu load lên bị sai lệch.")
    else:
        print("❌ Không tìm thấy file save.")

if __name__ == "__main__":
    run_test()