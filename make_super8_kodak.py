import re
import numpy as np
from pathlib import Path
from moviepy.editor import VideoFileClip, CompositeVideoClip, concatenate_videoclips, ColorClip

# ========== 1. 경로 설정 ==========
SOURCE_DIR = Path("영상위치")
ASSET_DIR = Path("8mm효과소스위치")

GRAIN_FILE = ASSET_DIR / "Super 8 Grain.mp4"
LEAK_FILE = ASSET_DIR / "Film Light Leak.mp4"
EFFECT_24FPS_FILE = ASSET_DIR / "Super 8 24fps.mp4"

# ========== 2. 비율 및 해상도 설정 ==========
TARGET_RATIO = 4/3
TARGET_HEIGHT = 1080
TARGET_WIDTH = int(TARGET_HEIGHT * TARGET_RATIO) 
TARGET_FPS = 24

OUTPUT_DIR = Path.home() / "super8_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "Kodak50D.mp4"

# ========== 3. 유틸리티 함수 ==========

def extract_number(filename: str):
    match = re.search(r'(\d+)', filename)
    return int(match.group()) if match else 999999

def load_source_files_sorted():
    exts = ["*.MOV", "*.mov", "*.MP4", "*.mp4"]
    files = []
    for e in exts: files.extend(SOURCE_DIR.glob(e))
    return sorted(files, key=lambda f: extract_number(f.name))

def apply_kodak50d_fade_tone(img):
    arr = img.astype("float32") / 255.0
    arr = arr * 0.88 + 0.06
    arr = (arr - 0.5) * 1.02 + 0.5
    r, g, b = arr[:,:,0]*1.05+0.02, arr[:,:,1]*1.03+0.01, arr[:,:,2]*0.97
    return (np.clip(np.stack([r,g,b], axis=2), 0, 1) * 255).astype("uint8")

def fit_to_target(clip, target_w, target_h):
    # 가로/세로 중 어디에 맞출지 계산
    scale_h = target_h / clip.h
    scale_w = target_w / clip.w
    scale = min(scale_h, scale_w)
    
    clip_resized = clip.resize(scale)
    bg = ColorClip(size=(target_w, target_h), color=(0,0,0)).set_duration(clip.duration)
    return CompositeVideoClip([bg, clip_resized.set_position("center")])

# ========== 4. 클립 처리 로직 (with문 제거) ==========

def process_clip_kodak50d_fade(path: Path):
    print(f"[PROCESS] 처리 중: {path.name}")
    
    # 여기서 clip을 닫지 않고 반환합니다.
    clip = VideoFileClip(str(path))
    base = fit_to_target(clip, TARGET_WIDTH, TARGET_HEIGHT).set_fps(TARGET_FPS)
    base = base.fl_image(apply_kodak50d_fade_tone)

    # 효과 레이어
    grain = (VideoFileClip(str(GRAIN_FILE))
             .loop(duration=base.duration)
             .resize(width=TARGET_WIDTH, height=TARGET_HEIGHT)
             .set_opacity(0.35))
    
    leak = (VideoFileClip(str(LEAK_FILE))
            .loop(duration=base.duration)
            .resize(width=TARGET_WIDTH, height=TARGET_HEIGHT)
            .set_opacity(0.10))

    # 오버레이 소스들은 오디오가 없으므로 base의 오디오를 명시적으로 유지
    comp = CompositeVideoClip([base, grain, leak]).set_audio(base.audio)
    return comp

def make_effect_segment(duration_sec: float):
    eff = VideoFileClip(str(EFFECT_24FPS_FILE))
    if eff.duration < duration_sec:
        eff = eff.loop(duration=duration_sec)
    
    eff_sub = eff.subclip(0, duration_sec)
    return fit_to_target(eff_sub, TARGET_WIDTH, TARGET_HEIGHT).set_fps(TARGET_FPS).without_audio()

# ========== 5. 메인 실행 ==========

if __name__ == "__main__":
    sources = load_source_files_sorted()
    if not sources:
        print("파일 없음"); exit()

    # 클립 리스트 생성
    processed_clips = [process_clip_kodak50d_fade(f) for f in sources]

    # 인트로/미드롤/아웃트로 생성
    intro = make_effect_segment(2.0)
    mid = make_effect_segment(1.0)
    outro = make_effect_segment(2.0)

    timeline = [intro]
    for idx, c in enumerate(processed_clips):
        timeline.append(c)
        if idx < len(processed_clips) - 1:
            timeline.append(mid)
    timeline.append(outro)

    final = concatenate_videoclips(timeline, method="compose")
    
    print(f"[WRITE] 시작: {OUTPUT_PATH}")
    # 오디오 인코딩 에러 방지를 위해 temp_audiofile 활용 및 파라미터 최적화
    final.write_videofile(
        str(OUTPUT_PATH),
        codec="libx264",
        audio_codec="aac",
        fps=TARGET_FPS,
        threads=4,
        preset="ultrafast" # 테스트를 위해 속도 우선, 나중에 medium으로 변경 가능
    )

    print("[DONE] 완료!")