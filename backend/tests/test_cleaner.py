import hashlib
from app.cleaner.cleaner import ContentCleaner


def test_cleaner_removes_scripts_and_styles():
    html_input = """
    <div>
        <script>console.log('tracker');</script>
        <style>body { color: red; }</style>
        <p>Đây là câu mở đầu của chương truyện.</p>
        <div class="advertisement-banner">Quảng cáo cờ bạc giảm giá 50%</div>
        <p>Nhân vật chính bước vào đại điện.</p>
        <div class="share-buttons"><span>Share on Facebook</span></div>
        <p>Kết thúc chương 1.</p>
    </div>
    """
    cleaned, p_count, hash_val = ContentCleaner.clean(html_input)

    assert "tracker" not in cleaned
    assert "color: red" not in cleaned
    assert "Quảng cáo" not in cleaned
    assert "Share on Facebook" not in cleaned
    assert "Đây là câu mở đầu của chương truyện." in cleaned
    assert "Nhân vật chính bước vào đại điện." in cleaned
    assert "Kết thúc chương 1." in cleaned
    assert p_count == 3
    assert hash_val == hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def test_cleaner_removes_promo_boilerplate():
    html_input = """
    <p>Chương 1: Khởi đầu</p>
    <p>Please visit NovelBin to read the latest chapters for free.</p>
    <p>Hắn vung kiếm chém tới.</p>
    <p>Join our Discord server for novel updates.</p>
    """
    cleaned, p_count, _ = ContentCleaner.clean(html_input)

    assert "Please visit NovelBin" not in cleaned
    assert "Join our Discord" not in cleaned
    assert "Hắn vung kiếm chém tới." in cleaned
    assert p_count == 2


def test_cleaner_preserves_dialogue_and_quotes():
    html_input = """
    <p>「Ngươi là ai?」- Lý Tiêu quát lớn.</p>
    <p>"Ta là kiếm thánh phương bắc."</p>
    """
    cleaned, p_count, _ = ContentCleaner.clean(html_input)

    assert "「Ngươi là ai?」" in cleaned
    assert '"Ta là kiếm thánh phương bắc."' in cleaned
    assert p_count == 2
