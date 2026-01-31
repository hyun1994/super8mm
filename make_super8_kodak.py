import re
from pathlib import Path
from moviepy.editor import VideoFileClip, CompositeVideoClip, concatenate_videoclips

# ========== 1. 경로 설정 ==========

SOURCE_DIR = Path("영상위치")
ASSET_DIR = Path("8mm효과소스위치")

GRAIN_FILE = ASSET_DIR / "Super 8 Grain.mp4"
LEAK_FILE = ASSET_DIR / "Film Light Leak.mp4"
EFFECT_24FPS_FILE = ASSET_DIR / "Super 8 24fps.mp4"

TARGET_WIDTH = 1080
TARGET_FPS = 24

OUTPUT_DIR = Path.home() / "super8_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "Kodak50D_super8mm.mp4"


# ========== 2. 숫자 추출해서 자동 정렬하는 함수 ==========

def extract_number(filename: str):
    match = re.search(r'(\d+)', filename)
    return int(match.group()) if match else 999999


def load_source_files_sorted():
    files = list(SOURCE_DIR.glob("*.MOV")) + list(SOURCE_DIR.glob("*.mp4"))
    files = sorted(files, key=lambda f: extract_number(f.name))
    print("[INFO] 자동 정렬된 소스:", [f.name for f in files])
    return files


# ========== 3. 더 날린 Kodak 50D 톤 ==========

def apply_kodak50d_fade_tone(img):
    """
    Kodak 50D 느낌:
    - shadow lift 더 강하게
    - contrast 낮추기
    - highlight soft
    - daylight yellow tone 강조
    """
    import numpy as np

    arr = img.astype("float32") / 255.0

    # 1) 더 강한 fade: blacks lift + whites soft
    arr = arr * 0.88 + 0.06   # 기존 0.95/0.03 → 더 페이드

    # 2) contrast 더 낮은 커브
    arr = (arr - 0.5) * 1.02 + 0.5  # 기존 1.05 → 1.02

    # 3) warm daylight 방향의 노란 톤
    r = arr[:, :, 0] * 1.05 + 0.02
    g = arr[:, :, 1] * 1.03 + 0.01
    b = arr[:, :, 2] * 0.97

    arr[:, :, 0] = r
    arr[:, :, 1] = g
    arr[:, :, 2] = b

    arr = np.clip(arr, 0.0, 1.0)
    arr = (arr * 255.0).astype("uint8")
    return arr


# ========== 4. 개별 클립 처리 ==========

def process_clip_kodak50d_fade(path: Path):
    print(f"[PROCESS] Kodak 50D Fade 적용: {path.name}")

    base = VideoFileClip(str(path)).resize(width=TARGET_WIDTH).set_fps(TARGET_FPS)

    # Kodak 50D 더 페이드 톤 적용
    base = base.fl_image(apply_kodak50d_fade_tone)

    grain = (
        VideoFileClip(str(GRAIN_FILE))
        .loop(duration=base.duration)
        .resize(base.size)
        .set_opacity(0.35)   # 페이드니까 그레인은 조금 더 보이게
    )

    leak = (
        VideoFileClip(str(LEAK_FILE))
        .loop(duration=base.duration)
        .resize(base.size)
        .set_opacity(0.10)   # leak는 낮게
    )

    comp = CompositeVideoClip([base, grain, leak]).set_audio(base.audio)

    return comp


# ========== 5. 24fps 효과 세그먼트 생성 ==========

def make_24fps_effect_segment(duration_sec: float):
    eff = VideoFileClip(str(EFFECT_24FPS_FILE))

    if eff.duration < duration_sec:
        eff = eff.loop(duration=duration_sec)

    eff = (
        eff.subclip(0, duration_sec)
            .resize(width=TARGET_WIDTH)
            .set_fps(TARGET_FPS)
            .without_audio()
    )

    return eff


# ========== 6. 최종 타임라인 구성 ==========

def build_timeline():
    sources = load_source_files_sorted()   # 자동 정렬된 파일 목록

    clips = [process_clip_kodak50d_fade(f) for f in sources]

    intro = make_24fps_effect_segment(2.0)
    mid = make_24fps_effect_segment(1.0)
    outro = make_24fps_effect_segment(2.0)

    # 예:
    # intro → clip1 → mid → clip2 → mid → clip3 → outro
    timeline = [intro]

    for idx, c in enumerate(clips):
        timeline.append(c)
        if idx < len(clips) - 1:
            timeline.append(mid)

    timeline.append(outro)

    final = concatenate_videoclips(timeline, method="compose")
    return final


# ========== 7. 메인 실행 ==========

if __name__ == "__main__":
    print("[START] Kodak 50D Fade Super8mm 렌더링")

    final_clip = build_timeline()

    print(f"[WRITE] 출력 파일: {OUTPUT_PATH}")
    final_clip.write_videofile(
        str(OUTPUT_PATH),
        codec="libx264",
        audio_codec="aac",
        fps=TARGET_FPS,
        bitrate="8M",
        preset="medium",
        threads=4,
    )

    print("[DONE] 렌더링 완료!")
